"""Tests for PostgreSQL log discovery in collect.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collect import build_postgres_collect_command  # noqa: E402


def test_postgres_command_includes_journal_and_psql() -> None:
    cmd = build_postgres_collect_command(100, ["/custom/pg.log"])
    assert cmd[:2] == ["bash", "-c"]
    script = cmd[2]
    assert "journalctl" in script
    assert "postgresql" in script
    assert "SHOW log_directory" in script
    assert "SHOW log_filename" in script
    assert "/var/log/postgresql/*.log" in script
    assert "/custom/pg.log" in script
