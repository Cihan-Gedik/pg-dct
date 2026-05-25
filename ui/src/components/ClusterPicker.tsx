import type { ClusterListItem } from "../api";

type Props = {
  clusters: ClusterListItem[];
  selectedId: string;
  onSelect: (id: string) => void;
};

export function ClusterPicker({ clusters, selectedId, onSelect }: Props) {
  return (
    <div className="cluster-picker">
      {clusters.map((c) => (
        <button
          key={c.id}
          type="button"
          className={`cluster-card ${c.id === selectedId ? "active" : ""}`}
          onClick={() => onSelect(c.id)}
        >
          <span className="cluster-card-name">{c.name}</span>
          <span className="cluster-card-meta">{c.node_count} nodes · {c.poll_interval_sec}s poll</span>
        </button>
      ))}
    </div>
  );
}
