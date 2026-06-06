import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type ClusterListItem, type LiveCluster, type LogEntry } from "../api";
import { ClusterSelector } from "../components/ClusterSelector";
import { DcsHealthPanel } from "../components/DcsHealthPanel";
import { EtcdMemberTable } from "../components/EtcdMemberTable";
import { MemberTable } from "../components/MemberTable";
import { LogFiltersBar, LogStreamPanel } from "../components/LogStream";
import { useLogFilters } from "../hooks/useLogFilters";

type Tab = "overview" | "logs";

export default function LiveMonitor() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [clusters, setClusters] = useState<ClusterListItem[]>([]);
  const [live, setLive] = useState<LiveCluster | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [tab, setTab] = useState<Tab>((searchParams.get("tab") as Tab) || "overview");
  const [loadingLive, setLoadingLive] = useState(false);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [liveErr, setLiveErr] = useState<string | null>(null);
  const [logErr, setLogErr] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<string[]>([]);
  const [peerNoiseFiltered, setPeerNoiseFiltered] = useState(0);
  const [lastLiveRefresh, setLastLiveRefresh] = useState<Date | null>(null);
  const [lastLogRefresh, setLastLogRefresh] = useState<Date | null>(null);
  const [paused, setPaused] = useState(false);

  const initial = searchParams.get("cluster") || "lc-pg-main";
  const filters = useLogFilters(initial);

  useEffect(() => {
    const fromUrl = searchParams.get("cluster");
    if (fromUrl && fromUrl !== filters.clusterId) {
      filters.setClusterId(fromUrl);
    }
  }, [searchParams]);

  useEffect(() => {
    api.listClusters().then((list) => {
      setClusters(list);
      if (list.length && !list.find((c) => c.id === filters.clusterId)) {
        filters.setClusterId(list[0].id);
      }
    });
  }, []);

  const nodes = live?.members.map((m) => m.name) ?? [];

  const onClusterChange = useCallback(
    (id: string) => {
      filters.setClusterId(id);
      const next = new URLSearchParams(searchParams);
      next.set("cluster", id);
      setSearchParams(next, { replace: true });
    },
    [filters, searchParams, setSearchParams],
  );

  const setActiveTab = (t: Tab) => {
    setTab(t);
    const next = new URLSearchParams(searchParams);
    next.set("tab", t);
    setSearchParams(next, { replace: true });
  };

  const refreshLive = useCallback(async () => {
    if (!filters.clusterId) return;
    setLoadingLive(true);
    setLiveErr(null);
    try {
      const liveData = await api.live(filters.clusterId);
      setLive(liveData);
      setAlerts(liveData.alerts ?? []);
      setLastLiveRefresh(new Date());
    } catch (e) {
      setLiveErr(String(e));
    } finally {
      setLoadingLive(false);
    }
  }, [filters.clusterId]);

  const refreshLogs = useCallback(async () => {
    if (!filters.clusterId) return;
    setLoadingLogs(true);
    setLogErr(null);
    try {
      const logData = await api.logs(filters.clusterId, filters.params);
      setLogs(logData.lines);
      setPeerNoiseFiltered(logData.peer_noise_filtered ?? 0);
      setLastLogRefresh(new Date());
    } catch (e) {
      setLogErr(String(e));
    } finally {
      setLoadingLogs(false);
    }
  }, [filters.clusterId, filters.params]);

  const refreshAll = useCallback(async () => {
    await Promise.all([refreshLive(), refreshLogs()]);
  }, [refreshLive, refreshLogs]);

  useEffect(() => {
    refreshLive();
  }, [filters.clusterId]);

  useEffect(() => {
    if (tab === "logs") refreshLogs();
  }, [tab, refreshLogs]);

  useEffect(() => {
    if (paused) return;
    const t = setInterval(() => {
      refreshLive();
      if (tab === "logs") refreshLogs();
    }, 5000);
    return () => clearInterval(t);
  }, [paused, tab, refreshLive, refreshLogs]);

  const leaderMember = live?.members.find((m) => m.role === "leader");

  return (
    <div className="live-page live-page-simple">
      <header className="page-header compact">
        <div>
          <h1>Cluster Health</h1>
          <p className="sub">One cluster at a time — overview and logs</p>
        </div>
        <div className="row header-actions">
          <button type="button" className="btn primary" disabled={loadingLive || loadingLogs} onClick={refreshAll}>
            {loadingLive || loadingLogs ? "Refreshing…" : "Refresh"}
          </button>
          <button type="button" className="btn" onClick={() => setPaused((p) => !p)}>
            {paused ? "Resume 5s" : "Pause"}
          </button>
        </div>
      </header>

      <section className="cluster-bar card">
        <ClusterSelector clusters={clusters} selectedId={filters.clusterId} onSelect={onClusterChange} />
      </section>

      <nav className="page-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          className={tab === "overview" ? "active" : ""}
          aria-selected={tab === "overview"}
          onClick={() => setActiveTab("overview")}
        >
          Overview
          {live?.leader && <span className="tab-meta"> · {live.leader}</span>}
        </button>
        <button
          type="button"
          role="tab"
          className={tab === "logs" ? "active" : ""}
          aria-selected={tab === "logs"}
          onClick={() => setActiveTab("logs")}
        >
          Logs
          <span className="tab-meta"> · {logs.length} lines</span>
        </button>
        <Link className="tab-link" to={`/live-logs?cluster=${filters.clusterId}`}>
          Open full log view →
        </Link>
      </nav>

      {tab === "overview" && (
        <section className="tab-panel">
          {liveErr && <div className="err">{liveErr}</div>}
          {loadingLive && !live && <p className="pill">Loading…</p>}

          {live && (
            <>
              {alerts.length > 0 && (
                <div className="alert-banner">
                  {alerts.map((a) => (
                    <p key={a}>{a}</p>
                  ))}
                </div>
              )}

              <div className="overview-summary card">
                <div className="overview-row">
                  <span>
                    <strong>Scope</strong> {live.scope}
                  </span>
                  <span>
                    <strong>Primary</strong> {live.leader ?? "—"} ({leaderMember?.state ?? "—"})
                  </span>
                  <span>
                    <strong>Nodes</strong> {live.active_nodes}/{live.expected_nodes}
                  </span>
                  <span>
                    <strong>Switchovers</strong> {live.switchover_total}
                  </span>
                  <span className={`pill refresh-status ${loadingLive ? "loading" : ""}`}>
                    {lastLiveRefresh ? lastLiveRefresh.toLocaleTimeString() : "—"}
                  </span>
                </div>
              </div>

              <div className="stats stats-compact">
                <div className="stat">
                  <div className="v">{live.etcd_quorum ?? "—"}</div>
                  <div className="l">Quorum</div>
                </div>
                <div className="stat">
                  <div className="v">{live.max_lag_bytes ?? 0}</div>
                  <div className="l">Max lag</div>
                </div>
                <div className="stat">
                  <div className="v">{live.members.length}</div>
                  <div className="l">Members shown</div>
                </div>
              </div>

              <DcsHealthPanel live={live} dcs={live.dcs} />

              <MemberTable members={live.members} leader={live.leader} title="Patroni members" />

              <EtcdMemberTable
                members={live.etcd_members ?? []}
                leaderName={live.dcs?.etcd_raft_leader}
              />
            </>
          )}
        </section>
      )}

      {tab === "logs" && (
        <section className="tab-panel">
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
            timeRange={filters.timeRange}
            setTimeRange={filters.setTimeRange}
            rangeFrom={filters.rangeFrom}
            setRangeFrom={filters.setRangeFrom}
            rangeTo={filters.rangeTo}
            setRangeTo={filters.setRangeTo}
            onApplyPreset={filters.applyPreset}
          />

          <LogStreamPanel
            lines={logs}
            loading={loadingLogs}
            error={logErr}
            mode="live"
            paused={paused}
            lastRefresh={lastLogRefresh}
            timeRangeLabel={filters.timeRangeLabel}
            peerNoiseFiltered={peerNoiseFiltered}
            onRefresh={refreshLogs}
            onPauseToggle={() => setPaused((p) => !p)}
          />
        </section>
      )}
    </div>
  );
}
