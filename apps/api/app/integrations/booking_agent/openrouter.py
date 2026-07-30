"""LLM-driven engine for the interview-booking chat, called through OpenRouter.

Same transport pattern as resume_parser/openrouter.py (plain httpx over the
OpenAI-compatible /chat/completions endpoint, defensive JSON parsing) but a
bounded tool-calling loop instead of a single completion — structurally
closer to mcp_calendar/src/scheduling_agent.py's `handle_message`, adapted to
this codebase's async/httpx style and to two in-process tools instead of an
MCP session.

Two design choices worth knowing:

* **The model never invents a date.** Every turn's directive to the model
  ("instruction" below) is built server-side from real data — the next real
  weekdays, or a tool's actual response — the same trick
  mcp_calendar/interview_api.py already uses for the same reason: an LLM
  asked to reason about calendars unprompted will happily offer a Saturday.
* **Every failure degrades to a small deterministic flow**, not an error.
  A missing API key, a timeout, a malformed reply, an exhausted tool-call
  budget — all fall back to `_fallback_turn`, which drives the exact same
  `check_availability`/`book_slot` tools with canned copy. A candidate must
  never be stuck mid-booking because the LLM had a bad day.
"""

import json
import logging
import re
from datetime import date, timedelta
from typing import get_args

import httpx

from app.core.config import settings
from app.integrations.booking_agent.protocol import (
    AgentTurnResult,
    BookingContext,
    BookSlot,
    CheckAvailability,
)
from app.schemas.calendar import AgentButton, AgentMessage, InterviewSlot

logger = logging.getLogger(__name__)

# A chat turn should feel snappy — unlike resume parsing's 90s budget, at most
# one or two tool round-trips happen here.
TIMEOUT = httpx.Timeout(30.0, connect=10.0)

MAX_TOOL_ITERATIONS = 4

SLOT_LABELS: dict[str, str] = {
    "13:00-14:00": "1:00 – 2:00 PM",
    "14:30-15:30": "2:30 – 3:30 PM",
    "16:00-17:00": "4:00 – 5:00 PM",
}

SYSTEM_PROMPT = """\
You are Matchify's interview-booking assistant, chatting with a candidate who
has already been approved for an interview.

Tone: warm, professional, concise — one or two sentences per reply. Never
robotic, never salesy.

Hard rules:
- The candidate can ONLY act through buttons. Never ask them to type
  anything, and never phrase a reply as a question expecting free text.
- Every reply except the final booking confirmation must offer at least one
  button.
- Never mention tools, function calls, APIs, JSON, or any other internal
  mechanics in your message text.
- Only ever offer a day or time that a tool actually returned as real —
  never invent a date or slot yourself.
- Once you are ready to reply to the candidate, your FINAL reply must be
  ONLY a single JSON object — no prose before or after it, no markdown code
  fence — with exactly this shape:
  {"message": "<what the candidate sees>",
   "buttons": [{"id": "<button id>", "label": "<short button text>"}],
   "done": <true only once the interview is actually booked>}
"""


def _next_weekdays(count: int) -> list[date]:
    """Next `count` Mon–Fri dates starting tomorrow — interviews are weekday-
    only, so weekends are never offered in the first place."""
    days: list[date] = []
    cursor = date.today() + timedelta(days=1)
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _format_day_label(value: date) -> str:
    return f"{value.strftime('%A')}, {value.day} {value.strftime('%B')}"


def _parse_action(selected_action: str | None) -> tuple[str, str | None, str | None]:
    """Button ids are the whole interface for "what did the candidate click" —
    see AgentButton's docstring. Parsed with a bounded split since a slot
    string ("14:30-15:30") itself contains colons."""
    if not selected_action or selected_action == "retry":
        return "start", None, None
    if selected_action.startswith("pick_day:"):
        return "pick_day", selected_action.split(":", 1)[1], None
    if selected_action.startswith("pick_slot:"):
        _, day, slot = selected_action.split(":", 2)
        return "pick_slot", day, slot
    return "start", None, None


