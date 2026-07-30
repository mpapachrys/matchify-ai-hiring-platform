from fastapi import APIRouter

from app.api.deps import CurrentCandidate, CurrentManager
from app.models.candidate_profile import CandidateProfile
from app.schemas.analytics import CandidateAnalyticsOut, ManagerAnalyticsOut
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/candidate", response_model=CandidateAnalyticsOut)
async def candidate_dashboard(candidate: CurrentCandidate) -> CandidateAnalyticsOut:
    data = await analytics_service.candidate_analytics(candidate.id)
    profile = await CandidateProfile.find_one(CandidateProfile.user_id == candidate.id)
    data.profile_completion = profile.completion_percent if profile else 0
    return data


@router.get("/manager", response_model=ManagerAnalyticsOut)
async def manager_dashboard(_: CurrentManager) -> ManagerAnalyticsOut:
    return await analytics_service.manager_analytics()
