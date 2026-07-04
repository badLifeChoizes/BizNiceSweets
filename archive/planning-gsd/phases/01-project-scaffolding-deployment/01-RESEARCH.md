# Phase 1: Project Scaffolding & Deployment — Research

**Researched:** 2026-06-23
**Domain:** FastAPI + SQLAlchemy 2.0 + Alembic + Vite/React/TypeScript + Podman Compose
**Confidence:** HIGH (verified stack items) / MEDIUM (podman-compose caveats)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Top-level repo gains `backend/`, `frontend/`, `compose/` directories. Existing prototype folders (`plum/`, `flan/`, `docs/`) are untouched.
- **D-02:** Backend uses module-as-package (feature-based) structure: `backend/app/modules/<suite>/` with its own `models.py`, `router.py`, `schemas.py`, `service.py`. Shared concerns in `backend/app/core/`.
- **D-03:** Single Alembic migration history for the whole application (one `alembic/` tree).
- **D-04:** Lightweight module registry + per-module Podman Compose profiles. Subset deployment (e.g., `--profile plum`) over the same PostgreSQL DB.
- **D-05:** Structure must be graduate-able to true plugin distributions later; Phase 1 does NOT build plugin machinery.
- **D-06:** SYERP is the always-on bundled hub, not an optional module. No graceful-degradation code paths.
- **D-07:** Frontend is a Vite + React SPA with React Router (client-side routing) and TanStack Query.
- **D-08:** Production: built static frontend assets served by the backend container (one deployable unit).
- **D-09:** Auto-migrate on startup: wait for Postgres healthy → `alembic upgrade head` → launch uvicorn. Single entrypoint, no separate migration service.
- **D-10:** Real seed data deferred to Phase 2. Phase 1 scaffolds the seed hook/pattern only.
- **D-11:** Both paths provided: containerized hot-reload (canonical/onboarding) + native-run documented escape hatch. Windows 10 file-watching considerations apply.

### Claude's Discretion

- Exact contents of the Phase 1 baseline migration (minimal/empty baseline is acceptable).
- Health-check depth (liveness vs readiness + DB connectivity).
- CI, pre-commit, linter/formatter (ruff, eslint/prettier) setup — may scaffold sensible defaults or defer.
- Config/secrets conventions (`.env` templates, env-var names).
- Naming of the dev compose overlay and exact profile names.

### Deferred Ideas (OUT OF SCOPE)

- True plugin distributions (entry-point machinery)
- Declared-dependency or graceful-degradation module models
- Dedicated one-shot migration service
- Separate nginx/static frontend container
- Real seed data (Phase 2)
- CI / pre-commit / linter-formatter pipeline (discretionary)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CORE-01 | User can run the suite as a containerized deployment via Podman Compose (`podman-compose up`) | Podman 5.8.3 available on host; podman-compose 1.6.0 latest; compose profiles + healthchecks researched |
| CORE-09 | Database schema managed via versioned Alembic migrations that apply cleanly on a fresh deploy | Alembic 1.18.4; SQLAlchemy 2.0.51; single-history multi-module autogenerate pattern confirmed |
</phase_requirements>

---

## Summary

Phase 1 establishes the complete skeleton that every subsequent phase plugs into: a FastAPI backend with module-as-package structure, a single Alembic migration history that autogenerates across all module models, a Vite/React/TypeScript SPA frontend, a multi-stage container image that serves both API and static assets, and a Podman Compose orchestration that reaches a known state from a single command.

The most critical architectural decision to get right is the shared `DeclarativeBase` and `target_metadata` wiring. Every module that ships in future phases must import a model through the centralized `backend/app/core/models.py` (or equivalent all-models import) for autogenerate to see it. If this wiring is wrong, migrations silently miss tables.

The second critical concern is podman-compose `service_healthy` / `depends_on: condition: service_healthy`. This was historically broken; PR #1184 (merged May 2025) fixed it in the main branch for podman-compose 1.4+, but version 1.6.0 is current (PyPI). The fix requires Podman >= 4.6.0 (host has Podman 5.8.3, so this is satisfied). Use `condition: service_healthy` in compose with a `pg_isready` healthcheck on the Postgres service.

**Primary recommendation:** Implement D-09 as a single `entrypoint.sh` shell script that calls `pg_isready` in a loop (belt-and-suspenders alongside compose healthcheck), then runs `alembic upgrade head`, then `exec uvicorn`. This makes the migration step robust even if compose healthcheck logic has edge cases.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HTTP API routing and business logic | Backend (FastAPI) | — | All app logic is server-side; no BFF needed |
| Database schema and migrations | Database (PostgreSQL + Alembic) | Backend (runs migrations) | Alembic runs in backend container at startup |
| SPA serving (production) | Backend (StaticFiles) | — | D-08: one deployable unit, no separate static server |
| SPA serving (development) | Frontend (Vite dev server) | — | D-11: hot-reload via Vite HMR in dev compose |
| Config / secrets | Backend (pydantic-settings) | Compose env_file | `.env` loaded by pydantic-settings from env vars |
| Container orchestration | Podman Compose | — | D-04: profiles for module subsets |
| Module registration | Backend (module registry, `core/`) | — | Centralized APIRouter composition in `core/` |

