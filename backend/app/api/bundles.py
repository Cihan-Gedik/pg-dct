from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas import (
    BundleCollectResponse,
    BundleDetail,
    BundleImportResponse,
    BundleListItem,
    CustomerListItem,
    LogEntryRead,
    LogLevel,
    LogSource,
    LogsResponse,
)
from app.services.bundle_collect import collect_cluster_bundle
from app.services.bundle_import import import_bundle_archive
from app.services.bundle_store import bundle_dir, list_bundles, list_customers, load_bundle_entries, load_manifest
from app.services.docker_logs import suppress_etcd_peer_noise
from app.services.logs_filter import filter_by_time_window, filter_log_entries, parse_range_datetime

router = APIRouter(tags=["bundles"])

ALL_SOURCES: list[LogSource] = ["patroni", "postgres", "etcd", "os"]
ALL_LEVELS: list[LogLevel] = ["critical", "warning", "info"]


@router.get("/bundles/customers", response_model=list[CustomerListItem])
async def get_bundle_customers() -> list[CustomerListItem]:
    return [CustomerListItem(**row) for row in list_customers()]


@router.get("/bundles", response_model=list[BundleListItem])
async def get_bundles(
    cluster_id: str | None = Query(default=None),
    customer_name: str | None = Query(default=None),
) -> list[BundleListItem]:
    return [
        BundleListItem(
            id=b.id,
            cluster_id=b.cluster_id,
            cluster_name=b.cluster_name,
            customer_name=b.customer_name,
            created_at=b.created_at,
            line_count=b.line_count,
            node_count=b.node_count,
            has_archive=b.archive_path is not None,
            log_time_start=b.log_time_start,
            log_time_end=b.log_time_end,
        )
        for b in list_bundles(cluster_id, customer_name)
    ]


@router.post("/bundles/import", response_model=BundleImportResponse)
async def import_bundle(
    file: UploadFile = File(...),
    customer_name: str = Form(..., min_length=1, max_length=128),
    cluster_name: str | None = Form(default=None),
    cluster_id: str | None = Form(default=None),
    session: AsyncSession = Depends(get_session),
) -> BundleImportResponse:
    if not file.filename or not (file.filename.endswith(".tar.gz") or file.filename.endswith(".tgz")):
        raise HTTPException(status_code=400, detail="Upload a .tar.gz bundle file from pgdct-bundle-collector")
    data = await file.read()
    if len(data) < 32:
        raise HTTPException(status_code=400, detail="File too small to be a valid bundle")
    try:
        result = await import_bundle_archive(
            session,
            data,
            customer_name.strip(),
            cluster_name.strip() if cluster_name else None,
            cluster_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Import failed: {exc}") from exc
    return BundleImportResponse(**result)


@router.get("/bundles/{bundle_id}", response_model=BundleDetail)
async def get_bundle(bundle_id: str) -> BundleDetail:
    manifest = load_manifest(bundle_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Bundle not found")
    archive = bundle_dir(bundle_id) / "bundle.tar.gz"
    return BundleDetail(
        id=bundle_id,
        cluster_id=str(manifest.get("cluster_id") or ""),
        cluster_name=str(manifest.get("cluster_name") or ""),
        customer_name=str(manifest.get("customer_name") or ""),
        created_at=str(manifest.get("created_at") or ""),
        line_count=int(manifest.get("line_count") or 0),
        lines_per_source=int(manifest.get("lines_per_source") or 0),
        sources=list(manifest.get("sources") or []),
        nodes=list(manifest.get("nodes") or []),
        patroni_snapshot=manifest.get("patroni_snapshot"),
        has_archive=archive.is_file(),
    )


@router.get("/bundles/{bundle_id}/archive")
async def download_bundle_archive(bundle_id: str) -> FileResponse:
    archive = bundle_dir(bundle_id) / "bundle.tar.gz"
    if not archive.is_file():
        raise HTTPException(status_code=404, detail="Archive not found for this bundle")
    return FileResponse(
        path=str(archive),
        filename=f"{bundle_id}.tar.gz",
        media_type="application/gzip",
    )


@router.get("/bundles/{bundle_id}/logs", response_model=LogsResponse)
async def get_bundle_logs(
    bundle_id: str,
    node: str = Query(default="all"),
    severity: str = Query(default="critical,warning,info"),
    patroni: str = Query(default="include"),
    postgres: str = Query(default="include"),
    etcd: str = Query(default="include"),
    os_log: str = Query(default="include", alias="os"),
    search: str = Query(default=""),
    hours: float | None = Query(default=None, ge=1, le=720),
    range_from: str | None = Query(default=None, description="ISO datetime lower bound (inclusive)"),
    range_to: str | None = Query(default=None, description="ISO datetime upper bound (inclusive)"),
    suppress_peer_noise: bool = Query(default=False),
) -> LogsResponse:
    manifest = load_manifest(bundle_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Bundle not found")

    cluster_id = str(manifest.get("cluster_id") or "")
    level_set = [lv.strip() for lv in severity.split(",") if lv.strip()]
    levels: list[LogLevel] = [lv for lv in ALL_LEVELS if not level_set or lv in level_set]
    source_modes: dict[LogSource, str] = {
        "patroni": patroni,
        "postgres": postgres,
        "etcd": etcd,
        "os": os_log,
    }

    raw = load_bundle_entries(bundle_id)
    peer_filtered = 0
    if suppress_peer_noise:
        down_hosts = {
            str(n.get("host") or "")
            for n in (manifest.get("patroni_snapshot") or [])
            if isinstance(n, dict) and n.get("state") in ("stopped", "crashed", "start failed")
        }
        down_hosts.discard("")
        if down_hosts:
            before = len(raw)
            raw = suppress_etcd_peer_noise(raw, down_hosts)
            peer_filtered = before - len(raw)

    filtered = filter_log_entries(raw, node, levels, source_modes, search)
    rf = parse_range_datetime(range_from)
    rt = parse_range_datetime(range_to)
    if rf is not None or rt is not None:
        filtered = filter_by_time_window(filtered, range_from=rf, range_to=rt)
    elif hours is not None:
        filtered = filter_by_time_window(filtered, hours=hours)

    return LogsResponse(
        cluster_id=cluster_id,
        count=len(filtered),
        peer_noise_filtered=peer_filtered,
        lines=[
            LogEntryRead(
                ts=e.ts,
                node=e.node,
                member_name=e.member_name,
                source=e.source,
                level=e.level,
                message=e.message,
            )
            for e in filtered
        ],
        fetched_at=datetime.now(UTC),
    )


@router.post("/clusters/{cluster_id}/bundles/collect", response_model=BundleCollectResponse)
async def collect_bundle(
    cluster_id: str,
    lines: int = Query(default=500, ge=50, le=2000),
    session: AsyncSession = Depends(get_session),
) -> BundleCollectResponse:
    try:
        result = await collect_cluster_bundle(session, cluster_id, lines_per_source=lines)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Bundle collection failed: {exc}") from exc

    return BundleCollectResponse(
        ok=True,
        bundle_id=result["bundle_id"],
        cluster_id=result["cluster_id"],
        line_count=result["line_count"],
        path=result.get("path"),
        archive_path=result.get("archive_path"),
    )
