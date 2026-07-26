# Local Development Guide

This document describes how to run BizNiceSweets locally — both as a single-command
containerized stack (canonical / onboarding path) and as a native process pair
(fast-debug escape hatch for Windows developers).

---

## Prerequisites

- **Container path:** [Podman 5.x](https://podman.io/) + `podman-compose`
  (or Docker 28+ + `docker compose` as a fallback — see below)
- **Native path:** Python 3.13, Node.js 22, a running PostgreSQL instance

---

## Path 1 — Containerized Stack (Canonical / Onboarding)

This is the recommended path for first-time setup, onboarding, and verifying a
production-like deploy. A single command starts everything.

### 1.1 Install podman-compose

```bash
pip install podman-compose==1.6.0
```

**Docker Compose fallback:** If you prefer Docker, `docker compose` (v2 plugin,
bundled with Docker Desktop) is functionally equivalent for development. Replace
`podman-compose` with `docker compose` in all commands below.

### 1.2 Configure the environment

The stack reads **two** env files (D-P5-10). Copy both:

```bash
cp .env.example    .env
cp .env.db.example .env.db
```

| File | Contents | Read by |
|------|----------|---------|
| `.env` | app config + app secrets (`JWT_SECRET`, `BNS_ADMIN_*`) | `api` only |
| `.env.db` | database credentials (`POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD`) | `db` **and** `api` |

Open `.env.db` and set a real `POSTGRES_PASSWORD`, and `.env` and set a real
`JWT_SECRET` and `BNS_ADMIN_PASSWORD`. The `changeme_*` placeholders will NOT work
for a secure deployment.

> **Why two files.** The Postgres container needs the database credentials and
> nothing else, so splitting them keeps `JWT_SECRET` out of a container that has no
> use for it. `POSTGRES_PASSWORD` therefore has exactly one home — `.env.db` — read
> by both containers rather than duplicated into two files that can drift.
>
> **Do not skip `.env.db`.** Without it the `db` container starts with an empty
> password. An *already-initialized* volume does not care, so the stack appears
> healthy — but a **fresh** volume refuses to initialize with
> `Database is uninitialized and superuser password is not specified`. That was
> defect U0 (v4.0 Phase 5); it is pinned by
> `backend/tests/test_compose_config.py`.

> Both `.env` and `.env.db` are listed in `.gitignore` — neither will ever be
> committed. Only the `.env.example` / `.env.db.example` templates are tracked.

### 1.3 Production-like stack (API + DB, built SPA served from backend)

```bash
podman-compose -f compose/compose.yml up -d
```

The startup sequence (automated — no manual steps):

1. Postgres starts and becomes healthy (pg_isready healthcheck, ~5–15 s).
2. The api container starts, `entrypoint.sh` waits for Postgres, runs
   `alembic upgrade head`, then launches uvicorn.
3. Stack is ready when `curl http://localhost:8000/health/ready` returns
   `{"status":"ok","db":"connected"}`.

To verify:

```bash
curl http://localhost:8000/health/live    # → {"status":"ok"}
curl http://localhost:8000/health/ready  # → {"status":"ok","db":"connected"}
curl http://localhost:8000/docs          # → OpenAPI UI (HTML)
# Open http://localhost:8000/ in a browser to see the SPA
```

### 1.4 Dev stack with hot-reload and HMR

```bash
podman-compose -f compose/compose.yml -f compose/compose.dev.yml up
```

This overlay adds:

- **`api` service:** source volume-mounted (`backend/` → `/app`),
  uvicorn `--reload` enabled, watchfiles polling forced
  (`WATCHFILES_FORCE_POLLING=true` — required on Windows 10 where WSL2
  inotify does not propagate host filesystem events).
- **`frontend` service:** Vite dev server on port 5173 with HMR
  (`VITE_USE_POLLING=true`), proxy `/api/*` → `http://api:8000`.

Visit `http://localhost:5173` for the Vite HMR frontend (development UI).
The API is still reachable at `http://localhost:8000`.

### 1.5 Teardown and reset

```bash
# Stop containers (data volume preserved)
podman-compose -f compose/compose.yml down

# Stop containers AND delete the Postgres data volume (full reset)
podman-compose -f compose/compose.yml down -v
```

After `down -v` + `up`, Alembic migrations run automatically on the fresh
database — no manual migration step. This confirms the repeatability
requirement (CORE-01).

---

## Path 2 — Native Run (Fast-Debug Escape Hatch)

> Recommended for active Python development on Windows 10, where container
> volume-mount file-watching can be slow or unreliable even with polling.

Run uvicorn and Vite directly on the host; keep only Postgres in a container.

### 2.1 Start Postgres in a container

```bash
podman run -d \
  --name biznice-db \
  -e POSTGRES_DB=biznice \
  -e POSTGRES_USER=app \
  -e POSTGRES_PASSWORD=changeme_in_production \
  -p 5432:5432 \
  postgres:17-alpine
```

### 2.2 Set up the Python backend

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Create a `.env` in `backend/` (or rely on the repo-root `.env`):

```ini
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=biznice
POSTGRES_USER=app
POSTGRES_PASSWORD=changeme_in_production
```

Run migrations and start the server:

```bash
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2.3 Set up the Node frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server starts on `http://localhost:5173` and proxies `/api/*` to
`http://api:8000` (as configured in `vite.config.ts`). For native dev, the
proxy target resolves to `localhost:8000` — update `vite.config.ts` if needed,
or set the `VITE_API_BASE_URL` env variable.

---

## Module Profiles (D-04)

SYERP (the hub), `db`, and `api` are **always-on** — they start with or without
any `--profile` flag. Optional modules (Phase 4–6) will be gated behind compose
profiles:

| Profile flag | Activates |
|---|---|
| _(none)_ | db + api (SYERP hub) only |
| `--profile plum` | PLUM module services |
| `--profile flan` | FLAN module services |
| `--profile mousse` | MOUSSE module services |
| `--profile crumb` | CRUMB module services |
| `--profile gelato` | GELATO module services |
| `--profile crisp` | CRISP module services |
| `--profile full` | All optional modules |

Example:

```bash
podman-compose -f compose/compose.yml --profile plum up -d
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `api` exits immediately with DB error | Postgres not ready yet | Check `podman-compose logs db`; ensure healthcheck passes |
| File changes don't trigger reload | inotify not working on Windows | Add `compose.dev.yml` overlay; `WATCHFILES_FORCE_POLLING=true` is set automatically |
| `alembic upgrade head` fails | Schema mismatch or bad URL | Verify `POSTGRES_HOST`/`POSTGRES_PORT` in `.env` and the credentials in `.env.db`; check migration logs in `podman-compose logs api` |
| `db` container restart-loops with `Database is uninitialized and superuser password is not specified` | `.env.db` is missing, so `POSTGRES_PASSWORD` is empty. Only ever shows up on a **fresh** volume | `cp .env.db.example .env.db`, set a real password, then `podman-compose -f compose/compose.yml up -d` again (defect U0) |
| Port 8000 already in use | Another process on the port | Stop the conflicting process or change the host port in `compose.yml` |
