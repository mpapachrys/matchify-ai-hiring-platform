"""Candidate export for the AI team's knowledge graph.

Machine-to-machine: authenticated with a service token, not a user session. See
docs/graph-export.md for the contract and the reasoning behind the fields that
differ from the AI team's original proposal.
"""

from datetime import datetime
from math import ceil
from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, Query

from app.api.deps import Paginate, ServiceCaller
from app.core.exceptions import NotFoundError
from app.schemas.graph import (
    SCHEMA_VERSION,
    GraphApplicationPage,
    GraphCandidate,
    GraphCandidatePage,
    GraphJob,
    GraphJobPage,
)
from app.services import graph_service

router = APIRouter(
    prefix="/graph",
    tags=["graph-export"],
    # Spelled out in the schema so the two failure modes are distinguishable
    # from /docs alone: a 403 is our misconfiguration, a 401 is the caller's.
    responses={
        401: {"description": "Missing or wrong service token"},
        403: {"description": "INBOUND_AI_TOKEN is unset — the export is disabled"},
    },
)


@router.get("/candidates", response_model=GraphCandidatePage)
async def list_candidates(
    _: ServiceCaller,
    page: Paginate,
    updated_since: Annotated[
        datetime | None,
        Query(description="ISO timestamp. Returns only profiles changed after it."),
    ] = None,
) -> GraphCandidatePage:
    """Every candidate, or only those changed since a timestamp.

    Ordered by `updated_at` ascending, so a caller can walk pages and use the
    last item's `profile_updated_at` as the next run's `updated_since` without
    missing or repeating anyone.
    """
    items, total = await graph_service.list_candidates(
        skip=page.skip, limit=page.page_size, updated_since=updated_since
    )
    return GraphCandidatePage(
        items=items,
        total=total,
        page=page.page,
        page_size=page.page_size,
        pages=max(1, ceil(total / page.page_size)) if page.page_size else 1,
    )


@router.get("/candidates/{candidate_id}", response_model=GraphCandidate)
async def get_candidate(candidate_id: PydanticObjectId, _: ServiceCaller) -> GraphCandidate:
    candidate = await graph_service.get_candidate(candidate_id)
    if candidate is None:
        raise NotFoundError("Candidate not found")
    return candidate


@router.get("/jobs", response_model=GraphJobPage)
async def list_jobs(
    _: ServiceCaller,
    page: Paginate,
    updated_since: Annotated[
        datetime | None,
        Query(description="ISO timestamp. Returns only jobs changed after it."),
    ] = None,
    include_unpublished: Annotated[
        bool,
        Query(description="Include drafts, paused and closed roles. Off by default."),
    ] = False,
) -> GraphJobPage:
    """Published jobs, or only those changed since a timestamp.

    Drafts and closed roles are excluded unless asked for — recommending
    candidates for a job that does not exist is worse than missing one.
    """
    items, total = await graph_service.list_jobs(
        skip=page.skip,
        limit=page.page_size,
        updated_since=updated_since,
        include_unpublished=include_unpublished,
    )
    return GraphJobPage(
        items=items,
        total=total,
        page=page.page,
        page_size=page.page_size,
        pages=max(1, ceil(total / page.page_size)) if page.page_size else 1,
    )


@router.get("/jobs/{job_id}", response_model=GraphJob)
async def get_job(job_id: PydanticObjectId, _: ServiceCaller) -> GraphJob:
    job = await graph_service.get_job(job_id)
    if job is None:
        raise NotFoundError("Job not found")
    return job


@router.get("/applications", response_model=GraphApplicationPage)
async def list_applications(
    _: ServiceCaller,
    page: Paginate,
    updated_since: Annotated[
        datetime | None,
        Query(description="ISO timestamp. Returns only applications changed after it."),
    ] = None,
    match_status: Annotated[
        str | None,
        Query(description="Filter by match state. Use 'pending' as the scoring queue."),
    ] = None,
) -> GraphApplicationPage:
    """The (:Candidate)-[:APPLIED_TO]->(:Job) edges.

    Just the ids — the nodes come from the by-id endpoints. Ordered by
    `updated_at` ascending for the same incremental `updated_since` walk as the
    other feeds. `match_status=pending` is the AI team's scoring queue.
    """
    items, total = await graph_service.list_applications(
        skip=page.skip,
        limit=page.page_size,
        updated_since=updated_since,
        match_status=match_status,
    )
    return GraphApplicationPage(
        items=items,
        total=total,
        page=page.page,
        page_size=page.page_size,
        pages=max(1, ceil(total / page.page_size)) if page.page_size else 1,
    )


@router.get("/schema-version")
async def schema_version(_: ServiceCaller) -> dict[str, str]:
    """Cheap probe: confirms the token works and reports the contract version."""
    return {"schema_version": SCHEMA_VERSION}
