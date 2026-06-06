from datetime import UTC, datetime, timedelta

from app.services.docker_logs import LogEntry
from app.services.logs_filter import entry_in_time_window, filter_by_time_window, parse_range_datetime


def _entry(ts: str) -> LogEntry:
    return LogEntry(
        ts=ts,
        node="n1",
        member_name="n1",
        source="patroni",
        level="info",
        message="test",
    )


def test_entry_in_time_window_hours():
    recent = (datetime.now(UTC) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    old = (datetime.now(UTC) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    assert entry_in_time_window(_entry(recent), hours=24) is True
    assert entry_in_time_window(_entry(old), hours=24) is False


def test_entry_in_time_window_absolute():
    t0 = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    t1 = datetime(2026, 5, 2, 12, 0, tzinfo=UTC)
    t2 = datetime(2026, 5, 3, 12, 0, tzinfo=UTC)
    e = _entry(t1.strftime("%Y-%m-%dT%H:%M:%S+00:00"))
    assert entry_in_time_window(e, range_from=t0, range_to=t2) is True
    assert entry_in_time_window(e, range_from=t2) is False
    assert entry_in_time_window(e, range_to=t0) is False


def test_parse_range_datetime():
    dt = parse_range_datetime("2026-05-01T10:30:00Z")
    assert dt == datetime(2026, 5, 1, 10, 30, tzinfo=UTC)


def test_filter_by_time_window_noop():
    lines = [_entry("2026-05-01T10:00:00+00:00")]
    assert filter_by_time_window(lines) == lines
