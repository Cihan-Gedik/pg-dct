export type ClusterListItem = {
  id: string;
  name: string;
  engine: string;
  poll_interval_sec: number;
  node_count: number;
};

export type NodeRead = {
  id: number;
  cluster_id: string;
  member_name: string;
  host: string;
  patroni_port: number;
  role: string;
  state: string | null;
};

export type ClusterRead = {
  id: string;
  name: string;
  patroni_seed_url: string;
  poll_interval_sec: number;
  nodes: NodeRead[];
};

export type LogEntry = {
  ts: string;
  node: string;
  member_name: string;
  source: "patroni" | "postgres" | "etcd" | "os";
  level: "critical" | "warning" | "info";
  message: string;
};

export type LiveCluster = {
  cluster_id: string;
  scope: string | null;
  members: { name: string; host: string; role: string; state: string | null; lag?: number }[];
  leader: string | null;
  max_lag_bytes: number | null;
};

const API = "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  const text = await res.text();
  let body: unknown = text;
  try {
    body = JSON.parse(text);
  } catch {
    /* plain text */
  }
  if (!res.ok) {
    const detail = typeof body === "object" && body && "detail" in body ? (body as { detail: string }).detail : text;
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return body as T;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  listClusters: () => request<ClusterListItem[]>("/api/v1/clusters"),
  getCluster: (id: string) => request<ClusterRead>(`/api/v1/clusters/${id}`),
  discover: (id: string) => request<unknown>(`/api/v1/clusters/${id}/discover`, { method: "POST" }),
  bootstrapDocker: () => request<unknown>("/api/v1/bootstrap/docker", { method: "POST" }),
  live: (id: string) => request<LiveCluster>(`/api/v1/clusters/${id}/live`),
  logs: (id: string, params: URLSearchParams) =>
    request<{ count: number; lines: LogEntry[] }>(`/api/v1/clusters/${id}/logs?${params}`),
};
