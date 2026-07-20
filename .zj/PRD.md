# PRD — BizNiceSweets
Updated: 2026-07-20 (PRD-12 added at the v4.0 spec — trustworthy, contributor-ready engineering
baseline: CI, enforced lint, runnable integration tests, ledger race-safety, human UAT; D-M4-1..3)
Prior: 2026-07-16 (PRD-8 refined + promoted to the active next milestone at the v3.0 spec —
order-to-cash + WMS scope, sell-side real books; D-V3-1..9)
Prior: 2026-07-11 (PRD-7/8 refined at the Phase-9 spec — GL+AP+reporting scope, AR→CRUMB; D-P9-1..4)
Originally: 2026-07-04 (reverse-engineered at ZJ adoption from code, `.planning/` GSD artifacts, and `docs/` program roadmap — all archived; see DECISIONS.md D-ADOPT-1)

## PRD-1: Self-hosted single-command deployment
- **Statement:** The product shall run as a self-hosted containerized deployment that one
  small shop can bring up with a single compose command and operate on its own infrastructure.
- **Why:** The core value is ownership — no per-seat SaaS lock-in. If this breaks, nothing
  else matters.
- **Priority:** must
- **Source:** original program roadmap (2025-12-21); PROJECT.md core value
- **Acceptance signal:** `podman-compose up` on a fresh machine yields a working, migrated,
  logged-in-able suite.
- **Evidence:** CORE-01, CORE-09 (see SRD).
- **Status: implemented** — verified live by the v1.0 milestone audit (2026-07-01).

## PRD-2: Secure multi-user access
- **Statement:** The product shall support multiple named users with authentication, roles,
  and per-module/per-action permissions administered in-app.
- **Why:** Replaces the prototypes' single-user/advisory-checkout model; a shared team system
  needs real access control, and the medical-device context needs attributable actions.
- **Priority:** must
- **Source:** Milestone-1 requirements (CORE-02..05)
- **Acceptance signal:** Admin creates users and roles; a user without a permission is
  refused by the API (not just hidden in the UI).
- **Evidence:** CORE-02, CORE-03, CORE-04, CORE-05 (see SRD).
- **Status: implemented**

## PRD-3: Modular suite shell
- **Statement:** The product shall present the installed suites as modules an admin can
  enable/disable, behind a navigation shell filtered by module state and user permissions,
  with system settings administered in-app.
- **Why:** "Installable modules over a shared database" is the architecture promise; each
  business enables only what it uses.
- **Priority:** must
- **Source:** Milestone-1 requirements (CORE-06..08); architecture decision (modular monolith)
- **Acceptance signal:** Toggling a module updates navigation live; SYERP cannot be disabled
  (hub guard).
- **Evidence:** CORE-06, CORE-07, CORE-08 (see SRD).
- **Status: implemented**

## PRD-4: SYERP hub — business partners and financial skeleton
- **Statement:** The product shall provide the ERP hub every other suite integrates with:
  vendors and customers (searchable, editable) and a basic general-ledger account structure.
- **Why:** SYERP is the hub of the modular monolith — PLUM AVL, purchasing, CRM, and
  financials all FK into it; it must exist before any dependent module.
- **Priority:** must
- **Source:** Milestone-1 requirements (SYERP-01..05); hub-architecture decision
- **Acceptance signal:** Vendors/customers manageable in-app; PLUM can link parts to vendors.
- **Evidence:** SYERP-01, SYERP-02, SYERP-03, SYERP-04, SYERP-05 (see SRD).
- **Status: implemented**

## PRD-5: PLUM — product design and costing
- **Statement:** The product shall let users design products: parts with revision workflow,
  multi-level BOMs (tree, flat roll-up, where-used), vendor links (AVL) with price breaks,
  cost roll-up and margin analysis, and JSON/Excel import/export.
- **Why:** Product development is the first real module and the proof of the whole port —
  the prototype's proven domain logic on the target stack.
- **Priority:** must
- **Source:** PLUM prototype (v54) domain logic; Milestone-1 requirements (PLUM-01..10)
- **Acceptance signal:** A user designs a multi-level assembly with costs rolled up from
  vendor pricing, and can round-trip the data via export/import.
