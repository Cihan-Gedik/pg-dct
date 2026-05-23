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
    fetched_at: datetime


class LiveMemberRead(BaseModel):
    name: str
    host: str
    role: str
    state: str | None
    timeline: int | None = None
    lag: int | None = None


class LiveClusterResponse(BaseModel):
    cluster_id: str
    scope: str | None
    members: list[LiveMemberRead]
    leader: str | None
    etcd_quorum: str | None = None
    max_lag_bytes: int | None = None
    fetched_at: datetime
