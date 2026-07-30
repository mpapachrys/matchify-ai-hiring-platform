"""Calls the calendar-mcp sidecar for interview scheduling.

Unlike match_webhook.py, this is request/response, not fire-and-forget: a
scheduling click has no other reconciliation path, so a failure here must
reach the caller rather than being logged and swallowed.
"""

import logging
from datetime import date

import httpx

from app.core.config import settings
from app.schemas.calendar import AvailabilityOut, InterviewSlot

logger = logging.getLogger(__name__)

# LLM tool-calling turns (find_events, create_event, ...) can take several
# seconds each across a few iterations — generous enough that the client
# doesn't give up mid-decision.
TIMEOUT = httpx.Timeout(65.0, connect=5.0)


class CalendarAssistantError(Exception):
    """The calendar-mcp service could not complete the request."""


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.calendar_assistant_token}"}


async def get_availability(target_date: date) -> AvailabilityOut:
    url = f"{settings.calendar_assistant_url}/interviews/availability"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(
                url, params={"date": target_date.isoformat()}, headers=_headers()
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("calendar-mcp availability call failed: %s", exc)
        raise CalendarAssistantError(str(exc)) from exc
    return AvailabilityOut.model_validate(response.json())


async def schedule_interview(
    *,
    candidate_name: str,
    candidate_email: str,
    job_title: str,
    target_date: date,
    slot: InterviewSlot,
) -> dict:
    """Returns calendar-mcp's raw decision dict — {"status", "start", "end",
    "event_id", "html_link", "message"}. calendar_service interprets
    "status", since "conflict"/"invalid_request" are legitimate scheduling
    outcomes here, not failures of this call."""
    url = f"{settings.calendar_assistant_url}/interviews/schedule"
    payload = {
        "candidate_name": candidate_name,
        "candidate_email": candidate_email,
        "job_title": job_title,
        "date": target_date.isoformat(),
        "slot": slot,
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(url, json=payload, headers=_headers())
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("calendar-mcp schedule call failed: %s", exc)
        raise CalendarAssistantError(str(exc)) from exc
    return response.json()


async def cancel_interview(event_id: str) -> None:
    url = f"{settings.calendar_assistant_url}/interviews/{event_id}/cancel"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(url, headers=_headers())
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("calendar-mcp cancel call failed: %s", exc)
        raise CalendarAssistantError(str(exc)) from exc
