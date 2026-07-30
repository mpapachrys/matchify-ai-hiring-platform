"""HTTP client for the Matchify API's graph-export and match write-back endpoints.

Configured from environment variables (.env): MATCHIFY_API_BASE_URL,
MATCHIFY_API_TOKEN. See apps/api/app/api/v1/routes/graph.py and
apps/api/app/schemas/graph.py for the read-side contract this pulls from —
the response items are shaped to match graph/ingest.py's add_candidate/
add_job field-for-field, so no translation happens here. The write-back
(post_match) hits apps/api/app/api/v1/routes/applications.py's
POST /applications/{id}/match, gated by the same service token
(MATCHIFY_API_TOKEN here, INBOUND_AI_TOKEN on the API side — one shared
secret, two env var names).
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

MATCHIFY_API_BASE_URL = os.environ.get(
    "MATCHIFY_API_BASE_URL", "https://api.matchify.gr/api/v1"
).rstrip("/")
MATCHIFY_API_TOKEN = os.environ["MATCHIFY_API_TOKEN"]

_PAGE_SIZE = 100


def _headers() -> dict:
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {MATCHIFY_API_TOKEN}",
    }


def _get(path: str, params: dict | None = None) -> dict:
    response = requests.get(
        f"{MATCHIFY_API_BASE_URL}{path}",
        headers=_headers(),
        params=params or {},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def fetch_pending_applications() -> list[dict]:
    """Every (:Candidate)-[:APPLIED_TO]->(:Job) edge still waiting to be
    scored — walks every page of GET /graph/applications?match_status=pending."""
    items: list[dict] = []
    page = 1
    while True:
        data = _get(
            "/graph/applications",
            {"match_status": "pending", "page": page, "page_size": _PAGE_SIZE},
        )
        items.extend(data["items"])
        if page >= data["pages"]:
            return items
        page += 1


def fetch_candidate(candidate_id: str) -> dict:
    """GET /graph/candidates/{candidate_id} — a single candidate node's full export."""
    return _get(f"/graph/candidates/{candidate_id}")


def fetch_job(job_id: str) -> dict:
    """GET /graph/jobs/{job_id} — a single job node's full export."""
    return _get(f"/graph/jobs/{job_id}")


def post_match(application_id: str, confidence: float, factors: dict | None = None) -> dict:
    """POST /applications/{application_id}/match — write back the match
    confidence (0.0-1.0) and an optional breakdown a manager sees on hover
    (MatchIn.factors, apps/api/app/schemas/application.py). Frozen once
    written; the API only accepts this from a service-token caller, never a
    candidate or manager."""
    payload: dict = {"confidence": confidence}
    if factors:
        payload["factors"] = factors
    response = requests.post(
        f"{MATCHIFY_API_BASE_URL}/applications/{application_id}/match",
        headers={**_headers(), "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
