"""Build the Neo4j-ready candidate export.

Everything here is derived from what the resume builder already stores — there
is no second place to maintain. The two non-obvious computations:

* **Per-skill years.** For each skill, take the date spans of every role that
  lists it, merge overlapping spans, and sum. A skill used at two concurrent
  jobs for a year counts once.
* **Canonical skill names.** Storage is lowercase so matching never depends on
  casing, but a graph wants "Python" on the node and a stable key to MERGE on.
  Both are sent: `id` (the slug) and `name` (display).
"""

from datetime import UTC, date, datetime

from beanie import PydanticObjectId

from app.models.application import Application
from app.models.candidate_profile import CandidateProfile, Experience
from app.models.enums import JobStatus
from app.models.job import Job
from app.models.user import User
from app.schemas.graph import (
    GraphAchievements,
    GraphApplication,
    GraphCandidate,
    GraphCertification,
    GraphEducation,
    GraphJob,
    GraphLanguage,
    GraphLocation,
    GraphMandatory,
    GraphNiceToHave,
    GraphRequiredEducation,
    GraphRequiredLanguage,
    GraphRequiredSkill,
    GraphSkill,
    GraphWeightedSkill,
    GraphWorkHistory,
)

#: Acronyms and product names whose display form is not just a capitalised word.
#: Anything absent falls through to title case, which is right far more often
#: than it is wrong ("kubernetes" → "Kubernetes").
CANONICAL_SKILL_NAMES: dict[str, str] = {
    ".net": ".NET",
    "ai": "AI",
    "angularjs": "AngularJS",
    "api": "API",
    "aws": "AWS",
    "ci/cd": "CI/CD",
    "css": "CSS",
    "dbt": "dbt",
    "etl": "ETL",
    "fastapi": "FastAPI",
    "expressjs": "Express.js",
    "gcp": "GCP",
    "github actions": "GitHub Actions",
    "github copilot": "GitHub Copilot",
    "graphql": "GraphQL",
    "grpc": "gRPC",
    "html": "HTML",
    "ios": "iOS",
    "javascript": "JavaScript",
    "jwt": "JWT",
    "ml": "ML",
    "mongodb": "MongoDB",
    "mysql": "MySQL",
    "neo4j": "Neo4j",
    "nlp": "NLP",
    "nestjs": "NestJS",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "nosql": "NoSQL",
    "php": "PHP",
    "postgresql": "PostgreSQL",
    "rest": "REST",
    "sql": "SQL",
    "typescript": "TypeScript",
    "ui/ux": "UI/UX",
    "ux": "UX",
    "vue.js": "Vue.js",
    "vuejs": "Vue.js",
    "web2py": "web2py",
}


def canonical_skill_name(slug: str) -> str:
    """Display form for a stored (lowercase) skill slug."""
    if slug in CANONICAL_SKILL_NAMES:
        return CANONICAL_SKILL_NAMES[slug]
    # Title-case each word but leave internal punctuation alone:
    # "node.js" → "Node.js", "machine learning" → "Machine Learning".
    return " ".join(word[:1].upper() + word[1:] for word in slug.split(" "))


