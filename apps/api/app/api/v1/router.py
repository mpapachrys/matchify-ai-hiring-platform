from fastapi import APIRouter

from app.api.v1.routes import (
    analytics,
    applications,
    auth,
    calendar,
    candidates,
    documents,
    graph,
    jobs,
    organization,
    resume,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(organization.router)
api_router.include_router(jobs.router)
api_router.include_router(applications.router)
api_router.include_router(candidates.router)
api_router.include_router(documents.router)
api_router.include_router(resume.router)
api_router.include_router(graph.router)
api_router.include_router(analytics.router)
api_router.include_router(calendar.router)