def _build_instruction(
    context: BookingContext, kind: str, day_str: str | None, slot_str: str | None
) -> str:
    if kind == "pick_day":
        target = date.fromisoformat(day_str)  # type: ignore[arg-type]
        return (
            f"The candidate clicked to see times on {_format_day_label(target)} "
            f"({target.isoformat()}). Call check_availability for that exact date, then offer "
            'only the slots it returns as available, each as a button with id '
            f'"pick_slot:{target.isoformat()}:<slot>" (slot exactly as returned, e.g. '
            '"14:30-15:30") and a friendly human-readable label. If none are available, '
            'apologize briefly and instead offer 2-3 other upcoming weekdays as '
            '"pick_day:<YYYY-MM-DD>" buttons; done stays false.'
        )
    if kind == "pick_slot":
        target = date.fromisoformat(day_str)  # type: ignore[arg-type]
        return (
            f"The candidate clicked to book {_format_day_label(target)}, {slot_str}. Call "
            f'book_slot for date="{target.isoformat()}", slot="{slot_str}". If the result '
            'status is "scheduled", warmly confirm the booking in your message, return an '
            'empty buttons list, and set done=true. If the result status is "conflict" or '
            '"invalid_request", apologize, call check_availability again for '
            f"{target.isoformat()}, and offer the remaining real slots (or other weekdays if "
            "none are left) as buttons; done stays false."
        )
    first_name = context.candidate_name.split(" ")[0] if context.candidate_name else "there"
    days = ", ".join(
        f'"pick_day:{d.isoformat()}" ({_format_day_label(d)})' for d in _next_weekdays(5)
    )
    return (
        f'{first_name} was just approved for an interview for the "{context.job_title}" role '
        "and has just opened this booking assistant for the first time. Greet them warmly and "
        "professionally in one or two sentences, mention they'll pick a day and then a time, "
        f"and offer exactly these weekday options as buttons (use the ids exactly as given): "
        f"{days}. Do not call any tool yet."
    )


def _tool_defs() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "check_availability",
                "description": "Look up real bookable interview time slots for one weekday date.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "ISO date, YYYY-MM-DD"},
                    },
                    "required": ["date"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "book_slot",
                "description": "Book the interview onto the shared calendar for one date and slot.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "ISO date, YYYY-MM-DD"},
                        "slot": {"type": "string", "enum": list(get_args(InterviewSlot))},
                    },
                    "required": ["date", "slot"],
                },
            },
        },
    ]


_TOOL_DEFS = _tool_defs()


def _extract_json(content: str) -> dict | None:
    """Same defensive parse as resume_parser/openrouter.py:_extract_json —
    models wrap JSON in fences or add a preamble depending on which model
    OpenRouter routed to, so parse leniently rather than force a
    response_format not every routed model supports."""
    content = content.strip()

    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", content, re.DOTALL)
    if fenced:
        content = fenced.group(1).strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    start, end = content.find("{"), content.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


