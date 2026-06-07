import { useCallback, useEffect, useState } from "react";
import { api, type ClusterListItem } from "../api";

const DOCKER_LAB_IDS = new Set(["lc-pg-main", "lc-pg-vanilla", "bc-pg-main"]);

export default function Settings() {
  const [clusters, setClusters] = useState<ClusterListItem[]>([]);
  const [loadingClusters, setLoadingClusters] = useState(true);
  const [clusterErr, setClusterErr] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refreshClusters = useCallback(async () => {
    setLoadingClusters(true);
    setClusterErr(null);
    try {
      setClusters(await api.listClusters());
    } catch (e) {
      setClusterErr(String(e));
    } finally {
      setLoadingClusters(false);
    }
  }, []);

  useEffect(() => {
    void refreshClusters();
  }, [refreshClusters]);

  async function bootstrap() {
    setLoading(true);
    setMsg(null);
    try {
      const res = await api.bootstrapDocker();
      setMsg(JSON.stringify(res, null, 2));
      await refreshClusters();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function deleteCluster(cluster: ClusterListItem) {
    const lab = DOCKER_LAB_IDS.has(cluster.id);
    const prompt = lab
      ? `Delete Docker lab cluster "${cluster.name}"?\n\nIt will reappear if you run Bootstrap Docker clusters again.`
      : `Delete cluster "${cluster.name}" (${cluster.id})?\n\nThis removes it from PG-DCT only (not Docker containers).`;
    if (!window.confirm(prompt)) return;

    setDeletingId(cluster.id);
    setClusterErr(null);
    try {
      await api.deleteCluster(cluster.id);
      await refreshClusters();
    } catch (e) {
      setClusterErr(String(e));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <>
      <h1>Settings</h1>
      <p className="sub">Cluster registration and Docker lab bootstrap</p>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Registered clusters</h3>
        <p className="pill">
          Remove imported or test clusters from the UI. Docker lab entries can be re-registered via bootstrap.
        </p>
        {clusterErr && <div className="err">{clusterErr}</div>}
        {loadingClusters && <p className="pill">Loading clusters…</p>}
        {!loadingClusters && clusters.length === 0 && <p className="pill">No clusters registered.</p>}
        {!loadingClusters && clusters.length > 0 && (
          <table className="settings-cluster-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Nodes</th>
                <th>Type</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {clusters.map((c) => (
                <tr key={c.id}>
                  <td>
                    <code>{c.id}</code>
                  </td>
                  <td>{c.name}</td>
                  <td>{c.node_count}</td>
                  <td>
                    {DOCKER_LAB_IDS.has(c.id) ? (
                      <span className="badge replica">Docker lab</span>
                    ) : (
                      <span className="badge">Manual / import</span>
                    )}
                  </td>
                  <td className="action-links">
                    <button
                      type="button"
                      className="btn btn-sm destructive"
                      disabled={deletingId === c.id}
                      onClick={() => void deleteCluster(c)}
                    >
                      {deletingId === c.id ? "Deleting…" : "Delete"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Docker lab</h3>
        <p className="pill">Requires ./scripts/expose-patroni-ports.sh running</p>
        <div className="row" style={{ marginTop: 12 }}>
          <button type="button" className="btn primary" onClick={bootstrap} disabled={loading}>
            Bootstrap Docker clusters
          </button>
        </div>
        {msg && (
          <pre style={{ marginTop: 16, fontSize: 11, overflow: "auto" }}>{msg}</pre>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Config</h3>
        <p className="pill">config/docker-clusters.yaml — cluster seeds and docker_hosts map</p>
      </div>
    </>
  );
}
