"""Dashboard aggregations.

Everything is computed on demand with `$facet` pipelines over `applications` —
no rollup collection. One round trip returns the tiles, the time series, and
the funnel. If this ever slows down past ~100k documents, the fix is a nightly
rollup; adding one now would be premature.
"""

from datetime import UTC, datetime, timedelta

from beanie import PydanticObjectId

from app.models.application import Application
from app.models.enums import PipelineStage
from app.models.job import Job, JobStatus
from app.schemas.analytics import (
    CandidateAnalyticsOut,
    ManagerAnalyticsOut,
    RatePoint,
    StageCount,
    TimePoint,
)

WINDOW_DAYS = 30


def _day_keys(days: int = WINDOW_DAYS) -> list[str]:
    today = datetime.now(UTC).date()
    return [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]


def _densify(rows: list[dict], days: int = WINDOW_DAYS) -> list[TimePoint]:
    """Fill missing days with zero so the chart has no gaps in its x-axis."""
    found = {r["_id"]: r["count"] for r in rows}
    return [TimePoint(date=d, value=found.get(d, 0)) for d in _day_keys(days)]


def _window_start(days: int = WINDOW_DAYS) -> datetime:
    return datetime.now(UTC) - timedelta(days=days - 1)


_DAY_GROUP = {
    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$applied_at"}},
    "count": {"$sum": 1},
}


async def candidate_analytics(candidate_id: PydanticObjectId) -> CandidateAnalyticsOut:
    pipeline = [
        {"$match": {"candidate_id": candidate_id}},
        {
            "$facet": {
                "totals": [{"$count": "n"}],
                "shortlisted": [{"$match": {"is_shortlisted": True}}, {"$count": "n"}],
                "by_stage": [{"$group": {"_id": "$stage", "count": {"$sum": 1}}}],
                "over_time": [
                    {"$match": {"applied_at": {"$gte": _window_start()}}},
                    {"$group": _DAY_GROUP},
                    {"$sort": {"_id": 1}},
                ],
                "daily_success": [
                    {"$match": {"applied_at": {"$gte": _window_start()}}},
                    {
                        "$group": {
                            "_id": {
                                "$dateToString": {
                                    "format": "%Y-%m-%d",
                                    "date": "$applied_at",
                                }
                            },
                            "total": {"$sum": 1},
                            "shortlisted": {
                                "$sum": {"$cond": ["$is_shortlisted", 1, 0]}
                            },
                        }
                    },
                    {"$sort": {"_id": 1}},
                ],
            }
        },
    ]

    result = await Application.aggregate(pipeline).to_list()
    facets = result[0] if result else {}

    total = _first_count(facets.get("totals"))
    shortlisted = _first_count(facets.get("shortlisted"))
    stage_counts = {r["_id"]: r["count"] for r in facets.get("by_stage", [])}

    return CandidateAnalyticsOut(
        jobs_applied=total,
        shortlisted=shortlisted,
        in_interview=stage_counts.get(PipelineStage.INTERVIEW.value, 0),
        offers=stage_counts.get(PipelineStage.OFFER.value, 0)
        + stage_counts.get(PipelineStage.HIRED.value, 0),
        success_rate=round(shortlisted / total * 100, 1) if total else 0.0,
        applications_over_time=_densify(facets.get("over_time", [])),
        success_rate_trend=_cumulative_rate(facets.get("daily_success", [])),
        stage_breakdown=[
            StageCount(stage=stage, count=stage_counts.get(stage, 0))
            for stage in (s.value for s in PipelineStage)
        ],
    )


def _cumulative_rate(rows: list[dict]) -> list[RatePoint]:
    """Running shortlist rate — a per-day rate on low volume is pure noise."""
    by_day = {r["_id"]: (r["total"], r["shortlisted"]) for r in rows}
    points: list[RatePoint] = []
    total = shortlisted = 0
    for day in _day_keys():
        t, s = by_day.get(day, (0, 0))
        total += t
        shortlisted += s
        points.append(
            RatePoint(date=day, value=round(shortlisted / total * 100, 1) if total else 0.0)
        )
    return points


def _first_count(rows: list[dict] | None) -> int:
    return rows[0]["n"] if rows else 0


async def manager_analytics() -> ManagerAnalyticsOut:
    pipeline = [
        {
            "$facet": {
                "totals": [{"$count": "n"}],
                "shortlisted": [{"$match": {"is_shortlisted": True}}, {"$count": "n"}],
                "hired": [
                    {"$match": {"stage": PipelineStage.HIRED.value}},
                    {"$count": "n"},
                ],
                "by_stage": [{"$group": {"_id": "$stage", "count": {"$sum": 1}}}],
                "over_time": [
                    {"$match": {"applied_at": {"$gte": _window_start()}}},
                    {"$group": _DAY_GROUP},
                    {"$sort": {"_id": 1}},
                ],
            }
        }
    ]

    result = await Application.aggregate(pipeline).to_list()
    facets = result[0] if result else {}

    total = _first_count(facets.get("totals"))
    shortlisted = _first_count(facets.get("shortlisted"))
    hired = _first_count(facets.get("hired"))
    stage_counts = {r["_id"]: r["count"] for r in facets.get("by_stage", [])}

    open_jobs = await Job.find(Job.status == JobStatus.PUBLISHED).count()

    top = (
        await Job.find(Job.status != JobStatus.ARCHIVED)
        .sort("-stats.applications")
        .limit(5)
        .to_list()
    )

    return ManagerAnalyticsOut(
        open_jobs=open_jobs,
        total_applications=total,
        shortlisted=shortlisted,
        hired=hired,
        conversion_rate=round(hired / total * 100, 1) if total else 0.0,
        applications_over_time=_densify(facets.get("over_time", [])),
        funnel=[
            StageCount(stage=stage.value, count=stage_counts.get(stage.value, 0))
            for stage in (
                PipelineStage.APPLIED,
                PipelineStage.SCREENING,
                PipelineStage.INTERVIEW,
                PipelineStage.OFFER,
                PipelineStage.HIRED,
            )
        ],
        top_jobs=[
            {
                "id": str(j.id),
                "title": j.title,
                "applications": j.stats.applications,
                "shortlisted": j.stats.shortlisted,
                "status": j.status.value,
            }
            for j in top
        ],
    )
