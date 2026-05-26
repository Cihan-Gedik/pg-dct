#!/usr/bin/env bash
# Install pgBackRest on AnyDBVer logcollector Patroni lab containers and wire
# archive_command via patronictl. Requires running containers and Patroni leader.
#
# Usage:
#   ./scripts/install-pgbackrest-lab.sh vanilla
#   ./scripts/install-pgbackrest-lab.sh main
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF_TPL="${ROOT}/deploy/pgbackrest/pgbackrest-lab.conf.tpl"

usage() {
  echo "Usage: $0 <vanilla|main>" >&2
  exit 1
}

[[ $# -eq 1 ]] || usage
TARGET="$1"

case "$TARGET" in
  vanilla)
    STANZA="lc-pg-vanilla"
    CONTAINERS=(
      logcollector-dev-cihangedik-node0
      logcollector-dev-cihangedik-node1
      logcollector-dev-cihangedik-node2
    )
    LEADER_CONTAINER="logcollector-dev-cihangedik-node0"
    PATRONI_CFG="/etc/patroni/lc-pg-vanilla-0.yml"
    ;;
  main)
    STANZA="lc-pg-main"
    CONTAINERS=(
      logcollector-cihangedik-node0
      logcollector-cihangedik-node1
      logcollector-cihangedik-node2
    )
    LEADER_CONTAINER="logcollector-cihangedik-node0"
    PATRONI_CFG="/etc/patroni/lc-pg-main-0.yml"
    ;;
  *)
    usage
    ;;
esac

if [[ ! -f "$CONF_TPL" ]]; then
  echo "Missing template: $CONF_TPL" >&2
  exit 1
fi

echo "==> Target: $TARGET (stanza=$STANZA)"

# Detect PostgreSQL major on leader (18, 17, …).
PG_MAJOR="$(docker exec "$LEADER_CONTAINER" bash -c \
  'sudo -u postgres psql -tAc "SHOW data_directory"' | tr -d '[:space:]' | sed -n 's|.*/pgsql/\([0-9]*\)/data|\1|p')"
if [[ -z "$PG_MAJOR" ]]; then
  echo "Could not detect PG major from data_directory on $LEADER_CONTAINER" >&2
  exit 1
fi
echo "==> PostgreSQL major: $PG_MAJOR"

render_conf() {
  STANZA="$STANZA" PG_MAJOR="$PG_MAJOR" envsubst '$STANZA $PG_MAJOR' <"$CONF_TPL"
}

echo "==> Installing pgbackrest package on ${#CONTAINERS[@]} containers…"
for c in "${CONTAINERS[@]}"; do
  if ! docker inspect "$c" &>/dev/null; then
    echo "Container not running: $c" >&2
    exit 1
  fi
  docker exec "$c" bash -c '
    if command -v pgbackrest >/dev/null; then
      echo "  already installed: pgbackrest $(pgbackrest version | head -1)"
      exit 0
    fi
    dnf install -y -q pgbackrest
  ' | sed "s/^/  [$c] /"
done

echo "==> Shared repo + logs on /nfs…"
for c in "${CONTAINERS[@]}"; do
  docker exec "$c" bash -c "
    install -d -o postgres -g postgres -m 0750 /nfs/pgbackrest/${STANZA}/repo
    install -d -o postgres -g postgres -m 0755 /var/log/pgbackrest
  "
done

CONF_BODY="$(render_conf)"
echo "==> Writing /etc/pgbackrest.conf on all nodes…"
for c in "${CONTAINERS[@]}"; do
  docker exec -i "$c" bash -c 'cat > /etc/pgbackrest.conf' <<<"$CONF_BODY"
  docker exec "$c" chown postgres:postgres /etc/pgbackrest.conf
  docker exec "$c" chmod 0640 /etc/pgbackrest.conf
done

echo "==> Patroni: archive_command → pgbackrest (cluster-wide)…"
docker exec "$LEADER_CONTAINER" patronictl -c "$PATRONI_CFG" edit-config --force \
  -p "archive_command=pgbackrest --stanza=${STANZA} archive-push %p" \
  -p "restore_command=pgbackrest --stanza=${STANZA} archive-get %f \"%p\"" \
  -q

echo "==> stanza-create on leader ($LEADER_CONTAINER)…"
docker exec -u postgres "$LEADER_CONTAINER" pgbackrest --stanza="$STANZA" stanza-create

echo "==> check…"
docker exec -u postgres "$LEADER_CONTAINER" pgbackrest --stanza="$STANZA" check

echo "==> Optional first full backup (may take a minute)…"
docker exec -u postgres "$LEADER_CONTAINER" pgbackrest --stanza="$STANZA" --type=full backup

echo ""
echo "Done. Add to config/docker-clusters.yaml for cluster id ${STANZA}:"
echo "  pgbackrest:"
echo "    enabled: true"
echo "    stanza: ${STANZA}"
echo ""
echo "Verify: docker exec -u postgres $LEADER_CONTAINER pgbackrest --stanza=${STANZA} info"
echo "PG-DCT Backup page → refresh Overview."
