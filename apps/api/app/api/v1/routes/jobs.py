from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, Query, status

from app.api.deps import CurrentManager, OptionalUser, Paginate
from app.models.candidate_profile import CandidateProfile
from app.models.enums import JobStatus, Role, SeniorityLevel, WorkMode
from app.schemas.common import MessageOut, Page
from app.schemas.job import JobCreateIn, JobManagerOut, JobOut, JobUpdateIn
from app.services import job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ── manager routes first: static segments must not be captured by /{job_id} ──

@router.get("/manage", response_model=Page[JobManagerOut])
async def list_managed_jobs(
    user: CurrentManager,
    page: Paginate,
    search: Annotated[str | None, Query()] = None,
    job_status: Annotated[JobStatus | None, Query(alias="status")] = None,
    mine_only: Annotated[bool, Query()] = False,
) -> Page[JobManagerOut]:
    """Every manager sees every job — single-tenant. `mine_only` is a filter,
    not a permission boundary."""
    jobs, total = await job_service.list_jobs(
        skip=page.skip,
        limit=page.page_size,
        search=search,
        statuses=[job_status] if job_status else None,
        created_by=user.id if mine_only else None,
        sort="-created_at",
    )
    return Page.build(
        [JobManagerOut.build_manager(j, can_edit=job_service.can_edit(user, j)) for j in jobs],
        total,
        page.page,
        page.page_size,
    )


@router.post("", response_model=JobManagerOut, status_code=status.HTTP_201_CREATED)
async def create_job(data: JobCreateIn, user: CurrentManager) -> JobManagerOut:
    job = await job_service.create_job(user, data)
    return JobManagerOut.build_manager(job, can_edit=True)


@router.get("", response_model=Page[JobOut])
async def list_jobs(
    page: Paginate,
    viewer: OptionalUser,
    search: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    seniority: Annotated[SeniorityLevel | None, Query()] = None,
    work_mode: Annotated[WorkMode | None, Query()] = None,
) -> Page[JobOut]:
    """Public job board. Only published postings are ever returned."""
    jobs, total = await job_service.list_jobs(
        skip=page.skip,
        limit=page.page_size,
        search=search,
        category=category,
        seniority=seniority,
        work_mode=work_mode,
        statuses=[JobStatus.PUBLISHED],
    )

    applied: set[PydanticObjectId] = set()
    saved: set[PydanticObjectId] = set()
    if viewer and viewer.role is Role.CANDIDATE:
        applied = await job_service.applied_job_ids(viewer.id, jobs)
        profile = await CandidateProfile.find_one(CandidateProfile.user_id == viewer.id)
        saved = set(profile.saved_job_ids) if profile else set()

    return Page.build(
        [
            JobOut.build(j, has_applied=j.id in applied, is_saved=j.id in saved)
            for j in jobs
        ],
        total,
        page.page,
        page.page_size,
    )


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: PydanticObjectId, viewer: OptionalUser) -> JobOut:
    job = await job_service.get_public_job(job_id)
    await job_service.increment_view(job_id)

    has_applied = False
    is_saved = False
    if viewer and viewer.role is Role.CANDIDATE:
        has_applied = bool(await job_service.applied_job_ids(viewer.id, [job]))
        profile = await CandidateProfile.find_one(CandidateProfile.user_id == viewer.id)
        is_saved = bool(profile and job.id in profile.saved_job_ids)

    return JobOut.build(job, has_applied=has_applied, is_saved=is_saved)


@router.get("/{job_id}/manage", response_model=JobManagerOut)
async def get_job_for_manager(job_id: PydanticObjectId, user: CurrentManager) -> JobManagerOut:
    job = await job_service.get_job_or_404(job_id)
    return JobManagerOut.build_manager(job, can_edit=job_service.can_edit(user, job))


@router.patch("/{job_id}", response_model=JobManagerOut)
async def update_job(
    job_id: PydanticObjectId, data: JobUpdateIn, user: CurrentManager
) -> JobManagerOut:
    job = await job_service.update_job(user, job_id, data)
    return JobManagerOut.build_manager(job, can_edit=True)


@router.post("/{job_id}/publish", response_model=JobManagerOut)
async def publish_job(job_id: PydanticObjectId, user: CurrentManager) -> JobManagerOut:
    job = await job_service.update_job(user, job_id, JobUpdateIn(status=JobStatus.PUBLISHED))
    return JobManagerOut.build_manager(job, can_edit=True)


@router.post("/{job_id}/close", response_model=JobManagerOut)
async def close_job(job_id: PydanticObjectId, user: CurrentManager) -> JobManagerOut:
    job = await job_service.update_job(user, job_id, JobUpdateIn(status=JobStatus.CLOSED))
    return JobManagerOut.build_manager(job, can_edit=True)


@router.delete("/{job_id}", response_model=MessageOut)
async def delete_job(job_id: PydanticObjectId, user: CurrentManager) -> MessageOut:
    await job_service.delete_job(user, job_id)
    return MessageOut(detail="Job removed")
