# ROADMAP — BizNiceSweets Milestone 1: Foundation + PLUM

**Milestone:** Milestone 1 — Foundation + PLUM
**Created:** 2026-06-22
**Granularity:** Standard (6 phases)
**Coverage:** 24/24 v1 requirements mapped
**Structure:** Horizontal Layers (dependency-first)

---

## Phases

- [ ] **Phase 1: Project Scaffolding & Deployment** - Containerized repo, Postgres, Alembic migrations, Podman Compose
- [ ] **Phase 2: Authentication & Users** - OAuth2/JWT auth, session management, user accounts, role-based access
- [x] **Phase 3: App Shell & Settings** - Navigation shell, system settings, module enable/disable
- [x] **Phase 4: SYERP Core Hub** - Vendor CRUD + search, Customer CRUD + search, GL account skeleton
- [x] **Phase 5: PLUM Parts & Revisions** - Parts CRUD, search/filter, revision workflow and status (completed 2026-06-29)
- [ ] **Phase 6: PLUM BOM, Costing & Integration** - BOM tree/flat/where-used, vendor linking, cost roll-up, margin, import/export

---

## Phase Details

### Phase 1: Project Scaffolding & Deployment

**Goal**: Developers can spin up the full stack locally and the suite is deployable on self-hosted infrastructure
**Depends on**: Nothing (first phase)
**Requirements**: CORE-01, CORE-09
**Success Criteria** (what must be TRUE):

  1. Running `podman-compose up` starts all services (API, frontend, database) without manual intervention
  2. The FastAPI backend serves a health-check endpoint and auto-generated OpenAPI docs at `/docs`
  3. Alembic migrations run cleanly against a fresh PostgreSQL instance, producing the initial schema
  4. A fresh deploy reaches a known, repeatable state from a single compose command

**Plans**: 3 plans
Plans:

- [x] 01-01-PLAN.md — Backend core skeleton (config, DB, DeclarativeBase, module registry, SYERP hub stub, single Alembic history, health endpoints, pytest Wave 0 harness)
- [x] 01-02-PLAN.md — Frontend Vite + React + TS SPA skeleton (Tailwind v4, shadcn, React Router, TanStack Query, landing/health page)
- [x] 01-03-PLAN.md — Containerization + Podman Compose orchestration (multi-stage Dockerfile, auto-migrate entrypoint, SPA static serving, module profiles, dev overlay, .env)

### Phase 2: Authentication & Users

**Goal**: Users can securely access the suite and admins can manage who has access to what
**Depends on**: Phase 1
**Requirements**: CORE-02, CORE-03, CORE-04, CORE-05
**Success Criteria** (what must be TRUE):

  1. User can create an account and log in with email/password via OAuth2/JWT
  2. Authenticated session persists across page reloads and API requests without re-login (token refresh)
  3. Admin can create, edit, and deactivate other user accounts from the user management screen
  4. Admin can assign roles to users, and a user with an incorrect role is denied access to gated resources

**Plans**: 4 plans
Plans:

- [x] 02-01-PLAN.md — Auth foundation: deps, config, SQLAlchemy models, service helpers, Alembic migration, Wave 0 test harness
- [x] 02-02-PLAN.md — Login/refresh/logout/me endpoints, two-token flow with rotation + reuse detection, get_current_user/require_permission dependencies
- [x] 02-03-PLAN.md — First-admin seed, admin user CRUD + deactivation + role assignment (admin-gated), RBAC enforcement, audit log
- [x] 02-04-PLAN.md — Frontend: axios silent-refresh client, ProtectedRoute, Login page, admin User Management UI (+ human verify checkpoint)

**UI hint**: yes

### Phase 3: App Shell & Settings

**Goal**: Users see a coherent application with navigation, and admins can configure system-wide settings and which modules are active
**Depends on**: Phase 2
**Requirements**: CORE-06, CORE-07, CORE-08
**Success Criteria** (what must be TRUE):

  1. After login, user sees a navigation shell listing all enabled modules and can switch between them
  2. Admin can update system settings (company name, defaults) and changes persist across sessions
  3. Admin can toggle a module off, and its nav entry disappears for all users immediately
  4. Admin can re-enable a module and it reappears in the navigation shell

**Plans**: 3 plans
Plans:

- [x] 03-01-PLAN.md — Backend data layer: modules + settings ORM models, idempotent seeds, Alembic 0003, settings:manage permission, Wave 0 core test scaffold
- [x] 03-02-PLAN.md — Backend API: modules router (toggle + always-on guard) + settings router, main.py mount, /auth/me permissions extension; greens the core tests
- [x] 03-03-PLAN.md — Frontend AppShell (sidebar/topbar/mobile drawer), permission-filtered nav, Home, System Settings + Modules admin screens, Switch install (+ human-verify checkpoint)

**UI hint**: yes

### Phase 4: SYERP Core Hub

