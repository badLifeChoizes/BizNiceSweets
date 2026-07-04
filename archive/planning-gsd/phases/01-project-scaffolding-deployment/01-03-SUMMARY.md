---
phase: 01-project-scaffolding-deployment
plan: 03
subsystem: infra
tags: [podman, podman-compose, docker, containerfile, alembic, fastapi, vite, postgres, spa, entrypoint]

requires:
  - phase: 01-01
    provides: FastAPI app, app.core config/db/models, /health routes, Alembic single history
  - phase: 01-02
    provides: Vite + React SPA, health-check landing page, /api dev proxy
provides:
  - Multi-stage Containerfile (frontend build -> python runtime serving API + static SPA)
  - entrypoint.sh auto-migrate (wait-for-db -> alembic upgrade head -> uvicorn)
  - Production compose (db + api, db not host-published, healthcheck-gated)
  - Dev compose overlay (source mounts, uvicorn --reload, Vite HMR, Windows polling)
  - Per-module compose profiles (plum..crisp, full) with SYERP/db/api always-on
  - .env.example operator template + root .dockerignore; deployment docs
affects: [all later phases that deploy modules, MOUSSE, GELATO, CRISP, any phase adding module containers]

tech-stack:
  added: [podman-compose==1.6.0, postgres:17-alpine, python:3.13-slim, node:22-slim, postgresql-client]
  patterns: [multi-stage container build, auto-migrate entrypoint, backend-serves-SPA fallback, per-module compose profiles, env_file secrets]

key-files:
  created: [Containerfile, backend/entrypoint.sh, backend/.dockerignore->.dockerignore, compose/compose.yml, compose/compose.dev.yml, .env.example, docs/deployment/local-dev.md]
  modified: [backend/app/main.py, backend/alembic.ini, frontend/src/routes/Landing.tsx, frontend/vite.config.ts, .gitignore]

key-decisions:
  - "Build file is a root-level Containerfile (Podman-native; auto-discovered even when podman-compose drops -f on Windows)"
  - "Health probes served at /health/* (root), business APIs under /api/v1/*; frontend and dev proxy aligned to that contract"
  - "Alembic prepend_sys_path = . so migrations import the app package in-container and locally"

patterns-established:
  - "Auto-migrate on startup: entrypoint waits for DB readiness, runs alembic upgrade head, then execs uvicorn"
  - "Backend serves built SPA via SPAStaticFiles mounted last; API/health routes registered first"
  - "Per-module Compose profiles over one shared Postgres; SYERP/db/api have no profile guard (always-on)"

requirements-completed: [CORE-01, CORE-09]

duration: ~90min (incl. operator smoke verification + 4 integration fixes)
completed: 2026-06-23
---

# Phase 01-03: Containerization & Orchestration Summary

**Single-command `podman-compose up` brings up Postgres + a FastAPI/uvicorn container that auto-migrates on startup and serves the built React SPA, API, and /docs from one origin — verified live on Windows + Podman 5.8.3.**

## Performance

- **Duration:** ~90 min (Tasks 1–2 autonomous; Task 3 operator-verified with 4 integration fixes)
- **Tasks:** 3 (2 auto + 1 human-verify checkpoint, approved)
- **Files modified:** 11

## Accomplishments
- Multi-stage `Containerfile`: `node:22-slim` builds the SPA → `python:3.13-slim` runtime serves API + static SPA; non-root `appuser`; `postgresql-client` for `pg_isready`.
- `backend/entrypoint.sh`: wait-for-DB (pg_isready loop) → `alembic upgrade head` → `exec uvicorn` (with optional `--reload`).
- `compose/compose.yml`: `db` (postgres:17-alpine, healthcheck, **no host port**) + `api` (`depends_on: service_healthy`, `env_file`); SYERP/db/api always-on; documented module profiles.
- `compose/compose.dev.yml`: source mounts, `UVICORN_RELOAD`, watchfiles + Vite polling, Vite HMR on :5173.
- `.env.example` template, root `.dockerignore`, and `docs/deployment/local-dev.md` (containerized + native-run paths).
- **Live operator verification passed:** `/health/ready` → `{"status":"ok","db":"connected"}`, `/docs` → 200, SPA renders at `/` with both health cards green.

## Task Commits

1. **Task 1: SPA serving + multi-stage Dockerfile + entrypoint** - `c918b27` (feat)
2. **Task 2: Compose (prod + dev), profiles, .env.example, gitignore, docs** - `a0f037b` (feat)
3. **Task 3: Operator smoke verification** - human-verify checkpoint, approved by operator

