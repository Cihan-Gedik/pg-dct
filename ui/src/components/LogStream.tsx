import type { ReactNode } from "react";
import type { BundleListItem, LogEntry } from "../api";

export type LogFilters = {
  clusterId: string;
  node: string;
  severity: Set<"critical" | "warning" | "info">;
  patroni: string;
  postgres: string;
  etcd: string;
  os: string;
  search: string;
};

type PanelProps = {
  lines: LogEntry[];
  loading: boolean;
  error: string | null;
  mode: "live" | "archive";
  paused?: boolean;
  lastRefresh: Date | null;
  peerNoiseFiltered?: number;
  onRefresh: () => void;
  onPauseToggle?: () => void;
  children?: ReactNode;
};

function formatTime(d: Date | null): string {
  if (!d) return "never";
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function LogStreamPanel({
  lines,
  loading,
  error,
  mode,
  paused,
  lastRefresh,
  peerNoiseFiltered = 0,
  onRefresh,
  onPauseToggle,
  children,
}: PanelProps) {
  const etcdCount = lines.filter((l) => l.source === "etcd").length;

  return (
    <div className="log-panel">
      <div className="log-toolbar">
        <strong>Log stream</strong>
        <span className={`badge ${mode === "live" ? "live" : "info"}`}>
          {mode === "live" ? (paused ? "Paused" : "Auto 5s") : "Archive"}
        </span>
        <span className="pill">{lines.length} events</span>
        <span className="pill">etcd: {etcdCount}</span>
        <span className={`pill refresh-status ${loading ? "loading" : ""}`}>
          Updated {formatTime(lastRefresh)}
        </span>
        {peerNoiseFiltered > 0 && (
          <span className="pill" title="Enable “Hide peer noise” to reduce these">
            {peerNoiseFiltered} peer lines hidden
          </span>
        )}
        <div style={{ flex: 1 }} />
        {mode === "live" && onPauseToggle && (
          <button type="button" className="btn" onClick={onPauseToggle}>
            {paused ? "Resume auto" : "Pause auto"}
          </button>
        )}
        <button type="button" className="btn primary" onClick={onRefresh} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh logs"}
        </button>
      </div>
      {children}
      {error && <div className="err">{error}</div>}
      {!loading && lines.length === 0 && !error && (
        <div className="log-empty">No log lines match filters. Try “etcd only” or clear search.</div>
      )}
      <div className="log-head">
        <span>Timestamp</span>
        <span>Host</span>
        <span>Source</span>
        <span>Level</span>
        <span>Message</span>
      </div>
      <div className="log-body">
        {lines.map((line, i) => (
          <div key={`${line.ts}-${line.member_name}-${i}`} className={`log-line ${line.level}`}>
            <span>{line.ts || "—"}</span>
            <span>{line.member_name || line.node}</span>
            <span>{line.source}</span>
            <span>
              <span className={`badge ${line.level}`}>{line.level}</span>
            </span>
            <span>{line.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

type FilterBarProps = {
  clusters: { id: string; name: string }[];
  clusterId: string;
  setClusterId: (v: string) => void;
  nodes: string[];
  node: string;
  setNode: (v: string) => void;
  severity: Set<"critical" | "warning" | "info">;
  toggleSeverity: (l: "critical" | "warning" | "info") => void;
  patroni: string;
  setPatroni: (v: string) => void;
  postgres: string;
  setPostgres: (v: string) => void;
  etcd: string;
  setEtcd: (v: string) => void;
  osLog: string;
  setOsLog: (v: string) => void;
  search: string;
  setSearch: (v: string) => void;
  suppressPeerNoise: boolean;
  setSuppressPeerNoise: (v: boolean) => void;
  onApplyPreset: (p: "all" | "etcd" | "patroni" | "errors") => void;
  bundleId?: string;
  setBundleId?: (v: string) => void;
  bundleOptions?: BundleListItem[];
  showBundle?: boolean;
  includeLiveBundleOption?: boolean;
};

export function LogFiltersBar({
  clusters,
  clusterId,
  setClusterId,
  nodes,
  node,
  setNode,
  severity,
  toggleSeverity,
  patroni,
  setPatroni,
  postgres,
  setPostgres,
  etcd,
  setEtcd,
  osLog,
  setOsLog,
  search,
  setSearch,
  suppressPeerNoise,
  setSuppressPeerNoise,
  onApplyPreset,
  bundleId,
  setBundleId,
  bundleOptions = [],
  showBundle,
  includeLiveBundleOption = true,
}: FilterBarProps) {
  const srcOpts = (
    <>
      <option value="include">Include</option>
      <option value="exclude">Exclude</option>
      <option value="errors">Errors only</option>
    </>
  );

  return (
    <div className="card filters-card">
      <div className="filters-presets">
        <span className="filters-presets-label">Quick:</span>
        <button type="button" className="btn btn-sm" onClick={() => onApplyPreset("all")}>
          All sources
        </button>
        <button type="button" className="btn btn-sm" onClick={() => onApplyPreset("etcd")}>
          etcd only
        </button>
        <button type="button" className="btn btn-sm" onClick={() => onApplyPreset("patroni")}>
          Patroni only
        </button>
        <button type="button" className="btn btn-sm" onClick={() => onApplyPreset("errors")}>
          Errors only
        </button>
      </div>
      <div className="filters">
        <div className="field">
          <label>Cluster</label>
          <select value={clusterId} onChange={(e) => setClusterId(e.target.value)}>
            {clusters.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        {showBundle && setBundleId && (
          <div className="field">
            <label>Bundle</label>
            <select value={bundleId} onChange={(e) => setBundleId(e.target.value)}>
              {includeLiveBundleOption && <option value="live">Live tail</option>}
              {bundleOptions.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.id} ({b.line_count} lines)
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="field">
          <label>Node</label>
          <select value={node} onChange={(e) => setNode(e.target.value)}>
            <option value="all">All nodes</option>
            {nodes.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Severity</label>
          <div className="sev-toggle">
            {(["critical", "warning", "info"] as const).map((lv) => (
              <button
                key={lv}
                type="button"
                className={`${severity.has(lv) ? "on" : ""} ${lv}`}
                onClick={() => toggleSeverity(lv)}
              >
                {lv}
              </button>
            ))}
          </div>
        </div>
        <div className="field">
          <label>Patroni</label>
          <select value={patroni} onChange={(e) => setPatroni(e.target.value)}>
            {srcOpts}
          </select>
        </div>
        <div className="field">
          <label>PostgreSQL</label>
          <select value={postgres} onChange={(e) => setPostgres(e.target.value)}>
            {srcOpts}
          </select>
        </div>
        <div className="field">
          <label>etcd</label>
          <select value={etcd} onChange={(e) => setEtcd(e.target.value)}>
            {srcOpts}
          </select>
        </div>
        <div className="field">
          <label>OS</label>
          <select value={osLog} onChange={(e) => setOsLog(e.target.value)}>
            {srcOpts}
          </select>
        </div>
        <div className="field field-grow">
          <label>Search</label>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="message, host, 172.18…"
          />
        </div>
      </div>
      <label className="filter-checkbox">
        <input
          type="checkbox"
          checked={suppressPeerNoise}
          onChange={(e) => setSuppressPeerNoise(e.target.checked)}
        />
        Hide repeated etcd peer errors (dial tcp …:2380 refused)
      </label>
    </div>
  );
}
