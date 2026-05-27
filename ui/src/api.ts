export type DashboardIssue = {
  id: string;
  cluster_id: string;
  cluster_name: string;
  level: "critical" | "warning" | "info";
  kind: string;
  category: string;
  member_name: string | null;
  host: string | null;
  source: string;
  title: string;
  message: string;
  ts: string | null;
  detail: string | null;
  occurrence_count: number;
  last_seen: string | null;
  first_seen: string | null;
};

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

export type LiveMember = {
  name: string;
  host: string;
  role: string;
  state: string | null;
  timeline?: number | null;
  lag?: number | null;
  switchover_count: number;
  container?: string | null;
  container_running?: boolean | null;
};

export type EtcdMember = {
  name: string;
  member_id: string;
  host: string;
  role: string;
  state: string;
  client_url: string;
  peer_url: string;
  container?: string | null;
  container_running?: boolean | null;
};

export type DcsStatus = {
  patroni_leader: string | null;
  patroni_leader_host: string | null;
  failover_candidates: string[];
  etcd_raft_leader: string | null;
  etcd_raft_leader_id: string | null;
  etcd_cluster_id: string | null;
  etcd_raft_term: number | null;
};

export type TimelineSegment = {
  role: string;
  start: string;
  end: string;
  leader?: string | null;
  timeline?: number | null;
  reason: string;
};

export type ClusterTimeline = {
  cluster_id: string;
  range_start: string;
  range_end: string;
  current_leader: string | null;
  members: { member: string; segments: TimelineSegment[] }[];
  switchovers: { at: string; leader: string; timeline?: number | null; reason: string }[];
};

export type BackupJobKind =
  | "backup_full"
  | "backup_diff"
  | "backup_incr"
  | "check"
  | "stanza_create";

export type BackupInfo = {
  cluster_id: string;
  ok: boolean;
  error: string | null;
  container: string | null;
  member: string | null;
  host: string | null;
  stanza: string;
  stanzas: Record<string, unknown>[];
  stdout_tail: string | null;
  fetched_at: string;
};

export type BackupJob = {
  id: number;
  cluster_id: string;
  kind: string;
  status: "pending" | "running" | "succeeded" | "failed";
  params: Record<string, string>;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  exit_code: number | null;
  stdout_tail: string;
  error: string | null;
};

export type PostgresSetting = {
  name: string;
  label: string;
  value: string;
  raw_setting: string;
  unit: string | null;
};

export type BundleListItem = {
  id: string;
  cluster_id: string;
  cluster_name: string;
  customer_name: string;
  created_at: string;
  line_count: number;
  node_count: number;
  has_archive: boolean;
  log_time_start?: string | null;
  log_time_end?: string | null;
};

export type CustomerListItem = {
  name: string;
  bundle_count: number;
  latest_bundle_id: string | null;
  latest_cluster_id: string | null;
};

export type BundleCollectResult = {
  ok: boolean;
  bundle_id: string;
  cluster_id: string;
  line_count: number;
  path?: string | null;
  archive_path?: string | null;
};

export type BundleImportResult = {
  ok: boolean;
  bundle_id: string;
  cluster_id: string;
  cluster_name: string;
  customer_name: string;
  line_count: number;
  log_time_start?: string | null;
  log_time_end?: string | null;
  message: string;
};

export type PostgresSettings = {
  cluster_id: string;
  ok: boolean;
  error: string | null;
  leader: string | null;
  host: string | null;
  container: string | null;
  version: string | null;
  settings: PostgresSetting[];
};

export type LiveCluster = {
  cluster_id: string;
  scope: string | null;
  members: LiveMember[];
  leader: string | null;
  max_lag_bytes: number | null;
  switchover_total: number;
  expected_nodes: number;
  active_nodes: number;
  alerts: string[];
  etcd_quorum?: string | null;
  etcd_members?: EtcdMember[];
  dcs?: DcsStatus | null;
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
  dashboardIssues: (hours?: number) => {
    const q = hours != null ? `?hours=${hours}` : "";
    return request<{ critical_count: number; warning_count: number; issues: DashboardIssue[] }>(
      `/api/v1/dashboard/issues${q}`,
    );
  },
  getCluster: (id: string) => request<ClusterRead>(`/api/v1/clusters/${id}`),
  discover: (id: string) => request<unknown>(`/api/v1/clusters/${id}/discover`, { method: "POST" }),
  bootstrapDocker: () => request<unknown>("/api/v1/bootstrap/docker", { method: "POST" }),
  live: (id: string) => request<LiveCluster>(`/api/v1/clusters/${id}/live`),
  postgresSettings: (id: string) =>
    request<PostgresSettings>(`/api/v1/clusters/${id}/postgres/settings`),
  timeline: (id: string, hours: number) =>
    request<ClusterTimeline>(`/api/v1/clusters/${id}/timeline?hours=${hours}`),
  logs: (id: string, params: URLSearchParams) => {
    const q = new URLSearchParams(params);
    q.set("_ts", String(Date.now()));
    return request<{ count: number; lines: LogEntry[]; peer_noise_filtered?: number; fetched_at?: string }>(
      `/api/v1/clusters/${id}/logs?${q}`,
    );
  },
  listCustomers: () => request<CustomerListItem[]>("/api/v1/bundles/customers"),
  listBundles: (opts?: { clusterId?: string; customerName?: string }) => {
    const q = new URLSearchParams();
    if (opts?.clusterId) q.set("cluster_id", opts.clusterId);
    if (opts?.customerName) q.set("customer_name", opts.customerName);
    const qs = q.toString();
    return request<BundleListItem[]>(`/api/v1/bundles${qs ? `?${qs}` : ""}`);
  },
  collectBundle: (clusterId: string, lines = 500) =>
    request<BundleCollectResult>(
      `/api/v1/clusters/${clusterId}/bundles/collect?lines=${lines}`,
      { method: "POST" },
    ),
  bundleLogs: (bundleId: string, params: URLSearchParams) => {
    const q = new URLSearchParams(params);
    return request<{ count: number; lines: LogEntry[]; peer_noise_filtered?: number; fetched_at?: string }>(
      `/api/v1/bundles/${encodeURIComponent(bundleId)}/logs?${q}`,
    );
  },
  bundleArchiveUrl: (bundleId: string) =>
    `/api/v1/bundles/${encodeURIComponent(bundleId)}/archive`,
  importBundle: (file: File, customerName: string, clusterName?: string, clusterId?: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("customer_name", customerName);
    if (clusterName) form.append("cluster_name", clusterName);
    if (clusterId) form.append("cluster_id", clusterId);
    return request<BundleImportResult>("/api/v1/bundles/import", { method: "POST", body: form });
  },
  backupInfo: (id: string) => request<BackupInfo>(`/api/v1/clusters/${id}/backup/info`),
  backupJobs: (id: string) => request<BackupJob[]>(`/api/v1/clusters/${id}/backup/jobs`),
  createBackupJob: (id: string, body: { kind: BackupJobKind; params?: Record<string, string> }) =>
    request<BackupJob>(`/api/v1/clusters/${id}/backup/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
};
