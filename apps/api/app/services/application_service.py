from datetime import UTC, datetime

from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.db.mongo import run_in_transaction
from app.models.application import (
    Application,
    CandidateSnapshot,
    InternalNote,
    JobSnapshot,
    MatchResult,
    StageChange,
)
from app.models.candidate_profile import CandidateProfile
from app.models.enums import (
    SHORTLISTED_FROM,
    TERMINAL_STAGES,
    MatchStatus,
    PipelineStage,
)
from app.models.job import Job
from app.models.user import User
from app.schemas.application import ApplicationCreateIn
from app.services import job_service


def _location_label(job: Job) -> str | None:
    if job.location.is_remote:
        return "Remote"
    parts = [p for p in (job.location.city, job.location.country) if p]
    return ", ".join(parts) or None


async def apply(candidate: User, data: ApplicationCreateIn) -> Application:
    """Create an application and keep the job's counter in step atomically.

    The unique index on (job_id, candidate_id) is what actually prevents a
    double submit — two concurrent requests cannot both pass a pre-check, so
    the DuplicateKeyError below is the real guard, not a fallback.
    """
    job = await job_service.get_public_job(data.job_id)
    if not job.accepts_applications:
        raise ConflictError("This job is no longer accepting applications")

    profile = await CandidateProfile.find_one(CandidateProfile.user_id == candidate.id)
    resume_id = data.resume_id or (profile.primary_resume_id if profile else None)

    application = Application(
        job_id=job.id,
        candidate_id=candidate.id,
        job_snapshot=JobSnapshot(
            title=job.title,
            location=_location_label(job),
            employment_type=job.employment_type,
            seniority=job.seniority,
        ),
        candidate_snapshot=CandidateSnapshot(
            full_name=candidate.full_name,
            email=candidate.email,
            headline=profile.headline if profile else None,
            avatar_url=candidate.avatar_url,
        ),
        resume_id=resume_id,
        cover_letter=data.cover_letter,
        answers=data.answers,
        stage=PipelineStage.APPLIED,
        stage_history=[StageChange(to_stage=PipelineStage.APPLIED, changed_by=candidate.id)],
    )

    async def _write(session) -> None:
        # Both writes commit together, so the counter can never drift from the
        # number of application documents. Replayed as a unit if MongoDB aborts
        # the transaction on a write conflict — which is the normal outcome when
        # several candidates apply to the same job at once.
        await application.insert(session=session)
        await Job.get_pymongo_collection().update_one(
            {"_id": job.id},
            {"$inc": {"stats.applications": 1}},
            session=session,
        )

    try:
        await run_in_transaction(_write)
    except DuplicateKeyError as exc:
        # The unique index on (job_id, candidate_id) — not a pre-flight check —
        # is what makes a double submit impossible under concurrency.
        raise ConflictError("You have already applied to this job") from exc

    return application


async def get_or_404(application_id: PydanticObjectId) -> Application:
    application = await Application.get(application_id)
    if application is None:
        raise NotFoundError("Application not found")
    return application


async def get_for_candidate(candidate: User, application_id: PydanticObjectId) -> Application:
    application = await get_or_404(application_id)
    if application.candidate_id != candidate.id:
        # 404 rather than 403: existence of someone else's application is not
        # information a candidate is entitled to.
        raise NotFoundError("Application not found")
    return application


async def list_for_candidate(
    candidate: User, *, skip: int, limit: int, stage: PipelineStage | None = None
) -> tuple[list[Application], int]:
    query: dict = {"candidate_id": candidate.id}
    if stage:
        query["stage"] = stage.value
    cursor = Application.find(query)
    total = await cursor.count()
    items = await cursor.sort("-applied_at").skip(skip).limit(limit).to_list()
    return items, total


async def list_for_job(
    job_id: PydanticObjectId,
    *,
    skip: int,
    limit: int,
    stage: PipelineStage | None = None,
    shortlisted_only: bool = False,
) -> tuple[list[Application], int]:
    query: dict = {"job_id": job_id}
    if stage:
        query["stage"] = stage.value
    if shortlisted_only:
        query["is_shortlisted"] = True
    cursor = Application.find(query)
    total = await cursor.count()
    items = await cursor.sort("-applied_at").skip(skip).limit(limit).to_list()
    return items, total


