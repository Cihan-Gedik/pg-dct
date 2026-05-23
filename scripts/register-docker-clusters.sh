#!/usr/bin/env bash
# Register Docker lab clusters via PG-DCT bootstrap API (idempotent).
set -euo pipefail

API="${PGDCT_API:-http://127.0.0.1:8080}"

echo "PG-DCT API: ${API}"
echo "Checking API health..."
health=$(curl -s -w "%{http_code}" -o /tmp/pgdct-health.json "${API}/health" || true)
if [[ "${health}" != "200" ]]; then
  echo "ERROR: API not reachable at ${API}/health (HTTP ${health})"
  echo "Start API first:"
  echo "  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8080"
  exit 1
fi
cat /tmp/pgdct-health.json
echo ""

echo "Bootstrap from config/docker-clusters.yaml..."
http_code=$(curl -s -w "%{http_code}" -o /tmp/pgdct-bootstrap.json \
  -X POST "${API}/api/v1/bootstrap/docker")
echo "HTTP ${http_code}"
cat /tmp/pgdct-bootstrap.json
echo ""

if [[ "${http_code}" != "200" ]]; then
  echo "ERROR: bootstrap failed"
  exit 1
fi

python3 -m json.tool /tmp/pgdct-bootstrap.json
echo ""
echo "Done. Open http://127.0.0.1:8080/ui/"
