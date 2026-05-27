# PG-DCT

**PostgreSQL Database Control Toolkit** — simple install, operational control for PostgreSQL (Patroni HA first). Planned: guided tasks for **MySQL** and **MongoDB**.

Troubleshooting (live metrics, logs, bundles) is the first module—not the whole product.

---

## Install (3 commands)

```bash
git clone git@github.com:Cihan-Gedik/pg-dct.git
cd pg-dct
./install.sh
```

Docker is used when available; otherwise a local Python virtualenv is prepared.

Verify:

```bash
make smoke
```

- **UI:** http://127.0.0.1:8080/ui/  
- API docs: http://127.0.0.1:8080/docs  

Full guide: [docs/INSTALL.md](docs/INSTALL.md) · Docker lab: [docs/DOCKER-LAB.md](docs/DOCKER-LAB.md)

**Releases:** [CHANGELOG.md](CHANGELOG.md) · [How to read versions & tags](docs/RELEASES.md) · [GitHub Releases](https://github.com/Cihan-Gedik/pg-dct/releases)

---

## Make targets

| Command | Description |
|---------|-------------|
| `make install` | Run installer |
| `make up` / `make down` | Docker start/stop |
| `make smoke` | Health + API smoke test |
| `make test` | Backend unit tests |
| `make dev` | Local uvicorn with reload |
| `make logs` | Follow API logs |

---

## Register a cluster

```bash
curl -s -X POST http://127.0.0.1:8080/api/v1/clusters \
  -H 'Content-Type: application/json' \
  -d '{
    "id": "prod-ha",
    "name": "prod-ha",
    "patroni_seed_url": "http://pg-node1:8008",
    "poll_interval_sec": 5
  }'

curl -s -X POST http://127.0.0.1:8080/api/v1/clusters/prod-ha/discover
```

---

## Repository layout

```
pg-dct/
├── install.sh          # One-command setup
├── docker-compose.yml  # Recommended runtime
├── backend/            # FastAPI API
├── ui/                 # Web UI (coming)
├── schemas/
└── docs/
```

## Roadmap

| Phase | Deliverable |
|-------|-------------|
| **Now** | Easy install, cluster CRUD, Patroni discover |
| Next | Settings UI, Live Monitor, log stream |
| Later | Bundles, MySQL/Mongo connectors |

## License

MIT — [LICENSE](LICENSE)
