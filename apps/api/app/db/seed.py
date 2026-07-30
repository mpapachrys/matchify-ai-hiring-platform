"""Demo data so `make up` yields a usable product, not an empty shell.

Deterministic on purpose — no randomness — so screenshots, charts, and tests
are reproducible across runs.

    python -m app.db.seed            # fill only if the database is empty
    python -m app.db.seed --reset    # wipe demo data, then fill   (make seed)
    python -m app.db.seed --clear    # wipe demo data and stop     (make unseed)

Candidate profiles are populated with the full structured shape the graph export
reads — dated per-role skills, employer industries, degree levels, CEFR
languages, certifications and achievements — so a freshly filled database
exercises every field the schema now carries, not just the ones the old flat
seed touched.
"""

import argparse
import asyncio
import logging
import os
from datetime import UTC, date, datetime, timedelta

from app.core.config import settings
from app.core.security import hash_password
from app.models.application import (
    Application,
    CandidateSnapshot,
    InternalNote,
    JobSnapshot,
    StageChange,
)
from app.models.candidate_profile import (
    Achievements,
    CandidateProfile,
    Certification,
    Education,
    Experience,
    Language,
    Links,
    Location,
)
from app.models.document import UserDocument
from app.models.enums import (
    SHORTLISTED_FROM,
    DegreeLevel,
    EmploymentType,
    JobStatus,
    LanguageProficiency,
    PipelineStage,
    Role,
    SeniorityLevel,
    WorkMode,
)
from app.models.job import (
    Job,
    JobLocation,
    MandatoryRequirements,
    NiceToHave,
    NiceToHaveSkill,
    RequiredEducation,
    RequiredLanguage,
    RequiredSkill,
    Salary,
)
from app.models.organization import ORG_SINGLETON_KEY, Organization
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services import organization_service

logger = logging.getLogger(__name__)

#: A sensible floor per level, so seeded jobs have a realistic experience bar.
SENIORITY_MIN_YEARS = {
    SeniorityLevel.INTERN: None,
    SeniorityLevel.JUNIOR: 0.0,
    SeniorityLevel.MID: 2.0,
    SeniorityLevel.SENIOR: 5.0,
    SeniorityLevel.LEAD: 8.0,
    SeniorityLevel.PRINCIPAL: 10.0,
}


#: Every seeded account shares this. The default is fine for a laptop; on a
#: public deployment it would put an *admin* login documented in the README on
#: the open internet, so `seed()` refuses to run in production without it set.
PASSWORD = os.getenv("SEED_PASSWORD", "Passw0rd!")


def _days_ago(n: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=n)


# ── people ───────────────────────────────────────────────────────────────────

MANAGERS = [
    ("manager@matchify.dev", "Elena Petrou", True),
    ("dimitris@matchify.dev", "Dimitris Anagnostou", False),
]

