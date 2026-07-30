"""Update endpoints must persist nested models as models, not dicts.

`data.model_dump()` flattens nested Pydantic models into plain dicts, and Beanie
documents do not validate on assignment — so a naive `setattr(doc, k, v)` loop
silently replaces `profile.location` (a `Location`) with a `dict`. Nothing fails
at write time; the next attribute access 500s.

Each test below saves, then reads back through a code path that touches a nested
attribute, which is what actually catches the regression.
"""

from httpx import AsyncClient

from tests.conftest import register

FULL_DRAFT = {
    "full_name": "Profile Person",
    "headline": "Senior Software Engineer",
    "summary": "Builds things.",
    "email": "profile@example.com",
    "phone": "6970000000",
    "city": "Patras",
    "country": "Greece",
    "job_category": "Software Engineer",
    "seniority": "senior",
    "years_experience": 7.5,
    "open_to_relocate": True,
    "work_modes": ["remote", "hybrid"],
    "experience": [
        {
            "company": "Acme",
            "title": "Engineer",
            "start_date": "2019-03",
            "is_current": True,
            "description": "Shipped things.",
            "skills": ["Python", "FastAPI", "python"],
            "company_industry": "Fintech",
        }
    ],
    "education": [
        {
            "institution": "University of Patras",
            "degree": "BSc",
            "degree_level": "Bachelor",
            "field": "Computer Science",
            "start_date": "2013-09",
            "end_date": "2018-07",
        }
    ],
    "languages": [{"name": "Greek", "level": "Native"}],
    "certifications": [
        {"name": "AWS Certified ML", "issuer": "Amazon Web Services", "issued_year": 2022}
    ],
    "achievements": {
        "career_highlights": ["Cut latency 40%"],
        "academic_distinctions": ["Top 5% of class"],
        "awards_and_competitions": [],
        "projects_and_open_source": [],
    },
    "links": {"github": "https://github.com/x"},
}


async def test_the_profile_has_no_write_endpoint(client: AsyncClient, api: str):
    """The resume builder is the single editing surface. A second write path
    would reintroduce two sources of truth for the same fields."""
    await register(client, api, email="nowrite@example.com", role="candidate")

    response = await client.put(f"{api}/candidates/me/profile", json={"headline": "Direct"})
    assert response.status_code == 405, response.text

    # Reading is still fine — the profile page renders from it.
    assert (await client.get(f"{api}/candidates/me/profile")).status_code == 200


async def test_generating_a_resume_writes_the_profile(client: AsyncClient, api: str):
    await register(client, api, email="viabuilder@example.com", role="candidate")

    generated = await client.post(
        f"{api}/resume/generate",
        json={"draft": FULL_DRAFT, "template": "professional"},
    )
    assert generated.status_code == 201, generated.text

    profile = (await client.get(f"{api}/candidates/me/profile")).json()
    assert profile["headline"] == "Senior Software Engineer"
    assert profile["location"]["city"] == "Patras"
    assert profile["experience"][0]["company"] == "Acme"
    # Skills are normalized and de-duplicated on write.
    assert profile["skills"] == ["python", "fastapi"]
    # Fields that only exist for matching still round-trip.
    assert profile["seniority"] == "senior"
    assert profile["job_category"] == "Software Engineer"
    # Derived from the role dates, not entered — one role since 2019-03.
    assert profile["years_experience"] is not None and profile["years_experience"] > 5
    assert profile["open_to_relocate"] is True
    assert set(profile["work_modes"]) == {"remote", "hybrid"}
    # completion_percent walks nested attributes — it is what used to raise
    # AttributeError when a dict was stored instead of a model.
    assert profile["completion_percent"] > 0


