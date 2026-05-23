# PG-DCT

**PostgreSQL Database Control Toolkit** — operational control plane for database workloads.

PG-DCT starts with Patroni HA troubleshooting (live metrics, log exploration, diagnostic bundles). The platform is designed to grow into simple, guided tasks across **PostgreSQL**, **MySQL**, and **MongoDB**.

## Current scope (Phase 1)

- Register clusters and nodes (Patroni `GET /cluster` discovery)
- REST API for cluster inventory
- Foundation for Live Monitor and Lets Check Logs (UI next)

## Planned scope

| Area | Examples |
|------|----------|
| Troubleshooting | Patroni/etcd/PostgreSQL logs, bundles, topology |
| PostgreSQL | Health checks, replication, common admin tasks |
| MySQL | Instance inventory, basic diagnostics |
| MongoDB | Replica set status, simple operations |

## Repository layout

```
pg-dct/
├── backend/          # FastAPI — API, poller, discovery
├── schemas/          # JSON Schema contracts
├── deploy/           # Docker Compose, env templates
├── docs/             # Architecture and runbooks
└── ui/               # Web UI (Phase 1b)
```

## Quick start

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp ../deploy/.env.example ../deploy/.env
uvicorn app.main:app --reload --port 8080
```

API docs: http://localhost:8080/docs

### Register a cluster

```bash
curl -s -X POST http://localhost:8080/api/v1/clusters \
  -H 'Content-Type: application/json' \
  -d '{
    "id": "prod-ha",
    "name": "prod-ha",
    "patroni_seed_url": "http://pg-node1:8008",
    "poll_interval_sec": 5
  }'

curl -s -X POST http://localhost:8080/api/v1/clusters/prod-ha/discover
```

## GitHub

Create the remote repository on GitHub named `PG-DCT` or `pg-dct`, then:

```bash
git remote add origin git@github.com:<your-org>/pg-dct.git
git push -u origin main
```

## License

MIT — see [LICENSE](LICENSE).