#: Each candidate carries the structured detail the graph export reads:
#: dated per-role skills (so years-per-skill and last-used-year vary), an
#: employer industry from the INDUSTRIES vocabulary, a normalized degree level,
#: CEFR languages, and — for some — certifications and achievements. `skills`
#: at the top level is the union of the roles' skills, used for job matching and
#: the flat profile list. A role tuple is (title, company, industry, start, end,
#: skills); end is None for the current job.
CANDIDATES = [
    {
        "email": "nikos@example.com",
        "name": "Nikos Koukis",
        "phone": "6972534499",
        "headline": "Senior Software Engineer",
        "summary": "Full-stack engineer focused on TypeScript, Python and distributed systems.",
        "category": "Software Engineer",
        "seniority": SeniorityLevel.SENIOR,
        "skills": ["python", "fastapi", "react", "next.js", "mongodb", "docker", "typescript"],
        "years": 7.5,
        "city": "Patras",
        "country": "Greece",
        "roles": [
            (
                "Senior Software Engineer", "Skroutz", "E-commerce",
                date(2021, 6, 1), None,
                ["python", "fastapi", "mongodb", "docker", "typescript"],
            ),
            (
                "Software Engineer", "Workable", "SaaS",
                date(2018, 2, 1), date(2021, 5, 1),
                ["python", "react", "next.js"],
            ),
        ],
        "degree": ("University of Patras", "BSc Computer Engineering", "Computer Science",
                   DegreeLevel.BACHELOR, 2013, 2018),
        "languages": [("Greek", LanguageProficiency.NATIVE), ("English", LanguageProficiency.C1)],
        "certifications": [],
        "achievements": {
            "career_highlights": [
                "Led the migration of a monolith to service boundaries, cutting "
                "deploy time from 40 to 6 minutes.",
            ],
            "projects_and_open_source": [
                "Maintainer of an open-source FastAPI starter with 1.2k GitHub stars.",
            ],
        },
    },
    {
        "email": "maria@example.com",
        "name": "Maria Georgiou",
        "phone": "6941112233",
        "headline": "Frontend Engineer",
        "summary": "Design-minded frontend engineer who cares about accessible interfaces.",
        "category": "Software Engineer",
        "seniority": SeniorityLevel.MID,
        "skills": ["react", "typescript", "next.js", "tailwind", "figma"],
        "years": 4.0,
        "city": "Athens",
        "country": "Greece",
        "roles": [
            (
                "Frontend Engineer", "Beat", "Travel",
                date(2022, 3, 1), None,
                ["react", "typescript", "next.js", "tailwind"],
            ),
            (
                "Junior Frontend Developer", "Persado", "Media",
                date(2020, 6, 1), date(2022, 2, 1),
                ["react", "figma"],
            ),
        ],
        "degree": ("Aristotle University of Thessaloniki", "BSc Informatics", "Informatics",
                   DegreeLevel.BACHELOR, 2016, 2020),
        "languages": [("Greek", LanguageProficiency.NATIVE), ("English", LanguageProficiency.C1)],
        "certifications": [],
        "achievements": {
            "academic_distinctions": ["Graduated top of class, GPA 9.1/10."],
        },
    },
    {
        "email": "yannis@example.com",
        "name": "Yannis Papadakis",
        "phone": "6944445566",
        "headline": "Backend Engineer",
        "summary": "Python backend engineer with a bias toward boring, observable systems.",
        "category": "Software Engineer",
        "seniority": SeniorityLevel.SENIOR,
        "skills": ["python", "fastapi", "postgresql", "kubernetes", "mongodb"],
        "years": 8.0,
        "city": "Thessaloniki",
        "country": "Greece",
        "roles": [
            (
                "Backend Engineer", "Pfizer Digital", "Healthcare",
                date(2019, 9, 1), None,
                ["python", "fastapi", "postgresql", "kubernetes"],
            ),
            (
                "Software Engineer", "Intrasoft International", "Consulting",
                date(2016, 7, 1), date(2019, 8, 1),
                ["python", "mongodb"],
            ),
        ],
        "degree": ("Aristotle University of Thessaloniki", "MSc Distributed Systems",
                   "Computer Science", DegreeLevel.MASTER, 2014, 2016),
        "languages": [("Greek", LanguageProficiency.NATIVE), ("English", LanguageProficiency.C2)],
        "certifications": [
            ("Certified Kubernetes Administrator (CKA)", "Cloud Native Computing Foundation", 2022),
        ],
        "achievements": {
            "career_highlights": [
                "Cut p99 API latency by 60% by moving hot paths off the ORM onto "
                "raw async queries.",
            ],
        },
    },
    {
        "email": "sofia@example.com",
        "name": "Sofia Dimitriou",
        "phone": "6947778899",
        "headline": "Product Designer",
        "summary": "Product designer working across research, systems and prototyping.",
        "category": "Design",
        "seniority": SeniorityLevel.SENIOR,
        "skills": ["figma", "design systems", "prototyping", "user research"],
        "years": 6.0,
        "city": "Athens",
        "country": "Greece",
        "roles": [
            (
                "Product Designer", "Viva Wallet", "Fintech",
                date(2020, 4, 1), None,
                ["figma", "design systems", "prototyping"],
            ),
            (
                "UX Designer", "Kaizen Gaming", "Gaming",
                date(2018, 2, 1), date(2020, 3, 1),
                ["figma", "user research"],
            ),
        ],
        "degree": ("Athens School of Fine Arts", "BA Graphic Design", "Design",
                   DegreeLevel.BACHELOR, 2011, 2015),
        "languages": [("Greek", LanguageProficiency.NATIVE), ("English", LanguageProficiency.C1)],
        "certifications": [],
        "achievements": {
            "awards_and_competitions": ["Won the 2021 Greek UX Awards in the Fintech category."],
        },
    },
    {
        "email": "alex@example.com",
        "name": "Alex Ioannou",
        "phone": "6931234567",
        "headline": "Junior Data Analyst",
        "summary": "Analyst moving from research into product analytics.",
        "category": "Data",
        "seniority": SeniorityLevel.JUNIOR,
        "skills": ["sql", "python", "pandas", "tableau"],
        "years": 1.5,
        "city": "Patras",
        "country": "Greece",
        "roles": [
            (
                "Junior Data Analyst", "Skroutz", "E-commerce",
                date(2024, 1, 1), None,
                ["sql", "python", "pandas", "tableau"],
            ),
        ],
        "degree": ("University of Patras", "BSc Mathematics", "Mathematics",
                   DegreeLevel.BACHELOR, 2018, 2023),
        "languages": [("Greek", LanguageProficiency.NATIVE), ("English", LanguageProficiency.B2)],
        "certifications": [
            ("Google Data Analytics Professional Certificate", "Google", 2024),
        ],
        "achievements": {},
    },
]

