"""Mandatory-requirements scoring and confidence heuristic for the match write-back.

Everything except skills is checked directly off the fetched candidate/job
JSON (GraphCandidate/GraphJob shape — apps/api/app/schemas/graph.py):
total-experience range, required education, required languages are all flat
comparisons the two payloads already carry. Skills are the one check that
needs the graph: the static taxonomy's IMPLIES chain
(graph/skills_taxonomy.py) means a candidate who knows a more advanced skill
should satisfy a job requiring a more foundational one it implies, and that
relationship only exists in Neo4j — this is why the taxonomy survives every
wipe_except_taxonomy() between items (graph/reset.py).

degree_level and language proficiency are closed vocabularies with an
explicit low->high order (apps/api/app/models/enums.py's DegreeLevel /
LanguageProficiency, declared in that order) — mirrored here as rank tables
rather than re-derived, since a job's "Master satisfies a Bachelor
requirement" only makes sense against that exact ordering.

Every application gets scored and posted, whether or not the candidate
clears the mandatory gate (2026-07-25 decision — see score_match()) — the
mandatory checks feed a *fraction*, not a hard pass/fail, so a candidate who
narrowly misses one requirement scores visibly higher than one who misses
everything.

field_of_study is matched by string similarity (difflib.SequenceMatcher),
not exact equality — unlike Skill, FieldOfStudy has no taxonomy backing it
in the graph, so there's no IMPLIES-style structure to lean on, and free-text
field names vary the same way skill names do ("Data Analytics" vs "Data
Analysis" for what a recruiter and a candidate both mean as the same field).
Tuned 2026-07-25 against real production data: "data analytics" scores 0.815
against a required "data analysis" (a clear match), while "data science"
(0.480), a long unrelated multi-field degree title (0.338), and an unrelated
field (0.178) all fall well short of FIELD_MATCH_THRESHOLD. Minimum
experience stays a hard cutoff deliberately (product decision) — a job's
posted `min_years_total_experience` is literal, not fuzzy. Maximum
experience is NOT a cutoff (reversed 2026-07-25 — see _experience_check):
a candidate with more experience than a job's posted max is treated as
qualified, never rejected as "overqualified," since a real 11.9-year
candidate failed an otherwise-obvious "Data Analyst" fit purely on a 7-year
cap. degree_level is ordered
(High School < ... < PhD, see DEGREE_ORDER below) so a candidate holding a
*higher* degree in the same field than a job requires already satisfies it
(a PhD satisfies a Bachelor requirement) — but never the reverse.

A candidate who clears the mandatory gate is scored the rest of the way by
an LLM (2026-07-25 — replaced an earlier hand-coded weighted-bonus formula,
per explicit product direction: the candidate's *extra* fit — nice-to-have
skills, achievements, relevant past experience, certifications, projects —
is a qualitative judgment call, not something to hard-code as
`0.2 * certification_match`). `_llm_evaluate` sends the candidate's and
job's JSON to OpenRouter (graph/llm_client.py) and asks for a confidence
score plus a plain-language reason, Pydantic-validated into
`CandidateEvaluation`. Every failure (missing API key, network error,
malformed response) falls back to `_deterministic_fallback_evaluation` — the
same category of signals, scored with a plain weighted formula, but the
formula itself never appears in what gets shown to a manager; the
`factors` text in both paths reads as a reason, not a computation.
"""

import json
import logging
import re
from difflib import SequenceMatcher

from pydantic import BaseModel, Field

from graph.llm_client import complete_json

logger = logging.getLogger(__name__)

#: Tuned against real data (see module docstring) — 0.815 for a genuine
#: near-miss spelling ("analytics"/"analysis"), 0.48 for a merely related
#: field. Conservative on purpose: a false match silently waves through an
#: unqualified candidate, a false non-match just under-scores a real one.
FIELD_MATCH_THRESHOLD = 0.75

DEGREE_ORDER = {
    level: rank
    for rank, level in enumerate(
        ["High School", "Certificate", "Diploma", "Bachelor", "Master", "PhD"]
    )
}

