"""CLI for loading candidate/job documents into the Neo4j hiring graph.

Usage:
    python -m graph.main --init-schema
    python -m graph.main --load-taxonomy
    python -m graph.main --candidates candidates.json
    python -m graph.main --jobs jobs.json --company-id comp_5541
    python -m graph.main --reset --init-schema --candidates c.json --jobs j.json --company-id comp_5541
    python -m graph.main --sync-pending
    python -m graph.main --process-pending
    python -m graph.main --watch

candidates.json / jobs.json may contain either a single object or a JSON
array of objects, each matching the platform's candidate/job schema.
jobs.json never carries company_id itself — a job's owning company is
always supplied by the caller (here, --company-id), the same way it would
come from an authenticated company's session in the real app.

Every invocation auto-bootstraps the constraints + static skills taxonomy
(_ensure_taxonomy) if the database looks taxonomy-less — a fresh database,
or one just wiped by --reset — so nobody has to remember to run
--init-schema --load-taxonomy by hand before the first real use. A no-op,
one cheap count query, once the taxonomy is already loaded. --load-taxonomy
still exists for an explicit/forced reload (e.g. after editing
graph/skills_taxonomy.py's content).

--sync-pending, --process-pending and --watch all pull from the live
Matchify graph-export API (graph/api_client.py, configured via
MATCHIFY_API_BASE_URL / MATCHIFY_API_TOKEN in .env), walking the AI team's
scoring queue (GET /graph/applications?match_status=pending):

  --sync-pending      ingests the candidate/job behind every pending
                       application and leaves them in the graph — for ad hoc
                       inspection (graph/pending_sync.py).
  --process-pending   the production pipeline: for each pending application,
                       ingest -> check the job's mandatory requirements
                       against the candidate -> if they all pass, POST a
                       confidence score back to
                       /applications/{id}/match -> wipe the graph back down
                       to the taxonomy -> next item (graph/match_pipeline.py).
                       Runs once and exits.
  --watch             runs --process-pending in a loop, once every 60s,
                       until interrupted (Ctrl+C).
"""

import argparse
import json
import time

from graph.constraints import apply_constraints
from graph.db import close_driver, get_session, verify_connectivity
from graph.ingest import add_candidates, add_jobs
from graph.match_pipeline import process_pending
from graph.pending_sync import sync_pending
from graph.reset import wipe_database
from graph.skills_taxonomy import apply_taxonomy

_WATCH_INTERVAL_SECONDS = 60


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else [data]


def _ensure_taxonomy(session) -> None:
    """Bootstraps constraints + the static skills taxonomy the first time
    they're missing (a fresh database, or right after --reset) — every
    graph.main invocation checks this cheaply, so the taxonomy (and the
    IMPLIES/CROSS_LINKS reasoning matching depends on) is always there
    without anyone having to remember --init-schema --load-taxonomy first.
    A single count query and a no-op once the taxonomy already exists."""
    result = session.run("MATCH (c:Category) RETURN count(c) > 0 AS present").single()
    if result and result["present"]:
        return
    print("No taxonomy found — bootstrapping constraints + skills taxonomy...")
    apply_constraints(session)
    apply_taxonomy(session)
    print("Taxonomy bootstrapped.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--init-schema",
        action="store_true",
        help="create uniqueness constraints (safe to re-run)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="DELETE ALL nodes/relationships in the database before loading anything else",
    )
    parser.add_argument(
        "--load-taxonomy",
        action="store_true",
        help="load the reference Category/SubCategory/Skill taxonomy (graph/skills_taxonomy.py)",
    )
    parser.add_argument("--candidates", help="path to a candidate JSON file")
    parser.add_argument("--jobs", help="path to a job JSON file")
    parser.add_argument(
        "--company-id",
        help="company_id that owns the jobs in --jobs (required together with --jobs)",
    )
    parser.add_argument(
        "--sync-pending",
        action="store_true",
        help="fetch pending applications from the graph-export API and ingest the candidate/job each one points at",
    )
    parser.add_argument(
        "--process-pending",
        action="store_true",
        help="run one cycle of the match pipeline: ingest, mandatory-match, write back, clean up (graph/match_pipeline.py)",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help=f"run --process-pending in a loop every {_WATCH_INTERVAL_SECONDS}s until Ctrl+C",
    )
    args = parser.parse_args()
    if args.jobs and not args.company_id:
        parser.error("--jobs requires --company-id")
    if args.watch and args.process_pending:
        parser.error("--watch already loops --process-pending; pass just one")

    verify_connectivity()
    print("Connected to Neo4j.")

    if args.watch:
        with get_session() as session:
            _ensure_taxonomy(session)
        _watch()
        close_driver()
        return

    with get_session() as session:
        if args.reset:
            wipe_database(session)
            print("Database wiped.")

        if args.init_schema:
            apply_constraints(session)
            print("Constraints applied.")

        if args.load_taxonomy:
            apply_taxonomy(session)
            print("Skills taxonomy loaded.")

        _ensure_taxonomy(session)

        if args.jobs:
            add_jobs(session, _load_json(args.jobs), args.company_id)
            print(f"Loaded jobs from {args.jobs} for company {args.company_id}.")

        if args.candidates:
            add_candidates(session, _load_json(args.candidates))
            print(f"Loaded candidates from {args.candidates}.")

        if args.sync_pending:
            result = sync_pending(session)
            print(
                f"Synced {result['applications']} pending application(s): "
                f"{result['candidates']} candidate(s), {result['jobs']} job(s) ingested."
            )

        if args.process_pending:
            result = process_pending(session)
            _print_process_result(result)

    close_driver()


def _print_process_result(result: dict) -> None:
    print(
        f"Processed {result['applications']} pending application(s): "
        f"{result['scored']} scored, {result['failed']} failed."
    )


def _watch() -> None:
    print(f"Watching for pending applications every {_WATCH_INTERVAL_SECONDS}s. Ctrl+C to stop.")
    try:
        while True:
            with get_session() as session:
                result = process_pending(session)
            _print_process_result(result)
            time.sleep(_WATCH_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
