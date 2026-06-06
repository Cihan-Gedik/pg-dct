from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Cluster
from app.schemas import BackupInfoResponse, BackupJobCreate, BackupJobRead, BackupSetupRequest
from app.services.pgbackrest import pgbackrest_ensure_ready, pgbackrest_info, pgbackrest_run
from app.services.pgbackrest_setup import pgbackrest_setup

router = APIRouter(prefix="/clusters", tags=["backups"])

# In-memory job log for the UI (resets on API restart).
_jobs: list[dict[str, Any]] = []
_job_seq = 0


@router.get("/{cluster_id}/backup/info", response_model=BackupInfoResponse)
async def get_backup_info(
    cluster_id: str,
    session: AsyncSession = Depends(get_session),
) -> BackupInfoResponse:
    result = await session.execute(
        select(Cluster).where(Cluster.id == cluster_id).options(selectinload(Cluster.nodes))
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    data = await pgbackrest_info(cluster.patroni_seed_url, cluster_id)
    return BackupInfoResponse(
        cluster_id=cluster_id,
        ok=data.get("ok", False),
        needs_setup=bool(data.get("needs_setup")),
        error=data.get("error"),
        container=data.get("container"),
        member=data.get("member"),
        host=data.get("host"),
        stanza=data.get("stanza") or "",
        stanzas=data.get("stanzas") or [],
        stdout_tail=data.get("stdout_tail"),
        fetched_at=datetime.now(UTC),
    )


@router.get("/{cluster_id}/backup/jobs", response_model=list[BackupJobRead])
async def list_backup_jobs(
    cluster_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[BackupJobRead]:
    result = await session.execute(select(Cluster.id).where(Cluster.id == cluster_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Cluster not found")
    out: list[BackupJobRead] = []
    for row in reversed(_jobs):
        if row.get("cluster_id") != cluster_id:
            continue
        out.append(BackupJobRead.model_validate(row))
        if len(out) >= 100:
            break
    return out


@router.post("/{cluster_id}/backup/jobs", response_model=BackupJobRead, status_code=201)
async def create_backup_job(
    cluster_id: str,
    body: BackupJobCreate,
    session: AsyncSession = Depends(get_session),
) -> BackupJobRead:
    global _job_seq  # noqa: PLW0603

    result = await session.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    _job_seq += 1
    job_id = _job_seq
    created = datetime.now(UTC)
    row: dict[str, Any] = {
        "id": job_id,
        "cluster_id": cluster_id,
        "kind": body.kind,
        "status": "running",
        "params": body.params or {},
        "created_at": created,
        "started_at": created,
        "finished_at": None,
        "exit_code": None,
        "stdout_tail": "",
        "error": None,
    }
    _jobs.append(row)

    setup_log = ""
    backup_kinds = {"backup_full", "backup_diff", "backup_incr", "check", "stanza_create"}
    if body.kind in backup_kinds:
        stanza_param = str((body.params or {}).get("stanza") or "")
        ensure = await pgbackrest_ensure_ready(
            cluster.patroni_seed_url,
            cluster_id,
            stanza_override=stanza_param,
        )
        if ensure.get("log") or ensure.get("stdout_tail"):
            setup_log = ensure.get("stdout_tail") or "\n".join(ensure.get("log") or [])
            setup_log = f"=== Ensure pgBackRest ready ===\n{setup_log}\n=== Job ===\n"
        if not ensure.get("ok") and not ensure.get("skipped"):
            finished = datetime.now(UTC)
            row["finished_at"] = finished
            row["stdout_tail"] = setup_log[-8000:]
            row["exit_code"] = 1
            row["error"] = ensure.get("error") or "pgBackRest setup failed"
            row["status"] = "failed"
            return BackupJobRead.model_validate(row)

    stanza = str((body.params or {}).get("stanza") or "")
    run = await pgbackrest_run(
        cluster.patroni_seed_url,
        cluster_id,
        body.kind,
        stanza_override=stanza,
    )
    finished = datetime.now(UTC)
    row["finished_at"] = finished
    row["stdout_tail"] = setup_log + (run.get("stdout_tail") or "")
    row["exit_code"] = run.get("exit_code")
    row["error"] = run.get("error")
    row["status"] = "succeeded" if run.get("ok") else "failed"
    if run.get("error") and not row["stdout_tail"]:
        row["stdout_tail"] = str(run.get("error"))

    return BackupJobRead.model_validate(row)


@router.post("/{cluster_id}/backup/setup", response_model=BackupJobRead, status_code=201)
async def setup_backup(
    cluster_id: str,
    body: BackupSetupRequest,
    session: AsyncSession = Depends(get_session),
) -> BackupJobRead:
    """Install and configure pgBackRest on lab containers (one-click from UI)."""
    global _job_seq  # noqa: PLW0603

    result = await session.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    _job_seq += 1
    job_id = _job_seq
    created = datetime.now(UTC)
    row: dict[str, Any] = {
        "id": job_id,
        "cluster_id": cluster_id,
        "kind": "setup",
        "status": "running",
        "params": {
            "run_first_backup": str(body.run_first_backup).lower(),
            **({"stanza": body.stanza} if body.stanza else {}),
        },
        "created_at": created,
        "started_at": created,
        "finished_at": None,
        "exit_code": None,
        "stdout_tail": "",
        "error": None,
    }
    _jobs.append(row)

    run = await pgbackrest_setup(
        cluster.patroni_seed_url,
        cluster_id,
        stanza_override=body.stanza or "",
        run_first_backup=body.run_first_backup,
    )
    finished = datetime.now(UTC)
    row["finished_at"] = finished
    row["stdout_tail"] = run.get("stdout_tail") or "\n".join(run.get("log") or [])
    row["exit_code"] = 0 if run.get("ok") else 1
    row["error"] = run.get("error")
    row["status"] = "succeeded" if run.get("ok") else "failed"

    return BackupJobRead.model_validate(row)
