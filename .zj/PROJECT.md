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

| Suite | Domain | Status (2026-07-19, post-v3.0) |
|-------|--------|--------------------------------|
| SYERP | ERP — partners, inventory, POs, GL, AP, **AR**, reporting — **the hub** | Core (Phase 4) + operations (Phases 8/9: inventory, purchasing, double-entry GL, AP, statements) + **accounts receivable shipped (SYERP-13, Phase 13, v3.0: invoice-from-shipment, receipts, AR aging tie-out)** |
| PLUM | Product Lifecycle Management | Ported + shipped v1.0 (Phases 5–7: parts, revisions, BOM, costing, AVL, import/export). Advanced features (PLUM-11..16) = later milestone |
| MOUSSE | Manufacturing Execution | Materials-only work-order core shipped (Phase 10, v2.0). Routing/work-centers, labor/overhead, shop-floor view deferred (D-P10-1) |
| CRUMB | CRM | **Shipped v3.0 (Phases 11a/11b, CRUMB-01 complete):** leads → opportunities → quotes → sales orders with PLUM-derived pricing, communication log, soft-reservation |
| GELATO | Warehouse Management | **Shipped v3.0 (Phases 12a/12b, GELATO-01):** bins, directed putaway, pick → pack → ship, reservation relief + COGS JE. Lot/serial deferred (D-V3-4) |
| FLAN | Project Management | HTML prototype only; port deferred to a later milestone |
| CRISP | Quality Management | Planned (candidate for v4.0 groundwork) |

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

## Definition of done — current milestone (v4.0 Infra-debt + quality paydown)

> **Confirmed at `/zj:spec` (2026-07-20, D-M4-1; traces PRD-12), C4 clause amended at close
> (2026-08-18, D-M4-4):** "The full test suite (integration + unit) runs green in a **GitHub Actions
> CI** pipeline on every push, both lint gates enforce a zero-violation baseline, the inventory ledger
> is race-safe across every writer, and every shipped UI flow has a **documented, runnable human
> check** keyed to the requirement it exercises — so a new deploy is trustworthy without a manual
> `verify_*` run."

> **C4 amendment (D-M4-4, owner at `/zj:milestone`).** The clause originally read "every shipped UI
> flow **has passed** a documented human click-through". D-P5-11 rewrote NFR-8's Statement and
> PRD-12's acceptance signal to make the *checklist* the deliverable and the owner's *reading* an
> ongoing activity — but the DoD sentence was never amended to match, so the milestone audit
> (`.zj/MILESTONE-v4.0-AUDIT.md`, GAP-1) found C4 NOT MET on its literal wording with `.zj/QA.md` §6
> holding zero readings. Amended rather than waited on, per the standing `QA docs: non-blocking`
> preference. **Consciously accepted:** v4.0 ships with **no** human-exercised evidence of any UI
> flow; the module rows caveated "UI-flow UAT-pending" stay caveated, and BACKLOG p1 "Run the human
> click-through checklist" stays open by design.

Chosen 2026-07-19 at the v3.0 close (D-M3-3) over the FLAN port and PLUM-advanced: correctness has
rested entirely on the standalone `verify_*` scripts + Vitest for **three** milestones while the p1
infra debt (no CI, broken live-DB pytest harness D-P7-4, both non-functional lint gates) rode unpaid,
and the shared inventory-ledger row-lock now has multiple writers (BACKLOG p2). Harden the foundation
before adding more features — **this milestone ships no new end-user capability.** Scope confirmed at
`/zj:spec`: **NFR-4** (CI), **NFR-5** (pytest harness repair + `verify_*` ported into the suite),
**NFR-6** (both lint gates fixed-to-clean, D-M4-3), **NFR-7** (shared inventory FOR-UPDATE lock +
inbound bin-blind fix), **NFR-8** (human UAT). CRISP-01 / offline groundwork deferred (D-M4-1).
Proposed 5-phase mapping in ROADMAP. **Next: `/zj:plan 1`.**

**Shipped milestones:**
- **v3.0 — Customer & logistics.** *"Can manage customers and a sales pipeline through to orders, fulfil
  those orders from warehouse inventory (bins → pick/pack/ship), and invoice customers with AR posting to
  the GL and AR aging that ties to its 1120 control account."* Two new suites (CRUMB CRM + GELATO WMS) and
  the sell-side of SYERP (AR). Closed 2026-07-19 (tag `v3.0`; audit `.zj/MILESTONE-v3.0-AUDIT.md` — whole
  money loop driven end-to-end on one order, all 3 clauses MET, 2 gaps fixed at close D-M3-1/2).
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
