.PHONY: install up down logs test smoke dev clean bootstrap-docker

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

expose-patroni:
	chmod +x scripts/expose-patroni-ports.sh
	./scripts/expose-patroni-ports.sh

ui-build:
	cd ui && npm install && npm run build

bootstrap-docker: expose-patroni
	chmod +x scripts/register-docker-clusters.sh
	PGDCT_API=http://127.0.0.1:$(PORT) ./scripts/register-docker-clusters.sh

e2e:
	chmod +x scripts/e2e-smoke.sh
	PGDCT_API=http://127.0.0.1:$(PORT) ./scripts/e2e-smoke.sh

test:
	cd backend && (test -d .venv || python3 -m venv .venv) && . .venv/bin/activate && pip install -q -e ".[dev]" && pytest -q && ruff check app tests

dev:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port $(PORT)

clean:
	rm -rf backend/.venv backend/data/*.db backend/.pytest_cache backend/.ruff_cache
	docker compose down -v 2>/dev/null || true