**Goal**: Users can manage the vendor and customer master data that all other modules depend on, with a chart-of-accounts skeleton in place
**Depends on**: Phase 3
**Requirements**: SYERP-01, SYERP-02, SYERP-03, SYERP-04, SYERP-05
**Success Criteria** (what must be TRUE):

  1. User can create, view, edit, and delete a vendor record
  2. User can search and filter the vendor list by name or attribute and see matching results instantly
  3. User can create, view, edit, and delete a customer record
  4. User can search and filter the customer list by name or attribute and see matching results instantly
  5. System exposes a chart-of-accounts skeleton (GL account structure) that is visible and browsable

**Plans**: 4 plans
Plans:

- [x] 04-01-PLAN.md — Backend foundation: Partner + GLAccount models, Alembic 0004, idempotent CoA seed, Wave 0 test scaffold
- [x] 04-02-PLAN.md — Backend API: partner CRUD/search/archive + audit + code-gen, GL browse endpoint, RBAC gating; greens backend tests
- [x] 04-03-PLAN.md — Frontend Vendor + Customer screens, shared PartnerSheet + ArchiveDialog, Wave 0 frontend tests
- [x] 04-04-PLAN.md — Frontend Chart-of-Accounts screen, App.tsx route wiring, human-verify checkpoint

**UI hint**: yes

### Phase 5: PLUM Parts & Revisions

**Goal**: Users can define and manage individual parts through their full lifecycle of revisions and statuses
**Depends on**: Phase 4
**Requirements**: PLUM-01, PLUM-02, PLUM-03
**Success Criteria** (what must be TRUE):

  1. User can create a new part with required attributes (number, description, type) and it appears in the parts list
  2. User can edit and delete an existing part record
  3. User can search and filter the parts list by part number, description, or status and see filtered results
  4. User can create a new revision on a part and advance it through the status workflow (e.g., Draft → Released → Obsolete)
  5. Revision history is visible on the part detail page showing all prior revisions and their statuses

**Plans**: 4 plans
Plans:
**Wave 1**

- [x] 05-01-PLAN.md — Backend data foundation: PlumPart/PlumPartRevision/tag tables, schemas, idempotent seed, Alembic 0005 + partial unique index, Wave 0 test scaffold

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 05-02-PLAN.md — Backend service + router: part CRUD/search, revision FSM (Draft→In Review→Released→Obsolete) with supersede-on-release, RBAC + audit; greens backend tests

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 05-03-PLAN.md — Frontend Parts list + PartSheet + ArchivePartDialog + PlumNav + Wave 0 smoke test

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 05-04-PLAN.md — Frontend Part Detail + revision timeline + New Revision/Advance Status dialogs + App.tsx wiring + human-verify checkpoint

**UI hint**: yes

### Phase 6: PLUM BOM, Costing & Integration

**Goal**: Users can build multi-level product structures, run cost analysis, link parts to vendors, and move data in and out of PLUM
**Depends on**: Phase 5
**Requirements**: PLUM-04, PLUM-05, PLUM-06, PLUM-07, PLUM-08, PLUM-09, PLUM-10
**Success Criteria** (what must be TRUE):

  1. User can add child parts to a parent part to build a multi-level BOM and view it as an expandable tree
  2. User can view a flat BOM with total quantity rolled up across all levels for each child part
  3. User can run where-used analysis on a part and see every assembly that directly or indirectly uses it
  4. User can link a part to one or more vendors from the SYERP vendor list (AVL), and those links are persisted
  5. User can set a cost on a part and see the cost roll up through the BOM tree to the top-level assembly
  6. User can view a margin analysis showing cost vs. price for a finished product
  7. User can export PLUM data as JSON or Excel and re-import it, restoring the same data set

**Plans**: TBD
**UI hint**: yes

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Project Scaffolding & Deployment | 0/3 | Planned | - |
| 2. Authentication & Users | 3/4 | In Progress|  |
| 3. App Shell & Settings | 3/3 | Complete | 2026-06-26 |
| 4. SYERP Core Hub | 4/4 | Complete | 2026-06-27 |
| 5. PLUM Parts & Revisions | 4/4 | Complete   | 2026-06-29 |
| 6. PLUM BOM, Costing & Integration | 0/0 | Not started | - |

---

## Coverage

| Requirement | Phase |
|-------------|-------|
| CORE-01 | Phase 1 |
| CORE-09 | Phase 1 |
| CORE-02 | Phase 2 |
| CORE-03 | Phase 2 |
| CORE-04 | Phase 2 |
| CORE-05 | Phase 2 |
| CORE-06 | Phase 3 |
| CORE-07 | Phase 3 |
| CORE-08 | Phase 3 |
| SYERP-01 | Phase 4 |
| SYERP-02 | Phase 4 |
| SYERP-03 | Phase 4 |
| SYERP-04 | Phase 4 |
| SYERP-05 | Phase 4 |
| PLUM-01 | Phase 5 |
| PLUM-02 | Phase 5 |
| PLUM-03 | Phase 5 |
| PLUM-04 | Phase 6 |
| PLUM-05 | Phase 6 |
| PLUM-06 | Phase 6 |
| PLUM-07 | Phase 6 |
| PLUM-08 | Phase 6 |
| PLUM-09 | Phase 6 |
| PLUM-10 | Phase 6 |

**Total mapped: 24/24**

---

*Roadmap created: 2026-06-22*
*Milestone: 1 — Foundation + PLUM*
