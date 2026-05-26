# pgBackRest lab config — substituted by install-pgbackrest-lab.sh
# Shared repo on /nfs so all Patroni nodes see the same backups after failover.

[global]
repo1-path=/nfs/pgbackrest/${STANZA}/repo
repo1-retention-full=2
repo1-retention-diff=1
log-path=/var/log/pgbackrest
log-level-file=detail
log-level-console=info
process-max=2
start-fast=y

[${STANZA}]
pg1-path=/var/lib/pgsql/${PG_MAJOR}/data
pg1-port=5432
pg1-socket-path=/var/run/postgresql
pg1-user=postgres
