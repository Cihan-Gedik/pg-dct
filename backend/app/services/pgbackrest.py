"""Run pgBackRest in Patroni lab containers via docker exec."""

from __future__ import annotations

import json
from typing import Any

from app.services.cluster_config import load_cluster_docker_hosts, load_cluster_pgbackrest
from app.services.docker_logs import _docker_exec, docker_exec
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
            "needs_setup": True,
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
            "needs_setup": True,
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
            "needs_setup": True,
        }

    stanzas = payload if isinstance(payload, list) else []
    ready, needs_setup, status_msg = _analyze_stanzas(stanzas, stanza)
    if not needs_setup and stanza and not await _leader_conf_has_pg1_path(container, stanza):
        needs_setup = True
        ready = False
        status_msg = "pgbackrest.conf missing pg1-path — run Setup pgBackRest"
    return {
        "ok": ready and not needs_setup,
        "needs_setup": needs_setup,
        "error": status_msg if needs_setup else None,
        "container": container,
        "member": member,
        "host": host,
        "stanza": stanza,
        "stanzas": stanzas,
    }


def _analyze_stanzas(stanzas: list, stanza_filter: str) -> tuple[bool, bool, str | None]:
    """Return (ready, needs_setup, user_message)."""
    if not stanzas:
        return False, True, "No pgBackRest stanza — run Setup pgBackRest first"
    target = None
    for item in stanzas:
        if not stanza_filter or str(item.get("name") or "") == stanza_filter:
            target = item
            break
    if target is None:
        return False, True, f"Stanza {stanza_filter!r} not found in pgbackrest info"
    status = target.get("status") if isinstance(target.get("status"), dict) else {}
    code = status.get("code")
    msg = str(status.get("message") or "")
    lower = msg.lower()
    if code == 1 or "missing stanza" in lower:
        return False, True, msg or "Stanza missing pg1-path — run Setup pgBackRest"
    if "error" in lower and "no valid backup" not in lower:
        return False, True, msg
    # code 0 = OK; code 2 = configured but no backups yet
    return True, False, msg or None


async def conf_has_pg1_path(container: str, stanza: str) -> bool:
    """True when /etc/pgbackrest.conf has pg1-path under [stanza]."""
    section = f"[{stanza}]"
    code, out = await docker_exec(container, ["cat", "/etc/pgbackrest.conf"], user="postgres", timeout=15)
    if code != 0:
        return False
    in_section = False
    for line in out.splitlines():
        text = line.strip()
        if text == section:
            in_section = True
            continue
        if in_section:
            if text.startswith("[") and text.endswith("]"):
                break
            if text.startswith("pg1-path=") and not text.startswith("#"):
                return True
    return False


async def pgbackrest_ensure_ready(
    patroni_seed_url: str,
    cluster_id: str,
    *,
    stanza_override: str = "",
) -> dict[str, Any]:
    """Install/configure pgBackRest on all nodes when any node or stanza is not ready."""
    from app.services.cluster_config import load_cluster_containers, load_cluster_pgbackrest
    from app.services.pgbackrest_setup import pgbackrest_setup

    containers = load_cluster_containers(cluster_id)
    if not containers:
        return {"ok": True, "skipped": True, "log": []}

    cfg = load_cluster_pgbackrest(cluster_id)
    stanza = (stanza_override or str(cfg.get("stanza") or "")).strip()
    if not stanza:
        return {"ok": False, "error": "No stanza name for cluster", "log": []}

    missing = [c for c in containers if not await conf_has_pg1_path(c, stanza)]
    info = await pgbackrest_info(patroni_seed_url, cluster_id)
    needs = bool(missing) or bool(info.get("needs_setup"))

    if not needs:
        return {"ok": True, "log": [], "stdout_tail": ""}

    log_prefix = []
    if missing:
        log_prefix.append(f"Nodes missing pg1-path: {', '.join(missing)}")

    setup = await pgbackrest_setup(
        patroni_seed_url,
        cluster_id,
        stanza_override=stanza,
        run_first_backup=False,
    )
    if log_prefix:
        setup["log"] = log_prefix + (setup.get("log") or [])
        setup["stdout_tail"] = "\n".join(setup.get("log") or [])
    return setup


async def _leader_conf_has_pg1_path(container: str, stanza: str) -> bool:
    return await conf_has_pg1_path(container, stanza)


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

    code, raw = await docker_exec(container, cmd, user="postgres", timeout=timeout)
    lower = raw.lower()
    failed = code != 0 or (
        "requires option:" in lower
        or "[037]" in raw
        or (" p00   error:" in lower and "completed successfully" not in lower)
    )

    if failed and ("[037]" in raw or "requires option:" in lower):
        ensure = await pgbackrest_ensure_ready(patroni_seed_url, cluster_id, stanza_override=stanza)
        if ensure.get("ok"):
            code, raw = await docker_exec(container, cmd, user="postgres", timeout=timeout)
            lower = raw.lower()
            failed = code != 0 or (
                "requires option:" in lower
                or "[037]" in raw
                or (" p00   error:" in lower and "completed successfully" not in lower)
            )
            if ensure.get("log"):
                raw = "=== Auto-setup ===\n" + "\n".join(ensure.get("log") or []) + "\n=== Job ===\n" + raw

    return {
        "ok": not failed,
        "error": None if not failed else "pgbackrest reported errors (see stdout)",
        "exit_code": code if code != 0 else (1 if failed else 0),
        "stdout_tail": raw[-8000:] if raw else "",
        "container": container,
        "member": member,
        "host": host,
        "kind": kind,
    }
