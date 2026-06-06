from datetime import UTC, datetime

import pytest

from app.services.backup_schedules import compute_next_run, validate_cron, validate_schedule_kind


def test_compute_next_run_daily_schedule() -> None:
    after = datetime(2026, 6, 6, 1, 59, tzinfo=UTC)
    assert compute_next_run("0 2 * * *", after) == datetime(2026, 6, 6, 2, 0, tzinfo=UTC)


def test_compute_next_run_every_six_hours() -> None:
    after = datetime(2026, 6, 6, 2, 30, tzinfo=UTC)
    assert compute_next_run("0 */6 * * *", after) == datetime(2026, 6, 6, 6, 0, tzinfo=UTC)


def test_compute_next_run_weekday_uses_cron_sunday() -> None:
    after = datetime(2026, 6, 6, 23, 59, tzinfo=UTC)
    assert compute_next_run("0 3 * * 0", after) == datetime(2026, 6, 7, 3, 0, tzinfo=UTC)


def test_validate_cron_rejects_bad_expression() -> None:
    with pytest.raises(ValueError, match="5 fields"):
        validate_cron("0 2 * *")


def test_validate_schedule_kind_rejects_non_backup_job() -> None:
    with pytest.raises(ValueError, match="Unsupported schedule kind"):
        validate_schedule_kind("stanza_create")
