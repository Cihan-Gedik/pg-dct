import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  api,
  type BundleImportResult,
  type BundleListItem,
  type ClusterListItem,
  type CustomerListItem,
} from "../api";

function formatRange(start?: string | null, end?: string | null): string {
  if (!start || !end) return "";
  return `${new Date(start).toLocaleString()} → ${new Date(end).toLocaleString()}`;
}

export default function Bundles() {
  const navigate = useNavigate();
  const [clusters, setClusters] = useState<ClusterListItem[]>([]);
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState("");
  const [clusterId, setClusterId] = useState("");
  const [bundles, setBundles] = useState<BundleListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [collecting, setCollecting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<BundleImportResult | null>(null);
  const [customerName, setCustomerName] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const loadCustomers = useCallback(async () => {
    const list = await api.listCustomers();
    setCustomers(list);
    return list;
  }, []);

  useEffect(() => {
    api.listClusters().then((list) => {
      setClusters(list);
      if (list.length) setClusterId((prev) => (prev && list.some((c) => c.id === prev) ? prev : list[0].id));
    });
    loadCustomers();
  }, [loadCustomers]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const list = await api.listBundles({
        customerName: selectedCustomer || undefined,
        clusterId: selectedCustomer ? undefined : clusterId || undefined,
      });
      setBundles(list);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }, [clusterId, selectedCustomer]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const activateCustomer = (c: CustomerListItem) => {
    setSelectedCustomer(c.name);
    if (c.latest_cluster_id && c.latest_bundle_id) {
      navigate(
        `/bundle-logs?cluster=${encodeURIComponent(c.latest_cluster_id)}&bundle=${encodeURIComponent(c.latest_bundle_id)}`,
      );
    }
  };

  const onCollect = async () => {
    if (!clusterId) return;
    setCollecting(true);
    setErr(null);
    try {
      await api.collectBundle(clusterId);
      await refresh();
    } catch (e) {
      setErr(String(e));
    } finally {
      setCollecting(false);
    }
  };

  const onImport = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setErr("Müşteriden gelen bundle .tar.gz dosyasını seçin");
      return;
    }
    if (!customerName.trim()) {
      setErr("Müşteri adı zorunludur");
      return;
    }
    setImporting(true);
    setErr(null);
    setImportResult(null);
    try {
      const res = await api.importBundle(file, customerName.trim());
      setImportResult(res);
      setSelectedCustomer(res.customer_name);
      await loadCustomers();
      await refresh();
      if (fileRef.current) fileRef.current.value = "";
    } catch (e) {
      setErr(String(e));
    } finally {
      setImporting(false);
    }
  };

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Bundles</h1>
          <p className="sub">
            Müşteri bundle import · müşteri seçerek log analizi · lab ortamında doğrudan toplama
          </p>
        </div>
      </header>

      <section className="card">
        <h2>Müşteri seç</h2>
        <p className="sub">Import ettiğiniz müşteriler burada listelenir. Seçince en son bundle log analizine açılır.</p>
        <div className="cluster-bar" style={{ display: "flex", gap: "1rem", flexWrap: "wrap", alignItems: "flex-end" }}>
          <label className="field field-grow">
            Müşteri
            <select
              value={selectedCustomer}
              onChange={(e) => {
                const name = e.target.value;
                setSelectedCustomer(name);
                const c = customers.find((x) => x.name === name);
                if (c) activateCustomer(c);
              }}
            >
              <option value="">— Tümü —</option>
              {customers.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name} ({c.bundle_count} bundle)
                </option>
              ))}
            </select>
          </label>
          {selectedCustomer && (
            <button
              type="button"
              className="btn primary"
              onClick={() => {
                const c = customers.find((x) => x.name === selectedCustomer);
                if (c) activateCustomer(c);
              }}
            >
              Logları aç
            </button>
          )}
        </div>
      </section>

      <section className="card">
        <h2>Import customer bundle</h2>
        <p className="sub">
          Müşteri <code>./pgdct-bundle-collect.sh</code> çalıştırır (ortamı otomatik keşfeder) ve{" "}
          <code>bundle_*.tar.gz</code> gönderir. Cluster adı bundle içindeki Patroni scope&apos;undan okunur.
        </p>
        <div className="filters" style={{ alignItems: "flex-end" }}>
          <div className="field field-grow">
            <label>Müşteri adı</label>
            <input
              type="text"
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              placeholder="ör. Acme Bank"
              list="customer-suggestions"
            />
            <datalist id="customer-suggestions">
              {customers.map((c) => (
                <option key={c.name} value={c.name} />
              ))}
            </datalist>
          </div>
          <div className="field field-grow">
            <label>Bundle (.tar.gz)</label>
            <input ref={fileRef} type="file" accept=".tar.gz,.tgz,application/gzip" />
          </div>
          <button type="button" className="btn primary" disabled={importing} onClick={onImport}>
            {importing ? "Importing…" : "Import"}
          </button>
        </div>
        {importResult && (
          <p className="pill ok" role="status">
            {importResult.message}
            <br />
            <strong>Cluster:</strong> {importResult.cluster_name} ({importResult.cluster_id})
            {importResult.log_time_start && importResult.log_time_end && (
              <>
                <br />
                <strong>Log aralığı:</strong> {formatRange(importResult.log_time_start, importResult.log_time_end)}
              </>
            )}
            {" — "}
            <Link
              to={`/bundle-logs?cluster=${encodeURIComponent(importResult.cluster_id)}&bundle=${encodeURIComponent(importResult.bundle_id)}`}
            >
              Analyze logs
            </Link>
          </p>
        )}
      </section>

      <section className="card">
        <h2>Lab collect (Docker)</h2>
        <div className="cluster-bar" style={{ display: "flex", gap: "1rem", flexWrap: "wrap", alignItems: "flex-end" }}>
          <label className="field">
            Cluster
            <select value={clusterId} onChange={(e) => setClusterId(e.target.value)}>
              {clusters.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="btn primary" disabled={collecting || !clusterId} onClick={onCollect}>
            {collecting ? "Collecting…" : "Collect bundle"}
          </button>
          <button type="button" className="btn" disabled={loading} onClick={refresh}>
            Refresh
          </button>
        </div>
      </section>

      {err && <p className="error-banner">{err}</p>}

      <section className="card">
        <h2>Snapshots{selectedCustomer ? ` — ${selectedCustomer}` : ""}</h2>
        {bundles.length === 0 && !loading && <p>No bundles for this filter.</p>}
        {bundles.length > 0 && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Bundle</th>
                <th>Müşteri</th>
                <th>Cluster</th>
                <th>Log range</th>
                <th>Lines</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {bundles.map((b) => (
                <tr key={b.id}>
                  <td>
                    <code>{b.id}</code>
                  </td>
                  <td>{b.customer_name || "—"}</td>
                  <td>{b.cluster_name}</td>
                  <td>{formatRange(b.log_time_start, b.log_time_end) || "—"}</td>
                  <td>{b.line_count}</td>
                  <td className="actions">
                    <Link
                      className="btn btn-sm"
                      to={`/bundle-logs?cluster=${encodeURIComponent(b.cluster_id)}&bundle=${encodeURIComponent(b.id)}`}
                    >
                      Analyze
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  );
}
