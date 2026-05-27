import json
import tarfile
from datetime import UTC, datetime
from io import BytesIO

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import init_db
from app.main import app
from app.services.bundle_import import compute_log_time_range, slugify_cluster_id
from app.services.docker_logs import LogEntry


def test_slugify_cluster_id():
    assert slugify_cluster_id("Acme Production") == "acme-production"


def test_compute_log_time_range():
    entries = [
        LogEntry("2026-05-27T10:00:00+00:00", "h", "m", "patroni", "info", "a"),
        LogEntry("2026-05-27T12:00:00+00:00", "h", "m", "patroni", "info", "b"),
    ]
    start, end = compute_log_time_range(entries)
    assert start is not None and end is not None
    assert "2026-05-27T10:00:00" in start
    assert "2026-05-27T12:00:00" in end


def _make_bundle_tar() -> bytes:
    manifest = {
        "collector": "test",
        "patroni_scope": "test",
        "created_at": datetime.now(UTC).isoformat(),
        "nodes": [{"host": "10.0.0.1", "member_name": "node0"}],
    }
    lines = [
        {
            "ts": "2026-05-27T11:00:00+00:00",
            "node": "10.0.0.1",
            "member_name": "node0",
            "source": "patroni",
            "level": "info",
            "message": "test line",
        }
    ]
    buf = BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        m = tarfile.TarInfo("manifest.json")
        data = json.dumps(manifest).encode()
        m.size = len(data)
        tar.addfile(m, BytesIO(data))
        log_member = tarfile.TarInfo("logs.jsonl")
        log_data = b"\n".join(json.dumps(x).encode() for x in lines) + b"\n"
        log_member.size = len(log_data)
        tar.addfile(log_member, BytesIO(log_data))
    return buf.getvalue()


@pytest.mark.asyncio
async def test_import_bundle_api(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.bundle_store.bundles_root", lambda: tmp_path / "bundles")
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/bundles/import",
            data={"customer_name": "Acme Bank"},
            files={"file": ("bundle_test.tar.gz", _make_bundle_tar(), "application/gzip")},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["customer_name"] == "Acme Bank"
    assert body["cluster_id"] == "test"
    assert body["line_count"] == 1
    assert body["log_time_start"]
    assert "log window" in body["message"]
