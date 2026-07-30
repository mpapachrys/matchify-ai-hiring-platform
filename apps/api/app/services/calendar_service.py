"""Interview scheduling orchestration — a two-step flow.

1. `approve_interview` (manager): marks the candidate approved and moves the
   pipeline stage. No calendar call — nothing is booked yet.
2. `book_interview` (candidate): the candidate picks the actual slot. This is
   the only place that calls the calendar assistant to create a real event.

The assistant's own conflict-avoidance decision is authoritative for step 2
— this module never second-guesses "scheduled" vs "conflict", it just
records the outcome.
"""

import logging
from datetime import UTC, date, datetime

from beanie import PydanticObjectId

from app.core.config import settings
from app.core.exceptions import ConflictError, ServiceUnavailableError
from app.integrations import booking_agent, calendar_assistant
from app.integrations.booking_agent import BookingContext
from app.integrations.calendar_assistant import CalendarAssistantError
from app.models.application import Application
from app.models.enums import TERMINAL_STAGES, InterviewStatus, PipelineStage
from app.models.user import User
from app.schemas.application import ApplicationManagerOut
from app.schemas.calendar import (
    AgentMessage,
    AgentTurnOut,
    AvailabilityOut,
    InterviewActionOut,
    InterviewSlot,
)
from app.services import application_service

logger = logging.getLogger(__name__)


def _require_configured() -> None:
    if not settings.calendar_assistant_url:
        raise ServiceUnavailableError(
            "Calendar assistant is not configured. "
            "Set CALENDAR_ASSISTANT_URL to enable interview scheduling."
        )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


async def get_availability(target_date: date) -> AvailabilityOut:
    _require_configured()
    try:
        return await calendar_assistant.get_availability(target_date)
    except CalendarAssistantError as exc:
        raise ServiceUnavailableError("Calendar assistant is unreachable") from exc


async def approve_interview(
    manager: User, application_id: PydanticObjectId
) -> ApplicationManagerOut:
    """Manager-side step 1: approve, don't book. The candidate picks the slot."""
    _require_configured()

    application = await application_service.get_or_404(application_id)
    if application.stage in TERMINAL_STAGES:
        raise ConflictError(
            f"Cannot approve an interview for an application in '{application.stage}' stage"
        )
    already_in_progress = (InterviewStatus.AWAITING_CANDIDATE, InterviewStatus.SCHEDULED)
    if application.interview.status in already_in_progress:
        raise ConflictError(
            "An interview has already been approved or scheduled for this application"
        )

    application.interview.status = InterviewStatus.AWAITING_CANDIDATE
    application.interview.approved_by = manager.id
    application.interview.approved_at = datetime.now(UTC)
    await application.save()

    # Reuses the single stage-transition/history code path rather than
    # duplicating it — also handles the shortlist side-effect and job
    # counter resync that change_stage already does.
    application = await application_service.change_stage(
        manager,
        application_id,
        PipelineStage.INTERVIEW,
        note="Approved for interview — awaiting the candidate to pick a slot",
    )
    return ApplicationManagerOut.build(application)


async def book_interview(
    candidate: User,
    application_id: PydanticObjectId,
    target_date: date,
    slot: InterviewSlot,
) -> InterviewActionOut:
    """Candidate-side step 2: picks the slot, this is what actually creates
    the Google Calendar event. Fails if the manager never approved one."""
    _require_configured()

    application = await application_service.get_for_candidate(candidate, application_id)
    if application.interview.status != InterviewStatus.AWAITING_CANDIDATE:
        raise ConflictError("This application is not awaiting an interview slot")

    try:
        result = await calendar_assistant.schedule_interview(
            candidate_name=application.candidate_snapshot.full_name,
            candidate_email=application.candidate_snapshot.email,
            job_title=application.job_snapshot.title,
            target_date=target_date,
            slot=slot,
        )
    except CalendarAssistantError as exc:
        raise ServiceUnavailableError("Calendar assistant is unreachable") from exc

    outcome = result.get("status")
    message = result.get("message") or ""

    if outcome == "scheduled":
        application.interview.status = InterviewStatus.SCHEDULED
        application.interview.event_id = result.get("event_id")
        application.interview.html_link = result.get("html_link")
        application.interview.scheduled_start = _parse_dt(result.get("start"))
        application.interview.scheduled_end = _parse_dt(result.get("end"))
        application.interview.scheduled_by = candidate.id
        application.interview.scheduled_at = datetime.now(UTC)
        application.interview.cancelled_at = None
        await application.save()
        return InterviewActionOut(status="scheduled", message=message or "Interview booked.")

    if outcome in ("conflict", "invalid_request"):
        # Legitimate outcomes, not failures — stays AWAITING_CANDIDATE so
        # the candidate can retry from the slot picker.
        return InterviewActionOut(status=outcome, message=message or "Could not book that slot.")

    logger.error("calendar assistant returned unexpected status %r: %s", outcome, message)
    raise ServiceUnavailableError("Calendar assistant could not complete the request")


