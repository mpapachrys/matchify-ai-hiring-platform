"""The contract for turning resume text into structured fields.

This was originally the only place the platform used an LLM; as of the
interview-booking chat widget it's one of two — see
app/integrations/booking_agent for the other. Candidate/job matching and
scoring remain the AI team's responsibility and happen outside this codebase,
from the data exposed by `/api/v1/graph` — see docs/graph-export.md.

Two implementations, chosen by the RESUME_PARSER env var:

    stub       → regex only. No API key, no invented values.
    openrouter → an LLM via OpenRouter.

Nothing else imports an implementation directly; everything goes through
`get_parser()`, so swapping one for the other is a config change.
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ParsedExperience(BaseModel):
    company: str | None = None
    title: str | None = None
    # Dates arrive as free text from the model ("2019-03", "March 2019",
    # "Present"). Normalization to real dates happens on the platform side, so a
    # sloppy date never fails the whole parse.
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    location: str | None = None
    description: str | None = None
    #: Technologies and competencies used in *this* role. The platform requires
    #: at least one per role before a resume can be generated.
    skills: list[str] = Field(default_factory=list)
    #: Employer's industry. Free text from the model; the platform maps it onto
    #: its fixed INDUSTRIES list and drops anything it cannot place.
    company_industry: str | None = None


class ParsedEducation(BaseModel):
    institution: str | None = None
    degree: str | None = None
    #: One of: High School, Certificate, Diploma, Bachelor, Master, PhD.
    degree_level: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    grade: str | None = None


class ParsedLanguage(BaseModel):
    name: str
    #: CEFR (A1–C2) or "Native".
    level: str | None = None


class ParsedCertification(BaseModel):
    name: str
    issuer: str | None = None
    issued_year: int | None = None
    credential_id: str | None = None


class ParsedAchievements(BaseModel):
    career_highlights: list[str] = Field(default_factory=list)
    academic_distinctions: list[str] = Field(default_factory=list)
    awards_and_competitions: list[str] = Field(default_factory=list)
    projects_and_open_source: list[str] = Field(default_factory=list)


class ParsedLinks(BaseModel):
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None


class ParsedLocation(BaseModel):
    country: str | None = None
    city: str | None = None


class ParsedResume(BaseModel):
    """Everything the resume builder can pre-fill.

    Every field is optional: a CV that omits a section, or a model that can't
    find it, must degrade to a blank field rather than a failed parse.
    """

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    headline: str | None = None
    summary: str | None = None
    job_category: str | None = None
    seniority: str | None = None
    location: ParsedLocation = Field(default_factory=ParsedLocation)
    #: Skills mentioned in the CV that could not be tied to a specific role.
    #: Shown to the candidate as a hint; never auto-assigned to a role.
    skills: list[str] = Field(default_factory=list)
    years_experience: float | None = None
    experience: list[ParsedExperience] = Field(default_factory=list)
    education: list[ParsedEducation] = Field(default_factory=list)
    languages: list[ParsedLanguage] = Field(default_factory=list)
    certifications: list[ParsedCertification] = Field(default_factory=list)
    achievements: ParsedAchievements = Field(default_factory=ParsedAchievements)
    links: ParsedLinks = Field(default_factory=ParsedLinks)
    raw_text: str | None = None
    model_version: str = "unknown"


class ResumeSource(BaseModel):
    """What the parser is handed: the document itself, its text, or both.

    A PDF is passed through as bytes rather than as pre-extracted text. A CV is
    a *designed* document — two columns, a sidebar, visual grouping — and every
    text extractor flattens that into one stream. Measured on a real two-column
    CV, the sidebar's "Frameworks: React, Angular" landed on the same output
    line as the next job's title, which is exactly how a skill gets attributed
    to a role that never used it. A model that sees the page keeps them apart.

    `text` is still carried when it is available: the stub parser has no vision,
    and it is what `raw_text` is populated from. Neither is required — a scanned
    PDF has no text layer at all and now parses anyway, which it never did while
    extraction was the only path in.
    """

    model_config = {"arbitrary_types_allowed": True}

    text: str | None = None
    pdf: bytes | None = None
    filename: str = "resume.pdf"


@runtime_checkable
class ResumeParser(Protocol):
    """A resume in, structured fields out. Deliberately the whole surface.

    The parser is given bytes or text that the platform has already fetched, so
    no implementation needs object-storage credentials.
    """

    async def parse_resume(self, source: ResumeSource) -> ParsedResume: ...
