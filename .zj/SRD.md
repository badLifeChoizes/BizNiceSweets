# SRD — BizNiceSweets
Updated: 2026-07-04

> **Provenance:** requirement IDs and statements ingested verbatim from the GSD-era
> `.planning/REQUIREMENTS.md` (defined 2026-06-22, last updated 2026-06-30), archived at
> `archive/planning-gsd/REQUIREMENTS.md`. Statuses re-derived at adoption from the live code,
> the v1.0 milestone audit (2026-07-01, archived at `archive/planning-gsd/v1.0-MILESTONE-AUDIT.md`),
> and direct code inspection on 2026-07-04. This document is self-contained — it does not
> defer to the archive.

Numbering is append-only. IDs CORE-*, SYERP-01..05, PLUM-*, FLAN-01 are the original scheme;
SYERP-10+ and the MOUSSE/CRUMB/GELATO/CRISP-01 placeholders were added at adoption for
future scope (expanded via `/zj:spec` when their milestones near).

---

## Foundation (Core)

## CORE-01: Containerized single-command deploy  [traces: PRD-1]  **Status: implemented**
- **Statement:** User can run the suite as a containerized deployment via Podman Compose (`podman-compose up`).
- **Evidence:** `compose/compose.yml`, `Containerfile`, `backend/entrypoint.sh` (waits for
  Postgres, runs `alembic upgrade head`); operator-verified in Phase 1; live deploy confirmed
  by the v1.0 audit.
- **Verification:** fresh-machine `podman-compose -f compose/compose.yml up -d` with `.env`
  from `.env.example` → login page served on :8000.

## CORE-02: Account login via OAuth2/JWT  [traces: PRD-2]  **Status: implemented**
- **Statement:** User can create an account and log in via OAuth2/JWT authentication.
- **Evidence:** `backend/app/modules/auth/` (PyJWT + Argon2 via pwdlib); `frontend/src/routes/Login.tsx`; `backend/tests/auth/test_login.py`.
- **Verification:** login flow test suite + live login.

## CORE-03: Secure session persistence  [traces: PRD-2]  **Status: implemented**
- **Statement:** User session persists securely across requests (token issuance + refresh).
- **Evidence:** 15-min access / 7-day refresh tokens (`backend/app/core/config.py:38-39`);
  httpOnly refresh cookie + single-flight axios refresh (`frontend/src/api/client.ts`,
  `frontend/src/auth/token.ts` — access token never in localStorage);
  `backend/tests/auth/test_refresh.py`, `test_refresh_rotation.py`.
- **Verification:** refresh-rotation tests; session survives access-token expiry in-app.

## CORE-04: Admin user management  [traces: PRD-2]  **Status: implemented**
- **Statement:** Admin can create, edit, and deactivate user accounts.
- **Evidence:** `frontend/src/routes/admin/Users.tsx`; `backend/tests/auth/test_user_admin.py`; seeded first admin (`BNS_ADMIN_*`, `backend/app/core/config.py:42-43`).
- **Verification:** admin CRUD tests + human-verified in Phase 2 (2026-06-25).

## CORE-05: Role-based access control  [traces: PRD-2]  **Status: implemented**
- **Statement:** Admin can assign roles to users, and roles gate access to modules and actions.
- **Evidence:** User↔Role↔Permission M2M with `module:action` codes; `require_permission` on
  every SYERP/PLUM route; `backend/tests/auth/test_rbac.py`; live 401/403 gate confirmed by audit.
- **Verification:** RBAC test suite; API refuses un-permissioned calls regardless of UI.

## CORE-06: System settings  [traces: PRD-3]  **Status: implemented**
- **Statement:** Admin can configure system settings (company info, defaults).
- **Evidence:** `backend/app/core/settings_router.py`, migration 0003; `frontend/src/routes/admin/Settings.tsx`; `backend/tests/core/test_settings.py`.
- **Verification:** settings persist across restart; human-verified in Phase 3.

## CORE-07: Module enable/disable  [traces: PRD-3]  **Status: implemented**
- **Statement:** Admin can enable or disable individual modules.
- **Evidence:** `backend/app/core/modules_router.py`; `frontend/src/routes/admin/Modules.tsx`;
  always-on SYERP hub guard; `backend/tests/core/test_modules.py`; live toggle confirmed by audit.
