#!/usr/bin/env python3
"""
PG-DCT bundle collector — run on the customer site.

Auto-discovers Docker Patroni clusters or local PostgreSQL, collects logs, outputs bundle_*.tar.gz.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from discovery import discover_all, print_discovery_report, resolve_target, target_to_config

LogSource = Literal["patroni", "postgres", "etcd", "os"]
LogLevel = Literal["critical", "warning", "info"]

LEVEL_PATTERNS: list[tuple[re.Pattern[str], LogLevel]] = [
    (re.compile(r"\b(FATAL|CRITICAL|PANIC)\b", re.I), "critical"),
    (re.compile(r"\b(ERROR|ERR)\b", re.I), "critical"),
    (re.compile(r"\b(WARNING|WARN)\b", re.I), "warning"),
]

DOCKER_SOURCE_COMMANDS: dict[LogSource, list[str]] = {
    "patroni": ["journalctl", "-u", "patroni", "-n", "{n}", "--no-pager", "-o", "short-iso"],
    "postgres": [
        "bash",
        "-c",
        "tail -n {n} /var/log/postgresql/*.log 2>/dev/null; "
        "tail -n {n} /pg/pglogs/postgresql*.log 2>/dev/null; "
        "tail -n {n} /var/lib/pgsql/*/log/*.log 2>/dev/null",
    ],
    "etcd": ["journalctl", "-u", "etcd", "-n", "{n}", "--no-pager", "-o", "short-iso"],
    "os": ["journalctl", "-n", "{n}", "--no-pager", "-o", "short-iso"],
}

LOCAL_SOURCE_COMMANDS: dict[LogSource, list[str]] = {
    "patroni": ["journalctl", "-u", "patroni", "-n", "{n}", "--no-pager", "-o", "short-iso"],
    "postgres": [
        "bash",
        "-c",
        "tail -n {n} /var/log/postgresql/*.log 2>/dev/null; "
        "tail -n {n} /opt/homebrew/var/log/postgresql*.log 2>/dev/null; "
        "tail -n {n} /usr/local/var/log/postgresql*.log 2>/dev/null; "
        "tail -n {n} ~/Library/Logs/Homebrew/postgresql*.log 2>/dev/null",
    ],
    "etcd": ["journalctl", "-u", "etcd", "-n", "{n}", "--no-pager", "-o", "short-iso"],
    "os": ["journalctl", "-n", "{n}", "--no-pager", "-o", "short-iso"],
}

_JOURNAL_ISO_PREFIX = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{4}|[+-]\d{2}:\d{2}))\s+",
)


@dataclass
class LogEntry:
    ts: str
    node: str
    member_name: str
    source: LogSource
    level: LogLevel
    message: str


def classify_level(line: str) -> LogLevel:
    for pattern, level in LEVEL_PATTERNS:
        if pattern.search(line):
            return level
    return "info"


def parse_journal_line(line: str) -> tuple[str, str]:
    line = line.strip()
    if not line:
        return "", ""
    iso_host = _JOURNAL_ISO_PREFIX.match(line)
    if iso_host:
        return iso_host.group(1), line[iso_host.end() :].strip()
    parts = line.split(" ", 2)
    if len(parts) >= 3 and parts[0].count("-") >= 2 and "T" not in parts[0]:
        return f"{parts[0]} {parts[1]}", parts[2]
    return "", line


def run_cmd(cmd: list[str], timeout: float = 60.0) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return ""
    return (proc.stdout or "") + (proc.stderr or "")


def docker_exec(container: str, cmd: list[str], timeout: float = 60.0) -> str:
    return run_cmd(["docker", "exec", container, *cmd], timeout=timeout)


def fetch_source_logs_docker(
    container: str,
    source: LogSource,
    lines: int,
    member_name: str,
    node_host: str,
) -> list[LogEntry]:
    template = DOCKER_SOURCE_COMMANDS[source]
    cmd = [part.format(n=lines) if "{n}" in part else part for part in template]
    return _parse_log_output(docker_exec(container, cmd), source, member_name, node_host)


def fetch_source_logs_local(
    source: LogSource,
    lines: int,
    member_name: str,
    node_host: str,
) -> list[LogEntry]:
    template = LOCAL_SOURCE_COMMANDS[source]
    cmd = [part.format(n=lines) if "{n}" in part else part for part in template]
    return _parse_log_output(run_cmd(cmd), source, member_name, node_host)


def _parse_log_output(raw: str, source: LogSource, member_name: str, node_host: str) -> list[LogEntry]:
    entries: list[LogEntry] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("-- No entries"):
            continue
        ts, msg = parse_journal_line(line)
        if not msg:
            msg = line
        entries.append(
            LogEntry(
                ts=ts or "",
                node=node_host,
                member_name=member_name,
                source=source,
                level=classify_level(msg),
                message=msg,
            )
        )
    return entries


def fetch_patroni_snapshot(url: str) -> list[dict[str, Any]] | dict[str, Any]:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/cluster", timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return list(data.get("members") or [])
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"error": str(exc)}


def fetch_patroni_snapshot_docker(leader_container: str) -> list[dict[str, Any]] | dict[str, Any]:
    raw = docker_exec(leader_container, ["curl", "-sf", "-m", "5", "http://127.0.0.1:8008/cluster"])
    if not raw:
        return {"error": "patroni API unreachable in container"}
    try:
        data = json.loads(raw)
        return list(data.get("members") or [])
    except json.JSONDecodeError as exc:
        return {"error": str(exc)}


def load_config(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise SystemExit("PyYAML required for YAML config: pip install pyyaml") from exc
        return yaml.safe_load(text) or {}
    return json.loads(text)


def collect_bundle(cfg: dict[str, Any], lines: int, sources: list[LogSource]) -> tuple[dict[str, Any], list[LogEntry]]:
    docker_hosts: dict[str, str] = {str(k): str(v) for k, v in (cfg.get("docker_hosts") or {}).items()}
    discovery = cfg.get("discovery") or {}
    is_local = discovery.get("kind") == "local_postgresql" or (not docker_hosts and cfg.get("local_mode"))

    nodes_cfg = cfg.get("nodes") or []
    node_payload: list[dict[str, str]] = []
    if nodes_cfg:
        for n in nodes_cfg:
            host = str(n.get("host") or "")
            member = str(n.get("member_name") or host)
            if is_local or host in docker_hosts:
                node_payload.append({"host": host, "member_name": member})
    elif docker_hosts:
        for host, container in docker_hosts.items():
            node_payload.append({"host": host, "member_name": container})
    elif is_local:
        node_payload.append({"host": "127.0.0.1", "member_name": "localhost"})

    if not node_payload:
        raise SystemExit("No nodes to collect — run discovery or fix config.yaml")

    entries: list[LogEntry] = []
    for node in node_payload:
        host = node["host"]
        member = node["member_name"]
        container = docker_hosts.get(host)
        for source in sources:
            if container:
                entries.extend(fetch_source_logs_docker(container, source, lines, member, host))
            else:
                entries.extend(fetch_source_logs_local(source, lines, member, host))

    entries.sort(key=lambda e: e.ts or e.message, reverse=True)

    patroni_snapshot: object = []
    if docker_hosts:
        leader_container = next(iter(docker_hosts.values()))
        patroni_snapshot = fetch_patroni_snapshot_docker(leader_container)
    else:
        patroni_url = cfg.get("patroni_url") or cfg.get("patroni_seed_url")
        if patroni_url:
            patroni_snapshot = fetch_patroni_snapshot(str(patroni_url))

    scope = str(cfg.get("cluster_label") or cfg.get("name") or discovery.get("patroni_scope") or "cluster")
    manifest: dict[str, Any] = {
        "collector": "pg-dct-bundle-collector",
        "collector_version": "2.0.0",
        "cluster_label": scope,
        "patroni_scope": scope,
        "created_at": datetime.now(UTC).isoformat(),
        "lines_per_source": lines,
        "sources": list(sources),
        "nodes": [
            {
                "host": n["host"],
                "container": docker_hosts.get(n["host"]),
                "member_name": n["member_name"],
            }
            for n in node_payload
        ],
        "patroni_snapshot": patroni_snapshot,
        "hostname": subprocess.getoutput("hostname").strip(),
        "discovery": discovery,
    }
    return manifest, entries


def write_outputs(manifest: dict[str, Any], entries: list[LogEntry], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest["line_count"] = len(entries)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with (out_dir / "logs.jsonl").open("w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(
                json.dumps(
                    {
                        "ts": e.ts,
                        "node": e.node,
                        "member_name": e.member_name,
                        "source": e.source,
                        "level": e.level,
                        "message": e.message,
                    },
                    ensure_ascii=False,
                )
            )
            fh.write("\n")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive = out_dir.parent / f"bundle_{stamp}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(out_dir / "manifest.json", arcname="manifest.json")
        tar.add(out_dir / "logs.jsonl", arcname="logs.jsonl")
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PG-DCT bundle collector with environment discovery",
    )
    parser.add_argument("-c", "--config", type=Path, default=None, help="optional config.yaml (skips discovery)")
    parser.add_argument("-o", "--output-dir", type=Path, default=Path("."), help="output directory")
    parser.add_argument("-n", "--lines", type=int, default=500, help="lines per source")
    parser.add_argument("--sources", default="patroni,postgres,etcd,os")
    parser.add_argument("--discover", action="store_true", help="only list detected environments")
    parser.add_argument("-y", "--yes", action="store_true", help="non-interactive: pick first environment")
    parser.add_argument("--pick", type=int, default=None, help="pick environment by index from discovery")
    args = parser.parse_args()

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    valid: list[LogSource] = [s for s in sources if s in ("patroni", "postgres", "etcd", "os")]  # type: ignore[misc]
    valid = valid or ["patroni", "postgres", "etcd", "os"]

    if args.discover:
        print_discovery_report(discover_all())
        return

    if args.config and args.config.is_file():
        cfg = load_config(args.config)
        lines = args.lines or int(cfg.get("lines_per_source") or 500)
    else:
        print("Scanning for Docker Patroni clusters and local PostgreSQL…\n")
        target = resolve_target(
            discover_only=False,
            non_interactive=args.yes,
            target_index=args.pick,
        )
        if target is None:
            print_discovery_report(discover_all())
            sys.exit(1)
        cfg = target_to_config(target, lines_per_source=args.lines)
        lines = args.lines
        print(f"Collecting from: {target.label}\n")

    work = args.output_dir / ".pgdct-bundle-work"
    if work.exists():
        shutil.rmtree(work)
    manifest, entries = collect_bundle(cfg, lines, valid)
    archive = write_outputs(manifest, entries, work)
    print(f"OK  {archive}")
    print(f"    cluster={manifest.get('patroni_scope')}  lines={len(entries)}  nodes={len(manifest.get('nodes') or [])}")
    print("Send this .tar.gz to your support team. Import in PG-DCT with your customer name (Müşteri adı).")


if __name__ == "__main__":
    main()
