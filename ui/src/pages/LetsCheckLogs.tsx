import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, type ClusterListItem, type LogEntry } from "../api";
import { ClusterSelector } from "../components/ClusterSelector";
import { LogFiltersBar, LogStreamPanel } from "../components/LogStream";
import { useLogFilters } from "../hooks/useLogFilters";

export default function LetsCheckLogs() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [clusters, setClusters] = useState<ClusterListItem[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [peerNoiseFiltered, setPeerNoiseFiltered] = useState(0);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [bundleId, setBundleId] = useState("live");
  const [nodes, setNodes] = useState<string[]>([]);

  const initial = searchParams.get("cluster") || "lc-pg-main";
  const filters = useLogFilters(initial);

  useEffect(() => {
    api.listClusters().then(setClusters);
  }, []);

  const onClusterChange = useCallback(
    (id: string) => {
      filters.setClusterId(id);
      navigate(`/logs?cluster=${encodeURIComponent(id)}`, { replace: true });
    },
    [filters, navigate],
  );

  useEffect(() => {
    if (!filters.clusterId) return;
    api.getCluster(filters.clusterId).then((c) => setNodes(c.nodes.map((n) => n.member_name)));
  }, [filters.clusterId]);

  const refresh = useCallback(async () => {
    if (!filters.clusterId) return;
    setLoading(true);
    setErr(null);
    try {
      const logData = await api.logs(filters.clusterId, filters.params);
      setLogs(logData.lines);
      setPeerNoiseFiltered(logData.peer_noise_filtered ?? 0);
      setLastRefresh(new Date());
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }, [filters.clusterId, filters.params]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Lets Check Logs</h1>
          <p className="sub">Deep log view for cluster {filters.clusterId}</p>
        </div>
        <button type="button" className="btn primary" disabled={loading} onClick={refresh}>
          {loading ? "Refreshing…" : "Refresh logs"}
        </button>
      </header>

      <section className="cluster-bar card">
        <ClusterSelector clusters={clusters} selectedId={filters.clusterId} onSelect={onClusterChange} />
      </section>

      <LogFiltersBar
        clusters={clusters}
        clusterId={filters.clusterId}
        setClusterId={onClusterChange}
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
        suppressPeerNoise={filters.suppressPeerNoise}
        setSuppressPeerNoise={filters.setSuppressPeerNoise}
        onApplyPreset={filters.applyPreset}
        showBundle
        bundleId={bundleId}
        setBundleId={setBundleId}
      />

      <LogStreamPanel
        lines={logs}
        loading={loading}
        error={err}
        mode="archive"
        lastRefresh={lastRefresh}
        peerNoiseFiltered={peerNoiseFiltered}
        onRefresh={refresh}
      />
    </>
  );
}
