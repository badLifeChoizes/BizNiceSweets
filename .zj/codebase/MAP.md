# Codebase Map
Generated: 2026-07-04 (commit 2329803) | **Refreshed: 2026-08-19** at the v5.0 Phase 1 close
(branch `feature-flan-core`) — FLAN folded in and every Concern re-verified by command on that date.

> **Headline finding:** this repo is no longer "two HTML prototypes plus plans."
> The target-architecture re-platform is **already substantially built**: a working
> FastAPI backend (`backend/`) and React frontend (`frontend/`) implement auth,
> an admin shell, and **six of the seven suites** — SYERP (partners, GL, inventory,
> purchasing, AP, AR), PLUM, MOUSSE, CRUMB, GELATO and, since v5.0 Phase 1, **FLAN**
> (only CRISP is unbuilt) — with Podman Compose deployment and a six-job GitHub
> Actions pipeline whose every job is a required status check on `master`. Planning
> should treat `backend/` and `frontend/` as the live codebase and the HTML apps as
> legacy reference implementations.

## Stack

### New platform (the active codebase)
- **Backend:** Python 3.13, FastAPI 0.138.0, SQLAlchemy 2.0.51 (async, asyncpg 0.31.0), Alembic 1.18.4, Pydantic Settings 2.14.2, PyJWT 2.13.0, pwdlib[argon2] 0.3.0, openpyxl 3.1.5 — `backend/requirements.txt:1-13`
- **Backend dev/test:** pytest 9.1.1, pytest-asyncio 1.4.0 (asyncio_mode=auto), httpx 0.28.1, ruff 0.15.18 — `backend/requirements-dev.txt`, `backend/pyproject.toml:1-15`
- **Frontend:** React 19.2.7, TypeScript 6.0.3, Vite 8.1.0, Tailwind CSS 4.3.1 (`@tailwindcss/vite`, no config file), shadcn/ui-style components (Radix primitives + cva), TanStack Query 5.101.1, react-router-dom 7.18.0, axios 1.18.1, sonner (toasts) — `frontend/package.json:13-51`
- **Frontend test/lint:** Vitest 4.1.9 + Testing Library + jsdom; ESLint 10 **flat config** + typescript-eslint 8.62.0; Prettier 3.8.4 — `frontend/package.json:33-55`, `frontend/eslint.config.js`, `frontend/.prettierrc.json`. The legacy `.eslintrc.cjs` was **deleted** from `frontend/` at v4.0 Phase 1 and no longer exists — an `ls` of that path returns *No such file or directory* (2026-08-19); `eslint.config.js:1-4,17-20` is the live config and gates itself.
- **Database:** PostgreSQL 17 (`postgres:17-alpine`) — `compose/compose.yml:32`
- **Containers:** Podman/Docker Compose; pinned bases `python:3.13-slim`, `node:22-slim` — `Containerfile:19,46`, `compose/compose.yml:37`
- **CI:** GitHub Actions — one workflow, `.github/workflows/ci.yml` (`on: push` + `pull_request`, `:6-8`), **six jobs** run in parallel with no `needs:` — `container-image` (`:25`), `frontend` (`:128`), `backend-lint` (`:148`), `backend-tests` (`:164`), `verify-scripts` (`:208`, globs `scripts/verify_*.py`), `verify-scripts-api` (`:414`, globs `scripts/verify_*_api.py`). All six are required status checks on `master`: `gh api repos/:owner/:repo/branches/master/protection --jq '.required_status_checks.contexts'` → `["frontend","backend-lint","backend-tests","verify-scripts","verify-scripts-api","container-image"]` (2026-08-19). *(The in-file NOTEs at `ci.yml:21-24,411-413` saying `container-image`/`verify-scripts-api` "report but do not block" are stale — the repo settings were since updated.)*

