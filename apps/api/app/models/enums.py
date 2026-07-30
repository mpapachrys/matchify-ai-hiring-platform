from enum import StrEnum


class Role(StrEnum):
    CANDIDATE = "candidate"
    HIRING_MANAGER = "hiring_manager"


class JobStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    PAUSED = "paused"
    CLOSED = "closed"
    ARCHIVED = "archived"


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"


class WorkMode(StrEnum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"


class SeniorityLevel(StrEnum):
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    PRINCIPAL = "principal"


class PipelineStage(StrEnum):
    APPLIED = "applied"
    SCREENING = "screening"
    INTERVIEW = "interview"
    OFFER = "offer"
    HIRED = "hired"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


#: Stages a candidate progresses *through*. Everything else is terminal.
ACTIVE_STAGES: tuple[PipelineStage, ...] = (
    PipelineStage.APPLIED,
    PipelineStage.SCREENING,
    PipelineStage.INTERVIEW,
    PipelineStage.OFFER,
)


class InterviewStatus(StrEnum):
    NONE = "none"
    #: Manager approved the candidate for an interview; the candidate picks
    #: the actual slot, not the manager.
    AWAITING_CANDIDATE = "awaiting_candidate"
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"


class MatchStatus(StrEnum):
    """Lifecycle of an application's AI-computed match confidence.

    PENDING the moment the candidate applies; the AI team scores it and writes
    SCORED back. FAILED only if they explicitly report they could not. There is
    no re-scoring: the value is frozen at apply time, like the resume snapshot.
    """

    PENDING = "pending"
    SCORED = "scored"
    FAILED = "failed"

TERMINAL_STAGES: tuple[PipelineStage, ...] = (
    PipelineStage.HIRED,
    PipelineStage.REJECTED,
    PipelineStage.WITHDRAWN,
)

#: Reaching any of these means the candidate cleared the first screen.
SHORTLISTED_FROM: tuple[PipelineStage, ...] = (
    PipelineStage.SCREENING,
    PipelineStage.INTERVIEW,
    PipelineStage.OFFER,
    PipelineStage.HIRED,
)


class DocumentType(StrEnum):
    RESUME = "resume"
    PASSPORT = "passport"
    DEGREE = "degree"
    MARK_SHEET = "mark_sheet"
    CERTIFICATE = "certificate"
    REFERENCE_LETTER = "reference_letter"
    OTHER = "other"


class DocumentStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class DegreeLevel(StrEnum):
    """Closed vocabulary so the graph gets one node per level.

    Free text produces "BSc", "B.Sc." and "Bachelor's" as three distinct nodes.
    """

    HIGH_SCHOOL = "High School"
    CERTIFICATE = "Certificate"
    DIPLOMA = "Diploma"
    BACHELOR = "Bachelor"
    MASTER = "Master"
    PHD = "PhD"


class LanguageProficiency(StrEnum):
    """CEFR plus Native — the vocabulary the AI team asked for."""

    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"
    NATIVE = "Native"


#: Industry of the employer, not of the candidate. Kept as a fixed list for the
#: same reason as the enums above — one graph node per industry, not one per
#: spelling. A free-text "other" is deliberately absent; add to the list instead.
INDUSTRIES: tuple[str, ...] = (
    "Fintech",
    "Banking",
    "Insurance",
    "E-commerce",
    "Retail",
    "Logistics",
    "Healthcare",
    "Biotech",
    "Education",
    "Gaming",
    "Media",
    "Telecommunications",
    "Energy",
    "Manufacturing",
    "Automotive",
    "Travel",
    "Real Estate",
    "Consulting",
    "Public Sector",
    "Non-profit",
    "Agency",
    "SaaS",
    "Tech",
)
