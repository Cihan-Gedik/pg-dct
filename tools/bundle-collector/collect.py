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
import socket
import subprocess
import sys
import tarfile
import tempfile
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

_LOCAL_HOST_ALIASES = {"127.0.0.1", "localhost", socket.gethostname(), socket.getfqdn()}

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


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    try:
        raw = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    if not raw:
        return default
    return raw in {"y", "yes"}


def ask_text(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


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


def ssh_exec(
    host: str,
    cmd: list[str],
    timeout: float = 60.0,
    known_hosts_file: str | None = None,
) -> str:
    opts = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=5"]
    if known_hosts_file:
        opts += ["-o", "StrictHostKeyChecking=accept-new", "-o", f"UserKnownHostsFile={known_hosts_file}"]
    return run_cmd(
        ["ssh", *opts, host, *cmd],
        timeout=timeout,
    )


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


def fetch_source_logs_ssh(
    ssh_target: str,
    source: LogSource,
    lines: int,
    member_name: str,
    node_host: str,
    known_hosts_file: str | None = None,
) -> list[LogEntry]:
    template = LOCAL_SOURCE_COMMANDS[source]
    cmd = [part.format(n=lines) if "{n}" in part else part for part in template]
    return _parse_log_output(
        ssh_exec(ssh_target, cmd, known_hosts_file=known_hosts_file),
        source,
        member_name,
        node_host,
    )


def fetch_custom_path_logs_local(
    source: LogSource,
    lines: int,
    member_name: str,
    node_host: str,
    custom_path: str,
) -> list[LogEntry]:
    cmd = ["bash", "-lc", f"tail -n {lines} {custom_path} 2>/dev/null"]
    return _parse_log_output(run_cmd(cmd), source, member_name, node_host)


def fetch_custom_path_logs_ssh(
    ssh_target: str,
    source: LogSource,
    lines: int,
    member_name: str,
    node_host: str,
    custom_path: str,
    known_hosts_file: str | None = None,
) -> list[LogEntry]:
    cmd = ["bash", "-lc", f"tail -n {lines} {custom_path} 2>/dev/null"]
    return _parse_log_output(
        ssh_exec(ssh_target, cmd, known_hosts_file=known_hosts_file),
        source,
        member_name,
        node_host,
    )


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


def collect_bundle(
    cfg: dict[str, Any],
    lines: int,
    sources: list[LogSource],
    *,
    interactive: bool = True,
) -> tuple[dict[str, Any], list[LogEntry]]:
    docker_hosts: dict[str, str] = {str(k): str(v) for k, v in (cfg.get("docker_hosts") or {}).items()}
    ssh_hosts: dict[str, str] = {str(k): str(v) for k, v in (cfg.get("ssh_hosts") or {}).items()}
    discovery = cfg.get("discovery") or {}
    discovery_kind = str(discovery.get("kind") or "")
    is_local = discovery_kind == "local_postgresql" or (not docker_hosts and cfg.get("local_mode"))
    is_host_patroni = discovery_kind == "host_patroni" or (
        not docker_hosts and str(cfg.get("patroni_url") or cfg.get("patroni_seed_url") or "").strip() != ""
    )

    nodes_cfg = cfg.get("nodes") or []
    node_payload: list[dict[str, str]] = []
    if nodes_cfg:
        for n in nodes_cfg:
            host = str(n.get("host") or "")
            member = str(n.get("member_name") or host)
            if is_local or is_host_patroni or host in docker_hosts:
                node_payload.append({"host": host, "member_name": member})
    elif docker_hosts:
        for host, container in docker_hosts.items():
            node_payload.append({"host": host, "member_name": container})
    elif is_local:
        node_payload.append({"host": "127.0.0.1", "member_name": "localhost"})

    if not node_payload:
        raise SystemExit("No nodes to collect — run discovery or fix config.yaml")

    remote_hosts = [
        n["host"]
        for n in node_payload
        if n["host"] not in _LOCAL_HOST_ALIASES and n["host"] not in docker_hosts
    ]
    temp_known_hosts: str | None = None
    ssh_ready: dict[str, bool] = {}
    if remote_hosts:
        tmp = tempfile.NamedTemporaryFile(prefix="pgdct-known-hosts-", delete=False)
        temp_known_hosts = tmp.name
        tmp.close()
        for host in sorted(set(remote_hosts)):
            target = ssh_hosts.get(host) or host
            probe = ssh_exec(target, ["true"], known_hosts_file=temp_known_hosts, timeout=8)
            ssh_ready[host] = probe.strip() == ""
        if interactive:
            bad = [h for h, ok in ssh_ready.items() if not ok]
            if bad:
                print("\n[SSH] Some remote nodes are not reachable with key-based SSH:")
                for b in bad:
                    print(f"  - {b} (target: {ssh_hosts.get(b) or b})")
                print("You can configure key-based SSH or provide ssh_hosts mapping in config.yaml.")

    entries: list[LogEntry] = []
    skipped_nodes: list[dict[str, str]] = []
    for node in node_payload:
        host = node["host"]
        member = node["member_name"]
        container = docker_hosts.get(host)
        for source in sources:
            if container:
                entries.extend(fetch_source_logs_docker(container, source, lines, member, host))
                continue
            if host in _LOCAL_HOST_ALIASES:
                local_logs = fetch_source_logs_local(source, lines, member, host)
                if not local_logs and interactive:
                    custom_path = ask_text(
                        f"[{host}] No {source} logs found via journal/default paths. Enter custom log path (or empty to skip): "
                    )
                    if custom_path:
                        local_logs = fetch_custom_path_logs_local(source, lines, member, host, custom_path)
                entries.extend(local_logs)
                continue
            ssh_target = ssh_hosts.get(host) or host
            if ssh_ready and not ssh_ready.get(host, False):
                skipped_nodes.append({"host": host, "member_name": member, "source": source, "reason": "ssh_unreachable"})
                continue
            remote = fetch_source_logs_ssh(
                ssh_target,
                source,
                lines,
                member,
                host,
                known_hosts_file=temp_known_hosts,
            )
            if not remote and interactive:
                custom_path = ask_text(
                    f"[{host}] No {source} logs found via journal/default paths. Enter custom remote log path (or empty to skip): "
                )
                if custom_path:
                    remote = fetch_custom_path_logs_ssh(
                        ssh_target,
                        source,
                        lines,
                        member,
                        host,
                        custom_path,
                        known_hosts_file=temp_known_hosts,
                    )
            if remote:
                entries.extend(remote)
            else:
                skipped_nodes.append({"host": host, "member_name": member, "source": source})

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
        "skipped_nodes": skipped_nodes,
        "ssh_probe": ssh_ready,
    }
    if temp_known_hosts:
        Path(temp_known_hosts).unlink(missing_ok=True)
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
    parser.add_argument("--no-prompt", action="store_true", help="disable follow-up prompts for missing logs")
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
        if not args.yes:
            print("Loaded manual config.")
            if not ask_yes_no("Proceed with collection using this config?", default=True):
                print("Cancelled by user.")
                sys.exit(1)
    else:
        print("Scanning for host Patroni, Docker Patroni, and local PostgreSQL…\n")
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
        if not args.yes:
            print("Discovered nodes:")
            for n in cfg.get("nodes") or []:
                print(f"  - {n.get('member_name')} ({n.get('host')})")
            if not ask_yes_no("Start collecting logs from these nodes now?", default=True):
                print("Cancelled by user.")
                sys.exit(1)

    work = args.output_dir / ".pgdct-bundle-work"
    if work.exists():
        shutil.rmtree(work)
    manifest, entries = collect_bundle(
        cfg,
        lines,
        valid,
        interactive=(not args.yes and not args.no_prompt),
    )
    archive = write_outputs(manifest, entries, work)
    print(f"OK  {archive}")
    print(f"    cluster={manifest.get('patroni_scope')}  lines={len(entries)}  nodes={len(manifest.get('nodes') or [])}")
    skipped = manifest.get("skipped_nodes") or []
    if skipped:
        print(f"    skipped={len(skipped)} node/source attempts (see manifest.json)")
    ssh_probe = manifest.get("ssh_probe") or {}
    if ssh_probe:
        print("    ssh equivalency check done; temporary known_hosts was cleaned after collection.")
    print("Send this .tar.gz to your support team. Import in PG-DCT with your customer name (Müşteri adı).")


if __name__ == "__main__":
    main()
