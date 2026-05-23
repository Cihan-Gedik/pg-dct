import type { ReactNode } from "react";
import type { LogEntry } from "../api";

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

type Props = {
  lines: LogEntry[];
  loading: boolean;
  error: string | null;
  mode: "live" | "archive";
  paused?: boolean;
  onRefresh: () => void;
  onPauseToggle?: () => void;
  children: ReactNode;
};

export function LogStreamPanel({
  lines,
  loading,
  error,
  mode,
  paused,
  onRefresh,
  onPauseToggle,
  children,
}: Props) {
  return (
    <div className="log-panel">
      <div className="log-toolbar">
        <strong>Log stream</strong>
        <span className={`badge ${mode === "live" ? "live" : "info"}`}>
          {mode === "live" ? (paused ? "Paused" : "Live · 5s") : "Archive"}
        </span>
        <span className="pill">{lines.length} events</span>
        <div style={{ flex: 1 }} />
        {mode === "live" && onPauseToggle && (
          <button type="button" className="btn" onClick={onPauseToggle}>
            {paused ? "Resume" : "Pause"}
          </button>
        )}
        <button type="button" className="btn primary" onClick={onRefresh} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>
      {children}
      {error && <div className="err">{error}</div>}
      <div className="log-head">
        <span>Timestamp</span>
        <span>Host</span>
        <span>Source</span>
        <span>Level</span>
        <span>Message</span>
      </div>
      <div className="log-body">
        {lines.map((line, i) => (
          <div key={`${line.ts}-${i}`} className={`log-line ${line.level}`}>
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
  bundleId,
  setBundleId,
  showBundle,
}: {
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
  bundleId?: string;
  setBundleId?: (v: string) => void;
  showBundle?: boolean;
}) {
  const srcOpts = (
    <>
      <option value="include">Include</option>
      <option value="exclude">Exclude</option>
      <option value="errors">Errors only</option>
    </>
  );

  return (
    <div className="card">
      <div className="filters">
        {showBundle && setBundleId && (
          <div className="field">
            <label>Bundle</label>
            <select value={bundleId} onChange={(e) => setBundleId(e.target.value)}>
              <option value="live">Live tail</option>
              <option value="bnd-local">Local snapshot</option>
            </select>
          </div>
        )}
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
        <div className="field" style={{ minWidth: 180 }}>
          <label>Search</label>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="message, host…"
          />
        </div>
      </div>
    </div>
  );
}
