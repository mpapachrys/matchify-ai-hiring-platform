"""Interview scheduling: a manager approves, the candidate books the slot.

`CALENDAR_ASSISTANT_URL` is unset in this suite (see conftest.py's env-var
pinning), so the assistant integration itself is never exercised over the
network here — only calendar_service's own logic: the fail-closed 503 when
unconfigured, and (via monkeypatching the integration) the two-step
approve/book flow and its conflict guards.
"""

from httpx import AsyncClient

from app.core.config import settings
from app.integrations import calendar_assistant
from tests.conftest import register

JOB_PAYLOAD = {
    "title": "Backend Engineer",
    "description": "Own the services behind matching.",
    "mandatory": {"skills": [{"slug": "python", "name": "Python", "min_years": 2}]},
    "seniority": "mid",
    "status": "published",
}

BOOKING_PAYLOAD = {"date": "2026-07-27", "slot": "13:00-14:00"}


async def _manager_candidate_application(client: AsyncClient, api: str) -> str:
    """Registers a manager with a published job, a candidate who applies to
    it, and leaves the client logged in as the manager. Returns the
    application id."""
    await register(client, api, email="cal-mgr@matchify.dev", role="hiring_manager")
    job = (await client.post(f"{api}/jobs", json=JOB_PAYLOAD)).json()
    await client.post(f"{api}/auth/logout")

    await register(client, api, email="cal-candidate@example.com", role="candidate")
    application_id = (
        await client.post(f"{api}/applications", json={"job_id": job["id"]})
    ).json()["id"]
    await client.post(f"{api}/auth/logout")

    await client.post(
        f"{api}/auth/login", json={"email": "cal-mgr@matchify.dev", "password": "Passw0rd!"}
    )
    return application_id


async def _login_candidate(client: AsyncClient, api: str) -> None:
    await client.post(f"{api}/auth/logout")
    await client.post(
        f"{api}/auth/login", json={"email": "cal-candidate@example.com", "password": "Passw0rd!"}
    )


async def test_approve_without_calendar_configured_returns_503(client: AsyncClient, api: str):
    assert not settings.calendar_assistant_url  # sanity: the suite default
    application_id = await _manager_candidate_application(client, api)

    response = await client.post(f"{api}/applications/{application_id}/interview/approve")
    assert response.status_code == 503

    unchanged = await client.get(f"{api}/applications/{application_id}")
    assert unchanged.json()["stage"] == "applied"
    assert unchanged.json()["interview"]["status"] == "none"


async def test_approve_moves_stage_and_awaits_candidate(client: AsyncClient, api: str, monkeypatch):
    monkeypatch.setattr(settings, "calendar_assistant_url", "http://fake-calendar-mcp:8090")
    application_id = await _manager_candidate_application(client, api)

    response = await client.post(f"{api}/applications/{application_id}/interview/approve")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["stage"] == "interview"
    assert body["interview"]["status"] == "awaiting_candidate"
    assert body["interview"]["scheduled_start"] is None

    # The manager cannot book on the candidate's behalf.
    manager_books = await client.post(
        f"{api}/applications/{application_id}/interview/book", json=BOOKING_PAYLOAD
    )
    assert manager_books.status_code == 403


async def test_candidate_cannot_book_without_approval(client: AsyncClient, api: str, monkeypatch):
    monkeypatch.setattr(settings, "calendar_assistant_url", "http://fake-calendar-mcp:8090")
    application_id = await _manager_candidate_application(client, api)
    await _login_candidate(client, api)

    response = await client.post(
        f"{api}/applications/{application_id}/interview/book", json=BOOKING_PAYLOAD
    )
    assert response.status_code == 409


