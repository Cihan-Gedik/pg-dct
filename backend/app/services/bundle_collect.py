"""Collect troubleshooting bundles from Patroni lab containers."""

from __future__ import annotations

import tarfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Cluster
from app.services.cluster_config import load_cluster_docker_hosts
from app.services.docker_logs import fetch_cluster_logs
from app.services.bundle_store import new_bundle_id, write_bundle
from app.services.patroni import PatroniDiscoveryError, fetch_cluster_members


async def collect_cluster_bundle(
    session: AsyncSession,
    cluster_id: str,
    *,
    lines_per_source: int = 500,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    result = await session.execute(
        select(Cluster).where(Cluster.id == cluster_id).options(selectinload(Cluster.nodes))
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise ValueError(f"Cluster not found: {cluster_id}")

    docker_hosts = load_cluster_docker_hosts(cluster_id)
    if not docker_hosts:
        raise ValueError(f"No docker_hosts for cluster {cluster_id} in config/docker-clusters.yaml")

    active_sources = sources or ["patroni", "postgres", "etcd", "os"]
    node_payload = [{"host": n.host, "member_name": n.member_name} for n in cluster.nodes]
    if not node_payload:
        node_payload = [{"host": host, "member_name": container} for host, container in docker_hosts.items()]

    patroni_members: list[dict[str, Any]] = []
    try:
        _scope, members_raw = await fetch_cluster_members(cluster.patroni_seed_url)
        patroni_members = members_raw
    except PatroniDiscoveryError as exc:
        patroni_members = [{"error": str(exc)}]

    entries = await fetch_cluster_logs(node_payload, docker_hosts, active_sources, lines_per_source)

    bundle_id = new_bundle_id(cluster_id)
    manifest: dict[str, Any] = {
        "cluster_id": cluster_id,
        "cluster_name": cluster.name,
        "created_at": datetime.now(UTC).isoformat(),
        "lines_per_source": lines_per_source,
        "sources": active_sources,
        "nodes": [
            {
                "host": host,
                "container": container,
                "member_name": next(
                    (n["member_name"] for n in node_payload if n["host"] == host),
                    container,
                ),
            }
            for host, container in sorted(docker_hosts.items())
        ],
        "patroni_snapshot": patroni_members,
    }
    dest = write_bundle(bundle_id, manifest, entries)
    archive_path = _write_tarball(dest, bundle_id)

    return {
        "ok": True,
        "bundle_id": bundle_id,
        "cluster_id": cluster_id,
        "line_count": len(entries),
        "path": str(dest),
        "archive_path": str(archive_path) if archive_path else None,
        "manifest": manifest,
    }


def _write_tarball(dest: Path, bundle_id: str) -> Path | None:
    archive = dest / "bundle.tar.gz"
    try:
        with tarfile.open(archive, "w:gz") as tar:
            for item in dest.iterdir():
                if item.name == "bundle.tar.gz":
                    continue
                tar.add(item, arcname=f"{bundle_id}/{item.name}")
        return archive
    except OSError:
        return None
