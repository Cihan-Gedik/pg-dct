.PHONY: install up down logs test smoke dev clean bootstrap-docker release-notes bundle-collector-dist

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
	chmod +x scripts/expose-patroni-ports.sh scripts/heal-lab-node.sh
	./scripts/expose-patroni-ports.sh

heal-main-node0:
	./scripts/heal-lab-node.sh logcollector-cihangedik-node0
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

# Generate Markdown between two refs: make release-notes PREV=v0.2.0 TAG=v0.2.1
PREV ?= v0.2.0
TAG ?= v0.2.1
release-notes:
	chmod +x scripts/release-notes.sh
	./scripts/release-notes.sh "$(PREV)" "$(TAG)"

# Customer-facing bundle collector package (send dist/pgdct-bundle-collector.tar.gz)
bundle-collector-dist:
	mkdir -p dist
	chmod +x tools/bundle-collector/pgdct-bundle-collect.sh tools/bundle-collector/collect.py
	tar czf dist/pgdct-bundle-collector.tar.gz -C tools/bundle-collector \
		collect.py discovery.py pgdct-bundle-collect.sh config.example.yaml README.txt
	@echo "OK  dist/pgdct-bundle-collector.tar.gz"

clean:
	rm -rf backend/.venv backend/data/*.db backend/.pytest_cache backend/.ruff_cache
	docker compose down -v 2>/dev/null || true
