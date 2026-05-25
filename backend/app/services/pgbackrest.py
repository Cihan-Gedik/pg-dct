"""Run pgBackRest in Patroni lab containers via docker exec."""

from __future__ import annotations

import json
from typing import Any

from app.services.cluster_config import load_cluster_docker_hosts, load_cluster_pgbackrest
from app.services.docker_logs import _docker_exec
from app.services.patroni import fetch_cluster_members


async def resolve_leader_container(
    patroni_seed_url: str,
    cluster_id: str,
) -> tuple[str | None, str | None, str | None]:
    """Return (container_name, member_name, host) for the Patroni leader."""
    docker_hosts = load_cluster_docker_hosts(cluster_id)
    if not docker_hosts:
        return None, None, None
    try:
        _scope, members = await fetch_cluster_members(patroni_seed_url)
    except Exception:
        return None, None, None
    leader = next(
        (m for m in members if str(m.get("role") or "").lower() in ("leader", "master")),
        None,
    )
    if not leader:
        leader = members[0] if members else None
    if not leader:
        return None, None, None
    host = str(leader.get("host") or "")
    container = docker_hosts.get(host)
    return container, str(leader.get("name") or ""), host


async def pgbackrest_info(
    patroni_seed_url: str,
    cluster_id: str,
    *,
    timeout: float = 45.0,
) -> dict[str, Any]:
    cfg = load_cluster_pgbackrest(cluster_id)
    container, member, host = await resolve_leader_container(patroni_seed_url, cluster_id)
    if not container:
        return {
            "ok": False,
            "error": "No docker_hosts mapping or leader not found",
            "container": None,
            "member": member,
            "host": host,
            "stanza": cfg.get("stanza") or "",
            "stanzas": [],
        }

    cmd = ["pgbackrest", "--output=json"]
    stanza = str(cfg.get("stanza") or "").strip()
    if stanza:
        cmd.append(f"--stanza={stanza}")
    cmd.append("info")

    raw = await _docker_exec(container, cmd, timeout=timeout)
    if not raw.strip():
        return {
            "ok": False,
            "error": "pgbackrest produced no output (binary missing?)",
            "container": container,
            "member": member,
            "host": host,
            "stanza": stanza,
            "stanzas": [],
            "stdout_tail": raw[-2000:] if raw else "",
        }

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error": "pgbackrest output was not valid JSON",
            "container": container,
            "member": member,
            "host": host,
            "stanza": stanza,
            "stanzas": [],
            "stdout_tail": raw[-2000:],
        }

    stanzas = payload if isinstance(payload, list) else []
    return {
        "ok": True,
        "error": None,
        "container": container,
        "member": member,
        "host": host,
        "stanza": stanza,
        "stanzas": stanzas,
    }


async def pgbackrest_run(
    patroni_seed_url: str,
    cluster_id: str,
    kind: str,
    *,
    stanza_override: str = "",
    timeout: float = 3600.0,
) -> dict[str, Any]:
    """Execute an allowlisted pgBackRest command on the leader container."""
    allowed: dict[str, list[str]] = {
        "backup_full": ["backup", "--type=full"],
        "backup_diff": ["backup", "--type=diff"],
        "backup_incr": ["backup", "--type=incr"],
        "check": ["check"],
        "stanza_create": ["stanza-create"],
    }
    if kind not in allowed:
        return {"ok": False, "error": f"Unsupported job kind: {kind}", "exit_code": None, "stdout_tail": ""}

    cfg = load_cluster_pgbackrest(cluster_id)
    container, member, host = await resolve_leader_container(patroni_seed_url, cluster_id)
    if not container:
        return {
            "ok": False,
            "error": "No docker_hosts mapping or leader not found",
            "exit_code": None,
            "stdout_tail": "",
            "container": None,
            "member": member,
        }

    stanza = (stanza_override or str(cfg.get("stanza") or "")).strip()
    cmd = ["pgbackrest", "--log-level-console=info"]
    if stanza:
        cmd.append(f"--stanza={stanza}")
    cmd.extend(allowed[kind])

    raw = await _docker_exec(container, cmd, timeout=timeout)
    # _docker_exec merges stderr into stdout; we cannot get exit code without subprocess change.
    # Treat presence of common error markers as failure heuristic.
    lower = raw.lower()
    failed = "error:" in lower and "completed successfully" not in lower
    return {
        "ok": not failed,
        "error": None if not failed else "pgbackrest reported errors (see stdout)",
        "exit_code": 0 if not failed else 1,
        "stdout_tail": raw[-8000:] if raw else "",
        "container": container,
        "member": member,
        "host": host,
        "kind": kind,
    }
