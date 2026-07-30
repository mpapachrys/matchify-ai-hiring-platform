"""The role boundary is the security-critical surface — test it directly."""

from httpx import AsyncClient

from tests.conftest import register

JOB_PAYLOAD = {
    "title": "Test Engineer",
    "description": "Testing things",
    "mandatory": {"skills": [{"slug": "python", "name": "Python"}]},
    "status": "published",
}


async def test_candidate_cannot_create_a_job(client: AsyncClient, api: str):
    await register(client, api, email="cand@example.com", role="candidate")
    response = await client.post(f"{api}/jobs", json=JOB_PAYLOAD)
    assert response.status_code == 403


async def test_anonymous_cannot_create_a_job(client: AsyncClient, api: str):
    assert (await client.post(f"{api}/jobs", json=JOB_PAYLOAD)).status_code == 401


async def test_manager_cannot_apply_to_a_job(client: AsyncClient, api: str):
    await register(client, api, email="mgr@matchify.dev", role="hiring_manager")
    job = (await client.post(f"{api}/jobs", json=JOB_PAYLOAD)).json()

    response = await client.post(f"{api}/applications", json={"job_id": job["id"]})
    assert response.status_code == 403


async def test_candidate_cannot_read_the_manager_applicant_feed(client: AsyncClient, api: str):
    await register(client, api, email="nosy@example.com", role="candidate")
    assert (await client.get(f"{api}/applications/manage")).status_code == 403


async def test_draft_jobs_are_absent_from_the_public_board(client: AsyncClient, api: str):
    await register(client, api, email="mgr2@matchify.dev", role="hiring_manager")
    await client.post(f"{api}/jobs", json={**JOB_PAYLOAD, "title": "Secret Draft", "status": "draft"})
    await client.post(f"{api}/auth/logout")

    listing = (await client.get(f"{api}/jobs")).json()
    assert all(item["title"] != "Secret Draft" for item in listing["items"])


async def test_non_admin_manager_cannot_edit_organization_settings(
    client: AsyncClient, api: str
):
    await register(client, api, email="admin@matchify.dev", role="hiring_manager")
    await client.post(f"{api}/auth/logout")

    await register(client, api, email="plain@matchify.dev", role="hiring_manager")
    response = await client.patch(f"{api}/organization", json={"name": "Hijacked"})
    assert response.status_code == 403


async def test_manager_cannot_open_a_profile_of_someone_who_never_applied(
    client: AsyncClient, api: str
):
    candidate = await register(client, api, email="private@example.com", role="candidate")
    await client.post(f"{api}/auth/logout")

    await register(client, api, email="mgr3@matchify.dev", role="hiring_manager")
    response = await client.get(f"{api}/candidates/{candidate['id']}/profile")
    assert response.status_code == 403
