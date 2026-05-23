"""Fetch logs from Patroni lab containers via docker exec."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Literal

LogSource = Literal["patroni", "postgres", "etcd", "os"]
LogLevel = Literal["critical", "warning", "info"]

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


def parse_journal_line(line: str) -> tuple[str, str]:
    line = line.strip()
    if not line:
        return "", ""
    parts = line.split(" ", 2)
    if len(parts) >= 3 and parts[0].count("-") >= 2:
        return f"{parts[0]} {parts[1]}", parts[2]
    return "", line


async def _docker_exec(container: str, cmd: list[str], timeout: float = 30.0) -> str:
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "exec",
        container,
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        return ""
    return (stdout or b"").decode("utf-8", errors="replace")


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
