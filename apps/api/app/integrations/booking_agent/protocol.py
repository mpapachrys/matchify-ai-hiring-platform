"""The contract for the interview-booking chat agent.

This is the platform's **second** LLM call site, alongside the resume parser
(app/integrations/resume_parser) — see that module's docstring and
CLAUDE.md's "LLM use in apps/api" section for why there are now two.

The agent walks a candidate through booking an already-approved interview
slot using nothing but button clicks. It decides what to say and when to call
the two tools below, but the tools themselves are this codebase's own,
already-tested `calendar_service.get_availability` / `calendar_service.
book_interview` — the agent narrates and sequences a real flow, it never
invents booking logic of its own. There is only one implementation
(`openrouter.py`); unlike the resume parser there is no env-selectable stub,
because an unconfigured/failing LLM must still let a candidate book — see
that module's internal deterministic fallback instead.
"""

from collections.abc import Awaitable, Callable
from datetime import date
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from app.schemas.calendar import (
    AgentButton,
    AgentMessage,
    AvailabilityOut,
    InterviewActionOut,
    InterviewSlot,
)


class BookingContext(BaseModel):
    """Everything about the specific application being booked. Handed to the
    agent fresh on every request, from data the platform already trusts —
    never derived from conversation history — so the candidate can never talk
    their way into booking a different application's interview."""

    application_id: str
    job_title: str
    candidate_name: str


class AgentTurnResult(BaseModel):
    message: str
    buttons: list[AgentButton]
    done: bool


#: Bound to one `application_id` by the caller (calendar_service), so the
#: agent itself never handles ownership/authorization — it only ever sees the
#: application it was scoped to.
CheckAvailability = Callable[[date], Awaitable[AvailabilityOut]]
BookSlot = Callable[[date, InterviewSlot], Awaitable[InterviewActionOut]]


@runtime_checkable
class BookingAgent(Protocol):
    async def next_turn(
        self,
        *,
        context: BookingContext,
        history: list[AgentMessage],
        selected_action: str | None,
        check_availability: CheckAvailability,
        book_slot: BookSlot,
    ) -> AgentTurnResult: ...