## Files Created/Modified
- `Containerfile` - multi-stage image (relocated to repo root; see deviations)
- `backend/entrypoint.sh` - auto-migrate startup sequence
- `backend/app/main.py` - `SPAStaticFiles` mounted last
- `backend/alembic.ini` - `prepend_sys_path = .`
- `compose/compose.yml`, `compose/compose.dev.yml` - prod + dev orchestration
- `.dockerignore` (root), `.env.example`, `.gitignore`, `docs/deployment/local-dev.md`
- `frontend/src/routes/Landing.tsx`, `frontend/vite.config.ts` - health path alignment

## Decisions Made
- Build file is a **root `Containerfile`** (Podman's native name) rather than `backend/Dockerfile`, so podman auto-discovers it at the context root — this both fixes a Windows podman-compose bug and aligns with the project's Podman-first stance.
- Health endpoints remain at `/health/*` (root); the frontend and the Vite dev proxy were corrected to that contract.

## Deviations from Plan

Four issues surfaced only during the live operator smoke test (Task 3) — none reproducible in the unit-test sandbox — and were fixed before approval.

### Auto-fixed Issues

**1. [Integration] Windows podman-compose drops the build `-f` flag**
- **Found during:** Task 3 (operator `up`)
- **Issue:** podman-compose 1.6.0 normalizes the `..` context to an absolute Windows path (`E:\...`); `is_context_git_url()` then misreads the `E:` drive letter as a URL scheme and never passes `-f backend/Dockerfile`, so podman looked for a build file at the context root and failed.
- **Fix:** Moved `backend/Dockerfile` → root `Containerfile` (podman auto-discovers it); moved `.dockerignore` to the context root (where it actually applies) and expanded it; pointed compose at `dockerfile: Containerfile`.
- **Committed in:** `84fdc7c`

**2. [Build] `tsc: not found` in frontend build stage**
- **Found during:** Task 3 (image build)
- **Issue:** `npm ci --omit=dev` stripped the build toolchain (typescript, vite, plugins live in devDependencies).
- **Fix:** Use `npm ci` in the builder stage; dev tooling stays in the discarded builder stage, only `dist/` reaches the runtime image.
- **Committed in:** `c4b892b`

**3. [Runtime] `ModuleNotFoundError: No module named 'app'` during migrations**
- **Found during:** Task 3 (entrypoint `alembic upgrade head`)
- **Issue:** the `alembic` console script does not add its cwd to `sys.path` (unlike uvicorn/pytest), so `import app.core.models` in `env.py` failed. Not caught locally because the local migration test skips without a DB.
- **Fix:** Enabled `prepend_sys_path = .` in `backend/alembic.ini`.
- **Committed in:** `dd93df4`

**4. [Integration] Frontend called `/api/health/*` but backend serves `/health/*`**
- **Found during:** Task 3 (SPA rendered but health cards showed "Unexpected token '<'")
- **Issue:** wrong prefix hit the SPA static fallback (HTML), so the frontend failed parsing HTML as JSON. Hidden in Vite dev because the proxy only forwarded `/api`.
- **Fix:** Point the landing-page queries at `/health/{live,ready}` and add a `/health` dev-proxy entry.
- **Committed in:** `5f7fee9`

---

**Total deviations:** 4 auto-fixed (2 integration, 1 build, 1 runtime)
**Impact on plan:** All four were necessary to make the single-command deploy actually reach a healthy state (CORE-01). The first is a portability fix for Windows operators; the rest are cross-plan integration gaps that only surface at runtime. No scope creep.

## Issues Encountered
- Base-image vulnerability warnings (`node:22-slim`, `python:3.13-slim`) flagged by the IDE scanner — accepted scaffolding tradeoff (T-01-13 pins versions); revisit image hardening in a later phase.

## User Setup Required
Operator must `cp .env.example .env` and set `POSTGRES_PASSWORD` (done during verification), and install `podman-compose==1.6.0` (or use the documented `docker compose` fallback). See `docs/deployment/local-dev.md`.

## Next Phase Readiness
- Full stack is deployable from one command; module containers can now be added behind their compose profiles.
- Phase 2 (auth/data) can build on a live, migrating Postgres and the backend-serves-SPA pattern.

---
*Phase: 01-project-scaffolding-deployment*
*Completed: 2026-06-23*
