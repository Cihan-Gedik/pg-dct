"""Read key PostgreSQL settings from the Patroni leader via docker exec."""

from __future__ import annotations

from typing import Any

from app.services.docker_logs import _docker_exec
from app.services.pgbackrest import resolve_leader_container

# Grafana-style dashboard KPIs (order preserved).
SETTING_KEYS: list[tuple[str, str]] = [
    ("server_version", "Version"),
    ("shared_buffers", "Shared Buffers"),
    ("effective_cache_size", "Effective Cache"),
    ("maintenance_work_mem", "Maintenance Work Mem"),
    ("work_mem", "Work Mem"),
    ("max_wal_size", "Max WAL Size"),
    ("random_page_cost", "Random Page Cost"),
    ("seq_page_cost", "Seq Page Cost"),
    ("max_worker_processes", "Max Worker Processes"),
    ("max_parallel_workers", "Max Parallel Workers"),
    ("max_connections", "Max Connections"),
]


def format_setting_value(setting: str, unit: str | None) -> str:
    """Human-readable value similar to Grafana stat panels."""
    raw = (setting or "").strip()
    u = (unit or "").strip()
    if not raw:
        return "—"
    if not u:
        return raw
    try:
        num = float(raw)
    except ValueError:
        return f"{raw} {u}".strip()

    if u == "8kB":
        return _human_bytes(int(num * 8192))
    if u == "kB":
        return _human_bytes(int(num * 1024))
    if u == "MB":
        return _human_bytes(int(num * 1024 * 1024))
    if u == "GB":
        return _human_bytes(int(num * 1024**3))
    return f"{_trim_float(num)} {u}"


def _trim_float(n: float) -> str:
    if n == int(n):
        return str(int(n))
    return f"{n:.2f}".rstrip("0").rstrip(".")


def _human_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024**2:
        return f"{size / 1024:.1f} KiB"
    if size < 1024**3:
        return f"{size / (1024**2):.1f} MiB"
    return f"{size / (1024**3):.1f} GiB"


def parse_settings_tsv(raw: str) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        parts = line.split("|", 2)
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        setting = parts[1].strip()
        unit = parts[2].strip() if len(parts) > 2 else ""
        out[name] = (setting, unit)
    return out


async def fetch_postgres_settings(
    patroni_seed_url: str,
    cluster_id: str,
    *,
    timeout: float = 20.0,
) -> dict[str, Any]:
    container, leader_name, host = await resolve_leader_container(patroni_seed_url, cluster_id)
    if not container:
        return {
            "ok": False,
            "error": "Leader container not found — check docker_hosts and Patroni cluster",
            "leader": None,
            "host": None,
            "container": None,
            "version": None,
            "settings": [],
        }

    names = [k for k, _ in SETTING_KEYS]
    in_list = ",".join(f"'{n}'" for n in names)
    sql = (
        f"SELECT name, setting, COALESCE(unit, '') "
        f"FROM pg_settings WHERE name IN ({in_list}) ORDER BY name"
    )
    cmd = [
        "psql",
        "-U",
        "postgres",
        "-d",
        "postgres",
        "-t",
        "-A",
        "-F|",
        "-c",
        sql,
    ]
    raw = await _docker_exec(container, cmd, timeout=timeout)
    if "error" in raw.lower() and "connection" in raw.lower() and not raw.count("|"):
        return {
            "ok": False,
            "error": raw.strip()[:300] or "psql failed",
            "leader": leader_name,
            "host": host,
            "container": container,
            "version": None,
            "settings": [],
        }

    parsed = parse_settings_tsv(raw)
    version_row = parsed.get("server_version")
    version = version_row[0] if version_row else None
    if not version:
        ver_raw = await _docker_exec(
            container,
            ["psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", "SHOW server_version"],
            timeout=timeout,
        )
        version = ver_raw.strip().split("\n")[0] if ver_raw.strip() else None

    settings: list[dict[str, str]] = []
    for key, label in SETTING_KEYS:
        row = parsed.get(key)
        if key == "server_version":
            if version:
                settings.append(
                    {
                        "name": key,
                        "label": label,
                        "value": version,
                        "raw_setting": version,
                        "unit": None,
                    }
                )
            continue
        if not row:
            continue
        setting, unit = row
        settings.append(
            {
                "name": key,
                "label": label,
                "value": format_setting_value(setting, unit or None),
                "raw_setting": setting,
                "unit": unit or None,
            }
        )

    return {
        "ok": True,
        "error": None,
        "leader": leader_name,
        "host": host,
        "container": container,
        "version": version,
        "settings": settings,
    }
