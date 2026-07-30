"""HTTP surface for Matchify's interview scheduling feature.

This is the ONLY thing apps/api talks to in this container. It keeps one
long-lived MCP session open to run_server.py (spawned as a stdio subprocess,
exactly like agent.py does interactively) and exposes four plain endpoints:

    GET  /health
    GET  /interviews/availability?date=YYYY-MM-DD   — LLM-free, direct MCP tool call
    POST /interviews/schedule                        — LLM + MCP tool-calling loop
    POST /interviews/{event_id}/cancel                — LLM-free, direct MCP tool call

The actual conflict-avoidance *decision* (schedule vs. conflict) always goes
through the LLM+MCP path in src/scheduling_agent.py — that's the one place
the booking policy lives. Reads and deletes are unambiguous, so they skip the
model and call the MCP tool directly.
"""
import asyncio
import contextlib
import json
import logging
import os
import secrets
import sys
from collections.abc import Awaitable, Callable
from datetime import date as date_type
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, EmailStr

from src.scheduling_agent import SLOT_POLICY, mcp_tool_to_openai_tool, run_scheduling_decision

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
RUN_SERVER = os.path.join(PROJECT_DIR, "run_server.py")

CALENDAR_ASSISTANT_TOKEN = os.getenv("CALENDAR_ASSISTANT_TOKEN", "")

# All slot math happens in this timezone regardless of the container's OS
# clock, so "13:00" always means 13:00 in the company's own timezone. The
# Dockerfile also sets the OS TZ to the same value so mcp_bridge.py's event
# creation (which stamps the machine's local UTC offset) agrees with it.
LOCAL_TZ = ZoneInfo("Europe/Athens")

SLOT_LABELS = [f"{start}-{end}" for start, end in SLOT_POLICY]


# ── request/response models ──────────────────────────────────────────────

class ScheduleIn(BaseModel):
    candidate_name: str
    candidate_email: EmailStr
    job_title: str
    date: date_type
    slot: str


class SlotOut(BaseModel):
    start: str
    end: str
    available: bool


class AvailabilityOut(BaseModel):
    date: date_type
    slots: list[SlotOut]


class ScheduleResultOut(BaseModel):
    status: str
    start: str | None = None
    end: str | None = None
    event_id: str | None = None
    html_link: str | None = None
    message: str


class CancelResultOut(BaseModel):
    status: str


# ── MCP session lifecycle ────────────────────────────────────────────────

async def _connect(app: FastAPI) -> None:
    stack = contextlib.AsyncExitStack()
    server_env = os.environ.copy()
    server_env["RELOAD"] = "false"  # avoid uvicorn's reload supervisor under stdio
    params = StdioServerParameters(command=sys.executable, args=[RUN_SERVER], env=server_env)

    read, write = await stack.enter_async_context(stdio_client(params))
    session = await stack.enter_async_context(ClientSession(read, write))
    await session.initialize()
    tools_result = await session.list_tools()
    openai_tools = [mcp_tool_to_openai_tool(t) for t in tools_result.tools]

    app.state.exit_stack = stack
    app.state.session = session
    app.state.openai_tools = openai_tools
    logger.info("Connected to calendar-mcp subprocess (%d tools).", len(openai_tools))


async def _reconnect(app: FastAPI) -> None:
    with contextlib.suppress(Exception):
        await app.state.exit_stack.aclose()
    await _connect(app)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.lock = asyncio.Lock()
    await _connect(app)
    try:
        yield
    finally:
        await app.state.exit_stack.aclose()


app = FastAPI(title="Matchify Calendar Assistant", lifespan=lifespan)


async def _with_retry(fn: Callable[[ClientSession, list], Awaitable]):
    """Runs fn(session, tools) under the shared lock; reconnects once and
    retries on failure (the subprocess/pipe can die between requests)."""
    async with app.state.lock:
        try:
            return await fn(app.state.session, app.state.openai_tools)
        except Exception:
            logger.warning("MCP call failed, reconnecting once", exc_info=True)
            try:
                await _reconnect(app)
            except Exception as exc:
                raise HTTPException(status_code=502, detail="Calendar subprocess unavailable") from exc
            try:
                return await fn(app.state.session, app.state.openai_tools)
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Calendar service call failed: {exc}") from exc


def _tool_text(result) -> str:
    return "\n".join(block.text for block in result.content if hasattr(block, "text"))


def _tool_json(result) -> dict:
    try:
        return json.loads(_tool_text(result))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Calendar service returned an unexpected response") from exc


# ── auth ──────────────────────────────────────────────────────────────────

