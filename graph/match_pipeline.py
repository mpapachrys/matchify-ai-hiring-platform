"""Per-item match pipeline: ingest -> score -> write back -> clean up.

For each application in the AI team's scoring queue
(GET /graph/applications?match_status=pending), pulls in just that candidate
and job, scores the candidate against the job's mandatory and nice-to-have
requirements (graph/matching.py:score_match), and posts the result back
through POST /applications/{id}/match. The graph is wiped back down to the
static taxonomy after each item (graph/reset.py:wipe_except_taxonomy) so the
scoring surface stays just the taxonomy plus whichever single candidate/job
pair is currently being evaluated, rather than accumulating every
application ever processed.

Every application gets a write-back, whether or not the candidate clears the
mandatory gate (2026-07-25 decision, reversing the original "leave it
pending" default) — score_match() scores a mandatory miss below 0.6 rather
than skipping it, so "did not qualify" is a real, visible, low score instead
of silence. This does mean scores are frozen at whatever score_match()
returns (application_service.record_match never re-fires for the same
application), so a heuristic that's later found to be wrong can't be
corrected retroactively for applications already posted — only prospectively.

What actually gets POSTed (2026-07-25 product decision) is trimmed to just
`confidence` and a `factors: {"justification": "..."}` — the plain-language
reason, nothing else. score_match()'s richer internal factors
(mandatory_met, satisfied/total counts, evaluation_source) stay in this
process's own logs, not in what a manager sees on the application.

One item failing (a bad payload, a network blip on the write-back) is logged
and does not stop the rest of the batch — the graph is cleaned up in a
`finally` regardless, and the application simply gets retried next cycle
since it's still pending server-side until a write-back succeeds.
"""

import logging

from graph.api_client import fetch_candidate, fetch_job, fetch_pending_applications, post_match
from graph.ingest import add_candidate, add_job
from graph.matching import score_match
from graph.reset import wipe_except_taxonomy

logger = logging.getLogger(__name__)


def process_pending(session) -> dict:
    applications = fetch_pending_applications()

    scored = 0
    failed = 0

    for application in applications:
        application_id = application["application_id"]
        candidate_id = application["candidate_id"]
        job_id = application["job_id"]

        try:
            candidate = fetch_candidate(candidate_id)
            job = fetch_job(job_id)
            add_candidate(session, candidate)
            # GraphJob.company_id is always "org" (single-tenant, platform-
            # computed) — trusted here for the same reason graph/pending_sync.py
            # trusts it, unlike --jobs/add_job's caller-supplied company_id.
            add_job(session, job, job.get("company_id", "org"))

            confidence, factors = score_match(session, candidate, job)
            # Only confidence + a plain-language justification actually go to
            # the API (2026-07-25 product decision) — mandatory_met/satisfied/
            # total/evaluation_source stay internal (logged below), not part
            # of what a manager sees on the application.
            post_match(application_id, confidence, factors={"justification": factors.get("justification", "")})
            scored += 1
            logger.info(
                "scored application %s: confidence=%.4f mandatory_met=%s source=%s",
                application_id,
                confidence,
                factors.get("mandatory_met"),
                factors.get("evaluation_source"),
            )
        except Exception:
            failed += 1
            logger.exception("failed to process application %s", application_id)
        finally:
            wipe_except_taxonomy(session)

    return {
        "applications": len(applications),
        "scored": scored,
        "failed": failed,
    }
