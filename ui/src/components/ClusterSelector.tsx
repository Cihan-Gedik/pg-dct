import { useMemo, useState } from "react";
import type { ClusterListItem } from "../api";

type Props = {
  clusters: ClusterListItem[];
  selectedId: string;
  onSelect: (id: string) => void;
};

/** Compact cluster picker — scales to many clusters (search + list). */
export function ClusterSelector({ clusters, selectedId, onSelect }: Props) {
  const [query, setQuery] = useState("");

  const selected = clusters.find((c) => c.id === selectedId);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return clusters;
    return clusters.filter(
      (c) => c.id.toLowerCase().includes(q) || c.name.toLowerCase().includes(q) || c.engine.toLowerCase().includes(q),
    );
  }, [clusters, query]);

  return (
    <div className="cluster-selector">
      <div className="cluster-selector-current">
        <span className="cluster-selector-label">Active cluster</span>
        <strong className="cluster-selector-name">{selected?.name ?? selectedId}</strong>
        {selected && (
          <span className="pill">
            {selected.id} · {selected.node_count} nodes
          </span>
        )}
      </div>
      <div className="cluster-selector-controls">
        <input
          type="search"
          className="cluster-search"
          placeholder="Search clusters…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search clusters"
        />
        <select
          className="cluster-select"
          value={selectedId}
          onChange={(e) => onSelect(e.target.value)}
          aria-label="Select cluster"
        >
          {filtered.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.id}) — {c.node_count} nodes
            </option>
          ))}
        </select>
      </div>
      {filtered.length > 1 && filtered.length <= 8 && (
        <div className="cluster-chips">
          {filtered.map((c) => (
            <button
              key={c.id}
              type="button"
              className={`cluster-chip ${c.id === selectedId ? "active" : ""}`}
              onClick={() => onSelect(c.id)}
            >
              {c.name}
            </button>
          ))}
        </div>
      )}
      {filtered.length > 8 && (
        <p className="pill cluster-selector-hint">{filtered.length} clusters — use search or dropdown</p>
      )}
    </div>
  );
}
