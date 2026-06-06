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


def load_cluster_pgbackrest(cluster_id: str) -> dict[str, str | bool]:
    """Optional pgBackRest block from docker-clusters.yaml."""
    path = default_clusters_path()
    if not path.is_file():
        return {"enabled": False, "stanza": ""}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for raw in data.get("clusters") or []:
        if str(raw.get("id")) != cluster_id:
            continue
        pgb = raw.get("pgbackrest") or {}
        if not isinstance(pgb, dict):
            pgb = {}
        stanza = str(pgb.get("stanza") or "").strip()
        if not stanza:
            stanza = str(raw.get("patroni_scope") or raw.get("id") or cluster_id).strip()
        docker_hosts = raw.get("docker_hosts") or {}
        enabled = bool(pgb.get("enabled", bool(docker_hosts)))
        return {"enabled": enabled, "stanza": stanza}
    return {"enabled": False, "stanza": ""}


def load_cluster_containers(cluster_id: str) -> list[str]:
    """Unique docker container names for a cluster (lab)."""
    hosts = load_cluster_docker_hosts(cluster_id)
    seen: set[str] = set()
    out: list[str] = []
    for name in hosts.values():
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out