- **Evidence:** PLUM-01, PLUM-02, PLUM-03 implemented; PLUM-04, PLUM-05, PLUM-06, PLUM-07, PLUM-08, PLUM-09, PLUM-10 partial pending v1.0 UAT (see SRD).
- **Status: partial** — parts/revisions/BOM/costing shipped; AVL and vendor import/export
  broken at runtime + Phase-6 human verification never run (see SRD PLUM-04..10; Phase 7).

## PRD-6: FLAN — project management on the new stack
- **Statement:** The product shall provide project management (projects, phases, tasks,
  timeline, budgets, team) as a module on the new stack, porting the FLAN prototype.
- **Why:** Second proven prototype; project management connects product development to
  execution. Prototype is frozen — the port is the only path forward.
- **Priority:** should (deferred milestone)
- **Source:** FLAN prototype (v24); v2 requirement FLAN-01
- **Acceptance signal:** The team runs a real project in the module instead of the prototype.
- **Status: planned**

## PRD-7: Operations — extended ERP and manufacturing execution
- **Statement:** The product shall support operations: inventory, purchase orders, then a
  **double-entry general ledger with accounts payable and financial reporting** (SYERP
  extended — inventory receipts and vendor bills auto-post to the GL; AP aging plus Trial
  Balance / P&L / Balance Sheet derive from posted activity), plus work orders, routing, and
  shop-floor execution consuming PLUM BOMs (MOUSSE). Accounts receivable ships later with CRUMB
  sales orders (see PRD-8), where its upstream invoices originate.
- **Why:** "Can manufacture products and track inventory" — the step that turns a design
  tool into a manufacturing suite. Owner confirmed (2026-07-04) this is the next milestone
  after v1.0 closes, per the dependency-first program roadmap. The owner chose real books
  (subledger→GL auto-posting) over document-only aging at the Phase-9 spec (2026-07-11, D-P9-1)
  so the shop's actual financial position is derivable, not just its open payables.
- **Priority:** should (next milestone)
- **Source:** program roadmap Phase 2 (archived `docs/ROADMAP.md`); owner decisions 2026-07-04
  and 2026-07-11 (D-P9-1..4)
- **Acceptance signal:** A work order for a released PLUM assembly consumes inventory and
  reports cost back to SYERP; and receiving a PO then billing and paying the vendor moves the
  right amounts through inventory, GR/IR, AP, and cash, visible on the financial statements.
- **Evidence:** SYERP-10, SYERP-11 implemented (Phase 8, backend verified live); SYERP-12
  (GL + AP + reporting) expanded for Phase 9; SYERP-13 (AR, CRUMB), MOUSSE-01 planned (see SRD).
- **Status: partial** — inventory + purchasing shipped and verified live (v2.0 Phase 8); GL +
  AP + financial reporting (SYERP-12) specified and planned for Phase 9; manufacturing execution
  (MOUSSE-01) planned for Phase 10 (closes v2.0). AR (SYERP-13) deferred to the CRUMB milestone.

## PRD-8: Customer and logistics — order-to-cash and warehouse
- **Statement:** The product shall support the full sell-side loop: **manage customers and a sales
  pipeline through to orders** (leads → opportunities → quotes → sales orders, CRUMB), **fulfil those
  orders from warehouse inventory** (bins, directed putaway, pick → pack → ship, GELATO), and
  **invoice customers with the books kept** — shipment relieves stock (Dr COGS / Cr Inventory), the
  invoice books revenue (Dr AR / Cr Revenue), the receipt collects cash (Dr Cash / Cr AR), and AR
  aging ties to its control account (SYERP-13).
- **Why:** Completes the lifecycle to fulfillment and closes the money loop — the sell-side mirror of
  the v2.0 procure-to-pay operations core; required for the "sells physical products" half of the
  audience. Chosen as the milestone after v2.0 over the FLAN port and PLUM-advanced (D-M2-4).
- **Priority:** should (**active next milestone — v3.0 "Customer & logistics"**)
- **Source:** program roadmap Phase 3 (archived); owner decisions at the v2.0 close (D-M2-4) and the
  v3.0 spec (D-V3-1..9)
- **Acceptance signal:** An order placed in CRUMB is picked, packed, and shipped in GELATO against
  live SYERP inventory; invoicing the shipment posts AR and revenue; a customer receipt clears it;
  and AR aging ties to the 1120 control account while the Trial Balance still nets zero.
- **Evidence:** CRUMB-01 (CRM + sales orders, Phase 11), GELATO-01 (warehouse core, Phase 12),
  SYERP-13 (AR + sell-side books, Phase 13) — all **expanded to full acceptance criteria at the v3.0
  spec** (2026-07-16). **Deferred within v3.0** (D-V3-4/5/6): lot/serial tracking, email
  integration/analytics, and price-list pricing.