def _merge_spans(spans: list[tuple[date, date]]) -> list[tuple[date, date]]:
    if not spans:
        return []
    spans = sorted(spans)
    merged: list[list[date]] = [list(spans[0])]
    for start, end in spans[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _years(spans: list[tuple[date, date]]) -> float:
    days = sum((end - start).days for start, end in _merge_spans(spans))
    return round(days / 365.25, 1)


def _role_span(role: Experience, today: date) -> tuple[date, date] | None:
    start = role.start_date
    if start is None:
        return None
    end = today if role.is_current else role.end_date
    if end is None or end < start:
        return None
    return start, min(end, today)


def _months(start: date, end: date) -> int:
    return max(0, round((end - start).days / 30.44))


def build_skills(experience: list[Experience], today: date) -> list[GraphSkill]:
    """Per-skill totals, computed from the roles that used each skill."""
    spans: dict[str, list[tuple[date, date]]] = {}
    last_used: dict[str, int | None] = {}

    for role in experience:
        span = _role_span(role, today)
        for slug in role.skills:
            slug = slug.strip().lower()
            if not slug:
                continue
            spans.setdefault(slug, [])
            last_used.setdefault(slug, None)
            if span is None:
                continue
            spans[slug].append(span)
            year = today.year if role.is_current else span[1].year
            previous = last_used[slug]
            last_used[slug] = year if previous is None else max(previous, year)

    skills = [
        GraphSkill(
            id=slug,
            name=canonical_skill_name(slug),
            years_experience=_years(slug_spans),
            last_used_year=last_used[slug],
        )
        for slug, slug_spans in spans.items()
    ]
    # Strongest first: most experience, then most recent.
    skills.sort(key=lambda s: (-s.years_experience, -(s.last_used_year or 0), s.id))
    return skills


def build_work_history(experience: list[Experience], today: date) -> list[GraphWorkHistory]:
    history: list[GraphWorkHistory] = []
    for role in experience:
        span = _role_span(role, today)
        history.append(
            GraphWorkHistory(
                role=role.title,
                company=role.company,
                company_industry=role.company_industry,
                start=role.start_date.strftime("%Y-%m") if role.start_date else None,
                end=None if role.is_current else (
                    role.end_date.strftime("%Y-%m") if role.end_date else None
                ),
                is_current=role.is_current,
                duration_months=_months(*span) if span else None,
                skills=[canonical_skill_name(s) for s in role.skills],
            )
        )
    # Newest first, undated last.
    history.sort(key=lambda r: r.start or "", reverse=True)
    return history


def build_candidate(user: User, profile: CandidateProfile) -> GraphCandidate:
    today = datetime.now(UTC).date()

    return GraphCandidate(
        candidate_id=str(user.id),
        profile_updated_at=profile.updated_at,
        total_years_experience=profile.years_experience,
        headline=profile.headline,
        seniority=profile.seniority.value if profile.seniority else None,
        job_category=profile.job_category,
        location=GraphLocation(city=profile.location.city, country=profile.location.country),
        open_to_relocate=profile.open_to_relocate,
        work_modes=[mode.value for mode in profile.work_modes],
        education=[
            GraphEducation(
                degree_level=entry.degree_level.value if entry.degree_level else None,
                field_of_study=entry.field,
                institution=entry.institution,
                graduation_year=entry.end_date.year if entry.end_date else None,
            )
            for entry in profile.education
        ],
        skills=build_skills(profile.experience, today),
        work_history=build_work_history(profile.experience, today),
        certifications=[
            GraphCertification(
                name=cert.name,
                issuer=cert.issuer,
                issued_year=cert.issued_year,
                credential_id=cert.credential_id,
            )
            for cert in profile.certifications
        ],
        achievements=GraphAchievements(
            career_highlights=profile.achievements.career_highlights,
            academic_distinctions=profile.achievements.academic_distinctions,
            awards_and_competitions=profile.achievements.awards_and_competitions,
            projects_and_open_source=profile.achievements.projects_and_open_source,
        ),
        languages=[
            GraphLanguage(language=lang.name, proficiency=lang.level.value)
            for lang in profile.languages
        ],
    )


async def get_candidate(candidate_id: PydanticObjectId) -> GraphCandidate | None:
    profile = await CandidateProfile.find_one(CandidateProfile.user_id == candidate_id)
    if profile is None:
        return None
    user = await User.get(candidate_id)
    if user is None:
        return None
    return build_candidate(user, profile)


async def list_candidates(
    *, skip: int, limit: int, updated_since: datetime | None = None
) -> tuple[list[GraphCandidate], int]:
    """Paginated export, optionally only what changed.

    `updated_since` is what makes incremental graph syncs possible — without it
    the AI side has to re-ingest every candidate on every run.
    """
    query: dict = {}
    if updated_since is not None:
        query["updated_at"] = {"$gt": updated_since}

    cursor = CandidateProfile.find(query)
    total = await cursor.count()
    profiles = await cursor.sort("updated_at").skip(skip).limit(limit).to_list()

    if not profiles:
        return [], total

    users = await User.find({"_id": {"$in": [p.user_id for p in profiles]}}).to_list()
    by_id = {user.id: user for user in users}

    return [
        build_candidate(by_id[p.user_id], p) for p in profiles if p.user_id in by_id
    ], total


# ── jobs ─────────────────────────────────────────────────────────────────────


def build_job(job: Job) -> GraphJob:
    return GraphJob(
        job_id=str(job.id),
        status=job.status.value,
        updated_at=job.updated_at,
        title=job.title,
        # Lowercase, matching the candidate export. Two spellings of the same
        # concept would mean the two sides never compare.
        seniority_level=job.seniority.value,
        job_category=job.job_category,
        employment_type=job.employment_type.value,
        work_mode=job.work_mode.value,
        location=GraphLocation(city=job.location.city, country=job.location.country),
        is_remote=job.location.is_remote,
        openings=job.openings,
        mandatory_requirements=GraphMandatory(
            min_years_total_experience=job.mandatory.min_years_total_experience,
            max_years_total_experience=job.mandatory.max_years_total_experience,
            education=[
                GraphRequiredEducation(
                    degree_level=e.degree_level.value if e.degree_level else None,
                    field_of_study=e.field_of_study,
                )
                for e in job.mandatory.education
            ],
            skills=[
                GraphRequiredSkill(
                    id=s.slug,
                    name=canonical_skill_name(s.slug),
                    min_years=s.min_years,
                )
                for s in job.mandatory.skills
            ],
            languages=[
                GraphRequiredLanguage(
                    language=lang.language, min_proficiency=lang.min_proficiency.value
                )
                for lang in job.mandatory.languages
            ],
        ),
        nice_to_have=GraphNiceToHave(
            skills=[
                GraphWeightedSkill(
                    id=s.slug, name=canonical_skill_name(s.slug), weight=s.weight
                )
                for s in sorted(job.nice_to_have.skills, key=lambda s: -s.weight)
            ],
            certifications=list(job.nice_to_have.certifications),
            preferred_industries=list(job.nice_to_have.preferred_industries),
        ),
    )


async def get_job(job_id: PydanticObjectId) -> GraphJob | None:
    job = await Job.get(job_id)
    return build_job(job) if job else None


async def list_jobs(
    *,
    skip: int,
    limit: int,
    updated_since: datetime | None = None,
    include_unpublished: bool = False,
) -> tuple[list[GraphJob], int]:
    """Published jobs only, unless explicitly asked otherwise.

    A graph that ingests drafts and closed roles will recommend candidates for
    positions that do not exist, so the safe set is the default.
    """
    query: dict = {}
    if not include_unpublished:
        query["status"] = JobStatus.PUBLISHED.value
    if updated_since is not None:
        query["updated_at"] = {"$gt": updated_since}

    cursor = Job.find(query)
    total = await cursor.count()
    jobs = await cursor.sort("updated_at").skip(skip).limit(limit).to_list()
    return [build_job(job) for job in jobs], total


# ── applications (the edges) ─────────────────────────────────────────────────


def build_application(app: Application) -> GraphApplication:
    return GraphApplication(
        application_id=str(app.id),
        candidate_id=str(app.candidate_id),
        job_id=str(app.job_id),
        applied_at=app.applied_at,
        updated_at=app.updated_at,
        match_status=app.match.status.value,
    )


async def list_applications(
    *,
    skip: int,
    limit: int,
    updated_since: datetime | None = None,
    match_status: str | None = None,
) -> tuple[list[GraphApplication], int]:
    """The APPLIED_TO edges, newest-changed last for incremental sync.

    `match_status="pending"` turns this into the AI team's scoring queue: the
    applications that have not been scored yet. Ordered by `updated_at` ascending
    so a caller can page through with `updated_since` and miss nothing.
    """
    query: dict = {}
    if updated_since is not None:
        query["updated_at"] = {"$gt": updated_since}
    if match_status is not None:
        query["match.status"] = match_status

    cursor = Application.find(query)
    total = await cursor.count()
    apps = await cursor.sort("updated_at").skip(skip).limit(limit).to_list()
    return [build_application(app) for app in apps], total