def require_matchify_token(authorization: str | None = Header(default=None)) -> None:
    if not CALENDAR_ASSISTANT_TOKEN:
        raise HTTPException(status_code=503, detail="CALENDAR_ASSISTANT_TOKEN is not configured")
    expected = f"Bearer {CALENDAR_ASSISTANT_TOKEN}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")


# ── availability ──────────────────────────────────────────────────────────

def _slot_bounds(target_date: date_type, start_str: str, end_str: str) -> tuple[datetime, datetime]:
    sh, sm = (int(part) for part in start_str.split(":"))
    eh, em = (int(part) for part in end_str.split(":"))
    start = datetime(target_date.year, target_date.month, target_date.day, sh, sm, tzinfo=LOCAL_TZ)
    end = datetime(target_date.year, target_date.month, target_date.day, eh, em, tzinfo=LOCAL_TZ)
    return start, end


def _extract_busy_intervals(
    events_payload: dict, day_start: datetime, day_end: datetime
) -> list[tuple[datetime, datetime]]:
    busy: list[tuple[datetime, datetime]] = []
    for item in events_payload.get("items", []):
        start_field = item.get("start", {}) or {}
        end_field = item.get("end", {}) or {}
        if "dateTime" in start_field and "dateTime" in end_field:
            try:
                busy.append(
                    (datetime.fromisoformat(start_field["dateTime"]), datetime.fromisoformat(end_field["dateTime"]))
                )
            except ValueError:
                continue
        elif "date" in start_field:
            # All-day event — no reliable time boundary, treat as busy all day.
            busy.append((day_start, day_end))
    return busy


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get(
    "/interviews/availability",
    response_model=AvailabilityOut,
    dependencies=[Depends(require_matchify_token)],
)
async def get_availability(date: date_type = Query(...)) -> AvailabilityOut:
    if date.weekday() >= 5:  # Saturday/Sunday — never bookable
        return AvailabilityOut(
            date=date, slots=[SlotOut(start=s, end=e, available=False) for s, e in SLOT_POLICY]
        )

    day_start = datetime(date.year, date.month, date.day, 0, 0, tzinfo=LOCAL_TZ)
    day_end = day_start + timedelta(days=1)

    result = await _with_retry(
        lambda session, _tools: session.call_tool(
            "find_events",
            {
                "calendar_id": "primary",
                "time_min": day_start.isoformat(),
                "time_max": day_end.isoformat(),
            },
        )
    )
    payload = _tool_json(result)
    if "error" in payload:
        raise HTTPException(status_code=502, detail=payload["error"])

    busy_intervals = _extract_busy_intervals(payload, day_start, day_end)
    slots = []
    for start_str, end_str in SLOT_POLICY:
        slot_start, slot_end = _slot_bounds(date, start_str, end_str)
        conflict = any(slot_start < busy_end and slot_end > busy_start for busy_start, busy_end in busy_intervals)
        slots.append(SlotOut(start=start_str, end=end_str, available=not conflict))

    return AvailabilityOut(date=date, slots=slots)


# ── schedule ──────────────────────────────────────────────────────────────

@app.post(
    "/interviews/schedule",
    response_model=ScheduleResultOut,
    dependencies=[Depends(require_matchify_token)],
)
async def schedule_interview(data: ScheduleIn) -> ScheduleResultOut:
    if data.slot not in SLOT_LABELS:
        raise HTTPException(status_code=422, detail=f"slot must be one of {SLOT_LABELS}")
    if data.date.weekday() >= 5:
        return ScheduleResultOut(
            status="invalid_request",
            message="Interviews are only scheduled Monday through Friday.",
        )

    instruction = (
        f"Schedule a 1-hour interview on {data.date.isoformat()} in the {data.slot} slot "
        f"for {data.candidate_name} regarding the '{data.job_title}' role. "
        "Use calendar_id 'primary'. Title the event with exactly the job title, nothing else: "
        f"'{data.job_title}'. "
        f"Add {data.candidate_email} as the only attendee."
    )

    result = await _with_retry(
        lambda session, tools: run_scheduling_decision(session, tools, instruction)
    )
    return ScheduleResultOut(**result)


# ── cancel ────────────────────────────────────────────────────────────────

@app.post(
    "/interviews/{event_id}/cancel",
    response_model=CancelResultOut,
    dependencies=[Depends(require_matchify_token)],
)
async def cancel_interview(event_id: str) -> CancelResultOut:
    result = await _with_retry(
        lambda session, _tools: session.call_tool(
            "delete_event", {"calendar_id": "primary", "event_id": event_id}
        )
    )
    payload = _tool_json(result)
    if "error" in payload:
        detail = str(payload["error"])
        status_code = 404 if ("404" in detail or "410" in detail) else 502
        raise HTTPException(status_code=status_code, detail=detail)
    return CancelResultOut(status="cancelled")
