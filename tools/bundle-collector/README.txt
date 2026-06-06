PG-DCT Bundle Collector v2
==========================

Automatically discovers:
  - Host Patroni first (curl to 127.0.0.1:8008/cluster)
  - Docker Patroni clusters (all nodes, cluster name from Patroni API)
  - Local PostgreSQL on this machine (if pg_isready works)

Priority order:
  1) Host Patroni (non-Docker, standard deployment)
  2) Docker Patroni
  3) Local PostgreSQL fallback

Quick start
-----------
  chmod +x pgdct-bundle-collect.sh
  ./pgdct-bundle-collect.sh

You will see a numbered list of environments; pick one.
Collector asks confirmation before collecting from discovered nodes.
If journal/default log paths fail, it asks the customer for a custom log path.
Output: bundle_YYYYMMDDTHHMMSSZ.tar.gz

Other commands
--------------
  ./pgdct-bundle-collect.sh --discover    # list only, no collect
  ./pgdct-bundle-collect.sh -y              # auto-pick first environment
  ./pgdct-bundle-collect.sh --pick 2        # pick item 2
  ./pgdct-bundle-collect.sh -c config.yaml  # manual config (no discovery)
  ./pgdct-bundle-collect.sh --no-prompt     # no follow-up questions
  ./pgdct-bundle-collect.sh --sources postgres,os   # force sources (overrides auto)

PostgreSQL logs (source=postgres) are discovered via:
  - journalctl for postgresql/postgres systemd units
  - psql SHOW log_directory + log_filename (when psql works)
  - common paths under /var/log/postgresql, /var/lib/pgsql, etc.
  - optional postgres_log_paths in config.yaml
  - interactive prompt if nothing found

Auto sources (when --sources is omitted):
  - Local PostgreSQL / no Patroni systemd unit → postgres, os only
  - Docker or host Patroni cluster → patroni, postgres, etcd, os

Notes for host Patroni:
  - For remote nodes in Patroni membership, collector tries SSH by host name/IP.
  - Optional config map:
      ssh_hosts:
        "10.0.0.12": "postgres@10.0.0.12"
        "10.0.0.13": "postgres@10.0.0.13"
  - SSH equivalency check uses temporary known_hosts and cleans it afterwards.

Requirements: python3, docker (for Patroni containers), docker exec access.

Send the .tar.gz to your DBA. They import in PG-DCT with "Müşteri adı" (customer name).
