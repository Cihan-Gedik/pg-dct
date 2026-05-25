"""Build primary/replica timeline from Patroni /history."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    text = str(raw).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


def parse_history_rows(history: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(history, list):
        return rows
    for item in history:
        if not isinstance(item, (list, tuple)) or len(item) < 5:
            continue
        ts = _parse_ts(item[3])
        if not ts:
            continue
        rows.append(
            {
                "timeline": int(item[0]) if item[0] is not None else None,
                "at": ts,
                "leader": str(item[4]),
                "reason": str(item[2]) if item[2] is not None else "",
            }
        )
    rows.sort(key=lambda r: r["at"])
    return rows


def build_leader_periods(
    history: Any,
    range_start: datetime,
    range_end: datetime,
    current_leader: str | None,
) -> list[dict[str, Any]]:
    """Intervals where each Patroni leader held primary."""
    rows = parse_history_rows(history)
    now = datetime.now(UTC)
    periods: list[dict[str, Any]] = []

    for i, row in enumerate(rows):
        start = row["at"]
        end = rows[i + 1]["at"] if i + 1 < len(rows) else now
        if end <= range_start or start >= range_end:
            continue
        clip_start = max(start, range_start)
        clip_end = min(end, range_end)
        if clip_start >= clip_end:
            continue
        periods.append(
            {
                "leader": row["leader"],
                "start": clip_start,
                "end": clip_end,
                "timeline": row["timeline"],
                "reason": row["reason"],
            }
        )

    if not periods and current_leader:
        periods.append(
            {
                "leader": current_leader,
                "start": range_start,
                "end": range_end,
                "timeline": None,
                "reason": "current",
            }
        )
    return periods


def _merge_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not segments:
        return []
    segments = sorted(segments, key=lambda s: s["start"])
    merged: list[dict[str, Any]] = [segments[0].copy()]
    for seg in segments[1:]:
        last = merged[-1]
        if seg["role"] == last["role"] and seg.get("leader") == last.get("leader"):
            last["end"] = max(last["end"], seg["end"])
        else:
            merged.append(seg.copy())
    return merged


def build_member_timeline(
    history: Any,
    member_names: list[str],
    range_start: datetime,
    range_end: datetime,
    current_leader: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Per-member role segments (leader=replica only; one role per instant).
    Same node can be green then blue in sequence — never both at once.
    """
    periods = build_leader_periods(history, range_start, range_end, current_leader)
    all_members = sorted(set(member_names) | {p["leader"] for p in periods})

    by_member: dict[str, list[dict[str, Any]]] = {m: [] for m in all_members}
    for p in periods:
        for name in all_members:
            role = "leader" if name == p["leader"] else "replica"
            by_member[name].append(
                {
                    "role": role,
                    "start": p["start"],
                    "end": p["end"],
                    "leader": p["leader"],
                    "timeline": p["timeline"],
                    "reason": p["reason"] if role == "leader" else f"following {p['leader']}",
                }
            )

    members_out: list[dict[str, Any]] = []
    for name in all_members:
        merged = _merge_segments(by_member.get(name, []))
        members_out.append(
            {
                "member": name,
                "segments": [
                    {
                        "role": s["role"],
                        "start": s["start"].isoformat(),
                        "end": s["end"].isoformat(),
                        "leader": s.get("leader"),
                        "timeline": s.get("timeline"),
                        "reason": s.get("reason", ""),
                    }
                    for s in merged
                ],
            }
        )

    switchovers = [
        {
            "at": p["start"].isoformat(),
            "leader": p["leader"],
            "timeline": p["timeline"],
            "reason": p["reason"],
        }
        for p in periods
        if p["start"] > range_start
    ]

    return members_out, switchovers


def default_range(hours: int) -> tuple[datetime, datetime]:
    end = datetime.now(UTC)
    start = end - timedelta(hours=max(1, min(hours, 24 * 90)))
    return start, end
