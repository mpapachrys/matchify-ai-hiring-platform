"""Ingestion of candidate and job documents into the Neo4j hiring graph.

Graph model
-----------
Shared/reference nodes, deduplicated so candidates and jobs can be matched by
pointing at the same node:
    (:Skill {normalized_name, name})
    (:Language {name})
    (:FieldOfStudy {name})
    (:Industry {name})
    (:Certification {name, issuer})

Skill is keyed on `normalized_name` (lower-cased, whitespace-stripped), not
`name` — see graph/skills_taxonomy.py's module docstring and
skill_normalized_name_unique in constraints.py for why (free-text skill
names from independent sources vary in casing/spacing for the same
real-world skill, e.g. "Power Bi" vs "Powerbi"). `name` is set via
`coalesce(s.name, sk.name)` — first value seen wins, so once the taxonomy has
loaded a canonical display name, a candidate's or job's own casing never
overwrites it.

Entity nodes:
    (:Candidate {candidate_id, total_years_experience, profile_updated_at,
                 headline, seniority, job_category, location_city,
                 location_country, open_to_relocate, work_modes,
                 career_highlights, academic_distinctions,
                 awards_and_competitions, projects_and_open_source})
    (:Job {job_id, title, status, seniority_level, job_category,
           employment_type, work_mode, location_city, location_country,
           is_remote, openings, min_years_total_experience,
           max_years_total_experience})
    (:Company {company_id})

Relationships:
    (:Candidate)-[:STUDIED {degree_level, institution, graduation_year}]->(:FieldOfStudy)
    (:Candidate)-[:HAS_SKILL {years_experience, last_used_year}]->(:Skill)
    (:Candidate)-[:WORKED_IN {role, company, start, end, is_current,
                              duration_months, skills_used}]->(:Industry)
    (:Candidate)-[:HAS_CERTIFICATION {issued_year, credential_id}]->(:Certification)
    (:Candidate)-[:SPEAKS {proficiency}]->(:Language)

`issued_year`/`credential_id` on HAS_CERTIFICATION (not on the shared
Certification node) because they're per-candidate facts, not properties of the
certification itself — putting them on the shared node would mean the last
candidate loaded wins, same class of bug as the rank collision noted in
skills_taxonomy.py. `company`/`start`/`end`/etc. on WORKED_IN for the same
reason: a candidate's past employer isn't the same entity as the :Company
node used for job postings (no company_id, not a platform tenant), so it's
kept as relationship data rather than merged into :Company.
`skills_used` is the free-text list of skill names from that job's
work_history entry, kept as-is (not reified into per-stint HAS_SKILL edges).

Skill.id uses coalesce(sk.id, s.id) rather than a plain overwrite — found via
testing: a candidate whose skills entry omits `id` would otherwise null out
the id that an earlier candidate had already set on that same shared Skill
node. Skill.name uses the same coalesce pattern for the same reason, once
`normalized_name` became the merge key (see above): whichever source loads a
given skill first sets its display name, and no later source's own
casing/spacing variant overwrites it.

An education/work-history entry whose merge key is null (`field_of_study` on
STUDIED/REQUIRES_EDUCATION, `company_industry` on WORKED_IN — both optional in
the export schema) is dropped entirely rather than ingested: MERGEing a node
on a null property is a Neo4j SemanticError, and there's no other node for the
entry's other fields (degree_level, role, dates, ...) to attach to in this
schema. Both FOREACH blocks pre-filter the list (`[x IN $list WHERE
x.key IS NOT NULL]`) rather than crashing ingestion for the rest of the
document. Found via a live candidate whose education had no field_of_study.

Re-ingesting an existing Candidate/Job (e.g. a candidate edits their CV) first
DELETEs every outgoing
relationship of the types below from that node, then FOREACH re-adds the
current set from the payload. Every add_candidate/add_job call carries that
entity's *full* current state (never a partial diff), so this is the only
way a removed skill/education/work-history/etc. actually disappears from the
graph — a plain MERGE (the original approach) only ever adds or updates
edges, so anything the candidate deleted from their profile would otherwise
stay in the graph forever as a stale edge. Shared reference nodes (Skill,
Language, ...) are never deleted this way, only the relationship instance —
so a Skill node briefly left with no relationships just sits idle rather
than being cleaned up; harmless, and not worth the extra complexity of
reference-counted node deletion.

location is flattened onto the Candidate node (location_city/location_country)
rather than a separate node — nothing yet needs to query/match by location as
a shared graph entity; revisit if that changes.

    (:Job)-[:POSTED_BY]->(:Company)
    (:Job)-[:REQUIRES_EDUCATION {degree_level}]->(:FieldOfStudy)
    (:Job)-[:REQUIRES_SKILL {min_years}]->(:Skill)
    (:Job)-[:REQUIRES_LANGUAGE {min_proficiency}]->(:Language)
    (:Job)-[:PREFERS_SKILL {weight}]->(:Skill)
    (:Job)-[:PREFERS_CERTIFICATION]->(:Certification)
    (:Job)-[:PREFERS_INDUSTRY]->(:Industry)

job['company_id'] is intentionally never read even though the job schema
includes it — company_id always comes from the caller (add_jobs' company_id
argument: --company-id on the CLI, or the authenticated company's session in
the real app), never trusted from the payload. See "Things to avoid" in
CLAUDE.md.

job['schema_version'] is not stored on the Job node — it describes the shape
of the source document for the ingestion pipeline, not a fact about the job
itself, so it has no bearing on matching.

Job.location is flattened the same way as Candidate.location
(location_city/location_country) for the same reason: no shared/queryable
location entity exists yet.

Job's REQUIRES_SKILL/PREFERS_SKILL FOREACH blocks also use
coalesce(sk.id, s.id) on the shared Skill node, same fix and same reason as
Candidate's HAS_SKILL.
"""

