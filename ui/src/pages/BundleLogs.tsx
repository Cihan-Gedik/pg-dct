import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, type BundleListItem, type ClusterListItem, type CustomerListItem, type LogEntry } from "../api";
import { ClusterSelector } from "../components/ClusterSelector";
import { LogFiltersBar, LogStreamPanel } from "../components/LogStream";
import { useLogFilters } from "../hooks/useLogFilters";

export default function BundleLogs() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [clusters, setClusters] = useState<ClusterListItem[]>([]);
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState(searchParams.get("customer") || "");
  const [bundles, setBundles] = useState<BundleListItem[]>([]);
  const [bundleId, setBundleId] = useState(searchParams.get("bundle") || "");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [peerNoiseFiltered, setPeerNoiseFiltered] = useState(0);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [nodes, setNodes] = useState<string[]>([]);

  const initialCluster = searchParams.get("cluster") || "lc-pg-main";
  const severityFromUrl = searchParams.get("severity");
  const filters = useLogFilters(initialCluster, severityFromUrl);

  useEffect(() => {
    api.listClusters().then(setClusters);
    api.listCustomers().then(setCustomers);
  }, []);

  useEffect(() => {
    filters.applySeverityParam(severityFromUrl);
  }, [severityFromUrl, filters.applySeverityParam]);

  useEffect(() => {
    if (!selectedCustomer) {
      setBundles([]);
      setBundleId("");
      setLogs([]);
      return;
    }
    api.listBundles({ customerName: selectedCustomer }).then((list) => {
      setBundles(list);
      const byUrl = searchParams.get("bundle");
      const targetBundle = byUrl && list.some((b) => b.id === byUrl) ? byUrl : list[0]?.id || "";
      setBundleId(targetBundle);
      const selected = list.find((b) => b.id === targetBundle) || list[0];
      if (selected?.cluster_id && selected.cluster_id !== filters.clusterId) {
        filters.setClusterId(selected.cluster_id);
      }
    });
  }, [selectedCustomer, searchParams, filters.clusterId, filters.setClusterId]);

  useEffect(() => {
    if (!filters.clusterId || !selectedCustomer) return;
    api.getCluster(filters.clusterId).then((c) => setNodes(c.nodes.map((n) => n.member_name)));
  }, [filters.clusterId, selectedCustomer]);

  const selectedBundle = useMemo(
    () => bundles.find((b) => b.id === bundleId) ?? null,
    [bundles, bundleId],
  );

  const onCustomerChange = useCallback(
    (name: string) => {
      setSelectedCustomer(name);
      setErr(null);
      const q = new URLSearchParams();
      if (name) q.set("customer", name);
      navigate(`/bundle-logs${q.toString() ? `?${q.toString()}` : ""}`, { replace: true });
    },
    [navigate],
  );

  const onClusterChange = useCallback(
    (id: string) => {
      filters.setClusterId(id);
      const q = new URLSearchParams();
      if (selectedCustomer) q.set("customer", selectedCustomer);
      q.set("cluster", id);
      if (bundleId) q.set("bundle", bundleId);
      navigate(`/bundle-logs?${q.toString()}`, { replace: true });
    },
    [filters, navigate, selectedCustomer, bundleId],
  );

  const onBundleChange = useCallback(
    (id: string) => {
      setBundleId(id);
      const selected = bundles.find((b) => b.id === id);
      if (selected?.cluster_id && selected.cluster_id !== filters.clusterId) {
        filters.setClusterId(selected.cluster_id);
      }
      const q = new URLSearchParams();
      if (selectedCustomer) q.set("customer", selectedCustomer);
      if (selected?.cluster_id) q.set("cluster", selected.cluster_id);
      q.set("bundle", id);
      navigate(`/bundle-logs?${q.toString()}`, { replace: true });
    },
    [bundles, filters, navigate, selectedCustomer],
  );

  const refresh = useCallback(async () => {
    if (!selectedCustomer || !bundleId) {
      setLogs([]);
      return;
    }
    setLoading(true);
    setErr(null);
    try {
      const logData = await api.bundleLogs(bundleId, filters.params);
      setLogs(logData.lines);
      setPeerNoiseFiltered(logData.peer_noise_filtered ?? 0);
      setLastRefresh(new Date());
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }, [selectedCustomer, bundleId, filters.params]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Troubleshoot</h1>
          <p className="sub">
            {selectedCustomer
              ? `Imported bundle logs · ${selectedCustomer}${selectedBundle ? ` · ${selectedBundle.id}` : ""}`
              : "Imported bundle logs appear after selecting a customer."}
          </p>
        </div>
        <button type="button" className="btn primary" disabled={loading || !bundleId} onClick={refresh}>
          {loading ? "Refreshing…" : "Refresh logs"}
        </button>
      </header>

      <section className="card">
        <div className="field field-grow">
          <label>Customer</label>
          <select value={selectedCustomer} onChange={(e) => onCustomerChange(e.target.value)}>
            <option value="">Select</option>
            {customers.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name} ({c.bundle_count})
              </option>
            ))}
          </select>
        </div>
      </section>

      {!selectedCustomer ? (
        <section className="card">
          <p>This screen only shows imported customer bundle data. Select a customer to continue.</p>
        </section>
      ) : (
        <>
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
            includeLiveBundleOption={false}
            bundleId={bundleId}
            setBundleId={onBundleChange}
            bundleOptions={bundles}
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
      )}
    </>
  );
}
