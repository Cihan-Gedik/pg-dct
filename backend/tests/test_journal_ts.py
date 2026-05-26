from datetime import UTC, datetime, timedelta

from app.services.docker_logs import (
    LogEntry,
    entry_within_hours,
    parse_journal_line,
    parse_log_timestamp,
)


def test_parse_journal_line_iso_with_hostname() -> None:
    line = (
        '2026-05-23T14:02:01+0000 node2 bash[2604]: {"level":"warn","msg":"prober detected unhealthy status"}'
    )
    ts, msg = parse_journal_line(line)
    assert ts == "2026-05-23T14:02:01+0000"
    assert "prober detected unhealthy status" in msg


def test_parse_log_timestamp_iso_offset() -> None:
    dt = parse_log_timestamp("2026-05-23T14:02:01+0000")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 5 and dt.day == 23


def test_entry_outside_24h_window() -> None:
    entry = LogEntry(
        ts="2026-05-23T14:02:01+0000",
        node="172.18.0.4",
        member_name="lc-pg-main6921-1",
        source="etcd",
        level="critical",
        message="dial tcp 172.18.0.2:2380: connect: connection refused",
    )
    assert entry_within_hours(entry, 24) is False


def test_entry_inside_24h_window() -> None:
    recent = (datetime.now(UTC) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    entry = LogEntry(
        ts=recent,
        node="172.18.0.4",
        member_name="n1",
        source="etcd",
        level="warning",
        message="recent",
    )
    assert entry_within_hours(entry, 24) is True
