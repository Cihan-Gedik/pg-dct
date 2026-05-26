import { useMemo } from "react";
import type { LiveMember } from "../api";

const VB_W = 400;
const LEADER_R = 24;
const REPLICA_R = 18;
const LEADER_X = 68;
const REPLICA_X = 292;
const PAD_Y = 28;
const ROW_GAP = 50;

const LAG_WARN_BYTES = 4 * 1024 * 1024;
const LAG_CRITICAL_BYTES = 8 * 1024 * 1024;

type NodeSlot = { cx: number; cy: number; r: number; index: number };

type LegStyle = {
  stroke: string;
  dash?: string;
  marker: string;
  label: string;
  solid: boolean;
};

type NodeStyle = {
  fill: string;
  stroke: string;
};

const HEALTH_PALETTE: NodeStyle[] = [
  { fill: "url(#topo-fill-r1)", stroke: "#22c55e" },
  { fill: "url(#topo-fill-r2)", stroke: "#38bdf8" },
  { fill: "url(#topo-fill-r3)", stroke: "#a78bfa" },
];

function lagLabel(bytes: number | null | undefined): string {
  if (bytes == null || bytes <= 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function isUnreachable(m: LiveMember): boolean {
  const role = String(m.role || "").toLowerCase();
  const state = String(m.state || "").toLowerCase();
  return role === "unreachable" || state === "down" || state === "crashed" || state === "stopped";
}

function legStyleFor(m: LiveMember): LegStyle {
  const lag = m.lag ?? 0;
  if (isUnreachable(m)) {
    return {
      stroke: "#ef4444",
      dash: "5 4",
      marker: "url(#topo-arr-red)",
      label: "Unreachable",
      solid: false,
    };
  }
  if (lag >= LAG_CRITICAL_BYTES) {
    return {
      stroke: "#f59e0b",
      dash: "7 5",
      marker: "url(#topo-arr-orange)",
      label: "Lagging…",
      solid: false,
    };
  }
  if (lag >= LAG_WARN_BYTES) {
    return {
      stroke: "#f59e0b",
      dash: "7 5",
      marker: "url(#topo-arr-orange)",
      label: "Replication lag…",
      solid: false,
    };
  }
  const state = String(m.state || "").toLowerCase();
  const idx = 0;
  const stroke = HEALTH_PALETTE[idx % HEALTH_PALETTE.length].stroke;
  return {
    stroke,
    marker: stroke === "#22c55e" ? "url(#topo-arr-green)" : "url(#topo-arr-blue)",
    label: state.includes("stream") ? `Streaming · ${lagLabel(lag)}` : lagLabel(lag),
    solid: !state.includes("stream"),
  };
}

function nodeStyleFor(m: LiveMember, index: number): NodeStyle {
  const lag = m.lag ?? 0;
  if (isUnreachable(m)) {
    return { fill: "url(#topo-fill-down)", stroke: "#ef4444" };
  }
  if (lag >= LAG_WARN_BYTES) {
    return { fill: "url(#topo-fill-r3)", stroke: "#f59e0b" };
  }
  return HEALTH_PALETTE[index % HEALTH_PALETTE.length];
}

function legStyleForIndex(m: LiveMember, index: number): LegStyle {
  const base = legStyleFor(m);
  if (isUnreachable(m) || (m.lag ?? 0) >= LAG_WARN_BYTES) return base;
  const stroke = HEALTH_PALETTE[index % HEALTH_PALETTE.length].stroke;
  const marker =
    stroke === "#22c55e"
      ? "url(#topo-arr-green)"
      : stroke === "#38bdf8"
        ? "url(#topo-arr-blue)"
        : "url(#topo-arr-violet)";
  return { ...base, stroke, marker, solid: index % 2 === 1 };
}

function replicaStatus(m: LiveMember, index: number): string {
  const tag = `R${index + 1}`;
  if (isUnreachable(m)) return `${tag} · down`;
  const lag = m.lag ?? 0;
  if (lag >= LAG_CRITICAL_BYTES) return `${tag} · lagging`;
  const state = String(m.state || "").toLowerCase();
  if (state) return `${tag} · ${state}`;
  return `${tag} · ${lagLabel(lag)}`;
}

function buildLegPath(leaderCy: number, replicaCy: number): string {
  const x0 = LEADER_X + LEADER_R;
  const y0 = leaderCy;
  const x1 = REPLICA_X - REPLICA_R;
  const y1 = replicaCy;
  if (Math.abs(y1 - y0) < 6) {
    return `M ${x0} ${y0} L ${x1} ${y1}`;
  }
  const cpx = (x0 + x1) / 2;
  const cpy = (y0 + y1) / 2;
  return `M ${x0} ${y0} Q ${cpx} ${cpy} ${x1} ${y1}`;
}

function computeLayout(replicaCount: number): { h: number; leaderCy: number; slots: NodeSlot[] } {
  if (replicaCount <= 0) {
    const h = 140;
    return { h, leaderCy: h / 2, slots: [] };
  }
  const span = replicaCount <= 1 ? 0 : (replicaCount - 1) * ROW_GAP;
  const h = Math.max(140, span + PAD_Y * 2 + REPLICA_R * 2);
  const leaderCy = h / 2;
  const slots: NodeSlot[] = [];

  if (replicaCount === 1) {
    slots.push({ cx: REPLICA_X, cy: leaderCy, r: REPLICA_R, index: 0 });
    return { h, leaderCy, slots };
  }

  const top = PAD_Y + REPLICA_R;
  const bottom = h - PAD_Y - REPLICA_R;
  for (let i = 0; i < replicaCount; i++) {
    const cy = top + (i / (replicaCount - 1)) * (bottom - top);
    slots.push({ cx: REPLICA_X, cy, r: REPLICA_R, index: i });
  }
  return { h, leaderCy, slots };
}

type Props = {
  leader: LiveMember | undefined;
  replicas: LiveMember[];
};

export function TopologyMap({ leader, replicas }: Props) {
  const sorted = useMemo(
    () => [...replicas].sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true })),
    [replicas],
  );

  const layout = useMemo(() => computeLayout(sorted.length), [sorted.length]);

  const legs = useMemo(
    () =>
      sorted.map((member, i) => {
        const slot = layout.slots[i];
        const path = buildLegPath(layout.leaderCy, slot.cy);
        return {
          id: `leg-${member.name}`,
          d: path,
          member,
          slot,
          style: legStyleForIndex(member, i),
        };
      }),
    [sorted, layout],
  );

  if (!leader && sorted.length === 0) {
    return (
      <div className="topo-ref topo-ref-round topo-ref-svg-only">
        <p className="muted topo-empty">No Patroni members to display.</p>
      </div>
    );
  }

  return (
    <div className="topo-ref topo-ref-round topo-ref-svg-only">
      <svg
        className="topo-ref-svg"
        viewBox={`0 0 ${VB_W} ${layout.h}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={`Cluster topology: 1 leader, ${sorted.length} replica${sorted.length === 1 ? "" : "s"}`}
      >
        <defs>
          <radialGradient id="topo-fill-leader" cx="35%" cy="30%" r="65%">
            <stop offset="0%" stopColor="#34d399" />
            <stop offset="55%" stopColor="#15803d" />
            <stop offset="100%" stopColor="#0f3d24" />
          </radialGradient>
          <radialGradient id="topo-fill-r1" cx="35%" cy="30%" r="65%">
            <stop offset="0%" stopColor="#4ade80" />
            <stop offset="55%" stopColor="#16a34a" />
            <stop offset="100%" stopColor="#14532d" />
          </radialGradient>
          <radialGradient id="topo-fill-r2" cx="35%" cy="30%" r="65%">
            <stop offset="0%" stopColor="#7dd3fc" />
            <stop offset="55%" stopColor="#2563eb" />
            <stop offset="100%" stopColor="#1e3a5f" />
          </radialGradient>
          <radialGradient id="topo-fill-r3" cx="35%" cy="30%" r="65%">
            <stop offset="0%" stopColor="#fdba74" />
            <stop offset="55%" stopColor="#ea580c" />
            <stop offset="100%" stopColor="#431407" />
          </radialGradient>
          <radialGradient id="topo-fill-down" cx="35%" cy="30%" r="65%">
            <stop offset="0%" stopColor="#fca5a5" />
            <stop offset="55%" stopColor="#dc2626" />
            <stop offset="100%" stopColor="#450a0a" />
          </radialGradient>

          <marker id="topo-arr-green" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
            <path d="M0,0 L7,3.5 L0,7 z" fill="#22c55e" />
          </marker>
          <marker id="topo-arr-blue" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
            <path d="M0,0 L7,3.5 L0,7 z" fill="#38bdf8" />
          </marker>
          <marker id="topo-arr-violet" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
            <path d="M0,0 L7,3.5 L0,7 z" fill="#a78bfa" />
          </marker>
          <marker id="topo-arr-orange" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
            <path d="M0,0 L7,3.5 L0,7 z" fill="#f59e0b" />
          </marker>
          <marker id="topo-arr-red" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
            <path d="M0,0 L7,3.5 L0,7 z" fill="#ef4444" />
          </marker>

          {legs.map((leg) => (
            <path key={leg.id} id={leg.id} d={leg.d} fill="none" />
          ))}
        </defs>

        {legs.map((leg) => (
          <g key={leg.id} className="topo-leg">
            <use
              href={`#${leg.id}`}
              stroke={leg.style.stroke}
              strokeWidth={2}
              strokeDasharray={leg.style.dash}
              fill="none"
              markerEnd={leg.style.marker}
              className={leg.style.solid ? "topo-leg-solid" : "topo-leg-dashed"}
            />
            <text className="topo-leg-textpath">
              <textPath href={`#${leg.id}`} startOffset="42%" textAnchor="middle">
                {leg.style.label}
              </textPath>
            </text>
          </g>
        ))}

        {leader && (
          <g className="topo-node topo-node-leader">
            <circle
              cx={LEADER_X}
              cy={layout.leaderCy}
              r={LEADER_R}
              fill="url(#topo-fill-leader)"
              stroke="#22c55e"
              strokeWidth={2}
            />
            <text x={LEADER_X} y={layout.leaderCy - 6} className="topo-node-glyph" textAnchor="middle">
              ⚡
            </text>
            <text x={LEADER_X} y={layout.leaderCy + 5} className="topo-node-id" textAnchor="middle">
              L
            </text>
            <text x={LEADER_X} y={layout.leaderCy + LEADER_R + 12} className="topo-node-host" textAnchor="middle">
              {leader.name}
            </text>
          </g>
        )}

        {sorted.map((member, i) => {
          const slot = layout.slots[i];
          const nodeStyle = nodeStyleFor(member, i);
          return (
            <g key={member.name} className="topo-node topo-node-replica">
              <circle
                cx={slot.cx}
                cy={slot.cy}
                r={slot.r}
                fill={nodeStyle.fill}
                stroke={nodeStyle.stroke}
                strokeWidth={2}
              />
              <text x={slot.cx} y={slot.cy + 4} className="topo-node-id" textAnchor="middle">
                R{i + 1}
              </text>
              <text x={slot.cx} y={slot.cy + slot.r + 11} className="topo-node-host" textAnchor="middle">
                {member.name}
              </text>
              <text x={slot.cx + slot.r + 8} y={slot.cy + 3} className="topo-node-status">
                {replicaStatus(member, i)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
