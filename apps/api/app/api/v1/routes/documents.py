from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, BackgroundTasks, Query, status

from app.api.deps import CurrentManager, CurrentUser
from app.core.config import settings
from app.models.enums import DocumentType
from app.schemas.common import MessageOut
from app.schemas.document import (
    DocumentConfirmIn,
    DocumentOut,
    DownloadUrlOut,
    PresignOut,
    PresignRequestIn,
    VerificationChecklistOut,
)
from app.services import document_service, resume_parse_service, storage_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/presign", response_model=PresignOut)
async def presign_upload(data: PresignRequestIn, user: CurrentUser) -> PresignOut:
    """Step 1 of 2. The browser PUTs the file to this URL, then calls /confirm."""
    url, key = await document_service.create_presigned_upload(user, data)
    return PresignOut(
        upload_url=url,
        object_key=key,
        expires_in=settings.presign_ttl_seconds,
        max_bytes=settings.max_upload_bytes,
    )


@router.post("/confirm", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def confirm_upload(
    data: DocumentConfirmIn, user: CurrentUser, background: BackgroundTasks
) -> DocumentOut:
    """Step 2 of 2. Records metadata once the direct upload has succeeded.

    Resumes additionally kick off AI extraction in the background — the response
    returns straight away with `parse.status = "queued"` and the client polls.
    """
    doc = await document_service.confirm_upload(user, data)

    if doc.type is DocumentType.RESUME and data.parse:
        doc = await resume_parse_service.queue_parse(doc)
        background.add_task(resume_parse_service.run_parse, doc.id)

    return DocumentOut.build(doc)


@router.get("/me", response_model=list[DocumentOut])
async def my_documents(user: CurrentUser) -> list[DocumentOut]:
    docs = await document_service.list_for_user(user.id)
    return [DocumentOut.build(d) for d in docs]


@router.get("/me/checklist", response_model=VerificationChecklistOut)
async def my_checklist(user: CurrentUser) -> VerificationChecklistOut:
    return await document_service.verification_checklist(user.id)


@router.get("/candidate/{candidate_id}", response_model=list[DocumentOut])
async def candidate_documents(
    candidate_id: PydanticObjectId, _: CurrentManager
) -> list[DocumentOut]:
    """Only the resumes this candidate actually submitted with an application.

    Not their whole document shelf — a manager never sees other resume versions
    or verification files, just what was attached when applying.
    """
    from app.services import application_service

    await application_service.assert_manager_may_view_candidate(candidate_id)
    docs = await document_service.list_submitted_resumes(candidate_id)
    return [DocumentOut.build(d) for d in docs]


@router.get("/{document_id}/url", response_model=DownloadUrlOut)
async def download_url(
    document_id: PydanticObjectId,
    user: CurrentUser,
    download: Annotated[bool, Query()] = False,
) -> DownloadUrlOut:
    """Short-lived signed URL, minted only after the caller is authorized.

    `?download=true` returns a save-to-disk link; the default previews in-browser.
    """
    doc = await document_service.get_for_viewer(user, document_id)
    return DownloadUrlOut(
        url=storage_service.presign_download(
            doc.file.object_key, doc.file.filename, attachment=download
        ),
        expires_in=settings.presign_ttl_seconds,
        filename=doc.file.filename,
    )


@router.post("/{document_id}/primary", response_model=DocumentOut)
async def make_primary(document_id: PydanticObjectId, user: CurrentUser) -> DocumentOut:
    doc = await document_service.set_primary_resume(user, document_id)
    return DocumentOut.build(doc)


@router.delete("/{document_id}", response_model=MessageOut)
async def delete_document(document_id: PydanticObjectId, user: CurrentUser) -> MessageOut:
    await document_service.delete_document(user, document_id)
    return MessageOut(detail="Document deleted")