---

## Standard Stack

### Core Backend

| Library | Version (verified) | Purpose | Why Standard |
|---------|--------------------|---------|--------------|
| FastAPI | 0.138.0 | Web framework, OpenAPI auto-docs | Project-locked; async-first, typed |
| SQLAlchemy | 2.0.51 | ORM and core SQL toolkit | Project-locked; 2.0 typing API |
| Alembic | 1.18.4 | DB migrations | Project-locked; SQLAlchemy-native |
| pydantic-settings | 2.14.2 | Config from env vars / `.env` | Standard FastAPI config pattern |
| uvicorn | 0.49.0 | ASGI server | Standard FastAPI production server |
| asyncpg | 0.31.0 | Async PostgreSQL driver | Pairs with SQLAlchemy async engine |
| psycopg2-binary | 2.9.12 | Sync PostgreSQL driver (Alembic migrations) | Alembic CLI uses sync by default |
| python-multipart | 0.0.32 | Form data support (required by FastAPI) | Needed for future auth forms |

### Core Frontend

| Library | Version (verified) | Purpose | Why Standard |
|---------|--------------------|---------|--------------|
| vite | 8.1.0 | Build tool + dev server | Project-locked; fastest HMR |
| react | 19.2.7 | UI framework | Project-locked |
| react-dom | 19.2.7 | React DOM renderer | Paired with react |
| typescript | 6.0.3 | Type system | Project-locked |
| tailwindcss | 4.3.1 | Utility-first CSS | Project-locked; v4 is current default |
| @tailwindcss/vite | 4.3.1 | Vite plugin for Tailwind v4 | Replaces PostCSS config in v4 |
| shadcn (CLI) | 4.11.0 | Component scaffolding CLI | Project-locked; `npx shadcn@latest` |
| react-router-dom | 7.18.0 | Client-side routing | Project-locked |
| @tanstack/react-query | 5.101.1 | Server state management | Project-locked |
| @vitejs/plugin-react | 6.0.3 | React Fast Refresh for Vite | Standard Vite + React pairing |
| lucide-react | 1.21.0 | Icon library used by shadcn/ui | shadcn/ui dependency |

### Supporting Dev Tools (Backend)

| Library | Version (verified) | Purpose | When to Use |
|---------|--------------------|---------|-------------|
| pytest | 9.1.1 | Test framework | Phase 1 test harness |
| pytest-asyncio | 1.4.0 | Async test support | For async route/service tests |
| httpx | 0.28.1 | HTTP client for tests | FastAPI TestClient uses it |
| ruff | 0.15.18 | Linter + formatter (replaces black+flake8) | Claude's discretion — scaffold |
| anyio | 4.14.0 | Async I/O primitives | SQLAlchemy async dependency |

### Supporting Dev Tools (Frontend)

| Library | Version (verified) | Purpose | When to Use |
|---------|--------------------|---------|-------------|
| eslint | 10.5.0 | Linting | Claude's discretion — scaffold |
| prettier | 3.8.4 | Formatting | Claude's discretion — scaffold |
| typescript-eslint | 8.62.0 | TypeScript ESLint rules | Paired with eslint |
| @types/react | 19.2.17 | React type defs | Required for TypeScript |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncpg (async driver) | psycopg3 (asyncpg alternative) | asyncpg is more mature for SQLAlchemy 2.0; psycopg3 works too |
| ruff | black + flake8 + isort | ruff replaces all three; simpler config |
| Tailwind v4 + @tailwindcss/vite | Tailwind v3 + PostCSS | v4 is current default with shadcn; no tailwind.config.js needed |

**Installation (backend):**
```bash
pip install fastapi==0.138.0 sqlalchemy==2.0.51 alembic==1.18.4 pydantic-settings==2.14.2 \
  uvicorn[standard]==0.49.0 asyncpg==0.31.0 psycopg2-binary==2.9.12 \
  python-multipart==0.0.32 anyio==4.14.0

pip install --dev pytest==9.1.1 pytest-asyncio==1.4.0 httpx==0.28.1 ruff==0.15.18
```

**Installation (frontend):**
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install tailwindcss @tailwindcss/vite
npm install react-router-dom @tanstack/react-query lucide-react
npx shadcn@latest init
# (adds components as needed: npx shadcn@latest add button card ...)
```

**Version verification:** All versions above verified against PyPI registry and npm registry on 2026-06-23.

---

## Architecture Patterns

### System Architecture Diagram

```
┌───────────────────────────────────────────────────────┐
│  Developer / Browser                                  │
└───────┬────────────────────────┬──────────────────────┘
        │ HTTP :8000              │ HMR :5173 (dev only)
        ▼                        ▼
