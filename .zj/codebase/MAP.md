# Codebase Map
Generated: 2026-07-04 | Commit: 2329803 (branch `chore-architecture-planning`)

> **Headline finding:** this repo is no longer "two HTML prototypes plus plans."
> The target-architecture re-platform is **already substantially built**: a working
> FastAPI backend (`backend/`) and React frontend (`frontend/`) implement auth,
> an admin shell, SYERP core (partners + GL), and PLUM (parts, revisions, BOM,
> costing, AVL, import/export), with Podman Compose deployment. The root
> `CLAUDE.md` "Technology Stack" / "Architecture" sections describe only the
> legacy prototypes and are **stale**. Planning should treat backend/frontend as
> the live codebase and the HTML apps as legacy reference implementations.

## Stack

### New platform (the active codebase)
- **Backend:** Python 3.13, FastAPI 0.138.0, SQLAlchemy 2.0.51 (async, asyncpg 0.31.0), Alembic 1.18.4, Pydantic Settings 2.14.2, PyJWT 2.13.0, pwdlib[argon2] 0.3.0, openpyxl 3.1.5 — `backend/requirements.txt:1-13`
- **Backend dev/test:** pytest 9.1.1, pytest-asyncio 1.4.0 (asyncio_mode=auto), httpx 0.28.1, ruff 0.15.18 — `backend/requirements-dev.txt`, `backend/pyproject.toml:1-15`
- **Frontend:** React 19.2.7, TypeScript 6.0.3, Vite 8.1.0, Tailwind CSS 4.3.1 (`@tailwindcss/vite`, no config file), shadcn/ui-style components (Radix primitives + cva), TanStack Query 5.101.1, react-router-dom 7.18.0, axios 1.18.1, sonner (toasts) — `frontend/package.json:13-51`
- **Frontend test/lint:** Vitest 4.1.9 + Testing Library + jsdom; ESLint 10 + typescript-eslint; Prettier 3.8.4 — `frontend/package.json:33-51`, `frontend/.eslintrc.cjs`, `frontend/.prettierrc.json`
- **Database:** PostgreSQL 17 (`postgres:17-alpine`) — `compose/compose.yml:32`
- **Containers:** Podman/Docker Compose; pinned bases `python:3.13-slim`, `node:22-slim` — `compose/compose.yml:24`, `Containerfile`

### Legacy prototypes (reference implementations, still runnable)
- Single-file vanilla ES6+ HTML apps, no build step, no framework:
  - **PLUM v54** — `plum/app/plm_v54.html` (31,353 lines, 1.27 MB); data: `plum/data/plm_database.json` (2.59 MB)
  - **FLAN v24** — `flan/app/prj-mgmt-v24.html` (11,568 lines, 1.6 MB); data: `flan/data/Crisis.json`, templates in `flan/templates/`
- CDN deps only: SheetJS 0.18.5, jsPDF 2.5.1 (per root `CLAUDE.md`; loaded at runtime, no lockfile)
- 22 archived FLAN versions in `flan/archive/`; PLUM archives under `plum/` (repo dirs: plum 33 MB, flan 8.7 MB)

## Architecture

**Modular monolith, SYERP as hub, one shared PostgreSQL database** — exactly per the stated constraint, and already realized in code:

