"""One-click pgBackRest lab setup (UI) — replaces install-pgbackrest-lab.sh."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any

from app.services.cluster_config import load_cluster_containers, load_cluster_pgbackrest
from app.services.docker_logs import docker_exec
from app.services.patroni import fetch_cluster_members
from app.services.pgbackrest import resolve_leader_container

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONF_TPL = _REPO_ROOT / "deploy" / "pgbackrest" / "pgbackrest-lab.conf.tpl"


async def _docker_exec(
    container: str,
    cmd: list[str],
    *,
    user: str | None = None,
    timeout: float = 120.0,
) -> tuple[int, str]:
    return await docker_exec(container, cmd, user=user, timeout=timeout)


def _render_conf(stanza: str, pg_major: str) -> str:
    tpl = _CONF_TPL.read_text(encoding="utf-8")
    return tpl.replace("${STANZA}", stanza).replace("${PG_MAJOR}", pg_major)


async def _detect_pg_major(leader: str) -> str:
    code, out = await _docker_exec(
        leader,
        ["bash", "-c", 'sudo -u postgres psql -tAc "SHOW data_directory"'],
        timeout=30,
    )
    if code != 0:
        return ""
    match = re.search(r"/pgsql/(\d+)/data", out.replace(" ", ""))
    return match.group(1) if match else ""


async def _find_patroni_config(leader: str) -> str:
    code, out = await _docker_exec(
        leader,
        ["bash", "-c", "ls -1 /etc/patroni/*.yml 2>/dev/null | head -1"],
        timeout=15,
    )
    path = out.strip().splitlines()[0].strip() if out.strip() else ""
    return path if code == 0 and path.endswith(".yml") else ""


async def _write_conf(container: str, body: str) -> tuple[int, str]:
    encoded = base64.b64encode(body.encode("utf-8")).decode("ascii")
    script = (
        f"echo {encoded} | base64 -d > /etc/pgbackrest.conf && "
        "chown postgres:postgres /etc/pgbackrest.conf && chmod 0640 /etc/pgbackrest.conf"
    )
    return await _docker_exec(container, ["bash", "-c", script], timeout=30)


async def pgbackrest_setup(
    patroni_seed_url: str,
    cluster_id: str,
    *,
    stanza_override: str = "",
    run_first_backup: bool = True,
) -> dict[str, Any]:
    """
    Install pgBackRest on all cluster containers, write config, wire Patroni archive_command,
    stanza-create, check, and optional first full backup.
    """
    log: list[str] = []
    cfg = load_cluster_pgbackrest(cluster_id)
    stanza = (stanza_override or str(cfg.get("stanza") or "")).strip()
    containers = load_cluster_containers(cluster_id)
    leader, member, host = await resolve_leader_container(patroni_seed_url, cluster_id)

    if not containers:
        return {"ok": False, "error": "No docker_hosts for this cluster in docker-clusters.yaml", "log": log}
    if not leader:
        return {"ok": False, "error": "Patroni leader container not found", "log": log}
    if not stanza:
        return {"ok": False, "error": "Could not resolve pgBackRest stanza name", "log": log}
    if not _CONF_TPL.is_file():
        return {"ok": False, "error": f"Missing config template: {_CONF_TPL}", "log": log}

    log.append(f"Stanza: {stanza} · leader: {leader} ({member}) · nodes: {len(containers)}")

    pg_major = await _detect_pg_major(leader)
    if not pg_major:
        return {"ok": False, "error": "Could not detect PostgreSQL major from data_directory", "log": log}
    log.append(f"PostgreSQL major: {pg_major}")

    install_sh = """
if command -v pgbackrest >/dev/null; then
  pgbackrest version | head -1
  exit 0
fi
dnf install -y -q pgbackrest
"""
    for c in containers:
        code, out = await _docker_exec(c, ["bash", "-c", install_sh], timeout=180)
        log.append(f"[{c}] install exit={code}: {(out or '').strip()[:200]}")
        if code != 0:
            return {"ok": False, "error": f"pgbackrest install failed on {c}", "log": log, "stdout_tail": out[-4000:]}

    for c in containers:
        prep = (
            f"install -d -o postgres -g postgres -m 0750 /nfs/pgbackrest/{stanza}/repo && "
            "install -d -o postgres -g postgres -m 0755 /var/log/pgbackrest"
        )
        code, out = await _docker_exec(c, ["bash", "-c", prep], timeout=30)
        if code != 0:
            return {"ok": False, "error": f"repo prep failed on {c}", "log": log, "stdout_tail": out}

    conf_body = _render_conf(stanza, pg_major)
    for c in containers:
        code, out = await _write_conf(c, conf_body)
        log.append(f"[{c}] wrote /etc/pgbackrest.conf exit={code}")
        if code != 0:
            return {"ok": False, "error": f"config write failed on {c}", "log": log, "stdout_tail": out}

    patroni_cfg = await _find_patroni_config(leader)
    if not patroni_cfg:
        return {"ok": False, "error": "Patroni config not found under /etc/patroni/*.yml", "log": log}

    archive_cmd = f"pgbackrest --stanza={stanza} archive-push %p"
    restore_cmd = f'pgbackrest --stanza={stanza} archive-get %f \\"%p\\"'
    edit = [
        "patronictl",
        "-c",
        patroni_cfg,
        "edit-config",
        "--force",
        "-p",
        f"archive_command={archive_cmd}",
        "-p",
        f"restore_command={restore_cmd}",
        "-q",
    ]
    code, out = await _docker_exec(leader, edit, timeout=60)
    log.append(f"Patroni archive_command exit={code}")
    if code != 0:
        return {"ok": False, "error": "patronictl edit-config failed", "log": log, "stdout_tail": out[-4000:]}

    for step, extra in (
        ("stanza-create", []),
        ("check", []),
    ):
        cmd = ["pgbackrest", f"--stanza={stanza}", "--log-level-console=info", step, *extra]
        code, out = await _docker_exec(leader, cmd, user="postgres", timeout=300)
        log.append(f"pgbackrest {step} exit={code}")
        if code != 0:
            benign = step == "stanza-create" and (
                "already exists" in out.lower() or "duplicate" in out.lower()
            )
            if benign:
                log.append(f"pgbackrest {step}: already present, continuing")
                continue
            return {
                "ok": False,
                "error": f"pgbackrest {step} failed",
                "log": log,
                "stdout_tail": out[-8000:],
            }

    if run_first_backup:
        cmd = ["pgbackrest", f"--stanza={stanza}", "--log-level-console=info", "backup", "--type=full"]
        code, out = await _docker_exec(leader, cmd, user="postgres", timeout=3600)
        log.append(f"pgbackrest backup --type=full exit={code}")
        if code != 0:
            return {
                "ok": False,
                "error": "first full backup failed (setup otherwise complete)",
                "log": log,
                "stdout_tail": out[-8000:],
            }

    # Touch Patroni members for logging only
    try:
        _scope, members = await fetch_cluster_members(patroni_seed_url)
        log.append(f"Cluster members: {len(members)}")
    except Exception as exc:  # noqa: BLE001
        log.append(f"Post-setup member check: {exc}")

    return {
        "ok": True,
        "error": None,
        "stanza": stanza,
        "container": leader,
        "member": member,
        "host": host,
        "log": log,
        "stdout_tail": "\n".join(log),
    }