┌───────────────────┐   ┌────────────────────┐
│  Backend Container │   │  Frontend Container │
│  (FastAPI/uvicorn) │   │  (Vite dev server)  │
│                   │   │  Dev compose only   │
│  /api/*  → routers │   │  Volume-mounted src │
│  /*      → SPA    │   └────────────────────┘
│  (StaticFiles)    │     (prod: dist/ built
│                   │      into backend image)
│  lifespan startup:│
│  alembic upgrade  │
│  head             │
└───────┬───────────┘
        │ asyncpg (async ORM)
        ▼
┌───────────────────┐
│  PostgreSQL 17    │
│  (DB container)   │
│  healthcheck:     │
│  pg_isready       │
└───────────────────┘

Module registry (core/):
  app.include_router(module.router, prefix="/api/v1")
  ↑ called at startup for each registered module

Compose profiles:
  (default / no profile) → postgres + backend + frontend-dev
  --profile plum         → adds PLUM-specific services if any
  --profile full         → all optional modules
  SYERP: always-on (no profile guard)
```

### Recommended Project Structure

```
BizNiceSweets/                   # repo root
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app factory, lifespan
│   │   ├── core/
│   │   │   ├── config.py        # pydantic-settings Settings class
│   │   │   ├── db.py            # engine, SessionLocal, get_db dep
│   │   │   ├── base.py          # shared DeclarativeBase
│   │   │   ├── models.py        # imports ALL module models (autogenerate)
│   │   │   └── registry.py      # module registration helpers
│   │   └── modules/
│   │       └── syerp/           # always-on hub (Phase 4 builds this)
│   │           ├── __init__.py
│   │           ├── models.py
│   │           ├── router.py
│   │           ├── schemas.py
│   │           └── service.py
│   ├── alembic/
│   │   ├── env.py               # target_metadata = Base.metadata
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0001_initial_baseline.py
│   ├── alembic.ini
│   ├── pyproject.toml           # deps + ruff config
│   ├── Dockerfile               # multi-stage: build-frontend → runtime
│   └── entrypoint.sh            # wait-for-db → alembic → uvicorn
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   └── lib/utils.ts         # shadcn/ui utility
│   ├── index.html
│   ├── vite.config.ts           # base: '/', @/ alias
│   ├── tsconfig.json
│   ├── tsconfig.app.json
│   └── package.json
├── compose/
│   ├── compose.yml              # production compose
│   └── compose.dev.yml          # dev overlay (volume mounts, HMR)
├── .env.example                 # env-var template for operators
├── plum/                        # prototype (untouched)
├── flan/                        # prototype (untouched)
└── docs/
```

### Pattern 1: SQLAlchemy 2.0 DeclarativeBase (Annotated Style)

**What:** All module models inherit from one shared `Base` class. Alembic's `env.py` uses `Base.metadata` as `target_metadata`.

**When to use:** Always — this is the single entry point for autogenerate.

```python
# backend/app/core/base.py
# Source: https://docs.sqlalchemy.org/en/20/orm/mapping_styles.html
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass
```

```python
# backend/app/core/models.py
# Import ALL module model files here so metadata is populated.
# Alembic env.py imports this module before autogenerate runs.
from app.modules.syerp import models as syerp_models  # noqa: F401
# Phase 4+: from app.modules.plum import models as plum_models  # noqa: F401
```

```python
# backend/app/modules/syerp/models.py
from app.core.base import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

class Vendor(Base):
    __tablename__ = "syerp_vendor"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
```

### Pattern 2: Alembic env.py — Single History, Multi-Module Autogenerate

**What:** `env.py` imports the shared `Base.metadata` so autogenerate discovers every module's tables.

**When to use:** Phase 1 wiring; stays unchanged as modules are added.

```python
# backend/alembic/env.py
# Source: https://alembic.sqlalchemy.org/en/latest/autogenerate.html
from alembic import context
from sqlalchemy import engine_from_config, pool

# CRITICAL: import all models via the aggregator module
import app.core.models  # noqa: F401 — side-effect: populates Base.metadata
from app.core.base import Base
from app.core.config import settings

target_metadata = Base.metadata

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
```

**Note on async vs sync Alembic:** The Alembic CLI (`alembic upgrade head`) is synchronous. For Phase 1, use a sync engine in `env.py` even if the app uses an async engine. The async pattern (`async_engine_from_config` + `asyncio.run`) is available but adds complexity that is not needed for the CLI invocation in the entrypoint script. [VERIFIED: alembic.sqlalchemy.org]

### Pattern 3: Module Registry

**What:** A lightweight registration function in `core/` that each module's `__init__.py` calls; `main.py` iterates registered modules to mount routers.

**When to use:** Phase 1 (SYERP stub); extended in Phases 4–6 as modules land.

```python
# backend/app/core/registry.py
from fastapi import FastAPI
from typing import Protocol

class Module(Protocol):
    router: object  # APIRouter
    MODULE_NAME: str

_registry: list[Module] = []

def register(module: Module) -> None:
    _registry.append(module)

def mount_all(app: FastAPI, prefix: str = "/api/v1") -> None:
    for mod in _registry:
        app.include_router(mod.router, prefix=prefix, tags=[mod.MODULE_NAME])
```

```python
# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.core.registry import mount_all
import app.modules.syerp  # registers itself via register()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions (after migrations have already run via entrypoint.sh)
    yield
    # Shutdown cleanup

app = FastAPI(title="BizNiceSweets", lifespan=lifespan)
mount_all(app)
# SPA fallback (production): mounted after API routes
```

### Pattern 4: SPA Fallback (FastAPI serves React)

**What:** A custom `SPAStaticFiles` class that catches 404 from StaticFiles and returns `index.html`, letting React Router handle client-side routes.

**When to use:** Production container; `frontend/dist/` is copied into image by multi-stage build.

```python
# backend/app/main.py (production SPA serving)
# Source: https://davidmuraya.com/blog/serving-a-react-frontend-application-with-fastapi/
import os
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except (HTTPException, StarletteHTTPException) as ex:
            if ex.status_code == 404:
                return await super().get_response("index.html", scope)
            raise

# Mount AFTER all /api routes
STATIC_DIR = os.getenv("STATIC_DIR", "frontend/dist")
if os.path.isdir(STATIC_DIR):
    app.mount("/", SPAStaticFiles(directory=STATIC_DIR, html=True), name="spa")
```

**Vite base path:** Set `base: "/"` in `vite.config.ts` (default). The SPA is served at `/`; API lives at `/api/v1/`. No sub-path conflict because API routes are mounted first.

### Pattern 5: Entrypoint Script (D-09)

**What:** Shell script run as the container `CMD` that sequences: wait-for-db → migrate → serve.

**When to use:** Production and dev containers using the backend image.

```bash
#!/usr/bin/env sh
# backend/entrypoint.sh
set -e

echo "Waiting for PostgreSQL..."
until pg_isready -h "${POSTGRES_HOST:-db}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER:-app}"; do
  sleep 1
done
echo "PostgreSQL is ready."

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Why belt-and-suspenders (pg_isready in script AND compose healthcheck):** Compose `depends_on: condition: service_healthy` has had reliability issues in podman-compose (fixed in 1.4+, but edge cases remain). The script loop ensures the backend will not proceed even if compose's healthcheck gate fires prematurely. [VERIFIED: github.com/containers/podman-compose PR #1184 merged May 2025]

### Pattern 6: pydantic-settings Config

**What:** Single `Settings` class reads from env vars (and `.env` file in dev).

```python
# backend/app/core/config.py
# Source: https://github.com/pydantic/pydantic-settings (Context7)
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "biznice"
    postgres_user: str = "app"
    postgres_password: str

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        # For Alembic env.py (sync psycopg2)
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

settings = Settings()
```

### Pattern 7: Dockerfile (Multi-Stage)

**What:** Stage 1 builds the React SPA; Stage 2 is the Python runtime that copies the built assets.

```dockerfile
# backend/Dockerfile
# Stage 1: Build React frontend
FROM node:22-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci --omit=dev
COPY frontend/ ./
RUN npm run build
# output: /frontend/dist/

# Stage 2: Python runtime
FROM python:3.13-slim AS runtime
WORKDIR /app

# Install pg_isready (for entrypoint wait-for-db)
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=frontend-builder /frontend/dist ./frontend/dist

COPY backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
CMD ["/entrypoint.sh"]
```

**Note:** Official FastAPI docs recommend building from `python:3.x` rather than from `tiangolo/uvicorn-gunicorn-fastapi` (deprecated). [VERIFIED: fastapi.tiangolo.com/deployment/docker/]

### Pattern 8: Compose Files

**What:** `compose/compose.yml` (production) + `compose/compose.dev.yml` (dev overlay).

```yaml
# compose/compose.yml
services:
  db:
    image: postgres:17-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-biznice}
      POSTGRES_USER: ${POSTGRES_USER:-app}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-app} -d ${POSTGRES_DB:-biznice}"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s

  api:
    build:
      context: ..
      dockerfile: backend/Dockerfile
    env_file: ../.env
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    environment:
      POSTGRES_HOST: db

volumes:
  pgdata:
```

```yaml
# compose/compose.dev.yml  (overlay: podman-compose -f compose.yml -f compose.dev.yml up)
services:
  api:
    build:
      target: runtime          # skip frontend-builder stage in dev
    volumes:
      - ../backend:/app:z      # :z = SELinux relabeling for rootless Podman
    command: ["/entrypoint.sh"]
    environment:
      UVICORN_RELOAD: "true"  # uvicorn --reload via env or override CMD

  frontend:
    image: node:22-slim
    working_dir: /frontend
    volumes:
      - ../frontend:/frontend:z
    ports:
      - "5173:5173"
    command: sh -c "npm install && npm run dev -- --host"
    environment:
      VITE_API_BASE_URL: "http://localhost:8000"
```

### Anti-Patterns to Avoid

- **`depends_on` without `condition: service_healthy`:** Without the condition, Compose starts the API container the moment Postgres container starts, not when Postgres is ready to accept connections. Always pair with a healthcheck.
- **Importing models lazily inside migration functions:** Alembic's autogenerate scans `target_metadata` at invocation. If models aren't imported before `run_migrations_*` is called, tables will appear missing and generate spurious DROP statements.
- **`declarative_base()` (old API) instead of `class Base(DeclarativeBase): pass`:** The old `declarative_base()` function is SQLAlchemy 1.x style. SQLAlchemy 2.0 uses `DeclarativeBase`; using the old form loses type-safety and `Mapped` annotation support. [VERIFIED: docs.sqlalchemy.org/en/20/]
- **Single alembic.ini `sqlalchemy.url` hardcoded:** Hardcoding the DB URL in `alembic.ini` blocks operator config. Override in `env.py` via `config.set_main_option("sqlalchemy.url", settings.database_url_sync)`.
- **Mounting `/` StaticFiles before API routes:** If the SPA mount comes before API route registration, it will swallow `/api/*` requests. Always mount the SPA last.
- **Vite `base` set to a non-root path without coordinating backend:** If `vite.config.ts` has `base: "/app/"` but FastAPI serves from `/`, asset paths break. Keep `base: "/"`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DB URL validation/parsing | Custom URL builder | `pydantic.PostgresDsn` or property on Settings | Validates scheme, handles edge cases |
| Wait-for-DB polling | Custom TCP ping loop | `pg_isready` (from `postgresql-client`) | `pg_isready` checks actual PostgreSQL readiness, not just TCP port open |
| Migration version tracking | Custom migration table | Alembic's `alembic_version` table | Alembic manages migration state; roll-your-own breaks tooling |
| SPA fallback routing | `@app.get("/{path:path}")` catch-all overriding API | `SPAStaticFiles` subclass | A bare catch-all conflicts with API routes and needs careful ordering |
| Config secrets storage | Env vars hardcoded in Dockerfile | `.env` file + `env_file:` in compose | Secrets must not be in images; operator supplies `.env` at deploy time |
| Multi-module metadata aggregation | Per-module `target_metadata` lists | Single `Base.metadata` from shared `DeclarativeBase` | Alembic supports `[meta1, meta2]` but one shared Base is simpler and avoids key collision errors |

**Key insight:** The migration infrastructure is the most brittle part of a modular monolith bootstrap. Getting the metadata import chain correct in `env.py` is more important than any single library choice.

---

## Common Pitfalls

### Pitfall 1: Autogenerate Sees No Tables (Empty Migration)

**What goes wrong:** Running `alembic revision --autogenerate` produces a migration with no `op.create_table` calls, even though models exist.

**Why it happens:** `env.py` doesn't import the model modules before autogenerate runs. SQLAlchemy only adds tables to `Base.metadata` when the model class is actually imported, not when the file exists on disk.

**How to avoid:** Ensure `app/core/models.py` imports every module's `models.py` with a side-effect import (`import app.modules.syerp.models  # noqa: F401`), and that `env.py` imports `app.core.models` before calling `context.configure`.

**Warning signs:** Generated migration file has only a `def upgrade()` and `def downgrade()` with `pass` bodies.

### Pitfall 2: podman-compose `service_healthy` Race Condition

**What goes wrong:** The API container starts before PostgreSQL is ready, migrations fail, container exits or loops.

**Why it happens:** Older podman-compose versions (pre-1.4) did not properly enforce `condition: service_healthy`. Even post-fix, there can be timing edge cases.

**How to avoid:** Two-layer defense: (1) compose healthcheck with `pg_isready` on the Postgres service, (2) `pg_isready` polling loop in `entrypoint.sh`. The entrypoint loop is the final safety net.

**Warning signs:** API container logs show `psycopg2.OperationalError: could not connect to server` before exiting, even though Postgres container shows as running.

### Pitfall 3: Windows 10 Volume Mount File Watching

**What goes wrong:** Uvicorn `--reload` or Vite HMR doesn't detect file changes when source is mounted from a Windows host path via Podman machine (WSL2 bridge).

**Why it happens:** Windows filesystem events don't propagate through WSL2 to inotify inside the container. Watchfiles (uvicorn's watcher) and Vite's watcher both rely on inotify by default.

**How to avoid:**
- For uvicorn: set `WATCHFILES_FORCE_POLLING=true` in the dev container environment.
- For Vite: set `server.watch.usePolling: true` in `vite.config.ts` dev config.
- Document the native-run escape hatch: run uvicorn and Vite directly on the host with a native Python venv and Node install, pointing at a Postgres container only. This avoids volume mount overhead entirely.

**Warning signs:** Code changes don't trigger reload; manual container restart required.

### Pitfall 4: podman-compose Profile Gaps

**What goes wrong:** Services without a `profiles:` key are started regardless of `--profile` flag; services WITH a profile are skipped unless that profile is explicitly activated.

**Why it happens:** Compose spec behavior: profileless services are "default" services always started. Profile-tagged services require explicit activation.

**How to avoid:**
- `db` and `api` (SYERP-bundled) have NO `profiles:` key — they always start.
- Optional modules get a profile tag (`profiles: [plum]`). Operators run `podman-compose --profile plum up` to add PLUM.
- Test the "no-profile" case to verify SYERP comes up cleanly without any `--profile` flag.

**Warning signs:** `podman-compose up` (no flags) tries to start optional module containers that aren't ready yet.

### Pitfall 5: Tailwind v4 vs v3 shadcn/ui Mismatch

**What goes wrong:** Running `npx shadcn@latest init` on a project with Tailwind v3 (PostCSS config) against a v4 shadcn release causes config incompatibilities.

**Why it happens:** shadcn/ui moved to Tailwind v4 as the default for new projects. v4 has no `tailwind.config.js`; configuration moves to the main CSS file.

**How to avoid:** Use the v4 stack throughout. Install `tailwindcss@latest` (currently 4.3.1) + `@tailwindcss/vite` (the Vite plugin replaces PostCSS). The CSS entry point becomes `@import "tailwindcss";` instead of `@tailwind base/components/utilities` directives. [VERIFIED: ui.shadcn.com/docs/installation/vite]

### Pitfall 6: `python:3.13-slim` Missing pg_isready

**What goes wrong:** Entrypoint script fails because `pg_isready` is not installed in the Python slim image.

**Why it happens:** `python:3.13-slim` is a minimal Debian image without PostgreSQL client tools.

**How to avoid:** Install `postgresql-client` in the Dockerfile's runtime stage (`apt-get install -y --no-install-recommends postgresql-client`). This is a small package that provides `pg_isready`.

---

## Code Examples

### Health Check Endpoint (Liveness + Readiness)

```python
# backend/app/api/health.py
# Source: Research synthesis — liveness vs readiness best practice
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.db import get_db

router = APIRouter(tags=["health"])

@router.get("/health/live")
async def liveness():
    """Liveness: Is the process alive? No external I/O."""
    return {"status": "ok"}

@router.get("/health/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    """Readiness: Can the process serve traffic? Checks DB connection."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")
```

**Rationale:** Two separate endpoints. The liveness check never touches the DB — a DB outage should drop from load balancer (readiness), not trigger a restart loop (liveness). [CITED: medium.com/@jtc.21.am/readiness-vs-liveness]

### Alembic Initial Baseline Migration

```python
# backend/alembic/versions/0001_initial_baseline.py
"""Initial baseline

Revision ID: 0001
Create Date: 2026-06-23
"""
from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Phase 1: empty baseline — tables created in Phase 4+ by module migrations
    pass

def downgrade() -> None:
    pass
```

### Vite Config with Polling (Windows-safe dev)

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    host: true,        // expose on all interfaces (for container)
    port: 5173,
    watch: {
      // Enable polling for Windows/WSL2 volume mounts
      usePolling: !!process.env.VITE_USE_POLLING,
    },
    proxy: {
      '/api': 'http://api:8000',  // proxy API calls to backend in dev compose
    },
  },
  base: '/',
})
```

### SQLAlchemy Async Session Factory

```python
# backend/app/core/db.py
# Source: SQLAlchemy 2.0 docs (Context7)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

### .env.example Template

```ini
# .env.example — copy to .env and fill in secrets
# Operator: never commit .env to git

POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=biznice
POSTGRES_USER=app
POSTGRES_PASSWORD=changeme_in_production
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `declarative_base()` function | `class Base(DeclarativeBase): pass` | SQLAlchemy 2.0 (2023) | Enables `Mapped[]` type annotations, full typing support |
| `@app.on_event("startup")` decorator | `lifespan` async context manager | FastAPI 0.93+ (2023) | `on_event` deprecated; lifespan is canonical |
| `tiangolo/uvicorn-gunicorn-fastapi` base image | `python:3.x` + `uvicorn` directly | FastAPI docs update 2024 | Old base image deprecated; build from scratch |
| `tailwind.config.js` + `@tailwind` directives | CSS `@import "tailwindcss"` + `@tailwindcss/vite` plugin | Tailwind v4 (early 2025) | No tailwind config file; Vite plugin replaces PostCSS |
| `npx create-react-app` | `npm create vite@latest -- --template react-ts` | ~2022-2023 | CRA deprecated; Vite is the standard scaffold |
| `black` + `flake8` + `isort` | `ruff` (all three in one) | ~2023-2024 | Ruff is 10-100x faster; single tool |
| shadcn `tailwindcss-animate` | `tw-animate-css` | shadcn Tailwind v4 update 2025 | Old package deprecated in v4 config |

**Deprecated/outdated:**
- `@app.on_event("startup")`: Deprecated in FastAPI; use `lifespan`.
- `declarative_base()` function: Still works but is the 1.x API; prefer `DeclarativeBase` class.
- `tiangolo/uvicorn-gunicorn-fastapi` Docker image: Explicitly deprecated by FastAPI docs.
- Tailwind CSS v3 `@tailwind base/components/utilities` directives: Do not use with v4.

---

## Runtime State Inventory

> Phase 1 is greenfield. There is no existing runtime state to migrate. This section is included to confirm the check was performed.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no target-stack DB exists | None |
| Live service config | None — no running containerized services | None |
| OS-registered state | None — no tasks/services registered for new stack | None |
| Secrets/env vars | None — `.env` file does not yet exist | Create `.env.example` template |
| Build artifacts | None — no prior builds | None |

**Nothing found in category:** All confirmed empty — verified by examining repo state (only HTML prototype files exist; no `backend/`, `frontend/`, or `compose/` directories).

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Podman | Container runtime for all services | ✓ | 5.8.3 | Use Docker (Docker 28.1.1 also available) |
| podman-compose | Compose orchestration (CORE-01) | ✗ | — | Install via pip: `pip install podman-compose==1.6.0` |
| Docker | Alternative container runtime | ✓ | 28.1.1 | — |
| Node.js | Frontend build + Vite dev server | ✓ | v22.13.1 | — |
| npm | Frontend package management | ✓ | 10.9.2 | — |
| Python 3 | Backend runtime | ✓ | 3.13 (pip) | — |
| pip3 | Python package management | ✓ | 25.2 | — |
| PostgreSQL (client) | `pg_isready` in entrypoint | ✗ | — | Install inside Dockerfile via `postgresql-client` |
| PostgreSQL (server) | Database service | ✗ (as native) | — | Run as container (postgres:17-alpine) |
| FastAPI / SQLAlchemy / etc. | Backend runtime | ✗ (not yet installed) | — | `pip install` from requirements.txt |

**Missing dependencies with no fallback:**
- `podman-compose` must be installed (`pip install podman-compose`) for CORE-01. Alternatively the project can use `docker compose` (v2 plugin, already installed via Docker Desktop) for development, with `podman-compose` documented as the target self-hosted tool.

**Missing dependencies with fallback:**
- `postgresql-client` (for `pg_isready`) — installed inside the Docker/Podman image, not on the host.
- PostgreSQL server — runs as a container; no native install needed.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `pytest backend/tests/test_health.py -x` |
| Full suite command | `pytest backend/tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CORE-01 | `podman-compose up` starts all services without manual steps | Smoke (manual + scripted) | `podman-compose up -d && sleep 5 && curl -f http://localhost:8000/health/live` | ❌ Wave 0 |
| CORE-01 | OpenAPI docs reachable at `/docs` | Smoke | `curl -f http://localhost:8000/docs` | ❌ Wave 0 |
| CORE-09 | Alembic migrations apply on fresh DB | Integration | `pytest backend/tests/test_migrations.py -x` | ❌ Wave 0 |
| CORE-09 | `/health/ready` returns 200 with DB connected | Integration | `pytest backend/tests/test_health.py::test_readiness -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest backend/tests/test_health.py -x`
- **Per wave merge:** `pytest backend/tests/ -x`
- **Phase gate:** All 4 test commands green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/__init__.py` — test package
- [ ] `backend/tests/conftest.py` — async test client, DB session fixtures
- [ ] `backend/tests/test_health.py` — covers liveness + readiness (REQ CORE-01, CORE-09)
- [ ] `backend/tests/test_migrations.py` — verifies `alembic upgrade head` runs clean on empty DB
- [ ] `backend/pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`
- [ ] Framework install: included in `requirements-dev.txt` (`pytest`, `pytest-asyncio`, `httpx`)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No (Phase 2) | — |
| V3 Session Management | No (Phase 2) | — |
| V4 Access Control | No (Phase 2) | — |
| V5 Input Validation | Partial | pydantic-settings validates config at startup; FastAPI validates path/query params via Pydantic |
| V6 Cryptography | No | No secrets processed in Phase 1 |
| V9 Communications | Yes (partial) | `POSTGRES_PASSWORD` must come from env var, not hardcoded in image — enforced by `.env.example` pattern |
| V14 Configuration | Yes | No default passwords in images; operator-supplied `.env`; no secrets in `alembic.ini` |

### Known Threat Patterns for Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| DB credentials leaked in image | Information Disclosure | Never bake credentials into Dockerfile; use `env_file:` in compose + `.env` gitignored |
| SQL injection via raw queries | Tampering | SQLAlchemy ORM + parameterized queries; avoid `text()` with user input |
| Migration run by multiple replicas | Denial of Service (lock contention) | Single-instance self-hosted deployment; document this constraint for Phase 5+ if scaling |
| Sensitive data in logs | Information Disclosure | Do not log `settings.postgres_password`; pydantic-settings fields are NOT automatically redacted — use `SecretStr` for password field |

**Phase 1 security action:** Use `pydantic.SecretStr` for `postgres_password` in `Settings` to prevent it from appearing in repr/logs.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Python 3.13 is compatible with all listed packages (FastAPI, SQLAlchemy, asyncpg, etc.) | Standard Stack | Some packages may not have Python 3.13 wheels; install may fail. Mitigation: test early; fall back to Python 3.12 if needed. |
| A2 | Podman 5.8.3 on Windows uses WSL2 machine; `service_healthy` fix in podman-compose 1.4+ applies | Pitfall 2 | If host Podman uses a different machine type, healthcheck behavior may differ |
| A3 | `docker compose` (v2 plugin) can be used interchangeably for development on this Windows 10 host | Environment Availability | Docker Compose v2 spec is largely compatible but there are minor differences (e.g., profile flag syntax) |

---

## Open Questions

1. **Sync vs Async Alembic in entrypoint**
   - What we know: Alembic CLI (`alembic upgrade head`) is synchronous. The `env.py` can use a sync psycopg2 URL even if the app uses asyncpg.
   - What's unclear: Whether the team wants a single `asyncpg` driver or both `asyncpg` (app) + `psycopg2-binary` (migrations). Two drivers is small overhead.
   - Recommendation: Use both. `asyncpg` for the app (better performance), `psycopg2-binary` for Alembic CLI only. This is the standard production pattern.

2. **Module profile naming convention**
   - What we know: D-04 says `--profile plum` for PLUM standalone; `--profile full` for everything.
   - What's unclear: Whether FLAN, MOUSSE, etc. each get their own profile or a composite `--profile all-modules`.
   - Recommendation: One profile per optional module (`plum`, `flan`, `mousse`, `crumb`, `gelato`, `crisp`) plus `--profile full` activates all. Document in compose file comments.

3. **`uvicorn --reload` in dev compose vs native**
   - What we know: `WATCHFILES_FORCE_POLLING=true` is required for Windows volume mounts.
   - What's unclear: Performance impact of polling on a large codebase.
   - Recommendation: Default to polling enabled in dev compose; document native-run path as the recommended option for active Python development on Windows.

---

## Sources

### Primary (HIGH confidence)

- `/websites/alembic_sqlalchemy` (Context7) — autogenerate target_metadata, multi-module metadata, env.py patterns
- `/websites/sqlalchemy_en_20_orm` (Context7) — DeclarativeBase, Mapped, mapped_column
- `/websites/fastapi_tiangolo` (Context7) — StaticFiles, lifespan, include_router
- `/pydantic/pydantic-settings` (Context7) — BaseSettings, model_config, env_file
- `/vitejs/vite` (Context7) — server.watch.usePolling, HMR
- PyPI registry — fastapi 0.138.0, sqlalchemy 2.0.51, alembic 1.18.4, pydantic-settings 2.14.2, uvicorn 0.49.0, asyncpg 0.31.0, ruff 0.15.18 (all verified 2026-06-23)
- npm registry — vite 8.1.0, react 19.2.7, react-router-dom 7.18.0, @tanstack/react-query 5.101.1, tailwindcss 4.3.1, shadcn 4.11.0 (all verified 2026-06-23)
- fastapi.tiangolo.com/deployment/docker/ — official Dockerfile pattern, deprecation of uvicorn-gunicorn base image
- ui.shadcn.com/docs/installation/vite — Tailwind v4 + shadcn init steps

### Secondary (MEDIUM confidence)

- github.com/containers/podman-compose PR #1184 (merged May 2025) — service_healthy fix in podman-compose 1.4+
- PyPI podman-compose 1.6.0 (released June 2026) — latest version confirmed
- davidmuraya.com/blog/serving-a-react-frontend-application-with-fastapi/ — SPAStaticFiles subclass pattern
- github.com/arctikant/fastapi-modular-monolith-starter-kit — central models.py import pattern for Alembic discovery
- medium.com/@jtc.21.am/readiness-vs-liveness — liveness vs readiness endpoint design

### Tertiary (LOW confidence)

- github.com/containers/podman-compose/issues/938 — Windows volume mount path issues (open issue; mitigations are workarounds)

---

## Metadata

**Confidence breakdown:**
- Standard stack versions: HIGH — verified against PyPI and npm registries on 2026-06-23
- Architecture patterns: HIGH — verified against Context7 docs (FastAPI, SQLAlchemy, Alembic, pydantic-settings)
- Podman-compose healthcheck/profiles: MEDIUM — fix is merged but not all edge cases confirmed on Windows 10
- Windows file-watching mitigations: MEDIUM — WATCHFILES_FORCE_POLLING documented in community sources, not official FastAPI/uvicorn docs

**Research date:** 2026-06-23
**Valid until:** 2026-09-23 (stable ecosystem; 90 days reasonable; Vite major versions may bump sooner)
