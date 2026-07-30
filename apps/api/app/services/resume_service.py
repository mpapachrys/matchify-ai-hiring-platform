"""Resume builder: seeding a draft, generating the PDF, saving back to profile."""

import logging
import re
from datetime import UTC, date, datetime

from beanie import PydanticObjectId

from app.core.config import settings
from app.models.candidate_profile import (
    Achievements,
    CandidateProfile,
    Certification,
    Education,
    Experience,
    Language,
    Links,
)
from app.models.document import StoredFile, UserDocument
from app.models.enums import DocumentStatus, DocumentType, LanguageProficiency, SeniorityLevel
from app.models.user import User
from app.schemas.resume import (
    DraftAchievements,
    DraftCertification,
    DraftEducation,
    DraftExperience,
    DraftIssue,
    DraftLanguage,
    DraftLinks,
    ResumeDraft,
)
from app.services import document_service, resume_pdf, storage_service

logger = logging.getLogger(__name__)


def _fmt_month(value: date | None) -> str | None:
    return value.strftime("%Y-%m") if value else None


def _normalize_skills(skills: list[str]) -> list[str]:
    """Lowercase and de-duplicate, preserving order.

    Matching runs against these, so casing must not create a second "Python" —
    and the builder is now the only write path, so this has to happen here.
    """
    seen: dict[str, None] = {}
    for skill in skills:
        cleaned = skill.strip().lower()
        if cleaned:
            seen.setdefault(cleaned, None)
    return list(seen)


def _parse_month(value: str | None) -> date | None:
    """Accept the loose date shapes a resume actually contains.

    "2019-03", "2019", "03/2019", "March 2019" all mean something to a human;
    anything we cannot read becomes None rather than rejecting the save.
    """
    if not value:
        return None
    text = value.strip()
    if not text or text.lower() in {"present", "current", "now"}:
        return None

    if match := re.match(r"^(\d{4})-(\d{1,2})", text):
        year, month = int(match.group(1)), int(match.group(2))
        if 1 <= month <= 12:
            return date(year, month, 1)
    if match := re.match(r"^(\d{1,2})[/-](\d{4})$", text):
        month, year = int(match.group(1)), int(match.group(2))
        if 1 <= month <= 12:
            return date(year, month, 1)
    if match := re.match(r"^(\d{4})$", text):
        return date(int(match.group(1)), 1, 1)

    for fmt in ("%B %Y", "%b %Y", "%d %B %Y", "%Y/%m"):
        try:
            return datetime.strptime(text, fmt).date().replace(day=1)
        except ValueError:
            continue
    return None


# ── validation ───────────────────────────────────────────────────────────────


def validate_draft(draft: ResumeDraft) -> list[DraftIssue]:
    """Everything that must be true before a resume can be generated.

    Skills and dates are mandatory per role for a concrete reason each: skills
    are what job matching runs on, and the dates are the only source for years
    of experience. A CV the AI read incompletely lands here, and the candidate
    fills the gaps by hand — which is the point of the review step.
    """
    issues: list[DraftIssue] = []

    if not draft.full_name.strip():
        issues.append(DraftIssue(field="full_name", message="Add your full name."))

    if not draft.experience:
        issues.append(
            DraftIssue(field="experience", message="Add at least one role to your work history.")
        )

    for index, role in enumerate(draft.experience):
        label = role.title or role.company or f"Role {index + 1}"

        if not (role.title or "").strip():
            issues.append(
                DraftIssue(field="title", index=index, message=f"{label}: add a job title.")
            )
        if not (role.company or "").strip():
            issues.append(
                DraftIssue(field="company", index=index, message=f"{label}: add the company.")
            )

        if not [s for s in role.skills if s.strip()]:
            issues.append(
                DraftIssue(
                    field="skills",
                    index=index,
                    message=f"{label}: add at least one skill you used in this role.",
                )
            )

        start = _parse_month(role.start_date)
        if start is None:
            issues.append(
                DraftIssue(
                    field="start_date",
                    index=index,
                    message=f"{label}: add a start date (YYYY-MM).",
                )
            )

        if role.is_current:
            continue

        end = _parse_month(role.end_date)
        if end is None:
            issues.append(
                DraftIssue(
                    field="end_date",
                    index=index,
                    message=f"{label}: add an end date, or tick “I currently work here”.",
                )
            )
        elif start is not None and end < start:
            issues.append(
                DraftIssue(
                    field="end_date",
                    index=index,
                    message=f"{label}: the end date is before the start date.",
                )
            )

    return issues


