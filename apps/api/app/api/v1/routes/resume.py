"""Resume builder: CV upload → background AI parse → autofilled draft → PDF."""

from beanie import PydanticObjectId
from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.api.deps import CurrentCandidate, CurrentUser
from app.core.config import settings
from app.schemas.resume import (
    DraftIssue,
    GenerateResumeIn,
    GenerateResumeOut,
    ParseStatusOut,
    ResumeDraftSeedOut,
    TemplateOut,
)
from app.services import document_service, resume_parse_service, resume_pdf, resume_service

router = APIRouter(prefix="/resume", tags=["resume-builder"])

TEMPLATE_DESCRIPTIONS = {
    "professional": "Clean and traditional format with modern typography",
}


@router.get("/templates", response_model=list[TemplateOut])
async def list_templates(_: CurrentCandidate) -> list[TemplateOut]:
    return [
        TemplateOut(
            id=key,
            label=spec["label"],
            description=TEMPLATE_DESCRIPTIONS.get(key, ""),
        )
        for key, spec in resume_pdf.TEMPLATES.items()
    ]


@router.get("/draft", response_model=ResumeDraftSeedOut)
async def seed_draft(candidate: CurrentCandidate) -> ResumeDraftSeedOut:
    """Open the wizard pre-filled from the existing profile."""
    draft, has_data = await resume_service.seed_draft(candidate)
    return ResumeDraftSeedOut(draft=draft, has_profile_data=has_data)


@router.post(
    "/documents/{document_id}/parse",
    response_model=ParseStatusOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_parse(
    document_id: PydanticObjectId,
    user: CurrentUser,
    background: BackgroundTasks,
) -> ParseStatusOut:
    """Kick off extraction and return immediately.

    202 with a `queued` status, not a parsed result: the model call takes tens of
    seconds and must not block the upload request. The client polls the GET below.
    """
    document = await document_service.get_owned_or_404(user, document_id)
    document = await resume_parse_service.queue_parse(document)
    background.add_task(resume_parse_service.run_parse, document.id)
    return ParseStatusOut.build(document)


@router.get("/documents/{document_id}/parse", response_model=ParseStatusOut)
async def parse_status(document_id: PydanticObjectId, user: CurrentUser) -> ParseStatusOut:
    document = await resume_parse_service.get_parse(user.id, document_id)
    return ParseStatusOut.build(document)


@router.post("/validate", response_model=list[DraftIssue])
async def validate_draft(data: GenerateResumeIn, _: CurrentCandidate) -> list[DraftIssue]:
    """What still needs filling in. Empty list means the draft is ready."""
    return resume_service.validate_draft(data.draft)


@router.post("/generate", response_model=GenerateResumeOut, status_code=status.HTTP_201_CREATED)
async def generate_resume(
    data: GenerateResumeIn, candidate: CurrentCandidate
) -> GenerateResumeOut:
    """Render the draft to PDF, store it, and hand back a download link.

    Rejects an incomplete draft rather than producing a half-empty resume: the
    per-role skills and dates are what job matching and years-of-experience are
    computed from, so a resume without them is not usable by the platform.
    """
    issues = resume_service.validate_draft(data.draft)
    if issues:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "Some details are still missing.",
                "code": "draft_incomplete",
                "issues": [issue.model_dump() for issue in issues],
            },
        )

    document, download_url = await resume_service.generate(
        candidate,
        data.draft,
        data.template,
        set_as_primary=data.set_as_primary,
    )
    return GenerateResumeOut(
        document_id=document.id,
        filename=document.file.filename,
        download_url=download_url,
        expires_in=settings.presign_ttl_seconds,
        is_primary=document.is_primary,
    )
