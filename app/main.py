"""MS365 Auto Renew FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    accounts_router,
    auth_router,
    logs_router,
    settings_router,
    setup_router,
    tasks_router,
)
from app.config import settings
from app.database import AsyncSessionLocal, init_db
from app.security import error_detail
from app.services.scheduler_service import scheduler_service
from app.services.setup_service import setup_manager

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

APP_CSP = (
    "default-src 'none'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "font-src 'self' data:; "
    "form-action 'self'; "
    "base-uri 'none'; "
    "frame-ancestors 'none'"
)
DOCS_CSP = (
    "default-src 'none'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "connect-src 'self'; "
    "font-src 'self' data: https://cdn.jsdelivr.net https://unpkg.com; "
    "base-uri 'none'; "
    "frame-ancestors 'none'"
)


@asynccontextmanager
async def lifespan(application: FastAPI):
    await init_db()
    async with AsyncSessionLocal() as db:
        await setup_manager.prepare(db)

    scheduler_service.start()
    if setup_manager.initialized:
        await scheduler_service.load_and_schedule_all()
    yield
    scheduler_service.shutdown()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "A self-hosted development and testing scheduler for delegated Microsoft Graph workflows. "
        "It does not guarantee Microsoft 365 Developer subscription renewal."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def setup_gate(request: Request, call_next):
    """Gate pre-setup APIs and attach the browser security baseline."""
    await setup_manager.ensure_prepared()
    path = request.url.path
    public_before_setup = (
        path in {"/", "/health", "/api/health"}
        or path.startswith("/static/")
        or path.startswith("/api/setup/")
        or (not path.startswith("/api/") and path not in {"/docs", "/redoc", "/openapi.json"})
    )
    if not setup_manager.initialized and not public_before_setup:
        response = JSONResponse(
            status_code=503,
            content={"detail": error_detail("setup_required", "Complete first-run setup to continue.")},
        )
    else:
        response = await call_next(request)

    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers.setdefault(
        "Content-Security-Policy",
        DOCS_CSP if path in {"/docs", "/redoc", "/openapi.json"} else APP_CSP,
    )
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


app.include_router(setup_router)
app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(tasks_router)
app.include_router(logs_router)
app.include_router(settings_router)


@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "scheduler_running": scheduler_service.is_running,
    }


STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    target_file = (STATIC_DIR / full_path).resolve()
    if full_path and target_file.is_relative_to(STATIC_DIR.resolve()) and target_file.is_file():
        return FileResponse(str(target_file))
    index_html = STATIC_DIR / "index.html"
    if index_html.exists():
        return FileResponse(str(index_html))
    return JSONResponse(
        status_code=404,
        content={"detail": error_detail("static_files_missing", "Static WebUI files were not found.")},
    )