async def test_generating_twice_reads_back_what_the_first_pass_wrote(
    client: AsyncClient, api: str
):
    await register(client, api, email="twice@example.com", role="candidate")

    first = await client.post(
        f"{api}/resume/generate", json={"draft": FULL_DRAFT, "template": "professional"}
    )
    assert first.status_code == 201

    second = await client.post(
        f"{api}/resume/generate",
        json={
            "draft": {**FULL_DRAFT, "headline": "Principal Engineer"},
            "template": "professional",
        },
    )
    assert second.status_code == 201, second.text

    profile = (await client.get(f"{api}/candidates/me/profile")).json()
    assert profile["headline"] == "Principal Engineer"
    assert profile["location"]["city"] == "Patras"


SECOND_ROLE = {
    "company": "Older Co",
    "title": "Junior Engineer",
    "start_date": "2016-01",
    "end_date": "2019-02",
    "is_current": False,
    "skills": ["php"],
    "company_industry": "Consulting",
}


async def test_deleting_entries_in_the_builder_clears_them_from_the_profile(
    client: AsyncClient, api: str
):
    """The draft is the profile, so removing a role must actually remove it.

    A merge that skipped empty values would leave the old entries in place and
    there would be no way to delete anything at all.
    """
    await register(client, api, email="clear@example.com", role="candidate")

    two_roles = {**FULL_DRAFT, "experience": [*FULL_DRAFT["experience"], SECOND_ROLE]}
    await client.post(
        f"{api}/resume/generate", json={"draft": two_roles, "template": "professional"}
    )
    seeded = (await client.get(f"{api}/candidates/me/profile")).json()
    assert len(seeded["experience"]) == 2
    assert "php" in seeded["skills"]

    # Drop the older role, its skills, and the education/languages sections.
    trimmed = await client.post(
        f"{api}/resume/generate",
        json={
            "draft": {
                **FULL_DRAFT,
                "education": [],
                "languages": [],
                "summary": "",
                "links": {"linkedin": None, "github": None, "portfolio": None},
            },
            "template": "professional",
        },
    )
    assert trimmed.status_code == 201, trimmed.text

    profile = (await client.get(f"{api}/candidates/me/profile")).json()
    assert len(profile["experience"]) == 1
    # The flat skill list is the union of the surviving roles, so a deleted
    # role takes its skills with it.
    assert "php" not in profile["skills"]
    assert profile["education"] == []
    assert profile["languages"] == []
    assert profile["summary"] is None  # "" must not be stored verbatim
    assert profile["links"]["github"] is None

    # And the builder opens with them gone, rather than resurrecting them.
    draft = (await client.get(f"{api}/resume/draft")).json()["draft"]
    assert len(draft["experience"]) == 1
    assert draft["education"] == []


async def test_generate_rejects_an_incomplete_draft(client: AsyncClient, api: str):
    """Skills and dates per role are what matching and years-of-experience are
    computed from, so a resume without them is not usable by the platform."""
    await register(client, api, email="incomplete@example.com", role="candidate")

    response = await client.post(
        f"{api}/resume/generate",
        json={
            "draft": {
                **FULL_DRAFT,
                "experience": [
                    {
                        "company": "Acme",
                        "title": "Engineer",
                        "start_date": None,  # missing
                        "end_date": None,  # missing, and not current
                        "is_current": False,
                        "skills": [],  # missing
                    }
                ],
            },
            "template": "professional",
        },
    )
    assert response.status_code == 422, response.text

    issues = response.json()["detail"]["issues"]
    fields = {issue["field"] for issue in issues}
    assert {"skills", "start_date", "end_date"} <= fields
    # Each issue points at the row it belongs to, so the UI can highlight it.
    assert all(issue["index"] == 0 for issue in issues if issue["index"] is not None)


async def test_generate_rejects_an_empty_work_history(client: AsyncClient, api: str):
    await register(client, api, email="norole@example.com", role="candidate")
    response = await client.post(
        f"{api}/resume/generate",
        json={"draft": {**FULL_DRAFT, "experience": []}, "template": "professional"},
    )
    assert response.status_code == 422
    assert "experience" in {i["field"] for i in response.json()["detail"]["issues"]}


