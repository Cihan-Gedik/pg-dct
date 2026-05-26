import type { ReactNode } from "react";
import type { PanelId } from "../lib/dashboardGrid";

const TITLES: Record<PanelId, string> = {
  search: "Search Clusters",
  timeline: "Leadership timeline",
  health: "Cluster Health",
  dcs: "DCS / etcd Health",
  topology: "Topology Map",
  wal: "WAL & Checkpoint Engine",
  incidents: "Incident Count & Feed",
  notes: "Notes & Diagnostics",
};

type Props = {
  panelId: PanelId;
  collapsed: boolean;
  onToggleCollapse: (id: PanelId) => void;
  children: ReactNode;
};

/** Fixed-position dashboard panel (placement via CSS grid areas). */
export function DashboardGridPanel({ panelId, collapsed, onToggleCollapse, children }: Props) {
  return (
    <section
      className={`card ref-card dashboard-window grid-panel panel-${panelId} ${collapsed ? "collapsed" : ""}`}
      data-panel={panelId}
    >
      <div className="window-head">
        <h2>{TITLES[panelId]}</h2>
        <div className="window-actions">
          <button
            type="button"
            className="icon-btn"
            title={collapsed ? "Expand" : "Collapse"}
            onClick={() => onToggleCollapse(panelId)}
          >
            {collapsed ? "⤢" : "⤡"}
          </button>
        </div>
      </div>
      {!collapsed && <div className="window-body grid-panel-body">{children}</div>}
    </section>
  );
}