- **Entry point:** `backend/app/main.py` — FastAPI app factory. Startup order: entrypoint waits for Postgres and runs `alembic upgrade head` (`backend/entrypoint.sh:22-25`), lifespan runs idempotent seeds (`main.py:52-59`), modules self-register, then a `SPAStaticFiles` catch-all serves the built React app from `frontend/dist` mounted **last** so it never swallows `/api/*` (`main.py:34-43,105-111`).
- **Module registry:** each module package's `__init__.py` calls `registry.register(module)`; `mount_all(app)` wires every module router under `/api/v1` (`backend/app/core/registry.py:38-46`, `main.py:79-84`). Registered today: `syerp`, `plum`, `auth`, `mousse` (`main.py:79-82`).
- **Module layout (repeated pattern):** `backend/app/modules/<name>/{__init__,models,schemas,router,service,seed}.py`. All business logic lives in `service.py`; routers are thin. **Exception (SYERP, since `chore-syerp-service-split`):** `syerp/service` is a **package**, not a single file — cohesive submodules `_common` (`_COST_QUANTUM`), `partners`, `locations`, `accounts` (`list_gl_accounts`, `_gl_account_id_by_code`), `items`, `inventory` (on-hand/txns, moving-average costing, `post_receipt`, adjustments, transfers), `journal` (double-entry post/reverse/list/get, balances, register), `purchasing` (POs, lines, costed receiving), `bills` (AP bills + payments), `reports` (AP aging + statements). `service/__init__.py` re-exports the full public surface, so `from app.modules.syerp.service import X` is unchanged. Dependency graph is acyclic: leaves (`partners`/`locations`/`accounts`/`items`) → `inventory` → `journal` → `purchasing` → `bills`; `reports` → `accounts`.
- **Cross-cutting platform code:** `backend/app/core/` — config (pydantic-settings, SecretStr for password/JWT, `config.py:25,35`), async engine/session (`db.py`), module-toggle and settings routers (`modules_router.py`, `settings_router.py`), seed orchestration (`seed.py`).
- **Cross-module integration via FKs:** PLUM AVL links reference SYERP partners (`backend/app/modules/plum/service.py:1634-1640` — currently broken, see Concerns).
- **Migrations:** 12 Alembic revisions, `backend/alembic/versions/0001`–`0012` (baseline → auth → modules/settings → syerp partners/GL accounts → plum → plum BOM/costing → **0007** syerp inventory → **0008** syerp purchasing → **0009** syerp GL journal `syerp_journal_entry`/`syerp_journal_line` double-entry ledger → **0010** syerp AP bills `syerp_bill`/`syerp_bill_line`/`syerp_payment`/`syerp_payment_allocation` → **0011** `syerp_bill.bill_date` NOT NULL + `created_at::date` backfill → **0012** MOUSSE work orders `mousse_work_order`/`mousse_work_order_component`/`mousse_work_order_issue`). Head is **0012**. *(0012 added at Phase 10; the `5190 Inventory Rounding` CoA account is seed-only, no migration.)*
- **Frontend:** SPA in `frontend/src/` — `main.tsx` → `App.tsx` route table; `components/AppShell.tsx` + Sidebar/Topbar shell; per-suite route folders `routes/plum/`, `routes/syerp/`, `routes/admin/`; server state via TanStack Query hooks (`hooks/useAuth.ts`, `useModules.ts`, `useSettings.ts`); single axios client with token handling (`src/api/client.ts`); shadcn/ui primitives in `components/ui/`.
- **Auth:** JWT two-token model (15-min access / 7-day refresh, `backend/app/core/config.py:38-39`), Argon2 hashing, seeded first admin (`BNS_ADMIN_*` env, `config.py:42-43`), RBAC tested in `backend/tests/auth/test_rbac.py`.
- **Legacy prototypes:** independent client-side silos — global state object + `renderAll()` string-template re-render + localStorage/JSON-file persistence (frozen reference per DECISIONS.md D-ADOPT-4; historical deep-dive archived at `archive/planning-gsd/codebase/ARCHITECTURE.md`).

### Directory structure (top level)
```
backend/            FastAPI app, alembic, tests (the live backend)
frontend/           React/Vite SPA (the live frontend)
compose/            compose.yml (prod) + compose.dev.yml (dev overlay: Vite HMR, --reload)
Containerfile       multi-stage image build (repo root; Podman-native name)
scripts/uat.ps1     one-command dev-stack launcher (PowerShell)
plum/, flan/        legacy prototypes: app/, archive/, data/, docs/, templates/
syerp/ crumb/ mousse/ crisp/ gelato/   placeholder suite dirs (CLAUDE.md only)
docs/               features/ (per-suite reference docs + requirements-progress.md),
                    tasks/ (branch checklists), deployment/local-dev.md, interviews/, reports/
archive/            planning-gsd/ (GSD phases 01–07, REQUIREMENTS, ROADMAP, STATE, audit,
                    codebase snapshots) + planning-docs/ (program ROADMAP.md, decisions.md)
                    — history only; the live planning source of truth is .zj/
_templates/         doc templates
```

## Commands

All verified against config files:

| Purpose | Command | Evidence |
|---|---|---|
| Full dev stack (db+api+Vite, containers only) | `./scripts/uat.ps1` (add `-Fresh` to reset DB, `-Down` to stop) | `scripts/uat.ps1:44-158` — requires `pwsh` on Linux |
| Prod stack | `podman-compose -f compose/compose.yml up -d` (needs `.env` from `.env.example`) | `compose/compose.yml:3-5` |
| Dev stack (manual) | `podman-compose -f compose/compose.yml -f compose/compose.dev.yml up` | `scripts/uat.ps1:58` |
| Backend tests | `pytest` from `backend/` (testpaths=tests, asyncio auto) | `backend/pyproject.toml:1-3` |
| Backend lint | `ruff check .` from `backend/` (E,F,I,UP; line-length 100) | `backend/pyproject.toml:5-15` |
| Migrations | `alembic upgrade head` from `backend/` (auto-run by container entrypoint) | `backend/alembic.ini`, `backend/entrypoint.sh:23` |
| Frontend dev | `npm run dev` from `frontend/` | `frontend/package.json:7` |
| Frontend build | `npm run build` (`tsc -b && vite build`) | `frontend/package.json:8` |
| Frontend lint | `npm run lint` (eslint, `--max-warnings 0`) | `frontend/package.json:10` |
| Frontend tests | `npm run test` (vitest) | `frontend/package.json:11` |
| Legacy prototypes | open `plum/app/plm_v54.html` / `flan/app/prj-mgmt-v24.html` in a browser | `README.md:21-27` |

Required env (no defaults; app refuses to start without them): `POSTGRES_PASSWORD`, `JWT_SECRET`, `BNS_ADMIN_PASSWORD` — `backend/app/core/config.py:25,35,43`, `.env.example:19-33`. `.env` exists locally but is not git-tracked (verified via `git ls-files`).

## Conventions

**Backend**
- Module patterns: one package per suite under `app/modules/`, files `models.py` / `schemas.py` / `router.py` / `service.py` / `seed.py`; `__init__.py` self-registers with `app.core.registry` (`registry.py:8-13`).
- Async everywhere: SQLAlchemy async sessions, pytest asyncio auto mode.
- Decision-traceability comments: code cites planning decision/threat IDs inline — `D-08`, `D-09`, `T-01-12` etc. (`main.py:4-12`, `compose/compose.yml:7,18,23`, `config.py:6`). New code is expected to reference the relevant `.planning` decision.
- Seeds are idempotent and run at startup lifespan (`main.py:54-58`).
- Secrets typed `SecretStr`; DB never port-mapped to host (`compose/compose.yml:39`).
- Tests grouped per module: `backend/tests/{auth,core,plum,syerp}/` (18 test files).

**Frontend**
- Per-suite route folders with a local `components/` subfolder (`src/routes/plum/components/`); suite nav components (`PlumNav.tsx`, `SyerpNav.tsx`).
- Server state via TanStack Query; no Zustand present (unverified whether planned).
- Colocated tests: `*.test.tsx` next to source (8 test files, e.g. `src/routes/plum/PartsList.test.tsx`).
- shadcn/ui primitives generated into `src/components/ui/` (`components.json`); `cn()` helper in `src/lib/utils.ts`.
- Prettier + ESLint enforced with zero-warning policy (`package.json:10`).

**Workflow (authoritative, from root `CLAUDE.md`)**
- Conventional commits; **no** "co-authored"/"generated with Claude" lines; never edit `CHANGELOG.md` directly.
- Branch naming `feature-*`/`bugfix-*`/`hotfix-*`/`chore-*`; checklist file at `docs/tasks/{branch}.md` per code-changing task.
- Feature work must reference requirement IDs (now maintained in `.zj/SRD.md`) and update `docs/features/requirements-progress.md`.

**Legacy prototype conventions** (namespace-by-object, `renderAll()`, template-literal `innerHTML`, suite-prefixed localStorage keys) are documented exhaustively in root `CLAUDE.md` — follow them only when touching `plum/app/` or `flan/app/`.

## Hotspots

