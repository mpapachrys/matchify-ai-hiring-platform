"""LLM-backed engine, called through OpenRouter.

OpenRouter exposes an OpenAI-compatible `/chat/completions` endpoint and routes
to whichever model `AI_MODEL` names, so this is plain HTTP over the `httpx` we
already depend on — no extra SDK, and swapping models is an env var.

Two design choices worth knowing:

* **PDFs are sent to the model as documents, not as extracted text.** A CV is a
  designed, often two-column page, and flattening it into a text stream reliably
  glues a sidebar's skill list onto whichever job sits beside it. The platform
  still downloads the object itself, so storage credentials stay out of the AI
  boundary — the engine receives bytes, never a bucket key.
* **Every failure degrades to an empty result.** A malformed response, a
  timeout, a missing API key — all return a blank `ParsedResume` rather than
  raising. A resume upload must never fail because the parser had a bad day.
"""

import base64
import json
import logging
import re

import httpx

from app.core.config import settings
from app.integrations.resume_parser.protocol import ParsedResume, ResumeSource
from app.models.enums import INDUSTRIES

logger = logging.getLogger(__name__)

# Resume parsing is a single long-ish call; be patient but bounded.
TIMEOUT = httpx.Timeout(90.0, connect=10.0)

#: Truncated so a 40-page CV can't blow up the request. The signal for parsing
#: is overwhelmingly in the first few pages.
MAX_RESUME_CHARS = 24_000

#: Sent alongside the document (or the text). Kept separate from the system
#: prompt so both input paths ask for exactly the same thing.
INSTRUCTION = "Extract structured data from this resume."

PARSE_SYSTEM_PROMPT = """\
You extract structured data from resumes/CVs.

Return ONLY a JSON object matching this shape — no prose, no markdown fences:

{
  "full_name": string|null,
  "email": string|null,
  "phone": string|null,
  "headline": string|null,          // current role, e.g. "Senior Software Engineer"
  "summary": string|null,           // 1-3 sentence professional summary
  "job_category": string|null,      // one of: Software Engineer, Design, Data,
                                    // Infrastructure, Product, Marketing, Sales, Operations
  "seniority": string|null,         // one of: intern, junior, mid, senior, lead, principal
  "location": { "country": string|null, "city": string|null },
  "skills": [string],               // ONLY skills you cannot tie to a specific role
                                    // (e.g. from a standalone "Skills" section)
  "years_experience": number|null,  // total professional years, may be fractional
  "experience": [{
    "company": string|null, "title": string|null,
    "start_date": string|null,      // "YYYY-MM" where possible
    "end_date": string|null,        // "YYYY-MM", or null when current
    "is_current": boolean,
    "location": string|null, "description": string|null,
    "skills": [string],             // lowercase; technologies/competencies used IN THIS ROLE
    "company_industry": string|null // e.g. Fintech, Healthcare, E-commerce, SaaS, Tech
  }],
  "education": [{
    "institution": string|null, "degree": string|null, "field": string|null,
    "degree_level": string|null,  // High School | Certificate | Diploma | Bachelor | Master | PhD
    "start_date": string|null, "end_date": string|null, "grade": string|null
  }],
  "languages": [{ "name": string, "level": string|null }],   // level: A1-C2, or "Native"
  "certifications": [{
    "name": string, "issuer": string|null,
    "issued_year": number|null, "credential_id": string|null
  }],
  "achievements": {
    "career_highlights": [string],        // measurable results at work
    "academic_distinctions": [string],    // honours, publications, GPA standing
    "awards_and_competitions": [string],  // hackathons, competition placings
    "projects_and_open_source": [string]  // side projects, OSS maintainership
  },
  "links": { "linkedin": string|null, "github": string|null, "portfolio": string|null }
}

Rules:
- Use null for anything not stated. Never invent a value.
- Order experience and education newest first.
- A role's "skills" may contain ONLY technologies named inside that role's own
  entry — its title, its bullets, its description. Never carry a skill over
  from a standalone skills/tech-stack section, from the profile summary, or
  from a different role.
- CVs are frequently laid out in columns. A skills list printed in a sidebar is
  NOT part of whichever job happens to sit beside it. Skills listed on their
  own belong in the top-level "skills" array, which the candidate assigns to
  roles manually.
- If a role's entry names no technologies, return an empty list for that role.
  An empty list is a correct answer; a plausible guess is not.
- start_date is required for every role, and end_date is required unless
  is_current is true. If the CV gives only a year, return "YYYY-01".
- Infer seniority and years_experience from the work history when not stated outright.
- Keep descriptions to one or two sentences; do not copy whole bullet lists.
- degree_level must be one of the six listed values; infer it from the degree
  name ("BSc" → Bachelor, "MEng" → Master). Use null if genuinely unclear.
- Language level must be CEFR (A1-C2) or "Native". Map "fluent" → C1,
  "professional working proficiency" → B2, "mother tongue" → Native.
- Sort achievements into the four buckets. Leave a bucket empty rather than
  forcing an item into the wrong one.
"""


