import type { LiveMember } from "../api";

const VB = { w: 400, h: 200 };

/** Reference anchor points (leader left, replicas stacked right). */
const LEADER = { cx: 68, cy: 100, r: 24 };
const REPLICAS = [
  { cx: 292, cy: 36, r: 18, tag: "R1" },
  { cx: 292, cy: 100, r: 18, tag: "R2" },
  { cx: 292, cy: 164, r: 18, tag: "R3" },
] as const;

/** Leg geometry — matches mockup: R1 arc up (dashed green), R2 flat (solid blue), R3 arc down (dashed orange). */
const LEGS = [
  {
    id: "leg-r1",
    d: "M 92 90 C 138 42, 198 32, 274 38",
    label: "Replication Lag…",
    dash: "7 5",
    solid: false,
    stroke: "#22c55e",
    marker: "url(#topo-arr-green)",
  },
  {
    id: "leg-r2",
    d: "M 92 100 L 274 100",
    label: "Replication Leg…",
    dash: undefined,
    solid: true,
    stroke: "#38bdf8",
    marker: "url(#topo-arr-blue)",
  },
  {
    id: "leg-r3",
    d: "M 92 110 C 138 158, 198 172, 274 164",
    label: "Lagging…",
    dash: "7 5",
    solid: false,
    stroke: "#f59e0b",
    marker: "url(#topo-arr-orange)",
  },
] as const;

function lagMsLabel(bytes: number | null | undefined): string {
  if (bytes == null || bytes <= 0) return "0ms";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function replicaStatus(r: LiveMember, index: number): string {
  const lag = r.lag ?? 0;
  if (lag > 8 * 1024 * 1024) return `R${index + 1}, lagging`;
  const state = String(r.state || "").toLowerCase();
  if (state.includes("async")) return `R${index + 1}, async`;
  if (state.includes("sync")) return `R${index + 1}: ${lagMsLabel(lag)}`;
  return `R${index + 1}: ${lagMsLabel(lag)}`;
}

function replicaFill(i: number, lagged: boolean): { fill: string; stroke: string } {
  if (i === 0) return { fill: "url(#topo-fill-r1)", stroke: "#22c55e" };
  if (i === 1) return { fill: "url(#topo-fill-r2)", stroke: "#38bdf8" };
  if (lagged || i === 2) return { fill: "url(#topo-fill-r3)", stroke: "#f59e0b" };
  return { fill: "url(#topo-fill-r2)", stroke: "#38bdf8" };
}

type Props = {
  leader: LiveMember | undefined;
  replicas: LiveMember[];
};

export function TopologyMap({ leader, replicas }: Props) {
  const shown = replicas.slice(0, 3);

  return (
    <div className="topo-ref topo-ref-round topo-ref-svg-only">
      <svg
        className="topo-ref-svg"
        viewBox={`0 0 ${VB.w} ${VB.h}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Cluster topology"
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

          <marker id="topo-arr-green" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
            <path d="M0,0 L7,3.5 L0,7 z" fill="#22c55e" />
          </marker>
          <marker id="topo-arr-blue" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
            <path d="M0,0 L7,3.5 L0,7 z" fill="#38bdf8" />
          </marker>
          <marker id="topo-arr-orange" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
            <path d="M0,0 L7,3.5 L0,7 z" fill="#f59e0b" />
          </marker>

          {LEGS.map((leg) => (
            <path key={leg.id} id={leg.id} d={leg.d} fill="none" />
          ))}
        </defs>

        {/* Replication legs (under nodes) */}
        {LEGS.map((leg, i) => {
          const r = shown[i];
          const lagged = (r?.lag ?? 0) > 4 * 1024 * 1024;
          const stroke = i === 2 && lagged ? "#f59e0b" : leg.stroke;
          return (
            <g key={leg.id} className="topo-leg">
              <use
                href={`#${leg.id}`}
                stroke={stroke}
                strokeWidth={2}
                strokeDasharray={leg.dash}
                fill="none"
                markerEnd={leg.marker}
                className={leg.solid ? "topo-leg-solid" : "topo-leg-dashed"}
              />
              <text className="topo-leg-textpath">
                <textPath href={`#${leg.id}`} startOffset="42%" textAnchor="middle">
                  {i === 0 && lagged ? "Replication lag…" : leg.label}
                </textPath>
              </text>
            </g>
          );
        })}

        {/* Leader */}
        <g className="topo-node topo-node-leader">
          <circle
            cx={LEADER.cx}
            cy={LEADER.cy}
            r={LEADER.r}
            fill="url(#topo-fill-leader)"
            stroke="#22c55e"
            strokeWidth={2}
          />
          <text x={LEADER.cx} y={LEADER.cy - 6} className="topo-node-glyph" textAnchor="middle">
            ⚡
          </text>
          <text x={LEADER.cx} y={LEADER.cy + 5} className="topo-node-id" textAnchor="middle">
            L
          </text>
          <text x={LEADER.cx} y={LEADER.cy + LEADER.r + 12} className="topo-node-host" textAnchor="middle">
            {leader?.name ?? "—"}
          </text>
        </g>

        {/* Replicas */}
        {REPLICAS.map((slot, i) => {
          const r = shown[i];
          const lagged = (r?.lag ?? 0) > 4 * 1024 * 1024;
          const { fill, stroke } = replicaFill(i, lagged);
          const status = r ? replicaStatus(r, i) : "—";
          return (
            <g key={slot.tag} className="topo-node topo-node-replica">
              <circle cx={slot.cx} cy={slot.cy} r={slot.r} fill={fill} stroke={stroke} strokeWidth={2} />
              <text x={slot.cx} y={slot.cy + 4} className="topo-node-id" textAnchor="middle">
                {slot.tag}
              </text>
              <text x={slot.cx} y={slot.cy + slot.r + 11} className="topo-node-host" textAnchor="middle">
                {r?.name ?? "—"}
              </text>
              <text x={slot.cx + slot.r + 8} y={slot.cy + 3} className="topo-node-status">
                {status}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
