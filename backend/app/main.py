import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.bootstrap import router as bootstrap_router
from app.api.clusters import router as clusters_router
from app.config import settings
from app.db import SessionLocal, init_db
from app.services.bootstrap import bootstrap_clusters, default_clusters_path


STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    if os.getenv("PGDCT_BOOTSTRAP_DOCKER", "").lower() in ("1", "true", "yes"):
        async with SessionLocal() as session:
            await bootstrap_clusters(session, default_clusters_path())
    yield


app = FastAPI(
    title="PG-DCT API",
    description="Database control toolkit — Patroni troubleshooting and future multi-DB tasks",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clusters_router, prefix="/api/v1")
app.include_router(bootstrap_router, prefix="/api/v1")

if STATIC_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=str(STATIC_DIR), html=True), name="ui")


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/ui/")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "pg-dct-api"}
