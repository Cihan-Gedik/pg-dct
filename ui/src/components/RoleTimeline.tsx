import { useMemo, useState } from "react";
import type { ClusterTimeline } from "../api";

const RANGE_OPTIONS = [
  { label: "6h", hours: 6 },
  { label: "24h", hours: 24 },
  { label: "7d", hours: 168 },
  { label: "30d", hours: 720 },
] as const;

type Props = {
  data: ClusterTimeline | null;
  loading: boolean;
  hours: number;
  onHoursChange: (h: number) => void;
  error: string | null;
  /** Dashboard panel already has a title — skip outer card chrome. */
  embedded?: boolean;
};

function parseMs(iso: string): number {
  return new Date(iso).getTime();
}

function fmtAxis(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function fmtDuration(ms: number): string {
  if (ms < 60_000) return `${Math.round(ms / 1000)}s`;
  if (ms < 3_600_000) return `${Math.round(ms / 60_000)}m`;
  if (ms < 86_400_000) return `${(ms / 3_600_000).toFixed(1)}h`;
  return `${(ms / 86_400_000).toFixed(1)}d`;
}

function memberShort(name: string): string {
  const parts = name.split("-");
  const tail = parts[parts.length - 1] ?? name;
  return tail.length <= 4 ? tail : name.slice(0, 3).toUpperCase();
}

export function RoleTimeline({ data, loading, hours, onHoursChange, error, embedded = false }: Props) {
  const [hover, setHover] = useState<{
    member: string;
    role: string;
    start: string;
    end: string;
    reason: string;
    leader?: string | null;
  } | null>(null);
  const [showSwitches, setShowSwitches] = useState(false);

  const range = useMemo(() => {
    if (!data) return null;
    const start = parseMs(data.range_start);
    const end = parseMs(data.range_end);
    const span = Math.max(end - start, 1);
    const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => ({
      pct: f * 100,
      label: fmtAxis(new Date(start + span * f).toISOString()),
    }));
    return { start, end, span, ticks };
  }, [data]);

  if (error) return <div className="err">{error}</div>;
  if (loading && !data) return <p className="pill">Loading timeline…</p>;
  if (!data || !range) return null;

  const inner = (
    <>
      {!embedded && (
      <div className="rt-v2-head">
        <div>
          <h3 className="section-title">Leadership timeline</h3>
          <p className="pill">Who was primary over time · hover segments for details</p>
        </div>
        <div className="timeline-range">
          {RANGE_OPTIONS.map((o) => (
            <button
              key={o.hours}
              type="button"
              className={`btn btn-sm ${hours === o.hours ? "primary" : ""}`}
              onClick={() => onHoursChange(o.hours)}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>
      )}
      {embedded && (
        <div className="rt-v2-head embedded">
          <p className="pill">Who was primary over time · hover segments for details</p>
          <div className="timeline-range">
            {RANGE_OPTIONS.map((o) => (
              <button
                key={o.hours}
                type="button"
                className={`btn btn-sm ${hours === o.hours ? "primary" : ""}`}
                onClick={() => onHoursChange(o.hours)}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="rt-v2-legend">
        <span className="rt-legend-pill primary">Primary</span>
        <span className="rt-legend-pill replica">Replica</span>
        <span className="rt-legend-pill switch">Switchover</span>
      </div>

      <div className="rt-v2-chart">
        <div className="rt-v2-axis">
          {range.ticks.map((t) => (
            <span key={t.pct} style={{ left: `${t.pct}%` }}>
              {t.label}
            </span>
          ))}
        </div>

        <div className="rt-v2-switch-rail">
          {data.switchovers.map((sw, i) => {
            const x = ((parseMs(sw.at) - range.start) / range.span) * 100;
            if (x < 0 || x > 100) return null;
            return (
              <div
                key={i}
                className="rt-v2-switch-dot"
                style={{ left: `${x}%` }}
                title={`${sw.leader} · ${fmtAxis(sw.at)}`}
              />
            );
          })}
        </div>

        <div className="rt-v2-lanes">
          {data.members.map((row) => {
            const isNow = row.member === data.current_leader;
            return (
              <div key={row.member} className={`rt-v2-lane ${isNow ? "current" : ""}`}>
                <div className="rt-v2-node">
                  <span className="rt-v2-avatar">{memberShort(row.member)}</span>
                  <div className="rt-v2-node-text">
                    <strong title={row.member}>{row.member}</strong>
                    {isNow && <span className="badge leader">primary now</span>}
                  </div>
                </div>
                <div className="rt-v2-track">
                  {row.segments.map((seg, i) => {
                    const left = ((parseMs(seg.start) - range.start) / range.span) * 100;
                    const width = ((parseMs(seg.end) - parseMs(seg.start)) / range.span) * 100;
                    const dur = parseMs(seg.end) - parseMs(seg.start);
                    return (
                      <div
                        key={`${seg.start}-${i}`}
                        className={`rt-v2-seg ${seg.role}`}
                        style={{ left: `${left}%`, width: `${Math.max(width, 0.35)}%` }}
                        onMouseEnter={() =>
                          setHover({
                            member: row.member,
                            role: seg.role,
                            start: seg.start,
                            end: seg.end,
                            reason: seg.reason,
                            leader: seg.leader,
                          })
                        }
                        onMouseLeave={() => setHover(null)}
                      >
                        <span className="rt-v2-seg-label">
                          {seg.role === "leader" ? "P" : "R"} · {fmtDuration(dur)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {hover && (
        <div className="rt-v2-popover">
          <strong>{hover.member}</strong>
          <span className={`badge ${hover.role === "leader" ? "leader" : "replica"}`}>
            {hover.role === "leader" ? "PRIMARY" : "REPLICA"}
          </span>
          <p>
            {fmtAxis(hover.start)} → {fmtAxis(hover.end)}
            <br />
            Duration {fmtDuration(parseMs(hover.end) - parseMs(hover.start))}
          </p>
          {hover.role === "replica" && hover.leader && (
            <p className="pill">Following {hover.leader}</p>
          )}
          {hover.reason && <p className="pill">{hover.reason}</p>}
        </div>
      )}

      {data.switchovers.length > 0 && (
        <div className="rt-v2-foot">
          <button type="button" className="btn btn-sm" onClick={() => setShowSwitches((s) => !s)}>
            {showSwitches ? "Hide" : "Show"} {data.switchovers.length} switchover
            {data.switchovers.length === 1 ? "" : "s"}
          </button>
          {showSwitches && (
            <div className="rt-v2-switch-chips">
              {data.switchovers.map((sw, i) => (
                <span key={i} className="rt-switch-chip">
                  {fmtAxis(sw.at)} → {sw.leader}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );

  if (embedded) return <div className="rt-v2 rt-v2-embedded">{inner}</div>;
  return <div className="card rt-v2">{inner}</div>;
}
