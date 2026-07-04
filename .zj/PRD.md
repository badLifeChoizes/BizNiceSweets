# PRD — BizNiceSweets
Updated: 2026-07-04 (reverse-engineered at ZJ adoption from code, `.planning/` GSD artifacts, and `docs/` program roadmap — all archived; see DECISIONS.md D-ADOPT-1)

## PRD-1: Self-hosted single-command deployment
- **Statement:** The product shall run as a self-hosted containerized deployment that one
  small shop can bring up with a single compose command and operate on its own infrastructure.
- **Why:** The core value is ownership — no per-seat SaaS lock-in. If this breaks, nothing
  else matters.
- **Priority:** must
- **Source:** original program roadmap (2025-12-21); PROJECT.md core value
- **Acceptance signal:** `podman-compose up` on a fresh machine yields a working, migrated,
  logged-in-able suite.
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
- **Status: implemented**

## PRD-4: SYERP hub — business partners and financial skeleton
- **Statement:** The product shall provide the ERP hub every other suite integrates with:
  vendors and customers (searchable, editable) and a basic general-ledger account structure.
- **Why:** SYERP is the hub of the modular monolith — PLUM AVL, purchasing, CRM, and
  financials all FK into it; it must exist before any dependent module.
- **Priority:** must
- **Source:** Milestone-1 requirements (SYERP-01..05); hub-architecture decision
- **Acceptance signal:** Vendors/customers manageable in-app; PLUM can link parts to vendors.
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
- **Statement:** The product shall support operations: inventory, purchase orders, AP/AR
  basics and financial reporting (SYERP extended), plus work orders, routing, and shop-floor
  execution consuming PLUM BOMs (MOUSSE).
- **Why:** "Can manufacture products and track inventory" — the step that turns a design
  tool into a manufacturing suite. Owner confirmed (2026-07-04) this is the next milestone
  after v1.0 closes, per the dependency-first program roadmap.
- **Priority:** should (next milestone)
- **Source:** program roadmap Phase 2 (archived `docs/ROADMAP.md`); owner decision 2026-07-04
- **Acceptance signal:** A work order for a released PLUM assembly consumes inventory and
  reports cost back to SYERP.
- **Status: planned**

## PRD-8: Customer and logistics — CRM and warehouse
- **Statement:** The product shall support selling and shipping: leads → opportunities →
  quotes → orders (CRUMB) and warehouse locations, receiving, pick/pack/ship, lot/serial
  tracking (GELATO).
- **Why:** Completes the lifecycle to fulfillment; required for the "sells physical products"
  half of the audience.
- **Priority:** could (later milestone)
- **Source:** program roadmap Phase 3 (archived)
- **Acceptance signal:** An order placed in CRUMB is picked, packed, and shipped in GELATO
  against live SYERP inventory.
- **Status: planned**

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
- **Status: partial** — stack chosen for permissive licenses throughout (MIT/Apache/PostgreSQL);
  no public release or license audit yet.
