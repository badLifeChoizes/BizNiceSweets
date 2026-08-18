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
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.health import router as health_router
from app.core.config import settings
from app.core.db import AsyncSessionLocal
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
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    # Startup — run seed data (idempotent; no-op if already seeded)
    from app.core.seed import run_seeds

    async with AsyncSessionLocal() as db:
        await run_seeds(db)
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

# Module registration: importlib.import_module triggers <module>/__init__.py
# which calls registry.register(). Using importlib avoids shadowing the `app`
# variable (FastAPI instance) with the `app` package name that a bare
# `import app.modules.*` statement would cause.
importlib.import_module("app.modules.syerp")
importlib.import_module("app.modules.plum")
importlib.import_module("app.modules.mousse")
importlib.import_module("app.modules.crumb")
importlib.import_module("app.modules.gelato")
importlib.import_module("app.modules.auth")

# Fully populate Base.metadata before serving. Module __init__ imports only the
# router, and GELATO's service imports its models LAZILY inside functions (so SYERP
# never imports gelato models — D-P12a-3). That leaves cross-module string FKs (e.g.
# syerp_inventory_txn.bin_id -> gelato_bin) unresolvable on a fresh process until some
# gelato service call happens to load the models, so the first InventoryTxn ORM flush
# 500s on mapper configuration. Importing the central aggregator here registers every
# module's tables up front — the same metadata contract Alembic and the verify_*.py
# scripts already rely on. importlib (not a bare import) avoids shadowing the `app`
# FastAPI instance with the `app` package, exactly as the module imports above do.
importlib.import_module("app.core.models")

# Wire all registered module routers under /api/v1
mount_all(app)

# ---------------------------------------------------------------------------
# Core platform routers (modules + settings) — mounted directly under /api/v1.
# These are cross-cutting platform concerns, NOT module packages, so they are
# not registered via the module registry. Mounted AFTER mount_all() (which
# handles module routers) and BEFORE the SPA catch-all (below) so /api/*
# traffic is never swallowed by the static file handler.
# ---------------------------------------------------------------------------
from app.core.modules_router import router as modules_router  # noqa: E402
from app.core.settings_router import router as settings_router  # noqa: E402

app.include_router(modules_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")

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
