#!/usr/bin/env bash
# PG-DCT — one-command install (Docker preferred, local Python fallback)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${CYAN}==>${NC} $*"; }
ok()    { echo -e "${GREEN}OK${NC}  $*"; }
warn()  { echo -e "${YELLOW}!!${NC}  $*"; }

if [[ ! -f .env ]]; then
  cp .env.example .env
  ok "Created .env from .env.example"
fi

# shellcheck disable=SC1091
set -a && source .env && set +a
PORT="${PGDCT_PORT:-8080}"

use_docker() {
  command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1
}

install_docker() {
  info "Installing with Docker (recommended)…"
  docker compose up -d --build
  info "Waiting for API health…"
  for _ in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
      ok "API is up at http://127.0.0.1:${PORT}"
      ok "Docs: http://127.0.0.1:${PORT}/docs"
      return 0
    fi
    sleep 2
  done
  warn "API did not become healthy in time. Check: docker compose logs api"
  return 1
}

install_local() {
  info "Installing locally with Python…"
  if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found. Install Python 3.11+ or use Docker."
    exit 1
  fi
  cd "$ROOT/backend"
  if [[ ! -d .venv ]]; then
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -q -U pip
  pip install -q -e ".[dev]"
  mkdir -p data
  if [[ ! -f .env ]]; then
    cp "$ROOT/.env.example" .env
  fi
  ok "Python env ready in backend/.venv"
  echo ""
  echo "Start the API:"
  echo "  cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port ${PORT}"
  echo ""
  echo "Then open: http://127.0.0.1:${PORT}/docs"
}

run_smoke() {
  if [[ -x "$ROOT/scripts/smoke.sh" ]]; then
    info "Running smoke checks…"
    PGDCT_PORT="$PORT" "$ROOT/scripts/smoke.sh" || warn "Smoke checks failed (API may still be starting)"
  fi
}

echo ""
echo "  PG-DCT installer"
echo "  ─────────────────"
echo ""

if use_docker; then
  install_docker
  run_smoke
else
  warn "Docker Compose not found — using local Python."
  install_local
fi

echo ""
ok "Install finished."
echo "  Next: ./scripts/smoke.sh   — verify API"
echo "  Docs:  docs/GETTING_STARTED.md"
echo ""
