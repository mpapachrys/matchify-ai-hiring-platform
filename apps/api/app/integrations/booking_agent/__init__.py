"""Agent selection. A single implementation today (OpenRouterBookingAgent,
which falls back to a scripted flow internally on any LLM failure) — unlike
resume_parser there is no env-selectable stub, because this always needs to
produce a working booking flow, not just a cheap one for local dev.
"""

from functools import lru_cache

from app.integrations.booking_agent.openrouter import OpenRouterBookingAgent
from app.integrations.booking_agent.protocol import AgentTurnResult, BookingAgent, BookingContext

__all__ = ["get_agent", "BookingAgent", "BookingContext", "AgentTurnResult"]


@lru_cache
def get_agent() -> BookingAgent:
    return OpenRouterBookingAgent()
