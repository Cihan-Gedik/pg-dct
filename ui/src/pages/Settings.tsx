import { useState } from "react";
import { api } from "../api";

export default function Settings() {
  const [msg, setMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function bootstrap() {
    setLoading(true);
    setMsg(null);
    try {
      const res = await api.bootstrapDocker();
      setMsg(JSON.stringify(res, null, 2));
    } catch (e) {
      setMsg(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <h1>Settings</h1>
      <p className="sub">Cluster registration and Docker lab bootstrap</p>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Docker lab</h3>
        <p className="pill">Requires ./scripts/expose-patroni-ports.sh running</p>
        <div className="row" style={{ marginTop: 12 }}>
          <button type="button" className="btn primary" onClick={bootstrap} disabled={loading}>
            Bootstrap Docker clusters
          </button>
        </div>
        {msg && (
          <pre style={{ marginTop: 16, fontSize: 11, overflow: "auto" }}>{msg}</pre>
        )}
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Config</h3>
        <p className="pill">config/docker-clusters.yaml — cluster seeds and docker_hosts map</p>
      </div>
    </>
  );
}