_ADD_CANDIDATE = """
MERGE (c:Candidate {candidate_id: $candidate_id})
SET c.total_years_experience = $total_years_experience,
    c.profile_updated_at = $profile_updated_at,
    c.headline = $headline,
    c.seniority = $seniority,
    c.job_category = $job_category,
    c.location_city = $location_city,
    c.location_country = $location_country,
    c.open_to_relocate = $open_to_relocate,
    c.work_modes = $work_modes,
    c.career_highlights = $career_highlights,
    c.academic_distinctions = $academic_distinctions,
    c.awards_and_competitions = $awards_and_competitions,
    c.projects_and_open_source = $projects_and_open_source

WITH c
OPTIONAL MATCH (c)-[stale:STUDIED|HAS_SKILL|WORKED_IN|HAS_CERTIFICATION|SPEAKS]->()
DELETE stale

WITH c
FOREACH (edu IN [e IN $education WHERE e.field_of_study IS NOT NULL] |
  MERGE (f:FieldOfStudy {name: edu.field_of_study})
  MERGE (c)-[r:STUDIED]->(f)
  SET r.degree_level = edu.degree_level,
      r.institution = edu.institution,
      r.graduation_year = edu.graduation_year
)

FOREACH (sk IN $skills |
  MERGE (s:Skill {normalized_name: replace(toLower(sk.name), " ", "")})
  SET s.name = coalesce(s.name, sk.name),
      s.id = coalesce(sk.id, s.id)
  MERGE (c)-[rs:HAS_SKILL]->(s)
  SET rs.years_experience = sk.years_experience,
      rs.last_used_year = sk.last_used_year
)

FOREACH (w IN [wh IN $work_history WHERE wh.company_industry IS NOT NULL] |
  MERGE (i:Industry {name: w.company_industry})
  MERGE (c)-[rw:WORKED_IN {role: w.role, company: w.company, start: w.start}]->(i)
  SET rw.end = w.end,
      rw.is_current = w.is_current,
      rw.duration_months = w.duration_months,
      rw.skills_used = w.skills
)

FOREACH (cert IN $certifications |
  MERGE (cf:Certification {name: cert.name})
  SET cf.issuer = cert.issuer
  MERGE (c)-[rc:HAS_CERTIFICATION]->(cf)
  SET rc.issued_year = cert.issued_year,
      rc.credential_id = cert.credential_id
)

FOREACH (lang IN $languages |
  MERGE (l:Language {name: lang.language})
  MERGE (c)-[rl:SPEAKS]->(l)
  SET rl.proficiency = lang.proficiency
)
"""

