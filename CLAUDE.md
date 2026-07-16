## Project

**BizNiceSweets**

BizNiceSweets is an open-source, open-core, self-hostable **modular business suite for small-to-medium manufacturers** — built first to run the user's own healthcare-simulation-device manufacturing business, and designed to be useful to any business that designs, manufactures, and sells physical products. It is a single application made of installable modules ("suites" with sweet names) over a shared database, deployable on the user's own infrastructure with offline capability.

The seven suites: **SYERP** (ERP/financials/inventory — the hub), **PLUM** (Product Lifecycle Management), **FLAN** (Project Management), **MOUSSE** (Manufacturing Execution), **CRUMB** (CRM), **GELATO** (Warehouse Management), **CRISP** (Quality Management). PLUM (v54) and FLAN (v24) already exist as working single-file HTML prototypes; the target architecture re-platforms them and adds the rest.

**Core Value:** A small manufacturer can run their real product lifecycle — design → projects → purchasing → manufacturing → quality → fulfillment — on a suite they **self-host and own**, with no per-seat SaaS lock-in. If everything else is deferred, the suite must remain something one shop can actually deploy and operate on its own.

### Constraints

- **Tech stack (backend):** FastAPI + SQLAlchemy 2.0 + PostgreSQL — Python ecosystem, auto OpenAPI docs, mature ORM/migrations.
- **Tech stack (frontend):** React 18+ + TypeScript + Tailwind CSS + shadcn/ui; state via Zustand or TanStack Query — modern, well-supported, permissively licensed.
- **Deployment:** Podman / Podman Compose (Docker CLI compatible) — self-hostable, rootless containers.
- **Architecture:** Modular monolith — installable modules over one shared PostgreSQL database; modules integrate via foreign keys with **SYERP as the hub**.
- **Offline:** Must support offline capability (Service Worker + IndexedDB) and sync on reconnect — a later cross-module concern but a standing constraint.
- **Licensing:** Open core — core suite open source (permissive deps only), premium add-ons possible.
- **Compliance posture:** Medical-device origin means audit trail and traceability are first-class concerns, designed for even before CRISP ships.

## ZJ Workflow (planning source of truth)

This project is managed with the **ZJ workflow**. All planning, requirements, and roadmap
authority lives in **`.zj/`** — read it before planning or implementing:

- `.zj/PROJECT.md` — vision, users, constraints, current reality
- `.zj/PRD.md` / `.zj/SRD.md` — requirements with statuses and evidence (IDs: CORE-*, SYERP-*, PLUM-*, FLAN-*, MOUSSE-*, …)
- `.zj/ROADMAP.md` — shipped phases (with evidence) and pending phases
- `.zj/STATE.md` — current position and the exact next command
- `.zj/DECISIONS.md`, `.zj/BACKLOG.md`, `.zj/codebase/MAP.md`

Check `/zj:status` for where things stand. Prior planning systems are **archived** (history
only, never authoritative): GSD at `archive/planning-gsd/`, the 2025 program roadmap and
decision log at `archive/planning-docs/`.

> **⚠ Stale sections below:** the "Technology Stack", "Conventions", and "Architecture"
> sections of this file describe the **legacy HTML prototypes only** (frozen reference —
> see `.zj/DECISIONS.md` D-ADOPT-4). The live codebase is the FastAPI backend (`backend/`)
> and React 19 frontend (`frontend/`) — see `.zj/codebase/MAP.md` for the accurate map,
> stack, and verified commands. Follow the legacy conventions only when reading
> `plum/app/` or `flan/app/`.

## Technology Stack

This section describes the **live codebase** — the FastAPI backend (`backend/`) and React
frontend (`frontend/`). `.zj/codebase/MAP.md` is the authoritative, evidence-cited source
for the current stack, directory layout, and verified commands; consult it when in doubt.
The vanilla-JS / CDN / localStorage details in the "Legacy prototypes" subsection apply
**only** when reading `plum/app/` or `flan/app/`.

