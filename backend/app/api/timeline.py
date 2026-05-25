from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Cluster
from app.schemas import ClusterTimelineResponse, TimelineMemberRead, TimelineSegmentRead, TimelineSwitchRead
from app.services.patroni import PatroniDiscoveryError, fetch_cluster_members, fetch_patroni_history
from app.services.timeline import build_member_timeline, default_range

router = APIRouter(prefix="/clusters", tags=["timeline"])


@router.get("/{cluster_id}/timeline", response_model=ClusterTimelineResponse)
async def get_cluster_timeline(
    cluster_id: str,
    hours: int = Query(default=168, ge=1, le=2160, description="Lookback window in hours (max 90d)"),
    session: AsyncSession = Depends(get_session),
) -> ClusterTimelineResponse:
    result = await session.execute(
        select(Cluster).where(Cluster.id == cluster_id).options(selectinload(Cluster.nodes))
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    try:
        _scope, members_raw = await fetch_cluster_members(cluster.patroni_seed_url)
        history = await fetch_patroni_history(cluster.patroni_seed_url)
    except PatroniDiscoveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    current_leader = None
    member_names: list[str] = []
    for m in members_raw:
        name = str(m.get("name") or "")
        if name:
            member_names.append(name)
        if str(m.get("role") or "") == "leader":
            current_leader = name
    for n in cluster.nodes:
        if n.member_name not in member_names:
            member_names.append(n.member_name)

    range_start, range_end = default_range(hours)
    raw_members, raw_switches = build_member_timeline(
        history, member_names, range_start, range_end, current_leader
    )

    return ClusterTimelineResponse(
        cluster_id=cluster_id,
        range_start=range_start,
        range_end=range_end,
        current_leader=current_leader,
        members=[
            TimelineMemberRead(
                member=m["member"],
                segments=[TimelineSegmentRead(**s) for s in m["segments"]],
            )
            for m in raw_members
        ],
        switchovers=[TimelineSwitchRead(**s) for s in raw_switches],
        fetched_at=datetime.now(UTC),
    )