### Legacy prototypes (reference implementations, still runnable)
- Single-file vanilla ES6+ HTML apps, no build step, no framework:
  - **PLUM v54** — `plum/app/plm_v54.html` (31,353 lines, 1.27 MB); data: `plum/data/plm_database.json` (2.59 MB)
  - **FLAN v24** — `flan/app/prj-mgmt-v24.html` (11,568 lines, 1.6 MB); data: `flan/data/Crisis.json`, templates in `flan/templates/`
- CDN deps only: SheetJS 0.18.5, jsPDF 2.5.1 (per root `CLAUDE.md`; loaded at runtime, no lockfile)
- 23 archived FLAN versions in `flan/archive/` (`ls flan/archive | wc -l`); PLUM archives under `plum/` (repo dirs: plum 33 MB, flan 8.9 MB — `du -sh plum flan`)

## Architecture

**Modular monolith, SYERP as hub, one shared PostgreSQL database** — exactly per the stated constraint, and already realized in code:

- **Entry point:** `backend/app/main.py` — FastAPI app factory. Startup order: entrypoint waits for Postgres and runs `alembic upgrade head` (`backend/entrypoint.sh:22-25`), lifespan runs idempotent seeds (`main.py:52-59`), modules self-register, then a `SPAStaticFiles` catch-all serves the built React app from `frontend/dist` mounted **last** so it never swallows `/api/*` (`main.py:34-43,105-111`).
- **Module registry:** each module package's `__init__.py` calls `registry.register(module)`; `mount_all(app)` wires every module router under `/api/v1` (`backend/app/core/registry.py:38-46`, `main.py:98`). Registered today — **seven**: `syerp`, `plum`, `mousse`, `crumb`, `gelato`, `flan`, `auth` (`main.py:78-84`, one `importlib.import_module` per module, in that order; `ls backend/app/modules/` shows the same seven packages).
- **Module layout (repeated pattern):** `backend/app/modules/<name>/{__init__,models,schemas,router,service,seed}.py`. All business logic lives in `service.py`; routers are thin. **Exception (SYERP, since `chore-syerp-service-split`):** `syerp/service` is a **package**, not a single file — cohesive submodules `_common` (`_COST_QUANTUM`), `partners`, `locations`, `accounts` (`list_gl_accounts`, `_gl_account_id_by_code`), `items`, `inventory` (on-hand/txns, moving-average costing, `post_receipt`, adjustments, transfers), `journal` (double-entry post/reverse/list/get, balances, register), `purchasing` (POs, lines, costed receiving), `bills` (AP bills + payments), `reports` (AP aging + statements). `service/__init__.py` re-exports the full public surface, so `from app.modules.syerp.service import X` is unchanged. Dependency graph is acyclic: leaves (`partners`/`locations`/`accounts`/`items`) → `inventory` → `journal` → `purchasing` → `bills`; `reports` → `accounts`. **CRUMB (since Phase 11a) also ships `service` as a package** — `_common` (`STAGE_TRANSITIONS`/`QUOTE_TRANSITIONS`/`SO_TRANSITIONS` FSMs, `DEFAULT_MARKUP_PCT`, `_resolve_customer`), `leads`, `opportunities`, `quotes` (PLUM-derived line pricing, numeric-safe `QUOTE-####`), `interactions`, `sales_orders` (Phase 11b — numeric-safe `SO-####`, FSM, accepted-quote→SO conversion, and the **soft-reservation crux**: `confirm_sales_order` locks the contended `InventoryItem` rows `FOR UPDATE` in sorted-id order before reserving `min(qty_ordered, available)`, cancel releases; imports SYERP `get_item_on_hand`); `service/__init__.py` re-exports the public surface. Audit is written at the router layer after each service commit. **FLAN (v5.0 Phase 1) ships `service` as a package too** — `_common`, `rollup` (phase `start_date`/`due_date`/`percent_complete` are COMPUTED per read, never stored), `projects`, `phases`, `keys` (per-project numeric-safe task keys), `tasks`, `roster`, `assignments`: 8 submodules, 2,314 lines (`wc -l backend/app/modules/flan/service/*.py`); `service/__init__.py` re-exports the public surface. FLAN has **no `seed.py`** — its only seed rows are the module-toggle entry `("flan", "FLAN — Project Management", False, 30)` in `backend/app/core/modules_seed.py:26`. Three suites now use the package form, so a `service/` package — not a `service.py` — is the pattern a new suite should copy. FLAN's `router.py` (744 lines) exposes **20 operations across 11 paths** under `/api/v1/flan` (`grep -cE '^@router\.' backend/app/modules/flan/router.py` → 20; `verify_flan_api.py` reports "20 routes (6 read + 14 write) and 14 audit actions exercised over real HTTP").
- **Cross-cutting platform code:** `backend/app/core/` — config (pydantic-settings, SecretStr for password/JWT, `config.py:25,35`), async engine/session (`db.py`), module-toggle and settings routers (`modules_router.py`, `settings_router.py`), seed orchestration (`seed.py`).
- **Cross-module integration via FKs:** PLUM AVL links reference SYERP partners (`backend/app/modules/plum/service.py:1669-1676`, `Partner as SyerpPartner`); CRUMB sales-order lines reference `syerp_inventory_item`; FLAN's roster references auth (`flan_team_member.user_id` → `users.id ON DELETE SET NULL`, `backend/app/modules/flan/models.py:393`) and is otherwise self-contained — no FLAN table points at another suite.
- **Metadata aggregator:** `backend/app/core/models.py` imports every module's `models` (`:22-23` for flan/gelato) and `main.py` imports it (`main.py:95`) so `Base.metadata` is fully populated before serving; cross-module string FKs would otherwise fail mapper configuration at request time.
- **Migrations:** 18 Alembic revisions in `backend/alembic/versions/`, `0001`–`0018` (baseline → auth → modules/settings → syerp partners/GL accounts → plum → plum BOM/costing → **0007** syerp inventory → **0008** syerp purchasing → **0009** syerp GL journal `syerp_journal_entry`/`syerp_journal_line` double-entry ledger → **0010** syerp AP bills `syerp_bill`/`syerp_bill_line`/`syerp_payment`/`syerp_payment_allocation` → **0011** `syerp_bill.bill_date` NOT NULL + `created_at::date` backfill → **0012** MOUSSE work orders `mousse_work_order`/`mousse_work_order_component`/`mousse_work_order_issue` → **0013** CRUMB CRM `crumb_lead`/`crumb_opportunity`/`crumb_quote`/`crumb_quote_line`/`crumb_interaction` (circular `crumb_lead`↔`crumb_opportunity` FK broken via post-create `op.create_foreign_key`) → **0014** CRUMB sales orders `crumb_sales_order`/`crumb_sales_order_line` (nullable `item_id` FK→`syerp_inventory_item`, `qty_reserved` accumulator; one-directional FKs, no post-create dance) → **0015** GELATO bins/putaway → **0016** GELATO shipments → **0017** SYERP AR invoicing `syerp_invoice`/`syerp_invoice_line`/`syerp_receipt`/`syerp_receipt_allocation` + `crumb_sales_order_line.qty_invoiced` accumulator → **0018** FLAN core (`0018_flan_core.py`) — **eight** tables `flan_project`/`flan_phase`/`flan_task`/`flan_project_tag`/`flan_task_tag`/`flan_team_member`/`flan_task_assignee`/`flan_phase_assignee` (`grep -n __tablename__ backend/app/modules/flan/models.py` → 8 hits at `:99,160,220,292,314,365,425,450`), hand-written, not autogenerated — see Concerns 10). Head is **0018** (`alembic current` in the dev stack → `0018 (head)`, 2026-08-19). *(0018 added at v5.0 Phase 1; 0017 at Phase 13; 0015/0016 at Phase 12a/12b; 0014 added at Phase 11b; 0013 at Phase 11a; 0012 at Phase 10; the `5190 Inventory Rounding` CoA account is seed-only, no migration.)*
- **Frontend:** SPA in `frontend/src/` — `main.tsx` → `App.tsx` route table; `components/AppShell.tsx` + Sidebar/Topbar shell; per-suite route folders `routes/plum/`, `routes/syerp/`, `routes/mousse/`, `routes/crumb/`, `routes/gelato/`, `routes/flan/`, `routes/admin/`; FLAN contributes four screens — `Projects.tsx`, `Phases.tsx`, `Tasks.tsx`, `Team.tsx` — on four routes plus a `/flan` → `/flan/projects` redirect (`frontend/src/App.tsx:135-140`), sharing one `routes/flan/hooks.ts` (622 lines) query layer; server state via TanStack Query hooks (`hooks/useAuth.ts`, `useModules.ts`, `useSettings.ts`); single axios client with token handling (`src/api/client.ts`); shadcn/ui primitives in `components/ui/`.
- **Auth:** JWT two-token model (15-min access / 7-day refresh, `backend/app/core/config.py:38-39`), Argon2 hashing, seeded first admin (`BNS_ADMIN_*` env, `config.py:42-43`), RBAC tested in `backend/tests/auth/test_rbac.py`.
- **Legacy prototypes:** independent client-side silos — global state object + `renderAll()` string-template re-render + localStorage/JSON-file persistence (frozen reference per DECISIONS.md D-ADOPT-4; historical deep-dive archived at `archive/planning-gsd/codebase/ARCHITECTURE.md`).

