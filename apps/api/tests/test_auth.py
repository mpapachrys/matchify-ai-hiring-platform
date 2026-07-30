from httpx import AsyncClient

from app.core.config import settings
from tests.conftest import register


async def test_register_sets_httponly_cookies(client: AsyncClient, api: str):
    response = await client.post(
        f"{api}/auth/register",
        json={
            "email": "new@example.com",
            "password": "Passw0rd!",
            "full_name": "New Person",
            "role": "candidate",
        },
    )
    assert response.status_code == 201

    # Tokens must never be readable by JavaScript.
    set_cookie_header = str(response.headers.get_list("set-cookie"))
    assert f"{settings.access_cookie_name}=" in set_cookie_header
    assert "HttpOnly" in set_cookie_header
    # ...and no token is echoed in the body.
    assert "token" not in response.text.lower()


async def test_duplicate_email_is_rejected(client: AsyncClient, api: str):
    await register(client, api, email="dupe@example.com", role="candidate")
    response = await client.post(
        f"{api}/auth/register",
        json={
            "email": "dupe@example.com",
            "password": "Passw0rd!",
            "full_name": "Copy Cat",
            "role": "candidate",
        },
    )
    assert response.status_code == 409


async def test_login_failure_does_not_reveal_whether_the_email_exists(
    client: AsyncClient, api: str
):
    await register(client, api, email="known@example.com", role="candidate")

    wrong_password = await client.post(
        f"{api}/auth/login", json={"email": "known@example.com", "password": "nope"}
    )
    unknown_email = await client.post(
        f"{api}/auth/login", json={"email": "ghost@example.com", "password": "nope"}
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


async def test_first_manager_becomes_admin_and_the_second_does_not(
    client: AsyncClient, api: str
):
    first = await register(client, api, email="boss@matchify.dev", role="hiring_manager")
    second = await register(client, api, email="second@matchify.dev", role="hiring_manager")

    assert first["is_admin"] is True
    assert second["is_admin"] is False


async def test_refresh_rotates_and_replay_burns_the_family(client: AsyncClient, api: str):
    await register(client, api, email="rotate@example.com", role="candidate")
    stolen = client.cookies.get(settings.refresh_cookie_name)

    first = await client.post(f"{api}/auth/refresh")
    assert first.status_code == 200
    assert client.cookies.get(settings.refresh_cookie_name) != stolen

    # Replaying the superseded token is treated as theft.
    client.cookies.set(settings.refresh_cookie_name, stolen)
    replay = await client.post(f"{api}/auth/refresh")
    assert replay.status_code == 401
    assert "reuse" in replay.json()["detail"].lower()


async def test_me_requires_authentication(client: AsyncClient, api: str):
    assert (await client.get(f"{api}/auth/me")).status_code == 401
