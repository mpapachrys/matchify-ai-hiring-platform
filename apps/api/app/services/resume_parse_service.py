"""Background resume parsing.

The upload response returns immediately and the LLM call runs after it, because
a 10–30 second model round trip must not sit inside the request that uploads a
file. The client polls `GET /resume/documents/{id}/parse` and applies the result
when it lands.

Runs on FastAPI's `BackgroundTasks` — same process, after the response is sent.
That is the right size for this: parsing is per-candidate and infrequent. If it
ever needs retries, scheduling, or to survive a restart, this is the function to
move behind a real queue (there is a reserved `app/worker/` slot for it).
"""

import logging
from datetime import UTC, datetime

from beanie import PydanticObjectId

from app.core.exceptions import NotFoundError, ValidationError
from app.integrations.resume_parser import get_parser
from app.models.document import ParseStatus, UserDocument
from app.models.enums import DocumentType
from app.services.resume_text import ResumeTextError, build_source

logger = logging.getLogger(__name__)


async def queue_parse(document: UserDocument) -> UserDocument:
    """Mark the document as queued. Call before scheduling `run_parse`."""
    if document.type is not DocumentType.RESUME:
        raise ValidationError("Only resume documents can be parsed")

    document.parse.status = ParseStatus.QUEUED
    document.parse.error = None
    document.parse.data = None
    document.parse.started_at = datetime.now(UTC)
    document.parse.completed_at = None
    await document.save()
    return document


async def run_parse(document_id: PydanticObjectId) -> None:
    """The background job itself. Never raises — it records failure instead."""
    document = await UserDocument.get(document_id)
    if document is None:
        logger.warning("resume parse: document %s vanished before parsing", document_id)
        return

    document.parse.status = ParseStatus.PROCESSING
    await document.save()

    try:
        source = build_source(document.file.object_key, document.file.content_type)
    except ResumeTextError as exc:
        # A predictable, explainable failure — an image upload, an unsupported
        # type. The message is written for the candidate, not for a log reader.
        await _fail(document, str(exc))
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("resume parse: could not read the upload")
        await _fail(document, f"Could not read the file ({exc.__class__.__name__}).")
        return

    try:
        parsed = await get_parser().parse_resume(source)
    except Exception as exc:  # noqa: BLE001 — the engine is meant to fail soft, but belt and braces
        logger.exception("resume parse: parser call crashed")
        await _fail(document, f"The parser failed ({exc.__class__.__name__}).")
        return

    payload = parsed.model_dump(mode="json")
    # The raw text is large and the client never renders it — drop it from what
    # we store and return, keeping only the structured extraction.
    payload.pop("raw_text", None)

    document.parse.status = ParseStatus.DONE
    document.parse.data = payload
    document.parse.model_version = parsed.model_version
    document.parse.error = None
    document.parse.completed_at = datetime.now(UTC)
    await document.save()

    logger.info(
        "resume parse: document=%s model=%s skills=%d experience=%d",
        document_id,
        parsed.model_version,
        len(parsed.skills),
        len(parsed.experience),
    )


async def _fail(document: UserDocument, message: str) -> None:
    document.parse.status = ParseStatus.FAILED
    document.parse.error = message
    document.parse.completed_at = datetime.now(UTC)
    await document.save()


async def get_parse(user_id: PydanticObjectId, document_id: PydanticObjectId) -> UserDocument:
    document = await UserDocument.get(document_id)
    if document is None or document.owner_id != user_id:
        raise NotFoundError("Document not found")
    return document
