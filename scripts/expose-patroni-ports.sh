#!/usr/bin/env bash
# Expose Patroni :8008 from Docker lab networks to Mac localhost.
# PG-DCT on the host cannot reach 172.18.x / 172.19.x directly on many setups.
set -euo pipefail

MAIN_NET="logcollector-cihangedik-anydbver"
DEV_NET="logcollector-dev-cihangedik-anydbver"
# Defaults; after switchover the leader IP moves — detect_leader_target updates these.
MAIN_TARGET="${PGDCT_MAIN_TARGET:-172.18.0.2:8008}"
DEV_TARGET="${PGDCT_DEV_TARGET:-172.19.0.2:8008}"
MAIN_PORT="${PGDCT_MAIN_PORT:-18080}"
DEV_PORT="${PGDCT_DEV_PORT:-19080}"

# Pick Patroni :8008 on the current leader (switchover-safe for host proxy).
detect_leader_target() {
  local container="$1"
  docker exec "$container" curl -sf -m 3 http://127.0.0.1:8008/cluster 2>/dev/null \
    | python3 -c "
import json, sys
data = json.load(sys.stdin)
for m in data.get('members') or []:
    if m.get('role') == 'leader':
        host = m.get('host') or ''
        if host:
            print(f'{host}:8008')
        break
" 2>/dev/null || true
}

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
main_detected=""
for c in logcollector-cihangedik-node0 logcollector-cihangedik-node1 logcollector-cihangedik-node2; do
  if main_detected="$(detect_leader_target "$c")" && [[ -n "$main_detected" ]]; then
    break
  fi
done
if [[ -n "$main_detected" ]]; then
  MAIN_TARGET="$main_detected"
  echo "Main cluster leader: $MAIN_TARGET"
else
  echo "Main cluster leader: $MAIN_TARGET (default)"
fi
dev_detected=""
for c in logcollector-dev-cihangedik-node0 logcollector-dev-cihangedik-node1 logcollector-dev-cihangedik-node2; do
  if dev_detected="$(detect_leader_target "$c")" && [[ -n "$dev_detected" ]]; then
    break
  fi
done
detected="$dev_detected"
if [[ -n "$detected" ]]; then
  DEV_TARGET="$detected"
  echo "Vanilla cluster leader: $DEV_TARGET"
else
  echo "Vanilla cluster leader: $DEV_TARGET (default)"
fi
start_proxy "pgdct-patroni-main" "$MAIN_NET" "$MAIN_PORT" "$MAIN_TARGET"
start_proxy "pgdct-patroni-vanilla" "$DEV_NET" "$DEV_PORT" "$DEV_TARGET"
echo ""
echo "Test:"
echo "  curl -s http://127.0.0.1:${MAIN_PORT}/cluster | head"
echo "  curl -s http://127.0.0.1:${DEV_PORT}/cluster | head"
echo ""
echo "Update seed URLs in config/docker-clusters.yaml to these localhost ports."
