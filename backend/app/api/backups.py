from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import BackupSchedule, Cluster
from app.schemas import (
    BackupInfoResponse,
    BackupJobCreate,
    BackupJobRead,
    BackupScheduleCreate,
    BackupScheduleRead,
    BackupScheduleUpdate,
)
from app.services.backup_jobs import list_backup_jobs as list_backup_job_rows
from app.services.backup_jobs import run_backup_job
from app.services.backup_schedules import compute_next_run, validate_cron, validate_schedule_kind
from app.services.pgbackrest import pgbackrest_info

router = APIRouter(prefix="/clusters", tags=["backups"])


async def _get_cluster(session: AsyncSession, cluster_id: str) -> Cluster:
    result = await session.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return cluster


async def _get_schedule(
    session: AsyncSession,
    cluster_id: str,
    schedule_id: int,
) -> BackupSchedule:
    result = await session.execute(
        select(BackupSchedule)
        .where(BackupSchedule.cluster_id == cluster_id)
        .where(BackupSchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Backup schedule not found")
    return schedule


def _schedule_to_read(schedule: BackupSchedule) -> BackupScheduleRead:
    return BackupScheduleRead(
        id=schedule.id,
        cluster_id=schedule.cluster_id,
        name=schedule.name,
        kind=schedule.kind,
        cron=schedule.cron,
        stanza=schedule.stanza or "",
        enabled=bool(schedule.enabled),
        next_run_at=schedule.next_run_at,
        last_run_at=schedule.last_run_at,
        last_status=schedule.last_status,
        last_job_id=schedule.last_job_id,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


def _normalize_cron_or_400(expr: str) -> str:
    try:
        return validate_cron(expr)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _validate_schedule_kind_or_400(kind: str) -> str:
    try:
        return validate_schedule_kind(kind)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    await _get_cluster(session, cluster_id)
    return [BackupJobRead.model_validate(row) for row in list_backup_job_rows(cluster_id)]


@router.post("/{cluster_id}/backup/jobs", response_model=BackupJobRead, status_code=201)
async def create_backup_job(
    cluster_id: str,
    body: BackupJobCreate,
    session: AsyncSession = Depends(get_session),
) -> BackupJobRead:
    cluster = await _get_cluster(session, cluster_id)
    row = await run_backup_job(cluster, body.kind, params=body.params or {})
    return BackupJobRead.model_validate(row)


@router.get("/{cluster_id}/backup/schedules", response_model=list[BackupScheduleRead])
async def list_backup_schedules(
    cluster_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[BackupScheduleRead]:
    await _get_cluster(session, cluster_id)
    result = await session.execute(
        select(BackupSchedule)
        .where(BackupSchedule.cluster_id == cluster_id)
        .order_by(BackupSchedule.id.asc())
    )
    return [_schedule_to_read(schedule) for schedule in result.scalars().all()]


@router.post("/{cluster_id}/backup/schedules", response_model=BackupScheduleRead, status_code=201)
async def create_backup_schedule(
    cluster_id: str,
    body: BackupScheduleCreate,
    session: AsyncSession = Depends(get_session),
) -> BackupScheduleRead:
    await _get_cluster(session, cluster_id)
    kind = _validate_schedule_kind_or_400(body.kind)
    cron = _normalize_cron_or_400(body.cron)
    now = datetime.now(UTC)
    schedule = BackupSchedule(
        cluster_id=cluster_id,
        name=body.name.strip(),
        kind=kind,
        cron=cron,
        stanza=body.stanza.strip(),
        enabled=1 if body.enabled else 0,
        next_run_at=compute_next_run(cron, now) if body.enabled else None,
    )
    session.add(schedule)
    await session.commit()
    await session.refresh(schedule)
    return _schedule_to_read(schedule)


@router.patch("/{cluster_id}/backup/schedules/{schedule_id}", response_model=BackupScheduleRead)
async def update_backup_schedule(
    cluster_id: str,
    schedule_id: int,
    body: BackupScheduleUpdate,
    session: AsyncSession = Depends(get_session),
) -> BackupScheduleRead:
    await _get_cluster(session, cluster_id)
    schedule = await _get_schedule(session, cluster_id, schedule_id)
    data = body.model_dump(exclude_unset=True)

    recalc_next_run = False
    if "name" in data and data["name"] is not None:
        schedule.name = str(data["name"]).strip()
    if "kind" in data and data["kind"] is not None:
        schedule.kind = _validate_schedule_kind_or_400(str(data["kind"]))
    if "cron" in data and data["cron"] is not None:
        schedule.cron = _normalize_cron_or_400(str(data["cron"]))
        recalc_next_run = True
    if "stanza" in data and data["stanza"] is not None:
        schedule.stanza = str(data["stanza"]).strip()
    if "enabled" in data and data["enabled"] is not None:
        schedule.enabled = 1 if bool(data["enabled"]) else 0
        recalc_next_run = True

    if schedule.enabled:
        if recalc_next_run or schedule.next_run_at is None:
            schedule.next_run_at = compute_next_run(schedule.cron, datetime.now(UTC))
    else:
        schedule.next_run_at = None

    await session.commit()
    await session.refresh(schedule)
    return _schedule_to_read(schedule)


@router.delete("/{cluster_id}/backup/schedules/{schedule_id}", status_code=204)
async def delete_backup_schedule(
    cluster_id: str,
    schedule_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    await _get_cluster(session, cluster_id)
    schedule = await _get_schedule(session, cluster_id, schedule_id)
    await session.delete(schedule)
    await session.commit()


@router.post("/{cluster_id}/backup/schedules/{schedule_id}/run", response_model=BackupJobRead)
async def run_backup_schedule_now(
    cluster_id: str,
    schedule_id: int,
    session: AsyncSession = Depends(get_session),
) -> BackupJobRead:
    cluster = await _get_cluster(session, cluster_id)
    schedule = await _get_schedule(session, cluster_id, schedule_id)
    params = {"stanza": schedule.stanza} if schedule.stanza else {}
    row = await run_backup_job(cluster, schedule.kind, params=params)
    schedule.last_run_at = datetime.now(UTC)
    schedule.last_job_id = int(row["id"])
    schedule.last_status = str(row["status"])
    await session.commit()
    return BackupJobRead.model_validate(row)
