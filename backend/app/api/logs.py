from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Cluster
from app.schemas import LogEntryRead, LogLevel, LogSource, LogsResponse
from app.services.cluster_config import load_cluster_docker_hosts
from app.services.docker_logs import (
    fetch_cluster_logs,
    suppress_etcd_peer_noise,
)
from app.services.logs_filter import filter_by_time_window, filter_log_entries, parse_range_datetime
from app.services.patroni import PatroniDiscoveryError, fetch_cluster_members

router = APIRouter(prefix="/clusters", tags=["logs"])

ALL_SOURCES: list[LogSource] = ["patroni", "postgres", "etcd", "os"]
ALL_LEVELS: list[LogLevel] = ["critical", "warning", "info"]


@router.get("/{cluster_id}/logs", response_model=LogsResponse)
async def get_cluster_logs(
    cluster_id: str,
    node: str = Query(default="all"),
    severity: str = Query(default="critical,warning,info"),
    patroni: str = Query(default="include"),
    postgres: str = Query(default="include"),
    etcd: str = Query(default="include"),
    os_log: str = Query(default="include", alias="os"),
    search: str = Query(default=""),
    lines: int = Query(default=80, ge=10, le=500),
    hours: float | None = Query(default=None, ge=1, le=720),
    range_from: str | None = Query(default=None, description="ISO datetime lower bound (inclusive)"),
    range_to: str | None = Query(default=None, description="ISO datetime upper bound (inclusive)"),
    suppress_peer_noise: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
) -> LogsResponse:
    result = await session.execute(
        select(Cluster).where(Cluster.id == cluster_id).options(selectinload(Cluster.nodes))
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    docker_hosts = load_cluster_docker_hosts(cluster_id)
    if not docker_hosts:
        raise HTTPException(
            status_code=400,
            detail="No docker_hosts mapping in config/docker-clusters.yaml for this cluster",
        )

    level_set = [lv.strip() for lv in severity.split(",") if lv.strip()]
    levels: list[LogLevel] = [lv for lv in ALL_LEVELS if not level_set or lv in level_set]

    source_modes: dict[LogSource, str] = {
        "patroni": patroni,
        "postgres": postgres,
        "etcd": etcd,
        "os": os_log,
    }
    active_sources = [s for s in ALL_SOURCES if source_modes.get(s) != "exclude"]

    node_payload = [
        {"host": n.host, "member_name": n.member_name}
        for n in cluster.nodes
    ]
    if not node_payload:
        raise HTTPException(status_code=400, detail="No nodes in cluster — run discover first")

    down_hosts: set[str] = set()
    if suppress_peer_noise:
        for n in cluster.nodes:
            if n.role == "unreachable":
                down_hosts.add(n.host)
        try:
            _, members = await fetch_cluster_members(cluster.patroni_seed_url)
            seen = {str(m.get("host") or "") for m in members}
            down_hosts |= {h for h in docker_hosts if h not in seen}
        except PatroniDiscoveryError:
            pass

    try:
        raw = await fetch_cluster_logs(node_payload, docker_hosts, active_sources, lines)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Log fetch failed: {exc}") from exc
    peer_filtered = 0
    if suppress_peer_noise and down_hosts:
        before = len(raw)
        raw = suppress_etcd_peer_noise(raw, down_hosts)
        peer_filtered = before - len(raw)
    filtered = filter_log_entries(raw, node, levels, source_modes, search)
    rf = parse_range_datetime(range_from)
    rt = parse_range_datetime(range_to)
    if rf is not None or rt is not None:
        filtered = filter_by_time_window(filtered, range_from=rf, range_to=rt)
    elif hours is not None:
        filtered = filter_by_time_window(filtered, hours=hours)

    return LogsResponse(
        cluster_id=cluster_id,
        count=len(filtered),
        peer_noise_filtered=peer_filtered,
        lines=[
            LogEntryRead(
                ts=e.ts,
                node=e.node,
                member_name=e.member_name,
                source=e.source,
                level=e.level,
                message=e.message,
            )
            for e in filtered
        ],
        fetched_at=datetime.now(UTC),
    )