def _match_industry(value: str | None) -> str | None:
    """Snap the model's free-text industry onto the platform's fixed list.

    The graph wants one node per industry, so anything that cannot be placed
    becomes None rather than inventing a new node. The candidate can pick the
    right one from the dropdown afterwards.
    """
    if not value:
        return None
    cleaned = value.strip().lower()
    for industry in INDUSTRIES:
        if cleaned == industry.lower():
            return industry
    for industry in INDUSTRIES:
        if industry.lower() in cleaned or cleaned in industry.lower():
            return industry
    return None


def _extract_json(content: str) -> dict:
    """Pull a JSON object out of a model response.

    Models wrap JSON in ```json fences, add a preamble, or both — depending on
    which model OpenRouter routed to. Rather than constrain every model with a
    response_format it may not support, parse defensively.
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


class OpenRouterResumeParser:
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
            # OpenRouter uses these for attribution on its dashboard.
            "http-referer": settings.org_website,
            "x-title": f"{settings.org_name} Hiring Platform",
        }

    async def _complete(
        self,
        system: str,
        user: str | list[dict],
        max_tokens: int = 4000,
        plugins: list[dict] | None = None,
    ) -> dict | None:
        if not self.is_configured:
            logger.warning("openrouter: OPENROUTER_API_KEY is not set — returning empty result")
            return None

        payload: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if plugins:
            payload["plugins"] = plugins

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=self._headers(),
                )
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "openrouter: HTTP %s — %s",
                exc.response.status_code,
                exc.response.text[:400],
            )
            return None
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("openrouter: request failed — %s", exc)
            return None

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            logger.warning("openrouter: unexpected response shape — %s", str(body)[:400])
            return None

        try:
            return _extract_json(content)
        except ValueError:
            logger.warning("openrouter: could not parse JSON from response — %s", content[:400])
            return None

    async def parse_resume(self, source: ResumeSource) -> ParsedResume:
        truncated = (source.text or "").strip()[:MAX_RESUME_CHARS]

        if source.pdf:
            user: str | list[dict] = [
                {"type": "text", "text": INSTRUCTION},
                {
                    "type": "file",
                    "file": {
                        "filename": source.filename,
                        "file_data": "data:application/pdf;base64,"
                        + base64.b64encode(source.pdf).decode(),
                    },
                },
            ]
            # engine=native hands the document to the model itself rather than
            # running it through OpenRouter's OCR first. That is the whole point:
            # the model sees the page, so a two-column layout stays two columns.
            plugins: list[dict] | None = [
                {"id": "file-parser", "pdf": {"engine": "native"}}
            ]
        elif truncated:
            user = f"{INSTRUCTION}\n\n{truncated}"
            plugins = None
        else:
            return ParsedResume(model_version=f"openrouter/{self.model}")

        data = await self._complete(
            PARSE_SYSTEM_PROMPT,
            user,
            # The schema grew (certifications, four achievement buckets, per-role
            # skills); 4k truncated long CVs mid-JSON, which then failed to parse.
            max_tokens=8000,
            plugins=plugins,
        )

        if data is None:
            # Still hand back the raw text — the builder can show it even when
            # structured extraction failed.
            return ParsedResume(raw_text=truncated or None, model_version="none")

        try:
            parsed = ParsedResume.model_validate(
                {**data, "model_version": f"openrouter/{self.model}"}
            )
        except Exception as exc:  # noqa: BLE001 — a malformed field must not fail the upload
            logger.warning("openrouter: parsed payload failed validation — %s", exc)
            return ParsedResume(raw_text=truncated, model_version="none")

        parsed.raw_text = truncated or None
        parsed.skills = _normalize_skills(parsed.skills)
        for role in parsed.experience:
            role.skills = _normalize_skills(role.skills)
            role.company_industry = _match_industry(role.company_industry)
        return parsed


def _normalize_skills(skills: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for skill in skills:
        cleaned = skill.strip().lower()
        if cleaned:
            seen.setdefault(cleaned, None)
    return list(seen)
