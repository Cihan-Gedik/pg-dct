"""Sync Patroni live state to DB and derive health / switchover metrics."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Cluster, Node
from app.services.cluster_config import load_cluster_docker_hosts
from app.services.patroni import member_to_node_fields


def parse_patroni_history(history: Any) -> tuple[int, dict[str, int]]:
    """Return (leadership_changes, times_as_leader per member name)."""
    if not isinstance(history, list):
        return 0, {}

    leaders: list[str] = []
    times_as_leader: dict[str, int] = {}
    for row in history:
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            continue
        name = str(row[4])
        leaders.append(name)
        times_as_leader[name] = times_as_leader.get(name, 0) + 1

    changes = 0
    prev: str | None = None
    for name in leaders:
        if prev is not None and name != prev:
            changes += 1
        prev = name
    return changes, times_as_leader


async def docker_container_running(container: str) -> bool | None:
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "inspect",
        "-f",
        "{{.State.Running}}",
        container,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        return None
    return stdout.decode().strip().lower() == "true"


def build_alerts(
    members: list[dict[str, Any]],
    docker_hosts: dict[str, str],
    container_health: dict[str, bool | None],
) -> list[str]:
    alerts: list[str] = []
    host_to_member = {str(m.get("host") or ""): str(m.get("name") or "") for m in members}

    for m in members:
        if str(m.get("role") or "") == "unreachable":
            host = str(m.get("host") or "")
            alerts.append(
                f"Member {m.get('name')} ({host}) is not in Patroni /cluster — "
                f"etcd may log dial tcp {host}:2380: connection refused until the node recovers."
            )

    for host, container in docker_hosts.items():
        running = container_health.get(container)
        member = host_to_member.get(host) or container
        if running is False:
            alerts.append(
                f"Container {container} is stopped — member {member} ({host}) is down."
            )

    in_patroni = sum(1 for m in members if m.get("role") in ("leader", "replica"))
    if docker_hosts and in_patroni < len(docker_hosts):
        alerts.append(
            f"Patroni reports {in_patroni}/{len(docker_hosts)} nodes — quorum may be degraded."
        )
    return alerts


async def check_docker_hosts_health(docker_hosts: dict[str, str]) -> dict[str, bool | None]:
    tasks = {name: asyncio.create_task(docker_container_running(name)) for name in docker_hosts.values()}
    out: dict[str, bool | None] = {}
    for name, task in tasks.items():
        out[name] = await task
    return out


async def sync_cluster_nodes(
    session: AsyncSession,
    cluster: Cluster,
    members_raw: list[dict[str, Any]],
) -> None:
    by_name = {n.member_name: n for n in cluster.nodes}
    seen_hosts = {str(m.get("host") or "") for m in members_raw}
    seen_names: set[str] = set()

    for member in members_raw:
        fields = member_to_node_fields(member)
        name = fields["member_name"]
        seen_names.add(name)
        if name in by_name:
            node = by_name[name]
            for key, value in fields.items():
                setattr(node, key, value)
        else:
            session.add(Node(cluster_id=cluster.id, **fields))

    for node in cluster.nodes:
        if node.member_name in seen_names:
            continue
        if node.host in seen_hosts:
            continue
        node.role = "unreachable"
        node.state = "down"

    await session.commit()
    await session.refresh(cluster, ["nodes"])


def merge_missing_members(
    members_raw: list[dict[str, Any]],
    docker_hosts: dict[str, str],
    host_to_member: dict[str, str] | None = None,
    times_as_leader: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Add YAML nodes absent from Patroni (e.g. crashed etcd peer)."""
    seen_hosts = {str(m.get("host") or "") for m in members_raw}
    seen_names = {str(m.get("name") or "") for m in members_raw}
    merged = list(members_raw)
    known = host_to_member or {}
    history_only = [n for n in (times_as_leader or {}) if n not in seen_names]

    for host, container in docker_hosts.items():
        if host in seen_hosts:
            continue
        name = known.get(host)
        if not name and len(history_only) == 1:
            name = history_only[0]
        merged.append(
            {
                "name": name or container,
                "host": host,
                "role": "unreachable",
                "state": "down",
                "timeline": None,
                "lag": None,
            }
        )
    return merged
