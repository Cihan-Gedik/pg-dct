PG-DCT Bundle Collector v2
==========================

Automatically discovers:
  - Docker Patroni clusters (all nodes, cluster name from Patroni API)
  - Local PostgreSQL on this machine (if pg_isready works)

Quick start
-----------
  chmod +x pgdct-bundle-collect.sh
  ./pgdct-bundle-collect.sh

You will see a numbered list of environments; pick one.
Output: bundle_YYYYMMDDTHHMMSSZ.tar.gz

Other commands
--------------
  ./pgdct-bundle-collect.sh --discover    # list only, no collect
  ./pgdct-bundle-collect.sh -y              # auto-pick first environment
  ./pgdct-bundle-collect.sh --pick 2        # pick item 2
  ./pgdct-bundle-collect.sh -c config.yaml  # manual config (no discovery)

Requirements: python3, docker (for Patroni containers), docker exec access.

Send the .tar.gz to your DBA. They import in PG-DCT with "Müşteri adı" (customer name).
