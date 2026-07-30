"""Sync the Neo4j graph from the AI team's scoring queue.

Replaces the old bulk `--from-api` sweep (which pulled every candidate/job on
a schedule). This instead follows the actual work: poll
`GET /graph/applications?match_status=pending` (apps/api/app/api/v1/routes/graph.py)
for applications still waiting to be scored, then fetch and ingest exactly the
candidate and job each one points at (`GET /graph/candidates/{id}`,
`GET /graph/jobs/{id}`) — so the graph has fresh data for the pairs that are
about to be matched, without walking the whole platform every run.

Scoring itself (writing a result back through `POST /applications/{id}/match`)
is not done here — this only builds the graph. The AI team's polling of
match_status=pending means an application not yet ingested this run will
simply be picked up again next run; ingestion is idempotent (MERGE-based, see
graph/ingest.py) so re-processing a pending application is harmless.
"""

from graph.api_client import fetch_candidate, fetch_job, fetch_pending_applications
from graph.ingest import add_candidate, add_job


def sync_pending(session) -> dict:
    applications = fetch_pending_applications()

    seen_candidates: set[str] = set()
    seen_jobs: set[str] = set()

    for application in applications:
        candidate_id = application["candidate_id"]
        job_id = application["job_id"]

        if candidate_id not in seen_candidates:
            candidate = fetch_candidate(candidate_id)
            add_candidate(session, candidate)
            seen_candidates.add(candidate_id)

        if job_id not in seen_jobs:
            job = fetch_job(job_id)
            # GraphJob.company_id is always "org" (single-tenant, platform-
            # computed) — trusted here for the same reason the old
            # add_jobs_from_export trusted it, unlike --jobs/add_job's
            # caller-supplied company_id.
            add_job(session, job, job.get("company_id", "org"))
            seen_jobs.add(job_id)

    return {
        "applications": len(applications),
        "candidates": len(seen_candidates),
        "jobs": len(seen_jobs),
    }
