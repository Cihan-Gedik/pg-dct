#!/usr/bin/env bash
# Customer-site bundle collector with environment discovery.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found" >&2
  exit 1
fi

case "${1:-}" in
  --discover|-d)
    exec python3 "$DIR/collect.py" --discover
    ;;
  --help|-h)
    echo "Usage: $0 [options passed to collect.py]"
    echo ""
    echo "  (no args)     Interactive discovery + collect"
    echo "  --discover    List Docker Patroni / local PostgreSQL only"
    echo "  -y            Non-interactive: first environment"
    echo "  --pick N      Select environment N from discovery"
    echo "  -c config.yaml Use manual config (skip discovery)"
    exit 0
    ;;
esac

if [[ "${1:-}" == "-c" ]] || [[ "${1:-}" == "--config" ]]; then
  exec python3 "$DIR/collect.py" "$@"
fi

exec python3 "$DIR/collect.py" -o "$DIR" "$@"