# ── postings ─────────────────────────────────────────────────────────────────

JOBS = [
    {
        "title": "Senior Full-Stack Engineer",
        "category": "Software Engineer",
        "seniority": SeniorityLevel.SENIOR,
        "mode": WorkMode.HYBRID,
        "skills": ["typescript", "react", "next.js", "python", "fastapi", "mongodb"],
        "status": JobStatus.PUBLISHED,
        "published_days_ago": 21,
        "salary": (55000, 75000),
        "openings": 2,
        "description": (
            "You will own features end to end across our Next.js frontend and "
            "FastAPI backend, working directly with hiring managers to shape "
            "what we build."
        ),
        "responsibilities": [
            "Design and ship full-stack features across the platform",
            "Own service boundaries, data models and API contracts",
            "Review code and raise the bar on testing and observability",
        ],
        "requirements": [
            "5+ years building production web applications",
            "Strong TypeScript and Python",
            "Comfortable with MongoDB or a similar document store",
        ],
        "nice_to_have": ["Docker and CI/CD experience", "Prior startup experience"],
    },
    {
        "title": "Frontend Engineer (React)",
        "category": "Software Engineer",
        "seniority": SeniorityLevel.MID,
        "mode": WorkMode.REMOTE,
        "skills": ["react", "typescript", "next.js", "tailwind"],
        "status": JobStatus.PUBLISHED,
        "published_days_ago": 18,
        "salary": (40000, 55000),
        "openings": 1,
        "description": "Build the interfaces candidates and hiring managers use every day.",
        "responsibilities": [
            "Implement accessible, responsive interfaces",
            "Grow and maintain our component library",
        ],
        "requirements": ["3+ years with React", "Solid CSS fundamentals"],
        "nice_to_have": ["Design systems experience"],
    },
    {
        "title": "Backend Engineer (Python)",
        "category": "Software Engineer",
        "seniority": SeniorityLevel.SENIOR,
        "mode": WorkMode.ONSITE,
        "skills": ["python", "fastapi", "mongodb", "docker"],
        "status": JobStatus.PUBLISHED,
        "published_days_ago": 14,
        "salary": (50000, 70000),
        "openings": 1,
        "description": "Own the services behind matching, applications and analytics.",
        "responsibilities": [
            "Design APIs and data models",
            "Keep the platform fast and observable under load",
        ],
        "requirements": ["5+ years Python", "Async experience", "Strong data modelling"],
        "nice_to_have": ["Kubernetes"],
    },
    {
        "title": "Product Designer",
        "category": "Design",
        "seniority": SeniorityLevel.SENIOR,
        "mode": WorkMode.HYBRID,
        "skills": ["figma", "design systems", "user research", "prototyping"],
        "status": JobStatus.PUBLISHED,
        "published_days_ago": 10,
        "salary": (42000, 58000),
        "openings": 1,
        "description": "Shape the end-to-end hiring experience for both sides of the marketplace.",
        "responsibilities": ["Run discovery and usability sessions", "Own the design system"],
        "requirements": ["4+ years in product design", "Portfolio of shipped work"],
        "nice_to_have": ["Front-end literacy"],
    },
    {
        "title": "Data Analyst",
        "category": "Data",
        "seniority": SeniorityLevel.JUNIOR,
        "mode": WorkMode.REMOTE,
        "skills": ["sql", "python", "pandas", "tableau"],
        "status": JobStatus.PUBLISHED,
        "published_days_ago": 7,
        "salary": (28000, 38000),
        "openings": 1,
        "description": "Turn hiring funnel data into decisions the team actually makes.",
        "responsibilities": ["Build dashboards", "Answer funnel and conversion questions"],
        "requirements": ["Strong SQL", "Python for analysis"],
        "nice_to_have": ["Experience with A/B testing"],
    },
    {
        "title": "DevOps Engineer",
        "category": "Infrastructure",
        "seniority": SeniorityLevel.MID,
        "mode": WorkMode.REMOTE,
        "skills": ["docker", "kubernetes", "terraform", "ci/cd"],
        "status": JobStatus.DRAFT,  # exercises the draft/publish flow in the UI
        "published_days_ago": None,
        "salary": (45000, 62000),
        "openings": 1,
        "description": "Own the deployment pipeline and production reliability.",
        "responsibilities": ["Build and maintain CI/CD", "Own observability"],
        "requirements": ["3+ years infrastructure work", "Kubernetes in production"],
        "nice_to_have": ["Terraform"],
    },
]

