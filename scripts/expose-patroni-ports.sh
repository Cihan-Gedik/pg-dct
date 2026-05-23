#!/usr/bin/env bash
# Expose Patroni :8008 from Docker lab networks to Mac localhost.
# PG-DCT on the host cannot reach 172.18.x / 172.19.x directly on many setups.
set -euo pipefail

MAIN_NET="logcollector-cihangedik-anydbver"
DEV_NET="logcollector-dev-cihangedik-anydbver"
MAIN_TARGET="172.18.0.2:8008"
DEV_TARGET="172.19.0.2:8008"
MAIN_PORT="${PGDCT_MAIN_PORT:-18080}"
DEV_PORT="${PGDCT_DEV_PORT:-19080}"

stop_proxy() {
  docker rm -f "$1" 2>/dev/null || true
}

start_proxy() {
  local name="$1" network="$2" host_port="$3" target="$4"
  stop_proxy "$name"
  docker run -d --name "$name" \
    --network "$network" \
    -p "127.0.0.1:${host_port}:8008" \
    alpine/socat \
    "TCP-LISTEN:8008,fork,reuseaddr" "TCP:${target}"
  echo "OK  ${name}: http://127.0.0.1:${host_port} -> ${target}"
}

echo "Starting Patroni port proxies for PG-DCT (host -> Docker network)…"
start_proxy "pgdct-patroni-main" "$MAIN_NET" "$MAIN_PORT" "$MAIN_TARGET"
start_proxy "pgdct-patroni-vanilla" "$DEV_NET" "$DEV_PORT" "$DEV_TARGET"
echo ""
echo "Test:"
echo "  curl -s http://127.0.0.1:${MAIN_PORT}/cluster | head"
echo "  curl -s http://127.0.0.1:${DEV_PORT}/cluster | head"
echo ""
echo "Update seed URLs in config/docker-clusters.yaml to these localhost ports."
