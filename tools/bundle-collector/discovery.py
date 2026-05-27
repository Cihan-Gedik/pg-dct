"""Auto-discover Patroni (Docker) and local PostgreSQL environments."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Literal

EnvKind = Literal["docker_patroni", "local_postgresql"]


@dataclass
class DiscoveredTarget:
    kind: EnvKind
    label: str
    patroni_scope: str
    docker_hosts: dict[str, str] = field(default_factory=dict)
    nodes: list[dict[str, str]] = field(default_factory=list)
    patroni_url: str | None = None
    detail: str = ""


def _run(cmd: list[str], timeout: float = 30.0) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return 127, str(exc)


def has_docker() -> bool:
    code, _ = _run(["docker", "info"], timeout=15)
    return code == 0


def has_local_postgresql() -> bool:
    for cmd in (
        ["pg_isready", "-h", "127.0.0.1", "-p", "5432"],
        ["pg_isready", "-h", "localhost"],
    ):
        code, out = _run(cmd, timeout=5)
        if code == 0 or "accepting connections" in out.lower():
            return True
    code, out = _run(["psql", "-Atqc", "SELECT 1"], timeout=8)
    return code == 0 and "1" in out


def list_docker_container_names() -> list[str]:
    code, out = _run(["docker", "ps", "--format", "{{.Names}}"])
    if code != 0:
        return []
    return [n.strip() for n in out.splitlines() if n.strip()]


def container_ip(container: str) -> str:
    code, out = _run(
        ["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}", container],
        timeout=10,
    )
    if code != 0:
        return ""
    for part in out.split():
        if part and re.match(r"^\d+\.\d+\.\d+\.\d+$", part):
            return part
    return ""


def patroni_cluster_from_container(container: str) -> dict[str, Any] | None:
    code, out = _run(
        ["docker", "exec", container, "curl", "-sf", "-m", "5", "http://127.0.0.1:8008/cluster"],
        timeout=12,
    )
    if code != 0 or not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def discover_docker_patroni_clusters() -> list[DiscoveredTarget]:
    names = list_docker_container_names()
    patroni_nodes: list[tuple[str, str, dict[str, Any]]] = []
    for name in names:
        data = patroni_cluster_from_container(name)
        if not data or not data.get("members"):
            continue
        ip = container_ip(name)
        patroni_nodes.append((name, ip, data))

    if not patroni_nodes:
        return []

    ip_to_container = {ip: name for name, ip, _ in patroni_nodes if ip}
    scopes: dict[str, list[tuple[str, str, dict[str, Any]]]] = {}
    for name, ip, data in patroni_nodes:
        scope = str(data.get("scope") or data.get("cluster") or "patroni-cluster")
        scopes.setdefault(scope, []).append((name, ip, data))

    targets: list[DiscoveredTarget] = []
    for scope, group in scopes.items():
        docker_hosts: dict[str, str] = {}
        nodes: list[dict[str, str]] = []
        members_seen: set[str] = set()

        for _name, _ip, data in group:
            for member in data.get("members") or []:
                if not isinstance(member, dict):
                    continue
                host = str(member.get("host") or "")
                member_name = str(member.get("name") or host)
                if not host:
                    continue
                if host in members_seen:
                    continue
                members_seen.add(host)
                container = ip_to_container.get(host) or group[0][0]
                docker_hosts[host] = container
                nodes.append({"host": host, "member_name": member_name})

        if not docker_hosts:
            continue

        leader_host = ""
        for _name, _ip, data in group:
            for member in data.get("members") or []:
                if isinstance(member, dict) and member.get("role") == "leader":
                    leader_host = str(member.get("host") or "")
                    break
            if leader_host:
                break
        if not leader_host:
            leader_host = next(iter(docker_hosts.keys()), "")

        targets.append(
            DiscoveredTarget(
                kind="docker_patroni",
                label=f"Docker Patroni — {scope} ({len(docker_hosts)} nodes)",
                patroni_scope=scope,
                docker_hosts=docker_hosts,
                nodes=nodes,
                patroni_url=f"http://{leader_host}:8008" if leader_host else None,
                detail=f"containers: {', '.join(sorted(set(docker_hosts.values())))}",
            )
        )
    return targets


def discover_local_postgresql() -> DiscoveredTarget | None:
    if not has_local_postgresql():
        return None
    return DiscoveredTarget(
        kind="local_postgresql",
        label="Local PostgreSQL (127.0.0.1:5432)",
        patroni_scope="local-postgresql",
        docker_hosts={},
        nodes=[{"host": "127.0.0.1", "member_name": "localhost"}],
        patroni_url=None,
        detail="Host-level log collection (no Docker)",
    )


def discover_all() -> list[DiscoveredTarget]:
    found: list[DiscoveredTarget] = []
    if has_docker():
        found.extend(discover_docker_patroni_clusters())
    local = discover_local_postgresql()
    if local:
        found.append(local)
    return found


def target_to_config(target: DiscoveredTarget, lines_per_source: int = 500) -> dict[str, Any]:
    return {
        "cluster_label": target.patroni_scope,
        "patroni_url": target.patroni_url,
        "lines_per_source": lines_per_source,
        "docker_hosts": target.docker_hosts,
        "nodes": target.nodes,
        "discovery": {
            "kind": target.kind,
            "label": target.label,
            "detail": target.detail,
        },
    }


def print_discovery_report(targets: list[DiscoveredTarget]) -> None:
    print("PG-DCT Bundle Collector — environment discovery\n")
    if not targets:
        print("No Patroni Docker clusters or local PostgreSQL detected.")
        print("  - Docker: ensure Patroni containers run and port 8008 answers inside the container")
        print("  - Local: ensure pg_isready / psql works on localhost")
        return
    print("Detected environments:\n")
    for i, t in enumerate(targets, 1):
        print(f"  [{i}] {t.label}")
        if t.detail:
            print(f"      {t.detail}")
        if t.docker_hosts:
            for host, c in sorted(t.docker_hosts.items()):
                print(f"      {host} -> {c}")
    print()


def prompt_select(targets: list[DiscoveredTarget]) -> DiscoveredTarget:
    if len(targets) == 1:
        print(f"Auto-selected: {targets[0].label}\n")
        return targets[0]
    print_discovery_report(targets)
    while True:
        try:
            raw = input(f"Select environment [1-{len(targets)}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.", file=sys.stderr)
            sys.exit(1)
        if not raw:
            continue
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(targets):
                return targets[idx]
        except ValueError:
            pass
        print("Invalid choice, try again.")


def resolve_target(
    *,
    discover_only: bool = False,
    non_interactive: bool = False,
    target_index: int | None = None,
    target_kind: str | None = None,
    target_scope: str | None = None,
) -> DiscoveredTarget | None:
    targets = discover_all()
    if discover_only:
        print_discovery_report(targets)
        return None
    if not targets:
        return None
    if target_scope:
        for t in targets:
            if t.patroni_scope == target_scope:
                return t
        raise SystemExit(f"No cluster with scope '{target_scope}' found")
    if target_kind:
        filtered = [t for t in targets if t.kind == target_kind]
        if not filtered:
            raise SystemExit(f"No environment of kind '{target_kind}'")
        targets = filtered
    if target_index is not None:
        if not (1 <= target_index <= len(targets)):
            raise SystemExit(f"--pick must be 1..{len(targets)}")
        return targets[target_index - 1]
    if non_interactive:
        return targets[0]
    return prompt_select(targets)