## Languages
- Python 3.13 — backend application language (`backend/`)
- TypeScript 6.0 — frontend application language (`frontend/`)
- SQL (PostgreSQL 17 dialect) — schema managed through Alembic migrations
- HTML/CSS — frozen legacy prototypes only (`plum/app/`, `flan/app/`)

## Backend
- **Framework:** FastAPI 0.138.0 — app factory in `backend/app/main.py`, auto OpenAPI docs, routers mounted under `/api/v1`
- **ORM:** SQLAlchemy 2.0.51, async, over asyncpg 0.31.0
- **Migrations:** Alembic 1.18.4 — revisions in `backend/alembic/versions/`, run at container boot
- **Config/validation:** Pydantic + pydantic-settings 2.14.2 (secrets typed `SecretStr`)
- **Auth:** PyJWT 2.13.0 (two-token access/refresh), pwdlib[argon2] 0.3.0 for hashing
- **Import/export:** openpyxl 3.1.5 for Excel (.xlsx)
- **Dev/test:** pytest 9.1.1 + pytest-asyncio 1.4.0 (asyncio auto), httpx 0.28.1, ruff 0.15.18 (line-length 100)

## Frontend
- **Framework:** React 19.2.7 (SPA) with react-router-dom 7.18.0
- **Language/build:** TypeScript 6.0.3, Vite 8.1.0 (`tsc -b && vite build`)
- **Styling:** Tailwind CSS 4.3.1 via `@tailwindcss/vite` (no `tailwind.config` file); shadcn/ui-style primitives (Radix + cva) generated into `src/components/ui/`
- **Server state:** TanStack Query 5.101.1; single axios 1.18.1 client (`src/api/client.ts`) handles tokens
- **UX:** sonner for toasts
- **Dev/test:** Vitest 4.1.9 + Testing Library + jsdom; Prettier 3.8.4. **Both lint gates are currently non-functional** (BACKLOG p1): ESLint 10 is flat-config-only but the repo still ships `.eslintrc.cjs`, the `lint` script passes the removed `--ext` flag, and the `@typescript-eslint` parser/plugin packages are absent from `devDependencies`; `ruff` is pinned in `requirements-dev.txt` but not installed in `backend/.venv`. Correctness rests on the test suites and `backend/scripts/verify_*.py`, not on lint.

## Database & Deployment
- **Database:** PostgreSQL 17 (`postgres:17-alpine`) — one shared database for all modules, never port-mapped to the host
- **Containers:** Podman / podman-compose (Docker CLI compatible); `compose/compose.yml` (prod) + `compose/compose.dev.yml` (dev overlay: Vite HMR, `--reload`); multi-stage `Containerfile` at repo root; pinned bases `python:3.13-slim`, `node:22-slim`
- **Boot sequence:** `backend/entrypoint.sh` waits for Postgres, runs `alembic upgrade head`, then startup seeds run idempotently; the built React app is served from `frontend/dist` by a catch-all mounted last so it never swallows `/api/*`

## Configuration
- Environment-driven (12-factor); required secrets have **no defaults** — the app refuses to start without them: `POSTGRES_PASSWORD`, `JWT_SECRET`, `BNS_ADMIN_PASSWORD` (see `.env.example`; `.env` is not git-tracked)
- Backend config surface in `backend/app/core/config.py`; module toggles/settings via `modules_router.py` / `settings_router.py`

## Legacy prototypes (frozen reference — `plum/app/`, `flan/app/` only)
- Single-file vanilla ES6+ HTML apps, no build step, no framework, no toolchain — open directly in a modern browser
- No npm/pip, no lockfile; third-party libs loaded via CDN at runtime: SheetJS 0.18.5 (PLUM, FLAN — Excel/CSV), jsPDF 2.5.1 (FLAN — PDF)
- Persistence is client-side: session/UI state in `localStorage`; canonical data as manually imported/exported JSON (`plum/data/plm_database.json`, `flan/data/Crisis.json`)
- Frozen per `.zj/DECISIONS.md` D-ADOPT-4; the platform re-hosts their features and supersedes them

