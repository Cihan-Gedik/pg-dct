import { useNavigate } from "react-router-dom";
import type { DashboardIssue, LogEntry } from "../api";

const RANGE_OPTIONS = [
  { label: "6h", hours: 6 },
  { label: "24h", hours: 24 },
  { label: "7d", hours: 168 },
  { label: "30d", hours: 720 },
] as const;

type FeedItem = {
  key: string;
  level: "critical" | "warning" | "info";
  title: string;
  message: string;
};

function toFeedItems(issues: DashboardIssue[], logs: LogEntry[], limit: number): FeedItem[] {
  const fromIssues: FeedItem[] = issues.map((i) => ({
    key: i.id,
    level: i.level === "critical" ? "critical" : i.level === "warning" ? "warning" : "info",
    title: i.title,
    message: i.message,
  }));
  if (fromIssues.length) return fromIssues.slice(0, limit);

  return logs.slice(0, limit).map((l, idx) => ({
    key: `${l.ts}-${idx}`,
    level: l.level === "critical" ? "critical" : l.level === "warning" ? "warning" : "info",
    title: `${l.level.toUpperCase()} · ${l.source}`,
    message: l.message.length > 72 ? `${l.message.slice(0, 72)}…` : l.message,
  }));
}

function countLevels(issues: DashboardIssue[], logs: LogEntry[]) {
  if (issues.length) {
    return {
      critical: issues.filter((i) => i.level === "critical").length,
      warning: issues.filter((i) => i.level === "warning").length,
    };
  }
  return {
    critical: logs.filter((l) => l.level === "critical").length,
    warning: logs.filter((l) => l.level === "warning").length,
  };
}

function rangeLabel(hours: number): string {
  const opt = RANGE_OPTIONS.find((o) => o.hours === hours);
  return opt ? `Last ${opt.label}` : `Last ${hours}h`;
}

type Props = {
  clusterId: string;
  hours: number;
  onHoursChange: (hours: number) => void;
  issues: DashboardIssue[];
  logLines: LogEntry[];
};

export function IncidentFeedMini({ clusterId, hours, onHoursChange, issues, logLines }: Props) {
  const navigate = useNavigate();
  const items = toFeedItems(issues, logLines, 8);
  const { critical: criticalCount, warning: warningCount } = countLevels(issues, logLines);

  const openLogs = (focus?: "critical" | "warning") => {
    const severity =
      focus === "critical"
        ? "critical"
        : focus === "warning"
          ? "warning"
          : "critical,warning,info";
    const q = new URLSearchParams({ cluster: clusterId || "lc-pg-main", severity });
    navigate(`/logs?${q.toString()}`);
  };

  return (
    <div className="incident-mini incident-mini-split">
      <div className="incident-mini-range-row">
        <span className="pill incident-mini-window">{rangeLabel(hours)}</span>
        <div className="timeline-range incident-mini-range">
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

      <div className="incident-mini-top">
        <div className="incident-mini-kpi">
          <button type="button" className="incident-mini-box critical" onClick={() => openLogs("critical")}>
            <span>CRITICAL</span>
            <strong>{criticalCount}</strong>
          </button>
          <button type="button" className="incident-mini-box warning" onClick={() => openLogs("warning")}>
            <span>WARNING</span>
            <strong>{warningCount}</strong>
          </button>
        </div>
      </div>

      <div className="incident-mini-feed-head">
        <span>Incident Feed</span>
        <button type="button" className="incident-mini-link" onClick={() => openLogs()}>
          All logs →
        </button>
      </div>

      <ul className="incident-mini-list" aria-label="Recent incidents">
        {items.map((item) => (
          <li key={item.key}>
            <button
              type="button"
              className={`incident-mini-row ${item.level}`}
              onClick={() => openLogs(item.level === "info" ? undefined : item.level)}
            >
              <span className={`incident-dot ${item.level}`} />
              <span className="incident-mini-text">
                <strong>{item.title}</strong>
                <small>{item.message}</small>
              </span>
            </button>
          </li>
        ))}
        {!items.length && (
          <li className="incident-mini-empty muted">No critical/warning events in {rangeLabel(hours).toLowerCase()}.</li>
        )}
      </ul>
    </div>
  );
}
