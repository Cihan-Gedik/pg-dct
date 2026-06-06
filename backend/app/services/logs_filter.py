"""Shared log filtering for live tail and bundle archive views."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.schemas import LogLevel, LogSource
from app.services.docker_logs import parse_log_timestamp


def filter_log_entries(
    lines: list,
    node: str | None,
    levels: list[LogLevel],
    sources: dict[LogSource, str],
    search: str | None,
) -> list:
    q = (search or "").strip().lower()
    out = []
    for entry in lines:
        if node and node != "all" and entry.node != node and entry.member_name != node:
            continue
        if entry.level not in levels:
            continue
        mode = sources.get(entry.source, "include")
        if mode == "exclude":
            continue
        if mode == "errors" and entry.level not in ("critical", "warning"):
            continue
        if q and q not in f"{entry.ts} {entry.node} {entry.source} {entry.level} {entry.message}".lower():
            continue
        out.append(entry)
    return out


def entry_in_time_window(
    entry,
    *,
    hours: float | None = None,
    range_from: datetime | None = None,
    range_to: datetime | None = None,
) -> bool:
    dt = parse_log_timestamp(entry.ts)
    if dt is None:
        return False
    if range_from is not None or range_to is not None:
        if range_from is not None and dt < range_from:
            return False
        if range_to is not None and dt > range_to:
            return False
        return True
    if hours is not None:
        return dt >= datetime.now(UTC) - timedelta(hours=hours)
    return True


def parse_range_datetime(raw: str | None) -> datetime | None:
    if not raw or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def filter_by_time_window(
    lines: list,
    *,
    hours: float | None = None,
    range_from: datetime | None = None,
    range_to: datetime | None = None,
) -> list:
    if hours is None and range_from is None and range_to is None:
        return lines
    return [
        e
        for e in lines
        if entry_in_time_window(e, hours=hours, range_from=range_from, range_to=range_to)
    ]
