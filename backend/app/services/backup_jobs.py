from datetime import UTC, datetime
from typing import Any

from app.models import Cluster
from app.services.pgbackrest import pgbackrest_ensure_ready, pgbackrest_run
from app.services.pgbackrest_setup import pgbackrest_setup

# In-memory job log for the UI (resets on API restart).
_jobs: list[dict[str, Any]] = []
_job_seq = 0

_BACKUP_KINDS = {"backup_full", "backup_diff", "backup_incr", "check", "stanza_create"}


def list_backup_jobs(cluster_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in reversed(_jobs):
        if row.get("cluster_id") != cluster_id:
            continue
        out.append(row)
        if len(out) >= limit:
            break
    return out


def _new_job_row(cluster_id: str, kind: str, params: dict[str, str]) -> dict[str, Any]:
    global _job_seq  # noqa: PLW0603

    _job_seq += 1
    created = datetime.now(UTC)
    row: dict[str, Any] = {
        "id": _job_seq,
        "cluster_id": cluster_id,
        "kind": kind,
        "status": "running",
        "params": params,
        "created_at": created,
        "started_at": created,
        "finished_at": None,
        "exit_code": None,
        "stdout_tail": "",
        "error": None,
    }
    _jobs.append(row)
    return row


async def run_backup_job(
    cluster: Cluster,
    kind: str,
    *,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    job_params = params or {}
    row = _new_job_row(cluster.id, kind, job_params)

    setup_log = ""
    if kind in _BACKUP_KINDS:
        stanza_param = str(job_params.get("stanza") or "")
        ensure = await pgbackrest_ensure_ready(
            cluster.patroni_seed_url,
            cluster.id,
            stanza_override=stanza_param,
        )
        if ensure.get("log") or ensure.get("stdout_tail"):
            setup_log = ensure.get("stdout_tail") or "\n".join(ensure.get("log") or [])
            setup_log = f"=== Ensure pgBackRest ready ===\n{setup_log}\n=== Job ===\n"
        if not ensure.get("ok") and not ensure.get("skipped"):
            row["finished_at"] = datetime.now(UTC)
            row["stdout_tail"] = setup_log[-8000:]
            row["exit_code"] = 1
            row["error"] = ensure.get("error") or "pgBackRest setup failed"
            row["status"] = "failed"
            return row

    stanza = str(job_params.get("stanza") or "")
    run = await pgbackrest_run(
        cluster.patroni_seed_url,
        cluster.id,
        kind,
        stanza_override=stanza,
    )
    row["finished_at"] = datetime.now(UTC)
    row["stdout_tail"] = setup_log + (run.get("stdout_tail") or "")
    row["exit_code"] = run.get("exit_code")
    row["error"] = run.get("error")
    row["status"] = "succeeded" if run.get("ok") else "failed"
    if run.get("error") and not row["stdout_tail"]:
        row["stdout_tail"] = str(run.get("error"))

    return row


async def run_setup_job(
    cluster: Cluster,
    *,
    stanza_override: str = "",
    run_first_backup: bool = True,
) -> dict[str, Any]:
    params: dict[str, str] = {"run_first_backup": str(run_first_backup).lower()}
    if stanza_override:
        params["stanza"] = stanza_override

    row = _new_job_row(cluster.id, "setup", params)

    run = await pgbackrest_setup(
        cluster.patroni_seed_url,
        cluster.id,
        stanza_override=stanza_override,
        run_first_backup=run_first_backup,
    )
    row["finished_at"] = datetime.now(UTC)
    row["stdout_tail"] = run.get("stdout_tail") or "\n".join(run.get("log") or [])
    row["exit_code"] = 0 if run.get("ok") else 1
    row["error"] = run.get("error")
    row["status"] = "succeeded" if run.get("ok") else "failed"

    return row
