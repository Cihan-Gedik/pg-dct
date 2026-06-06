"""Fetch logs from Patroni lab containers via docker exec."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

LogSource = Literal["patroni", "postgres", "etcd", "os"]
LogLevel = Literal["critical", "warning", "info"]

# etcd on healthy nodes spams this when a peer is down but still in the raft group.
ETCD_PEER_REFUSED = re.compile(
    r"dial tcp (\d+\.\d+\.\d+\.\d+):2380: connect: connection refused",
    re.I,
)

LEVEL_PATTERNS: list[tuple[re.Pattern[str], LogLevel]] = [
    (re.compile(r"\b(FATAL|CRITICAL|PANIC)\b", re.I), "critical"),
    (re.compile(r"\b(ERROR|ERR)\b", re.I), "critical"),
    (re.compile(r"\b(WARNING|WARN)\b", re.I), "warning"),
]

SOURCE_COMMANDS: dict[LogSource, list[str]] = {
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


_JOURNAL_ISO_PREFIX = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{4}|[+-]\d{2}:\d{2}))\s+",
)


def normalize_log_timestamp(raw: str) -> str:
    """Extract a parseable ISO prefix from journal / API timestamp strings."""
    text = (raw or "").strip()
    if not text:
        return ""
    m = _JOURNAL_ISO_PREFIX.match(text + " ") if "T" in text[:20] else None
    if m:
        return m.group(1)
    m2 = re.match(
        r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{4}|[+-]\d{2}:\d{2})?)",
        text,
    )
    return m2.group(1) if m2 else text


def parse_log_timestamp(raw: str) -> datetime | None:
    """Parse log line timestamp to UTC; None if unknown."""
    text = normalize_log_timestamp(raw)
    if not text:
        return None
    if re.search(r"[+-]\d{4}$", text):
        text = f"{text[:-5]}{text[-5:-2]}:{text[-2:]}"
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def entry_within_hours(entry: LogEntry, hours: float) -> bool:
    dt = parse_log_timestamp(entry.ts)
    if dt is None:
        return False
    return dt >= datetime.now(UTC) - timedelta(hours=hours)


def parse_journal_line(line: str) -> tuple[str, str]:
    line = line.strip()
    if not line:
        return "", ""
    # journalctl short-iso on Patroni lab: 2026-05-23T14:02:01+0000 node2 bash[...]: msg
    iso_host = _JOURNAL_ISO_PREFIX.match(line)
    if iso_host:
        return iso_host.group(1), line[iso_host.end() :].strip()
    parts = line.split(" ", 2)
    if len(parts) >= 3 and parts[0].count("-") >= 2 and "T" not in parts[0]:
        return f"{parts[0]} {parts[1]}", parts[2]
    return "", line


async def _docker_exec(container: str, cmd: list[str], timeout: float = 30.0) -> str:
    code, out = await docker_exec(container, cmd, timeout=timeout)
    return out


async def docker_exec(
    container: str,
    cmd: list[str],
    *,
    user: str | None = None,
    timeout: float = 30.0,
) -> tuple[int, str]:
    argv = ["docker", "exec"]
    if user:
        argv.extend(["-u", user])
    argv.extend([container, *cmd])
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        return 124, "timeout"
    text = (stdout or b"").decode("utf-8", errors="replace")
    return proc.returncode or 0, text


async def fetch_source_logs(
    container: str,
    source: LogSource,
    lines: int,
    member_name: str,
    node_host: str,
) -> list[LogEntry]:
    template = SOURCE_COMMANDS[source]
    cmd = [part.format(n=lines) if "{n}" in part else part for part in template]
    raw = await _docker_exec(container, cmd)
    entries: list[LogEntry] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("-- No entries"):
            continue
        ts, msg = parse_journal_line(line)
        if not msg:
            msg = line
        if not ts:
            ts = ""
        entries.append(
            LogEntry(
                ts=ts,
                node=node_host,
                member_name=member_name,
                source=source,
                level=classify_level(msg),
                message=msg,
            )
        )
    return entries


def suppress_etcd_peer_noise(entries: list[LogEntry], down_hosts: set[str]) -> list[LogEntry]:
    if not down_hosts:
        return entries
    kept: list[LogEntry] = []
    for entry in entries:
        if entry.source != "etcd":
            kept.append(entry)
            continue
        match = ETCD_PEER_REFUSED.search(entry.message)
        if match and match.group(1) in down_hosts:
            continue
        kept.append(entry)
    return kept


async def fetch_cluster_logs(
    nodes: list[dict],
    docker_hosts: dict[str, str],
    sources: list[LogSource],
    lines_per_source: int = 80,
) -> list[LogEntry]:
    tasks: list[asyncio.Task[list[LogEntry]]] = []
    for node in nodes:
        host = str(node.get("host") or "")
        member = str(node.get("member_name") or host)
        container = docker_hosts.get(host)
        if not container:
            continue
        for source in sources:
            tasks.append(
                asyncio.create_task(
                    fetch_source_logs(container, source, lines_per_source, member, host)
                )
            )
    if not tasks:
        return []
    results = await asyncio.gather(*tasks, return_exceptions=True)
    merged: list[LogEntry] = []
    for result in results:
        if isinstance(result, list):
            merged.extend(result)
    merged.sort(key=lambda e: e.ts or e.message, reverse=True)
    return merged
