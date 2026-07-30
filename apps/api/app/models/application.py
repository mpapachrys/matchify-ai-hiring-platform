from datetime import UTC, datetime

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.models.enums import (
    EmploymentType,
    InterviewStatus,
    MatchStatus,
    PipelineStage,
    SeniorityLevel,
)


class JobSnapshot(BaseModel):
    """Frozen at apply time.

    When a manager renames or re-scopes a job, a candidate's application
    history must not silently rewrite itself. Company name/logo are absent
    because this deployment has exactly one company.
    """

    title: str
    location: str | None = None
    employment_type: EmploymentType | None = None
    seniority: SeniorityLevel | None = None


class CandidateSnapshot(BaseModel):
    full_name: str
    email: str
    headline: str | None = None
    avatar_url: str | None = None


class StageChange(BaseModel):
    from_stage: PipelineStage | None = None
    to_stage: PipelineStage
    changed_by: PydanticObjectId | None = None
    changed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    note: str | None = None


class ScreeningAnswer(BaseModel):
    question: str
    answer: str


class InternalNote(BaseModel):
    """Manager-only. Never serialized into a candidate-facing response."""

    author_id: PydanticObjectId
    author_name: str
    body: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MatchResult(BaseModel):
    """The AI team's confidence that this candidate fits this job.

    Computed off the platform, from the graph export, and written back through
    `POST /applications/{id}/match` with the service token — never by a user.
    It lives on the *application*, not the candidate, because the same person
    scores differently against different jobs.

    Frozen at scoring time, like `resume_id` and `job_snapshot`: a later profile
    edit does not rewrite the score of an application already submitted. `status`
    starts PENDING at apply and the write-back moves it to SCORED.
    """

    status: MatchStatus = MatchStatus.PENDING
    #: 0.0–1.0. None until scored. The UI renders it as a percentage.
    confidence: float | None = None
    #: Free-form breakdown from the AI team (skills matched, years, …). Shown to
    #: managers as the reasoning behind the number; empty until they send it.
    factors: dict = Field(default_factory=dict)
    #: Which version of their scoring produced this, so a number is traceable.
    graph_version: str | None = None
    scored_at: datetime | None = None


class Interview(BaseModel):
    """A two-step booking on the shared company Google Calendar, mirrored
    here so the pipeline UI never has to make a live calendar call to render.

    A manager approves (status -> AWAITING_CANDIDATE, no calendar call yet);
    the candidate then picks the actual slot (status -> SCHEDULED, this is
    when the real Google Calendar event is created). `status` tracks
    Matchify's own view independent of `Application.stage` — cancelling a
    booking does not move the stage back on its own.
    """

    status: InterviewStatus = InterviewStatus.NONE
    event_id: str | None = None
    calendar_id: str = "primary"
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    html_link: str | None = None
    approved_by: PydanticObjectId | None = None
    approved_at: datetime | None = None
    scheduled_by: PydanticObjectId | None = None
    scheduled_at: datetime | None = None
    cancelled_at: datetime | None = None


class Application(Document):
    """The hot collection — nearly every product action reads or writes here.

    Its own collection rather than an array on Job: a popular posting would
    otherwise approach the 16 MB document ceiling, and cross-job pipeline
    queries are impossible from nested arrays.
    """

    job_id: PydanticObjectId
    candidate_id: PydanticObjectId

    job_snapshot: JobSnapshot
    candidate_snapshot: CandidateSnapshot

    # Pins the exact resume version submitted. Re-uploading a resume later
    # never retroactively alters a past application.
    resume_id: PydanticObjectId | None = None
    cover_letter: str | None = None
    answers: list[ScreeningAnswer] = Field(default_factory=list)

    stage: PipelineStage = PipelineStage.APPLIED
    stage_history: list[StageChange] = Field(default_factory=list)
    is_shortlisted: bool = False

    # ── manager-only fields ──
    rating: int | None = None  # 1..5
    notes: list[InternalNote] = Field(default_factory=list)

    # The AI team's match confidence for this (candidate, job) pair. Starts
    # PENDING at apply; they score it from the graph export and write it back.
    # See docs/graph-export.md.
    match: MatchResult = Field(default_factory=MatchResult)

    # Booked via the calendar-mcp assistant. See Interview's docstring for why
    # this tracks separately from `stage`.
    interview: Interview = Field(default_factory=Interview)

    applied_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    withdrawn_at: datetime | None = None

    class Settings:
        name = "applications"
        indexes = [
            # The most important index in the system: one application per job
            # per candidate, enforced by the database rather than by an
            # app-layer check that races under concurrent submits.
            IndexModel(
                [("job_id", ASCENDING), ("candidate_id", ASCENDING)],
                unique=True,
                name="uniq_job_candidate",
            ),
            IndexModel(
                [("candidate_id", ASCENDING), ("applied_at", DESCENDING)],
                name="candidate_recent",
            ),
            IndexModel([("job_id", ASCENDING), ("stage", ASCENDING)], name="job_stage"),
            # Org-wide "everyone at Interview" — no company filter needed
            # because the deployment is single-tenant.
            IndexModel(
                [("stage", ASCENDING), ("applied_at", DESCENDING)],
                name="stage_recent",
            ),
            IndexModel(
                [("job_id", ASCENDING), ("is_shortlisted", ASCENDING)],
                name="job_shortlisted",
            ),
            # The AI team's pending-scoring feed and the graph applications
            # export both read by match status ordered by change time.
            IndexModel(
                [("match.status", ASCENDING), ("updated_at", ASCENDING)],
                name="match_status_recent",
            ),
            # The manager-facing "upcoming interviews" list, sorted by when
            # they actually happen rather than when they were booked.
            IndexModel(
                [("interview.status", ASCENDING), ("interview.scheduled_start", ASCENDING)],
                name="interview_upcoming",
            ),
        ]
