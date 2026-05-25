import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { DashboardIssue } from "../api";

type Props = {
  issues: DashboardIssue[];
  criticalCount: number;
  warningCount: number;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  lastRefresh: Date | null;
};

type CategoryGroup = {
  key: string;
  cluster_id: string;
  cluster_name: string;
  category: string;
  critical: number;
  warning: number;
  total: number;
  items: DashboardIssue[];
};

function fmtTime(ts: string | null): string {
  if (!ts) return "—";
  const d = new Date(ts);
  return Number.isNaN(d.getTime())
    ? ts
    : d.toLocaleString(undefined, { hour: "2-digit", minute: "2-digit", month: "short", day: "numeric" });
}

function buildCategorySummary(issues: DashboardIssue[]): CategoryGroup[] {
  const map = new Map<string, CategoryGroup>();
  for (const issue of issues) {
    const key = `${issue.cluster_id}:${issue.category}`;
    const n = issue.occurrence_count || 1;
    let row = map.get(key);
    if (!row) {
      row = {
        key,
        cluster_id: issue.cluster_id,
        cluster_name: issue.cluster_name,
        category: issue.category,
        critical: 0,
        warning: 0,
        total: 0,
        items: [],
      };
      map.set(key, row);
    }
    row.total += n;
    if (issue.level === "critical") row.critical += n;
    else if (issue.level === "warning") row.warning += n;
    row.items.push(issue);
  }
  return [...map.values()].sort((a, b) => b.total - a.total);
}

export function CriticalIssuesPanel({
  issues,
  criticalCount,
  warningCount,
  loading,
  error,
  onRefresh,
  lastRefresh,
}: Props) {
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const summary = useMemo(() => buildCategorySummary(issues), [issues]);
  const expanded = summary.find((g) => g.key === expandedKey) ?? null;

  const toggle = (key: string) => setExpandedKey((prev) => (prev === key ? null : key));

  return (
    <section className="issues-compact card">
      <div className="issues-compact-head">
        <div>
          <h2 className="section-title">Issues summary</h2>
          <p className="pill">
            {summary.length} categories · {criticalCount} critical · {warningCount} warning events
          </p>
        </div>
        <div className="row">
          <button type="button" className="btn btn-sm" disabled={loading} onClick={onRefresh}>
            {loading ? "…" : "Refresh"}
          </button>
          {lastRefresh && <span className="pill">{lastRefresh.toLocaleTimeString()}</span>}
        </div>
      </div>

      {error && <div className="err err-inline">{error}</div>}

      {!loading && summary.length === 0 && (
        <div className="issues-empty issues-empty-sm">No open issues — clusters look healthy.</div>
      )}

      {summary.length > 0 && (
        <div className="issues-compact-scroll">
          <table className="issues-compact-table">
            <thead>
              <tr>
                <th>Cluster</th>
                <th>Category</th>
                <th>Crit</th>
                <th>Warn</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {summary.map((row) => (
                <tr
                  key={row.key}
                  className={`issues-compact-row ${expandedKey === row.key ? "open" : ""} ${row.critical > 0 ? "has-critical" : ""}`}
                >
                  <td>
                    <button type="button" className="issues-compact-btn" onClick={() => toggle(row.key)}>
                      {row.cluster_name}
                    </button>
                  </td>
                  <td>
                    <button type="button" className="issues-compact-btn" onClick={() => toggle(row.key)}>
                      <span className={`issues-cat-badge cat-${row.category}`}>{row.category}</span>
                    </button>
                  </td>
                  <td className="num critical">{row.critical || "—"}</td>
                  <td className="num warning">{row.warning || "—"}</td>
                  <td className="num total">
                    <button type="button" className="issues-total-btn" onClick={() => toggle(row.key)}>
                      {row.total}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {expanded && (
        <div className="issues-compact-detail">
          <div className="issues-detail-head">
            <strong>
              {expanded.cluster_name} · {expanded.category}
            </strong>
            <span className="pill">{expanded.total} events</span>
            <button type="button" className="btn btn-sm" onClick={() => setExpandedKey(null)}>
              Close
            </button>
          </div>
          <ul className="issues-detail-samples">
            {expanded.items.slice(0, 3).map((issue) => (
              <li key={issue.id}>
                <span className={`badge ${issue.level}`}>{issue.level}</span>
                {issue.occurrence_count > 1 && <span className="issue-count">×{issue.occurrence_count}</span>}
                <span className="pill">{issue.member_name ?? "cluster"}</span>
                <span className="issue-sample-msg">{(issue.detail ?? issue.message).slice(0, 140)}</span>
                <span className="pill">{fmtTime(issue.last_seen ?? issue.ts)}</span>
              </li>
            ))}
          </ul>
          {expanded.items.length > 3 && (
            <p className="pill">+ {expanded.items.length - 3} more patterns in this category</p>
          )}
          <div className="issue-actions">
            <Link className="btn primary btn-sm" to={`/live?cluster=${expanded.cluster_id}&tab=logs`}>
              View logs
            </Link>
            <Link className="btn btn-sm" to={`/live?cluster=${expanded.cluster_id}&tab=overview`}>
              Overview
            </Link>
          </div>
        </div>
      )}
    </section>
  );
}