LANGUAGE_ORDER = {
    level: rank for rank, level in enumerate(["A1", "A2", "B1", "B2", "C1", "C2", "Native"])
}


def _normalize(name: str) -> str:
    """Same normalization as Skill.normalized_name (graph/ingest.py,
    graph/skills_taxonomy.py) — lower-cased, whitespace-stripped. Kept as a
    plain string function here (not a Cypher fragment) for the nice-to-have
    bonus in score_match(), which compares JSON directly and never touches
    the graph for that part."""
    return name.strip().lower().replace(" ", "")


def _experience_check(candidate: dict, job: dict) -> tuple[int, int]:
    """(satisfied, total) — total is 0 (no opinion) when the job sets no
    minimum. Only a shortfall against `min_years_total_experience` fails
    this check; `max_years_total_experience` is no longer a gate (product
    decision 2026-07-25) — a candidate with *more* experience than a job's
    stated max is treated as qualified, not rejected as overqualified. A
    real candidate with 11.9 years failed a "3-7 years" mandatory range
    outright under the old two-sided cutoff despite being an obvious fit on
    every other axis; the job's max is still visible to the LLM evaluation
    step afterwards (full mandatory_requirements is in its prompt) if it's
    a useful signal there, it just no longer hard-gates."""
    mandatory = job.get("mandatory_requirements") or {}
    min_years = mandatory.get("min_years_total_experience")
    if min_years is None:
        return 0, 0
    years = candidate.get("total_years_experience")
    ok = years is not None and years >= min_years
    return (1 if ok else 0), 1


def _education_check(candidate: dict, job: dict) -> tuple[int, int]:
    """(satisfied, total) across the job's required (field_of_study,
    degree_level) entries. A requirement is satisfied if *any* of the
    candidate's education entries both field-matches by string similarity
    (see module docstring) and meets the required degree_level — existential,
    not "pick the single closest-named field first": a candidate can hold a
    near-exact field name at too low a level (a Diploma) *and* a
    sufficient level under a more loosely-related name (a Master's with the
    field buried in a longer title) as separate entries, and either one
    alone should satisfy the requirement."""
    required = (job.get("mandatory_requirements") or {}).get("education") or []
    if not required:
        return 0, 0
    held = [
        ((edu.get("field_of_study") or "").strip().lower(), edu.get("degree_level"))
        for edu in candidate.get("education") or []
        if edu.get("field_of_study")
    ]
    if not held:
        return 0, len(required)

    satisfied = 0
    for req in required:
        field = (req.get("field_of_study") or "").strip().lower()
        if not field:
            continue
        req_level = req.get("degree_level")
        if any(
            SequenceMatcher(None, field, held_field).ratio() >= FIELD_MATCH_THRESHOLD
            and (not req_level or DEGREE_ORDER.get(held_level, -1) >= DEGREE_ORDER.get(req_level, 0))
            for held_field, held_level in held
        ):
            satisfied += 1
    return satisfied, len(required)


def _languages_check(candidate: dict, job: dict) -> tuple[int, int]:
    required = (job.get("mandatory_requirements") or {}).get("languages") or []
    if not required:
        return 0, 0
    held = {
        (lang.get("language") or "").strip().lower(): lang.get("proficiency")
        for lang in candidate.get("languages") or []
    }

    satisfied = 0
    for req in required:
        name = (req.get("language") or "").strip().lower()
        held_level = held.get(name)
        if held_level is None:
            continue
        min_level = req.get("min_proficiency")
        if min_level and LANGUAGE_ORDER.get(held_level, -1) < LANGUAGE_ORDER.get(min_level, 0):
            continue
        satisfied += 1
    return satisfied, len(required)


