---
phase: 01-project-scaffolding-deployment
plan: "01"
subsystem: backend-core
tags: [fastapi, sqlalchemy, alembic, pytest, backend, scaffold]
dependency_graph:
  requires: []
  provides:
    - FastAPI app factory (backend/app/main.py)
    - Shared DeclarativeBase for all module models (backend/app/core/base.py)
    - pydantic-settings config with SecretStr password (backend/app/core/config.py)
    - Async SQLAlchemy engine and get_db dependency (backend/app/core/db.py)
    - Module registry (register/mount_all) (backend/app/core/registry.py)
    - Liveness and readiness health endpoints (backend/app/api/health.py)
    - Central model aggregator for Alembic autogenerate (backend/app/core/models.py)
    - SYERP always-on hub stub (backend/app/modules/syerp/)
    - Seed hook pattern (backend/app/core/seed.py)
    - Single Alembic migration history (backend/alembic/)
    - pytest Wave 0 harness (backend/tests/)
  affects: []
tech_stack:
  added:
    - fastapi==0.138.0
    - sqlalchemy==2.0.51
    - alembic==1.18.4
    - pydantic-settings==2.14.2
    - uvicorn[standard]==0.49.0
    - asyncpg==0.31.0
    - psycopg2-binary==2.9.12
    - python-multipart==0.0.32
    - anyio==4.14.0
    - pytest==9.1.1
    - pytest-asyncio==1.4.0
    - httpx==0.28.1
    - ruff==0.15.18
  patterns:
    - SQLAlchemy 2.0 DeclarativeBase (not legacy declarative_base())
    - Alembic single-history multi-module autogenerate via central aggregator import
    - pydantic-settings BaseSettings with SecretStr for DB password
    - FastAPI lifespan context manager (not deprecated @app.on_event)
    - Module-as-package layout (backend/app/modules/<suite>/)
    - Module registry Protocol pattern (register/mount_all)
    - pytest-asyncio auto mode with httpx.ASGITransport test client
key_files:
  created:
    - backend/app/__init__.py
    - backend/app/main.py
    - backend/app/core/__init__.py
    - backend/app/core/config.py
    - backend/app/core/base.py
    - backend/app/core/db.py
    - backend/app/core/registry.py
    - backend/app/core/models.py
    - backend/app/core/seed.py
    - backend/app/api/__init__.py
    - backend/app/api/health.py
    - backend/app/modules/__init__.py
    - backend/app/modules/syerp/__init__.py
    - backend/app/modules/syerp/models.py
    - backend/app/modules/syerp/router.py
    - backend/app/modules/syerp/schemas.py
    - backend/app/modules/syerp/service.py
    - backend/alembic.ini
    - backend/alembic/env.py
    - backend/alembic/script.py.mako
    - backend/alembic/versions/0001_initial_baseline.py
    - backend/requirements.txt
    - backend/requirements-dev.txt
    - backend/pyproject.toml
    - backend/.gitignore
    - backend/tests/__init__.py
    - backend/tests/conftest.py
    - backend/tests/test_health.py
    - backend/tests/test_migrations.py
  modified: []
decisions:
  - "Used importlib.import_module('app.modules.syerp') in main.py instead of bare import statement to prevent 'app' package from shadowing 'app' FastAPI instance variable"
  - "SYERP self-registers via sys.modules[__name__] passed to registry.register() — satisfies Module Protocol without requiring a separate module object"
  - "Seed hook is async function (run_seeds) receiving AsyncSession — ready for Phase 2 coroutine callers with no sync/async friction"
  - "pytest conftest injects POSTGRES_PASSWORD env var before app imports so pydantic-settings does not raise ValidationError in CI/sandbox without a .env file"
  - "db_available() probe is session-scoped singleton using psycopg2 sync connect — avoids asyncio complexity in a probe that runs during fixture setup"
metrics:
  duration: "9m"
  completed_date: "2026-06-23"
  tasks_completed: 3
  tasks_total: 3
  files_created: 29
  files_modified: 1
---

# Phase 1 Plan 01: Backend Core Skeleton Summary

**One-liner:** FastAPI backend skeleton with SQLAlchemy 2.0 DeclarativeBase→Alembic single-history wiring, SYERP always-on hub stub, SecretStr config, liveness+readiness health endpoints, and pytest Wave 0 harness (4 pass, 2 skip without DB).

---

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Backend core (config, DB, Base, registry, app factory, health) | f1ca179 | app/core/config.py, app/core/base.py, app/core/db.py, app/core/registry.py, app/api/health.py, app/main.py, requirements.txt |
| 2 | SYERP hub stub + central model aggregator + seed hook + Alembic single history | 8e4b060 | app/modules/syerp/, app/core/models.py, app/core/seed.py, alembic/, alembic.ini |
| 3 | pytest Wave 0 harness | a81e985 | requirements-dev.txt, pyproject.toml, tests/conftest.py, tests/test_health.py, tests/test_migrations.py |

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Python name collision between FastAPI `app` variable and `app` package**

- **Found during:** Task 3 (first pytest run)
- **Issue:** `app/main.py` used `import app.modules.syerp` which binds the name `app` in module scope to the `app` package, shadowing the `app = FastAPI(...)` instance defined earlier. When `mount_all(app)` was called, it received the `app` package object instead of the FastAPI instance, causing `AttributeError: module 'app' has no attribute 'include_router'`.
- **Fix:** Replaced `import app.modules.syerp` with `importlib.import_module("app.modules.syerp")` which triggers the side-effect (SYERP self-registration) without polluting the module namespace with the `app` name.
- **Files modified:** `backend/app/main.py`
- **Commit:** a81e985 (included in Task 3 commit)

