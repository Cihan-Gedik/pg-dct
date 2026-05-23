import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Cluster, Node
from app.schemas import ClusterCreate, ClusterListItem, ClusterRead, DiscoverResult, NodeRead
from app.services.patroni import PatroniDiscoveryError, fetch_cluster_members, member_to_node_fields

router = APIRouter(prefix="/clusters", tags=["clusters"])


def _cluster_to_read(cluster: Cluster) -> ClusterRead:
    endpoints = None
    if cluster.etcd_endpoints:
        endpoints = json.loads(cluster.etcd_endpoints)
    return ClusterRead(
        id=cluster.id,
        name=cluster.name,
        engine=cluster.engine,
        patroni_scope=cluster.patroni_scope,
        patroni_seed_url=cluster.patroni_seed_url,
        etcd_endpoints=endpoints,
        poll_interval_sec=cluster.poll_interval_sec,
        created_at=cluster.created_at,
        updated_at=cluster.updated_at,
        nodes=[NodeRead.model_validate(n) for n in cluster.nodes],
    )


@router.get("", response_model=list[ClusterListItem])
async def list_clusters(session: AsyncSession = Depends(get_session)) -> list[ClusterListItem]:
    result = await session.execute(select(Cluster).options(selectinload(Cluster.nodes)))
    clusters = result.scalars().all()
    return [
        ClusterListItem(
            id=c.id,
            name=c.name,
            engine=c.engine,
            poll_interval_sec=c.poll_interval_sec,
            node_count=len(c.nodes),
        )
        for c in clusters
    ]


@router.post("", response_model=ClusterRead, status_code=201)
async def create_cluster(
    body: ClusterCreate,
    session: AsyncSession = Depends(get_session),
) -> ClusterRead:
    existing = await session.get(Cluster, body.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Cluster '{body.id}' already exists")

    etcd_json = json.dumps(body.etcd_endpoints) if body.etcd_endpoints else None
    cluster = Cluster(
        id=body.id,
        name=body.name,
        engine=body.engine,
        patroni_scope=body.patroni_scope or body.id,
        patroni_seed_url=str(body.patroni_seed_url),
        etcd_endpoints=etcd_json,
        poll_interval_sec=body.poll_interval_sec,
    )
    session.add(cluster)
    await session.commit()
    await session.refresh(cluster, ["nodes"])
    return _cluster_to_read(cluster)


@router.get("/{cluster_id}", response_model=ClusterRead)
async def get_cluster(
    cluster_id: str,
    session: AsyncSession = Depends(get_session),
) -> ClusterRead:
    result = await session.execute(
        select(Cluster).where(Cluster.id == cluster_id).options(selectinload(Cluster.nodes))
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return _cluster_to_read(cluster)


@router.delete("/{cluster_id}", status_code=204)
async def delete_cluster(
    cluster_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    cluster = await session.get(Cluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    await session.delete(cluster)
    await session.commit()


@router.post("/{cluster_id}/discover", response_model=DiscoverResult)
async def discover_cluster(
    cluster_id: str,
    session: AsyncSession = Depends(get_session),
) -> DiscoverResult:
    result = await session.execute(
        select(Cluster).where(Cluster.id == cluster_id).options(selectinload(Cluster.nodes))
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    try:
        scope, members = await fetch_cluster_members(cluster.patroni_seed_url)
    except PatroniDiscoveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if scope and not cluster.patroni_scope:
        cluster.patroni_scope = scope

    by_name = {n.member_name: n for n in cluster.nodes}
    seen: set[str] = set()

    for member in members:
        fields = member_to_node_fields(member)
        name = fields["member_name"]
        seen.add(name)
        if name in by_name:
            node = by_name[name]
            for key, value in fields.items():
                setattr(node, key, value)
        else:
            session.add(Node(cluster_id=cluster.id, **fields))

    for name, node in list(by_name.items()):
        if name not in seen:
            await session.delete(node)

    await session.commit()
    await session.refresh(cluster, ["nodes"])

    nodes = [NodeRead.model_validate(n) for n in cluster.nodes]
    return DiscoverResult(cluster_id=cluster.id, discovered=len(nodes), members=nodes)
