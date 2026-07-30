"""Regex-only placeholder parser.

Extracts only what a regex can honestly find. Everything requiring judgement
stays empty on purpose: a plausible-looking fabricated field is worse than a
blank one, because the candidate would have to notice it is wrong.

Set RESUME_PARSER=openrouter for real extraction.
"""

import re

from app.integrations.resume_parser.protocol import ParsedLinks, ParsedResume, ResumeSource

MODEL_VERSION = "stub-0.1.0"


class StubResumeParser:
    async def parse_resume(self, source: ResumeSource) -> ParsedResume:
        """Pull only what a regex can honestly find — email, phone, links."""
        # No vision here: a PDF with no text layer yields nothing, which is the
        # honest answer for a placeholder parser.
        text = source.text or ""

        def first(pattern: str) -> str | None:
            match = re.search(pattern, text, re.IGNORECASE)
            return match.group(0) if match else None

        return ParsedResume(
            email=first(r"[\w.+-]+@[\w-]+\.[\w.]+"),
            phone=first(r"(?:\+\d{1,3}[\s-]?)?(?:\d[\s-]?){9,13}"),
            links=ParsedLinks(
                linkedin=first(r"https?://(?:www\.)?linkedin\.com/\S+"),
                github=first(r"https?://(?:www\.)?github\.com/\S+"),
            ),
            raw_text=text[:24_000] or None,
            model_version=MODEL_VERSION,
        )
