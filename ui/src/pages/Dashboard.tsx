import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  api,
  type ClusterListItem,
  type ClusterTimeline,
  type DashboardIssue,
  type LiveCluster,
  type LogEntry,
} from "../api";
import { DashboardGridPanel } from "../components/DashboardGridPanel";
import { HealthUptimePanel } from "../components/HealthUptimePanel";
import { IncidentFeedMini } from "../components/IncidentFeedMini";
import { RoleTimeline } from "../components/RoleTimeline";
import { TopologyMap } from "../components/TopologyMap";
import type { PanelId } from "../lib/dashboardGrid";

type ClusterSnapshot = {
  id: string;
  status: "healthy" | "degraded" | "outage";
  healthy: number;
  degraded: number;
  outage: number;
  live: LiveCluster | null;
};

function parseTimeMs(v: string): number {
  const t = Date.parse(v);
  return Number.isFinite(t) ? t : 0;
}

function classifySnapshot(live: LiveCluster | null): ClusterSnapshot["status"] {
  if (!live) return "outage";
  const downCount = live.members.filter((m) => {
    const role = String(m.role || "").toLowerCase();
    const state = String(m.state || "").toLowerCase();
    return role === "unreachable" || state === "down" || state === "crashed";
  }).length;
  if (downCount > 0) return "outage";
  if ((live.alerts ?? []).length > 0 || (live.max_lag_bytes ?? 0) > 16 * 1024 * 1024) return "degraded";
  return "healthy";
}

function aggregateHod(live: LiveCluster | null): { healthy: number; degraded: number; outage: number } {
  if (!live) return { healthy: 0, degraded: 0, outage: 1 };
  let healthy = 0;
  let degraded = 0;
  let outage = 0;
  for (const m of live.members) {
    const role = String(m.role || "").toLowerCase();
    const state = String(m.state || "").toLowerCase();
    const lag = m.lag ?? 0;
    if (role === "unreachable" || state === "down" || state === "crashed") outage += 1;
    else if (lag > 4 * 1024 * 1024 || state === "starting") degraded += 1;
    else healthy += 1;
  }
  return { healthy, degraded, outage };
}

type WalSeriesRow = { hour: string; wal: number; checkpoint: number };

function hourKey(d: Date): string {
  return d.toISOString().slice(11, 13);
}

function isCheckpointMsg(msg: string): boolean {
  return /checkpoint|checkpoints|cp\s*complete|ending\s+checkpoint/i.test(msg);
}

function isWalMsg(msg: string): boolean {
  return /wal|xlog|archive_command|pg_wal|redo|transaction\s+log/i.test(msg);
}

/** Last N hour buckets (filled), normalized-friendly counts from postgres/patroni logs. */
function buildWalSeries(logs: LogEntry[], slotCount = 12): WalSeriesRow[] {
  const endMs = logs.reduce((max, l) => Math.max(max, parseTimeMs(l.ts)), Date.now());
  const slots: string[] = [];
  const buckets = new Map<string, { wal: number; checkpoint: number }>();

  for (let i = slotCount - 1; i >= 0; i--) {
    const key = hourKey(new Date(endMs - i * 3_600_000));
    slots.push(key);
    buckets.set(key, { wal: 0, checkpoint: 0 });
  }

  for (const line of logs) {
    const when = parseTimeMs(line.ts);
    if (!Number.isFinite(when) || when <= 0) continue;
    const key = hourKey(new Date(when));
    if (!buckets.has(key)) continue;
    const row = buckets.get(key)!;
    const msg = line.message.toLowerCase();
    if (isCheckpointMsg(msg)) {
      row.checkpoint += 1;
      continue;
    }
    if (isWalMsg(msg)) {
      row.wal += 3;
      continue;
    }
    if (line.source === "postgres") row.wal += 1;
    else if (line.source === "patroni" && /archive|backup|replicat|sync/i.test(msg)) row.wal += 1;
  }

  return slots.map((hour) => ({ hour, ...buckets.get(hour)! }));
}

function walBarHeight(value: number, max: number): string {
  if (value <= 0) return "0%";
  const pct = (value / Math.max(1, max)) * 100;
  return `${Math.max(12, Math.min(100, pct))}%`;
}

