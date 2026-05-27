"""Import customer bundle .tar.gz into PG-DCT storage."""

from __future__ import annotations

import json
import re
import shutil
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Cluster, Node
from app.services.bundle_store import new_bundle_id, write_bundle
from app.services.docker_logs import LogEntry, parse_log_timestamp


def slugify_cluster_id(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9-_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    if not s or not re.match(r"^[a-z0-9]", s):
        s = f"import-{s}" if s else "imported-cluster"
    return s[:63]


def compute_log_time_range(entries: list[LogEntry]) -> tuple[str | None, str | None]:
    times: list[datetime] = []
    for entry in entries:
        dt = parse_log_timestamp(entry.ts)
        if dt is not None:
            times.append(dt)
    if not times:
        return None, None
    start = min(times).astimezone(UTC).isoformat()
    end = max(times).astimezone(UTC).isoformat()
    return start, end


def _extract_bundle_archive(archive_path: Path) -> tuple[Path, Path]:
    """Return (work_root_for_cleanup, dir_with_manifest_and_logs)."""
    root = Path(tempfile.mkdtemp(prefix="pgdct-import-"))
    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(root, filter="data")
    if (root / "manifest.json").is_file():
        return root, root
    for child in root.iterdir():
        if child.is_dir() and (child / "manifest.json").is_file():
            return root, child
    shutil.rmtree(root, ignore_errors=True)
    raise ValueError("Archive must contain manifest.json and logs.jsonl at top level or in one folder")


def _read_manifest_and_logs(extracted: Path) -> tuple[dict[str, Any], list[LogEntry]]:
    manifest_path = extracted / "manifest.json"
    logs_path = extracted / "logs.jsonl"
    if not manifest_path.is_file():
        raise ValueError("manifest.json missing in bundle")
    if not logs_path.is_file():
        raise ValueError("logs.jsonl missing in bundle")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries: list[LogEntry] = []
    for line in logs_path.read_text(encoding="utf-8").splitlines():
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
    return manifest, entries


async def upsert_imported_cluster(
    session: AsyncSession,
    cluster_id: str,
    cluster_name: str,
    manifest: dict[str, Any],
) -> Cluster:
    placeholder_url = "http://127.0.0.1:1/imported"
    result = await session.execute(select(Cluster).where(Cluster.id == cluster_id))
    cluster = result.scalar_one_or_none()
    if cluster:
        cluster.name = cluster_name
        await session.flush()
    else:
        cluster = Cluster(
            id=cluster_id,
            name=cluster_name,
            engine="postgresql",
            patroni_scope=cluster_id,
            patroni_seed_url=placeholder_url,
            poll_interval_sec=60,
        )
        session.add(cluster)
        await session.flush()

    # Sync nodes from manifest for UI filters (optional)
    nodes_raw = manifest.get("nodes") or []
    if nodes_raw:
        node_rows = await session.execute(select(Node).where(Node.cluster_id == cluster_id))
        existing = {n.host: n for n in node_rows.scalars()}
        for raw in nodes_raw:
            if not isinstance(raw, dict):
                continue
            host = str(raw.get("host") or "")
            member = str(raw.get("member_name") or host)
            if not host:
                continue
            if host in existing:
                existing[host].member_name = member
            else:
                session.add(
                    Node(
                        cluster_id=cluster_id,
                        member_name=member,
                        host=host,
                        role="unknown",
                        state=None,
                    )
                )
    await session.flush()
    return cluster


def cluster_name_from_manifest(manifest: dict[str, Any]) -> str:
    for key in ("patroni_scope", "cluster_label", "cluster_name"):
        val = str(manifest.get(key) or "").strip()
        if val:
            return val
    disc = manifest.get("discovery") or {}
    if isinstance(disc, dict):
        val = str(disc.get("patroni_scope") or disc.get("label") or "").strip()
        if val:
            return val
    return "imported-cluster"


async def import_bundle_archive(
    session: AsyncSession,
    archive_bytes: bytes,
    customer_name: str,
    cluster_name: str | None = None,
    cluster_id: str | None = None,
) -> dict[str, Any]:
    customer_name = customer_name.strip()
    if not customer_name:
        raise ValueError("Customer name (müşteri adı) is required")

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmpf:
        tmpf.write(archive_bytes)
        tmp_path = Path(tmpf.name)

    work_root: Path | None = None
    try:
        work_root, extracted = _extract_bundle_archive(tmp_path)
        manifest, entries = _read_manifest_and_logs(extracted)
        if not entries:
            raise ValueError("Bundle contains no log lines")

        resolved_cluster_name = (cluster_name or "").strip() or cluster_name_from_manifest(manifest)
        cid = (cluster_id or "").strip() or slugify_cluster_id(resolved_cluster_name)
        if not re.match(r"^[a-z0-9][a-z0-9-_]{1,62}$", cid):
            raise ValueError("Invalid cluster id; use lowercase letters, numbers, hyphens")

        log_start, log_end = compute_log_time_range(entries)
        bundle_id = new_bundle_id(cid)
        manifest["cluster_id"] = cid
        manifest["cluster_name"] = resolved_cluster_name
        manifest["customer_name"] = customer_name
        manifest["imported_at"] = datetime.now(UTC).isoformat()
        manifest["log_time_start"] = log_start
        manifest["log_time_end"] = log_end
        manifest["source"] = manifest.get("source") or manifest.get("collector") or "customer-import"

        dest = write_bundle(bundle_id, manifest, entries)
        # Keep original customer archive
        shutil.copy2(tmp_path, dest / "bundle.tar.gz")

        await upsert_imported_cluster(session, cid, resolved_cluster_name, manifest)
        await session.commit()

        message = f"Imported {len(entries)} log lines for customer «{customer_name}»"
        if log_start and log_end:
            message += f" (log window: {log_start} → {log_end})"

        return {
            "ok": True,
            "bundle_id": bundle_id,
            "cluster_id": cid,
            "cluster_name": resolved_cluster_name,
            "customer_name": customer_name,
            "line_count": len(entries),
            "log_time_start": log_start,
            "log_time_end": log_end,
            "message": message,
        }
    finally:
        tmp_path.unlink(missing_ok=True)
        if work_root is not None:
            shutil.rmtree(work_root, ignore_errors=True)
