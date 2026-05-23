import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, type ClusterListItem, type ClusterRead, type LogEntry } from "../api";
import { LogFiltersBar, LogStreamPanel } from "../components/LogStream";
import { useLogFilters } from "../hooks/useLogFilters";

export default function LetsCheckLogs() {
  const [searchParams] = useSearchParams();
  const [clusters, setClusters] = useState<ClusterListItem[]>([]);
  const [clusterDetail, setClusterDetail] = useState<ClusterRead | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [bundleId, setBundleId] = useState("live");

  const initial = searchParams.get("cluster") || "lc-pg-main";
  const filters = useLogFilters(initial);

  useEffect(() => {
    api.listClusters().then(setClusters);
  }, []);

  const nodes = clusterDetail?.nodes.map((n) => n.member_name) ?? [];

  const refresh = useCallback(async () => {
    if (!filters.clusterId) return;
    setLoading(true);
    setErr(null);
    try {
      const detail = await api.getCluster(filters.clusterId);
      setClusterDetail(detail);
      const logData = await api.logs(filters.clusterId, filters.params);
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

  return (
    <>
      <h1>Lets Check Logs</h1>
      <p className="sub">Filtered log view · live tail or future bundle archive</p>

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
        showBundle
        bundleId={bundleId}
        setBundleId={setBundleId}
      />

      <LogStreamPanel lines={logs} loading={loading} error={err} mode="archive" onRefresh={refresh}>
        <span className="pill">Bundle mode: {bundleId} (live uses docker exec tail)</span>
      </LogStreamPanel>
    </>
  );
}
