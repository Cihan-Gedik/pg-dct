from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

LogSource = Literal["patroni", "postgres", "etcd", "os"]
LogLevel = Literal["critical", "warning", "info"]


class NodeRead(BaseModel):
    id: int
    cluster_id: str
    member_name: str
    host: str
    patroni_port: int
    api_url: str | None
    role: str
    state: str | None
    last_seen_at: datetime | None

    model_config = {"from_attributes": True}


class ClusterCreate(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-_]{1,62}$")
    name: str = Field(min_length=1, max_length=128)
    engine: str = Field(default="postgresql")
    patroni_scope: str | None = None
    patroni_seed_url: HttpUrl
    etcd_endpoints: list[str] | None = None
    poll_interval_sec: int = Field(default=5, ge=1, le=300)


class ClusterRead(BaseModel):
    id: str
    name: str
    engine: str
    patroni_scope: str | None
    patroni_seed_url: str
    etcd_endpoints: list[str] | None
    poll_interval_sec: int
    created_at: datetime
    updated_at: datetime
    nodes: list[NodeRead] = []

    model_config = {"from_attributes": True}


class ClusterListItem(BaseModel):
    id: str
    name: str
    engine: str
    poll_interval_sec: int
    node_count: int

    model_config = {"from_attributes": True}


class DiscoverResult(BaseModel):
    cluster_id: str
    discovered: int
    members: list[NodeRead]


class LogEntryRead(BaseModel):
    ts: str
    node: str
    member_name: str
    source: LogSource
    level: LogLevel
    message: str


class LogsResponse(BaseModel):
    cluster_id: str
    count: int
    lines: list[LogEntryRead]
    peer_noise_filtered: int = 0
    fetched_at: datetime


class LiveMemberRead(BaseModel):
    name: str
    host: str
    role: str
    state: str | None
    timeline: int | None = None
    lag: int | None = None
    switchover_count: int = 0
    container: str | None = None
    container_running: bool | None = None


class EtcdMemberRead(BaseModel):
    name: str
    member_id: str
    host: str
    role: str
    state: str
    client_url: str = ""
    peer_url: str = ""
    container: str | None = None
    container_running: bool | None = None


class DcsStatusRead(BaseModel):
    patroni_leader: str | None = None
    patroni_leader_host: str | None = None
    failover_candidates: list[str] = []
    etcd_raft_leader: str | None = None
    etcd_raft_leader_id: str | None = None
    etcd_cluster_id: str | None = None
    etcd_raft_term: int | None = None


class TimelineSegmentRead(BaseModel):
    role: str
    start: str
    end: str
    leader: str | None = None
    timeline: int | None = None
    reason: str = ""


class TimelineMemberRead(BaseModel):
    member: str
    segments: list[TimelineSegmentRead]


class TimelineSwitchRead(BaseModel):
    at: str
    leader: str
    timeline: int | None = None
    reason: str = ""


class DashboardIssueRead(BaseModel):
    id: str
    cluster_id: str
    cluster_name: str
    level: LogLevel
    kind: str
    category: str
    member_name: str | None
    host: str | None
    source: str
    title: str
    message: str
    ts: str | None = None
    detail: str | None = None
    occurrence_count: int = 1
    last_seen: str | None = None
    first_seen: str | None = None


class DashboardIssuesResponse(BaseModel):
    critical_count: int
    warning_count: int
    issues: list[DashboardIssueRead]
    fetched_at: datetime


class ClusterTimelineResponse(BaseModel):
    cluster_id: str
    range_start: datetime
    range_end: datetime
    current_leader: str | None
    members: list[TimelineMemberRead]
    switchovers: list[TimelineSwitchRead]
    fetched_at: datetime


class LiveClusterResponse(BaseModel):
    cluster_id: str
    scope: str | None
    members: list[LiveMemberRead]
    leader: str | None
    etcd_quorum: str | None = None
    etcd_members: list[EtcdMemberRead] = []
    dcs: DcsStatusRead | None = None
    max_lag_bytes: int | None = None
    switchover_total: int = 0
    expected_nodes: int = 0
    active_nodes: int = 0
    alerts: list[str] = []
    fetched_at: datetime


BackupJobKind = Literal[
    "backup_full",
    "backup_diff",
    "backup_incr",
    "check",
    "stanza_create",
]


class BackupInfoResponse(BaseModel):
    cluster_id: str
    ok: bool
    error: str | None = None
    container: str | None = None
    member: str | None = None
    host: str | None = None
    stanza: str = ""
    stanzas: list[dict] = []
    stdout_tail: str | None = None
    fetched_at: datetime


class BackupJobCreate(BaseModel):
    kind: BackupJobKind
    params: dict[str, str] = Field(default_factory=dict)


class BackupJobRead(BaseModel):
    id: int
    cluster_id: str
    kind: str
    status: Literal["pending", "running", "succeeded", "failed"]
    params: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    exit_code: int | None = None
    stdout_tail: str = ""
    error: str | None = None
