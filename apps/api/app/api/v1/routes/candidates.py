from beanie import PydanticObjectId
from fastapi import APIRouter

from app.api.deps import CurrentCandidate, CurrentManager
from app.core.exceptions import NotFoundError
from app.models.candidate_profile import CandidateProfile
from app.models.user import User
from app.schemas.common import MessageOut
from app.schemas.profile import CandidateProfileOut
from app.services import application_service

router = APIRouter(prefix="/candidates", tags=["candidates"])


async def _get_profile(user_id: PydanticObjectId) -> CandidateProfile:
    profile = await CandidateProfile.find_one(CandidateProfile.user_id == user_id)
    if profile is None:
        raise NotFoundError("Candidate profile not found")
    return profile


@router.get("/me/profile", response_model=CandidateProfileOut)
async def get_my_profile(candidate: CurrentCandidate) -> CandidateProfileOut:
    profile = await _get_profile(candidate.id)
    return CandidateProfileOut.build(
        profile,
        full_name=candidate.full_name,
        email=candidate.email,
        avatar_url=candidate.avatar_url,
    )


# NOTE: there is deliberately no PUT here.
#
# The resume builder is the single editing surface for a profile — it writes via
# `resume_service.apply_draft_to_profile` when a resume is generated. A second
# write endpoint would reintroduce exactly the two-sources-of-truth problem this
# design removes, and would let a client set fields the builder cannot show.


@router.post("/me/saved-jobs/{job_id}", response_model=MessageOut)
async def toggle_saved_job(job_id: PydanticObjectId, candidate: CurrentCandidate) -> MessageOut:
    profile = await _get_profile(candidate.id)
    if job_id in profile.saved_job_ids:
        profile.saved_job_ids.remove(job_id)
        detail = "Job removed from saved"
    else:
        profile.saved_job_ids.append(job_id)
        detail = "Job saved"
    await profile.save()
    return MessageOut(detail=detail)


@router.get("/{candidate_id}/profile", response_model=CandidateProfileOut)
async def get_candidate_profile(
    candidate_id: PydanticObjectId, _: CurrentManager
) -> CandidateProfileOut:
    """A manager reaches a profile only through an application.

    There is deliberately no endpoint that lists or searches candidates — that
    would turn the platform into a candidate directory, which it is not.
    """
    await application_service.assert_manager_may_view_candidate(candidate_id)

    user = await User.get(candidate_id)
    if user is None:
        raise NotFoundError("Candidate not found")

    profile = await _get_profile(candidate_id)
    return CandidateProfileOut.build(
        profile, full_name=user.full_name, email=user.email, avatar_url=user.avatar_url
    )
