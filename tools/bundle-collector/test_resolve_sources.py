"""Tests for auto source selection in collect.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collect import (  # noqa: E402
    ALL_LOG_SOURCES,
    STANDALONE_LOG_SOURCES,
    parse_sources_arg,
    resolve_default_sources,
)


def test_parse_sources_explicit() -> None:
    assert parse_sources_arg("postgres,os") == ["postgres", "os"]
    assert parse_sources_arg(None) is None


def test_resolve_local_postgresql() -> None:
    cfg = {"discovery": {"kind": "local_postgresql"}}
    assert resolve_default_sources(cfg) == STANDALONE_LOG_SOURCES


def test_resolve_docker_patroni() -> None:
    cfg = {
        "discovery": {"kind": "docker_patroni"},
        "docker_hosts": {"10.0.0.1": "node0"},
    }
    assert resolve_default_sources(cfg) == ALL_LOG_SOURCES


def test_resolve_host_patroni() -> None:
    cfg = {"discovery": {"kind": "host_patroni"}, "patroni_url": "http://127.0.0.1:8008"}
    assert resolve_default_sources(cfg) == ALL_LOG_SOURCES


def test_resolve_manual_config_sources_override() -> None:
    cfg = {"sources": "postgres,os"}
    assert resolve_default_sources(cfg) == ["postgres", "os"]
