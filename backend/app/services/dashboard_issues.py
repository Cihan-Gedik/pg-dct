"""Aggregate critical / warning issues for the dashboard."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Cluster
from app.services.cluster_config import load_cluster_docker_hosts
from app.services.docker_logs import fetch_cluster_logs
from app.services.live_sync import build_alerts, check_docker_hosts_health, merge_missing_members
from app.services.patroni import PatroniDiscoveryError, fetch_cluster_members

IssueLevel = Literal["critical", "warning"]
IssueKind = Literal["cluster", "log"]


def _issue_id(cluster_id: str, kind: str, key: str) -> str:
    digest = hashlib.sha256(f"{cluster_id}:{kind}:{key}".encode()).hexdigest()[:12]
    return f"{cluster_id}-{digest}"


_NORMALIZE_PATTERNS = [
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.\d+Z]*"), "<ts>"),
    (re.compile(r"\d+\.\d+\.\d+\.\d+"), "<ip>"),
    (re.compile(r'"ts":"[^"]*"'), '"ts":"…"'),
    (re.compile(r'"rtt":"[^"]*"'), '"rtt":"…"'),
    (re.compile(r"\s+"), " "),
]


def normalize_message(message: str) -> str:
    text = message.strip()
    for pattern, repl in _NORMALIZE_PATTERNS:
        text = pattern.sub(repl, text)
    return text[:240]


def issue_fingerprint(issue: dict) -> str:
    body = normalize_message(str(issue.get("detail") or issue.get("message") or ""))
    return "|".join(
        [
            str(issue.get("cluster_id") or ""),
            str(issue.get("level") or ""),
            str(issue.get("category") or ""),
            str(issue.get("kind") or ""),
            str(issue.get("member_name") or ""),
            str(issue.get("source") or ""),
            body,
        ]
    )


def dedupe_issues(issues: list[dict]) -> list[dict]:
    """Merge repeated log lines into one row with occurrence_count."""
    grouped: dict[str, dict] = {}
    for issue in issues:
        fp = issue_fingerprint(issue)
        if fp not in grouped:
            grouped[fp] = {
                **issue,
                "id": _issue_id(str(issue.get("cluster_id") or ""), "group", fp),
                "occurrence_count": 1,
                "last_seen": issue.get("ts"),
                "first_seen": issue.get("ts"),
            }
            continue
        row = grouped[fp]
        row["occurrence_count"] = int(row.get("occurrence_count", 1)) + 1
        ts = issue.get("ts")
        if ts:
            if not row.get("first_seen") or ts < str(row["first_seen"]):
                row["first_seen"] = ts
            if not row.get("last_seen") or ts > str(row["last_seen"]):
                row["last_seen"] = ts
    return list(grouped.values())


def _categorize(source: str, message: str) -> str:
    msg = message.lower()
    if source == "etcd" or "etcd" in msg or ":2380" in msg:
        return "etcd"
    if source == "patroni" or "patroni" in msg:
        return "patroni"
    if source == "postgres" or "postgresql" in msg:
        return "postgres"
    if "quorum" in msg or "unreachable" in msg or "down" in msg:
        return "cluster"
    return source or "other"


async def collect_issues_for_cluster(cluster: Cluster) -> list[dict]:
    issues: list[dict] = []
    docker_hosts = load_cluster_docker_hosts(cluster.id)
    member_names = [n.member_name for n in cluster.nodes]

    try:
        _scope, members_raw = await fetch_cluster_members(cluster.patroni_seed_url)
    except PatroniDiscoveryError as exc:
        issues.append(
            {
                "id": _issue_id(cluster.id, "cluster", "patroni_unreachable"),
                "cluster_id": cluster.id,
                "cluster_name": cluster.name,
                "level": "critical",
                "kind": "cluster",
                "category": "patroni",
                "member_name": None,
                "host": None,
                "source": "patroni",
                "title": "Patroni API unreachable",
                "message": str(exc),
                "ts": None,
                "detail": f"Seed URL: {cluster.patroni_seed_url}",
            }
        )
        return issues

    host_to_member = {n.host: n.member_name for n in cluster.nodes}
    times_as_leader: dict[str, int] = {}
    members_merged = merge_missing_members(members_raw, docker_hosts, host_to_member, times_as_leader)
    container_health = await check_docker_hosts_health(docker_hosts) if docker_hosts else {}

    for alert in build_alerts(members_merged, docker_hosts, container_health):
        issues.append(
            {
                "id": _issue_id(cluster.id, "cluster", alert),
                "cluster_id": cluster.id,
                "cluster_name": cluster.name,
                "level": "critical",
                "kind": "cluster",
                "category": "cluster",
                "member_name": None,
                "host": None,
                "source": "cluster",
                "title": "Cluster health",
                "message": alert,
                "ts": None,
                "detail": alert,
            }
        )

    for m in members_merged:
        if str(m.get("role")) == "unreachable":
            host = str(m.get("host") or "")
            name = str(m.get("name") or "")
            issues.append(
                {
                    "id": _issue_id(cluster.id, "cluster", f"down-{host}"),
                    "cluster_id": cluster.id,
                    "cluster_name": cluster.name,
                    "level": "critical",
                    "kind": "cluster",
                    "category": "patroni",
                    "member_name": name,
                    "host": host,
                    "source": "patroni",
                    "title": f"Node not in Patroni cluster",
                    "message": f"{name} ({host}) is unreachable or not reporting to Patroni.",
                    "ts": None,
                    "detail": "Check container and run scripts/heal-lab-node.sh if etcd/patroni are stopped.",
                }
            )

    if docker_hosts and member_names:
        node_payload = [{"host": n.host, "member_name": n.member_name} for n in cluster.nodes]
        if not node_payload:
            node_payload = [
                {"host": str(m.get("host") or ""), "member_name": str(m.get("name") or "")}
                for m in members_raw
            ]
        try:
            raw_logs = await fetch_cluster_logs(
                node_payload, docker_hosts, ["patroni", "postgres", "etcd", "os"], 50
            )
        except Exception:
            raw_logs = []

        for entry in raw_logs:
            if entry.level not in ("critical", "warning"):
                continue
            category = _categorize(entry.source, entry.message)
            title = f"{entry.level.upper()} · {entry.source} on {entry.member_name}"
            issues.append(
                {
                    "id": _issue_id(cluster.id, "log", entry.message[:80]),
                    "cluster_id": cluster.id,
                    "cluster_name": cluster.name,
                    "level": entry.level,
                    "kind": "log",
                    "category": category,
                    "member_name": entry.member_name,
                    "host": entry.node,
                    "source": entry.source,
                    "title": title,
                    "message": entry.message[:500],
                    "ts": entry.ts or None,
                    "detail": entry.message,
                }
            )

    return issues


async def collect_all_issues(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(Cluster).options(selectinload(Cluster.nodes)))
    clusters = result.scalars().all()
    if not clusters:
        return []

    import asyncio

    batches = await asyncio.gather(
        *[collect_issues_for_cluster(c) for c in clusters],
        return_exceptions=True,
    )
    merged: list[dict] = []
    for batch in batches:
        if isinstance(batch, list):
            merged.extend(batch)
    return sort_issues(dedupe_issues(merged))


def sort_issues(issues: list[dict]) -> list[dict]:
    critical = sorted(
        [i for i in issues if i["level"] == "critical"],
        key=lambda i: i.get("ts") or "",
        reverse=True,
    )
    warning = sorted(
        [i for i in issues if i["level"] == "warning"],
        key=lambda i: i.get("ts") or "",
        reverse=True,
    )
    return critical + warning
