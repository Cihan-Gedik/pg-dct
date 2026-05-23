#!/usr/bin/env bash
# Quick smoke test after install
set -euo pipefail

PORT="${PGDCT_PORT:-8080}"
BASE="http://127.0.0.1:${PORT}"

echo "Smoke test → ${BASE}"

health=$(curl -sf "${BASE}/health")
echo "  /health        ${health}"

clusters=$(curl -sf "${BASE}/api/v1/clusters")
echo "  /api/v1/clusters  ${clusters}"

echo "Smoke test passed."