async def test_candidate_books_after_approval(client: AsyncClient, api: str, monkeypatch):
    monkeypatch.setattr(settings, "calendar_assistant_url", "http://fake-calendar-mcp:8090")

    async def fake_schedule_interview(**_kwargs):
        return {
            "status": "scheduled",
            "start": "2026-07-27T13:00:00+03:00",
            "end": "2026-07-27T14:00:00+03:00",
            "event_id": "evt-123",
            "html_link": "https://calendar.example/evt-123",
            "message": "Interview booked for 2026-07-27 13:00-14:00.",
        }

    monkeypatch.setattr(calendar_assistant, "schedule_interview", fake_schedule_interview)

    application_id = await _manager_candidate_application(client, api)
    await client.post(f"{api}/applications/{application_id}/interview/approve")
    await _login_candidate(client, api)

    response = await client.post(
        f"{api}/applications/{application_id}/interview/book", json=BOOKING_PAYLOAD
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "scheduled"

    mine = await client.get(f"{api}/applications/me/{application_id}")
    assert mine.json()["interview"]["status"] == "scheduled"
    assert mine.json()["interview"]["event_id"] == "evt-123"


async def test_booking_conflict_leaves_status_awaiting_candidate(
    client: AsyncClient, api: str, monkeypatch
):
    monkeypatch.setattr(settings, "calendar_assistant_url", "http://fake-calendar-mcp:8090")

    async def fake_schedule_interview(**_kwargs):
        return {
            "status": "conflict",
            "start": None,
            "end": None,
            "event_id": None,
            "html_link": None,
            "message": "That slot is already booked.",
        }

    monkeypatch.setattr(calendar_assistant, "schedule_interview", fake_schedule_interview)

    application_id = await _manager_candidate_application(client, api)
    await client.post(f"{api}/applications/{application_id}/interview/approve")
    await _login_candidate(client, api)

    response = await client.post(
        f"{api}/applications/{application_id}/interview/book", json=BOOKING_PAYLOAD
    )
    assert response.status_code == 200
    assert response.json()["status"] == "conflict"

    mine = await client.get(f"{api}/applications/me/{application_id}")
    assert mine.json()["interview"]["status"] == "awaiting_candidate"


async def test_cancel_before_booking_revokes_approval(client: AsyncClient, api: str, monkeypatch):
    monkeypatch.setattr(settings, "calendar_assistant_url", "http://fake-calendar-mcp:8090")
    application_id = await _manager_candidate_application(client, api)
    await client.post(f"{api}/applications/{application_id}/interview/approve")

    response = await client.delete(f"{api}/applications/{application_id}/interview")
    assert response.status_code == 200
    assert response.json()["interview"]["status"] == "none"


async def test_cancel_without_any_interview_is_a_conflict(
    client: AsyncClient, api: str, monkeypatch
):
    monkeypatch.setattr(settings, "calendar_assistant_url", "http://fake-calendar-mcp:8090")
    application_id = await _manager_candidate_application(client, api)

    response = await client.delete(f"{api}/applications/{application_id}/interview")
    assert response.status_code == 409


async def test_cancel_after_booking_clears_the_calendar_event(
    client: AsyncClient, api: str, monkeypatch
):
    monkeypatch.setattr(settings, "calendar_assistant_url", "http://fake-calendar-mcp:8090")

    async def fake_schedule_interview(**_kwargs):
        return {
            "status": "scheduled",
            "start": "2026-07-27T13:00:00+03:00",
            "end": "2026-07-27T14:00:00+03:00",
            "event_id": "evt-456",
            "html_link": "https://calendar.example/evt-456",
            "message": "Interview booked.",
        }

    cancelled_event_ids: list[str] = []

    async def fake_cancel_interview(event_id: str) -> None:
        cancelled_event_ids.append(event_id)

    monkeypatch.setattr(calendar_assistant, "schedule_interview", fake_schedule_interview)
    monkeypatch.setattr(calendar_assistant, "cancel_interview", fake_cancel_interview)

    application_id = await _manager_candidate_application(client, api)
    await client.post(f"{api}/applications/{application_id}/interview/approve")
    await _login_candidate(client, api)
    await client.post(f"{api}/applications/{application_id}/interview/book", json=BOOKING_PAYLOAD)

    await client.post(f"{api}/auth/logout")
    await client.post(
        f"{api}/auth/login", json={"email": "cal-mgr@matchify.dev", "password": "Passw0rd!"}
    )
    response = await client.delete(f"{api}/applications/{application_id}/interview")
    assert response.status_code == 200
    assert response.json()["interview"]["status"] == "cancelled"
    assert cancelled_event_ids == ["evt-456"]
    # Cancelling does not revert the pipeline stage — that stays a separate,
    # explicit action via PATCH /applications/{id}/stage.
    assert response.json()["stage"] == "interview"


async def test_terminal_stage_application_cannot_be_approved(
    client: AsyncClient, api: str, monkeypatch
):
    monkeypatch.setattr(settings, "calendar_assistant_url", "http://fake-calendar-mcp:8090")
    application_id = await _manager_candidate_application(client, api)

    reject = await client.patch(
        f"{api}/applications/{application_id}/stage", json={"stage": "rejected"}
    )
    assert reject.status_code == 200

    response = await client.post(f"{api}/applications/{application_id}/interview/approve")
    assert response.status_code == 409


async def test_approving_twice_is_a_conflict(client: AsyncClient, api: str, monkeypatch):
    monkeypatch.setattr(settings, "calendar_assistant_url", "http://fake-calendar-mcp:8090")
    application_id = await _manager_candidate_application(client, api)

    first = await client.post(f"{api}/applications/{application_id}/interview/approve")
    assert first.status_code == 200
    second = await client.post(f"{api}/applications/{application_id}/interview/approve")
    assert second.status_code == 409