_ADD_JOB = """
MERGE (j:Job {job_id: $job_id})
SET j.title = $title,
    j.status = $status,
    j.seniority_level = $seniority_level,
    j.job_category = $job_category,
    j.employment_type = $employment_type,
    j.work_mode = $work_mode,
    j.location_city = $location_city,
    j.location_country = $location_country,
    j.is_remote = $is_remote,
    j.openings = $openings,
    j.min_years_total_experience = $min_years_total_experience,
    j.max_years_total_experience = $max_years_total_experience

WITH j
OPTIONAL MATCH (j)-[stale:POSTED_BY|REQUIRES_EDUCATION|REQUIRES_SKILL|REQUIRES_LANGUAGE|PREFERS_SKILL|PREFERS_CERTIFICATION|PREFERS_INDUSTRY]->()
DELETE stale

WITH j
MERGE (co:Company {company_id: $company_id})
MERGE (j)-[:POSTED_BY]->(co)

FOREACH (edu IN [e IN $mandatory_education WHERE e.field_of_study IS NOT NULL] |
  MERGE (f:FieldOfStudy {name: edu.field_of_study})
  MERGE (j)-[re:REQUIRES_EDUCATION]->(f)
  SET re.degree_level = edu.degree_level
)

FOREACH (sk IN $mandatory_skills |
  MERGE (s:Skill {normalized_name: replace(toLower(sk.name), " ", "")})
  SET s.name = coalesce(s.name, sk.name),
      s.id = coalesce(sk.id, s.id)
  MERGE (j)-[rs:REQUIRES_SKILL]->(s)
  SET rs.min_years = sk.min_years
)

FOREACH (lang IN $mandatory_languages |
  MERGE (l:Language {name: lang.language})
  MERGE (j)-[rl:REQUIRES_LANGUAGE]->(l)
  SET rl.min_proficiency = lang.min_proficiency
)

FOREACH (sk IN $nice_to_have_skills |
  MERGE (s:Skill {normalized_name: replace(toLower(sk.name), " ", "")})
  SET s.name = coalesce(s.name, sk.name),
      s.id = coalesce(sk.id, s.id)
  MERGE (j)-[rp:PREFERS_SKILL]->(s)
  SET rp.weight = sk.weight
)

FOREACH (cert_name IN $nice_to_have_certifications |
  MERGE (cf:Certification {name: cert_name})
  MERGE (j)-[:PREFERS_CERTIFICATION]->(cf)
)

FOREACH (ind IN $preferred_industries |
  MERGE (i:Industry {name: ind})
  MERGE (j)-[:PREFERS_INDUSTRY]->(i)
)
"""


def add_candidate(session, candidate: dict) -> None:
    """Only candidate_id is required — every other field is optional and
    missing ones are passed through as None/[] so a partial profile still
    gets a Candidate node rather than failing ingestion."""
    achievements = candidate.get("achievements", {}) or {}
    location = candidate.get("location", {}) or {}
    session.run(
        _ADD_CANDIDATE,
        candidate_id=candidate["candidate_id"],
        total_years_experience=candidate.get("total_years_experience"),
        profile_updated_at=candidate.get("profile_updated_at"),
        headline=candidate.get("headline"),
        seniority=candidate.get("seniority"),
        job_category=candidate.get("job_category"),
        location_city=location.get("city"),
        location_country=location.get("country"),
        open_to_relocate=candidate.get("open_to_relocate"),
        work_modes=candidate.get("work_modes", []),
        career_highlights=achievements.get("career_highlights", []),
        academic_distinctions=achievements.get("academic_distinctions", []),
        awards_and_competitions=achievements.get("awards_and_competitions", []),
        projects_and_open_source=achievements.get("projects_and_open_source", []),
        education=candidate.get("education", []),
        skills=candidate.get("skills", []),
        work_history=candidate.get("work_history", []),
        certifications=candidate.get("certifications", []),
        languages=candidate.get("languages", []),
    )


def add_job(session, job: dict, company_id: str) -> None:
    """company_id is supplied by the caller (e.g. the authenticated company's
    session), not read from the job payload, so a company cannot post a job
    under another company's id — job.get("company_id") is intentionally
    ignored even if present.

    Only job_id is required — every other field is optional and missing ones
    (e.g. nice_to_have.skills, nice_to_have.preferred_industries) are passed
    through as None/[] so a partial job document still gets a Job node
    rather than failing ingestion."""
    mandatory = job.get("mandatory_requirements", {}) or {}
    nice_to_have = job.get("nice_to_have", {}) or {}
    location = job.get("location", {}) or {}
    session.run(
        _ADD_JOB,
        job_id=job["job_id"],
        company_id=company_id,
        title=job.get("title"),
        status=job.get("status"),
        seniority_level=job.get("seniority_level"),
        job_category=job.get("job_category"),
        employment_type=job.get("employment_type"),
        work_mode=job.get("work_mode"),
        location_city=location.get("city"),
        location_country=location.get("country"),
        is_remote=job.get("is_remote"),
        openings=job.get("openings"),
        min_years_total_experience=mandatory.get("min_years_total_experience"),
        max_years_total_experience=mandatory.get("max_years_total_experience"),
        mandatory_education=mandatory.get("education", []),
        mandatory_skills=mandatory.get("skills", []),
        mandatory_languages=mandatory.get("languages", []),
        nice_to_have_skills=nice_to_have.get("skills", []),
        nice_to_have_certifications=nice_to_have.get("certifications", []),
        preferred_industries=nice_to_have.get("preferred_industries", []),
    )


def add_candidates(session, candidates) -> None:
    for candidate in candidates:
        add_candidate(session, candidate)


def add_jobs(session, jobs, company_id: str) -> None:
    """Bulk-load jobs belonging to a single company (the normal case: a
    company uploads a batch of its own job postings in one authenticated
    request)."""
    for job in jobs:
        add_job(session, job, company_id)
