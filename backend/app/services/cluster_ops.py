"""Docker lab cluster lifecycle: start/stop nodes, Patroni switchover, proxy refresh."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.services.cluster_config import load_cluster_docker_hosts
from app.services.patroni import PatroniDiscoveryError, fetch_cluster_members

_REPO_ROOT = Path(__file__).resolve().parents[3]
_EXPOSE_SCRIPT = _REPO_ROOT / "scripts" / "expose-patroni-ports.sh"


def cluster_containers(cluster_id: str) -> dict[str, str]:
    """host IP -> docker container name."""
    return load_cluster_docker_hosts(cluster_id)


def resolve_container(cluster_id: str, node_ref: str) -> str | None:
    """Match container name, host IP, or Patroni member name."""
    ref = node_ref.strip()
    if not ref:
        return None
    hosts = cluster_containers(cluster_id)
    if ref in hosts.values():
        return ref
    if ref in hosts:
        return hosts[ref]
    for host, container in hosts.items():
        if ref in {host, container}:
            return container
    return None


async def _run_cmd(*args: str, timeout: float = 120.0) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        return 124, "timeout"
    text = (stdout or b"").decode("utf-8", errors="replace").strip()
    return proc.returncode or 0, text


async def docker_start_container(container: str) -> tuple[int, str]:
    return await _run_cmd("docker", "start", container, timeout=60)


async def docker_stop_container(container: str) -> tuple[int, str]:
    return await _run_cmd("docker", "stop", container, timeout=60)


async def heal_lab_node(container: str) -> tuple[int, str]:
    script = """
set -e
if systemctl is-active etcd >/dev/null 2>&1; then
  echo "etcd already active"
else
  systemctl start etcd
  echo "etcd started"
fi
sleep 2
if systemctl is-active patroni >/dev/null 2>&1; then
  echo "patroni already active"
else
  systemctl start patroni
  echo "patroni started"
fi
systemctl is-active etcd patroni
"""
    return await _run_cmd("docker", "exec", container, "bash", "-c", script, timeout=90)


async def refresh_patroni_proxies() -> tuple[int, str]:
    if not _EXPOSE_SCRIPT.is_file():
        return 1, f"Script not found: {_EXPOSE_SCRIPT}"
    return await _run_cmd("bash", str(_EXPOSE_SCRIPT), timeout=120)


def _pick_candidate(members: list[dict[str, Any]], leader_name: str, preferred: str | None) -> str | None:
    replicas = [
        str(m.get("name") or "")
        for m in members
        if str(m.get("role") or "").lower() == "replica" and str(m.get("name") or "") != leader_name
    ]
    if preferred:
        pref = preferred.strip()
        if pref in replicas:
            return pref
        raise ValueError(f"Candidate '{pref}' is not a running replica")
    return replicas[0] if replicas else None


async def patroni_switchover(
    seed_url: str,
    *,
    candidate: str | None = None,
) -> dict[str, Any]:
    try:
        _scope, members = await fetch_cluster_members(seed_url)
    except PatroniDiscoveryError as exc:
        return {"ok": False, "error": str(exc)}

    leader = next(
        (str(m.get("name") or "") for m in members if str(m.get("role") or "").lower() == "leader"),
        "",
    )
    if not leader:
        return {"ok": False, "error": "No Patroni leader found"}

    try:
        candidate_name = _pick_candidate(members, leader, candidate)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    if not candidate_name:
        return {"ok": False, "error": "No replica available for switchover"}

    url = seed_url.rstrip("/") + "/switchover"
    payload = {"leader": leader, "candidate": candidate_name}
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_sec) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        return {"ok": False, "error": f"Patroni switchover failed: {exc}"}

    body = (response.text or "").strip()
    if response.status_code >= 400:
        return {
            "ok": False,
            "error": f"Patroni switchover HTTP {response.status_code}: {body[:500]}",
            "leader": leader,
            "candidate": candidate_name,
        }

    proxy_code, proxy_out = await refresh_patroni_proxies()
    return {
        "ok": True,
        "leader": leader,
        "candidate": candidate_name,
        "message": body or f"Switched over from {leader} to {candidate_name}",
        "proxy_refresh_exit_code": proxy_code,
        "proxy_refresh_output": proxy_out[-2000:] if proxy_out else "",
    }


async def start_cluster_node(cluster_id: str, node_ref: str) -> dict[str, Any]:
    container = resolve_container(cluster_id, node_ref)
    if not container:
        return {"ok": False, "error": f"Unknown node '{node_ref}' for cluster '{cluster_id}'"}

    code, out = await docker_start_container(container)
    if code != 0:
        return {"ok": False, "error": f"docker start failed (exit {code})", "output": out, "container": container}

    heal_code, heal_out = await heal_lab_node(container)
    return {
        "ok": heal_code == 0,
        "container": container,
        "action": "start",
        "output": "\n".join(x for x in [out, heal_out] if x),
        "error": None if heal_code == 0 else f"Container started but heal failed (exit {heal_code})",
    }


async def stop_cluster_node(cluster_id: str, node_ref: str) -> dict[str, Any]:
    container = resolve_container(cluster_id, node_ref)
    if not container:
        return {"ok": False, "error": f"Unknown node '{node_ref}' for cluster '{cluster_id}'"}

    code, out = await docker_stop_container(container)
    return {
        "ok": code == 0,
        "container": container,
        "action": "stop",
        "output": out,
        "error": None if code == 0 else f"docker stop failed (exit {code})",
    }
