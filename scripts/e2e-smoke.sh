#!/usr/bin/env bash
set -euo pipefail
API="${PGDCT_API:-http://127.0.0.1:8080}"

echo "1. Health"
curl -sf "${API}/health"
echo ""

echo "2. Bootstrap"
curl -sf -X POST "${API}/api/v1/bootstrap/docker" | head -c 400
echo ""

echo "3. Clusters"
curl -sf "${API}/api/v1/clusters"
echo ""

CID=$(curl -sf "${API}/api/v1/clusters" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if d else '')")
if [[ -z "${CID}" ]]; then
  echo "No clusters — skip live/logs"
  exit 0
fi

echo "4. Live ${CID}"
curl -sf "${API}/api/v1/clusters/${CID}/live" | head -c 300
echo ""

echo "5. Logs ${CID}"
curl -sf "${API}/api/v1/clusters/${CID}/logs?lines=20" | python3 -c "import sys,json; d=json.load(sys.stdin); print('lines', d.get('count'))"

echo ""
echo "E2E smoke OK"
