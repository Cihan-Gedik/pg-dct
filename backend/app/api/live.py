from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Cluster
from app.schemas import DcsStatusRead, EtcdMemberRead, LiveClusterResponse, LiveMemberRead
from app.services.cluster_config import load_cluster_docker_hosts
from app.services.etcd_status import fetch_etcd_cluster_status
from app.services.live_sync import (
    build_alerts,
    check_docker_hosts_health,
    merge_missing_members,
    parse_patroni_history,
    sync_cluster_nodes,
)
from app.services.patroni import (
    PatroniDiscoveryError,
    fetch_cluster_members,
    fetch_patroni_history,
    member_lag_bytes,
    member_timeline,
)

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
        history = await fetch_patroni_history(cluster.patroni_seed_url)
    except PatroniDiscoveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    switchover_total, times_as_leader = parse_patroni_history(history)
    docker_hosts = load_cluster_docker_hosts(cluster_id)
    host_to_container = {host: name for host, name in docker_hosts.items()}
    container_health = await check_docker_hosts_health(docker_hosts) if docker_hosts else {}

    host_to_member = {n.host: n.member_name for n in cluster.nodes}
    members_merged = merge_missing_members(
        members_raw, docker_hosts, host_to_member, times_as_leader
    )
    alerts = build_alerts(members_merged, docker_hosts, container_health)

    await sync_cluster_nodes(session, cluster, members_raw)

    members: list[LiveMemberRead] = []
    leader: str | None = None
    max_lag = 0
    active = 0

    for m in members_merged:
        name = str(m.get("name") or "")
        role = str(m.get("role") or "unknown")
        host = str(m.get("host") or "")
        if role == "leader":
            leader = name
        if role in ("leader", "replica") and m.get("state") not in ("down", "crashed"):
            active += 1
        lag = member_lag_bytes(m) if m.get("lag") is not None else 0
        max_lag = max(max_lag, lag)
        container = host_to_container.get(host)
        members.append(
            LiveMemberRead(
                name=name,
                host=host,
                role=role,
                state=str(m["state"]) if m.get("state") is not None else None,
                timeline=member_timeline(m),
                lag=lag if role == "replica" else None,
                switchover_count=times_as_leader.get(name, 0),
                container=container,
                container_running=container_health.get(container) if container else None,
            )
        )

    expected = len(docker_hosts) or len(members)
    quorum_ok = active >= (expected // 2 + 1) if expected else bool(active)
    patroni_quorum = f"{active}/{expected}" if expected else f"{active}/?"

    leader_host = next((m.host for m in members if m.name == leader), None)
    failover_candidates = sorted(
        m.name for m in members if m.role == "replica" and m.state not in ("down", "crashed")
    )

    preferred_container = next((m.container for m in members if m.name == leader and m.container), None)
    etcd_raw = (
        await fetch_etcd_cluster_status(docker_hosts, container_health, preferred_container)
        if docker_hosts
        else None
    )

    etcd_members: list[EtcdMemberRead] = []
    etcd_quorum = patroni_quorum
    dcs: DcsStatusRead | None = None

    if etcd_raw:
        etcd_members = [EtcdMemberRead(**row) for row in etcd_raw["members"]]
        etcd_quorum = str(etcd_raw["quorum"])
        if etcd_raw["healthy_count"] < (etcd_raw["total_count"] // 2 + 1):
            etcd_quorum = f"{etcd_quorum} (degraded)"
        dcs = DcsStatusRead(
            patroni_leader=leader,
            patroni_leader_host=leader_host,
            failover_candidates=failover_candidates,
            etcd_raft_leader=etcd_raw.get("leader_name"),
            etcd_raft_leader_id=etcd_raw.get("leader_id"),
            etcd_cluster_id=etcd_raw.get("cluster_id"),
            etcd_raft_term=etcd_raw.get("raft_term"),
        )
    else:
        dcs = DcsStatusRead(
            patroni_leader=leader,
            patroni_leader_host=leader_host,
            failover_candidates=failover_candidates,
        )
        etcd_quorum = patroni_quorum if quorum_ok else f"{patroni_quorum} (degraded)"

    return LiveClusterResponse(
        cluster_id=cluster.id,
        scope=scope or cluster.patroni_scope,
        members=members,
        leader=leader,
        etcd_quorum=etcd_quorum,
        etcd_members=etcd_members,
        dcs=dcs,
        max_lag_bytes=max_lag,
        switchover_total=switchover_total,
        expected_nodes=expected,
        active_nodes=active,
        alerts=alerts,
        fetched_at=datetime.now(UTC),
    )