### Directory structure (top level)
```
backend/            FastAPI app, alembic, tests (the live backend)
                    app/modules/{auth,syerp,plum,mousse,crumb,gelato,flan}/  <- the seven
                    scripts/verify_*.py (28, of which 10 are *_api.py) - CI-run gates
frontend/           React/Vite SPA (the live frontend)
                    src/routes/{syerp,plum,mousse,crumb,gelato,flan,admin}/
compose/            compose.yml (prod) + compose.dev.yml (dev overlay: Vite HMR, --reload)
.github/workflows/  ci.yml - the six-job pipeline; all six gate master
Containerfile       multi-stage image build (repo root; Podman-native name)
scripts/uat.sh      one-command dev-stack launcher (bash); uat.ps1 is the PowerShell twin
plum/, flan/        legacy prototypes: app/, archive/, data/, docs/, templates/
syerp/ crumb/ mousse/ crisp/ gelato/   placeholder suite dirs (CLAUDE.md + doc templates,
                    no source at all - the code is under backend/app/modules/)
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
| Full dev stack (db+api+Vite, containers only) | `./scripts/uat.sh` (add `--fresh` to reset DB, `--down` to stop) or `./scripts/uat.ps1` (`-Fresh` / `-Down`) | `scripts/uat.sh:50-228`; `scripts/uat.ps1:44-178` — the `.ps1` requires `pwsh` on Linux |
| Prod stack | `podman-compose -f compose/compose.yml up -d` (needs **both** `.env` from `.env.example` and `.env.db` from `.env.db.example` — D-P5-10) | `compose/compose.yml:3-5`, `:85-88` (`api` reads both files) |
| Dev stack (manual) | `podman-compose -f compose/compose.yml -f compose/compose.dev.yml up` | `scripts/uat.sh:126` |
| Backend tests | `pytest` from `backend/` (testpaths=tests, asyncio auto). **DB-backed (v4.0 Phase 2a, NFR-5):** the harness provisions a dedicated migrated **`biznice_test`** DB (never the live `biznice`) and requires a live Postgres — no silent-skip mode. **The one-liner that works locally mounts the REPO ROOT** (not `backend/`) — `tests/test_compose_config.py:48` and `tests/test_containerfile_config.py:58` resolve the repo root as `Path(__file__).resolve().parents[2]`, so a `backend/`-only mount lands on `/` and the 9 layout tests break (`3 failed, 236 passed, 6 errors` at this phase's preflight); `pytest` is also absent from the image, hence the `pip install`: <br>`podman run --rm --user root --network compose_default -v "$PWD:/repo:z" -w /repo/backend --env-file .env --env-file .env.db -e POSTGRES_HOST=db -e PYTHONPATH=/repo/backend -e TEST_POSTGRES_DB=biznice_test compose_api sh -c "pip install -q -r requirements-dev.txt; python -m pytest -q"` <br>→ **268 passed, 0 skipped** (2026-08-19, 43 test files). Use a private `TEST_POSTGRES_DB` if anyone else may be running the suite — see Concerns 12. | `backend/pyproject.toml:1-3`, `backend/tests/conftest.py:16-33` |
| Backend lint | `ruff check .` from `backend/` (E,F,I,UP; line-length 100) | `backend/pyproject.toml:5-15` |
| Migrations | `alembic upgrade head` from `backend/` (auto-run by container entrypoint) | `backend/alembic.ini`, `backend/entrypoint.sh:23` |
| Frontend dev | `npm run dev` from `frontend/` | `frontend/package.json:7` |
| Frontend build | `npm run build` (`tsc -b && vite build`) | `frontend/package.json:8` |
| Frontend lint | `npm run lint` (eslint, `--max-warnings 0`) | `frontend/package.json:10` |
| Frontend tests | `npm run test -- --run` from `frontend/` → **51 files / 196 tests passed** (2026-08-19). ⚠ The `test` script is bare `vitest`, i.e. **watch mode** — a plain `npm run test` never exits and hangs any non-interactive gate. `-- --run` is mandatory. | `frontend/package.json:11` |
| Verify scripts | `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_<x>.py` from a running dev stack (recurring `PYTHONPATH` tax). The `.zj/`-reading ones (e.g. `verify_qa_doc.py`) need the **repo root** mounted, not `backend/` — in the `api` container they die with `FileNotFoundError: /.zj/SRD.md`. | `.github/workflows/ci.yml:272-281` |
| CI (all gates, automatically) | pushed to any branch — six jobs, all required on `master` | `.github/workflows/ci.yml:6-8,25,128,148,164,208,414` |
| Legacy prototypes | open `plum/app/plm_v54.html` / `flan/app/prj-mgmt-v24.html` in a browser | `README.md:21-27` |

Required env (no defaults; app refuses to start without them) is split across **two** files since D-P5-10: `JWT_SECRET` + `BNS_ADMIN_PASSWORD` in `.env` (`.env.example:32,36`) and `POSTGRES_PASSWORD` in `.env.db` (`.env.db.example:34`) — `backend/app/core/config.py:24,33,41`. `db` reads `../.env.db` only; `api` reads both (`compose/compose.yml:51`, `:85-88`). Both files exist locally but neither is git-tracked (verified via `git ls-files`); only the two `*.example` templates are.

## Conventions

**Backend**
- Module patterns: one package per suite under `app/modules/`, files `models.py` / `schemas.py` / `router.py` / `service.py` (or a `service/` package — SYERP, CRUMB, FLAN) / optional `seed.py`; `__init__.py` self-registers with `app.core.registry` (`registry.py:8-13`, `register()` at `:38`, `mount_all()` at `:43-46`). FLAN is the cleanest small example of the whole shape (`backend/app/modules/flan/`, 4,101 lines incl. its service package).
- Async everywhere: SQLAlchemy async sessions, pytest asyncio auto mode.
- Decision-traceability comments: code cites planning decision/threat IDs inline — `D-08`, `D-09`, `T-01-12` etc. (`main.py:4-12`, `compose/compose.yml:7,18,23`, `config.py:6`). New code is expected to reference the relevant `.planning` decision.
- Seeds are idempotent and run at startup lifespan (`main.py:54-58`).
- Secrets typed `SecretStr`; DB never port-mapped to host (`compose/compose.yml:39`).
- Tests grouped per module: `backend/tests/{auth,core,crumb,flan,gelato,mousse,plum,syerp}/` plus five top-level files (`test_compose_config`, `test_containerfile_config`, `test_harness_selfcheck`, `test_health`, `test_migrations`) — **43 test files, 268 passing, 0 skipped**.

**Frontend**
- Per-suite route folders with a local `components/` subfolder (`src/routes/plum/components/`, `src/routes/flan/components/`); suite nav components (`PlumNav.tsx`, `SyerpNav.tsx`, `FlanNav.tsx`) and, in the four newest suites (`crumb`, `flan`, `gelato`, `mousse`), one `hooks.ts` per suite holding its whole TanStack Query layer (`ls frontend/src/routes/*/hooks.ts`).
- Server state via TanStack Query; no Zustand present (unverified whether planned).
- Colocated tests: `*.test.tsx` next to source — **51 test files / 196 tests** (e.g. `src/routes/plum/PartsList.test.tsx`, `src/routes/flan/Tasks.test.tsx`).
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
| `backend/app/modules/plum/service.py` | 3,058 lines — all PLUM business logic (parts, revisions, BOM roll-up, costing, AVL, import/export); highest churn among source files. **Now the largest single service file** — the SYERP monolith (3,824 lines) was split into a `syerp/service/` package at `chore-syerp-service-split`; PLUM's split remains owed (BACKLOG). |
| `backend/app/modules/syerp/service/` | package (was a 3,824-line `service.py`) — 10 cohesive submodules behind unchanged public functions; `bills.py` (~1,001) and `purchasing.py` (~719) are the largest. See Module layout note above. |
| `backend/app/modules/plum/router.py` | 1,060 lines; PLUM API surface; 4 changes in recent history |
| `backend/app/main.py` | app factory, module registration order, SPA mount — every module addition touches it |
| `backend/app/core/registry.py` | module mounting contract every new suite must satisfy |
| `frontend/src/App.tsx` | route table; changed with every new page (4 recent changes) |
| `frontend/src/api/client.ts` | single axios client — all API traffic and token handling |
| `frontend/src/routes/plum/PartDetail.tsx` | 1,350 lines; largest frontend view, hosts most PLUM dialogs |
| `backend/alembic/versions/` | schema source of truth (18 revisions, head `0018`); every model change adds one — **hand-check every autogenerated draft**, see Concerns 10 |
| `compose/compose.yml` + `Containerfile` + `backend/entrypoint.sh` | deployment path incl. migration-on-boot sequence |
| `.github/workflows/ci.yml` | the six gates every branch must pass; both `verify-*` jobs are glob-driven, so a new `scripts/verify_*.py` enrols itself |
| `frontend/src/routes/flan/hooks.ts` | 622 lines — FLAN's entire query/mutation layer; every FLAN screen imports from it |

## Concerns

**Every item below was re-verified by command on 2026-08-19** (v5.0 Phase 1 close) and carries the
`file:line` or command it was checked with. Four claims that earlier editions of this map asserted
did **not** survive that check — a fixed bug called a live BLOCKER, "no CI", a deleted lint config,
and a short module list — and are corrected in place rather than quietly dropped, because six phases
of architects would otherwise have planned around them.

1. **CORRECTED — the `SyerpPartner` "BLOCKER" is fixed and has been since v3.0 Phase 7.** Earlier
   editions called `SyerpPartner` a *nonexistent class* imported at four sites in
   `backend/app/modules/plum/service.py`, breaking AVL vendor links, JSON export and vendor-referencing
   import with HTTP 500. **False today.** All four sites read
   `from app.modules.syerp.models import Partner as SyerpPartner` — an **alias** for the real class
   (`service.py:1669,2200,2670,2803`; `class Partner` at `backend/app/modules/syerp/models.py:48`).
   Fixed by `5c33ed8` *"fix: resolve plum vendor-path ImportError (Partner alias)"*
   (`git log -S"Partner as SyerpPartner" -- backend/app/modules/plum/service.py`). The missing-test
   gap that let it ship through four plans is also closed: `backend/tests/plum/test_avl.py` and
   `backend/scripts/verify_plum_vendor_paths.py` (the latter runs in CI's `verify-scripts`). Residual
   risk is UI-level only — PLUM-07 is `partial (runtime fix landed + backend guarded; UI UAT pending)`
   at `.zj/SRD.md:174`.
2. **Verification debt (narrowed, still real):** several PLUM requirements remain flow-level
   unverified — PLUM-04/05/09 `partial (unverified)`, PLUM-06 `partial (UI UAT pending)`, PLUM-08
   `partial` (`.zj/SRD.md:158,163,168,189,198`); the backends are guarded by tests and `verify_*`
   scripts, the *UI flows* are what nobody has walked. **`.zj/SRD.md` is the only authoritative
   requirement-status source** — neither this map nor `docs/features/requirements-progress.md`
   should be read as one.
3. **Stale project context (shrunk, and now self-contradictory):** root `CLAUDE.md`'s
   "Technology Stack" and "Architecture" sections have been rewritten and now describe the **live**
   FastAPI/React codebase accurately — but the ⚠ banner at `CLAUDE.md:36-42` still says all three of
   "Technology Stack", "Conventions" and "Architecture" describe "the legacy HTML prototypes only".
   That is true of `## Conventions` (`CLAUDE.md:100-149`) and false of the other two. The
   `## Suite Status` table (`CLAUDE.md:89-98`) is genuinely stale: it lists FLAN as
   "Prototype only, not yet re-platformed" and GELATO as "Planned" though both now ship backend +
   frontend code. (The Windows `E:\Projects\` paths an earlier edition flagged live in the
   *workspace-root* `/home/zack/Projects/CLAUDE.md:1-14`, not this project's `CLAUDE.md` — `grep -n 'E:' CLAUDE.md`
   returns nothing.)
4. **Service-layer monolith:** SYERP's 3,824-line `service.py` was split into a `syerp/service/`
   package (`chore-syerp-service-split`), and CRUMB and FLAN were built as packages from the start.
   `backend/app/modules/plum/service.py` at **3,058 lines** (`wc -l`) is the last monolith and still
   owes the same treatment (BACKLOG).
5. **CORRECTED — CI exists, and it is currently RED on `master`.** Earlier editions said
   *"No CI: no `.github/`, no pipeline config anywhere (verified)"*. **False since v4.0 Phase 3.**
   `.github/workflows/ci.yml` runs **six** jobs on every push and PR — `container-image`, `frontend`,
   `backend-lint`, `backend-tests`, `verify-scripts`, `verify-scripts-api` (`ci.yml:6-8,25,128,148,164,208,414`)
   — and all six are required status checks on `master`
   (`gh api repos/:owner/:repo/branches/master/protection --jq '.required_status_checks.contexts'`).
   **The live problem is the opposite of the old one:** `verify-scripts` globs `scripts/verify_*.py`
   (`ci.yml:272-281`), which includes `verify_qa_doc.py`, and that script **fails on `master`** —
   `.zj/QA.md`'s §3 accounts for 47 requirements while `.zj/SRD.md` has 58, so it reports
   `3 assertion(s) FAILED`
   (run 2026-08-19 with the repo root mounted; `git diff master...HEAD -- .zj/QA.md .zj/SRD.md` is
   empty, so this is inherited, not branch-local). Until `.zj/QA.md` absorbs the 11 missing
   requirements (`FLAN-02..11`, `NFR-9`), a red `verify-scripts` is the *expected* state and will
   mask the next real regression in that job.
6. **Tooling friction on Linux:** largely resolved — `scripts/uat.sh` (228 lines) is a bash port of
   the pwsh-only `scripts/uat.ps1`, so no `pwsh` is required. One Windows-era comment survives at
   `compose/compose.yml:74-79` (podman-compose 1.6.0 misreading an `E:\...` context as a git URL);
   it explains why the build file is named `Containerfile` and is still worth keeping.
7. **Repo weight from legacy artifacts:** `plum/` 33 MB + `flan/` 8.9 MB (`du -sh plum flan`),
   including 23 archived FLAN versions (`flan/archive/`) and a 2.6 MB JSON database — harmless but
   slows clones; consider git-lfs or pruning now that FLAN and PLUM are both re-platformed.
8. **Legacy prototype risks** (XSS via `innerHTML`, localStorage limits, advisory-only checkout
   locking) — moot for new work since the prototypes are frozen reference (D-ADOPT-4); historical
   detail archived at `archive/planning-gsd/codebase/CONCERNS.md`.
9. **Placeholder suite dirs** (`syerp/`, `crumb/`, `mousse/`, `crisp/`, `gelato/` at repo root) hold
   a `CLAUDE.md` and a `docs/tasks/_templates/` tree and **no source whatsoever** (35 files total,
   `find syerp crumb mousse crisp gelato -type f`) — the real code is `backend/app/modules/<name>/`.
   `flan/` and `plum/` are *not* placeholders: they hold the frozen HTML prototypes and their data.
10. **`alembic revision --autogenerate` proposes DROPPING seven live unique constraints.** Reproduced
    against the migrated dev DB at head `0018` on 2026-08-19 (autogenerate run in a scratch copy of
    `backend/`); the draft's `upgrade()` was exactly seven drops and nothing else:
    `uq_plum_part_number`, `uq_plum_part_one_released` (a partial unique *index*),
    `uq_syerp_gl_account_code`, `uq_syerp_inventory_item_code`, `uq_syerp_partner_code`,
    `uq_syerp_purchase_order_po_number`, `uq_syerp_stock_location_name`. They exist in Postgres but
    not in `Base.metadata`, so Alembic reads them as drift. Migration `0018`'s own draft contained
    all seven and they were deleted by hand before commit. **Never commit an autogenerated draft
    unread**; filed p2 in `.zj/BACKLOG.md` (grep `proposes DROPPING`).
11. **On FastAPI 0.138, `app.routes` no longer yields flattened `APIRoute`s.** `include_router()`
    results are wrapped: `Counter(type(r).__name__ for r in app.routes)` →
    `{'_IncludedRouter': 10, 'Route': 4}`, and a naive
    `[r for r in app.routes if isinstance(r, APIRoute) and '/flan' in r.path]` finds **zero**. Any
    route-inventory script written the old way passes **vacuously**. Assert against
    `app.openapi()["paths"]` or drive real HTTP instead (`backend/scripts/verify_flan_api.py` does
    the latter — 20 routes over real HTTP).
12. **The backend suite runs only from a container mounting the REPO ROOT, and `biznice_test` is not
    concurrency-safe.** `tests/test_compose_config.py:48` and `tests/test_containerfile_config.py:58`
    resolve the repo root as `Path(__file__).resolve().parents[2]`, so the dev overlay's
    `-v ../backend:/app` lands them on `/` and the 9 layout tests break (`3 failed, 236 passed, 6 errors`); `pytest` is absent from the image;
    and `tests/conftest.py` has no no-DB mode while compose `db` is never host-published, so the host
    venv cannot collect at all. The working invocation is in the Commands table. Separately, two
    concurrent runs against the same `TEST_POSTGRES_DB` destroy each other — the same suite gave
    `10 failed, 238 passed, 20 errors` while another run shared `biznice_test`, and `268 passed`
    moments later on a private `TEST_POSTGRES_DB`. Pass your own DB name when anyone else might be testing.
13. **`frontend/package.json:11`'s `test` script is bare `vitest` — watch mode.** Every
    non-interactive invocation must be `npm run test -- --run`, or the gate hangs forever instead of
    reporting. CI sidesteps it by calling `npx vitest run` directly (`ci.yml:145`) rather than fixing the script.
