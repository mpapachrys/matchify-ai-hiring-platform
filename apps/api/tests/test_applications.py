"""The vertical slice: manager posts a job → candidate applies → pipeline moves."""

import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.conftest import register

JOB_PAYLOAD = {
    "title": "Senior Backend Engineer",
    "description": "Own the services behind matching.",
    "mandatory": {
        "skills": [
            {"slug": "python", "name": "Python", "min_years": 2},
            {"slug": "fastapi", "name": "FastAPI"},
        ],
        "min_years_total_experience": 3,
    },
    "seniority": "senior",
    "status": "published",
}


async def _manager_with_job(client: AsyncClient, api: str) -> dict:
    await register(client, api, email="pipeline-mgr@matchify.dev", role="hiring_manager")
    response = await client.post(f"{api}/jobs", json=JOB_PAYLOAD)
    assert response.status_code == 201, response.text
    return response.json()


async def test_full_hiring_flow(client: AsyncClient, api: str):
    job = await _manager_with_job(client, api)
    # Skills are normalized on write so matching never depends on casing.
    # Derived on save from `mandatory.skills`.
    assert job["skills_required"] == ["python", "fastapi"]
    await client.post(f"{api}/auth/logout")

    await register(client, api, email="applicant@example.com", role="candidate")
    applied = await client.post(
        f"{api}/applications",
        json={"job_id": job["id"], "cover_letter": "I would like to apply."},
    )
    assert applied.status_code == 201
    application_id = applied.json()["id"]
    assert applied.json()["stage"] == "applied"

    # The candidate response must not carry manager-only fields.
    assert "notes" not in applied.json()
    assert "rating" not in applied.json()

    await client.post(f"{api}/auth/logout")

    await client.post(
        f"{api}/auth/login",
        json={"email": "pipeline-mgr@matchify.dev", "password": "Passw0rd!"},
    )
    moved = await client.patch(
        f"{api}/applications/{application_id}/stage",
        json={"stage": "interview", "note": "Strong screen"},
    )
    assert moved.status_code == 200
    body = moved.json()
    assert body["stage"] == "interview"
    assert body["is_shortlisted"] is True
    assert len(body["stage_history"]) == 2

    # The denormalized counter tracked the transition.
    refreshed = (await client.get(f"{api}/jobs/{job['id']}/manage")).json()
    assert refreshed["stats"]["applications"] == 1
    assert refreshed["stats"]["shortlisted"] == 1


async def test_duplicate_application_is_blocked(client: AsyncClient, api: str):
    job = await _manager_with_job(client, api)
    await client.post(f"{api}/auth/logout")

    await register(client, api, email="twice@example.com", role="candidate")
    first = await client.post(f"{api}/applications", json={"job_id": job["id"]})
    second = await client.post(f"{api}/applications", json={"job_id": job["id"]})

    assert first.status_code == 201
    assert second.status_code == 409


async def test_concurrent_applications_cannot_both_succeed(client: AsyncClient, api: str):
    """The unique index — not an app-layer pre-check — is what holds here."""
    job = await _manager_with_job(client, api)
    await client.post(f"{api}/auth/logout")
    await register(client, api, email="racer@example.com", role="candidate")

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=client.cookies
    ) as racer:
        results = await asyncio.gather(
            racer.post(f"{api}/applications", json={"job_id": job["id"]}),
            racer.post(f"{api}/applications", json={"job_id": job["id"]}),
        )

    codes = sorted(r.status_code for r in results)
    assert codes == [201, 409]


async def test_candidate_sees_only_their_own_application(client: AsyncClient, api: str):
    job = await _manager_with_job(client, api)
    await client.post(f"{api}/auth/logout")

    await register(client, api, email="owner@example.com", role="candidate")
    application_id = (
        await client.post(f"{api}/applications", json={"job_id": job["id"]})
    ).json()["id"]
    await client.post(f"{api}/auth/logout")

    await register(client, api, email="snoop@example.com", role="candidate")
    response = await client.get(f"{api}/applications/me/{application_id}")
    # 404, not 403 — the existence of another candidate's application is not
    # information this user is entitled to.
    assert response.status_code == 404


async def test_withdraw_closes_the_application(client: AsyncClient, api: str):
    job = await _manager_with_job(client, api)
    await client.post(f"{api}/auth/logout")

    await register(client, api, email="quitter@example.com", role="candidate")
    application_id = (
        await client.post(f"{api}/applications", json={"job_id": job["id"]})
    ).json()["id"]

    withdrawn = await client.post(f"{api}/applications/{application_id}/withdraw")
    assert withdrawn.status_code == 200
    assert withdrawn.json()["stage"] == "withdrawn"

    again = await client.post(f"{api}/applications/{application_id}/withdraw")
    assert again.status_code == 409


async def test_applying_to_a_draft_job_is_not_possible(client: AsyncClient, api: str):
    await register(client, api, email="draft-mgr@matchify.dev", role="hiring_manager")
    job = (
        await client.post(f"{api}/jobs", json={**JOB_PAYLOAD, "status": "draft"})
    ).json()
    await client.post(f"{api}/auth/logout")

    await register(client, api, email="eager@example.com", role="candidate")
    response = await client.post(f"{api}/applications", json={"job_id": job["id"]})
    assert response.status_code == 404
