from pydantic import BaseModel, Field


class TimePoint(BaseModel):
    date: str  # YYYY-MM-DD
    value: int


class RatePoint(BaseModel):
    date: str
    value: float


class StageCount(BaseModel):
    stage: str
    count: int


class CandidateAnalyticsOut(BaseModel):
    jobs_applied: int = 0
    shortlisted: int = 0
    in_interview: int = 0
    offers: int = 0
    success_rate: float = 0.0
    profile_completion: int = 0
    applications_over_time: list[TimePoint] = Field(default_factory=list)
    success_rate_trend: list[RatePoint] = Field(default_factory=list)
    stage_breakdown: list[StageCount] = Field(default_factory=list)


class ManagerAnalyticsOut(BaseModel):
    open_jobs: int = 0
    total_applications: int = 0
    shortlisted: int = 0
    hired: int = 0
    conversion_rate: float = 0.0
    applications_over_time: list[TimePoint] = Field(default_factory=list)
    funnel: list[StageCount] = Field(default_factory=list)
    top_jobs: list[dict] = Field(default_factory=list)
