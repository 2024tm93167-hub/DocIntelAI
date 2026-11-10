"""Metrics endpoint for evaluation instrumentation.

Provides aggregated latency statistics (p50/p95) per endpoint and recent
request records. Requires authentication; only accessible to logged-in users.
"""
from fastapi import APIRouter, Depends, Query

from app.api.deps import AuthenticatedUser, get_current_user
from app.services.metrics_collector import metrics_collector

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/summary")
def get_metrics_summary(current_user: AuthenticatedUser = Depends(get_current_user)) -> dict:
    """Return per-endpoint p50/p95 latency and request counts."""
    return metrics_collector.get_summary()


@router.get("/recent")
def get_recent_metrics(
    limit: int = Query(default=100, ge=1, le=1000),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[dict]:
    """Return the most recent request records."""
    return metrics_collector.get_recent(limit=limit)


@router.post("/reset", status_code=204)
def reset_metrics(current_user: AuthenticatedUser = Depends(get_current_user)) -> None:
    """Clear all collected metrics. Useful before running a benchmark."""
    metrics_collector.reset()
