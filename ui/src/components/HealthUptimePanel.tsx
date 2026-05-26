import type { ClusterTimeline, LiveCluster } from "../api";

function fmtDuration(ms: number): string {
  if (ms < 60_000) return `${Math.round(ms / 1000)}s`;
  if (ms < 3_600_000) return `${Math.round(ms / 60_000)}m`;
  if (ms < 86_400_000) return `${(ms / 3_600_000).toFixed(1)}h`;
  return `${(ms / 86_400_000).toFixed(1)}d`;
}

function parseMs(iso: string): number {
  const t = Date.parse(iso);
  return Number.isFinite(t) ? t : 0;
}

export type NodeUptime = {
  name: string;
  host: string;
  upMs: number;
  upPct: number;
  state: string;
};

export function computeNodeUptimes(
  timeline: ClusterTimeline | null,
  live: LiveCluster | null,
): { dbUpMs: number; dbUpPct: number; nodes: NodeUptime[] } {
  if (!timeline) {
    const nodes =
      live?.members.map((m) => ({
        name: m.name,
        host: m.host,
        upMs: m.container_running === false ? 0 : 0,
        upPct: m.container_running === false ? 0 : 100,
        state: m.state ?? m.role,
      })) ?? [];
    return { dbUpMs: 0, dbUpPct: 0, nodes };
  }

  const rangeStart = parseMs(timeline.range_start);
  const rangeEnd = parseMs(timeline.range_end);
  const span = Math.max(rangeEnd - rangeStart, 1);

  const nodes: NodeUptime[] = timeline.members.map((row) => {
    let up = 0;
    for (const seg of row.segments) {
      const role = String(seg.role || "").toLowerCase();
      if (role === "unreachable" || role === "down") continue;
      up += Math.max(0, parseMs(seg.end) - parseMs(seg.start));
    }
    const liveM = live?.members.find((m) => m.name === row.member);
    return {
      name: row.member,
      host: liveM?.host ?? "—",
      upMs: up,
      upPct: Math.min(100, (up / span) * 100),
      state: liveM?.state ?? liveM?.role ?? "—",
    };
  });

  const leaderRow = timeline.members.find((m) =>
    m.segments.some((s) => String(s.role).toLowerCase().includes("leader")),
  );
  let dbUp = span;
  if (leaderRow) {
    dbUp = leaderRow.segments
      .filter((s) => String(s.role).toLowerCase().includes("leader"))
      .reduce((acc, s) => acc + Math.max(0, parseMs(s.end) - parseMs(s.start)), 0);
  }

  return { dbUpMs: dbUp, dbUpPct: Math.min(100, (dbUp / span) * 100), nodes };
}

type Props = {
  variant: "cluster" | "dcs";
  chi: number;
  live: LiveCluster | null;
  timeline: ClusterTimeline | null;
  subtitle: string;
};

export function HealthUptimePanel({ variant, chi, live, timeline, subtitle }: Props) {
  const { dbUpMs, dbUpPct, nodes } = computeNodeUptimes(timeline, live);

  return (
    <div className={`health-uptime ${variant}`}>
      <div className="chi-wrap compact">
        <div className="chi-ring" style={{ ["--chi" as string]: `${chi}%` }}>
          <div className="chi-value">{chi.toFixed(1)}%</div>
          <div className="chi-label">{variant === "cluster" ? "Healthy" : "Quorum"}</div>
        </div>
        <div className="chi-side">
          <div className="chi-side-item">
            <strong>{fmtDuration(dbUpMs)}</strong>
            <span>{variant === "cluster" ? "DB up (window)" : "DCS up (window)"}</span>
          </div>
          <div className="chi-side-item">
            <strong>{dbUpPct.toFixed(0)}%</strong>
            <span>Uptime in selected range</span>
          </div>
        </div>
      </div>
      <p className="muted health-sub">{subtitle}</p>

      <div className="uptime-list-head">
        <span>{variant === "cluster" ? "Node uptime" : "etcd / host uptime"}</span>
      </div>
      <ul className="uptime-list">
        {nodes.map((n) => (
          <li key={n.name}>
            <div className="uptime-node-meta">
              <strong>{n.name}</strong>
              <small>{n.host}</small>
            </div>
            <div className="uptime-bar-wrap">
              <div className="uptime-bar" style={{ width: `${n.upPct}%` }} />
            </div>
            <span className="uptime-val">{fmtDuration(n.upMs)}</span>
          </li>
        ))}
        {!nodes.length && <li className="muted">No node data.</li>}
      </ul>
      {variant === "dcs" && (
        <p className="pill dcs-quorum-pill">etcd quorum: {live?.etcd_quorum ?? "unknown"}</p>
      )}
    </div>
  );
}
