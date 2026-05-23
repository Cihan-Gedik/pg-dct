"""Load per-cluster docker host map from YAML."""

from __future__ import annotations

import yaml

from app.services.bootstrap import default_clusters_path


def load_cluster_docker_hosts(cluster_id: str) -> dict[str, str]:
    path = default_clusters_path()
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for raw in data.get("clusters") or []:
        if str(raw.get("id")) == cluster_id:
            hosts = raw.get("docker_hosts") or {}
            return {str(k): str(v) for k, v in hosts.items()}
    return {}


def all_cluster_ids_from_yaml() -> list[str]:
    path = default_clusters_path()
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [str(c["id"]) for c in (data.get("clusters") or []) if c.get("id")]
