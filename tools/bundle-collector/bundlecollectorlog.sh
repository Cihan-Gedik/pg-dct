#!/usr/bin/env bash
set -euo pipefail

# Customer-facing wrapper for PG-DCT bundle collector.
# - Auto-discovers host Patroni / Docker Patroni / local PostgreSQL
# - Collects patroni, postgres, etcd, os logs
# - Produces bundle_YYYYMMDDTHHMMSSZ.tar.gz in this folder

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found on PATH" >&2
  exit 1
fi

echo "PG-DCT Bundle Collector"
echo "Working directory: $DIR"
echo ""

case "${1:-}" in
  --discover|-d)
    exec python3 "$DIR/collect.py" --discover
    ;;
  --help|-h)
    cat <<'EOF'
Usage:
  ./bundlecollectorlog.sh                # discovery + confirmation + collect
  ./bundlecollectorlog.sh --discover     # discovery only
  ./bundlecollectorlog.sh -y             # auto-pick first discovered environment
  ./bundlecollectorlog.sh --pick 2       # pick environment index 2
  ./bundlecollectorlog.sh -n 200         # collect 200 lines per source
  ./bundlecollectorlog.sh -c config.yaml # manual config (skip discovery)
  ./bundlecollectorlog.sh --no-prompt    # disable missing-path questions
EOF
    exit 0
    ;;
esac

if [[ "${1:-}" == "-c" || "${1:-}" == "--config" ]]; then
  exec python3 "$DIR/collect.py" "$@"
fi

exec python3 "$DIR/collect.py" -o "$DIR" "$@"
