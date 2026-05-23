from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.clusters import discover_cluster
from app.db import get_session
from app.services.bootstrap import bootstrap_clusters, default_clusters_path, load_clusters_yaml

router = APIRouter(prefix="/bootstrap", tags=["bootstrap"])


@router.post("/docker")
async def bootstrap_docker_clusters(session: AsyncSession = Depends(get_session)) -> dict:
    """Upsert clusters from config/docker-clusters.yaml and run discover on each."""
    path = default_clusters_path()
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Config not found: {path}")

    cluster_ids = await bootstrap_clusters(session, path)
    discover_results: dict[str, str] = {}
    for cluster_id in cluster_ids:
        try:
            result = await discover_cluster(cluster_id, session)
            discover_results[cluster_id] = f"ok:{result.discovered} nodes"
        except HTTPException as exc:
            discover_results[cluster_id] = f"error:{exc.detail}"
        except Exception as exc:  # noqa: BLE001
            discover_results[cluster_id] = f"error:{exc}"

    return {
        "config": str(path),
        "clusters": cluster_ids,
        "discover": discover_results,
        "yaml_preview": load_clusters_yaml(path),
    }