def _parse_reply(content: str) -> AgentTurnResult | None:
    data = _extract_json(content)
    if data is None:
        return None
    try:
        return AgentTurnResult(
            message=data["message"],
            buttons=[AgentButton(**b) for b in data.get("buttons", [])],
            done=bool(data.get("done", False)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("booking agent: malformed structured reply — %s", exc)
        return None


def _day_buttons(*, exclude: date | None = None, count: int = 5) -> list[AgentButton]:
    days = [d for d in _next_weekdays(count + 1) if d != exclude][:count]
    return [AgentButton(id=f"pick_day:{d.isoformat()}", label=_format_day_label(d)) for d in days]


async def _fallback_turn(
    context: BookingContext,
    kind: str,
    day_str: str | None,
    slot_str: str | None,
    check_availability: CheckAvailability,
    book_slot: BookSlot,
) -> AgentTurnResult:
    """Scripted equivalent of the LLM flow — same two tools, canned copy.
    What actually keeps booking working when OpenRouter is unconfigured or
    misbehaving."""
    if kind == "pick_day":
        target = date.fromisoformat(day_str)  # type: ignore[arg-type]
        availability = await check_availability(target)
        free = [s for s in availability.slots if s.available]
        if not free:
            return AgentTurnResult(
                message=f"No open times on {_format_day_label(target)} — here are some other days:",
                buttons=_day_buttons(exclude=target),
                done=False,
            )
        return AgentTurnResult(
            message=f"Here's what's open on {_format_day_label(target)}:",
            buttons=[
                AgentButton(
                    id=f"pick_slot:{target.isoformat()}:{s.start}-{s.end}",
                    label=SLOT_LABELS.get(f"{s.start}-{s.end}", f"{s.start} – {s.end}"),
                )
                for s in free
            ],
            done=False,
        )

    if kind == "pick_slot":
        target = date.fromisoformat(day_str)  # type: ignore[arg-type]
        result = await book_slot(target, slot_str)  # type: ignore[arg-type]
        if result.status == "scheduled":
            return AgentTurnResult(
                message=result.message or "You're all set — the interview is booked.",
                buttons=[],
                done=True,
            )
        return AgentTurnResult(
            message=f"{result.message} Let's try another day:",
            buttons=_day_buttons(),
            done=False,
        )

    first_name = context.candidate_name.split(" ")[0] if context.candidate_name else "there"
    return AgentTurnResult(
        message=(
            f"Good news, {first_name} — you're approved for an interview for {context.job_title}. "
            "Pick a day that works for you:"
        ),
        buttons=_day_buttons(),
        done=False,
    )


class OpenRouterBookingAgent:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.openrouter_api_key
        self.model = model or settings.ai_model
        self.base_url = settings.openrouter_base_url.rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
            "http-referer": settings.org_website,
            "x-title": f"{settings.org_name} Hiring Platform",
        }

    async def next_turn(
        self,
        *,
        context: BookingContext,
        history: list[AgentMessage],
        selected_action: str | None,
        check_availability: CheckAvailability,
        book_slot: BookSlot,
    ) -> AgentTurnResult:
        kind, day_str, slot_str = _parse_action(selected_action)

        if not self.is_configured:
            logger.warning("booking agent: OPENROUTER_API_KEY not set — using scripted fallback")
            return await _fallback_turn(
                context, kind, day_str, slot_str, check_availability, book_slot
            )

        instruction = _build_instruction(context, kind, day_str, slot_str)
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += [{"role": m.role, "content": m.content} for m in history]
        messages.append({"role": "user", "content": instruction})

        result: AgentTurnResult | None = None
        try:
            result = await self._run_loop(messages, check_availability, book_slot)
        except Exception as exc:  # noqa: BLE001 — an LLM/tooling hiccup must not block booking
            logger.warning("booking agent: loop failed — %s", exc)

        if result is None:
            return await _fallback_turn(
                context, kind, day_str, slot_str, check_availability, book_slot
            )
        return result

    async def _run_loop(
        self, messages: list[dict], check_availability: CheckAvailability, book_slot: BookSlot
    ) -> AgentTurnResult | None:
        for _ in range(MAX_TOOL_ITERATIONS):
            body = await self._complete(messages)
            if body is None:
                return None
            try:
                message = body["choices"][0]["message"]
            except (KeyError, IndexError, TypeError):
                logger.warning("booking agent: unexpected response shape — %s", str(body)[:400])
                return None
            messages.append(message)

            tool_calls = message.get("tool_calls")
            if not tool_calls:
                return _parse_reply(message.get("content") or "")

            for tool_call in tool_calls:
                fn = tool_call["function"]
                try:
                    arguments = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                result = await self._call_tool(fn["name"], arguments, check_availability, book_slot)
                messages.append(
                    {"role": "tool", "tool_call_id": tool_call["id"], "content": json.dumps(result)}
                )
        return None

    async def _call_tool(
        self,
        name: str,
        arguments: dict,
        check_availability: CheckAvailability,
        book_slot: BookSlot,
    ) -> dict:
        try:
            if name == "check_availability":
                availability = await check_availability(date.fromisoformat(arguments["date"]))
                return availability.model_dump(mode="json")
            if name == "book_slot":
                outcome = await book_slot(date.fromisoformat(arguments["date"]), arguments["slot"])
                return outcome.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 — surfaced to the model as a tool error, not raised
            logger.warning("booking agent: tool %s failed — %s", name, exc)
            return {"error": str(exc)}
        return {"error": f"unknown tool {name}"}

    async def _complete(self, messages: list[dict]) -> dict | None:
        payload = {
            "model": self.model,
            "max_tokens": 600,
            "messages": messages,
            "tools": _TOOL_DEFS,
            "tool_choice": "auto",
        }
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self._headers(),
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "booking agent: openrouter HTTP %s — %s",
                exc.response.status_code,
                exc.response.text[:400],
            )
            return None
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("booking agent: openrouter request failed — %s", exc)
            return None
