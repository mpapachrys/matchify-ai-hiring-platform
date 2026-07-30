"""Test harness.

Runs against the same MongoDB instance as the app but in a throwaway database,
dropped after the session. Real Mongo rather than a mock, because the unique
index on (job_id, candidate_id) is load-bearing behaviour — mocking it out
would test nothing.
"""

import os
import uuid

import pytest
import pytest_asyncio
from beanie import init_beanie
from httpx import ASGITransport, AsyncClient
from pymongo import AsyncMongoClient

TEST_DB = f"matchify_test_{uuid.uuid4().hex[:8]}"
os.environ.setdefault("MONGO_DB", TEST_DB)
os.environ["MONGO_DB"] = TEST_DB
# The graph endpoints fail closed when this is unset, so the tests need a value
# to exercise them at all.
os.environ["INBOUND_AI_TOKEN"] = "test-service-token"
os.environ["SEED_ON_STARTUP"] = "false"
# The suite must never reach a paid API. Locally `make test` runs inside the dev
# container, which has the real .env loaded — so without these two lines a test
# that touched the parse path would quietly spend money against the live key.
# Pinned here rather than in CI so it holds wherever the tests run.
os.environ["RESUME_PARSER"] = "stub"
os.environ["OPENROUTER_API_KEY"] = ""
# Same reasoning: the suite must never reach the real calendar-mcp container.
# Individual tests that need the "configured" path monkeypatch this back in.
os.environ["CALENDAR_ASSISTANT_URL"] = ""

from app.core.config import settings  # noqa: E402
from app.db import mongo  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _database():
    client = AsyncMongoClient(settings.mongo_url, uuidRepresentation="standard")
    mongo._client = client
    await init_beanie(database=client[TEST_DB], document_models=mongo.DOCUMENT_MODELS)
    yield
    await client.drop_database(TEST_DB)
    await client.close()


@pytest_asyncio.fixture(autouse=True)
async def _clean_collections():
    for model in mongo.DOCUMENT_MODELS:
        await model.get_pymongo_collection().delete_many({})
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def api() -> str:
    return settings.api_v1_prefix


async def register(client: AsyncClient, api: str, *, email: str, role: str) -> dict:
    response = await client.post(
        f"{api}/auth/register",
        json={
            "email": email,
            "password": "Passw0rd!",
            "full_name": email.split("@")[0].title(),
            "role": role,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["user"]
