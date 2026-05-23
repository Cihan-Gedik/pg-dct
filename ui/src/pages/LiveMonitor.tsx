import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type ClusterListItem, type ClusterRead, type LiveCluster, type LogEntry } from "../api";
import { LogFiltersBar, LogStreamPanel } from "../components/LogStream";
import { useLogFilters } from "../hooks/useLogFilters";

export default function LiveMonitor() {
  const [searchParams] = useSearchParams();
  const [clusters, setClusters] = useState<ClusterListItem[]>([]);
  const [clusterDetail, setClusterDetail] = useState<ClusterRead | null>(null);
  const [live, setLive] = useState<LiveCluster | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);

  const initial = searchParams.get("cluster") || "lc-pg-main";
  const filters = useLogFilters(initial);

  useEffect(() => {
    api.listClusters().then((list) => {
      setClusters(list);
      if (list.length && !list.find((c) => c.id === filters.clusterId)) {
        filters.setClusterId(list[0].id);
      }
    });
  }, []);

  const nodes = clusterDetail?.nodes.map((n) => n.member_name) ?? [];

  const refresh = useCallback(async () => {
    if (!filters.clusterId) return;
    setLoading(true);
    setErr(null);
    try {
      const [detail, liveData, logData] = await Promise.all([
        api.getCluster(filters.clusterId),
        api.live(filters.clusterId),
        api.logs(filters.clusterId, filters.params),
      ]);
      setClusterDetail(detail);
      setLive(liveData);
      setLogs(logData.lines);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }, [filters.clusterId, filters.params]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (paused) return;
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [paused, refresh]);

  return (
    <>
      <h1>Live Monitor</h1>
      <p className="sub">
        {live?.scope ?? filters.clusterId} · leader {live?.leader ?? "—"} · auto refresh 5s
      </p>

      <div className="stats">
        <div className="stat">
          <div className="v">{live?.leader?.split("-").pop() ?? "—"}</div>
          <div className="l">Leader</div>
        </div>
        <div className="stat">
          <div className="v">3/3</div>
          <div className="l">etcd quorum</div>
        </div>
        <div className="stat">
          <div className="v">{live?.max_lag_bytes ?? 0}</div>
          <div className="l">Max lag (bytes)</div>
        </div>
        <div className="stat">
          <div className="v">{live?.members[0]?.state ?? "—"}</div>
          <div className="l">Primary state</div>
        </div>
      </div>

      <div className="topology">
        <div className="topo-box">
          <h3>Patroni cluster</h3>
          {live?.members.map((m) => (
            <div key={m.name} className={`node-chip ${m.role === "leader" ? "leader" : ""}`}>
              <div>
                <strong>{m.name}</strong>
              </div>
              <div className={`badge ${m.role === "leader" ? "leader" : "replica"}`}>{m.role}</div>
              <div className="pill">{m.state}</div>
            </div>
          ))}
        </div>
      </div>

      {clusterDetail && (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Member</th>
                <th>Host</th>
                <th>role</th>
                <th>state</th>
              </tr>
            </thead>
            <tbody>
              {clusterDetail.nodes.map((n) => (
                <tr key={n.id}>
                  <td>{n.member_name}</td>
                  <td>{n.host}</td>
                  <td>
                    <span className={`badge ${n.role === "leader" ? "leader" : "replica"}`}>{n.role}</span>
                  </td>
                  <td>{n.state}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <LogFiltersBar
        clusters={clusters}
        clusterId={filters.clusterId}
        setClusterId={filters.setClusterId}
        nodes={nodes}
        node={filters.node}
        setNode={filters.setNode}
        severity={filters.severity}
        toggleSeverity={filters.toggleSeverity}
        patroni={filters.patroni}
        setPatroni={filters.setPatroni}
        postgres={filters.postgres}
        setPostgres={filters.setPostgres}
        etcd={filters.etcd}
        setEtcd={filters.setEtcd}
        osLog={filters.osLog}
        setOsLog={filters.setOsLog}
        search={filters.search}
        setSearch={filters.setSearch}
      />

      <LogStreamPanel
        lines={logs}
        loading={loading}
        error={err}
        mode="live"
        paused={paused}
        onRefresh={refresh}
        onPauseToggle={() => setPaused((p) => !p)}
      >
        <span />
      </LogStreamPanel>
    </>
  );
}
