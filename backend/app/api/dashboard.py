from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas import DashboardIssueRead, DashboardIssuesResponse
from app.services.dashboard_issues import collect_all_issues, sort_issues

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/issues", response_model=DashboardIssuesResponse)
async def get_dashboard_issues(
    session: AsyncSession = Depends(get_session),
) -> DashboardIssuesResponse:
    sorted_issues = await collect_all_issues(session)
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