async def test_years_of_experience_merges_overlapping_roles(client: AsyncClient, api: str):
    """Two jobs held at once for a year is one year of experience, not two."""
    await register(client, api, email="overlap@example.com", role="candidate")

    await client.post(
        f"{api}/resume/generate",
        json={
            "draft": {
                **FULL_DRAFT,
                "experience": [
                    {
                        "company": "A",
                        "title": "Engineer",
                        "start_date": "2015-01",
                        "end_date": "2020-01",
                        "is_current": False,
                        "skills": ["python"],
                    },
                    {
                        "company": "B",
                        "title": "Consultant",
                        "start_date": "2017-01",
                        "end_date": "2019-01",  # entirely inside the first span
                        "is_current": False,
                        "skills": ["sql"],
                    },
                ],
            },
            "template": "professional",
        },
    )

    profile = (await client.get(f"{api}/candidates/me/profile")).json()
    # 5 years total, not 7 — the overlap is not double-counted.
    assert 4.9 <= profile["years_experience"] <= 5.1
    assert set(profile["skills"]) == {"python", "sql"}


async def test_the_builder_draft_is_seeded_from_the_profile(client: AsyncClient, api: str):
    """Round trip: what the builder wrote is what it offers back next time."""
    await register(client, api, email="seed@example.com", role="candidate")
    await client.post(
        f"{api}/resume/generate", json={"draft": FULL_DRAFT, "template": "professional"}
    )

    seeded = await client.get(f"{api}/resume/draft")
    assert seeded.status_code == 200
    draft = seeded.json()["draft"]
    assert seeded.json()["has_profile_data"] is True
    assert draft["headline"] == "Senior Software Engineer"
    assert draft["seniority"] == "senior"
    assert draft["work_modes"] == ["remote", "hybrid"]
    assert draft["experience"][0]["company"] == "Acme"