def _skill_satisfied(session, candidate_id: str, skill_name: str, min_years) -> bool:
    """True if the candidate holds `skill_name` — or a skill that IMPLIES it
    via the taxonomy, including across subcategories via CROSS_LINKS
    (graph/skills_taxonomy.py) — with enough years on the skill they actually
    hold.

    Looks up `required` by `normalized_name`, same as every Skill MERGE
    (graph/ingest.py, graph/skills_taxonomy.py) — free-text skill names from
    independent sources vary in casing/spacing for the same real-world skill
    ("Power Bi" vs "Powerbi"), and normalized_name is what makes those the
    *same* node rather than two disconnected ones, which is what lets the
    IMPLIES traversal below actually reach it. The IMPLIES traversal itself
    still has to run off the literal `required` node — that chain is only
    defined between the taxonomy's canonical nodes."""
    result = session.run(
        """
        MATCH (required:Skill {normalized_name: $normalized_skill_name})
        OPTIONAL MATCH (c:Candidate {candidate_id: $candidate_id})-[held:HAS_SKILL]->(known:Skill)
          WHERE known = required OR (known)-[:IMPLIES*1..]->(required)
        WITH held
        WHERE held IS NOT NULL
          AND ($min_years IS NULL OR held.years_experience >= $min_years)
        RETURN count(held) > 0 AS satisfied
        """,
        candidate_id=candidate_id,
        normalized_skill_name=_normalize(skill_name),
        min_years=min_years,
    ).single()
    return bool(result and result["satisfied"])


def _skills_check(session, candidate_id: str, job: dict) -> tuple[int, int]:
    required = (job.get("mandatory_requirements") or {}).get("skills") or []
    if not required:
        return 0, 0
    satisfied = sum(
        1
        for req in required
        if req.get("name") and _skill_satisfied(session, candidate_id, req["name"], req.get("min_years"))
    )
    return satisfied, len(required)


def mandatory_fit(session, candidate: dict, job: dict) -> tuple[int, int]:
    """(satisfied, total) individual mandatory checks across minimum
    experience, each required education entry, each required language, and
    each required skill. `total` is 0 only if the job sets no mandatory
    requirements at all. Candidate and job must already be ingested
    (graph/ingest.py) — the skill check queries the graph directly."""
    checks = (
        _experience_check(candidate, job),
        _education_check(candidate, job),
        _languages_check(candidate, job),
        _skills_check(session, candidate["candidate_id"], job),
    )
    satisfied = sum(s for s, _ in checks)
    total = sum(t for _, t in checks)
    return satisfied, total


class CandidateEvaluation(BaseModel):
    """The post-mandatory-gate evaluation, from either _llm_evaluate or
    _deterministic_fallback_evaluation — same shape either way, so score_match
    doesn't need to know or care which one produced it."""

    confidence: float = Field(ge=0.0, le=1.0)
    #: A plain-language reason, never a formula/weight breakdown — see
    #: _build_evaluation_prompt and _deterministic_fallback_evaluation.
    factors: str


def _job_keyword_terms(job: dict) -> set[str]:
    """Lowercased, space-preserved vocabulary for this job (skill names +
    job_category) — used only for substring/fuzzy checks against free text
    (achievements, certification names). Deliberately NOT _normalize()'d:
    that strips spaces, which would let a multi-word term like "data
    analysis" falsely match across word boundaries in a long joined string
    of achievement text."""
    mandatory_skills = (job.get("mandatory_requirements") or {}).get("skills") or []
    nice_skills = (job.get("nice_to_have") or {}).get("skills") or []
    terms = {
        (s.get("name") or "").strip().lower() for s in (mandatory_skills + nice_skills) if s.get("name")
    }
    terms.discard("")
    category = (job.get("job_category") or "").strip().lower()
    if category:
        terms.add(category)
    return terms