function clusterHealthIndex(live: LiveCluster | null): number {
  if (!live || !live.members.length) return 0;
  let score = 100;
  score -= (live.alerts?.length ?? 0) * 7;
  const down = live.members.filter((m) => String(m.role || "").toLowerCase() === "unreachable").length;
  score -= down * 25;
  const maxLagMb = (live.max_lag_bytes ?? 0) / (1024 * 1024);
  score -= Math.min(20, maxLagMb * 1.5);
  return Math.max(0, Math.min(100, score));
}

function dcsHealthIndex(live: LiveCluster | null): number {
  if (!live) return 0;
  let score = 100;
  const q = String(live.etcd_quorum ?? "").toLowerCase();
  if (q.includes("no") || q.includes("lost") || q.includes("false")) score -= 45;
  if (q.includes("unknown")) score -= 15;
  for (const m of live.members) {
    if (m.container_running === false) score -= 18;
    if (String(m.state || "").toLowerCase() === "down") score -= 12;
  }
  return Math.max(0, Math.min(100, score));
}

export default function Dashboard() {
  const [clusters, setClusters] = useState<ClusterListItem[]>([]);
  const [search, setSearch] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [snapshots, setSnapshots] = useState<Record<string, ClusterSnapshot>>({});
  const [selectedClusterId, setSelectedClusterId] = useState("");
  const [timeline, setTimeline] = useState<ClusterTimeline | null>(null);
  const [timelineErr, setTimelineErr] = useState<string | null>(null);
  const [loadingTimeline, setLoadingTimeline] = useState(false);
  const [timelineHours, setTimelineHours] = useState(168);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logsErr, setLogsErr] = useState<string | null>(null);
  const [issues, setIssues] = useState<DashboardIssue[]>([]);
  const [criticalCount, setCriticalCount] = useState(0);
  const [warningCount, setWarningCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [collapsedPanels, setCollapsedPanels] = useState<Record<PanelId, boolean>>({
    search: false,
    timeline: false,
    health: false,
    dcs: false,
    topology: false,
    wal: false,
    incidents: false,
    notes: false,
  });

  const refreshIssues = useCallback(async () => {
    try {
      const data = await api.dashboardIssues();
      setIssues(data.issues);
      setCriticalCount(data.critical_count);
      setWarningCount(data.warning_count);
    } catch {
      /* optional */
    }
  }, []);

  const refreshClusterMatrix = useCallback(async (clusterList: ClusterListItem[]) => {
    const entries = await Promise.all(
      clusterList.map(async (c): Promise<[string, ClusterSnapshot]> => {
        try {
          const live = await api.live(c.id);
          const hod = aggregateHod(live);
          return [
            c.id,
            {
              id: c.id,
              status: classifySnapshot(live),
              healthy: hod.healthy,
              degraded: hod.degraded,
              outage: hod.outage,
              live,
            },
          ];
        } catch {
          return [
            c.id,
            { id: c.id, status: "outage", healthy: 0, degraded: 0, outage: c.node_count || 1, live: null },
          ];
        }
      }),
    );
    setSnapshots(Object.fromEntries(entries));
  }, []);

  const refreshSelectedCluster = useCallback(async (clusterId: string) => {
    if (!clusterId) return;
    setTimelineErr(null);
    setLogsErr(null);
    setLoadingTimeline(true);
    try {
      setTimeline(await api.timeline(clusterId, timelineHours));
    } catch (e) {
      setTimelineErr(String(e));
      setTimeline(null);
    } finally {
      setLoadingTimeline(false);
    }
    try {
      const params = new URLSearchParams();
      params.set("severity", "critical,warning,info");
      params.set("patroni", "include");
      params.set("postgres", "include");
      params.set("etcd", "include");
      params.set("os", "errors");
      params.set("lines", "2000");
      setLogs((await api.logs(clusterId, params)).lines);
    } catch (e) {
      setLogsErr(String(e));
      setLogs([]);
    }
  }, [timelineHours]);

  const refreshAll = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const clusterList = await api.listClusters();
      setClusters(clusterList);
      const nextSelected = selectedClusterId || clusterList[0]?.id || "";
      setSelectedClusterId(nextSelected);
      await Promise.all([refreshClusterMatrix(clusterList), refreshIssues()]);
      await refreshSelectedCluster(nextSelected);
      setLastRefresh(new Date());
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }, [refreshClusterMatrix, refreshIssues, refreshSelectedCluster, selectedClusterId]);

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  useEffect(() => {
    if (!selectedClusterId) return;
    void refreshSelectedCluster(selectedClusterId);
  }, [selectedClusterId, timelineHours, refreshSelectedCluster]);

  const filteredClusters = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return clusters;
    return clusters.filter((c) => [c.id, c.name, c.engine].some((t) => t.toLowerCase().includes(q)));
  }, [clusters, search]);

  const selectedLive = snapshots[selectedClusterId]?.live ?? null;
  const selectedIssues = useMemo(
    () => issues.filter((i) => i.cluster_id === selectedClusterId).slice(0, 10),
    [issues, selectedClusterId],
  );
  const walSeries = useMemo(() => buildWalSeries(logs, 12), [logs]);
  const walMax = useMemo(() => Math.max(1, ...walSeries.map((r) => r.wal)), [walSeries]);
  const cpMax = useMemo(() => Math.max(1, ...walSeries.map((r) => r.checkpoint)), [walSeries]);
  const clusterChi = useMemo(() => clusterHealthIndex(selectedLive), [selectedLive]);
  const etcdChi = useMemo(() => dcsHealthIndex(selectedLive), [selectedLive]);
  const incidentFeed = useMemo(
    () => logs.filter((l) => l.level === "critical" || l.level === "warning").slice(0, 8),
    [logs],
  );

  const leader = selectedLive?.members.find((m) => String(m.role).toLowerCase().includes("leader"));
  const replicas = (selectedLive?.members ?? []).filter((m) => m !== leader);

  const expandAllPanels = () => {
    setCollapsedPanels({
      search: false,
      timeline: false,
      health: false,
      dcs: false,
      topology: false,
      wal: false,
      incidents: false,
      notes: false,
    });
  };

  const renderPanelBody = (panelId: PanelId) => {
    switch (panelId) {
      case "search":
        return (
          <>
            <div className="field field-grow">
              <label>Search Clusters</label>
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="prod-finance-01, db-analytics, app-stage..."
              />
            </div>
            <div className="ops-cluster-grid">
              {filteredClusters.map((c) => {
                const s = snapshots[c.id];
                return (
                  <button
                    type="button"
                    key={c.id}
                    onClick={() => setSelectedClusterId(c.id)}
                    className={`ops-cluster-card ${selectedClusterId === c.id ? "focus" : ""} ${s?.status ?? "outage"}`}
                  >
                    <div className="ops-cluster-title">
                      <span className={`dot ${s?.status ?? "outage"}`} />
                      <strong>{c.name}</strong>
                    </div>
                    <div className="ops-cluster-hod">
                      <span>H {s?.healthy ?? 0}</span>
                      <span>O {s?.outage ?? 0}</span>
                      <span>D {s?.degraded ?? 0}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </>
        );
      case "timeline":
        return (
          <RoleTimeline
            data={timeline}
            loading={loadingTimeline}
            hours={timelineHours}
            onHoursChange={setTimelineHours}
            error={timelineErr}
          />
        );
      case "health":
        return (
          <HealthUptimePanel
            variant="cluster"
            chi={clusterChi}
            live={selectedLive}
            timeline={timeline}
            subtitle={
              selectedLive?.alerts?.length ? selectedLive.alerts[0] : "No active split-brain risk detected."
            }
          />
        );
      case "dcs":
        return (
          <HealthUptimePanel
            variant="dcs"
            chi={etcdChi}
            live={selectedLive}
            timeline={timeline}
            subtitle={`etcd quorum: ${selectedLive?.etcd_quorum ?? "unknown"} · per-host container reachability`}
          />
        );
      case "topology":
        return <TopologyMap leader={leader} replicas={replicas} />;
      case "wal":
        return (
          <div className="wal-panel-fill">
            <div className="wal-legend">
              <span className="wal-legend-item wal">Hourly WAL volume</span>
              <span className="wal-legend-item checkpoint">Checkpoint count</span>
            </div>
            <div className="wal-chart">
              {walSeries.map((row) => (
                <div key={row.hour} className="wal-col">
                  <div className="bars">
                    <div
                      className="bar wal"
                      style={{ height: walBarHeight(row.wal, walMax) }}
                      title={`WAL activity: ${row.wal}`}
                    />
                    <div
                      className="bar checkpoint"
                      style={{ height: walBarHeight(row.checkpoint, cpMax) }}
                      title={`Checkpoints: ${row.checkpoint}`}
                    />
                  </div>
                  <small>{row.hour}:00</small>
                </div>
              ))}
            </div>
            {!walSeries.length && <p className="muted">{logsErr ?? "No WAL/checkpoint lines in window."}</p>}
          </div>
        );
      case "incidents":
        return (
          <IncidentFeedMini
            clusterId={selectedClusterId}
            criticalCount={criticalCount}
            warningCount={warningCount}
            issues={selectedIssues}
            logLines={incidentFeed}
          />
        );
      case "notes":
        return (
          <div className="ref-notes-strip">
            {replicas.some((r) => (r.lag ?? 0) > 8 * 1024 * 1024) ? (
              <p>
                <span className="ref-notes-warn">R3 Lagging:</span> Pending Restart required.
              </p>
            ) : selectedLive?.alerts?.length ? (
              <p>
                <span className="ref-notes-warn">DCS:</span> {selectedLive.alerts[0]}
              </p>
            ) : (
              <p className="muted">No active diagnostics flags.</p>
            )}
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="ref-dashboard ref-dashboard-fit">
      <div className="ref-topbar">
        <div className="ref-tabs">
          <span className="active">Dashboard</span>
          <Link to="/logs">Log Analyzer (Bundle Import)</Link>
          <Link to={`/live?cluster=${selectedClusterId || "lc-pg-main"}`}>Live Monitor</Link>
        </div>
        <div className="row header-actions">
          <button type="button" className="btn" onClick={expandAllPanels}>
            Expand panels
          </button>
          <button type="button" className="btn primary" disabled={loading} onClick={() => void refreshAll()}>
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      {err && <div className="err">{err}</div>}

      <section className="card ref-card dashboard-search-strip" aria-label="Search clusters">
        <div className="dashboard-search-strip-head">
          <h2>Search Clusters</h2>
        </div>
        <div className="dashboard-search-strip-body">{renderPanelBody("search")}</div>
      </section>

      <div className="dashboard-stack">
        <div className="dashboard-row dashboard-row-top">
          {(["topology", "health", "dcs"] as const).map((panelId) => (
            <DashboardGridPanel
              key={panelId}
              panelId={panelId}
              collapsed={collapsedPanels[panelId]}
              onToggleCollapse={(id) => setCollapsedPanels((p) => ({ ...p, [id]: !p[id] }))}
            >
              {renderPanelBody(panelId)}
            </DashboardGridPanel>
          ))}
        </div>

        <div className="dashboard-row dashboard-row-timeline">
          <DashboardGridPanel
            panelId="timeline"
            collapsed={collapsedPanels.timeline}
            onToggleCollapse={(id) => setCollapsedPanels((p) => ({ ...p, [id]: !p[id] }))}
          >
            {renderPanelBody("timeline")}
          </DashboardGridPanel>
        </div>

        <div className="dashboard-row dashboard-row-wal">
          <DashboardGridPanel
            panelId="wal"
            collapsed={collapsedPanels.wal}
            onToggleCollapse={(id) => setCollapsedPanels((p) => ({ ...p, [id]: !p[id] }))}
          >
            {renderPanelBody("wal")}
          </DashboardGridPanel>
        </div>

        <div className="dashboard-row dashboard-row-bottom">
          {(["notes", "incidents"] as const).map((panelId) => (
            <DashboardGridPanel
              key={panelId}
              panelId={panelId}
              collapsed={collapsedPanels[panelId]}
              onToggleCollapse={(id) => setCollapsedPanels((p) => ({ ...p, [id]: !p[id] }))}
            >
              {renderPanelBody(panelId)}
            </DashboardGridPanel>
          ))}
        </div>
      </div>
    </div>
  );
}
