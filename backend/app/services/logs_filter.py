"""Shared log filtering for live tail and bundle archive views."""

from __future__ import annotations

from app.schemas import LogLevel, LogSource


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