# (candidate index, job index, stage, days ago) — deterministic funnel that
# produces a realistic stage distribution and a readable chart.
APPLICATION_MATRIX = [
    (0, 0, PipelineStage.INTERVIEW, 19),
    (0, 1, PipelineStage.SCREENING, 16),
    (0, 2, PipelineStage.OFFER, 12),
    (0, 4, PipelineStage.APPLIED, 5),
    (1, 1, PipelineStage.INTERVIEW, 15),
    (1, 0, PipelineStage.REJECTED, 17),
    (1, 3, PipelineStage.APPLIED, 6),
    (2, 2, PipelineStage.HIRED, 13),
    (2, 0, PipelineStage.SCREENING, 11),
    (2, 1, PipelineStage.REJECTED, 9),
    (3, 3, PipelineStage.INTERVIEW, 8),
    (3, 0, PipelineStage.APPLIED, 4),
    (4, 4, PipelineStage.SCREENING, 6),
    (4, 2, PipelineStage.REJECTED, 10),
    (4, 0, PipelineStage.APPLIED, 2),
]


async def _seed_organization() -> None:
    org = await Organization.find_one(Organization.key == ORG_SINGLETON_KEY)
    if org is None:
        org = Organization(key=ORG_SINGLETON_KEY, name=settings.org_name)
    org.name = settings.org_name
    org.website = settings.org_website
    org.description = (
        "We build hiring software. Small team, high ownership, remote-friendly."
    )
    org.industry = "Software"
    org.size = "11-50"
    org.headquarters = Location(country="Greece", city="Patras", postal_code="26500")
    await org.save()
    organization_service.invalidate_cache()


async def _seed_users() -> tuple[list[User], list[User]]:
    managers: list[User] = []
    for email, name, is_admin in MANAGERS:
        user = User(
            email=email,
            password_hash=hash_password(PASSWORD),
            role=Role.HIRING_MANAGER,
            full_name=name,
            is_admin=is_admin,
            is_email_verified=True,
        )
        await user.insert()
        managers.append(user)

    candidates: list[User] = []
    for spec in CANDIDATES:
        user = User(
            email=spec["email"],
            password_hash=hash_password(PASSWORD),
            role=Role.CANDIDATE,
            full_name=spec["name"],
            phone=spec["phone"],
            is_email_verified=True,
        )
        await user.insert()

        experience = [
            Experience(
                company=company,
                title=title,
                start_date=start,
                end_date=end,
                is_current=end is None,
                location=spec["city"],
                description="Built and shipped production systems end to end.",
                # Skills live on the role that used them; the profile's flat
                # list is the union of these. Dated roles let the graph export
                # derive years-per-skill and last-used-year.
                skills=list(role_skills),
                company_industry=industry,
            )
            for (title, company, industry, start, end, role_skills) in spec["roles"]
        ]

        inst, degree, field, degree_level, start_year, end_year = spec["degree"]
        education = [
            Education(
                institution=inst,
                degree=degree,
                degree_level=degree_level,
                field=field,
                start_date=date(start_year, 9, 1),
                end_date=date(end_year, 7, 1),
            )
        ]

        achievements = (
            Achievements(**spec["achievements"]) if spec["achievements"] else Achievements()
        )

        profile = CandidateProfile(
            user_id=user.id,
            headline=spec["headline"],
            summary=spec["summary"],
            job_category=spec["category"],
            seniority=spec["seniority"],
            skills=spec["skills"],
            years_experience=spec["years"],
            location=Location(country=spec["country"], city=spec["city"]),
            work_modes=[WorkMode.REMOTE, WorkMode.HYBRID],
            open_to_relocate=True,
            experience=experience,
            education=education,
            languages=[Language(name=name, level=level) for name, level in spec["languages"]],
            certifications=[
                Certification(name=name, issuer=issuer, issued_year=year)
                for name, issuer, year in spec["certifications"]
            ],
            achievements=achievements,
            links=Links(github="https://github.com/", linkedin="https://linkedin.com/"),
        )
        profile.recompute_completion()
        await profile.insert()
        candidates.append(user)

    return managers, candidates


