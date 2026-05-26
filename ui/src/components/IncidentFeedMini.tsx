import { useNavigate } from "react-router-dom";
import type { DashboardIssue, LogEntry } from "../api";

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

type Props = {
  clusterId: string;
  criticalCount: number;
  warningCount: number;
  issues: DashboardIssue[];
  logLines: LogEntry[];
};

export function IncidentFeedMini({ clusterId, criticalCount, warningCount, issues, logLines }: Props) {
  const navigate = useNavigate();
  const items = toFeedItems(issues, logLines, 8);

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
          <li className="incident-mini-empty muted">No recent critical/warning events.</li>
        )}
      </ul>
    </div>
  );
}
