from datetime import UTC, datetime

from beanie import PydanticObjectId

from app.core.config import settings
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.models.candidate_profile import CandidateProfile
from app.models.document import StoredFile, UserDocument
from app.models.enums import DocumentStatus, DocumentType, Role
from app.models.user import User
from app.schemas.document import DocumentConfirmIn, PresignRequestIn, VerificationChecklistOut
from app.services import organization_service, storage_service


async def create_presigned_upload(user: User, data: PresignRequestIn) -> tuple[str, str]:
    storage_service.validate_upload(data.content_type, data.size_bytes)
    key = storage_service.build_object_key(str(user.id), data.type, data.filename)
    return storage_service.presign_upload(key), key


async def confirm_upload(user: User, data: DocumentConfirmIn) -> UserDocument:
    """Record metadata after the browser's direct PUT succeeded.

    The key is re-derived from the caller's id prefix, so a client cannot claim
    ownership of an object uploaded under someone else's namespace.
    """
    if not data.object_key.startswith(f"{user.id}/"):
        raise PermissionDeniedError("Object key does not belong to this account")

    storage_service.validate_upload(data.content_type, data.size_bytes)

    previous = await UserDocument.find(
        UserDocument.owner_id == user.id, UserDocument.type == data.type
    ).count()

    doc = UserDocument(
        owner_id=user.id,
        type=data.type,
        status=DocumentStatus.PENDING,
        file=StoredFile(
            bucket=settings.storage_bucket,
            object_key=data.object_key,
            filename=data.filename,
            content_type=data.content_type,
            size_bytes=data.size_bytes,
        ),
        version=previous + 1,
    )
    await doc.insert()

    # First resume uploaded becomes primary automatically. Return the value
    # set_primary_resume produces — it re-reads the document, so the local `doc`
    # here is already stale and would report is_primary=false to the client.
    if data.type is DocumentType.RESUME and (data.make_primary or previous == 0):
        return await set_primary_resume(user, doc.id)

    return doc


async def set_primary_resume(user: User, document_id: PydanticObjectId) -> UserDocument:
    doc = await get_owned_or_404(user, document_id)

    await UserDocument.find(
        UserDocument.owner_id == user.id, UserDocument.type == DocumentType.RESUME
    ).set({UserDocument.is_primary: False})

    doc.is_primary = True
    await doc.save()

    profile = await CandidateProfile.find_one(CandidateProfile.user_id == user.id)
    if profile:
        profile.primary_resume_id = doc.id
        profile.recompute_completion()
        profile.updated_at = datetime.now(UTC)
        await profile.save()

    return doc


async def get_owned_or_404(user: User, document_id: PydanticObjectId) -> UserDocument:
    doc = await UserDocument.get(document_id)
    if doc is None or doc.owner_id != user.id:
        raise NotFoundError("Document not found")
    return doc


async def _is_submitted_resume(document_id: PydanticObjectId) -> bool:
    """True if this document is the resume frozen onto some application.

    This is the whole of a manager's document access: not "the candidate applied
    somewhere, so show everything they own", but "this exact file was submitted
    with an application". Other resume versions, passports and degrees are never
    reachable — a manager sees only what a candidate chose to attach when applying.
    """
    from app.models.application import Application

    hit = await Application.find_one(Application.resume_id == document_id)
    return hit is not None


async def get_for_viewer(viewer: User, document_id: PydanticObjectId) -> UserDocument:
    """Owner always; a manager only for a resume submitted with an application."""
    doc = await UserDocument.get(document_id)
    if doc is None:
        raise NotFoundError("Document not found")

    if doc.owner_id == viewer.id:
        return doc

    if viewer.role is Role.HIRING_MANAGER and await _is_submitted_resume(doc.id):
        return doc

    # 404, not 403: whether some other document exists is not a manager's to know.
    raise NotFoundError("Document not found")


async def list_for_user(user_id: PydanticObjectId) -> list[UserDocument]:
    return await UserDocument.find(UserDocument.owner_id == user_id).sort("-uploaded_at").to_list()


async def list_submitted_resumes(candidate_id: PydanticObjectId) -> list[UserDocument]:
    """The distinct resumes a candidate actually submitted, newest first.

    What a manager is allowed to see of a candidate's files — nothing else.
    """
    from app.models.application import Application

    apps = await Application.find(Application.candidate_id == candidate_id).to_list()
    resume_ids = {a.resume_id for a in apps if a.resume_id is not None}
    if not resume_ids:
        return []
    return (
        await UserDocument.find({"_id": {"$in": list(resume_ids)}})
        .sort("-uploaded_at")
        .to_list()
    )


async def delete_document(user: User, document_id: PydanticObjectId) -> None:
    doc = await get_owned_or_404(user, document_id)
    try:
        storage_service.delete_object(doc.file.object_key)
    except Exception:  # noqa: BLE001 — orphaned object is preferable to a failed delete
        pass
    await doc.delete()


async def verification_checklist(user_id: PydanticObjectId) -> VerificationChecklistOut:
    """Drives the 'Verification documents pending' banner on the dashboard."""
    org = await organization_service.get_organization()
    required = org.hiring.required_documents

    docs = await UserDocument.find(UserDocument.owner_id == user_id).to_list()
    satisfied = {
        d.type for d in docs if d.status in (DocumentStatus.PENDING, DocumentStatus.VERIFIED)
    }

    missing = [t for t in required if t not in satisfied]
    return VerificationChecklistOut(
        required=required,
        satisfied=[t for t in required if t in satisfied],
        missing=missing,
        is_complete=not missing,
    )