- **Verification:** toggle updates nav live; SYERP toggle refused.

## CORE-08: Navigation shell  [traces: PRD-3]  **Status: implemented**
- **Statement:** User sees a navigation shell listing enabled modules and can switch between them.
- **Evidence:** `frontend/src/components/AppShell.tsx` (nav = enabled modules ∩ user permissions); route table in `frontend/src/App.tsx`.
- **Verification:** human-verified in Phase 3; module keys match routes.

## CORE-09: Versioned migrations  [traces: PRD-1]  **Status: implemented**
- **Statement:** Database schema is managed via versioned migrations (Alembic) that apply cleanly on a fresh deploy.
- **Evidence:** `backend/alembic/versions/0001`–`0006` single chained history; auto-run by `backend/entrypoint.sh:23`; chain 0001→0006 verified clean by audit.
- **Verification:** fresh DB migrates to head on container start.

---

## SYERP Core (Hub)

## SYERP-01: Vendor CRUD  [traces: PRD-4]  **Status: implemented**
- **Statement:** User can create, view, edit, and delete vendors.
- **Evidence:** `backend/app/modules/syerp/` (`Partner` model, `models.py:39`); `frontend/src/routes/syerp/Vendors.tsx`; archive-via-PATCH pattern; human-verified in Phase 4 (with 4 UAT fixes landed).
- **Verification:** Vendors screen CRUD + `Vendors.test.tsx`.

## SYERP-02: Vendor search/filter  [traces: PRD-4]  **Status: implemented**
- **Statement:** User can search and filter the vendor list.
- **Evidence:** `frontend/src/routes/syerp/Vendors.tsx`; live search confirmed by audit.
- **Verification:** search narrows list against live API.

## SYERP-03: Customer CRUD  [traces: PRD-4]  **Status: implemented**
- **Statement:** User can create, view, edit, and delete customers.
- **Evidence:** `frontend/src/routes/syerp/Customers.tsx` + shared `PartnerSheet`; `Customers.test.tsx`.
- **Verification:** as SYERP-01, customer-flagged partners.

## SYERP-04: Customer search/filter  [traces: PRD-4]  **Status: implemented**
- **Statement:** User can search and filter the customer list.
- **Evidence:** `frontend/src/routes/syerp/Customers.tsx`; live confirmed by audit.
- **Verification:** as SYERP-02.

## SYERP-05: General-ledger skeleton  [traces: PRD-4]  **Status: implemented**
- **Statement:** System provides a basic general-ledger account structure (chart-of-accounts skeleton).
- **Evidence:** seeded standard CoA (two-pass parent-code resolution, `backend/app/modules/syerp/seed.py`); read-only `frontend/src/routes/syerp/GLAccounts.tsx`; `backend/tests/syerp/test_gl.py`.
- **Verification:** CoA renders grouped by account type after fresh seed.

---

## PLUM (PLM Port — v1 Core)

## PLUM-01: Part CRUD  [traces: PRD-5]  **Status: implemented**
- **Statement:** User can create, view, edit, and delete parts.
- **Evidence:** `backend/app/modules/plum/` models/service/router, migration 0005; `frontend/src/routes/plum/PartsList.tsx`, `PartSheet.tsx`; `backend/tests/plum/test_parts.py`; human UAT 10/10 in Phase 5.
- **Defect (resolved, Phase 7 `1b8bfa1`):** `generate_part_number()` used lexicographic `MAX`
  on a VARCHAR — past a digit-width boundary it returned a stale number → duplicate-key 500.
  Rewritten to filter `^P[0-9]+$` then order by `cast(substring, Integer)`. **Proven live** against
  Postgres 17 (DB already held `P100000`; generator returned `P100001` = numeric MAX+1) plus a
  SQL proof that regex-before-cast survives non-numeric rows like `P-DUPE-01`. Regression test
  `test_generate_part_number_digit_boundary` ships (runs once the test harness is repaired —
  BACKLOG p1 / D-P7-4).