async def cancel_interview(
    manager: User, application_id: PydanticObjectId
) -> ApplicationManagerOut:
    """Cancels a booked interview, or — if the candidate hasn't booked yet —
    revokes the approval. Either way this is a manager action."""
    _require_configured()

    application = await application_service.get_or_404(application_id)

    if application.interview.status == InterviewStatus.SCHEDULED:
        if application.interview.event_id:
            try:
                await calendar_assistant.cancel_interview(application.interview.event_id)
            except CalendarAssistantError as exc:
                raise ServiceUnavailableError("Calendar assistant is unreachable") from exc
        application.interview.status = InterviewStatus.CANCELLED
        application.interview.cancelled_at = datetime.now(UTC)
    elif application.interview.status == InterviewStatus.AWAITING_CANDIDATE:
        # Nothing was ever booked on the calendar — just revoke the approval.
        application.interview.status = InterviewStatus.NONE
        application.interview.approved_by = None
        application.interview.approved_at = None
    else:
        raise ConflictError("This application has no interview to cancel")

    await application.save()
    return ApplicationManagerOut.build(application)


async def list_awaiting_candidate(candidate: User) -> list[Application]:
    """Applications of this candidate's that a manager approved for interview
    but that have no booked slot yet — backs the cheap polling endpoint the
    floating booking widget uses to decide whether to show itself, so it
    deliberately doesn't reuse the full `/applications/me` payload."""
    query = {
        "candidate_id": candidate.id,
        "interview.status": InterviewStatus.AWAITING_CANDIDATE.value,
    }
    return await Application.find(query).to_list()


async def run_agent_turn(
    candidate: User,
    application_id: PydanticObjectId,
    history: list[AgentMessage],
    selected_action: str | None,
) -> AgentTurnOut:
    """One turn of the booking chat agent. Stateless: `history` is the full
    prior transcript the client echoes back, nothing is kept server-side
    between turns. The agent's two tools are bound here to this specific,
    already-ownership-checked application, so it can never act on any other
    candidate's or job's interview."""
    _require_configured()

    application = await application_service.get_for_candidate(candidate, application_id)
    if application.interview.status != InterviewStatus.AWAITING_CANDIDATE:
        raise ConflictError("This application is not awaiting an interview slot")

    context = BookingContext(
        application_id=str(application.id),
        job_title=application.job_snapshot.title,
        candidate_name=application.candidate_snapshot.full_name or "",
    )

    async def _check_availability(target_date: date) -> AvailabilityOut:
        return await get_availability(target_date)

    async def _book_slot(target_date: date, slot: InterviewSlot) -> InterviewActionOut:
        return await book_interview(candidate, application_id, target_date, slot)

    result = await booking_agent.get_agent().next_turn(
        context=context,
        history=history,
        selected_action=selected_action,
        check_availability=_check_availability,
        book_slot=_book_slot,
    )

    return AgentTurnOut(
        message=result.message,
        buttons=result.buttons,
        done=result.done,
        history=[*history, AgentMessage(role="assistant", content=result.message)],
    )


async def list_upcoming_interviews(*, skip: int, limit: int) -> tuple[list[Application], int]:
    """Approved-but-unbooked and booked interviews together, sorted so items
    still needing the candidate's attention (no scheduled_start yet) surface
    first. Filters on interview.status, not stage == INTERVIEW — a manager
    can move stages without booking, or cancel a booking without moving
    stages, so the two signals are not the same thing."""
    query = {
        "interview.status": {
            "$in": [InterviewStatus.AWAITING_CANDIDATE.value, InterviewStatus.SCHEDULED.value]
        }
    }
    cursor = Application.find(query)
    total = await cursor.count()
    items = await cursor.sort("interview.scheduled_start").skip(skip).limit(limit).to_list()
    return items, total