def compute_years_experience(experience: list[DraftExperience]) -> float | None:
    """Total professional years, from the role date ranges.

    Overlapping roles are merged rather than summed — holding two jobs at once
    for a year is one year of experience, not two.
    """
    spans: list[tuple[date, date]] = []
    today = datetime.now(UTC).date()

    for role in experience:
        start = _parse_month(role.start_date)
        if start is None:
            continue
        end = today if role.is_current else _parse_month(role.end_date)
        if end is None or end < start:
            continue
        spans.append((start, min(end, today)))

    if not spans:
        return None

    spans.sort()
    merged: list[list[date]] = [list(spans[0])]
    for start, end in spans[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    days = sum((end - start).days for start, end in merged)
    return round(days / 365.25, 1)


def collect_skills(experience: list[DraftExperience]) -> list[str]:
    """The profile's flat skill list is the union of every role's skills."""
    return _normalize_skills([skill for role in experience for skill in role.skills])


# ── seeding the wizard ───────────────────────────────────────────────────────


async def seed_draft(user: User) -> tuple[ResumeDraft, bool]:
    profile = await CandidateProfile.find_one(CandidateProfile.user_id == user.id)

    if profile is None:
        return ResumeDraft(full_name=user.full_name, email=user.email, phone=user.phone), False

    draft = ResumeDraft(
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        headline=profile.headline,
        summary=profile.summary,
        city=profile.location.city,
        country=profile.location.country,
        job_category=profile.job_category,
        seniority=profile.seniority,
        open_to_relocate=profile.open_to_relocate,
        work_modes=list(profile.work_modes),
        experience=[
            DraftExperience(
                company=e.company,
                title=e.title,
                start_date=_fmt_month(e.start_date),
                end_date=_fmt_month(e.end_date),
                is_current=e.is_current,
                location=e.location,
                description=e.description,
                skills=list(e.skills),
                company_industry=e.company_industry,
            )
            for e in profile.experience
        ],
        education=[
            DraftEducation(
                institution=e.institution,
                degree=e.degree,
                degree_level=e.degree_level,
                field=e.field,
                start_date=_fmt_month(e.start_date),
                end_date=_fmt_month(e.end_date),
                grade=e.grade,
            )
            for e in profile.education
        ],
        languages=[DraftLanguage(name=lang.name, level=lang.level) for lang in profile.languages],
        certifications=[
            DraftCertification(
                name=c.name,
                issuer=c.issuer,
                issued_year=c.issued_year,
                credential_id=c.credential_id,
            )
            for c in profile.certifications
        ],
        achievements=DraftAchievements(
            career_highlights=list(profile.achievements.career_highlights),
            academic_distinctions=list(profile.achievements.academic_distinctions),
            awards_and_competitions=list(profile.achievements.awards_and_competitions),
            projects_and_open_source=list(profile.achievements.projects_and_open_source),
        ),
        links=DraftLinks(
            linkedin=profile.links.linkedin,
            github=profile.links.github,
            portfolio=profile.links.portfolio,
        ),
    )

    has_data = bool(profile.headline or profile.experience)
    return draft, has_data


# ── saving the draft back to the profile ─────────────────────────────────────


async def apply_draft_to_profile(user: User, draft: ResumeDraft) -> CandidateProfile | None:
    """Replace the candidate profile with the draft.

    **Full replace, not a merge.** The builder is the only editing surface and
    always submits the complete draft, so the draft *is* the profile. Skipping
    empty values would look safer but makes deletion impossible: clearing your
    work history and regenerating would silently leave the old entries in place.

    The one thing this does not touch is name/email/phone — those live on the
    user account and are edited in Settings.
    """
    profile = await CandidateProfile.find_one(CandidateProfile.user_id == user.id)
    if profile is None:
        return None

    # A cleared text input arrives as "", which should mean "not set", not an
    # empty string sitting in the database.
    def blank_to_none(value: str | None) -> str | None:
        cleaned = (value or "").strip()
        return cleaned or None

    profile.headline = blank_to_none(draft.headline)
    profile.summary = blank_to_none(draft.summary)
    profile.location.city = blank_to_none(draft.city)
    profile.location.country = blank_to_none(draft.country)
    profile.job_category = blank_to_none(draft.job_category)
    profile.seniority = draft.seniority
    profile.work_modes = list(draft.work_modes)
    profile.open_to_relocate = draft.open_to_relocate
    # Both derived from the work history rather than entered separately, so
    # they can never contradict it.
    profile.years_experience = compute_years_experience(draft.experience)
    profile.skills = collect_skills(draft.experience)

    profile.experience = [
        Experience(
            company=e.company or "—",
            title=e.title or "—",
            start_date=_parse_month(e.start_date) or date(1970, 1, 1),
            end_date=_parse_month(e.end_date),
            is_current=e.is_current,
            location=e.location,
            description=e.description,
            skills=_normalize_skills(e.skills),
            company_industry=e.company_industry,
        )
        for e in draft.experience
    ]

    profile.education = [
        Education(
            institution=e.institution or "—",
            degree=e.degree or "—",
            degree_level=e.degree_level,
            field=e.field,
            start_date=_parse_month(e.start_date),
            end_date=_parse_month(e.end_date),
            grade=e.grade,
        )
        for e in draft.education
    ]

    profile.languages = [
        Language(name=lang.name, level=lang.level or LanguageProficiency.B2)
        for lang in draft.languages
    ]

    profile.certifications = [
        Certification(
            name=c.name,
            issuer=c.issuer,
            issued_year=c.issued_year,
            credential_id=c.credential_id,
        )
        for c in draft.certifications
        if c.name.strip()
    ]

    def clean(items: list[str]) -> list[str]:
        return [i.strip() for i in items if i.strip()]

    profile.achievements = Achievements(
        career_highlights=clean(draft.achievements.career_highlights),
        academic_distinctions=clean(draft.achievements.academic_distinctions),
        awards_and_competitions=clean(draft.achievements.awards_and_competitions),
        projects_and_open_source=clean(draft.achievements.projects_and_open_source),
    )

    profile.links = Links(
        linkedin=blank_to_none(draft.links.linkedin),
        github=blank_to_none(draft.links.github),
        portfolio=blank_to_none(draft.links.portfolio),
    )

    profile.recompute_completion()
    profile.updated_at = datetime.now(UTC)
    await profile.save()
    return profile


def infer_seniority(years: float | None) -> SeniorityLevel | None:
    if years is None:
        return None
    if years < 1:
        return SeniorityLevel.JUNIOR
    if years < 3:
        return SeniorityLevel.MID
    if years < 8:
        return SeniorityLevel.SENIOR
    return SeniorityLevel.LEAD


# ── generating the PDF ───────────────────────────────────────────────────────


async def generate(
    user: User,
    draft: ResumeDraft,
    template: str,
    *,
    set_as_primary: bool,
) -> tuple[UserDocument, str]:
    """Render, store, and register the PDF as a real resume document.

    Uploading it back means the generated resume is the same artifact that gets
    attached to applications — not a browser download the platform never sees.
    """
    pdf_bytes = resume_pdf.render(draft, template)

    safe_name = re.sub(r"[^A-Za-z0-9]+", "-", draft.full_name or user.full_name).strip("-")
    filename = f"{safe_name or 'resume'}-resume.pdf"

    object_key = storage_service.build_object_key(
        str(user.id), DocumentType.RESUME, filename
    )
    storage_service.put_object(object_key, pdf_bytes, "application/pdf")

    previous = await UserDocument.find(
        UserDocument.owner_id == user.id, UserDocument.type == DocumentType.RESUME
    ).count()

    document = UserDocument(
        owner_id=user.id,
        type=DocumentType.RESUME,
        status=DocumentStatus.PENDING,
        file=StoredFile(
            bucket=settings.storage_bucket,
            object_key=object_key,
            filename=filename,
            content_type="application/pdf",
            size_bytes=len(pdf_bytes),
        ),
        version=previous + 1,
        is_generated=True,
    )
    await document.insert()

    if set_as_primary:
        document = await document_service.set_primary_resume(user, document.id)

    # Unconditional: generating a resume is the only way a profile gets written.
    await apply_draft_to_profile(user, draft)

    download_url = storage_service.presign_download(object_key, filename)
    logger.info(
        "resume generated user=%s template=%s bytes=%d", user.id, template, len(pdf_bytes)
    )
    return document, download_url


async def latest_generated(user_id: PydanticObjectId) -> UserDocument | None:
    return (
        await UserDocument.find(
            UserDocument.owner_id == user_id,
            UserDocument.is_generated == True,  # noqa: E712
        )
        .sort("-uploaded_at")
        .first_or_none()
    )
