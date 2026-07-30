"""Interview scheduling — the calendar-mcp assistant's request/response shapes,
plus the booking agent's chat turn shapes (see app/integrations/booking_agent/).

`Literal` for `slot` rather than a free string: the three daily interview
slots are a fixed company policy (see calendar-mcp's SLOT_POLICY), not
something a client should be able to invent.
"""

from datetime import date
from typing import Literal

from beanie import PydanticObjectId
from pydantic import BaseModel

InterviewSlot = Literal["13:00-14:00", "14:30-15:30", "16:00-17:00"]


class BookInterviewIn(BaseModel):
    """The candidate's chosen slot for an interview a manager already
    approved — the manager never supplies a date/slot themselves."""

    date: date
    slot: InterviewSlot


class InterviewSlotOut(BaseModel):
    start: str
    end: str
    available: bool


class AvailabilityOut(BaseModel):
    date: date
    slots: list[InterviewSlotOut]


class InterviewActionOut(BaseModel):
    """Result of a booking attempt. 'conflict'/'invalid_request' are
    legitimate business outcomes returned with 200 — the slot picker retries
    from them, they are not error responses.

    No `application` field: this is candidate-facing, and ApplicationOut's
    manager-only fields (notes, rating) must never reach a candidate. Callers
    re-fetch their own view (router.refresh()) after a successful booking.
    """

    status: Literal["scheduled", "conflict", "invalid_request"]
    message: str


class AwaitingInterviewOut(BaseModel):
    """One application of the current candidate's that a manager has approved
    for interview but that has no booked slot yet — what the floating booking
    widget polls for to decide whether to show itself."""

    application_id: PydanticObjectId
    job_title: str


class AgentMessage(BaseModel):
    """One turn of the booking agent chat. `content` is always plain text —
    the button choices that produced a "user" turn are flattened to their
    label before being stored here, never sent back as structured data."""

    role: Literal["user", "assistant"]
    content: str


class AgentButton(BaseModel):
    """A candidate-clickable next step. `id` encodes the action deterministically
    (e.g. "pick_day:2026-08-04", "pick_slot:2026-08-04:14:30-15:30", "retry")
    so a click is unambiguous — the agent never has to infer intent from a
    free-text reply, because there isn't one."""

    id: str
    label: str


class AgentTurnIn(BaseModel):
    """`history` is the full prior transcript, echoed back by the client from
    the previous response — the endpoint is stateless, nothing is kept
    server-side between turns. `selected_action` is the id of the button the
    candidate just clicked; both are empty/null on the very first turn."""

    history: list[AgentMessage] = []
    selected_action: str | None = None


class AgentTurnOut(BaseModel):
    """`history` is echoed back including this turn, so the client never has
    to reconstruct it — it just stores what it's given and resends it
    verbatim on the next click. `done` is true once the interview is booked."""

    message: str
    buttons: list[AgentButton]
    done: bool
    history: list[AgentMessage]
