"""
BizNiceSweets FastAPI application factory.

Startup sequence (D-09):
  1. Container entrypoint waits for Postgres, runs alembic upgrade head.
  2. uvicorn starts this module — lifespan runs (no migration work here).
  3. Health router is mounted, SYERP self-registers, mount_all wires routers.
  4. SPAStaticFiles is mounted LAST at "/" so it never swallows /api/* routes.

SPA static-file serving (D-08): SPAStaticFiles subclass catches 404s from
StaticFiles and returns index.html, letting React Router handle client routes.
See Pattern 4 in RESEARCH.md.
"""
import importlib
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.health import router as health_router
from app.core.config import settings
from app.core.registry import mount_all


# --- SPA static-file fallback (D-08) ----------------------------------------
# Subclass catches 404 from StaticFiles and serves index.html so React Router
# can handle client-side routes.  Mounted LAST — after all /api and health
# routes — so it never intercepts API traffic.

class SPAStaticFiles(StaticFiles):
    """StaticFiles subclass with SPA fallback: 404 → index.html."""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as ex:
            if ex.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


# --- Lifespan ----------------------------------------------------------------
# Migrations have already been applied by entrypoint.sh before uvicorn starts.
# Add any startup/shutdown hooks here as they are needed (caches, background
# tasks, etc.).  Phase 1: empty yield — no work to do at startup.


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
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

# Module registration: importlib.import_module triggers syerp/__init__.py
# which calls registry.register(). Using importlib avoids shadowing the `app`
# variable (FastAPI instance) with the `app` package name that a bare
# `import app.modules.syerp` statement would cause.
importlib.import_module("app.modules.syerp")

# Wire all registered module routers under /api/v1
mount_all(app)

# ---------------------------------------------------------------------------
# SPA mount (D-08) — MUST be last: mounted after all API and health routes
# so the catch-all does not swallow /api/* traffic.  Guarded by directory
# existence so the app still starts cleanly outside the production container
# (e.g. native dev run without a pre-built frontend/dist).
# ---------------------------------------------------------------------------
_static_dir = settings.static_dir
if os.path.isdir(_static_dir):
    app.mount(
        "/",
        SPAStaticFiles(directory=_static_dir, html=True),
        name="spa",
    )