async def _seed_jobs(managers: list[User]) -> list[Job]:
    jobs: list[Job] = []
    for index, spec in enumerate(JOBS):
        owner = managers[index % len(managers)]
        published = (
            _days_ago(spec["published_days_ago"])
            if spec["published_days_ago"] is not None
            else None
        )
        job = Job(
            created_by=owner.id,
            title=spec["title"],
            slug=spec["title"].lower().replace(" ", "-").replace("(", "").replace(")", ""),
            description=spec["description"],
            responsibilities=spec["responsibilities"],
            # Structured requirements. The first two skills are mandatory with a
            # minimum duration; the rest are weighted preferences.
            mandatory=MandatoryRequirements(
                min_years_total_experience=SENIORITY_MIN_YEARS.get(spec["seniority"]),
                education=[
                    RequiredEducation(
                        degree_level=DegreeLevel.BACHELOR, field_of_study=spec["category"]
                    )
                ],
                skills=[
                    RequiredSkill(slug=s, name=s.title(), min_years=2)
                    for s in spec["skills"][:2]
                ],
                languages=[
                    RequiredLanguage(
                        language="English", min_proficiency=LanguageProficiency.B2
                    )
                ],
            ),
            nice_to_have=NiceToHave(
                skills=[
                    NiceToHaveSkill(slug=s, name=s.title(), weight=weight)
                    for s, weight in zip(
                        spec["skills"][2:5], (1.0, 0.6, 0.3), strict=False
                    )
                ],
                preferred_industries=["Tech", "SaaS"],
            ),
            skills_required=list(spec["skills"]),
            job_category=spec["category"],
            seniority=spec["seniority"],
            employment_type=EmploymentType.FULL_TIME,
            work_mode=spec["mode"],
            location=JobLocation(
                country="Greece",
                city="Patras",
                is_remote=spec["mode"] is WorkMode.REMOTE,
            ),
            salary=Salary(min=spec["salary"][0], max=spec["salary"][1], currency="EUR"),
            openings=spec["openings"],
            status=spec["status"],
            published_at=published,
            created_at=published or _days_ago(2),
        )
        await job.insert()
        jobs.append(job)
    return jobs


