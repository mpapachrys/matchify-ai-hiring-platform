"""Two output shapes over one document.

`ApplicationCandidateOut` and `ApplicationManagerOut` are the reason services
never return raw Beanie documents: internal notes, ratings, and AI scores must
be structurally impossible to leak into a candidate response.
"""

from datetime import UTC, datetime

from beanie import PydanticObjectId
from pydantic import BaseModel, Field

from app.models.application import (
    Application,
    CandidateSnapshot,
    InternalNote,
    Interview,
    JobSnapshot,
    MatchResult,
    ScreeningAnswer,
    StageChange,
)
from app.models.enums import InterviewStatus, MatchStatus, PipelineStage


class MatchIn(BaseModel):
    """The AI team's write-back. Confidence is required; a call means a score."""

    confidence: float = Field(ge=0.0, le=1.0)
    factors: dict = Field(default_factory=dict)
    graph_version: str | None = None


class MatchOut(BaseModel):
    """What a manager sees — the precise number and its reasoning."""

    status: MatchStatus
    confidence: float | None
    factors: dict
    graph_version: str | None
    scored_at: datetime | None

    @classmethod
    def build(cls, match: MatchResult) -> "MatchOut":
        return cls(
            status=match.status,
            confidence=match.confidence,
            factors=match.factors,
            graph_version=match.graph_version,
            scored_at=match.scored_at,
        )




class InterviewOut(BaseModel):
    """What both a manager and the candidate themselves see — no field here
    is manager-only, unlike ApplicationManagerOut's notes/rating."""

    status: InterviewStatus
    event_id: str | None
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    html_link: str | None

    @classmethod
    def build(cls, interview: Interview) -> "InterviewOut":
        return cls(
            status=interview.status,
            event_id=interview.event_id,
            # Mongo round-trips datetimes as naive UTC. Left naive here, a
            # browser's `new Date(...)` parses the string as *local* time
            # instead — silently shifting the one field where being off by a
            # few hours is not a cosmetic bug. Stamp the offset explicitly.
            scheduled_start=_as_utc(interview.scheduled_start),
            scheduled_end=_as_utc(interview.scheduled_end),
            html_link=interview.html_link,
        )


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class ApplicationCreateIn(BaseModel):
    job_id: PydanticObjectId
    cover_letter: str | None = Field(default=None, max_length=8000)
    resume_id: PydanticObjectId | None = None
    answers: list[ScreeningAnswer] = Field(default_factory=list)


class StageChangeIn(BaseModel):
    stage: PipelineStage
    note: str | None = Field(default=None, max_length=2000)


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class RatingIn(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)


class ShortlistIn(BaseModel):
    is_shortlisted: bool


class ApplicationCandidateOut(BaseModel):
    id: PydanticObjectId
    job_id: PydanticObjectId
    job_snapshot: JobSnapshot
    stage: PipelineStage
    is_shortlisted: bool
    cover_letter: str | None
    resume_id: PydanticObjectId | None
    applied_at: datetime
    updated_at: datetime
    withdrawn_at: datetime | None
    # Only the transitions themselves — never the manager's private note.
    timeline: list[dict] = Field(default_factory=list)
    # The candidate sees the same confidence percentage the manager does — just
    # without the factors breakdown. `match_confidence` is None until scored.
    match_status: MatchStatus
    match_confidence: float | None
    interview: InterviewOut

    @classmethod
    def build(cls, app: Application) -> "ApplicationCandidateOut":
        return cls(
            id=app.id,
            job_id=app.job_id,
            job_snapshot=app.job_snapshot,
            stage=app.stage,
            is_shortlisted=app.is_shortlisted,
            cover_letter=app.cover_letter,
            resume_id=app.resume_id,
            applied_at=app.applied_at,
            updated_at=app.updated_at,
            withdrawn_at=app.withdrawn_at,
            timeline=[
                {"to_stage": c.to_stage, "changed_at": c.changed_at}
                for c in app.stage_history
            ],
            match_status=app.match.status,
            match_confidence=app.match.confidence,
            interview=InterviewOut.build(app.interview),
        )


class ApplicationManagerOut(BaseModel):
    id: PydanticObjectId
    job_id: PydanticObjectId
    candidate_id: PydanticObjectId
    job_snapshot: JobSnapshot
    candidate_snapshot: CandidateSnapshot
    stage: PipelineStage
    stage_history: list[StageChange]
    is_shortlisted: bool
    cover_letter: str | None
    resume_id: PydanticObjectId | None
    answers: list[ScreeningAnswer]
    rating: int | None
    notes: list[InternalNote]
    match: MatchOut
    interview: InterviewOut
    applied_at: datetime
    updated_at: datetime
    withdrawn_at: datetime | None

    @classmethod
    def build(cls, app: Application) -> "ApplicationManagerOut":
        return cls(
            id=app.id,
            job_id=app.job_id,
            candidate_id=app.candidate_id,
            job_snapshot=app.job_snapshot,
            candidate_snapshot=app.candidate_snapshot,
            stage=app.stage,
            stage_history=app.stage_history,
            is_shortlisted=app.is_shortlisted,
            cover_letter=app.cover_letter,
            resume_id=app.resume_id,
            answers=app.answers,
            rating=app.rating,
            notes=app.notes,
            match=MatchOut.build(app.match),
            interview=InterviewOut.build(app.interview),
            applied_at=app.applied_at,
            updated_at=app.updated_at,
            withdrawn_at=app.withdrawn_at,
        )
