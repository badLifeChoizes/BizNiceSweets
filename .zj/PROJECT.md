# PROJECT — BizNiceSweets

Adopted into ZJ: 2026-07-04 (brownfield adoption; prior system: GSD, archived at `archive/planning-gsd/`)

## Vision

An open-source, open-core, **self-hostable modular business suite for small-to-medium
manufacturers** — built first to run the owner's healthcare-simulation-device manufacturing
business, and designed to be useful to any business that designs, manufactures, and sells
physical products. One application, installable modules ("suites" with sweet names) over one
shared PostgreSQL database, deployable on the owner's own infrastructure.

**Core value:** a small manufacturer can run their real product lifecycle — design → projects
→ purchasing → manufacturing → quality → fulfillment — on a suite they self-host and own,
with no per-seat SaaS lock-in. If everything else is deferred, the suite must remain something
one shop can actually deploy and operate on its own.

## The Seven Suites

| Suite | Domain | Status (2026-07-04) |
|-------|--------|---------------------|
| SYERP | ERP — partners, GL, (later: inventory, POs, AP/AR) — **the hub** | Core shipped (Phase 4); extended = next milestone |
| PLUM | Product Lifecycle Management | Ported to new stack (Phases 5–6); gap-closure phase pending |
| FLAN | Project Management | HTML prototype only; port deferred to a later milestone |
| MOUSSE | Manufacturing Execution | Planned — next milestone with SYERP extended |
| CRUMB | CRM | Planned |
| GELATO | Warehouse Management | Planned |
| CRISP | Quality Management | Planned |

## Users

- **Primary:** the owner's manufacturing shop (medical-simulation devices) — a small team
  that deploys the suite itself and uses it daily.
- **Secondary:** any SMB manufacturer wanting a self-hosted, integrated, open-source
  alternative to per-seat SaaS (target of the eventual public open-source release).

## Current Reality (evidence-based)

The re-platform is **substantially built** — this is no longer a prototypes-plus-plans repo:

- Live backend: FastAPI 0.138 + SQLAlchemy 2.0 (async) + PostgreSQL 17, 6 Alembic
  migrations, modular-monolith module registry (`backend/app/`).
- Live frontend: React 19 + TypeScript + Vite + Tailwind 4 + shadcn/ui + TanStack Query
  (`frontend/src/`).
- Deployment: Podman Compose (`compose/compose.yml`), auto-migrating container entrypoint.
- Shipped: auth/RBAC, app shell with module toggles, SYERP partners + chart of accounts,
  PLUM parts/revisions/BOM/costing/AVL/import-export.
- Two known runtime blockers (`SyerpPartner` ImportError; lexicographic part-number MAX)
  keep v1.0 from closing — Phase 7 (pending) fixes them. See SRD statuses.
- Legacy HTML prototypes (`plum/app/plm_v54.html`, `flan/app/prj-mgmt-v24.html`) are
  **frozen reference implementations** — domain-logic reference for porting, no further
  development or bug fixes (owner decision, 2026-07-04).

Full codebase detail: `.zj/codebase/MAP.md`.

## Constraints

- **Backend:** FastAPI + SQLAlchemy 2.0 + PostgreSQL.
- **Frontend:** React + TypeScript + Tailwind CSS + shadcn/ui; server state via TanStack Query.
- **Deployment:** Podman / Podman Compose, rootless containers, single-command deploy.
- **Architecture:** modular monolith — one shared PostgreSQL database, modules integrate via
  foreign keys, **SYERP is the hub**.
- **Offline:** offline capability (Service Worker + IndexedDB, sync on reconnect) is a
  standing constraint for a later cross-module phase.
- **Licensing:** open core — core suite open source with permissive deps only.
- **Compliance posture:** medical-device origin → audit trail and traceability are
  first-class from the start (audit events already written by auth/SYERP/PLUM services),
  designed for even before CRISP ships.

## Workflow Notes

- Conventional commits; **never** add "co-authored"/"generated with Claude" lines; never
  edit `CHANGELOG.md` directly.
- Branch naming `feature-*` / `bugfix-*` / `hotfix-*` / `chore-*`; per-branch checklist at
  `docs/tasks/{branch}.md`.
- Feature work references SRD requirement IDs (see `.zj/SRD.md`).