def _term_in_text(term: str, text: str) -> bool:
    """Word-boundary match, not plain substring — "go" as a bare skill name
    must not match inside "going"/"algorithm". Still matches multi-word
    terms like "data analysis" as a contiguous phrase."""
    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def _certification_relevance(candidate: dict, job: dict) -> float:
    """0.0-1.0. The better of two signals: exact match against the job's
    literal nice_to_have.certifications list, or — new, since a job rarely
    enumerates every acceptable certification — any candidate certification
    whose name relates (word-boundary match or fuzzy similarity) to the
    job's required/nice-to-have skills or category."""
    candidate_cert_names = {
        (c.get("name") or "").strip().lower() for c in candidate.get("certifications", []) if c.get("name")
    }
    if not candidate_cert_names:
        return 0.0

    required_certs = (job.get("nice_to_have") or {}).get("certifications") or []
    exact_fraction = 0.0
    if required_certs:
        matched = sum(1 for c in required_certs if (c or "").strip().lower() in candidate_cert_names)
        exact_fraction = matched / len(required_certs)

    job_terms = _job_keyword_terms(job)
    broadened_fraction = 0.0
    if job_terms:
        related = sum(
            1
            for cert in candidate_cert_names
            if any(
                _term_in_text(term, cert) or SequenceMatcher(None, term, cert).ratio() >= FIELD_MATCH_THRESHOLD
                for term in job_terms
            )
        )
        broadened_fraction = related / len(candidate_cert_names)

    return max(exact_fraction, broadened_fraction)


def _experience_relevance(candidate: dict, job: dict) -> float:
    """0.0-1.0. Best (max, not average — one clearly relevant role shouldn't
    be diluted by unrelated ones on the same CV) match across the
    candidate's work_history, blending job-title similarity with overlap
    between that stint's tools/skills and the job's required+nice-to-have
    skills."""
    work_history = candidate.get("work_history") or []
    if not work_history:
        return 0.0

    job_skill_names = {
        _normalize(s["name"])
        for s in (
            (job.get("mandatory_requirements") or {}).get("skills", [])
            + (job.get("nice_to_have") or {}).get("skills", [])
        )
        if s.get("name")
    }
    title = (job.get("title") or "").strip().lower()

    best = 0.0
    for stint in work_history:
        role = (stint.get("role") or "").strip().lower()
        title_similarity = SequenceMatcher(None, role, title).ratio() if role and title else 0.0
        if job_skill_names:
            stint_skills = {_normalize(s) for s in stint.get("skills") or [] if s}
            skills_overlap = len(stint_skills & job_skill_names) / len(job_skill_names)
            composite = 0.5 * title_similarity + 0.5 * skills_overlap
        else:
            composite = title_similarity
        best = max(best, composite)
    return best


def _achievements_relevance(candidate: dict, job: dict) -> float:
    """0.0-1.0. Fraction of the job's skill/category vocabulary that shows
    up (word-boundary match) somewhere across the candidate's achievements
    and projects."""
    job_terms = _job_keyword_terms(job)
    if not job_terms:
        return 0.0

    achievements = candidate.get("achievements") or {}
    texts = (
        achievements.get("career_highlights", [])
        + achievements.get("academic_distinctions", [])
        + achievements.get("awards_and_competitions", [])
        + achievements.get("projects_and_open_source", [])
    )
    if not texts:
        return 0.0

    text_blob = " ".join(t for t in texts if t).lower()
    matched = sum(1 for term in job_terms if _term_in_text(term, text_blob))
    return matched / len(job_terms)


