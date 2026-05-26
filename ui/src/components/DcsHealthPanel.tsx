import type { DcsStatus, LiveCluster } from "../api";

type Props = {
  live: LiveCluster;
  dcs: DcsStatus | null | undefined;
};

export function DcsHealthPanel({ live, dcs }: Props) {
  const patroniLeader = dcs?.patroni_leader ?? live.leader;
  const patroniHost = dcs?.patroni_leader_host;
  const candidates = dcs?.failover_candidates ?? [];
  const etcdLeader = dcs?.etcd_raft_leader;
  const etcdLeaderId = dcs?.etcd_raft_leader_id;

  return (
    <div className="card dcs-health-panel">
      <h3 className="section-title">DCS / etcd Health</h3>

      <div className="dcs-summary-grid">
        <section className="dcs-summary-block">
          <h4>Patroni (PostgreSQL HA)</h4>
          <dl className="dcs-kv">
            <div>
              <dt>Leader (primary)</dt>
              <dd>
                <strong>{patroniLeader ?? "—"}</strong>
                {patroniHost && <span className="dcs-kv-meta"> @ {patroniHost}</span>}
              </dd>
            </div>
            <div>
              <dt>Failover candidates</dt>
              <dd>
                {candidates.length ? (
                  <span className="dcs-candidate-list">{candidates.join(" · ")}</span>
                ) : (
                  <span className="muted">No streaming replicas</span>
                )}
              </dd>
            </div>
          </dl>
        </section>

        <section className="dcs-summary-block">
          <h4>etcd (Raft consensus)</h4>
          <dl className="dcs-kv">
            <div>
              <dt>Raft leader</dt>
              <dd>
                <strong>{etcdLeader ?? "—"}</strong>
                {etcdLeaderId && <span className="dcs-kv-meta"> · id {etcdLeaderId}</span>}
              </dd>
            </div>
            <div>
              <dt>Quorum (healthy endpoints)</dt>
              <dd>
                <span className={`badge ${String(live.etcd_quorum ?? "").includes("degraded") ? "warning" : "leader"}`}>
                  {live.etcd_quorum ?? "—"}
                </span>
              </dd>
            </div>
            {dcs?.etcd_cluster_id && (
              <div>
                <dt>Cluster ID</dt>
                <dd className="mono-sm">{dcs.etcd_cluster_id}</dd>
              </div>
            )}
            {dcs?.etcd_raft_term != null && (
              <div>
                <dt>Raft term</dt>
                <dd>{dcs.etcd_raft_term}</dd>
              </div>
            )}
          </dl>
        </section>
      </div>

      {patroniLeader && etcdLeader && patroniLeader !== etcdLeader && (
        <p className="pill dcs-note-warn">
          Patroni primary and etcd raft leader are on different nodes — this is normal after switchover or
          during recovery.
        </p>
      )}
    </div>
  );
}
