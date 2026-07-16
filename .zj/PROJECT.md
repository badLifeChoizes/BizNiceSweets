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

| Suite | Domain | Status (2026-07-16, post-v2.0) |
|-------|--------|--------------------------------|
| SYERP | ERP — partners, inventory, POs, GL, AP, reporting — **the hub** | Core (Phase 4) + operations shipped (Phases 8/9: inventory, purchasing, double-entry GL, AP, financial statements). AR (SYERP-13) = v3.0 |
| PLUM | Product Lifecycle Management | Ported + shipped v1.0 (Phases 5–7: parts, revisions, BOM, costing, AVL, import/export). Advanced features (PLUM-11..16) = later milestone |
| MOUSSE | Manufacturing Execution | Materials-only work-order core shipped (Phase 10, v2.0). Routing/work-centers, labor/overhead, shop-floor view deferred (D-P10-1) |
| CRUMB | CRM | Planned — **v3.0 (next milestone)** |
| GELATO | Warehouse Management | Planned — **v3.0 (next milestone)** |
| FLAN | Project Management | HTML prototype only; port deferred to a later milestone |
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
  PLUM parts/revisions/BOM/costing/AVL/import-export, SYERP inventory + purchasing (v2.0
  Phase 8).
- **Milestone v1.0 closed 2026-07-09.** The Phase-7 blockers (`SyerpPartner` ImportError;
  lexicographic part-number MAX) are fixed and proven live. The milestone audit found and
  fixed one further major defect the phase verifications had missed (Where-Used labelled every
  parent "Direct parent" — see `.zj/MILESTONE-v1.0-AUDIT.md`, gap G1).
- Legacy HTML prototypes (`plum/app/plm_v54.html`, `flan/app/prj-mgmt-v24.html`) are
  **frozen reference implementations** — domain-logic reference for porting, no further
  development or bug fixes (owner decision, 2026-07-04).

Full codebase detail: `.zj/codebase/MAP.md`.

## Definition of done — current milestone (v3.0 Customer & logistics)

> **Draft (confirm at `/zj:spec`):** "Can manage customers and a sales pipeline through to orders,
> fulfil those orders from warehouse inventory (receive → pick/pack → ship), and invoice customers
> with AR posting to the GL and AR aging that ties to its control account."

Chosen 2026-07-16 at the v2.0 close (D-M2-4) over the FLAN port and PLUM-advanced: it completes the
sell-side + fulfilment loop on the operations core and is where AR was parked (SYERP-13, D-P9-4).
Candidate phases — **CRUMB-01** (CRM: leads/pipeline/quotes/orders), **GELATO-01** (warehouse:
bins, receiving, pick/pack/ship, lot/serial), **SYERP-13** (accounts receivable) — are all coarse
FR placeholders needing `/zj:spec` expansion, and sequencing is open. **Next: `/zj:ship`** (resolve
the 2-milestone-deep master-merge debt, D-M2-3) then **`/zj:spec`** to sharpen this DoD into clauses.

**Shipped milestones:**
- **v2.0 — Operations.** *"Can track inventory, raise purchase orders, keep real books (double-entry
  GL with AP + financial statements), and execute work orders that consume PLUM BOMs and inventory."*
  Closed 2026-07-16 (tag `v2.0`; audit `.zj/MILESTONE-v2.0-AUDIT.md`, all four clauses proven live).
- **v1.0 — Foundation + PLUM.** *"Can deploy it, log in, manage vendors/customers, and design parts
  with multi-level BOMs and cost roll-up."* Closed 2026-07-09 (tag `v1.0`).

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
