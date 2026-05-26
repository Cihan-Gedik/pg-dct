"""Fetch etcd raft cluster status from Patroni lab containers."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from urllib.parse import urlparse

_HOST_RE = re.compile(r"(\d+\.\d+\.\d+\.\d+)")


def _host_from_url(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"http://{url}")
    if parsed.hostname:
        return parsed.hostname
    match = _HOST_RE.search(url)
    return match.group(1) if match else ""


def _member_id_str(raw: Any) -> str:
    try:
        return f"{int(raw):x}"
    except (TypeError, ValueError):
        return str(raw or "")


async def _docker_etcdctl(container: str, *args: str, timeout: float = 15.0) -> str:
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "exec",
        container,
        "etcdctl",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        return ""
    return (stdout or b"").decode("utf-8", errors="replace")


def parse_etcd_member_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    members = payload.get("members") or []
    rows: list[dict[str, Any]] = []
    for m in members:
        if not isinstance(m, dict):
            continue
        peer = str(m.get("peerURLs", [""])[0] if m.get("peerURLs") else "")
        client = str(m.get("clientURLs", [""])[0] if m.get("clientURLs") else "")
        rows.append(
            {
                "member_id": _member_id_str(m.get("ID")),
                "name": str(m.get("name") or ""),
                "host": _host_from_url(peer or client),
                "peer_url": peer,
                "client_url": client,
            }
        )
    return rows


def parse_etcd_endpoint_status(
    payload: list[Any],
    member_by_id: dict[str, dict[str, Any]],
) -> tuple[str | None, int, dict[str, str]]:
    """Return (raft_leader_name, healthy_count, member_id -> health state)."""
    leader_id: str | None = None
    healthy = 0
    health_by_id: dict[str, str] = {}

    for item in payload:
        if not isinstance(item, dict):
            continue
        status = item.get("Status")
        if not isinstance(status, dict):
            continue
        mid = _member_id_str(status.get("header", {}).get("member_id"))
        if leader_id is None:
            leader_id = _member_id_str(status.get("leader"))
        if mid:
            health_by_id[mid] = "up"
            healthy += 1

    leader_name = None
    if leader_id and leader_id in member_by_id:
        leader_name = member_by_id[leader_id].get("name")

    return leader_name, healthy, health_by_id


def build_etcd_members(
    member_rows: list[dict[str, Any]],
    leader_id: str | None,
    health_by_id: dict[str, str],
    docker_hosts: dict[str, str],
    container_health: dict[str, bool | None],
) -> list[dict[str, Any]]:
    host_to_container = {host: name for host, name in docker_hosts.items()}
    out: list[dict[str, Any]] = []
    for row in member_rows:
        mid = row["member_id"]
        is_leader = bool(leader_id and mid == leader_id)
        health = health_by_id.get(mid, "unknown")
        host = row.get("host") or ""
        container = host_to_container.get(host)
        running = container_health.get(container) if container else None
        if running is False:
            state = "down"
        elif health == "up":
            state = "started"
        else:
            state = "unreachable"
        out.append(
            {
                "name": row.get("name") or host or mid,
                "member_id": mid,
                "host": host,
                "role": "leader" if is_leader else "follower",
                "state": state,
                "client_url": row.get("client_url") or "",
                "peer_url": row.get("peer_url") or "",
                "container": container,
                "container_running": running,
            }
        )
    out.sort(key=lambda m: (0 if m["role"] == "leader" else 1, m["name"]))
    return out


async def fetch_etcd_cluster_status(
    docker_hosts: dict[str, str],
    container_health: dict[str, bool | None],
    preferred_container: str | None = None,
) -> dict[str, Any] | None:
    """Run etcdctl on a lab container; None if unavailable."""
    candidates: list[str] = []
    if preferred_container:
        candidates.append(preferred_container)
    for name in docker_hosts.values():
        if name not in candidates:
            candidates.append(name)

    container: str | None = None
    for name in candidates:
        running = container_health.get(name)
        if running is not False:
            container = name
            break
    if not container:
        return None

    members_raw = await _docker_etcdctl(container, "member", "list", "-w", "json")
    if not members_raw.strip():
        return None
    try:
        members_payload = json.loads(members_raw)
    except json.JSONDecodeError:
        return None

    member_rows = parse_etcd_member_list(members_payload)
    member_by_id = {r["member_id"]: r for r in member_rows}

    status_raw = await _docker_etcdctl(container, "endpoint", "status", "--cluster", "-w", "json")
    leader_name: str | None = None
    healthy = 0
    health_by_id: dict[str, str] = {}
    leader_id: str | None = None
    if status_raw.strip():
        try:
            status_payload = json.loads(status_raw)
            if isinstance(status_payload, list):
                leader_name, healthy, health_by_id = parse_etcd_endpoint_status(
                    status_payload, member_by_id
                )
                for item in status_payload:
                    if isinstance(item, dict) and isinstance(item.get("Status"), dict):
                        leader_id = _member_id_str(item["Status"].get("leader"))
                        break
        except json.JSONDecodeError:
            pass

    members = build_etcd_members(
        member_rows, leader_id, health_by_id, docker_hosts, container_health
    )
    total = len(members)
    quorum = f"{healthy}/{total}" if total else "0/0"

    return {
        "cluster_id": _member_id_str(members_payload.get("header", {}).get("cluster_id")),
        "raft_term": members_payload.get("header", {}).get("raft_term"),
        "leader_name": leader_name,
        "leader_id": leader_id,
        "members": members,
        "healthy_count": healthy,
        "total_count": total,
        "quorum": quorum,
    }
