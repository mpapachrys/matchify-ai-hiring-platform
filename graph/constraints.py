"""Uniqueness constraints for the hiring graph.

Reference/shared nodes (Skill, Language, FieldOfStudy, Industry, Certification)
are deduplicated so candidates and jobs can be matched by pointing at the
same node. Run once against a fresh database.

Skill is keyed on `normalized_name` (lower-cased, whitespace-stripped —
2026-07-25, replacing a plain `name` key), not `name`: free-text skill names
from independent sources (a candidate's parsed resume, a job posting, the
static taxonomy) vary in casing/spacing for the same real-world skill
("Power Bi" vs "Powerbi"), and a `name`-keyed MERGE silently created two
disconnected nodes for what should be one — found live in production data.
`name` is kept as a display property (first value seen wins, via
`coalesce()` in graph/ingest.py and graph/skills_taxonomy.py), just no longer
the dedup key. See graph/skills_taxonomy.py's module docstring for the
migration this required on an already-populated graph.
"""

CONSTRAINTS = [
    "CREATE CONSTRAINT candidate_id_unique IF NOT EXISTS "
    "FOR (c:Candidate) REQUIRE c.candidate_id IS UNIQUE",
    "CREATE CONSTRAINT job_id_unique IF NOT EXISTS "
    "FOR (j:Job) REQUIRE j.job_id IS UNIQUE",
    "CREATE CONSTRAINT company_id_unique IF NOT EXISTS "
    "FOR (co:Company) REQUIRE co.company_id IS UNIQUE",
    "CREATE CONSTRAINT skill_normalized_name_unique IF NOT EXISTS "
    "FOR (s:Skill) REQUIRE s.normalized_name IS UNIQUE",
    "CREATE CONSTRAINT language_name_unique IF NOT EXISTS "
    "FOR (l:Language) REQUIRE l.name IS UNIQUE",
    "CREATE CONSTRAINT field_of_study_name_unique IF NOT EXISTS "
    "FOR (f:FieldOfStudy) REQUIRE f.name IS UNIQUE",
    "CREATE CONSTRAINT industry_name_unique IF NOT EXISTS "
    "FOR (i:Industry) REQUIRE i.name IS UNIQUE",
    "CREATE CONSTRAINT certification_name_unique IF NOT EXISTS "
    "FOR (cert:Certification) REQUIRE cert.name IS UNIQUE",
    "CREATE CONSTRAINT category_name_unique IF NOT EXISTS "
    "FOR (cat:Category) REQUIRE cat.name IS UNIQUE",
    "CREATE CONSTRAINT subcategory_name_unique IF NOT EXISTS "
    "FOR (sub:SubCategory) REQUIRE sub.name IS UNIQUE",
]

#: Superseded by skill_normalized_name_unique above (2026-07-25). Dropped
#: explicitly rather than left to coexist, so constraints.py stays an
#: accurate description of the current dedup keys.
_DROPPED_CONSTRAINTS = [
    "DROP CONSTRAINT skill_name_unique IF EXISTS",
]


def apply_constraints(session):
    for statement in _DROPPED_CONSTRAINTS:
        session.run(statement)
    for statement in CONSTRAINTS:
        session.run(statement)
