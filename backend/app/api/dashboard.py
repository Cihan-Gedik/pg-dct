from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas import DashboardIssueRead, DashboardIssuesResponse
from app.services.dashboard_issues import collect_all_issues
from app.services.docker_logs import parse_log_timestamp

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _issue_within_hours(issue: dict, hours: float) -> bool:
    """Cluster alerts without ts are current state; log rows must fall in the window."""
    if issue.get("kind") == "cluster" and not issue.get("ts") and not issue.get("last_seen"):
        return True
    raw = issue.get("last_seen") or issue.get("ts")
    if not raw:
        return False
    dt = parse_log_timestamp(str(raw))
    if dt is None:
        return False
    return dt >= datetime.now(UTC) - timedelta(hours=hours)


@router.get("/issues", response_model=DashboardIssuesResponse)
async def get_dashboard_issues(
    hours: float | None = Query(default=None, ge=1, le=720),
    session: AsyncSession = Depends(get_session),
) -> DashboardIssuesResponse:
    sorted_issues = await collect_all_issues(session)
    if hours is not None:
        sorted_issues = [i for i in sorted_issues if _issue_within_hours(i, hours)]
    critical_count = sum(
        int(i.get("occurrence_count", 1)) for i in sorted_issues if i["level"] == "critical"
    )
    warning_count = sum(
        int(i.get("occurrence_count", 1)) for i in sorted_issues if i["level"] == "warning"
    )
    return DashboardIssuesResponse(
        critical_count=critical_count,
        warning_count=warning_count,
        issues=[DashboardIssueRead(**item) for item in sorted_issues],
        fetched_at=datetime.now(UTC),
    )
