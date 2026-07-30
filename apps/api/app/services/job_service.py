import re
from datetime import UTC, datetime
from typing import Any

from beanie import PydanticObjectId
from beanie.operators import In

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.models.application import Application
from app.models.enums import JobStatus, SeniorityLevel, WorkMode
from app.models.job import Job
from app.models.user import User
from app.schemas.job import JobCreateIn, JobUpdateIn

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    return _SLUG_STRIP.sub("-", value.lower()).strip("-") or "job"


async def _unique_slug(title: str) -> str:
    base = _slugify(title)
    slug = base
    suffix = 2
    while await Job.find_one(Job.slug == slug) is not None:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def _slugify_skill(name: str) -> str:
    """The stable key a skill is matched on, both here and in the graph export."""
    return name.strip().lower()


def normalize_requirements(job: Job) -> None:
    """Canonicalise skill slugs and rebuild the derived flat list.

    `skills_required` exists only to keep the multikey and text indexes working;
    it is never edited directly. Rebuilding it here means it can never fall out
    of step with the structured requirements it summarises.
    """
    for skill in job.mandatory.skills:
        skill.slug = _slugify_skill(skill.name or skill.slug)
    for skill in job.nice_to_have.skills:
        skill.slug = _slugify_skill(skill.name or skill.slug)

    seen: dict[str, None] = {}
    for slug in [s.slug for s in job.mandatory.skills] + [
        s.slug for s in job.nice_to_have.skills
    ]:
        if slug:
            seen.setdefault(slug, None)
    job.skills_required = list(seen)


def can_edit(user: User, job: Job) -> bool:
    """Single-tenant rule: every manager reads every job, but mutating one is
    limited to its creator or an admin."""
    return job.created_by == user.id or user.is_admin


def assert_can_edit(user: User, job: Job) -> None:
    if not can_edit(user, job):
        raise PermissionDeniedError("Only the job's creator or an admin can modify it")


async def create_job(user: User, data: JobCreateIn) -> Job:
    job = Job(
        created_by=user.id,
        title=data.title.strip(),
        slug=await _unique_slug(data.title),
        description=data.description,
        responsibilities=data.responsibilities,
        mandatory=data.mandatory,
        nice_to_have=data.nice_to_have,

        job_category=data.job_category,
        seniority=data.seniority,
        employment_type=data.employment_type,
        work_mode=data.work_mode,
        location=data.location,
        salary=data.salary,
        openings=data.openings,
        application_deadline=data.application_deadline,
        status=data.status,
    )
    normalize_requirements(job)

    if data.pipeline_stages:
        job.pipeline_stages = data.pipeline_stages
    if job.status is JobStatus.PUBLISHED:
        job.published_at = datetime.now(UTC)

    await job.insert()
    return job


async def update_job(user: User, job_id: PydanticObjectId, data: JobUpdateIn) -> Job:
    job = await get_job_or_404(job_id)
    assert_can_edit(user, job)

    # Copy the validated objects across, not model_dump() output — dumping
    # flattens `location` and `salary` into plain dicts, and Beanie documents
    # do not validate on assignment, so the nested models would be silently
    # replaced by dicts that break on the next attribute access.
    provided = data.model_fields_set
    handled = {"title", "status"}

    for key in provided - handled:
        value = getattr(data, key)
        # These two are legitimately clearable; everything else treats an
        # explicit null as "leave alone".
        if value is not None or key in {"salary", "application_deadline"}:
            setattr(job, key, value)

    if data.title:
        job.title = data.title.strip()

    # Always: the derived list must follow any change to the requirements.
    normalize_requirements(job)

    if "status" in provided and data.status is not None:
        if data.status is JobStatus.PUBLISHED and job.published_at is None:
            job.published_at = datetime.now(UTC)
        if data.status in (JobStatus.CLOSED, JobStatus.ARCHIVED):
            job.closed_at = datetime.now(UTC)
        job.status = data.status

    job.updated_at = datetime.now(UTC)
    await job.save()
    return job


async def delete_job(user: User, job_id: PydanticObjectId) -> None:
    job = await get_job_or_404(job_id)
    assert_can_edit(user, job)

    if await Application.find(Application.job_id == job.id).count() > 0:
        # Applications reference this job; archiving preserves candidate history.
        job.status = JobStatus.ARCHIVED
        job.closed_at = datetime.now(UTC)
        await job.save()
        return

    await job.delete()


async def get_job_or_404(job_id: PydanticObjectId) -> Job:
    job = await Job.get(job_id)
    if job is None:
        raise NotFoundError("Job not found")
    return job


async def get_public_job(job_id: PydanticObjectId) -> Job:
    job = await get_job_or_404(job_id)
    if job.status not in (JobStatus.PUBLISHED, JobStatus.PAUSED, JobStatus.CLOSED):
        raise NotFoundError("Job not found")
    return job


def _build_filter(
    *,
    search: str | None,
    category: str | None,
    seniority: SeniorityLevel | None,
    work_mode: WorkMode | None,
    statuses: list[JobStatus] | None,
    created_by: PydanticObjectId | None = None,
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if statuses:
        query["status"] = {"$in": [s.value for s in statuses]}
    if category:
        query["job_category"] = category
    if seniority:
        query["seniority"] = seniority.value
    if work_mode:
        query["work_mode"] = work_mode.value
    if created_by:
        query["created_by"] = created_by
    if search:
        query["$text"] = {"$search": search}
    return query


async def list_jobs(
    *,
    skip: int,
    limit: int,
    search: str | None = None,
    category: str | None = None,
    seniority: SeniorityLevel | None = None,
    work_mode: WorkMode | None = None,
    statuses: list[JobStatus] | None = None,
    created_by: PydanticObjectId | None = None,
    sort: str = "-published_at",
) -> tuple[list[Job], int]:
    query = _build_filter(
        search=search,
        category=category,
        seniority=seniority,
        work_mode=work_mode,
        statuses=statuses,
        created_by=created_by,
    )
    cursor = Job.find(query)
    total = await cursor.count()
    items = await cursor.sort(sort).skip(skip).limit(limit).to_list()
    return items, total


async def applied_job_ids(candidate_id: PydanticObjectId, jobs: list[Job]) -> set[PydanticObjectId]:
    """One query for a whole page of job cards instead of one per card."""
    if not jobs:
        return set()
    ids = [j.id for j in jobs]
    apps = await Application.find(
        Application.candidate_id == candidate_id, In(Application.job_id, ids)
    ).to_list()
    return {a.job_id for a in apps}


async def increment_view(job_id: PydanticObjectId) -> None:
    await Job.get_pymongo_collection().update_one({"_id": job_id}, {"$inc": {"stats.views": 1}})