async def list_all(
    *, skip: int, limit: int, stage: PipelineStage | None = None
) -> tuple[list[Application], int]:
    """Org-wide applicant view. Single-tenant means no company scoping."""
    query: dict = {}
    if stage:
        query["stage"] = stage.value
    cursor = Application.find(query)
    total = await cursor.count()
    items = await cursor.sort("-applied_at").skip(skip).limit(limit).to_list()
    return items, total


async def record_match(
    application_id: PydanticObjectId,
    *,
    confidence: float,
    factors: dict,
    graph_version: str | None,
) -> Application:
    """Store the AI team's confidence for an application.

    Frozen once written: this is the only path that sets a score, and it is not
    invoked again for the same application unless the AI team explicitly re-posts.
    """
    application = await get_or_404(application_id)
    application.match = MatchResult(
        status=MatchStatus.SCORED,
        confidence=confidence,
        factors=factors,
        graph_version=graph_version,
        scored_at=datetime.now(UTC),
    )
    application.updated_at = datetime.now(UTC)
    await application.save()
    return application


async def _resync_job_counters(job_id: PydanticObjectId) -> None:
    """Recompute derived counters from the source of truth.

    Both counts hit compound indexes, so this is cheaper than reasoning about
    every possible stage transition — and it cannot drift.
    """
    shortlisted = await Application.find(
        Application.job_id == job_id, Application.is_shortlisted == True  # noqa: E712
    ).count()
    hired = await Application.find(
        Application.job_id == job_id, Application.stage == PipelineStage.HIRED
    ).count()
    await Job.get_pymongo_collection().update_one(
        {"_id": job_id},
        {"$set": {"stats.shortlisted": shortlisted, "stats.hired": hired}},
    )


async def change_stage(
    manager: User,
    application_id: PydanticObjectId,
    new_stage: PipelineStage,
    note: str | None = None,
) -> Application:
    application = await get_or_404(application_id)

    if new_stage is PipelineStage.WITHDRAWN:
        raise ValidationError("Only the candidate can withdraw an application")
    if application.stage is PipelineStage.WITHDRAWN:
        raise ConflictError("This application was withdrawn by the candidate")
    if application.stage == new_stage:
        return application

    application.stage_history.append(
        StageChange(
            from_stage=application.stage,
            to_stage=new_stage,
            changed_by=manager.id,
            note=note,
        )
    )
    application.stage = new_stage
    # Reaching screening or beyond means the candidate cleared the first pass.
    if new_stage in SHORTLISTED_FROM:
        application.is_shortlisted = True
    application.updated_at = datetime.now(UTC)
    await application.save()

    await _resync_job_counters(application.job_id)
    return application


async def set_shortlisted(
    application_id: PydanticObjectId, is_shortlisted: bool
) -> Application:
    application = await get_or_404(application_id)
    application.is_shortlisted = is_shortlisted
    application.updated_at = datetime.now(UTC)
    await application.save()
    await _resync_job_counters(application.job_id)
    return application


async def set_rating(application_id: PydanticObjectId, rating: int | None) -> Application:
    application = await get_or_404(application_id)
    application.rating = rating
    application.updated_at = datetime.now(UTC)
    await application.save()
    return application


async def add_note(
    manager: User, application_id: PydanticObjectId, body: str
) -> Application:
    application = await get_or_404(application_id)
    application.notes.append(
        InternalNote(author_id=manager.id, author_name=manager.full_name, body=body)
    )
    application.updated_at = datetime.now(UTC)
    await application.save()
    return application


async def withdraw(candidate: User, application_id: PydanticObjectId) -> Application:
    application = await get_for_candidate(candidate, application_id)
    if application.stage in TERMINAL_STAGES:
        raise ConflictError("This application is already closed")

    application.stage_history.append(
        StageChange(
            from_stage=application.stage,
            to_stage=PipelineStage.WITHDRAWN,
            changed_by=candidate.id,
        )
    )
    application.stage = PipelineStage.WITHDRAWN
    application.is_shortlisted = False
    application.withdrawn_at = datetime.now(UTC)
    application.updated_at = datetime.now(UTC)
    await application.save()

    # stats.applications intentionally still counts this — it records how many
    # applications the posting received, not how many are currently live.
    await _resync_job_counters(application.job_id)
    return application


async def assert_manager_may_view_candidate(
    candidate_id: PydanticObjectId,
) -> None:
    """A manager reaches a candidate profile only through an application.

    There is no candidate directory — this is the rule that keeps the platform
    from becoming one.
    """
    exists = await Application.find_one(Application.candidate_id == candidate_id)
    if exists is None:
        raise PermissionDeniedError("This candidate has not applied to any of your jobs")