async def test_updating_a_job_keeps_nested_location_and_salary(client: AsyncClient, api: str):
    await register(client, api, email="jobedit@matchify.dev", role="hiring_manager")

    created = await client.post(
        f"{api}/jobs",
        json={
            "title": "Backend Engineer",
            "mandatory": {"skills": [{"slug": "python", "name": "Python"}]},
            "status": "draft",
        },
    )
    job_id = created.json()["id"]

    updated = await client.patch(
        f"{api}/jobs/{job_id}",
        json={
            "title": "  Staff Backend Engineer  ",
            "location": {"country": "Greece", "city": "Athens", "is_remote": False},
            "salary": {"min": 60000, "max": 80000, "currency": "EUR", "is_public": True},
            "mandatory": {
                "skills": [
                    {"slug": "python", "name": "Python", "min_years": 3},
                    {"slug": "go", "name": "Go"},
                ]
            },
            "status": "published",
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["title"] == "Staff Backend Engineer"  # trimmed
    assert body["location"]["city"] == "Athens"
    assert body["salary"]["min"] == 60000
    # Derived from the structured requirements, never sent by the client.
    assert body["skills_required"] == ["python", "go"]
    assert body["mandatory"]["skills"][0]["min_years"] == 3
    assert body["published_at"] is not None

    # The public serializer reads job.location.is_remote — a dict breaks it.
    public = await client.get(f"{api}/jobs/{job_id}")
    assert public.status_code == 200
    assert public.json()["location"]["is_remote"] is False


async def test_updating_the_organization_keeps_nested_settings(client: AsyncClient, api: str):
    await register(client, api, email="orgadmin@matchify.dev", role="hiring_manager")

    updated = await client.patch(
        f"{api}/organization",
        json={
            "name": "Matchify Hellas",
            "headquarters": {"country": "Greece", "city": "Patras"},
            "hiring": {
                "default_pipeline_stages": ["applied", "interview", "hired"],
                "require_cover_letter": True,
                "required_documents": ["resume", "passport"],
            },
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["headquarters"]["city"] == "Patras"
    assert updated.json()["hiring"]["require_cover_letter"] is True

    # The checklist endpoint reads org.hiring.required_documents.
    await client.post(f"{api}/auth/logout")
    await register(client, api, email="checklist@example.com", role="candidate")
    checklist = await client.get(f"{api}/documents/me/checklist")
    assert checklist.status_code == 200
    assert checklist.json()["required"] == ["resume", "passport"]


async def test_updating_the_account_name(client: AsyncClient, api: str):
    await register(client, api, email="acct@example.com", role="candidate")
    response = await client.patch(f"{api}/auth/me", json={"full_name": "Renamed Person"})
    assert response.status_code == 200
    assert response.json()["user"]["full_name"] == "Renamed Person"


async def test_job_graph_export_mirrors_the_candidate_vocabulary(
    client: AsyncClient, api: str
):
    """The two sides of the graph must speak the same language.

    Skill slugs, seniority casing and CEFR levels have to line up or a MERGE on
    one side never meets the other.
    """
    await register(client, api, email="graphjob@matchify.dev", role="hiring_manager")

    created = await client.post(
        f"{api}/jobs",
        json={
            "title": "Senior Data Scientist",
            "seniority": "senior",
            "job_category": "Data",
            "status": "published",
            "mandatory": {
                "min_years_total_experience": 4,
                "education": [
                    {"degree_level": "Bachelor", "field_of_study": "Data Science"}
                ],
                "skills": [
                    {"slug": "python", "name": "Python", "min_years": 3},
                    {"slug": "sql", "name": "SQL", "min_years": 2},
                ],
                "languages": [{"language": "English", "min_proficiency": "C1"}],
            },
            "nice_to_have": {
                "skills": [
                    {"slug": "neo4j", "name": "Neo4j", "weight": 1.0},
                    {"slug": "docker", "name": "Docker", "weight": 0.3},
                ],
                "certifications": ["AWS Certified Machine Learning - Specialty"],
                "preferred_industries": ["Fintech"],
            },
        },
    )
    assert created.status_code == 201, created.text
    job_id = created.json()["id"]

    exported = await client.get(
        f"{api}/graph/jobs/{job_id}",
        headers={"Authorization": "Bearer test-service-token"},
    )
    assert exported.status_code == 200, exported.text
    body = exported.json()

    # Same lowercase vocabulary as the candidate export.
    assert body["seniority_level"] == "senior"
    assert [s["id"] for s in body["mandatory_requirements"]["skills"]] == ["python", "sql"]
    # Display names are canonicalised, keys are not.
    assert [s["name"] for s in body["mandatory_requirements"]["skills"]] == ["Python", "SQL"]
    assert body["mandatory_requirements"]["skills"][0]["min_years"] == 3
    assert body["mandatory_requirements"]["languages"][0]["min_proficiency"] == "C1"
    # Nice-to-have comes back strongest first.
    assert [s["weight"] for s in body["nice_to_have"]["skills"]] == [1.0, 0.3]
    assert body["status"] == "published"


async def test_graph_job_export_hides_unpublished_roles(client: AsyncClient, api: str):
    """A graph that ingests drafts recommends candidates for jobs that do not exist."""
    await register(client, api, email="draftjob@matchify.dev", role="hiring_manager")
    await client.post(
        f"{api}/jobs",
        json={
            "title": "Draft Role",
            "status": "draft",
            "mandatory": {"skills": [{"slug": "python", "name": "Python"}]},
        },
    )

    headers = {"Authorization": "Bearer test-service-token"}
    published = await client.get(f"{api}/graph/jobs", headers=headers)
    assert published.status_code == 200
    assert all(item["status"] == "published" for item in published.json()["items"])

    everything = await client.get(
        f"{api}/graph/jobs?include_unpublished=true", headers=headers
    )
    assert everything.json()["total"] > published.json()["total"]


async def test_graph_endpoints_require_the_service_token(client: AsyncClient, api: str):
    assert (await client.get(f"{api}/graph/jobs")).status_code == 401
    assert (
        await client.get(f"{api}/graph/jobs", headers={"Authorization": "Bearer wrong"})
    ).status_code == 401