- **Verification:** live-DB standalone proof (Phase 7); UI new-part auto-numbering = UAT check 12
  (v1.0 milestone, D-P7-5).

## PLUM-02: Part search/filter  [traces: PRD-5]  **Status: implemented**
- **Statement:** User can search and filter parts.
- **Evidence:** `frontend/src/routes/plum/PartsList.tsx`; `test_parts.py`; live search confirmed by audit.
- **Verification:** search/filter against live API.

## PLUM-03: Revisions and status workflow  [traces: PRD-5]  **Status: implemented**
- **Statement:** User can create part revisions and advance a part through its status workflow.
- **Evidence:** revision FSM in `service.py` with one-Released partial unique index (DB-level invariant); `NewRevisionDialog.tsx`, `AdvanceStatusDialog.tsx`; `backend/tests/plum/test_revisions.py`; Released immutability enforced in UI (Phase-5 UAT fix).
- **Verification:** FSM tests; Draft→Released→Obsolete walk in-app.

## PLUM-04: Multi-level BOM tree  [traces: PRD-5]  **Status: partial (unverified)**
- **Statement:** User can build a multi-level BOM and view it as an expandable tree.
- **Evidence:** BOM CRUD/tree with BFS cycle detection (`service.py`, migration 0006); `frontend/src/routes/plum/components/BomTree.tsx` + smoke test; `backend/tests/plum/test_bom.py`. Live tree confirmed working by the audit; check 1 (Add Part on a Draft) passed Phase-7 spot-verify; full flow stays partial pending v1.0 milestone UAT (D-P7-5).
- **Verification:** v1.0 milestone UAT check 1 (`.zj/UAT-v1.0.md`).

## PLUM-05: Flat BOM roll-up  [traces: PRD-5]  **Status: partial (unverified)**
- **Statement:** User can view a flat BOM with quantity roll-up across levels.
- **Evidence:** flat-BOM accumulation in `service.py`; `BomTree.tsx` flat mode; `test_bom.py`. Live-confirmed by audit; human-verify deferred to v1.0 milestone UAT (D-P7-5).
- **Verification:** v1.0 milestone UAT check 2.

## PLUM-06: Where-used analysis  [traces: PRD-5]  **Status: partial (unverified)**
- **Statement:** User can run where-used analysis to see which assemblies consume a part.
- **Evidence:** where-used traversal in `service.py`; Where-Used card in `frontend/src/routes/plum/PartDetail.tsx`; `test_bom.py`. Live-confirmed by audit; human-verify deferred to v1.0 milestone UAT (D-P7-5).
- **Verification:** v1.0 milestone UAT check 3.

## PLUM-07: Part-to-vendor links (AVL)  [traces: PRD-4, PRD-5]  **Status: partial (runtime fix landed; UI UAT pending)**
- **Statement:** User can link a part to one or more vendors (FK to SYERP vendors / AVL).
- **Evidence:** all layers built — FK `plum_avl_link.vendor_id → syerp_partner.id` (migration
  0006), schemas, `AvlLinkSheet.tsx`, `PriceBreakEditor.tsx`, `test_avl.py`. The runtime break —
  `service.py` importing nonexistent `SyerpPartner` (real class `Partner`, `syerp/models.py:39`)
  at 4 sites → HTTP 500 on every AVL call — is **fixed in Phase 7 (`5c33ed8`)**, aliasing
  `Partner as SyerpPartner`. Code-verified live: the previously-failing import now resolves and
  `plum.service` imports clean; the import-commit vendor path passed a manual per-test run. Full
  add-vendor-link UI flow (persist-after-refresh, Preferred badge, no 500) is deferred to v1.0
  milestone UAT (checks 4/9, D-P7-5).
- **Verification:** live import-resolution proof (Phase 7); v1.0 milestone UAT checks 4 & 9.

