from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import BackupSchedule, Cluster
from app.services.backup_jobs import run_backup_job

SCHEDULE_JOB_KINDS = {"backup_full", "backup_diff", "backup_incr"}


@dataclass(frozen=True)
class CronField:
    values: set[int]
    wildcard: bool = False


@dataclass(frozen=True)
class ParsedCron:
    minute: CronField
    hour: CronField
    day_of_month: CronField
    month: CronField
    day_of_week: CronField


def _parse_int(raw: str, minimum: int, maximum: int, *, field_name: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name} value: {raw}") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"{field_name} value {value} is outside {minimum}-{maximum}")
    return value


def _parse_cron_field(
    raw: str,
    *,
    minimum: int,
    maximum: int,
    field_name: str,
    allow_seven_as_sunday: bool = False,
) -> CronField:
    raw = raw.strip()
    if not raw:
        raise ValueError(f"{field_name} cannot be empty")

    values: set[int] = set()
    wildcard = raw == "*" or raw.startswith("*/")

    for part in raw.split(","):
        part = part.strip()
        if not part:
            raise ValueError(f"Invalid {field_name} list")

        step = 1
        if "/" in part:
            base, step_raw = part.split("/", 1)
            step = _parse_int(step_raw, 1, maximum, field_name=f"{field_name} step")
        else:
            base = part

        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            start_raw, end_raw = base.split("-", 1)
            start = _parse_int(start_raw, minimum, maximum, field_name=field_name)
            end = _parse_int(end_raw, minimum, maximum, field_name=field_name)
            if start > end:
                raise ValueError(f"{field_name} range start cannot exceed range end")
        else:
            start = end = _parse_int(base, minimum, maximum, field_name=field_name)

        for value in range(start, end + 1, step):
            if allow_seven_as_sunday and value == 7:
                values.add(0)
            else:
                values.add(value)

    return CronField(values=values, wildcard=wildcard)


def parse_cron(expr: str) -> ParsedCron:
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError("Cron expression must have 5 fields: minute hour day month weekday")
    return ParsedCron(
        minute=_parse_cron_field(parts[0], minimum=0, maximum=59, field_name="minute"),
        hour=_parse_cron_field(parts[1], minimum=0, maximum=23, field_name="hour"),
        day_of_month=_parse_cron_field(parts[2], minimum=1, maximum=31, field_name="day of month"),
        month=_parse_cron_field(parts[3], minimum=1, maximum=12, field_name="month"),
        day_of_week=_parse_cron_field(
            parts[4],
            minimum=0,
            maximum=7,
            field_name="day of week",
            allow_seven_as_sunday=True,
        ),
    )


def _cron_dow(dt: datetime) -> int:
    # Python: Monday=0; cron: Sunday=0.
    return (dt.weekday() + 1) % 7


def _matches_cron(parsed: ParsedCron, dt: datetime) -> bool:
    dom_match = dt.day in parsed.day_of_month.values
    dow_match = _cron_dow(dt) in parsed.day_of_week.values
    if parsed.day_of_month.wildcard or parsed.day_of_week.wildcard:
        day_match = dom_match and dow_match
    else:
        # Standard cron behavior: restricted day-of-month and day-of-week are OR'ed.
        day_match = dom_match or dow_match

    return (
        dt.minute in parsed.minute.values
        and dt.hour in parsed.hour.values
        and day_match
        and dt.month in parsed.month.values
    )


def compute_next_run(expr: str, after: datetime | None = None) -> datetime:
    parsed = parse_cron(expr)
    cursor = after or datetime.now(UTC)
    if cursor.tzinfo is None:
        cursor = cursor.replace(tzinfo=UTC)
    cursor = cursor.astimezone(UTC).replace(second=0, microsecond=0) + timedelta(minutes=1)

    max_minutes = 366 * 24 * 60
    for _ in range(max_minutes):
        if _matches_cron(parsed, cursor):
            return cursor
        cursor += timedelta(minutes=1)
    raise ValueError("Cron expression did not produce a run within the next 366 days")


def validate_schedule_kind(kind: str) -> str:
    if kind not in SCHEDULE_JOB_KINDS:
        allowed = ", ".join(sorted(SCHEDULE_JOB_KINDS))
        raise ValueError(f"Unsupported schedule kind: {kind}. Allowed: {allowed}")
    return kind


def validate_cron(expr: str) -> str:
    normalized = " ".join(expr.split())
    compute_next_run(normalized)
    return normalized


async def run_due_backup_schedules(session: AsyncSession, now: datetime | None = None) -> int:
    due_at = now or datetime.now(UTC)
    result = await session.execute(
        select(BackupSchedule)
        .where(BackupSchedule.enabled == 1)
        .where(BackupSchedule.next_run_at.is_not(None))
        .where(BackupSchedule.next_run_at <= due_at)
        .order_by(BackupSchedule.next_run_at.asc(), BackupSchedule.id.asc())
    )
    schedules = result.scalars().all()
    ran = 0

    for schedule in schedules:
        cluster = await session.get(Cluster, schedule.cluster_id)
        if not cluster:
            schedule.enabled = 0
            schedule.last_status = "cluster_missing"
            schedule.next_run_at = None
            await session.commit()
            continue

        params = {"stanza": schedule.stanza} if schedule.stanza else {}
        job = await run_backup_job(cluster, schedule.kind, params=params)
        schedule.last_run_at = datetime.now(UTC)
        schedule.last_job_id = int(job["id"])
        schedule.last_status = str(job["status"])
        schedule.next_run_at = compute_next_run(schedule.cron, schedule.last_run_at)
        await session.commit()
        ran += 1

    return ran


async def scheduler_loop(session_factory: async_sessionmaker[AsyncSession]) -> None:
    while True:
        try:
            async with session_factory() as session:
                await run_due_backup_schedules(session)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Scheduler failures should not terminate the API process. The next tick retries.
            pass
        await asyncio.sleep(60)
