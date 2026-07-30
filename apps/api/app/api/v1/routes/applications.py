from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, BackgroundTasks, Query, status

from app.api.deps import CurrentCandidate, CurrentManager, Paginate, ServiceCaller
from app.integrations import match_webhook
from app.models.enums import PipelineStage
from app.schemas.application import (
    ApplicationCandidateOut,
    ApplicationCreateIn,
    ApplicationManagerOut,
    MatchIn,
    MatchOut,
    NoteIn,
    RatingIn,
    ShortlistIn,
    StageChangeIn,
)
from app.schemas.calendar import (
    AgentTurnIn,
    AgentTurnOut,
    AwaitingInterviewOut,
    BookInterviewIn,
    InterviewActionOut,
)
from app.schemas.common import Page
from app.services import application_service, calendar_service

router = APIRouter(prefix="/applications", tags=["applications"])


# ── candidate ────────────────────────────────────────────────────────────────

@router.post("", response_model=ApplicationCandidateOut, status_code=status.HTTP_201_CREATED)
async def apply_to_job(
    data: ApplicationCreateIn, candidate: CurrentCandidate, background: BackgroundTasks
) -> ApplicationCandidateOut:
    application = await application_service.apply(candidate, data)
    # After the response is sent, nudge the AI team to score this pair. Best-
    # effort: apply has already succeeded and a failed ping is caught by their
    # pending-applications poll.
    background.add_task(
        match_webhook.notify_application,
        application.id,
        application.candidate_id,
        application.job_id,
    )
    return ApplicationCandidateOut.build(application)


@router.get("/me", response_model=Page[ApplicationCandidateOut])
async def my_applications(
    candidate: CurrentCandidate,
    page: Paginate,
    stage: Annotated[PipelineStage | None, Query()] = None,
) -> Page[ApplicationCandidateOut]:
    items, total = await application_service.list_for_candidate(
        candidate, skip=page.skip, limit=page.page_size, stage=stage
    )
    return Page.build(
        [ApplicationCandidateOut.build(a) for a in items], total, page.page, page.page_size
    )


@router.get("/me/awaiting-interview", response_model=list[AwaitingInterviewOut])
async def my_awaiting_interview(candidate: CurrentCandidate) -> list[AwaitingInterviewOut]:
    """What the floating booking widget polls to decide whether to show
    itself — deliberately cheaper than the full /applications/me list.
    Declared above /me/{application_id} so 'awaiting-interview' is never
    swallowed as a (malformed) application id, same caution as /interviews
    below."""
    items = await calendar_service.list_awaiting_candidate(candidate)
    return [
        AwaitingInterviewOut(application_id=a.id, job_title=a.job_snapshot.title) for a in items
    ]


@router.get("/me/{application_id}", response_model=ApplicationCandidateOut)
async def my_application(
    application_id: PydanticObjectId, candidate: CurrentCandidate
) -> ApplicationCandidateOut:
    application = await application_service.get_for_candidate(candidate, application_id)
    return ApplicationCandidateOut.build(application)


@router.post("/{application_id}/withdraw", response_model=ApplicationCandidateOut)
async def withdraw_application(
    application_id: PydanticObjectId, candidate: CurrentCandidate
) -> ApplicationCandidateOut:
    application = await application_service.withdraw(candidate, application_id)
    return ApplicationCandidateOut.build(application)


# ── hiring manager ───────────────────────────────────────────────────────────

@router.get("/manage", response_model=Page[ApplicationManagerOut])
async def list_all_applications(
    _: CurrentManager,
    page: Paginate,
    stage: Annotated[PipelineStage | None, Query()] = None,
) -> Page[ApplicationManagerOut]:
    """Org-wide applicant feed across every job."""
    items, total = await application_service.list_all(
        skip=page.skip, limit=page.page_size, stage=stage
    )
    return Page.build(
        [ApplicationManagerOut.build(a) for a in items], total, page.page, page.page_size
    )


@router.get("/job/{job_id}", response_model=Page[ApplicationManagerOut])
async def list_job_applications(
    job_id: PydanticObjectId,
    _: CurrentManager,
    page: Paginate,
    stage: Annotated[PipelineStage | None, Query()] = None,
    shortlisted_only: Annotated[bool, Query()] = False,
) -> Page[ApplicationManagerOut]:
    items, total = await application_service.list_for_job(
        job_id,
        skip=page.skip,
        limit=page.page_size,
        stage=stage,
        shortlisted_only=shortlisted_only,
    )
    return Page.build(
        [ApplicationManagerOut.build(a) for a in items], total, page.page, page.page_size
    )


