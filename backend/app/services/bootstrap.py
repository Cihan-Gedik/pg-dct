"""Load cluster definitions from YAML (Docker lab, etc.)."""

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Cluster
from app.schemas import ClusterCreate


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_clusters_path() -> Path:
    return _repo_root() / "config" / "docker-clusters.yaml"


def load_clusters_yaml(path: Path | None = None) -> list[dict[str, Any]]:
    file_path = path or default_clusters_path()
    if not file_path.is_file():
        return []
    data = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    clusters = data.get("clusters")
    if not isinstance(clusters, list):
        return []
    return clusters


async def upsert_cluster_from_dict(session: AsyncSession, raw: dict[str, Any]) -> Cluster:
    body = ClusterCreate(
        id=str(raw["id"]),
        name=str(raw.get("name") or raw["id"]),
        engine=str(raw.get("engine") or "postgresql"),
        patroni_scope=raw.get("patroni_scope"),
        patroni_seed_url=raw["patroni_seed_url"],
        etcd_endpoints=raw.get("etcd_endpoints"),
        poll_interval_sec=int(raw.get("poll_interval_sec") or 5),
    )
    import json

    existing = await session.get(Cluster, body.id)
    etcd_json = json.dumps(body.etcd_endpoints) if body.etcd_endpoints else None
    if existing:
        existing.name = body.name
        existing.engine = body.engine
        existing.patroni_scope = body.patroni_scope or body.id
        existing.patroni_seed_url = str(body.patroni_seed_url)
        existing.etcd_endpoints = etcd_json
        existing.poll_interval_sec = body.poll_interval_sec
        return existing

    cluster = Cluster(
        id=body.id,
        name=body.name,
        engine=body.engine,
        patroni_scope=body.patroni_scope or body.id,
        patroni_seed_url=str(body.patroni_seed_url),
        etcd_endpoints=etcd_json,
        poll_interval_sec=body.poll_interval_sec,
    )
    session.add(cluster)
    return cluster


async def bootstrap_clusters(session: AsyncSession, path: Path | None = None) -> list[str]:
    loaded: list[str] = []
    for raw in load_clusters_yaml(path):
        if not raw.get("id") or not raw.get("patroni_seed_url"):
            continue
        await upsert_cluster_from_dict(session, raw)
        loaded.append(str(raw["id"]))
    if loaded:
        await session.commit()
    return loaded
