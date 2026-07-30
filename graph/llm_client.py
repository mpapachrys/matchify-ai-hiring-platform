"""Generic OpenRouter chat-completion helper: prompt in, JSON dict out.

OpenRouter exposes an OpenAI-compatible /chat/completions endpoint, so this is
plain HTTP over `requests` (already a graph/ dependency) — no SDK needed, and
swapping models is an env var. `graph/` is fully synchronous (the Neo4j
driver, graph/api_client.py's calls to the Matchify API), so this stays
synchronous too, unlike apps/api's async-httpx-based resume_parser (the
codebase's only other LLM integration, which this otherwise mirrors closely):
no `response_format`/tool-schema is sent — a prose-prompted JSON reply,
parsed defensively, since not every model OpenRouter might route to supports
a constrained response format.

Config is read from the root .env under OPEN_ROUTER_API_KEY / OPENROUTER_MODEL
— deliberately not OPENROUTER_API_KEY/AI_MODEL, which are apps/api's own,
separate settings for its own, separate LLM use (resume parsing). Two
different codebases, two different env var names for what happens to be the
same underlying secret today — same pattern as MATCHIFY_API_TOKEN (here) vs
INBOUND_AI_TOKEN (apps/api).

Every failure degrades to None rather than raising — a missing key, a
timeout, a malformed reply must never crash the match pipeline; the caller
(graph/matching.py) falls back to a deterministic score instead.
"""

import json
import logging
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

OPEN_ROUTER_API_KEY = os.environ.get("OPEN_ROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash")
OPENROUTER_BASE_URL = os.environ.get(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
).rstrip("/")

#: (connect, read) seconds — a single short evaluation call, not a long
#: document parse, so bounded tighter than resume_parser's 90s.
TIMEOUT = (10.0, 30.0)


def _extract_json(content: str) -> dict:
    """Pull a JSON object out of a model response.

    Models wrap JSON in ```json fences, add a preamble, or both — depending on
    which model OpenRouter routed to. Same defensive parsing as
    apps/api/app/integrations/resume_parser/openrouter.py:_extract_json.
    """
    content = content.strip()

    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", content, re.DOTALL)
    if fenced:
        content = fenced.group(1).strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Last resort: the outermost {...} span.
    start, end = content.find("{"), content.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(content[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError("no JSON object found in model response")


def complete_json(system: str, user: str, max_tokens: int = 1000) -> dict | None:
    """One prompt in, one JSON dict out — or None on any failure (missing key,
    network error, malformed reply). Never raises; every failure is logged
    and degrades to None, same fail-soft philosophy as the resume parser."""
    if not OPEN_ROUTER_API_KEY:
        logger.warning("llm_client: OPEN_ROUTER_API_KEY is not set — skipping LLM call")
        return None

    payload = {
        "model": OPENROUTER_MODEL,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "authorization": f"Bearer {OPEN_ROUTER_API_KEY}",
        "content-type": "application/json",
    }

    try:
        response = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
    except requests.HTTPError as exc:
        logger.warning(
            "llm_client: HTTP %s — %s",
            exc.response.status_code,
            exc.response.text[:400],
        )
        return None
    except (requests.RequestException, ValueError) as exc:
        logger.warning("llm_client: request failed — %s", exc)
        return None

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        logger.warning("llm_client: unexpected response shape — %s", str(body)[:400])
        return None

    try:
        return _extract_json(content)
    except ValueError:
        logger.warning("llm_client: could not parse JSON from response — %s", content[:400])
        return None
