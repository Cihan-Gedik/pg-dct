from datetime import UTC, datetime
from typing import Any

from app.models import Cluster
from app.services.pgbackrest import pgbackrest_run

# In-memory job log for the UI (resets on API restart).
_jobs: list[dict[str, Any]] = []
_job_seq = 0


def list_backup_jobs(cluster_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in reversed(_jobs):
        if row.get("cluster_id") != cluster_id:
            continue
        out.append(row)
        if len(out) >= limit:
            break
    return out


async def run_backup_job(
    cluster: Cluster,
    kind: str,
    *,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    global _job_seq  # noqa: PLW0603

    _job_seq += 1
    created = datetime.now(UTC)
    row: dict[str, Any] = {
        "id": _job_seq,
        "cluster_id": cluster.id,
        "kind": kind,
        "status": "running",
        "params": params or {},
        "created_at": created,
        "started_at": created,
        "finished_at": None,
        "exit_code": None,
        "stdout_tail": "",
        "error": None,
    }
    _jobs.append(row)

    stanza = str((params or {}).get("stanza") or "")
    run = await pgbackrest_run(
        cluster.patroni_seed_url,
        cluster.id,
        kind,
        stanza_override=stanza,
    )
    row["finished_at"] = datetime.now(UTC)
    row["stdout_tail"] = run.get("stdout_tail") or ""
    row["exit_code"] = run.get("exit_code")
    row["error"] = run.get("error")
    row["status"] = "succeeded" if run.get("ok") else "failed"
    if run.get("error") and not row["stdout_tail"]:
        row["stdout_tail"] = str(run.get("error"))

    return row
