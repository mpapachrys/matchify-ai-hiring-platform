"""Mongo lifecycle: one client for the process, Beanie bound to the models.

The compose stack runs a single-node replica set, so `transaction()` gives us
real multi-document atomicity — used where a write must not drift from a
denormalized counter.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from beanie import init_beanie
from pymongo import AsyncMongoClient
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import settings
from app.models.application import Application
from app.models.candidate_profile import CandidateProfile
from app.models.document import UserDocument
from app.models.job import Job
from app.models.organization import Organization
from app.models.refresh_token import RefreshToken
from app.models.user import User

logger = logging.getLogger(__name__)

T = TypeVar("T")

DOCUMENT_MODELS = [
    User,
    CandidateProfile,
    Organization,
    Job,
    Application,
    UserDocument,
    RefreshToken,
]

_client: AsyncMongoClient | None = None


async def connect() -> AsyncDatabase:
    """Create the client and let Beanie build every index declared on a model."""
    global _client
    _client = AsyncMongoClient(settings.mongo_url, uuidRepresentation="standard")
    db = _client[settings.mongo_db]
    await init_beanie(database=db, document_models=DOCUMENT_MODELS)
    logger.info("mongo connected db=%s models=%d", settings.mongo_db, len(DOCUMENT_MODELS))
    return db


async def disconnect() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def get_client() -> AsyncMongoClient:
    if _client is None:
        raise RuntimeError("Mongo client not initialized — call connect() first")
    return _client


async def run_in_transaction(operation: Callable[[AsyncClientSession], Awaitable[T]]) -> T:
    """Run `operation` inside a transaction, retrying transient conflicts.

    Callback form rather than a context manager, and deliberately so: when two
    transactions touch the same document MongoDB aborts one with a
    `TransientTransactionError` and expects the *client* to replay it. A context
    manager cannot re-run its own body, so it would surface a write conflict as
    a 500 — which is exactly what concurrent applications to one job produce,
    since they all increment the same counter.

    `with_transaction` handles that replay, plus the commit-retry case where the
    outcome is unknown. Non-transient failures (a duplicate key, for instance)
    propagate on the first attempt, so callers still catch them normally.
    """
    client = get_client()
    async with client.start_session() as session:
        return await session.with_transaction(operation)
