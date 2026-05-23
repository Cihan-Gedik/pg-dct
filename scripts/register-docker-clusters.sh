#!/usr/bin/env bash
# Register AnyDBVer Docker lab clusters and run Patroni discover.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API="${PGDCT_API:-http://127.0.0.1:8080}"

echo "PG-DCT API: ${API}"

register() {
  local id="$1" seed="$2" scope="$3"
  echo "==> Register ${id}"
  curl -sf -X POST "${API}/api/v1/clusters" \
    -H 'Content-Type: application/json' \
    -d "{
      \"id\": \"${id}\",
      \"name\": \"${id}\",
      \"patroni_scope\": \"${scope}\",
      \"patroni_seed_url\": \"${seed}\",
      \"poll_interval_sec\": 5
    }" >/dev/null 2>&1 || true

  echo "==> Discover ${id}"
  curl -sf -X POST "${API}/api/v1/clusters/${id}/discover" | python3 -m json.tool
  echo ""
}

register "lc-pg-main" "http://172.18.0.2:8008" "lc-pg-main"
register "lc-pg-vanilla" "http://172.19.0.2:8008" "lc-pg-vanilla"

echo "==> All clusters"
curl -sf "${API}/api/v1/clusters" | python3 -m json.tool