def _deterministic_fallback_evaluation(candidate: dict, job: dict) -> CandidateEvaluation:
    """Safety net used only when _llm_evaluate can't produce a result
    (missing/invalid API key, network error, unparseable response) — see
    score_match. Blends the same category of signals the LLM is asked to
    judge (nice-to-have skills/industries, certifications, relevant past
    experience, achievements/projects) into [0.6, 1.0] via a plain weighted
    formula, so it's directly comparable to the LLM's output — but the
    formula itself (the weights below) never appears in `factors`: that text
    only names *which* signals were positive, exactly like the LLM is
    instructed to do, since a manager reading it shouldn't be able to tell
    which path produced the score from its wording alone."""
    nice_to_have = job.get("nice_to_have") or {}
    candidate_skill_names = {_normalize(s["name"]) for s in candidate.get("skills", []) if s.get("name")}
    candidate_industries = {
        (w.get("company_industry") or "").strip().lower()
        for w in candidate.get("work_history", [])
        if w.get("company_industry")
    }

    skill_fraction = 0.0
    weighted_skills = nice_to_have.get("skills") or []
    if weighted_skills:
        total_weight = sum(s.get("weight") or 0 for s in weighted_skills) or 1
        matched_weight = sum(
            s.get("weight") or 0
            for s in weighted_skills
            if s.get("name") and _normalize(s["name"]) in candidate_skill_names
        )
        skill_fraction = matched_weight / total_weight

    industry_fraction = 0.0
    preferred_industries = nice_to_have.get("preferred_industries") or []
    if preferred_industries:
        matched = sum(1 for i in preferred_industries if (i or "").strip().lower() in candidate_industries)
        industry_fraction = matched / len(preferred_industries)

    cert_fraction = _certification_relevance(candidate, job)
    experience_fraction = _experience_relevance(candidate, job)
    achievements_fraction = _achievements_relevance(candidate, job)

    blended = (
        0.35 * skill_fraction
        + 0.10 * industry_fraction
        + 0.15 * cert_fraction
        + 0.25 * experience_fraction
        + 0.15 * achievements_fraction
    )
    confidence = round(0.6 + 0.4 * min(1.0, blended), 4)

    contributing = []
    if skill_fraction > 0:
        contributing.append("matching nice-to-have skills")
    if cert_fraction > 0:
        contributing.append("relevant certifications")
    if experience_fraction > 0:
        contributing.append("similar past work experience")
    if achievements_fraction > 0:
        contributing.append("relevant achievements or projects")
    if industry_fraction > 0:
        contributing.append("a matching industry background")

    if contributing:
        justification = (
            "Fallback evaluation (the AI evaluator was unavailable) — "
            + ", ".join(contributing)
            + " were the main positive factors for this candidate."
        )
    else:
        justification = (
            "Fallback evaluation (the AI evaluator was unavailable) — the candidate met every "
            "mandatory requirement, but no additional nice-to-have skills, certifications, "
            "relevant experience, or achievements stood out for this role."
        )

    return CandidateEvaluation(confidence=confidence, factors=justification)


def _build_evaluation_prompt(candidate: dict, job: dict, satisfied: int, total: int) -> tuple[str, str]:
    """(system, user) messages for the post-mandatory-gate LLM evaluation."""
    system = (
        "You are evaluating a job candidate who has ALREADY been confirmed, by a separate "
        f"deterministic check, to meet all {total} of this job's mandatory requirements "
        "(minimum/maximum years of experience, required education, required languages, and "
        "required skills) — do not re-evaluate or second-guess those; treat them as settled.\n\n"
        "Your job is to score how well the candidate's ADDITIONAL qualities fit this specific "
        "role: nice-to-have skills, certifications, preferred industries, achievements (career "
        "highlights, academic distinctions, awards, projects/open-source work), and how "
        "relevant their past and current work experience (job titles, tools and skills actually "
        "used) is to this role.\n\n"
        "Return ONLY a JSON object with this exact shape — no prose, no markdown fences:\n"
        '{"confidence": <float between 0.6 and 1.0>, "factors": "<a short, plain-language '
        'reason a hiring manager would understand>"}\n\n'
        "Rules:\n"
        "- confidence must be between 0.6 and 1.0 (the candidate already qualifies; you are "
        "scoring how strong a match they are beyond the minimum bar, not whether they qualify "
        "at all).\n"
        '- factors must read as a natural reason, e.g. "Strong hands-on Tableau and SQL '
        "experience directly matches the role's core tools, and their e-commerce analytics "
        'background fits the industry well." NEVER describe it as a formula, list weights, '
        'percentages, or per-criterion scores (no "0.2 x certification", no "skill_bonus=0.15", '
        "no itemized breakdown) — just the reason, in plain language.\n"
    )

    mandatory = job.get("mandatory_requirements") or {}
    job_summary = {
        "title": job.get("title"),
        "job_category": job.get("job_category"),
        "seniority_level": job.get("seniority_level"),
        "mandatory_requirements_already_confirmed_met": {
            "min_years_total_experience": mandatory.get("min_years_total_experience"),
            "max_years_total_experience": mandatory.get("max_years_total_experience"),
            "education": mandatory.get("education", []),
            "skills": mandatory.get("skills", []),
            "languages": mandatory.get("languages", []),
        },
        "nice_to_have": job.get("nice_to_have") or {},
    }
    candidate_summary = {
        "skills": candidate.get("skills", []),
        "education": candidate.get("education", []),
        "work_history": candidate.get("work_history", []),
        "certifications": candidate.get("certifications", []),
        "achievements": candidate.get("achievements") or {},
    }
    user = json.dumps({"job": job_summary, "candidate": candidate_summary}, ensure_ascii=False)
    return system, user


