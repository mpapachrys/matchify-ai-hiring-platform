import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.db import mongo

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)
logger = logging.getLogger("matchify")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await mongo.connect()

    # The organization singleton must exist before anything reads it.
    from app.services import organization_service

    await organization_service.get_organization()

    if settings.seed_on_startup and not settings.is_production:
        from app.db.seed import seed_if_empty

        await seed_if_empty()

    logger.info(
        "api ready environment=%s resume_parser=%s",
        settings.environment,
        settings.resume_parser,
    )
    yield
    await mongo.disconnect()


app = FastAPI(
    title="Matchify.ai API",
    version="0.1.0",
    description=(
        "Single-tenant hiring platform. Candidates apply; hiring managers post "
        "jobs and run pipelines. AI scoring is delegated through a swappable seam."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# The browser reaches this service through the Next.js proxy, so it is
# same-origin and needs no CORS. This exists only for direct API clients
# (curl, the OpenAPI page, a native app later).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "environment": settings.environment}
