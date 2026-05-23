# PG-DCT Architecture

## Vision

PG-DCT is a control toolkit for database operations. **Troubleshooting** (Patroni HA, logs, bundles) is the first module. Future modules add guided tasks for PostgreSQL, MySQL, and MongoDB without replacing full DBA tooling.

## Components

| Component | Responsibility |
|-----------|----------------|
| **API** | Cluster/node inventory, discovery, future task runners |
| **Metadata DB** | Clusters, nodes, poll state |
| **Poller** (Phase 2) | Periodic Patroni `/cluster`, etcd health |
| **UI** (Phase 1b) | Live Monitor, Lets Check Logs, Settings |
| **Agent** (Phase 3+) | Log tail, bundle collect on nodes |

## Cluster registration (Phase 1)

1. Operator creates a cluster in **Settings** with a Patroni seed URL.
2. API calls `GET {seed}/cluster` and upserts `members[]` into `nodes`.
3. UI comboboxes read from `GET /api/v1/clusters` and `.../nodes`.

## Multi-engine roadmap

| Engine | Status | Entry point |
|--------|--------|-------------|
| PostgreSQL + Patroni | Phase 1 | `patroni_seed_url` |
| PostgreSQL standalone | Planned | host + port |
| MySQL | Planned | instance connector |
| MongoDB | Planned | replica set URI |

Engines share the same **cluster** abstraction; engine-specific discovery adapters plug into registration.
