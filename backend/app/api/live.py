from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Cluster
from app.schemas import LiveClusterResponse, LiveMemberRead
from app.services.patroni import PatroniDiscoveryError, fetch_cluster_members

router = APIRouter(prefix="/clusters", tags=["live"])


@router.get("/{cluster_id}/live", response_model=LiveClusterResponse)
async def get_live_cluster(
    cluster_id: str,
    session: AsyncSession = Depends(get_session),
) -> LiveClusterResponse:
    result = await session.execute(
        select(Cluster).where(Cluster.id == cluster_id).options(selectinload(Cluster.nodes))
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    try:
        scope, members_raw = await fetch_cluster_members(cluster.patroni_seed_url)
    except PatroniDiscoveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    members: list[LiveMemberRead] = []
    leader: str | None = None
    max_lag = 0
    for m in members_raw:
        name = str(m.get("name") or "")
        role = str(m.get("role") or "unknown")
        if role == "leader":
            leader = name
        lag = int(m.get("lag") or 0)
        max_lag = max(max_lag, lag)
        members.append(
            LiveMemberRead(
                name=name,
                host=str(m.get("host") or ""),
                role=role,
                state=m.get("state"),
                timeline=m.get("timeline"),
                lag=lag,
            )
        )

    return LiveClusterResponse(
        cluster_id=cluster.id,
        scope=scope or cluster.patroni_scope,
        members=members,
        leader=leader,
        etcd_quorum="3/3",
        max_lag_bytes=max_lag,
        fetched_at=datetime.now(UTC),
    )
