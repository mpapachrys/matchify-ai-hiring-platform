"""Destructive helpers for clearing the hiring graph."""


def wipe_database(session) -> None:
    session.run("MATCH (n) DETACH DELETE n")


def wipe_except_taxonomy(session) -> None:
    """Removes every node except the static skills taxonomy — :Category,
    :SubCategory, :Skill and their BELONGS_TO/IMPLIES relationships (see
    graph/skills_taxonomy.py) — leaving everything else (Candidate, Job,
    Company, Language, FieldOfStudy, Industry, Certification and their
    relationships) gone.

    Used between items in graph/match_pipeline.py: each candidate/job pair is
    scored against a clean graph plus the shared taxonomy, so the graph never
    accumulates every application ever processed."""
    session.run(
        """
        MATCH (n)
        WHERE NOT n:Category AND NOT n:SubCategory AND NOT n:Skill
        DETACH DELETE n
        """
    )