async def _seed_applications(
    candidates: list[User], jobs: list[Job], managers: list[User]
) -> None:
    counters: dict[str, dict[str, int]] = {}

    for candidate_idx, job_idx, stage, days in APPLICATION_MATRIX:
        candidate = candidates[candidate_idx]
        job = jobs[job_idx]
        spec = CANDIDATES[candidate_idx]
        applied_at = _days_ago(days)

        history = [StageChange(to_stage=PipelineStage.APPLIED, changed_at=applied_at)]
        if stage is not PipelineStage.APPLIED:
            history.append(
                StageChange(
                    from_stage=PipelineStage.APPLIED,
                    to_stage=stage,
                    changed_by=managers[0].id,
                    changed_at=applied_at + timedelta(days=1),
                )
            )

        notes = []
        if stage in (PipelineStage.INTERVIEW, PipelineStage.OFFER, PipelineStage.HIRED):
            notes.append(
                InternalNote(
                    author_id=managers[0].id,
                    author_name=managers[0].full_name,
                    body="Strong technical screen — moving forward.",
                    created_at=applied_at + timedelta(days=1),
                )
            )

        application = Application(
            job_id=job.id,
            candidate_id=candidate.id,
            job_snapshot=JobSnapshot(
                title=job.title,
                location="Remote" if job.location.is_remote else "Patras, Greece",
                employment_type=job.employment_type,
                seniority=job.seniority,
            ),
            candidate_snapshot=CandidateSnapshot(
                full_name=candidate.full_name,
                email=candidate.email,
                headline=spec["headline"],
            ),
            cover_letter=(
                f"I am excited about the {job.title} role and believe my "
                f"{spec['years']} years of experience are a strong fit."
            ),
            stage=stage,
            stage_history=history,
            is_shortlisted=stage in SHORTLISTED_FROM,
            rating=4 if stage in (PipelineStage.OFFER, PipelineStage.HIRED) else None,
            notes=notes,
            applied_at=applied_at,
            updated_at=applied_at + timedelta(days=1),
        )
        await application.insert()

        bucket = counters.setdefault(str(job.id), {"applications": 0, "shortlisted": 0, "hired": 0})
        bucket["applications"] += 1
        if application.is_shortlisted:
            bucket["shortlisted"] += 1
        if stage is PipelineStage.HIRED:
            bucket["hired"] += 1

    for job in jobs:
        stats = counters.get(str(job.id))
        if stats:
            job.stats.applications = stats["applications"]
            job.stats.shortlisted = stats["shortlisted"]
            job.stats.hired = stats["hired"]
            job.stats.views = stats["applications"] * 14
            await job.save()


#: Everything a demo run creates, in delete order (children before the users
#: they hang off). The organization singleton is deliberately absent: it is this
#: deployment's identity, not funnel data, so clearing leaves a working-but-empty
#: app rather than one with no company. `documents` rows are removed but the
#: MinIO blobs they pointed at are not — orphaned objects are harmless in dev.
_MOCK_MODELS = (Application, UserDocument, RefreshToken, Job, CandidateProfile, User)


async def clear() -> None:
    """Delete all demo data — people, postings, applications, uploads, sessions.

    Idempotent: safe to run against an already-empty database. Used both by
    `--clear` (wipe and stop) and by `--reset` (wipe, then refill).
    """
    total = 0
    for model in _MOCK_MODELS:
        result = await model.get_pymongo_collection().delete_many({})
        total += result.deleted_count
        logger.info("cleared %-18s %d", model.Settings.name, result.deleted_count)
    logger.info("clear complete — %d documents removed", total)


async def seed(reset: bool = False) -> None:
    # Demo data on a production deployment is a deliberate act, and the failure
    # mode is severe: the seeded hiring manager is an admin, and its password is
    # published in the README. Requiring SEED_PASSWORD makes that impossible to
    # do by accident.
    if settings.is_production and not os.getenv("SEED_PASSWORD"):
        raise RuntimeError(
            "Refusing to seed a production deployment with the default demo "
            "password. Set SEED_PASSWORD to a strong value to proceed."
        )

    if reset:
        await clear()

    await _seed_organization()
    managers, candidates = await _seed_users()
    jobs = await _seed_jobs(managers)
    await _seed_applications(candidates, jobs, managers)

    logger.info(
        "seed complete — %d managers, %d candidates, %d jobs, %d applications",
        len(managers),
        len(candidates),
        len(jobs),
        len(APPLICATION_MATRIX),
    )


async def seed_if_empty() -> None:
    """Called on startup in non-production so a fresh stack is never empty."""
    if await User.count() > 0:
        return
    await seed()


async def _main() -> None:
    from app.db import mongo

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Seed the Matchify database")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--reset", action="store_true", help="Delete existing demo data, then re-seed"
    )
    group.add_argument(
        "--clear", action="store_true", help="Delete all demo data and stop (no re-seed)"
    )
    args = parser.parse_args()

    await mongo.connect()
    if args.clear:
        await clear()
    else:
        await seed(reset=args.reset)
    await mongo.disconnect()


if __name__ == "__main__":
    asyncio.run(_main())
