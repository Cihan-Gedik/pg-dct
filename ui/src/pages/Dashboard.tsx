import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type ClusterListItem, type DashboardIssue } from "../api";
import { CriticalIssuesPanel } from "../components/CriticalIssuesPanel";

export default function Dashboard() {
  const [clusters, setClusters] = useState<ClusterListItem[]>([]);
  const [issues, setIssues] = useState<DashboardIssue[]>([]);
  const [criticalCount, setCriticalCount] = useState(0);
  const [warningCount, setWarningCount] = useState(0);
  const [search, setSearch] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [issuesErr, setIssuesErr] = useState<string | null>(null);
  const [loadingIssues, setLoadingIssues] = useState(false);
  const [lastIssuesRefresh, setLastIssuesRefresh] = useState<Date | null>(null);

  const refreshIssues = useCallback(async () => {
    setLoadingIssues(true);
    setIssuesErr(null);
    try {
      const data = await api.dashboardIssues();
      setIssues(data.issues);
      setCriticalCount(data.critical_count);
      setWarningCount(data.warning_count);
      setLastIssuesRefresh(new Date());
    } catch (e) {
      setIssuesErr(String(e));
    } finally {
      setLoadingIssues(false);
    }
  }, []);

  useEffect(() => {
    api
      .listClusters()
      .then(setClusters)
      .catch((e) => setErr(String(e)));
    refreshIssues();
  }, [refreshIssues]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return clusters;
    return clusters.filter(
      (c) => c.id.toLowerCase().includes(q) || c.name.toLowerCase().includes(q) || c.engine.toLowerCase().includes(q),
    );
  }, [clusters, search]);

  return (
    <>
      <header className="page-header compact">
        <div>
          <h1>Dashboard</h1>
          <p className="sub">Cluster inventory and open critical issues</p>
        </div>
      </header>

      {err && <div className="err">{err}</div>}

      <CriticalIssuesPanel
        issues={issues}
        criticalCount={criticalCount}
        warningCount={warningCount}
        loading={loadingIssues}
        error={issuesErr}
        onRefresh={refreshIssues}
        lastRefresh={lastIssuesRefresh}
      />

      <div className="dashboard-toolbar card">
        <div className="field" style={{ flex: 1, minWidth: 220 }}>
          <label>Cluster search</label>
          <input
            type="search"
            placeholder="Filter by name, id, engine…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="stats">
        <div className="stat">
          <div className="v">{clusters.length}</div>
          <div className="l">Clusters</div>
        </div>
        <div className="stat">
          <div className="v">{criticalCount}</div>
          <div className="l">Critical events</div>
        </div>
        <div className="stat">
          <div className="v">{warningCount}</div>
          <div className="l">Warning events</div>
        </div>
        <div className="stat">
          <div className="v">{issues.length}</div>
          <div className="l">Unique issue groups</div>
        </div>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Cluster</th>
              <th>Engine</th>
              <th>Nodes</th>
              <th>Poll</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((c) => (
              <tr key={c.id}>
                <td>
                  <strong>{c.name}</strong>
                  <div className="pill">{c.id}</div>
                </td>
                <td>{c.engine}</td>
                <td>{c.node_count}</td>
                <td>{c.poll_interval_sec}s</td>
                <td className="action-links">
                  <Link className="btn primary" to={`/live?cluster=${c.id}`}>
                    Live Monitor
                  </Link>
                  <Link className="btn" to={`/logs?cluster=${c.id}`}>
                    Lets Check Logs
                  </Link>
                </td>
              </tr>
            ))}
            {!filtered.length && (
              <tr>
                <td colSpan={5} className="pill">
                  No clusters match your search.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
