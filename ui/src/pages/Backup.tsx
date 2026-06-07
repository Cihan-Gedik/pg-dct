import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  api,
  type BackupInfo,
  type BackupJob,
  type BackupJobKind,
  type BackupSchedule,
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

const formatDateTime = (value?: string | null) => value ? new Date(value).toLocaleString() : "—";

export default function Backup() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [clusters, setClusters] = useState<ClusterListItem[]>([]);
  const [clusterId, setClusterId] = useState(searchParams.get("cluster") || "lc-pg-main");
  const [tab, setTab] = useState<Tab>((searchParams.get("tab") as Tab) || "overview");
  const [info, setInfo] = useState<BackupInfo | null>(null);
  const [jobs, setJobs] = useState<BackupJob[]>([]);
  const [schedules, setSchedules] = useState<BackupSchedule[]>([]);
  const [loadingInfo, setLoadingInfo] = useState(false);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [loadingSchedules, setLoadingSchedules] = useState(false);
  const [infoErr, setInfoErr] = useState<string | null>(null);
  const [jobErr, setJobErr] = useState<string | null>(null);
  const [scheduleErr, setScheduleErr] = useState<string | null>(null);
  const [submitKind, setSubmitKind] = useState<BackupJobKind>("backup_full");
  const [submitStanza, setSubmitStanza] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [settingUp, setSettingUp] = useState(false);
  const [runFirstBackupOnSetup, setRunFirstBackupOnSetup] = useState(true);
  const [expandedJobId, setExpandedJobId] = useState<number | null>(null);
  const [scheduleName, setScheduleName] = useState("Nightly full backup");
  const [scheduleKind, setScheduleKind] = useState<BackupJobKind>("backup_full");
  const [scheduleCron, setScheduleCron] = useState("0 2 * * *");
  const [scheduleStanza, setScheduleStanza] = useState("");
  const [scheduleSubmitting, setScheduleSubmitting] = useState(false);
  const [scheduleActionId, setScheduleActionId] = useState<number | null>(null);

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

  const refreshSchedules = useCallback(async () => {
    if (!clusterId) return;
    setLoadingSchedules(true);
    setScheduleErr(null);
    try {
      setSchedules(await api.backupSchedules(clusterId));
    } catch (e) {
      setScheduleErr(String(e));
    } finally {
      setLoadingSchedules(false);
    }
  }, [clusterId]);

  const refreshAll = useCallback(async () => {
    await Promise.all([refreshInfo(), refreshJobs(), refreshSchedules()]);
  }, [refreshInfo, refreshJobs, refreshSchedules]);

  useEffect(() => {
    refreshInfo();
    refreshJobs();
    refreshSchedules();
  }, [clusterId, refreshInfo, refreshJobs, refreshSchedules]);

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

  const showSetup = info && (info.needs_setup || !info.ok);

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

  const runSetup = async () => {
    setSettingUp(true);
    setJobErr(null);
    try {
      await api.backupSetup(clusterId, { run_first_backup: runFirstBackupOnSetup });
      await refreshJobs();
      await refreshInfo();
      setActiveTab("jobs");
    } catch (e) {
      setJobErr(String(e));
    } finally {
      setSettingUp(false);
    }
  };

  const submitSchedule = async () => {
    setScheduleSubmitting(true);
    setScheduleErr(null);
    try {
      await api.createBackupSchedule(clusterId, {
        name: scheduleName.trim(),
        kind: scheduleKind,
        cron: scheduleCron.trim(),
        stanza: scheduleStanza.trim(),
        enabled: true,
      });
      setScheduleName(scheduleKind === "backup_full" ? "Nightly full backup" : "Scheduled backup");
      setScheduleStanza("");
      await refreshSchedules();
    } catch (e) {
      setScheduleErr(String(e));
    } finally {
      setScheduleSubmitting(false);
    }
  };

  const toggleSchedule = async (schedule: BackupSchedule) => {
    setScheduleActionId(schedule.id);
    setScheduleErr(null);
    try {
      await api.updateBackupSchedule(clusterId, schedule.id, { enabled: !schedule.enabled });
      await refreshSchedules();
    } catch (e) {
      setScheduleErr(String(e));
    } finally {
      setScheduleActionId(null);
    }
  };

  const deleteSchedule = async (schedule: BackupSchedule) => {
    setScheduleActionId(schedule.id);
    setScheduleErr(null);
    try {
      await api.deleteBackupSchedule(clusterId, schedule.id);
      await refreshSchedules();
    } catch (e) {
      setScheduleErr(String(e));
    } finally {
      setScheduleActionId(null);
    }
  };

  const runScheduleNow = async (schedule: BackupSchedule) => {
    setScheduleActionId(schedule.id);
    setScheduleErr(null);
    try {
      await api.runBackupSchedule(clusterId, schedule.id);
      await Promise.all([refreshSchedules(), refreshJobs(), refreshInfo()]);
    } catch (e) {
      setScheduleErr(String(e));
    } finally {
      setScheduleActionId(null);
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
            className="btn"
            disabled={settingUp || loadingInfo}
            onClick={runSetup}
            title="Install config, stanza-create, check on all nodes"
          >
            {settingUp ? "Setting up…" : "Setup pgBackRest"}
          </button>
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
            {id === "schedules" && <span className="tab-meta"> · {schedules.length}</span>}
          </button>
        ))}
      </nav>

      {tab === "overview" && (
        <section className="tab-panel">
          {infoErr && <div className="err">{infoErr}</div>}
          {loadingInfo && !info && <p className="pill">Loading pgBackRest info…</p>}

          {info && (
            <>
              {showSetup && (
                <div className="alert-banner">
                  <p>{info.error ?? "pgBackRest needs one-time setup on this cluster"}</p>
                  {info.stdout_tail && (
                    <pre className="backup-stdout-preview">{info.stdout_tail}</pre>
                  )}
                  <p className="hint">
                    Click <strong>Setup pgBackRest</strong> once, or run any backup job — setup runs
                    automatically if needed.
                  </p>
                  <div className="row" style={{ marginTop: 12 }}>
                    <label className="filter-checkbox">
                      <input
                        type="checkbox"
                        checked={runFirstBackupOnSetup}
                        onChange={(e) => setRunFirstBackupOnSetup(e.target.checked)}
                      />
                      Run first full backup after setup
                    </label>
                    <button
                      type="button"
                      className="btn primary"
                      disabled={settingUp || loadingInfo}
                      onClick={runSetup}
                    >
                      {settingUp ? "Setting up…" : "Setup pgBackRest"}
                    </button>
                  </div>
                </div>
              )}

              {info.ok && !info.needs_setup && backupCount === 0 && (
                <div className="card" style={{ marginBottom: 12 }}>
                  <p className="card-desc">
                    Stanza exists but no backups yet. Run <strong>backup_full</strong> from the Jobs tab,
                    or use Setup again with first backup enabled.
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
          <p className="hint card-desc">
            Old <strong>failed</strong> jobs with <code>pg1-path</code> are from before Setup — ignore them.
            Select cluster → header <strong>Setup pgBackRest</strong> once per cluster, then run a new{" "}
            <strong>backup_full</strong>.
          </p>
          <div className="card backup-job-form">
            <h2 className="card-title">Safe ops — new job</h2>
            <p className="card-desc">
              Allowed: {JOB_KINDS.filter((k) => k !== "setup").join(", ")}. Use Overview → Setup for
              first-time install. Restore and stanza-delete are not exposed.
            </p>
            <div className="row filters">
              <div className="field">
                <label>Kind</label>
                <select value={submitKind} onChange={(e) => setSubmitKind(e.target.value as BackupJobKind)}>
                  {JOB_KINDS.filter((k) => k !== "setup").map((k) => (
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
                        <td className="mono-sm">{formatDateTime(j.created_at)}</td>
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
          <div className="card backup-schedule-form">
            <h2 className="card-title">Backup schedules</h2>
            <p className="card-desc">
              Cron schedules run in UTC and execute the same allowlisted pgBackRest backup jobs used
              by the Jobs tab.
            </p>
            <div className="row filters">
              <div className="field wide-field">
                <label>Name</label>
                <input
                  value={scheduleName}
                  onChange={(e) => setScheduleName(e.target.value)}
                  placeholder="Nightly full backup"
                />
              </div>
              <div className="field">
                <label>Kind</label>
                <select
                  value={scheduleKind}
                  onChange={(e) => setScheduleKind(e.target.value as BackupJobKind)}
                >
                  {SCHEDULE_KINDS.map((k) => (
                    <option key={k} value={k}>
                      {k}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>Cron (UTC)</label>
                <input
                  className="mono-sm"
                  value={scheduleCron}
                  onChange={(e) => setScheduleCron(e.target.value)}
                  placeholder="0 2 * * *"
                />
              </div>
              <div className="field">
                <label>Stanza (optional)</label>
                <input
                  value={scheduleStanza}
                  onChange={(e) => setScheduleStanza(e.target.value)}
                  placeholder={info?.stanza || "default from yaml"}
                />
              </div>
              <button
                type="button"
                className="btn primary"
                disabled={scheduleSubmitting || !scheduleName.trim() || !scheduleCron.trim()}
                onClick={submitSchedule}
              >
                {scheduleSubmitting ? "Saving…" : "Create schedule"}
              </button>
            </div>
            <ul className="backup-schedule-presets muted">
              <li>Every day at 02:00 UTC — <code>0 2 * * *</code></li>
              <li>Every 6 hours — <code>0 */6 * * *</code></li>
              <li>Sundays at 03:00 UTC — <code>0 3 * * 0</code></li>
            </ul>
            {scheduleErr && <div className="err">{scheduleErr}</div>}
          </div>

          <div className="card">
            <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
              <h2 className="card-title" style={{ margin: 0 }}>
                Schedule registry
              </h2>
              <button type="button" className="btn" disabled={loadingSchedules} onClick={refreshSchedules}>
                {loadingSchedules ? "Refreshing…" : "Refresh"}
              </button>
            </div>
            {schedules.length === 0 && (
              <p className="muted">No schedules for this cluster yet.</p>
            )}
            {schedules.length > 0 && (
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Kind</th>
                    <th>Cron</th>
                    <th>Next run</th>
                    <th>Last run</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {schedules.map((s) => (
                    <tr key={s.id}>
                      <td>
                        <strong>{s.name}</strong>
                        {s.stanza && (
                          <div className="mono-sm muted">stanza: {s.stanza}</div>
                        )}
                      </td>
                      <td><span className="badge info">{s.kind}</span></td>
                      <td className="mono-sm">{s.cron}</td>
                      <td className="mono-sm">{formatDateTime(s.next_run_at)}</td>
                      <td className="mono-sm">{formatDateTime(s.last_run_at)}</td>
                      <td>
                        <span className={`badge ${s.enabled ? "leader" : "warning"}`}>
                          {s.enabled ? "enabled" : "paused"}
                        </span>
                        {s.last_status && (
                          <span className={`badge ${s.last_status === "succeeded" ? "leader" : "critical"} schedule-last-status`}>
                            {s.last_status}
                          </span>
                        )}
                      </td>
                      <td>
                        <div className="row schedule-actions">
                          <button
                            type="button"
                            className="btn"
                            disabled={scheduleActionId === s.id}
                            onClick={() => toggleSchedule(s)}
                          >
                            {s.enabled ? "Pause" : "Enable"}
                          </button>
                          <button
                            type="button"
                            className="btn"
                            disabled={scheduleActionId === s.id}
                            onClick={() => runScheduleNow(s)}
                          >
                            Run now
                          </button>
                          <button
                            type="button"
                            className="btn"
                            disabled={scheduleActionId === s.id}
                            onClick={() => deleteSchedule(s)}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
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
