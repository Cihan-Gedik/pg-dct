"""On-disk bundle storage and log archive loading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.bootstrap import _repo_root
from app.services.docker_logs import LogEntry


def bundles_root() -> Path:
    root = _repo_root() / "data" / "bundles"
    root.mkdir(parents=True, exist_ok=True)
    return root


def bundle_dir(bundle_id: str) -> Path:
    safe = bundle_id.replace("/", "_").replace("..", "")
    return bundles_root() / safe


def new_bundle_id(cluster_id: str, when: datetime | None = None) -> str:
    ts = (when or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return f"{cluster_id}_{ts}"


def write_bundle(
    bundle_id: str,
    manifest: dict[str, Any],
    entries: list[LogEntry],
) -> Path:
    dest = bundle_dir(bundle_id)
    dest.mkdir(parents=True, exist_ok=True)
    manifest_path = dest / "manifest.json"
    logs_path = dest / "logs.jsonl"
    manifest["id"] = bundle_id
    manifest["line_count"] = len(entries)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with logs_path.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(
                json.dumps(
                    {
                        "ts": entry.ts,
                        "node": entry.node,
                        "member_name": entry.member_name,
                        "source": entry.source,
                        "level": entry.level,
                        "message": entry.message,
                    },
                    ensure_ascii=False,
                )
            )
            fh.write("\n")
    return dest


def load_manifest(bundle_id: str) -> dict[str, Any] | None:
    path = bundle_dir(bundle_id) / "manifest.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_bundle_entries(bundle_id: str) -> list[LogEntry]:
    path = bundle_dir(bundle_id) / "logs.jsonl"
    if not path.is_file():
        return []
    entries: list[LogEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        raw = json.loads(line)
        entries.append(
            LogEntry(
                ts=str(raw.get("ts") or ""),
                node=str(raw.get("node") or ""),
                member_name=str(raw.get("member_name") or ""),
                source=raw.get("source") or "os",
                level=raw.get("level") or "info",
                message=str(raw.get("message") or ""),
            )
        )
    return entries


@dataclass
class BundleSummary:
    id: str
    cluster_id: str
    cluster_name: str
    customer_name: str
    created_at: str
    line_count: int
    node_count: int
    archive_path: str | None
    log_time_start: str | None = None
    log_time_end: str | None = None


def list_customers() -> list[dict[str, str | int | None]]:
    by_name: dict[str, list[BundleSummary]] = {}
    for b in list_bundles():
        if not b.customer_name:
            continue
        by_name.setdefault(b.customer_name, []).append(b)
    out: list[dict[str, str | int | None]] = []
    for name in sorted(by_name.keys(), key=str.lower):
        bundles = sorted(by_name[name], key=lambda x: x.created_at, reverse=True)
        latest = bundles[0]
        out.append(
            {
                "name": name,
                "bundle_count": len(bundles),
                "latest_bundle_id": latest.id,
                "latest_cluster_id": latest.cluster_id,
            }
        )
    return out


def list_bundles(
    cluster_id: str | None = None,
    customer_name: str | None = None,
) -> list[BundleSummary]:
    root = bundles_root()
    out: list[BundleSummary] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name, reverse=True):
        if not child.is_dir():
            continue
        manifest = load_manifest(child.name)
        if not manifest:
            continue
        cid = str(manifest.get("cluster_id") or "")
        cname = str(manifest.get("customer_name") or "")
        if cluster_id and cid != cluster_id:
            continue
        if customer_name and cname != customer_name:
            continue
        archive = child / "bundle.tar.gz"
        out.append(
            BundleSummary(
                id=child.name,
                cluster_id=cid,
                cluster_name=str(manifest.get("cluster_name") or cid),
                customer_name=cname,
                created_at=str(manifest.get("created_at") or ""),
                line_count=int(manifest.get("line_count") or 0),
                node_count=len(manifest.get("nodes") or []),
                archive_path=str(archive) if archive.is_file() else None,
                log_time_start=manifest.get("log_time_start"),
                log_time_end=manifest.get("log_time_end"),
            )
        )
    return out
