from datetime import UTC, datetime

import pytest

from app.services.bundle_store import (
    list_bundles,
    load_bundle_entries,
    load_manifest,
    new_bundle_id,
    write_bundle,
)
from app.services.docker_logs import LogEntry
from app.services.logs_filter import filter_log_entries


@pytest.fixture
def bundle_root(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.bundle_store.bundles_root", lambda: tmp_path / "bundles")
    return tmp_path / "bundles"


def test_write_and_load_bundle(bundle_root):
    bid = new_bundle_id("bc-pg-main", datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC))
    assert bid == "bc-pg-main_20260527T120000Z"
    entries = [
        LogEntry(
            ts="2026-05-27T12:00:00+00:00",
            node="n0",
            member_name="bc-pg-main-0",
            source="patroni",
            level="info",
            message="hello",
        )
    ]
    write_bundle(
        bid,
        {"cluster_id": "bc-pg-main", "cluster_name": "bc-pg-main", "created_at": "2026-05-27T12:00:00+00:00"},
        entries,
    )
    assert load_manifest(bid)["line_count"] == 1
    loaded = load_bundle_entries(bid)
    assert len(loaded) == 1
    assert loaded[0].message == "hello"
    summaries = list_bundles("bc-pg-main")
    assert len(summaries) == 1
    assert summaries[0].id == bid


def test_filter_log_entries():
    entry = LogEntry(
        ts="t",
        node="n0",
        member_name="m0",
        source="etcd",
        level="warning",
        message="peer dial failed",
    )
    out = filter_log_entries(
        [entry],
        node="all",
        levels=["warning"],
        sources={"patroni": "include", "postgres": "include", "etcd": "exclude", "os": "include"},
        search=None,
    )
    assert out == []
