# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Backup schedules:** Added UTC cron schedules for pgBackRest full/diff/incr backups, with persistent schedule registry, API scheduler loop, and UI controls for create, pause/enable, run-now, and delete.

### Changed

### Fixed

---

## [0.3.0] - 2026-05-27

[Compare v0.2.1...v0.3.0](https://github.com/Cihan-Gedik/pg-dct/compare/v0.2.1...v0.3.0)

### Added

- **Customer bundle collector package:** `tools/bundle-collector` now supports environment discovery (Docker Patroni clusters and local PostgreSQL) and exports portable `bundle_*.tar.gz` archives for remote customer troubleshooting.
- **Bundle import API:** Added bundle import endpoints with customer metadata and reusable archive storage (`/api/v1/bundles/import`, `/api/v1/bundles/customers`, `/api/v1/bundles/*`).
- **Bundle workflows in UI:** Bundles page now supports customer-tagged imports, customer list management, and bundle-driven log analysis flow.

### Changed

- **Navigation split:** Log viewing is separated into **Live Logs** and **Bundle Logs** routes so live telemetry and imported archives are isolated by design.
- **Bundle Logs behavior:** Screen shows only imported customer data; if no customer is selected, the view stays intentionally empty.

### Fixed

- Removed stale test/import placeholder customer records and cleaned bundle-log routing so live data no longer leaks into bundle-only flows.

---

## [0.2.1] - 2026-05-26

[Compare v0.2.0...v0.2.1](https://github.com/Cihan-Gedik/pg-dct/compare/v0.2.0...v0.2.1)

### Added

- **Dashboard — PostgreSQL Settings:** Grafana-style KPI strip for the **selected cluster** (values from the Patroni leader via `pg_settings`).
- **API:** `GET /api/v1/clusters/{cluster_id}/postgres/settings` — version, shared_buffers, work_mem, max_wal_size, max_connections, and related parameters.

### Changed

- **Dashboard:** Removed duplicate top navigation links (Log Analyzer / Live Monitor); sidebar remains the single app navigation.

---

## [0.2.0] - 2026-05-26

[Tag v0.2.0](https://github.com/Cihan-Gedik/pg-dct/releases/tag/v0.2.0) · [Compare since v0.2.1 predecessor](https://github.com/Cihan-Gedik/pg-dct/compare/v0.2.1^...v0.2.0)

### Added

- **Live Monitor — DCS / etcd:** Patroni leader vs failover candidates, etcd raft leader, quorum, and **etcd members** table (same style as Patroni members).
- **Dashboard — dynamic topology:** Replica nodes from Patroni only (no fixed R3 slot); lag-based coloring from real `lag` bytes.
- **Dashboard — incident window:** Default **24h** with selectable range (6h / 24h / 7d / 30d); server-side `hours` filter on logs and dashboard issues.
- **Backend:** Journal timestamp parsing fix (`2026-05-23T14:02:01+0000`); etcd status service (`etcdctl`).

### Changed

- **Live Monitor:** Leadership timeline removed from Overview (stays on Dashboard only).

### Fixed

- Incidents older than the selected time window no longer appear as “last 24 hours” when journal timestamps were misparsed.

---

## [0.1.0] - earlier

Initial toolkit: React UI, Live Monitor, log streaming, Docker lab bootstrap, Backup hub (pgBackRest), dashboard reference layout.

[0.2.1]: https://github.com/Cihan-Gedik/pg-dct/releases/tag/v0.2.1
[0.2.0]: https://github.com/Cihan-Gedik/pg-dct/releases/tag/v0.2.0
[0.3.0]: https://github.com/Cihan-Gedik/pg-dct/releases/tag/v0.3.0
[Unreleased]: https://github.com/Cihan-Gedik/pg-dct/compare/v0.3.0...HEAD
