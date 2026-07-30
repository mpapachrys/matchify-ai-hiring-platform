from datetime import datetime

from beanie import PydanticObjectId
from pydantic import BaseModel, Field

from app.models.document import ParseStatus, UserDocument, Verification
from app.models.enums import DocumentStatus, DocumentType


class PresignRequestIn(BaseModel):
    type: DocumentType
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = "application/octet-stream"
    size_bytes: int = Field(ge=1)


class PresignOut(BaseModel):
    """The browser PUTs the file straight to object storage with this URL.

    FastAPI authorizes the upload and mints the URL, but never touches the bytes.
    """

    upload_url: str
    object_key: str
    expires_in: int
    max_bytes: int


class DocumentConfirmIn(BaseModel):
    """Called after the direct PUT succeeds so we can record the metadata."""

    type: DocumentType
    object_key: str
    filename: str
    content_type: str
    size_bytes: int = Field(ge=1)
    make_primary: bool = False
    #: Resumes only — run AI extraction in the background after recording.
    parse: bool = False


class DocumentOut(BaseModel):
    id: PydanticObjectId
    owner_id: PydanticObjectId
    type: DocumentType
    status: DocumentStatus
    filename: str
    content_type: str
    size_bytes: int
    version: int
    is_primary: bool
    is_generated: bool = False
    parse_status: ParseStatus = ParseStatus.IDLE
    verification: Verification
    uploaded_at: datetime

    @classmethod
    def build(cls, doc: UserDocument) -> "DocumentOut":
        return cls(
            is_generated=doc.is_generated,
            parse_status=doc.parse.status,
            id=doc.id,
            owner_id=doc.owner_id,
            type=doc.type,
            status=doc.status,
            filename=doc.file.filename,
            content_type=doc.file.content_type,
            size_bytes=doc.file.size_bytes,
            version=doc.version,
            is_primary=doc.is_primary,
            verification=doc.verification,
            uploaded_at=doc.uploaded_at,
        )


class DownloadUrlOut(BaseModel):
    url: str
    expires_in: int
    filename: str


class VerificationChecklistOut(BaseModel):
    """Powers the 'Verification documents pending' banner."""

    required: list[DocumentType]
    satisfied: list[DocumentType]
    missing: list[DocumentType]
    is_complete: bool
