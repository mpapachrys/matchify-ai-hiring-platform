"""Tell the AI team an application is waiting to be scored.

Fired from a FastAPI BackgroundTask after `POST /applications` returns, so the
apply itself never waits on it. Best-effort by design:

* A missing URL is a no-op — the feature is simply off until configured.
* Any failure is logged and swallowed. The AI team also reconciles from
  `GET /graph/applications?match_status=pending`, so a dropped webhook is caught
  on their next poll, never lost.

The platform does not call the AI team for the score — this only *notifies*.
They read the candidate and job from the graph export and write the result back
through `POST /applications/{id}/match`.
"""

import logging

import httpx
from beanie import PydanticObjectId

from app.core.config import settings

logger = logging.getLogger(__name__)

# Short: this runs after the response is sent, but a hung receiver should not
# tie up a worker indefinitely.
TIMEOUT = httpx.Timeout(10.0, connect=5.0)


async def notify_application(
    application_id: PydanticObjectId,
    candidate_id: PydanticObjectId,
    job_id: PydanticObjectId,
) -> None:
    url = settings.ai_match_webhook_url
    if not url:
        return

    headers = {"content-type": "application/json"}
    if settings.ai_match_webhook_token:
        headers["x-matchify-token"] = settings.ai_match_webhook_token

    payload = {
        "event": "application.created",
        "application_id": str(application_id),
        "candidate_id": str(candidate_id),
        "job_id": str(job_id),
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        logger.info("match webhook sent for application %s", application_id)
    except Exception as exc:  # noqa: BLE001 — a webhook failure must never surface
        logger.warning("match webhook failed for application %s: %s", application_id, exc)
