#!/usr/bin/env bash
# Start etcd + patroni inside a Patroni lab container when services are inactive.
# Fixes repeated etcd logs: dial tcp <peer>:2380: connection refused
set -euo pipefail

CONTAINER="${1:-}"
if [[ -z "$CONTAINER" ]]; then
  echo "Usage: $0 <docker-container-name>"
  echo "Example: $0 logcollector-cihangedik-node0"
  exit 1
fi

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "Container not found: $CONTAINER"
  exit 1
fi

echo "Healing $CONTAINER (etcd + patroni)…"
docker exec "$CONTAINER" bash -c '
  set -e
  if systemctl is-active etcd >/dev/null 2>&1; then
    echo "etcd already active"
  else
    systemctl start etcd
    echo "etcd started"
  fi
  sleep 2
  if systemctl is-active patroni >/dev/null 2>&1; then
    echo "patroni already active"
  else
    systemctl start patroni
    echo "patroni started"
  fi
  systemctl is-active etcd patroni
  curl -sf -m 3 http://127.0.0.1:8008/cluster | head -c 120 || echo "(patroni API not ready yet — wait 10s)"
'

echo ""
echo "Done. Refresh Patroni proxy if needed:"
echo "  ./scripts/expose-patroni-ports.sh"
