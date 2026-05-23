.PHONY: install up down logs test smoke dev clean

PORT ?= 8080

install:
	@chmod +x install.sh scripts/smoke.sh
	@./install.sh

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api

smoke:
	PGDCT_PORT=$(PORT) ./scripts/smoke.sh

test:
	cd backend && (test -d .venv || python3 -m venv .venv) && . .venv/bin/activate && pip install -q -e ".[dev]" && pytest -q && ruff check app tests

dev:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port $(PORT)

clean:
	rm -rf backend/.venv backend/data/*.db backend/.pytest_cache backend/.ruff_cache
	docker compose down -v 2>/dev/null || true