## PLUM-08: Cost roll-up  [traces: PRD-5]  **Status: partial**
- **Statement:** User can set part pricing/cost and see cost roll-up across a BOM.
- **Evidence:** effective-cost chain (vendor price → manual cost → BOM roll-up → uncosted),
  `Numeric(18,6)`/`Decimal` math, release cost snapshot (`service.py`); Cost & Margin card in
  `PartDetail.tsx`; `test_costing.py`. Manual + roll-up path live-verified correct by audit
  (child 10 × qty 2 → parent 20); **vendor-price source now reachable** (PLUM-07 runtime fix
  landed, `5c33ed8`), pending UI confirmation.
- **Verification:** v1.0 milestone UAT check 5 (incl. vendor-price cost source).

## PLUM-09: Margin analysis  [traces: PRD-5]  **Status: partial (unverified)**
- **Statement:** User can view margin analysis for a product.
- **Evidence:** margin calc in `service.py` (live-verified by audit: margin 30, 150%); Cost & Margin card in `PartDetail.tsx`; `test_costing.py`. Human-verify deferred to v1.0 milestone UAT (D-P7-5).
- **Verification:** v1.0 milestone UAT check 6.

## PLUM-10: JSON/Excel import-export  [traces: PRD-5]  **Status: partial (fixes landed; UI UAT pending)**
- **Statement:** User can import and export PLUM data as JSON and Excel.
- **Evidence:** lossless JSON + 3-sheet Excel export, two-step preview/commit upsert-never-delete import with 10MB guard (`service.py`, openpyxl); `frontend/src/routes/plum/ImportExport.tsx` + test; `test_import_export.py`. Basic no-vendor round-trip works. Two Phase-7 fixes landed: (1) the vendor cross-reference 500 (same `SyerpPartner` bug) is fixed in `5c33ed8` (import-commit vendor path passed a manual per-test run); (2) import commit now invalidates the `['plum','parts']` query cache in `37b5f97` (tsc-clean, ImportExport tests pass). Full vendor round-trip + no-refresh list update deferred to v1.0 milestone UAT (checks 7/10/11, D-P7-5). Note: Excel export may 500 on the stale API image (missing `openpyxl` — BACKLOG), not a code regression.
- **Verification:** code-level (Phase 7 `5c33ed8`+`37b5f97`); v1.0 milestone UAT checks 7, 10, 11.

---

## PLUM Advanced (v2 — planned)

## PLUM-11: Document links  [traces: PRD-5]  **Status: planned**
- **Statement:** User can attach document links (URL/path references with document types) to parts.

## PLUM-12: Document management  [traces: PRD-5]  **Status: planned**
- **Statement:** User can upload, version, and preview documents in-app.

## PLUM-13: ECO workflow  [traces: PRD-5]  **Status: planned**
- **Statement:** User can create and approve Engineering Change Orders with impact analysis.

