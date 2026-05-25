from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

import httpx

from app.config import settings


class PatroniDiscoveryError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


async def fetch_cluster_members(seed_url: str) -> tuple[str | None, list[dict[str, Any]]]:
    """Call Patroni GET /cluster and return scope + members."""
    base = seed_url.rstrip("/")
    url = urljoin(base + "/", "cluster")
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_sec) as client:
            response = await client.get(url)
    except httpx.TimeoutException as exc:
        raise PatroniDiscoveryError(f"Patroni timeout: {url}") from exc
    except httpx.HTTPError as exc:
        raise PatroniDiscoveryError(f"Patroni unreachable: {exc}") from exc
    if response.status_code != 200:
        raise PatroniDiscoveryError(
            f"Patroni /cluster returned {response.status_code}",
            status_code=response.status_code,
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise PatroniDiscoveryError("Patroni /cluster returned invalid JSON") from exc
    scope = payload.get("scope")
    members = payload.get("members") or []
    if not isinstance(members, list):
        raise PatroniDiscoveryError("Invalid Patroni /cluster response: members is not a list")
    return scope, members


async def fetch_patroni_history(seed_url: str) -> list[Any]:
    """Call Patroni GET /history (timeline / leader changes)."""
    base = seed_url.rstrip("/")
    url = urljoin(base + "/", "history")
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_sec) as client:
            response = await client.get(url)
    except httpx.HTTPError:
        return []
    if response.status_code != 200:
        return []
    try:
        payload = response.json()
    except ValueError:
        return []
    return payload if isinstance(payload, list) else []


def member_lag_bytes(member: dict[str, Any]) -> int:
    raw = member.get("lag")
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def member_timeline(member: dict[str, Any]) -> int | None:
    raw = member.get("timeline")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def member_to_node_fields(member: dict[str, Any]) -> dict[str, Any]:
    host = str(member.get("host") or "")
    port = int(member.get("port") or 8008)
    api_url = member.get("api_url") or f"http://{host}:{port}"
    return {
        "member_name": str(member.get("name") or host or "unknown"),
        "host": host,
        "patroni_port": port,
        "api_url": str(api_url),
        "role": str(member.get("role") or "unknown"),
        "state": member.get("state"),
        "last_seen_at": datetime.now(UTC),
    }
