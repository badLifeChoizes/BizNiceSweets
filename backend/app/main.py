"""
BizNiceSweets FastAPI application factory.

Startup sequence (D-09):
  1. Container entrypoint waits for Postgres, runs alembic upgrade head.
  2. uvicorn starts this module — lifespan runs (no migration work here).
  3. Health router is mounted, SYERP self-registers, mount_all wires routers.

SPA static-file serving (D-08) is intentionally NOT mounted here.
It will be added in Plan 03 (container + compose wiring), mounted LAST
so it does not swallow /api/* routes. See Pattern 4 in RESEARCH.md.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.registry import mount_all

# --- Lifespan ----------------------------------------------------------------
# Migrations have already been applied by entrypoint.sh before uvicorn starts.
# Add any startup/shutdown hooks here as they are needed (caches, background
# tasks, etc.).  Phase 1: empty yield — no work to do at startup.


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    yield
    # Shutdown


# --- App factory -------------------------------------------------------------

app = FastAPI(
    title="BizNiceSweets",
    description="Modular business suite for small-to-medium manufacturers.",
    version="0.1.0",
    lifespan=lifespan,
)

# Health endpoints (unauthenticated; always mounted)
app.include_router(health_router)

# Module registration: import causes syerp/__init__.py to call register()
import app.modules.syerp  # noqa: E402, F401

# Wire all registered module routers under /api/v1
mount_all(app)

# ---------------------------------------------------------------------------
# SPA MOUNT PLACEHOLDER (Plan 03)
# ---------------------------------------------------------------------------
# from app.core.config import settings
# from app.main_spa import SPAStaticFiles
# import os
# if os.path.isdir(settings.static_dir):
#     app.mount("/", SPAStaticFiles(directory=settings.static_dir, html=True), name="spa")
# ---------------------------------------------------------------------------
