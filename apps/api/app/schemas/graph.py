"""The candidate export the AI team ingests into Neo4j.

Shaped to their proposed contract, with four deliberate additions — each one
exists because the original shape would have caused a concrete problem in a
graph. They are called out in `docs/graph-export.md`; the short version:

* `skills[].id`   — a stable slug to MERGE on. Keying nodes on the display name
                    turns "Python"/"python" into two nodes.
* `skills[].last_used_year` — recency is as strong a signal as duration.
* `work_history[].company` — without it there is no (:Company) node, so the
                    most useful traversal in the whole graph is impossible.
* `work_history[].start/end` — `duration_months` alone hides overlap and order,
                    and makes the durations fail to add up to the total.
"""

from datetime import datetime

from pydantic import BaseModel, Field

#: Bump when a field changes meaning or disappears, so the AI side can branch.
SCHEMA_VERSION = "1.0"


class GraphEducation(BaseModel):
    degree_level: str | None = None
    field_of_study: str | None = None
    institution: str | None = None
    graduation_year: int | None = None


class GraphSkill(BaseModel):
    #: Stable lowercase slug. Use this as the MERGE key.
    id: str
    #: Display form, e.g. "Python", "SQL". Never key on this.
    name: str
    #: Summed across every role listing the skill, with overlaps merged.
    years_experience: float
    #: Year the skill was last used. `null` only when a role has no end date.
    last_used_year: int | None = None


class GraphWorkHistory(BaseModel):
    role: str
    company: str | None = None
    company_industry: str | None = None
    #: "YYYY-MM". Present so the graph can order roles and see overlaps.
    start: str | None = None
    end: str | None = None
    is_current: bool = False
    #: Derived from start/end. Note these will NOT sum to
    #: `total_years_experience` when roles overlap — that is intended.
    duration_months: int | None = None
    skills: list[str] = Field(default_factory=list)


class GraphCertification(BaseModel):
    name: str
    issuer: str | None = None
    issued_year: int | None = None
    credential_id: str | None = None


class GraphAchievements(BaseModel):
    career_highlights: list[str] = Field(default_factory=list)
    academic_distinctions: list[str] = Field(default_factory=list)
    awards_and_competitions: list[str] = Field(default_factory=list)
    projects_and_open_source: list[str] = Field(default_factory=list)


class GraphLanguage(BaseModel):
    language: str
    proficiency: str


class GraphLocation(BaseModel):
    city: str | None = None
    country: str | None = None


class GraphCandidate(BaseModel):
    schema_version: str = SCHEMA_VERSION
    candidate_id: str
    profile_updated_at: datetime | None = None

    #: Overlapping roles are merged, so this is time actually worked — not the
    #: sum of `work_history[].duration_months`.
    total_years_experience: float | None = None

    # Matching attributes the platform already holds. Cheap to send, and they
    # save the AI side from re-deriving them from prose.
    headline: str | None = None
    seniority: str | None = None
    job_category: str | None = None
    location: GraphLocation = Field(default_factory=GraphLocation)
    open_to_relocate: bool = False
    work_modes: list[str] = Field(default_factory=list)

    education: list[GraphEducation] = Field(default_factory=list)
    skills: list[GraphSkill] = Field(default_factory=list)
    work_history: list[GraphWorkHistory] = Field(default_factory=list)
    certifications: list[GraphCertification] = Field(default_factory=list)
    achievements: GraphAchievements = Field(default_factory=GraphAchievements)
    languages: list[GraphLanguage] = Field(default_factory=list)


# ── jobs ─────────────────────────────────────────────────────────────────────


class GraphRequiredSkill(BaseModel):
    #: Same slug space as `GraphSkill.id` — this is what makes the two sides of
    #: the graph join. MERGE on it.
    id: str
    name: str
    #: Compare against the candidate's `skills[].years_experience`.
    min_years: float | None = None


class GraphWeightedSkill(BaseModel):
    id: str
    name: str
    #: 0–1. Raises a score; never gates.
    weight: float


class GraphRequiredEducation(BaseModel):
    #: Ordered: a Master satisfies a Bachelor requirement.
    degree_level: str | None = None
    field_of_study: str | None = None


class GraphRequiredLanguage(BaseModel):
    language: str
    #: CEFR is ordered: A1 < A2 < B1 < B2 < C1 < C2 < Native.
    min_proficiency: str


class GraphMandatory(BaseModel):
    min_years_total_experience: float | None = None
    max_years_total_experience: float | None = None
    education: list[GraphRequiredEducation] = Field(default_factory=list)
    skills: list[GraphRequiredSkill] = Field(default_factory=list)
    languages: list[GraphRequiredLanguage] = Field(default_factory=list)


class GraphNiceToHave(BaseModel):
    skills: list[GraphWeightedSkill] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    preferred_industries: list[str] = Field(default_factory=list)


class GraphJob(BaseModel):
    schema_version: str = SCHEMA_VERSION
    job_id: str
    #: Constant — this deployment serves one hiring company. Present so the
    #: contract does not have to change if that ever stops being true.
    company_id: str = "org"
    #: Only `published` jobs are exported by default. Without this the graph
    #: would happily recommend candidates for drafts and closed roles.
    status: str
    updated_at: datetime | None = None

    title: str
    #: Lowercase, same vocabulary as the candidate export's `seniority`.
    seniority_level: str
    job_category: str | None = None
    employment_type: str
    work_mode: str
    location: GraphLocation = Field(default_factory=GraphLocation)
    is_remote: bool = False
    openings: int = 1

    mandatory_requirements: GraphMandatory = Field(default_factory=GraphMandatory)
    nice_to_have: GraphNiceToHave = Field(default_factory=GraphNiceToHave)


class GraphJobPage(BaseModel):
    items: list[GraphJob]
    total: int
    page: int
    page_size: int
    pages: int
    schema_version: str = SCHEMA_VERSION


class GraphCandidatePage(BaseModel):
    items: list[GraphCandidate]
    total: int
    page: int
    page_size: int
    pages: int
    schema_version: str = SCHEMA_VERSION


class GraphApplication(BaseModel):
    """The (:Candidate)-[:APPLIED_TO]->(:Job) edge.

    Deliberately just the three ids plus timing and match status — no candidate
    or job detail. Those are nodes, fetched from the by-id endpoints; embedding
    them here would duplicate data that can drift. Filter `match_status=pending`
    and this doubles as the AI team's scoring queue.
    """

    application_id: str
    candidate_id: str
    job_id: str
    applied_at: datetime
    updated_at: datetime
    match_status: str  # pending | scored | failed


class GraphApplicationPage(BaseModel):
    items: list[GraphApplication]
    total: int
    page: int
    page_size: int
    pages: int
    schema_version: str = SCHEMA_VERSION
