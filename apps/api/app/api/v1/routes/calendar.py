from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser
from app.schemas.calendar import AvailabilityOut
from app.services import calendar_service

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/availability", response_model=AvailabilityOut)
async def get_availability(
    _: CurrentUser,
    date: Annotated[date, Query(description="Day to check, YYYY-MM-DD")],
) -> AvailabilityOut:
    """The three fixed interview slots for one day, each flagged free/busy
    against the shared company Google Calendar. Any authenticated user can
    read this — it's just free/busy booleans, nothing candidate- or
    application-specific — but a candidate can only ever *book* through
    their own approved application (see POST .../interview/book)."""
    return await calendar_service.get_availability(date)
