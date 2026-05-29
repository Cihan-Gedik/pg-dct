import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  api,
  type BackupInfo,
  type BackupJob,
  type BackupJobKind,
  type ClusterListItem,
} from "../api";
import {
  BackupRetentionTimeline,
  formatBackupBytes,
  sumRepoSizeBytes,
  type PgbrStanza,
} from "../components/BackupRetentionTimeline";
import { ClusterSelector } from "../components/ClusterSelector";

const JOB_KINDS: BackupJobKind[] = [
  "backup_full",
  "backup_diff",
  "backup_incr",
  "check",
  "stanza_create",
];

const SCHEDULE_KINDS: BackupJobKind[] = ["backup_full", "backup_diff", "backup_incr"];

type Tab = "overview" | "jobs" | "schedules" | "wal" | "storage";

export default function Backup() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [clusters, setClusters] = useState<ClusterListItem[]>([]);
  const [clusterId, setClusterId] = useState(searchParams.get("cluster") || "lc-pg-main");
  const [tab, setTab] = useState<Tab>((searchParams.get("tab") as Tab) || "overview");
  const [info, setInfo] = useState<BackupInfo | null>(null);
  const [jobs, setJobs] = useState<BackupJob[]>([]);
  const [loadingInfo, setLoadingInfo] = useState(false);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [infoErr, setInfoErr] = useState<string | null>(null);
  const [jobErr, setJobErr] = useState<string | null>(null);
  const [submitKind, setSubmitKind] = useState<BackupJobKind>("backup_full");
  const [submitStanza, setSubmitStanza] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [expandedJobId, setExpandedJobId] = useState<number | null>(null);

  useEffect(() => {
    api.listClusters().then((list) => {
      setClusters(list);
      if (list.length && !list.find((c) => c.id === clusterId)) {
        setClusterId(list[0].id);
      }
    });
  }, []);

  const onClusterChange = useCallback(
    (id: string) => {
      setClusterId(id);
      const next = new URLSearchParams(searchParams);
      next.set("cluster", id);
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const setActiveTab = (t: Tab) => {
    setTab(t);
    const next = new URLSearchParams(searchParams);
    next.set("tab", t);
    setSearchParams(next, { replace: true });
  };

  const refreshInfo = useCallback(async () => {
    if (!clusterId) return;
    setLoadingInfo(true);
    setInfoErr(null);
    try {
      setInfo(await api.backupInfo(clusterId));
    } catch (e) {
      setInfoErr(String(e));
      setInfo(null);
    } finally {
      setLoadingInfo(false);
    }
  }, [clusterId]);

  const refreshJobs = useCallback(async () => {
    if (!clusterId) return;
    setLoadingJobs(true);
    setJobErr(null);
    try {
      setJobs(await api.backupJobs(clusterId));
    } catch (e) {
      setJobErr(String(e));
    } finally {
      setLoadingJobs(false);
    }
  }, [clusterId]);

  const refreshAll = useCallback(async () => {
    await Promise.all([refreshInfo(), refreshJobs()]);
  }, [refreshInfo, refreshJobs]);

  useEffect(() => {
    refreshInfo();
    refreshJobs();
  }, [clusterId, refreshInfo, refreshJobs]);

  const stanzas = useMemo(() => {
    const raw = info?.stanzas ?? [];
    const byName = new Map<string, PgbrStanza>();
    for (const s of raw) {
      const name = String((s as PgbrStanza).name ?? "");
      if (name && !byName.has(name)) byName.set(name, s as PgbrStanza);
    }
    return [...byName.values()];
  }, [info]);

  const backupCount = stanzas.reduce((n, s) => n + (s.backup?.length ?? 0), 0);
  const repoBytes = sumRepoSizeBytes(stanzas);

  const submitJob = async () => {
    setSubmitting(true);
    setJobErr(null);
    try {
      await api.createBackupJob(clusterId, {
        kind: submitKind,
        params: submitStanza.trim() ? { stanza: submitStanza.trim() } : {},
      });
      await refreshJobs();
      if (tab === "overview") await refreshInfo();
    } catch (e) {
      setJobErr(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="backup-page">
      <header className="page-header compact">
        <div>
          <h1>Backup</h1>
          <p className="sub">pgBackRest — overview, jobs, schedules, WAL, storage</p>
        </div>
        <div className="row header-actions">
          <button
            type="button"
            className="btn primary"
            disabled={loadingInfo || loadingJobs}
            onClick={refreshAll}
          >
            {loadingInfo || loadingJobs ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </header>

      <section className="cluster-bar card">
        <ClusterSelector clusters={clusters} selectedId={clusterId} onSelect={onClusterChange} />
      </section>

      <nav className="page-tabs" role="tablist">
        {(
          [
            ["overview", "Overview"],
            ["jobs", "Jobs"],
            ["schedules", "Schedules"],
            ["wal", "WAL"],
            ["storage", "Storage"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            className={tab === id ? "active" : ""}
            aria-selected={tab === id}
            onClick={() => setActiveTab(id)}
          >
            {label}
            {id === "overview" && info?.ok && (
              <span className="tab-meta"> · {backupCount} backups</span>
            )}
            {id === "jobs" && <span className="tab-meta"> · {jobs.length}</span>}
          </button>
        ))}
      </nav>

      {tab === "overview" && (
        <section className="tab-panel">
          {infoErr && <div className="err">{infoErr}</div>}
          {loadingInfo && !info && <p className="pill">Loading pgBackRest info…</p>}

          {info && (
            <>
              {!info.ok && (
                <div className="alert-banner">
                  <p>{info.error ?? "pgBackRest info unavailable"}</p>
                  {info.stdout_tail && (
                    <pre className="backup-stdout-preview">{info.stdout_tail}</pre>
                  )}
                  <p className="hint">
                    Enable pgBackRest on the leader container and add{" "}
                    <code>pgbackrest: {"{ enabled: true, stanza: ... }"}</code> to{" "}
                    <code>config/docker-clusters.yaml</code>.
                  </p>
                </div>
              )}

              <div className="stats stats-compact">
                <div className="stat">
                  <div className="v">{formatBackupBytes(repoBytes || null)}</div>
                  <div className="l">Repo size (approx)</div>
                </div>
                <div className="stat">
                  <div className="v">{backupCount}</div>
                  <div className="l">Backups in window</div>
                </div>
                <div className="stat">
                  <div className="v">{info.member ?? "—"}</div>
                  <div className="l">Leader / exec host</div>
                </div>
                <div className="stat">
                  <div className="v mono-sm">{info.container ?? "—"}</div>
                  <div className="l">Docker container</div>
                </div>
              </div>

              <div className="card">
                <h2 className="card-title">Safety window — retention</h2>
                <p className="card-desc">
                  Each bar is one backup. Span from oldest bar to now is the PITR window.
                </p>
                <BackupRetentionTimeline stanzas={stanzas} />
              </div>

              {info.stanza && (
                <p className="hint">
                  Configured stanza filter: <code>{info.stanza}</code>
                </p>
              )}
            </>
          )}
        </section>
      )}

      {tab === "jobs" && (
        <section className="tab-panel">
          <div className="card backup-job-form">
            <h2 className="card-title">Safe ops — new job</h2>
            <p className="card-desc">
              Allowed: {JOB_KINDS.join(", ")}. Restore and stanza-delete are not exposed.
            </p>
            <div className="row filters">
              <div className="field">
                <label>Kind</label>
                <select value={submitKind} onChange={(e) => setSubmitKind(e.target.value as BackupJobKind)}>
                  {JOB_KINDS.map((k) => (
                    <option key={k} value={k}>
                      {k}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Stanza (optional)</label>
                <input
                  value={submitStanza}
                  onChange={(e) => setSubmitStanza(e.target.value)}
                  placeholder={info?.stanza || "default from yaml"}
                />
              </div>
              <button type="button" className="btn primary" disabled={submitting} onClick={submitJob}>
                {submitting ? "Running…" : "Run job"}
              </button>
            </div>
            {jobErr && <div className="err">{jobErr}</div>}
          </div>

          <div className="card">
            <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
              <h2 className="card-title" style={{ margin: 0 }}>
                Job history
              </h2>
              <button type="button" className="btn" disabled={loadingJobs} onClick={refreshJobs}>
                Refresh
              </button>
            </div>
            {jobs.length === 0 && (
              <p className="muted">No jobs for this cluster yet.</p>
            )}
            {jobs.length > 0 && (
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Kind</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Exit</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((j) => (
                    <Fragment key={j.id}>
                      <tr
                        className="job-row-clickable"
                        onClick={() => setExpandedJobId((id) => (id === j.id ? null : j.id))}
                      >
                        <td>{j.id}</td>
                        <td>
                          <span className="badge info">{j.kind}</span>
                        </td>
                        <td>
                          <span className={`badge ${j.status === "succeeded" ? "leader" : j.status === "failed" ? "critical" : "warning"}`}>
                            {j.status}
                          </span>
                        </td>
                        <td className="mono-sm">{new Date(j.created_at).toLocaleString()}</td>
                        <td>{j.exit_code ?? "—"}</td>
                      </tr>
                      {expandedJobId === j.id && (
                        <tr>
                          <td colSpan={5}>
                            <pre className="backup-stdout-preview">{j.stdout_tail || j.error || "(no output)"}</pre>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      )}

      {tab === "schedules" && (
        <section className="tab-panel">
          <div className="card">
            <h2 className="card-title">Backup schedules</h2>
            <p className="card-desc">
              Cron schedules ({SCHEDULE_KINDS.join(", ")}) — coming in a later phase. Use Jobs for
              one-off backups today.
            </p>
            <ul className="backup-schedule-presets muted">
              <li>Every day · 02:00 UTC — <code>0 2 * * *</code></li>
              <li>Every 6 hours — <code>0 */6 * * *</code></li>
              <li>Sundays · 03:00 UTC — <code>0 3 * * 0</code></li>
            </ul>
          </div>
        </section>
      )}

      {tab === "wal" && (
        <section className="tab-panel">
          <div className="card">
            <h2 className="card-title">WAL archive health</h2>
            <p className="card-desc">
              Archive lag and gap detection need agent snapshots (PCT-style). For now use{" "}
              <strong>Cluster Health → Realtime Logs</strong> with pgBackRest / Patroni sources, or cluster
              alerts on the Dashboard.
            </p>
            {info?.ok && stanzas.length > 0 && (
              <pre className="backup-stdout-preview">
                {JSON.stringify(stanzas[0], null, 2)}
              </pre>
            )}
          </div>
        </section>
      )}

      {tab === "storage" && (
        <section className="tab-panel">
          <div className="card">
            <h2 className="card-title">Storage runway</h2>
            <p className="card-desc">
              Linear forecast over repo growth (PCT manager feature). PG-DCT shows current repo
              footprint from the latest <code>info</code> snapshot.
            </p>
            <div className="stats stats-compact">
              <div className="stat">
                <div className="v">{formatBackupBytes(repoBytes || null)}</div>
                <div className="l">Current repo size (approx)</div>
              </div>
              <div className="stat">
                <div className="v">{stanzas.length}</div>
                <div className="l">Stanzas</div>
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