## Suite Status
| Suite | Live location | Status |
|-------|---------------|--------|
| SYERP (ERP — hub) | `backend/app/modules/syerp/`, `frontend/src/routes/syerp/` | Building (partners + GL; inventory + purchasing added in Phase 8 / v2.0) |
| PLUM (PLM) | `backend/app/modules/plum/`, `frontend/src/routes/plum/` | Building (parts, revisions, BOM, costing, AVL, import/export); legacy `plum/app/plm_v54.html` |
| FLAN (Project Mgmt) | — (legacy `flan/app/prj-mgmt-v24.html`) | Prototype only, not yet re-platformed |
| CRUMB (CRM) | `backend/app/modules/crumb/`, `frontend/src/routes/crumb/` | Building (leads → opportunities (stage FSM) → quotes (PLUM-derived line pricing + status FSM) + append-only communication log; verified Phase 11a — sales orders + soft-reservation deferred to 11b) |
| MOUSSE (MES) | `backend/app/modules/mousse/`, `frontend/src/routes/mousse/` | Building (materials-only work orders: create/release/issue/complete, WIP clears to zero; verified Phase 10) |
| CRISP (QMS) | — | Planned |
| GELATO (WMS) | — | Planned |

## Conventions

## Language & Style
- **Vanilla ES6+ JavaScript**, inline in `<script>` blocks. No modules (`import`/`export`), no TypeScript, no JSX.
- **Variable declarations:** `const` is dominant (~2,900 occurrences in PLUM), `let` for mutable locals/state (~260). `var` is essentially absent in JS (raw counts are inflated by CSS `var(--token)` custom properties).
- **Strings:** template literals are used heavily for HTML generation (`` `<div>${x}</div>` ``).
- **Semicolons:** present (conventional JS).
- **Indentation:** inconsistent — generated/edited sections vary between compact (1–2 space) and standard indentation within the same file. No formatter enforces it.
## Naming
| Element | Convention | Example |
|---------|-----------|---------|
| Domain module objects | `PascalCase` object literal | `const Parts = { ... }`, `const ECO`, `const RFQ` |
| Global state container | `UPPER`/`PascalCase` const | `const DB = { ... }` |
| Functions | `camelCase`, verb-first | `sortParts()`, `checkoutDatabase()`, `markUnsaved()` |
| Render functions | `render` + `PascalCase` view name | `renderDashboard()`, `renderBomView()`, `renderWhereUsedView()` |
| Prompt/handler functions | `prompt`/`toggle`/`update` prefixes | `promptForUsername()`, `toggleSort()`, `updateSyncStatus()` |
| Local variables | `camelCase` | `partNumber`, `selectedProduct` |
| JSON data keys | `camelCase` | `checkedOutBy`, `costAvg`, `countryOfOrigin` |
| localStorage keys | suite-prefixed | PLUM `plm*` (`plmUsername`), FLAN `prj_mgmt_*` |
| CSS classes / custom props | `kebab-case` / `--token` | `--color`, `.breadcrumb-nav` |
## Code Organization Patterns
- **Namespace-by-object:** each domain concern is a single `const Name = { method(){}, ... }` object literal grouping its logic. PLUM has 30+ such modules (`Parts`, `BomConfigurations`, `Compliance`, `VendorPerformance`, `SupplyChainRisk`, …). This is the primary modularization unit in lieu of files/imports.
- **Section banners:** CSS and JS are divided with comment banners — `/* ===== HEADER ===== */`, `/* ===== TABLES ===== */`, and `// STATE MANAGEMENT`-style markers — used to navigate the large single files.
- **Render-everything orchestration:** a single `renderAll()` calls all per-view render functions; views own their DOM region and rebuild it via `innerHTML`.
- **String-template rendering:** views build HTML as template-literal strings and assign to `element.innerHTML` (no DOM node construction APIs, no framework).
## Error Handling
- **`try/catch` around risky operations** — primarily JSON parsing, `localStorage` access, and Excel/PDF import-export. PLUM: ~22 try/catch pairs; FLAN: ~8 try / ~10 catch.
- **User feedback via native dialogs:** `alert()`, `confirm()`, and `prompt()` are used directly (PLUM ~53 call sites, FLAN ~7) for confirmations, errors, and simple input (e.g. `promptForUsername`, delete confirmations). There is no toast/notification abstraction shared across suites.
- No centralized error logger; failures are surfaced inline at the call site.
## DOM & UI
- Event handling is mostly **inline `onclick`/`oninput` attributes** in generated HTML strings calling global functions.
- Heavy reliance on `innerHTML` for both reads and writes (PLUM 145, FLAN 117 occurrences) — see `archive/planning-gsd/codebase/CONCERNS.md` for the XSS/perf implications.
- Charts are **hand-rolled inline SVG** (PLUM `Charts` object; FLAN `renderPieChart`/`renderBarChart`) rather than a charting library.
## Persistence Conventions
- Session/UI state → `localStorage` under a suite-specific prefix.
- Canonical data → JSON file, imported/exported explicitly by the user (SheetJS for Excel/CSV, native JSON for the database).
- PLUM adds advisory checkout metadata (`checkedOutBy`, `checkedOutAt`) to support manual multi-user sync.
## Commit & Workflow Conventions (from `CLAUDE.md`)
- **Conventional commits:** `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
- **Do NOT** include "co-authored", "powered by", or "generated with Claude" lines in commit messages (explicit project rule).
- Branch naming: `feature-*`, `bugfix-*`, `hotfix-*`, `chore-*`.
- Every code-changing task must have a checklist file at `docs/tasks/{branch-name}.md`; update it before each commit.
- `CHANGELOG.md` is generated from commits — never edit it directly.
- Feature work must reference requirement IDs and update `docs/features/requirements-progress.md`.
## What's Absent (by design)
- No linter / formatter / style config (no ESLint, Prettier, `.editorconfig`).
- No type system.
- No build or bundling step — code must run directly in the browser.
- No shared/common library across suites — patterns are duplicated per suite.

## Architecture

This section describes the **live architecture** — the FastAPI backend + React frontend
platform. `.zj/codebase/MAP.md` holds the authoritative, evidence-cited map. The legacy
single-file prototype architecture is captured in the final "Legacy prototypes" subsection
and applies **only** to `plum/app/` and `flan/app/`.

## Architectural Pattern
- **Modular monolith over one shared PostgreSQL database, with SYERP as the hub** — installable modules integrate via foreign keys, exactly per the stated constraint and already realized in code.
- Backend and frontend ship as one deployable unit: the FastAPI app serves its own `/api/v1` surface and also serves the built React SPA from `frontend/dist` (catch-all mounted last so it never swallows API routes).
- Modules self-register at import time and are mounted through a central registry, so adding a suite is additive rather than invasive.

## Backend structure
- **Entry point:** `backend/app/main.py` — FastAPI app factory. Startup: entrypoint waits for Postgres and runs `alembic upgrade head`, lifespan runs idempotent seeds, modules self-register, then the SPA catch-all mounts last.
- **Module registry:** each module package's `__init__.py` calls `registry.register(module)`; `mount_all(app)` wires every router under `/api/v1` (`backend/app/core/registry.py`). Registered today: `syerp`, `plum`, `auth`.
- **Module layout (repeated pattern):** `backend/app/modules/<name>/{__init__,models,schemas,router,service}.py`. Business logic lives in `service.py`; routers are thin. Seeding is per-module but **not uniformly named**: `auth/seed.py` and `plum/seed.py`, but SYERP splits its into `syerp/coa_seed.py` and `syerp/inventory_seed.py` — all wired from `backend/app/core/seed.py`.
- **Cross-cutting platform code:** `backend/app/core/` — config (pydantic-settings, `SecretStr`), async engine/session (`db.py`), module-toggle + settings routers, seed orchestration (`seed.py`).
- **Cross-module integration via FKs:** PLUM AVL rows reference SYERP partners — the concrete realization of "SYERP as the hub."
- **Migrations:** Alembic revisions in `backend/alembic/versions/` are the schema source of truth; every model change adds one.

## Frontend structure
- SPA in `frontend/src/` — `main.tsx` → `App.tsx` route table; `components/AppShell.tsx` + Sidebar/Topbar shell; per-suite route folders (`routes/plum/`, `routes/syerp/`, `routes/admin/`) each with a local `components/` subfolder.
- Server state via TanStack Query hooks (`hooks/useAuth.ts`, `useModules.ts`, `useSettings.ts`); a single axios client (`src/api/client.ts`) carries all API traffic and token handling.
- shadcn/ui primitives in `components/ui/`; `cn()` helper in `src/lib/utils.ts`.

## Data Flow
- Client calls `/api/v1/*` through the axios client → thin FastAPI router → module `service.py` (business logic) → async SQLAlchemy session → PostgreSQL. Responses are Pydantic-validated schemas; TanStack Query caches and revalidates on the client.

## Auth & Collaboration Model
- Multi-user by design: JWT two-token model (15-min access / 7-day refresh), Argon2 password hashing, a seeded first admin (`BNS_ADMIN_*` env), and RBAC enforced server-side (`backend/tests/auth/test_rbac.py`).
- Persistence and concurrency are the database's responsibility — no file checkout/checkin dance (that was a legacy-prototype workaround).

## Architectural Constraints
- **Permissive licensing only** — open-core suite; dependencies must stay permissively licensed.
- **Self-hostable** — must deploy on the user's own infrastructure via Podman/podman-compose, rootless.
- **Audit trail & traceability are first-class** (medical-device origin), designed for even before CRISP ships.
- **Offline capability** (Service Worker + IndexedDB, sync on reconnect) is a standing cross-module constraint, not yet built.
- **Split PLUM's service layer before it metastasizes** — `plum/service.py` is ~3,000 lines; keep new suites thin.

## Entry Points
- **Full dev stack:** `./scripts/uat.ps1` (requires `pwsh`), or `podman-compose -f compose/compose.yml -f compose/compose.dev.yml up`.
- **Prod stack:** `podman-compose -f compose/compose.yml up -d` (needs `.env` from `.env.example`).
- **Backend:** `pytest` / `ruff check .` / `alembic upgrade head` from `backend/`.
- **Frontend:** `npm run dev` / `npm run build` / `npm run lint` / `npm run test` from `frontend/`.

## Legacy prototypes (frozen reference — `plum/app/`, `flan/app/` only)
- All markup, styles, and logic live in a single `.html` file opened directly in the browser; no framework, no build step, no server.
- State is held in module-level JS objects (`const DB = {}`, domain namespaces like `Parts`/`ECO`/`RFQ`); views rebuild via string-template `innerHTML` orchestrated by `renderAll()`.
- Persistence is dual: session/UI state in `localStorage`; canonical data as manually imported/exported JSON (`plum/data/plm_database.json`, `flan/data/Crisis.json`). PLUM adds an advisory checkout/checkin convention for SharePoint-hosted manual sync — cooperative, not enforced.
- Frozen per `.zj/DECISIONS.md` D-ADOPT-4; a historical deep-dive is archived at `archive/planning-gsd/codebase/ARCHITECTURE.md`.

## Related Docs
- `.zj/codebase/MAP.md` — authoritative current map, stack, commands, hotspots, and concerns
- `docs/features/plum/architecture.md`, `docs/features/flan/architecture.md` — per-suite (legacy) architecture detail
- `docs/features/INDEX.md` — suite relationships and integration vision

## Project Skills

| Skill | Description | Path |
|-------|-------------|------|
| code-docs | Analyze code documentation across multiple languages (Python, JavaScript/TypeScript, C/C++, C#, Go, Rust). Use when (1) auditing documentation coverage, (2) finding undocumented code, (3) generating doc templates, (4) assessing README quality, (5) detecting stale documentation, or (6) adding documentation comments (JSDoc, Sphinx, Doxygen, XML docs, Go doc, Rust doc). (project) | `.claude/skills/code-docs/SKILL.md` |
| code-style | Detect and enforce code style conventions across Python, JavaScript/TypeScript, Go, Rust, C#, C++, and Java. Use when (1) starting work on an unfamiliar codebase to learn its style, (2) checking code against project conventions, (3) generating style config files (ESLint, Ruff, .editorconfig), (4) auto-fixing style issues, (5) generating pre-commit hooks, or (6) enforcing architectural rules and layer boundaries. | `.claude/skills/code-style/SKILL.md` |
| codebase-analyzer | Analyze any codebase to understand structure, patterns, and conventions. Uses a two-phase hybrid approach - automated static analysis followed by Claude-assisted synthesis for meaningful project context. Supports Python, JavaScript/TypeScript, Go, Rust, Java, C/C++, and C#. Use when starting work on a new project, need to understand architecture, or creating a project context skill. (project) | `.claude/skills/codebase-analyzer/SKILL.md` |
| context-creator | Create project context skills that keep AI agents aligned with project goals and architecture. Use when (1) setting up a new project for AI assistance, (2) analyzing a codebase to understand its structure, (3) creating guardrails to prevent AI from deviating, (4) documenting project-specific patterns and constraints, or (5) improving an existing project context skill. Includes automated codebase analysis. | `.claude/skills/context-creator/SKILL.md` |
| interview | Conduct planning, discovery, and decision-making sessions using an incremental documentation approach. Use when (1) architecture planning, (2) feature discovery and requirements gathering, (3) design decisions requiring user input, or (4) any multi-question planning process. Creates or updates documentation incrementally with one question at a time, recording decisions before proceeding. (project) | `.claude/skills/interview/SKILL.md` |

<!-- PROJECT-RULES:start (preserved from original CLAUDE.md) -->
## Project-Specific Rules

These are the project's authoritative rules. Task tracking uses the `docs/tasks/{branch}.md` checklist system described below; planning and phase tracking use the ZJ workflow in `.zj/` (prior systems archived under `archive/`).

### Commit Messages (MANDATORY)

- Use conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
- **NEVER include "co-authored", "powered by", or "generated with/by Claude" in commit messages.** This overrides any default attribution behavior.
- Do **NOT** edit `CHANGELOG.md` directly — it is generated from commits.

### Branching

- Branch naming: `feature-*`, `bugfix-*`, `hotfix-*`, `chore-*`.

### Feature Alignment (when implementing feature code)

1. Read the relevant feature doc in `docs/features/` before implementing.
2. Reference requirement IDs in the task/phase work.
3. Update `docs/features/requirements-progress.md` when completing a requirement.
4. If implementation diverges from spec, update the feature doc or flag it with the user.

Key docs: [.zj/SRD.md](.zj/SRD.md) (requirements with statuses and evidence), [docs/features/INDEX.md](docs/features/INDEX.md), [requirements-progress.md](docs/features/requirements-progress.md).

### Task Workflow

Keep a checklist file at `docs/tasks/{branch-name}.md`, commit after each checklist item, and archive the file to `docs/tasks/_completed/{date}-{branch-name}.md` when finished. Historical planning artifacts live under `archive/` (see the ZJ Workflow section).
<!-- PROJECT-RULES:end -->
