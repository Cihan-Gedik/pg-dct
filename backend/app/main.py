import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.bootstrap import router as bootstrap_router
from app.api.dashboard import router as dashboard_router
from app.api.clusters import router as clusters_router
from app.api.live import router as live_router
from app.api.logs import router as logs_router
from app.api.timeline import router as timeline_router
from app.api.backups import router as backups_router
from app.api.bundles import router as bundles_router
from app.config import settings
from app.db import SessionLocal, init_db
from app.services.backup_schedules import scheduler_loop as backup_scheduler_loop
from app.services.bootstrap import bootstrap_clusters, default_clusters_path


STATIC_DIR = Path(__file__).resolve().parent / "static"
FAVICON_PATH = STATIC_DIR / "favicon.svg"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    if os.getenv("PGDCT_BOOTSTRAP_DOCKER", "").lower() in ("1", "true", "yes"):
        async with SessionLocal() as session:
            await bootstrap_clusters(session, default_clusters_path())
    scheduler_task = asyncio.create_task(backup_scheduler_loop(SessionLocal))
    try:
        yield
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="PG-DCT API",
    description="Database control toolkit — Patroni troubleshooting and future multi-DB tasks",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(clusters_router, prefix="/api/v1")
app.include_router(bootstrap_router, prefix="/api/v1")
app.include_router(live_router, prefix="/api/v1")
app.include_router(logs_router, prefix="/api/v1")
app.include_router(timeline_router, prefix="/api/v1")
app.include_router(backups_router, prefix="/api/v1")
app.include_router(bundles_router, prefix="/api/v1")


def _favicon_response() -> FileResponse:
    if not FAVICON_PATH.is_file():
        raise FileNotFoundError("favicon.svg missing — run: cd ui && npm run build")
    return FileResponse(
        FAVICON_PATH,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
async def favicon_root() -> FileResponse:
    """Browsers request /favicon.ico from site root (not under /ui/)."""
    return _favicon_response()


if STATIC_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=str(STATIC_DIR), html=True), name="ui")


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/ui/")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "pg-dct-api"}