- **Status: planned** — v3.0 spec complete; phases not yet planned/built.

## PRD-9: Quality and compliance
- **Statement:** The product shall support quality management — inspections, NCRs, CAPA,
  quality holds, compliance tracking (CRISP) — on top of a suite-wide audit trail that exists
  from the start.
- **Why:** Medical-device origin: traceability and audit trail are the highest-value
  differentiator for the owner's own business and regulated SMBs generally.
- **Priority:** should (CRISP later; audit trail standing)
- **Source:** program roadmap Phase 4 (archived); compliance-posture constraint
- **Acceptance signal:** Every significant action is attributable in an audit log; CRISP
  workflows reference manufacturing and inventory records.
- **Evidence:** NFR-1 implemented (audit-trail foundation); CRISP-01 planned (see SRD).
- **Status: partial** — audit-trail foundation implemented (audit events written across
  auth/SYERP/PLUM services); CRISP module planned.

## PRD-10: Offline capability
- **Statement:** The product shall remain usable offline (Service Worker + IndexedDB) and
  sync when reconnected.
- **Why:** Shop-floor and self-hosted environments can't assume connectivity; standing
  constraint from the original vision.
- **Priority:** could (cross-module, late phase)
- **Source:** original vision / program roadmap Phase 4 (archived)
- **Acceptance signal:** Core flows work with the network down; changes sync on reconnect.
- **Status: planned**

## PRD-11: Open-core distribution
- **Statement:** The product's core shall be open source with permissively licensed
  dependencies only, structured so premium add-ons remain possible.
- **Why:** Contributor-friendly ownership story; the licensing model is a design constraint,
  not an afterthought.
- **Priority:** must (standing constraint)
- **Source:** original vision (2025-12-21)
- **Acceptance signal:** Dependency audit shows permissive licenses; public release possible
  without relicensing.
- **Evidence:** NFR-2 implemented but unaudited (permissive-license dependencies) (see SRD).
- **Status: partial** — stack chosen for permissive licenses throughout (MIT/Apache/PostgreSQL);
  no public release or license audit yet.

## PRD-12: Trustworthy, contributor-ready engineering baseline
- **Statement:** The product's codebase shall enforce its own correctness automatically — every
  push runs the full test suite and static-analysis gates and reports pass/fail; integration
  coverage runs in the ordinary test suite rather than as a separate manual step; the inventory
  ledger stays correct under concurrent writers; and every shipped user-facing flow is confirmed
  by a documented human click-through — so a new deployment is trustworthy **without a manual
  verification run**.
- **Why:** For three milestones (v1.0→v3.0) correctness has rested entirely on standalone
  `verify_*` scripts and Vitest run **by hand**. The class of bug that ships when tests silently
  skip is real and already bit — a `SyerpPartner` 500 shipped through four plans because the
  live-DB tests never ran (v1.0 audit G3 / D-P7-4). This is the safety net that makes future
  feature work — and the eventual public open-source release with outside contributors —
  trustworthy. Unlike a feature, this outlives any single suite: it protects all of them. *(No new
  end-user capability ships in this milestone — it hardens the foundation.)*
- **Priority:** should (**active next milestone — v4.0 "Infra-debt + quality paydown"**)
- **Source:** v3.0 close decision D-M3-3; BACKLOG p1 (CI, harness, lint) + p2 (ledger race);
  D-P7-4; owner scope confirmation at the v4.0 spec (D-M4-1..3)
- **Acceptance signal:** A contributor pushes a branch; GitHub shows green test/lint/build checks
  automatically, and a maintainer merges trusting the gate without anyone running `verify_*` by
  hand. `pytest` runs (not skips) its DB-backed tests. Two simultaneous inventory saves cannot
  drive on-hand negative. The consolidated UAT checklist is complete for every shipped flow.
- **Evidence:** NFR-4 (CI), NFR-5 (runnable integration tests), NFR-6 (enforced lint), NFR-7
  (ledger race-safety), NFR-8 (human UAT) — see SRD.
- **Status: planned** — v4.0 spec complete (this doc); phases not yet planned/built. CRISP-01 (QMS)
  and NFR-3 (offline) groundwork were weighed and **deferred** out of this milestone (D-M4-1).