@router.get("/interviews", response_model=Page[ApplicationManagerOut])
async def list_upcoming_interviews(
    _: CurrentManager, page: Paginate
) -> Page[ApplicationManagerOut]:
    """Org-wide, sorted by when interviews actually happen — this is what the
    manager Calendar page renders. Declared ahead of GET /{application_id} so
    'interviews' is never swallowed as a (malformed) application id."""
    items, total = await calendar_service.list_upcoming_interviews(
        skip=page.skip, limit=page.page_size
    )
    return Page.build(
        [ApplicationManagerOut.build(a) for a in items], total, page.page, page.page_size
    )


@router.get("/{application_id}", response_model=ApplicationManagerOut)
async def get_application(
    application_id: PydanticObjectId, _: CurrentManager
) -> ApplicationManagerOut:
    application = await application_service.get_or_404(application_id)
    return ApplicationManagerOut.build(application)


@router.patch("/{application_id}/stage", response_model=ApplicationManagerOut)
async def change_stage(
    application_id: PydanticObjectId, data: StageChangeIn, manager: CurrentManager
) -> ApplicationManagerOut:
    application = await application_service.change_stage(
        manager, application_id, data.stage, data.note
    )
    return ApplicationManagerOut.build(application)


@router.patch("/{application_id}/shortlist", response_model=ApplicationManagerOut)
async def set_shortlist(
    application_id: PydanticObjectId, data: ShortlistIn, _: CurrentManager
) -> ApplicationManagerOut:
    application = await application_service.set_shortlisted(application_id, data.is_shortlisted)
    return ApplicationManagerOut.build(application)


@router.patch("/{application_id}/rating", response_model=ApplicationManagerOut)
async def set_rating(
    application_id: PydanticObjectId, data: RatingIn, _: CurrentManager
) -> ApplicationManagerOut:
    application = await application_service.set_rating(application_id, data.rating)
    return ApplicationManagerOut.build(application)


@router.post("/{application_id}/notes", response_model=ApplicationManagerOut)
async def add_note(
    application_id: PydanticObjectId, data: NoteIn, manager: CurrentManager
) -> ApplicationManagerOut:
    application = await application_service.add_note(manager, application_id, data.body)
    return ApplicationManagerOut.build(application)


@router.post("/{application_id}/interview/approve", response_model=ApplicationManagerOut)
async def approve_interview(
    application_id: PydanticObjectId, manager: CurrentManager
) -> ApplicationManagerOut:
    """Approves the candidate for an interview and moves the pipeline stage.
    No calendar call yet — the candidate picks the actual slot via
    POST /{application_id}/interview/book."""
    return await calendar_service.approve_interview(manager, application_id)


@router.post("/{application_id}/interview/book", response_model=InterviewActionOut)
async def book_interview(
    application_id: PydanticObjectId, data: BookInterviewIn, candidate: CurrentCandidate
) -> InterviewActionOut:
    """Candidate books their approved interview onto the shared calendar. A
    'conflict' or 'invalid_request' result is a normal 200 — the slot picker
    retries from it — not an HTTP error."""
    return await calendar_service.book_interview(candidate, application_id, data.date, data.slot)


@router.post("/{application_id}/interview/agent", response_model=AgentTurnOut)
async def interview_agent_turn(
    application_id: PydanticObjectId, data: AgentTurnIn, candidate: CurrentCandidate
) -> AgentTurnOut:
    """One turn of the button-driven booking chat. Stateless — `history` is
    the full prior transcript the client echoes back and gets returned
    again, with this turn's reply appended, so the client never reconstructs
    it itself."""
    return await calendar_service.run_agent_turn(
        candidate, application_id, data.history, data.selected_action
    )


@router.delete("/{application_id}/interview", response_model=ApplicationManagerOut)
async def cancel_interview(
    application_id: PydanticObjectId, manager: CurrentManager
) -> ApplicationManagerOut:
    return await calendar_service.cancel_interview(manager, application_id)


# ── AI team (service token) ──────────────────────────────────────────────────

@router.post("/{application_id}/match", response_model=MatchOut)
async def record_match(
    application_id: PydanticObjectId, data: MatchIn, _: ServiceCaller
) -> MatchOut:
    """Write back the match confidence for an application.

    Machine-to-machine, gated by the service token — a candidate or manager can
    never set a score. The value is frozen once written; re-posting overwrites it.
    """
    application = await application_service.record_match(
        application_id,
        confidence=data.confidence,
        factors=data.factors,
        graph_version=data.graph_version,
    )
    return MatchOut.build(application.match)