## PLUM-14: Labor costing  [traces: PRD-5]  **Status: planned**
- **Statement:** User can record labor cost on assemblies (flat cost plus hours × rate × notes) rolled up the BOM tree. *(Prototype `laborCost`/`laborHours`/`laborRate`/`laborNotes`; promoted from a Phase-6 deferral at the owner's explicit request.)*

## PLUM-15: Dev-estimate cost ranges  [traces: PRD-5]  **Status: planned**
- **Statement:** User can record low/high/average estimated costs with a costed-date for early-design estimating before a released cost exists. *(Prototype `costLow`/`costHigh`/`costAvg`/`costedDate`.)*

## PLUM-16: Distributor pricing & margin reporting  [traces: PRD-5]  **Status: planned**
- **Statement:** User can apply distributor discount / multi-tier pricing and view a dedicated margin-analysis report screen (beyond the inline v1 margin card).

---

## FLAN (v2 — planned)

## FLAN-01: FLAN port  [traces: PRD-6]  **Status: planned**
- **Statement:** The system shall provide FLAN project management on the new stack: projects, phases, tasks, timeline, budgets, team members. *(Functional reference: frozen prototype `flan/app/prj-mgmt-v24.html`.)*

---

## Future Suites (coarse placeholders — expand via /zj:spec at milestone planning)

## SYERP-10: Inventory management  [traces: PRD-7]  **Status: planned**
- **Statement:** The system shall track inventory items, quantities, locations, and transaction history.

## SYERP-11: Purchase orders  [traces: PRD-7]  **Status: planned**
- **Statement:** The system shall support a purchase-order workflow with vendor purchase history.

## SYERP-12: AP/AR and financial reporting  [traces: PRD-7]  **Status: planned**
- **Statement:** The system shall support invoice management (AP/AR basics) and basic financial reporting on the GL.

## MOUSSE-01: Manufacturing execution core  [traces: PRD-7]  **Status: planned**
- **Statement:** The system shall support work orders with status workflow, routing (operations/work centers), BOM consumption from PLUM, inventory consumption, shop-floor execution view, and work-order costing flowing to SYERP.

## CRUMB-01: CRM core  [traces: PRD-8]  **Status: planned**
- **Statement:** The system shall support leads, opportunity pipeline, quotes, orders, and a customer communication log referencing SYERP customers.

## GELATO-01: Warehouse core  [traces: PRD-8]  **Status: planned**
- **Statement:** The system shall support warehouse/location management, receiving, pick/pack/ship, lot and serial tracking against SYERP inventory.

## CRISP-01: Quality core  [traces: PRD-9]  **Status: planned**
- **Statement:** The system shall support inspections, NCRs, CAPA, quality holds on inventory, and compliance tracking linked to MOUSSE work orders.

---

## Non-Functional Requirements

## NFR-1: Audit trail  [traces: PRD-9]  **Status: implemented (foundation)**
- **Statement:** Significant actions (logins incl. failures, entity create/update/archive, revision FSM transitions) shall be recorded as attributable audit events.
- **Evidence:** audit events written unconditionally in auth (`auth.login_success`/`auth.login_failed`), SYERP (`partner.*`), and PLUM (`part.*`, `revision.*`) services/routers.
- **Verification:** audit rows present after each mutating flow; coverage re-check as each new module lands.

## NFR-2: Permissive-license dependencies  [traces: PRD-11]  **Status: implemented (unaudited)**
- **Statement:** All core dependencies shall carry permissive licenses (MIT/Apache/BSD/PostgreSQL) compatible with open-core distribution.
- **Evidence:** stack chosen accordingly (FastAPI/SQLAlchemy/React/Tailwind/shadcn — see `codebase/MAP.md`); no formal license audit performed yet (backlog).
- **Verification:** dependency license audit before public release.

## NFR-3: Offline capability  [traces: PRD-10]  **Status: planned**
- **Statement:** Core flows shall work offline via Service Worker + IndexedDB and sync on reconnect.
- **Verification:** network-down usage test; sync-on-reconnect demonstration.

---

## Traceability

| PRD | Covered by | Gaps |
|-----|------------|------|
| PRD-1 | CORE-01, CORE-09 | — |
| PRD-2 | CORE-02..05 | — |
| PRD-3 | CORE-06..08 | — |
| PRD-4 | SYERP-01..05, PLUM-07 | — |
| PRD-5 | PLUM-01..16 | Phase-7 code fixes landed & code-verified (`5c33ed8`/`1b8bfa1`/`37b5f97`); PLUM-04..10 flow-level UI confirmation deferred to v1.0 milestone UAT (`.zj/UAT-v1.0.md`, D-P7-5) |
| PRD-6 | FLAN-01 | expand at milestone planning |
| PRD-7 | SYERP-10..12, MOUSSE-01 | coarse — expand via /zj:spec |
| PRD-8 | CRUMB-01, GELATO-01 | coarse — expand via /zj:spec |
| PRD-9 | CRISP-01, NFR-1 | CRISP coarse |
| PRD-10 | NFR-3 | — |
| PRD-11 | NFR-2 | license audit outstanding |

**Counts (2026-07-04, post-Phase-7):** implemented 17 (CORE-01..09, SYERP-01..05, PLUM-01..03 —
PLUM-01 defect **resolved** & proven live, `1b8bfa1`) + 2 NFR foundations · partial 7
(PLUM-04..10 — all three Phase-7 runtime/cache fixes landed & code-verified; flow-level UI
confirmation deferred to v1.0 milestone UAT per D-P7-5) · planned 15 (PLUM-11..16, FLAN-01,
SYERP-10..12, MOUSSE/CRUMB/GELATO/CRISP-01, NFR-3).