| File | Why central |
|---|---|
| `backend/app/modules/plum/service.py` | 2,995 lines — all PLUM business logic (parts, revisions, BOM roll-up, costing, AVL, import/export); highest churn among source files. **Now the largest single service file** — the SYERP monolith (3,824 lines) was split into a `syerp/service/` package at `chore-syerp-service-split`; PLUM's split remains owed (BACKLOG). |
| `backend/app/modules/syerp/service/` | package (was a 3,824-line `service.py`) — 10 cohesive submodules behind unchanged public functions; `bills.py` (~1,001) and `purchasing.py` (~719) are the largest. See Module layout note above. |
| `backend/app/modules/plum/router.py` | 1,062 lines; PLUM API surface; 4 changes in recent history |
| `backend/app/main.py` | app factory, module registration order, SPA mount — every module addition touches it |
| `backend/app/core/registry.py` | module mounting contract every new suite must satisfy |
| `frontend/src/App.tsx` | route table; changed with every new page (4 recent changes) |
| `frontend/src/api/client.ts` | single axios client — all API traffic and token handling |
| `frontend/src/routes/plum/PartDetail.tsx` | 1,345 lines; largest frontend view, hosts most PLUM dialogs |
| `backend/alembic/versions/` | schema source of truth (12 revisions, head `0012`); every model change adds one |
| `compose/compose.yml` + `Containerfile` + `backend/entrypoint.sh` | deployment path incl. migration-on-boot sequence |

## Concerns

1. **BLOCKER (known, verified live in code):** `backend/app/modules/plum/service.py` imports a nonexistent class `SyerpPartner` at lines **1634, 2139, 2607, 2740** — the actual class is `Partner` (`backend/app/modules/syerp/models.py:39`). Breaks AVL vendor-link creation, JSON export with AVL rows, and vendor-referencing import (HTTP 500). Found by the v1.0 milestone audit (archived at `archive/planning-gsd/v1.0-MILESTONE-AUDIT.md`; PLUM-07/PLUM-10 unsatisfied); Phase 7 closes these gaps. It is a trivially small fix (rename 10 references) plus a missing-test gap: no test exercises the AVL/vendor path end-to-end, which is why 4 plans claimed it complete.
2. **Verification debt:** Phase 6 was never goal-verified; PLUM-04/05/06/08/09 are "partial — verification gap" per the archived v1.0 milestone audit (statuses now carried in `.zj/SRD.md`). `docs/features/requirements-progress.md` marks things Complete that were never human-verified.
3. **Stale project context:** root `CLAUDE.md` "Technology Stack" and "Architecture" sections describe only the vanilla-JS prototypes ("No server-side runtime", "None — no npm"), contradicting the live FastAPI/React codebase. Also references Windows paths (`E:\Projects\`) while the workspace now runs on Linux. Any agent relying on CLAUDE.md's stack section will mis-model the codebase.
4. **Service-layer monolith:** SYERP's `service.py` had grown to 3,824 lines (Phases 8–9c) and was split into a `syerp/service/` package at `chore-syerp-service-split` (10 cohesive submodules, unchanged public surface). `plum/service.py` at ~3,000 lines is the remaining monolith and still needs the same treatment (BACKLOG) before it metastasizes.
5. **No CI:** no `.github/`, no pipeline config anywhere (verified). Lint/test enforcement is manual; the SyerpPartner bug shipping through 4 plans is the direct consequence.
6. **Tooling friction on Linux:** the only stack launcher is PowerShell (`scripts/uat.ps1`); requires `pwsh` or manual compose commands. Compose comments still reference a Windows podman-compose bug (`compose/compose.yml:57-60`).
7. **Repo weight from legacy artifacts:** `plum/` 33 MB + `flan/` 8.7 MB, including 22 archived FLAN versions (`flan/archive/`) and a 2.6 MB JSON database — harmless but slows clones; consider git-lfs or pruning once re-platforming supersedes them.
8. **Legacy prototype risks** (XSS via `innerHTML`, localStorage limits, advisory-only checkout locking) — moot for new work since the prototypes are frozen reference (D-ADOPT-4); historical detail archived at `archive/planning-gsd/codebase/CONCERNS.md`.
9. **Placeholder suite dirs** (`syerp/`, `crumb/`, `mousse/`, `crisp/`, `gelato/` at repo root) contain only `CLAUDE.md` files and can confuse navigation — the real SYERP code is `backend/app/modules/syerp/`, not `syerp/`.
