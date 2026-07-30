"""LLM-driven interview scheduling over an MCP session.

Reusable core shared by the interactive CLI (agent.py) and interview_api.py.
Nothing here talks to stdio/subprocess directly — callers pass in an already
-initialized MCP ClientSession.
"""
import json
import logging
import os
import re
from datetime import datetime

import requests
from dotenv import load_dotenv

# Self-contained like src/auth.py's own load_dotenv() call — callers
# (agent.py, interview_api.py) must not need to load .env before importing
# this module, since OPENROUTER_API_KEY below is read at import time.
load_dotenv()

#: Fallback for a reply that wraps JSON in a markdown fence or adds stray
#: text despite instructions — matches the first top-level {...} block.
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MAX_TOOL_ITERATIONS = 8

#: The three bookable interview slots each weekday. Kept as data (not just
#: prose in AGENT_INSTRUCTIONS) so a caller can enforce the identical policy
#: without a model round-trip — see interview_api.py's availability endpoint.
SLOT_POLICY: list[tuple[str, str]] = [
    ("13:00", "14:00"),
    ("14:30", "15:30"),
    ("16:00", "17:00"),
]

AGENT_INSTRUCTIONS = (
    "You schedule meetings under a fixed booking policy. Follow it exactly:\n"
    "- Meetings are only allowed Monday through Friday, never on a weekend.\n"
    "- Every meeting is exactly 1 hour long, and only these three slots exist "
    "each weekday (so a 30-minute break always separates consecutive meetings): "
    "13:00-14:00, 14:30-15:30, 16:00-17:00.\n"
    "- If the user asks for a day that's a weekend, or a time that isn't one of "
    "the three slots above, explain the policy and ask which of the three slots "
    "(and which weekday) they'd like instead. Do not create anything yet.\n"
    "- Once you have a specific weekday and slot, use find_events to check the "
    "target calendar for that whole day for existing events that overlap the "
    "requested slot.\n"
    "- If the slot is already taken, do NOT create the meeting. Instead tell the "
    "user it's taken and recommend the next free slot from the three options that "
    "day (or the same slots on the next weekday if all three are taken), and wait "
    "for them to confirm. Do not reveal ANY details about the existing/conflicting "
    "meeting - no attendee emails, no title, no description, nothing. Just say "
    "the slot is already booked, with no further specifics about what it is or "
    "who it's with.\n"
    "- If the slot is free, create the meeting right away.\n"
    "- Always end with a clear message to the user: either the confirmed meeting "
    "details (date, time, attendees) or an explanation of the conflict and your "
    "recommended alternative."
)

#: Appended for one-shot, non-interactive callers (interview_api.py) that need
#: a machine-parseable result instead of the conversational sign-off above.
STRUCTURED_REPLY_INSTRUCTIONS = (
    "\n\nYou are being driven by a program, not a person, so once you have "
    "reached a conclusion (scheduled, conflict, or the request itself was "
    "invalid), your FINAL reply must be ONLY a single JSON object — no prose "
    "before or after it, no markdown code fence — with exactly this shape:\n"
    '{"status": "scheduled" | "conflict" | "invalid_request", '
    '"start": "<ISO 8601 datetime or null>", "end": "<ISO 8601 datetime or null>", '
    '"event_id": "<string or null>", "html_link": "<string or null>", '
    '"message": "<one sentence a human will read>"}\n'
    "Use \"scheduled\" only after the event was actually created. Use "
    "\"conflict\" when the requested slot is taken. Use \"invalid_request\" "
    "when the requested day/time falls outside the policy above."
)


def build_system_prompt(structured: bool = False) -> str:
    now = datetime.now().astimezone()
    technical_notes = (
        "The current date and time is "
        f"{now.isoformat()}. Resolve relative dates (e.g. 'tomorrow', 'next Friday') "
        "against this. Use calendar_id 'primary' unless the user names another "
        "calendar. Before updating or deleting an event, make sure you have the "
        "correct event_id (look it up with find_events if you don't already have it)."
    )
    prompt = f"{AGENT_INSTRUCTIONS.strip()}\n\n{technical_notes}"
    if structured:
        prompt += STRUCTURED_REPLY_INSTRUCTIONS
    return prompt


def mcp_tool_to_openai_tool(tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema or {"type": "object", "properties": {}},
        },
    }


def call_openrouter(messages: list, tools: list, response_format: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
    }
    if response_format:
        payload["response_format"] = response_format
    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenRouter error {resp.status_code}: {resp.text}")
    return resp.json()


async def handle_message(
    session, messages: list, openai_tools: list, user_input: str, response_format: dict | None = None
) -> str:
    """Sends one user message through the LLM, executing any MCP tool calls it
    requests, until the model replies with plain text or the iteration cap is hit.

    Returns the model's final plain-text reply ("" if the cap was hit).
    """
    messages.append({"role": "user", "content": user_input})

    for _ in range(MAX_TOOL_ITERATIONS):
        response = call_openrouter(messages, openai_tools, response_format=response_format)
        message = response["choices"][0]["message"]
        messages.append(message)

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            return message.get("content", "") or ""

        for tool_call in tool_calls:
            fn = tool_call["function"]
            name = fn["name"]
            try:
                arguments = json.loads(fn["arguments"] or "{}")
            except json.JSONDecodeError:
                arguments = {}

            logger.info("tool call: %s(%s)", name, arguments)
            result = await session.call_tool(name, arguments)
            content_text = "\n".join(
                block.text for block in result.content if hasattr(block, "text")
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": content_text or "(no output)",
                }
            )

    return ""


async def run_scheduling_decision(session, openai_tools: list, instruction: str) -> dict:
    """Runs one scheduling instruction through the LLM+MCP tool-calling loop
    and returns a structured result dict.

    Never raises on a malformed model reply — returns {"status": "error", ...}
    instead, since this drives an HTTP endpoint that must always respond.
    """
    # response_format=json_object is deliberately NOT forced on every turn:
    # several models routed through OpenRouter drop or ignore tool_calls once
    # JSON mode is active, which would break the find_events/create_event
    # steps entirely. Instead the prompt alone demands JSON-only on the final
    # reply, and parsing below tolerates a stray code fence or preamble.
    messages = [{"role": "system", "content": build_system_prompt(structured=True)}]
    reply = await handle_message(session, messages, openai_tools, instruction)

    if not reply:
        return {
            "status": "error",
            "start": None,
            "end": None,
            "event_id": None,
            "html_link": None,
            "message": "Stopped after too many tool-call iterations.",
        }

    try:
        parsed = json.loads(reply)
    except json.JSONDecodeError:
        match = _JSON_OBJECT_RE.search(reply)
        if match:
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError:
                parsed = None
        else:
            parsed = None

        if parsed is None:
            logger.warning("model did not return valid JSON: %s", reply[:500])
            return {
                "status": "error",
                "start": None,
                "end": None,
                "event_id": None,
                "html_link": None,
                "message": reply[:500],
            }

    parsed.setdefault("start", None)
    parsed.setdefault("end", None)
    parsed.setdefault("event_id", None)
    parsed.setdefault("html_link", None)
    parsed.setdefault("message", "")
    return parsed