---

## Success Criteria Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Backend core skeleton (config/DB/Base/registry/app factory) exists and imports cleanly | PASS | `python -c "from app.main import app"` succeeds with `POSTGRES_PASSWORD=testpassword` |
| SYERP always-on hub stub self-registers (D-06) | PASS | `MODULE_NAME = "syerp"` and `registry.register(sys.modules[__name__])` in `syerp/__init__.py` |
| Module-as-package boundaries clean (D-02, D-05) | PASS | `backend/app/modules/syerp/` has models/router/schemas/service/__init__ |
| Single Alembic history (D-03) wired to central aggregator | PASS | `alembic/env.py` imports `app.core.models` → `target_metadata = Base.metadata` |
| Pitfall 1 (empty autogenerate) avoided | PASS | `app/core/models.py` side-effect-imports `app.modules.syerp.models` before Alembic runs |
| Liveness + readiness health endpoints | PASS | `GET /health/live` (no DB) and `GET /health/ready` (checks DB) in `app/api/health.py` |
| Baseline migration applies cleanly on empty DB (structural check) | PASS | `down_revision = None` verified; live run tested in Plan 03 compose |
| pytest Wave 0 harness green (no live DB required) | PASS | `python -m pytest tests/ -x -q` → 4 passed, 2 skipped |
| SecretStr for DB password (T-01-01) | PASS | `postgres_password: SecretStr` in `Settings`; URL properties call `.get_secret_value()` |
| No hardcoded URL in alembic.ini (T-01-02) | PASS | URL injected in `env.py` via `settings.database_url_sync` |
| Generic DB error in readiness endpoint (T-01-04) | PASS | HTTPException 503 with generic "Database unavailable" detail |
| Seed hook only, no real data (D-10) | PASS | `run_seeds()` is a no-op async function with Phase 2 extension point comment |
| SPA mount deferred to Plan 03 | PASS | Placeholder comment block in `app/main.py`; no StaticFiles mount |

---

## Architecture Decisions Made

1. **importlib over bare import for SYERP registration** — `importlib.import_module("app.modules.syerp")` avoids the Python name-shadowing issue where `import app.modules.syerp` would rebind the local name `app` to the package, hiding the FastAPI instance.

2. **SYERP self-registers as `sys.modules[__name__]`** — The module object itself is the registry entry. The Module Protocol (router + MODULE_NAME attributes) is satisfied by the module's package-level attributes. No separate class or dataclass needed.

3. **Async `run_seeds(db: AsyncSession)` signature** — Accepts an already-opened AsyncSession so callers (lifespan or startup scripts) control the session lifecycle. Phase 2 can pass a session from the async context without friction.

4. **Test conftest sets `POSTGRES_PASSWORD` before imports** — pydantic-settings reads env at `Settings()` instantiation (module-level), so the password must be in `os.environ` before `from app.main import app`. The conftest uses `os.environ.setdefault()` to inject a test-only value without overriding a real `.env`-sourced value.

---

## Threat Mitigations Applied

| Threat ID | Applied | Evidence |
|-----------|---------|----------|
| T-01-01 (SecretStr) | Yes | `postgres_password: SecretStr`; `.get_secret_value()` only in URL properties |
| T-01-02 (No URL in alembic.ini) | Yes | `alembic.ini` has no `sqlalchemy.url = postgresql*`; URL from `settings` in `env.py` |
| T-01-03 (Parameterless SELECT 1) | Yes | `text("SELECT 1")` in readiness — no user input |
| T-01-04 (Generic 503 detail) | Yes | `detail="Database unavailable"` — no credentials or host internals |

---

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| SYERP models.py has no concrete tables | `backend/app/modules/syerp/models.py` | Intentional — SYERP Vendor/Customer/GL tables land in Phase 4 per plan scope |
| SYERP router.py has no routes | `backend/app/modules/syerp/router.py` | Intentional — SYERP API endpoints land in Phase 4 |
| `run_seeds()` is a no-op | `backend/app/core/seed.py` | Intentional per D-10 — Phase 1 scaffolds hook only; real seed data deferred to Phase 2 |
| SPA mount commented out in main.py | `backend/app/main.py` | Intentional — SPA serving wired in Plan 03 (compose/container wiring) |

All stubs are intentional and documented as deferral to later plans/phases. They do not prevent this plan's goal from being achieved.

---

## Self-Check: PASSED

**Files verified:**

- `backend/app/main.py` — exists, parses, imports successfully
- `backend/app/core/config.py` — exists, contains SecretStr
- `backend/app/core/base.py` — exists, contains DeclarativeBase
- `backend/app/core/db.py` — exists, defines get_db
- `backend/app/core/registry.py` — exists, defines register/mount_all
- `backend/app/core/models.py` — exists, contains syerp import
- `backend/app/core/seed.py` — exists, defines run_seeds
- `backend/app/api/health.py` — exists, defines /health/live and /health/ready
- `backend/app/modules/syerp/__init__.py` — exists, contains MODULE_NAME and register(
- `backend/alembic/env.py` — exists, contains target_metadata = Base.metadata
- `backend/alembic/versions/0001_initial_baseline.py` — exists, down_revision = None
- `backend/tests/test_health.py` — exists, defines test_liveness and test_readiness
- `backend/tests/test_migrations.py` — exists, references 0001 and upgrade

**Commits verified:**

- f1ca179 — Task 1: backend core
- 8e4b060 — Task 2: SYERP stub + Alembic
- a81e985 — Task 3: Wave 0 pytest harness

**Test run verified:** `python -m pytest tests/ -x -q` → 4 passed, 2 skipped (exit 0)
