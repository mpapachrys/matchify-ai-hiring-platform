from datetime import UTC, datetime
from enum import StrEnum

from beanie import Document as BeanieDocument
from beanie import PydanticObjectId
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.models.enums import DocumentStatus, DocumentType


class StoredFile(BaseModel):
    """Pointer only — zero file bytes ever enter MongoDB."""

    bucket: str
    object_key: str
    filename: str
    content_type: str
    size_bytes: int = 0
    checksum: str | None = None


class Verification(BaseModel):
    reviewed_by: PydanticObjectId | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None


class ParseStatus(StrEnum):
    IDLE = "idle"
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class ResumeParse(BaseModel):
    """Result of the background AI extraction for a resume upload.

    Stored on the document rather than the profile because it describes *this
    file*. The candidate reviews it and chooses what to apply — nothing here is
    written to their profile automatically.
    """

    status: ParseStatus = ParseStatus.IDLE
    error: str | None = None
    model_version: str | None = None
    # The engine's ParsedResume, kept as a plain dict so extending the AI
    # contract never requires a database migration.
    data: dict | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class UserDocument(BeanieDocument):
    """Resumes and verification files.

    Uploads go browser → presigned PUT → MinIO directly; FastAPI never proxies
    file bytes. Downloads are short-lived presigned GETs minted only after the
    caller has been authorized, so URLs cannot be shared indefinitely.
    """

    owner_id: PydanticObjectId
    type: DocumentType
    status: DocumentStatus = DocumentStatus.PENDING

    file: StoredFile
    version: int = 1
    is_primary: bool = False

    verification: Verification = Field(default_factory=Verification)
    expires_at: datetime | None = None

    # Populated asynchronously for resume uploads; see resume_parse_service.
    parse: ResumeParse = Field(default_factory=ResumeParse)
    # True for PDFs this platform rendered from the resume builder, so the UI
    # can distinguish "generated" from "uploaded by the candidate".
    is_generated: bool = False

    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "documents"
        indexes = [
            IndexModel(
                [("owner_id", ASCENDING), ("type", ASCENDING), ("status", ASCENDING)],
                name="owner_type_status",
            ),
            IndexModel(
                [("owner_id", ASCENDING), ("type", ASCENDING), ("is_primary", ASCENDING)],
                name="owner_primary",
            ),
            IndexModel([("owner_id", ASCENDING), ("uploaded_at", DESCENDING)], name="owner_recent"),
        ]
