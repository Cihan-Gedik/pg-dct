export type PgbrBackup = {
  type?: string;
  label?: string;
  timestamp?: { start?: number; stop?: number };
  info?: { size?: number; repository?: { delta?: number; size?: number } };
};

export type PgbrStanza = {
  name: string;
  backup?: PgbrBackup[];
};

function formatBytes(n: number | undefined): string {
  if (n == null || n <= 0) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

type Row = {
  label: string;
  type: string;
  stanza: string;
  leftPct: number;
  widthPct: number;
  startIso: string;
  stopIso: string;
  size?: number;
};

function buildRows(stanzas: PgbrStanza[]): { rows: Row[]; t0Iso: string; t1Iso: string } {
  const flat: Array<Row & { start: number; stop: number }> = [];
  let minStart = Number.POSITIVE_INFINITY;
  let maxStop = 0;

  for (const stanza of stanzas) {
    for (const backup of stanza.backup ?? []) {
      const start = backup.timestamp?.start ?? 0;
      const stop = backup.timestamp?.stop ?? start;
      if (!start) continue;
      minStart = Math.min(minStart, start);
      maxStop = Math.max(maxStop, stop);
      flat.push({
        label: backup.label ?? "?",
        type: backup.type ?? "full",
        stanza: stanza.name,
        leftPct: 0,
        widthPct: 0,
        startIso: new Date(start * 1000).toISOString().slice(0, 19).replace("T", " "),
        stopIso: new Date(stop * 1000).toISOString().slice(0, 19).replace("T", " "),
        size: backup.info?.size,
        start,
        stop: Math.max(stop, start + 60),
      });
    }
  }

  if (flat.length === 0) return { rows: [], t0Iso: "", t1Iso: "" };
  const now = Math.floor(Date.now() / 1000);
  const t0 = minStart;
  const t1 = Math.max(maxStop, now);
  const span = t1 - t0 || 1;

  const rows = flat
    .sort((a, b) => a.start - b.start)
    .map((r) => ({
      label: r.label,
      type: r.type,
      stanza: r.stanza,
      startIso: r.startIso,
      stopIso: r.stopIso,
      size: r.size,
      leftPct: ((r.start - t0) / span) * 100,
      widthPct: Math.max(((r.stop - r.start) / span) * 100, 0.8),
    }));

  return {
    rows,
    t0Iso: new Date(t0 * 1000).toISOString().slice(0, 19).replace("T", " "),
    t1Iso: new Date(t1 * 1000).toISOString().slice(0, 19).replace("T", " "),
  };
}

export function BackupRetentionTimeline({ stanzas }: { stanzas: PgbrStanza[] }) {
  const { rows, t0Iso, t1Iso } = buildRows(stanzas);

  if (rows.length === 0) {
    return (
      <div className="backup-timeline-empty">
        No pgBackRest backups in the last info snapshot. Run a backup or check stanza config.
      </div>
    );
  }

  return (
    <div className="backup-timeline">
      <div className="backup-timeline-legend">
        <span className="legend-full">full</span>
        <span className="legend-diff">diff</span>
        <span className="legend-incr">incr</span>
      </div>
      <div className="backup-timeline-rows">
        {rows.map((row) => (
          <div key={`${row.stanza}-${row.label}`} className="backup-timeline-row">
            <span className="backup-row-label" title={row.stanza}>
              {row.label}
            </span>
            <div className="backup-row-track">
              <div
                className={`backup-bar type-${row.type}`}
                style={{ marginLeft: `${row.leftPct}%`, width: `${row.widthPct}%` }}
                title={`${row.stanza}/${row.label} (${row.type})\n${row.startIso} → ${row.stopIso}\n${formatBytes(row.size)}`}
              >
                <span className="backup-bar-label">{row.type}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="backup-timeline-axis">
        <span>oldest: {t0Iso} UTC</span>
        <span>now: {t1Iso} UTC</span>
      </div>
    </div>
  );
}

export function sumRepoSizeBytes(stanzas: PgbrStanza[]): number {
  return stanzas.reduce(
    (sum, s) =>
      sum +
      (s.backup ?? []).reduce(
        (acc, b) =>
          acc + (b.info?.repository?.delta ?? b.info?.repository?.size ?? b.info?.size ?? 0),
        0,
      ),
    0,
  );
}

export function formatBackupBytes(n: number | null | undefined): string {
  if (n == null) return "—";
  return formatBytes(n);
}
