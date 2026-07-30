"""Parser selection. One env var swaps the implementation.

Resume parsing was the only LLM use in this codebase; the interview-booking
chat widget (app/integrations/booking_agent) is the other. Matching and
scoring are the AI team's, driven from the graph export — see
docs/graph-export.md.
"""

import logging
from functools import lru_cache

from app.core.config import settings
from app.integrations.resume_parser.openrouter import OpenRouterResumeParser
from app.integrations.resume_parser.protocol import ParsedResume, ResumeParser
from app.integrations.resume_parser.stub import StubResumeParser

logger = logging.getLogger(__name__)

__all__ = ["get_parser", "ResumeParser", "ParsedResume"]


@lru_cache
def get_parser() -> ResumeParser:
    if settings.resume_parser.lower() == "openrouter":
        parser = OpenRouterResumeParser()
        if not parser.is_configured:
            # Falling back keeps uploads working with no key, and says so loudly
            # rather than failing every parse with an opaque error.
            logger.warning(
                "RESUME_PARSER=openrouter but OPENROUTER_API_KEY is empty — using the stub"
            )
            return StubResumeParser()
        logger.info("resume parser: openrouter model=%s", parser.model)
        return parser

    return StubResumeParser()
