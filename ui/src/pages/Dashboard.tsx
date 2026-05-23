import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type ClusterListItem } from "../api";

export default function Dashboard() {
  const [clusters, setClusters] = useState<ClusterListItem[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api
      .listClusters()
      .then(setClusters)
      .catch((e) => setErr(String(e)));
  }, []);

  return (
    <>
      <h1>Dashboard</h1>
      <p className="sub">Registered PostgreSQL / Patroni clusters</p>
      {err && <div className="err">{err}</div>}
      <div className="stats">
        <div className="stat">
          <div className="v">{clusters.length}</div>
          <div className="l">Clusters</div>
        </div>
        <div className="stat">
          <div className="v">{clusters.reduce((a, c) => a + c.node_count, 0)}</div>
          <div className="l">Nodes</div>
        </div>
      </div>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Cluster</th>
              <th>Nodes</th>
              <th>Poll</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {clusters.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{c.node_count}</td>
                <td>{c.poll_interval_sec}s</td>
                <td>
                  <Link to={`/live?cluster=${c.id}`}>Live</Link> ·{" "}
                  <Link to={`/logs?cluster=${c.id}`}>Logs</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