def _llm_evaluate(candidate: dict, job: dict, satisfied: int, total: int) -> CandidateEvaluation | None:
    """Calls out to OpenRouter (graph/llm_client.py) for the post-mandatory
    evaluation. Never raises — every failure (missing API key, network
    error, malformed/unvalidatable response) returns None, and the caller
    (score_match) falls back to _deterministic_fallback_evaluation."""
    system, user = _build_evaluation_prompt(candidate, job, satisfied, total)
    data = complete_json(system, user)
    if data is None:
        return None
    try:
        evaluation = CandidateEvaluation.model_validate(data)
    except Exception as exc:  # noqa: BLE001 — a malformed field must not fail scoring
        logger.warning("llm evaluation: response failed validation — %s", exc)
        return None
    # Belt-and-braces: the prompt already asks for [0.6, 1.0], but the model
    # isn't guaranteed to follow it exactly.
    evaluation.confidence = max(0.6, min(1.0, evaluation.confidence))
    return evaluation


def score_match(session, candidate: dict, job: dict) -> tuple[float, dict]:
    """Confidence + an explainable factors breakdown, for every application —
    whether or not the candidate clears the mandatory gate. Two regimes:

    * Mandatory not fully met: confidence is `mandatory_fraction * 0.5`, i.e.
      always below 0.6 — "did not meet every mandatory requirement" is
      always visibly distinguishable from "met them all," while still
      rewarding a near-miss (e.g. 3 of 4 requirements satisfied) over a
      candidate who matches nothing. No LLM call happens in this branch;
      `justification` is a plain factual sentence (satisfied/total count),
      not a judgment call, so it doesn't need one.
    * All mandatory requirements met: `_llm_evaluate` sends the candidate's
      and job's JSON to an LLM (OpenRouter) and asks it to score confidence
      in [0.6, 1.0] plus a plain-language reason, based on nice-to-have
      skills/certifications/industries, achievements, and relevant past
      experience — a qualitative judgment, not a hard-coded formula. Any
      failure falls back to `_deterministic_fallback_evaluation`, the same
      category of signals scored with a plain weighted formula whose
      weights never surface in the output text.

    Heuristic v1 — not tuned against real judgment yet.
    """
    satisfied, total = mandatory_fit(session, candidate, job)
    mandatory_fraction = 1.0 if total == 0 else satisfied / total
    mandatory_met = mandatory_fraction >= 1.0

    factors: dict = {
        "mandatory_met": mandatory_met,
        "mandatory_requirements_satisfied": satisfied,
        "mandatory_requirements_total": total,
    }

    if not mandatory_met:
        confidence = round(mandatory_fraction * 0.5, 4)
        factors["justification"] = (
            f"Did not meet all of this role's mandatory requirements "
            f"({satisfied} of {total} met)."
        )
        return confidence, factors

    evaluation = _llm_evaluate(candidate, job, satisfied, total)
    source = "llm"
    if evaluation is None:
        evaluation = _deterministic_fallback_evaluation(candidate, job)
        source = "fallback"

    factors["justification"] = evaluation.factors
    factors["evaluation_source"] = source
    confidence = round(evaluation.confidence, 4)
    return confidence, factors
