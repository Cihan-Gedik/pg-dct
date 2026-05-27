import type { PostgresSettings } from "../api";

type Props = {
  clusterId: string;
  clusterName?: string;
  data: PostgresSettings | null;
  loading: boolean;
  error: string | null;
};

export function PostgresSettingsStrip({ clusterId, clusterName, data, loading, error }: Props) {
  return (
    <section className="card ref-card pg-settings-strip" aria-label="PostgreSQL settings">
      <div className="pg-settings-head">
        <div>
          <h2 className="section-title">PostgreSQL Settings</h2>
          <p className="pill pg-settings-sub">
            {clusterName || clusterId}
            {data?.leader && (
              <>
                {" "}
                · leader <strong>{data.leader}</strong>
                {data.host && <span className="pg-settings-host"> @ {data.host}</span>}
              </>
            )}
          </p>
        </div>
        {loading && <span className="pill">Loading…</span>}
      </div>

      {error && <div className="err">{error}</div>}

      {!error && !loading && data && !data.ok && data.error && (
        <p className="muted">{data.error}</p>
      )}

      {!error && data?.ok && data.settings.length > 0 && (
        <div className="pg-settings-grid">
          {data.settings.map((s) => (
            <div key={s.name} className="pg-settings-stat">
              <span className="pg-settings-label">{s.label}</span>
              <strong className="pg-settings-value">{s.value}</strong>
            </div>
          ))}
        </div>
      )}

      {!error && !loading && data?.ok && !data.settings.length && (
        <p className="muted">No settings returned from the leader.</p>
      )}
    </section>
  );
}
