# BizNiceSweets

## What This Is

BizNiceSweets is an open-source, open-core, self-hostable **modular business suite for small-to-medium manufacturers** — built first to run the user's own healthcare-simulation-device manufacturing business, and designed to be useful to any business that designs, manufactures, and sells physical products. It is a single application made of installable modules ("suites" with sweet names) over a shared database, deployable on the user's own infrastructure with offline capability.

The seven suites: **SYERP** (ERP/financials/inventory — the hub), **PLUM** (Product Lifecycle Management), **FLAN** (Project Management), **MOUSSE** (Manufacturing Execution), **CRUMB** (CRM), **GELATO** (Warehouse Management), **CRISP** (Quality Management). PLUM (v54) and FLAN (v24) already exist as working single-file HTML prototypes; the target architecture re-platforms them and adds the rest.

## Core Value

A small manufacturer can run their real product lifecycle — design → projects → purchasing → manufacturing → quality → fulfillment — on a suite they **self-host and own**, with no per-seat SaaS lock-in. If everything else is deferred, the suite must remain something one shop can actually deploy and operate on its own.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. The HTML prototypes prove the domain logic; they are not the target stack. -->

- ✓ PLUM domain logic proven in prototype (parts, BOMs, where-used, cost roll-up, ECO, compliance) — `plum/app/plm_v54.html`
- ✓ FLAN domain logic proven in prototype (projects, phases, tasks, timeline, budgets) — `flan/app/prj-mgmt-v24.html`

### Active

<!-- Current milestone scope: Milestone 1 = Foundation + PLUM port. -->

**Milestone 1 — Foundation + PLUM**

- [ ] Project scaffolding on the target stack (FastAPI + React/TypeScript)
- [ ] Database schema and migrations (SQLAlchemy 2.0 + Alembic)
- [ ] Authentication (OAuth2 / JWT), user and role management
- [ ] Settings/configuration system + module enable/disable
- [ ] SYERP core: Vendors CRUD, Customers CRUD, basic general-ledger structure
- [ ] Podman Compose deployment + basic UI shell with navigation
- [ ] PLUM port: parts management (CRUD, search, filter), part revisions & status workflow
- [ ] PLUM port: BOM tree view + flat view with quantity roll-up, where-used analysis
- [ ] PLUM port: part-to-vendor linking (FK → SYERP.vendors), pricing & cost roll-up, margin analysis
- [ ] PLUM port: data import/export (JSON, Excel)

### Out of Scope

<!-- For Milestone 1. Carried in the long-term vision but explicitly deferred. -->

- Re-porting FLAN to the new stack — deferred to a later milestone (HTML prototype covers project mgmt meanwhile)
- MOUSSE, CRUMB, GELATO, CRISP modules — later phases/milestones
- PLUM advanced features (document management/file upload, ECO workflow automation, RFQ, supply-chain risk) — beyond core port
- Real-time multi-user collaboration beyond what auth + shared DB provide
- Cloud/hosted SaaS offering — product is self-hosted by design

## Context

- **Origin:** Built to run a healthcare-simulation-device manufacturing business; medical-device context makes quality/regulatory (traceability, CAPA, device history records) unusually high-value, even though CRISP lands in a later phase.
- **Existing assets:** Two mature single-file HTML apps (PLUM ~31k lines, FLAN ~11.5k lines) using vanilla JS, `localStorage`, and JSON import/export. These are the functional reference for the rewrite, not the deployment target.
- **Codebase map:** `.planning/codebase/` (ARCHITECTURE, STACK, STRUCTURE, CONVENTIONS, INTEGRATIONS, CONCERNS, TESTING) describes the current prototypes.
- **Existing planning:** `docs/ROADMAP.md` (5-phase program roadmap), `docs/features/` (221 documented requirements across suites), `docs/decisions.md` (5 architecture decisions), `docs/interviews/` (planning interviews). GSD milestones will draw scope from these.
- **Strategy chosen:** Full rewrite of all suites into the target stack, in **dependency-first order** (Foundation → Product Dev → Operations → Customer/Logistics → Quality). A value-first reorder was considered and explicitly rejected.

## Constraints

- **Tech stack (backend):** FastAPI + SQLAlchemy 2.0 + PostgreSQL — Python ecosystem, auto OpenAPI docs, mature ORM/migrations.
- **Tech stack (frontend):** React 18+ + TypeScript + Tailwind CSS + shadcn/ui; state via Zustand or TanStack Query — modern, well-supported, permissively licensed.
- **Deployment:** Podman / Podman Compose (Docker CLI compatible) — self-hostable, rootless containers.
- **Architecture:** Modular monolith — installable modules over one shared PostgreSQL database; modules integrate via foreign keys with **SYERP as the hub**.
- **Offline:** Must support offline capability (Service Worker + IndexedDB) and sync on reconnect — a later cross-module concern but a standing constraint.
- **Licensing:** Open core — core suite open source (permissive deps only), premium add-ons possible.
- **Compliance posture:** Medical-device origin means audit trail and traceability are first-class concerns, designed for even before CRISP ships.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Hybrid open-source business suite (7 integrated suites) | One ecosystem covering the full product lifecycle for SMB manufacturers | ✓ Good |
| Modular monolith over shared PostgreSQL, SYERP as hub | Simpler ops than microservices; FK integration is sufficient at this scale | — Pending |
| Full rewrite of all suites into FastAPI + React stack | Multi-user, server-hosted, integrated DB; HTML prototypes can't scale to a shared team system | — Pending |
| Dependency-first phase order (Foundation → PLUM/FLAN → ops → customer → quality) | Clean integration story; build the hub everything FKs into first | — Pending (value-first reorder considered & rejected) |
| Milestone 1 = Foundation + PLUM port | Thin foundation paired with the first real module so M1 ends with a usable tool, not just plumbing | — Pending |
| Manufacturing (work centers/routing) lives in MOUSSE, not PLUM | PLUM = product development; released products hand off to MOUSSE for manufacturing | — Pending |
| Self-hosted + offline-capable, open-core licensing | User ownership, no SaaS lock-in, contributor-friendly | — Pending |
| Server stack supersedes earlier client-side DataService/localStorage plan | Decision 4 (2025-12-20) chose a swappable client data layer; the 2025-12-21 roadmap moved to a real backend, which this project adopts | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-22 after initialization*
