# SRD — BizNiceSweets
Updated: 2026-07-20 (v4.0 "Infra-debt + quality paydown" spec — NFR-4 (CI), NFR-5 (runnable
integration tests / harness repair), NFR-6 (enforced lint gates), NFR-7 (concurrency-safe
inventory ledger), NFR-8 (human UAT) added under new PRD-12; D-M4-1..3)
Prior: 2026-07-16 (v3.0 "Customer & logistics" spec — SYERP-13 (AR), CRUMB-01, GELATO-01
expanded from coarse placeholders into full acceptance criteria; D-V3-1..9)
Prior: 2026-07-11

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
- **Evidence:** single chained history from `backend/alembic/versions/0001_initial_baseline.py` through `backend/alembic/versions/0008_syerp_purchasing.py`; auto-run by `backend/entrypoint.sh:23`. The v1.0 chain (0001→0006) was verified clean by audit; revisions 0007 and 0008 are v2.0 Phase 8.
- **Verification:** fresh DB migrates to head on container start.

---

## SYERP Core (Hub)

## SYERP-01: Vendor CRUD  [traces: PRD-4]  **Status: implemented**
- **Statement:** User can create, view, edit, and delete vendors.
- **Evidence:** `Partner` model at `backend/app/modules/syerp/models.py:39`; `frontend/src/routes/syerp/Vendors.tsx`; archive-via-PATCH pattern; human-verified in Phase 4 (with 4 UAT fixes landed).
- **Verification:** Vendors screen CRUD + `Vendors.test.tsx`.

## SYERP-02: Vendor search/filter  [traces: PRD-4]  **Status: implemented**
- **Statement:** User can search and filter the vendor list.
- **Evidence:** `frontend/src/routes/syerp/Vendors.tsx`; live search confirmed by audit.
- **Verification:** search narrows list against live API.

## SYERP-03: Customer CRUD  [traces: PRD-4]  **Status: implemented**
- **Statement:** User can create, view, edit, and delete customers.
- **Evidence:** `frontend/src/routes/syerp/Customers.tsx` + shared `frontend/src/routes/syerp/components/PartnerSheet.tsx`; `frontend/src/routes/syerp/Customers.test.tsx`.
- **Verification:** as SYERP-01, customer-flagged partners.

## SYERP-04: Customer search/filter  [traces: PRD-4]  **Status: implemented**
- **Statement:** User can search and filter the customer list.
- **Evidence:** `frontend/src/routes/syerp/Customers.tsx`; live confirmed by audit.
- **Verification:** as SYERP-02.

## SYERP-05: General-ledger skeleton  [traces: PRD-4]  **Status: implemented**
- **Statement:** System provides a basic general-ledger account structure (chart-of-accounts skeleton).
- **Evidence:** seeded standard CoA (two-pass parent-code resolution, `backend/app/modules/syerp/coa_seed.py`); read-only `frontend/src/routes/syerp/GLAccounts.tsx`; `backend/tests/syerp/test_gl.py`.
- **Verification:** CoA renders grouped by account type after fresh seed.

---

## PLUM (PLM Port — v1 Core)

## PLUM-01: Part CRUD  [traces: PRD-5]  **Status: implemented**
- **Verified:** a88431c (re-stamped 2026-07-11 — `service.py` changed again for the AVL D2 fix,
  which does not touch the part-CRUD or numbering paths; part CRUD re-proven live after that commit,
  201 on create and numeric successor still correct past the 5→6-digit boundary; guarded by
  `backend/scripts/verify_part_numbering.py` + `backend/tests/plum/test_part_number.py`)
- **Statement:** User can create, view, edit, and delete parts.
- **Evidence:** `backend/app/modules/plum/models.py`, `backend/app/modules/plum/service.py`, `backend/app/modules/plum/router.py`, migration `backend/alembic/versions/0005_plum_tables.py`; `frontend/src/routes/plum/PartsList.tsx`, `frontend/src/routes/plum/components/PartSheet.tsx`; `backend/tests/plum/test_parts.py`; human UAT 10 of 10 in Phase 5.
- **Defect (resolved, Phase 7 `1b8bfa1`):** `generate_part_number()` used lexicographic `MAX`
  on a VARCHAR — past a digit-width boundary it returned a stale number → duplicate-key 500.
  Rewritten to filter `^P[0-9]+$` then order by `cast(substring, Numeric)`. **Proven live** against
  Postgres 17 (DB already held `P100000`; generator returned `P100001` = numeric MAX+1) plus a
  SQL proof that regex-before-cast survives non-numeric rows like `P-DUPE-01`.
- **Blocker (introduced by that fix; resolved at `/zj:verify 07`, `7562a02`):** the rewrite cast the
  suffix to **int4**. `part_number` is `String(50)` with no format constraint, so a legal
  `P9999999999` matched the regex and overflowed the cast — Postgres raised "value out of range for
  type integer" and **every** subsequent auto-numbered create returned 500 until the row was deleted
  by hand (any `plum:write` user could trigger it; reproduced end-to-end). Cast target is now
  `Numeric`, which cannot overflow for a 50-char digit string.
- **Verification:** live-DB standalone proof (Phase 7). Durable guards now run:
  `backend/scripts/verify_part_numbering.py` (7 live assertions — boundary, non-numeric row,
  `> int4` overflow; proven red/green) and `backend/tests/plum/test_part_number.py` (4 pure tests
  that execute in the ordinary pytest suite). `test_generate_part_number_digit_boundary` still ships
  but remains non-executable until the harness is repaired (BACKLOG p1 / D-P7-4). UI new-part
  auto-numbering = UAT check 12 (v1.0 milestone, D-P7-5).

## PLUM-02: Part search/filter  [traces: PRD-5]  **Status: implemented**
- **Statement:** User can search and filter parts.
- **Evidence:** `frontend/src/routes/plum/PartsList.tsx`; `backend/tests/plum/test_parts.py`; live search confirmed by audit.
- **Verification:** search/filter against live API.

## PLUM-03: Revisions and status workflow  [traces: PRD-5]  **Status: implemented**
- **Statement:** User can create part revisions and advance a part through its status workflow.
- **Evidence:** revision FSM in `backend/app/modules/plum/service.py` with one-Released partial unique index (DB-level invariant); `frontend/src/routes/plum/components/NewRevisionDialog.tsx`, `frontend/src/routes/plum/components/AdvanceStatusDialog.tsx`; `backend/tests/plum/test_revisions.py`; Released immutability enforced in UI (Phase-5 UAT fix).
- **Verification:** FSM tests; Draft→Released→Obsolete walk in-app.

## PLUM-04: Multi-level BOM tree  [traces: PRD-5]  **Status: partial (unverified)**
- **Statement:** User can build a multi-level BOM and view it as an expandable tree.
- **Evidence:** BOM CRUD/tree with BFS cycle detection (`service.py`, migration 0006); `frontend/src/routes/plum/components/BomTree.tsx` + smoke test; `backend/tests/plum/test_bom.py`. Live tree confirmed working by the audit; check 1 (Add Part on a Draft) passed Phase-7 spot-verify; full flow stays partial pending v1.0 milestone UAT (D-P7-5).
- **Verification:** v1.0 milestone UAT check 1 (`.zj/UAT-v1.0.md`).

## PLUM-05: Flat BOM roll-up  [traces: PRD-5]  **Status: partial (unverified)**
- **Statement:** User can view a flat BOM with quantity roll-up across levels.
- **Evidence:** flat-BOM accumulation in `service.py`; `BomTree.tsx` flat mode; `test_bom.py`. Live-confirmed by audit; human-verify deferred to v1.0 milestone UAT (D-P7-5).
- **Verification:** v1.0 milestone UAT check 2.

## PLUM-06: Where-used analysis  [traces: PRD-5]  **Status: partial (UI defect fixed at milestone audit; UI UAT pending)**
- **Statement:** User can run where-used analysis to see which assemblies consume a part.
- **Evidence:** where-used traversal in `backend/app/modules/plum/service.py` (`get_where_used`, now emits `via_part_number`); `WhereUsedRow` in `backend/app/modules/plum/schemas.py`; Where-Used card in `frontend/src/routes/plum/PartDetail.tsx`; guards `frontend/src/routes/plum/PartDetail.test.tsx` (5 tests, runs in the ordinary vitest suite) and `backend/tests/plum/test_bom.py` (via-part assertions, currently skipped — D-P7-4).
- **Note:** the backend traversal was always correct, but the **UI labelled every parent "Direct parent"** because it derived the label from a `via_part_number` the API never sent (v1.0 milestone-audit gap **G1**, fixed `63ea954`). The Phase-6/7 "live-confirmed by audit" claim covered the API only — this is why the `partial (unverified)` status was right to hold.
- **Verification:** proven live 2026-07-09 (indirect ancestor names its intermediate part); visual affordance = v1.0 milestone UAT check 3.

## PLUM-07: Part-to-vendor links (AVL)  [traces: PRD-4, PRD-5]  **Status: partial (runtime fix landed + backend guarded; UI UAT pending)**
- **Verified:** 8975eeb (Phase 07 verify, 2026-07-09 — `add_avl_link` accepts an `is_vendor=True`
  Partner and rejects a non-vendor with 422, proven live; guarded by
  `scripts/verify_plum_vendor_paths.py`. UI flow still UAT-pending, so status stays `partial`.)
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

## PLUM-10: JSON/Excel import-export  [traces: PRD-5]  **Status: partial (fixes landed + backend/cache guarded; UI UAT pending)**
- **Verified:** 8975eeb (Phase 07 verify, 2026-07-09 — `build_json_export` resolves vendor_id→code,
  `validate_import` accepts a resolvable vendor_code and errors on an unknown one, `commit_import`
  upserts the AVL link: all proven live and guarded by `scripts/verify_plum_vendor_paths.py`.
  Cache invalidation on commit pinned by `ImportExport.test.tsx` (positive + negative path). Full
  vendor round-trip through the UI still UAT-pending, so status stays `partial`.)
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

## SYERP Extended — Operations (v2.0 — Phase 8)

> Expanded from coarse placeholders 2026-07-05 (`/zj:spec`) ahead of Phase 8 planning.
> Scope decisions: D-P8-1 (suite ownership), D-P8-2 (hybrid item↔PLUM), D-P8-3 (flat
> locations, GELATO boundary), D-P8-4 (moving-average valuation), D-P8-5 (PO depth = receive,
> no AP). IDs unchanged (append-only). SYERP-12 and later suites remain coarse placeholders.

## SYERP-10: Inventory management  [traces: PRD-7]  **Status: implemented (backend verified live; UI flow UAT pending)**
- **Verified:** 554c3fe (Phase 08 verify, 2026-07-08 — all 8 ACs proven live; crux/audit/RBAC
  regression tests deferred to BACKLOG p1, harness repair D-P7-4)
- **Statement:** The system shall let a user track on-hand inventory for stocked items across
  named stock locations, with an immutable transaction history and moving-weighted-average
  valuation. An **inventory item** is a SYERP master record that **may optionally reference a
  PLUM part** (`plum_part_id` nullable, D-P8-2); items without a PLUM link (raw materials,
  packaging, shop consumables) are fully supported so inventory works even when PLUM is
  disabled.
- **Acceptance criteria:**
  1. **Item master** — User can create, view, edit, and archive an inventory item with: unique
     `code`, `name`, unit of measure, optional `plum_part_id` FK, and `active` soft-delete flag
     (archived items hidden from default lists, mirroring `Partner`). Item `code` uses a
     numeric-safe auto-generator (order by integer cast, never lexicographic `MAX` — the
     PLUM `generate_part_number` lesson, D-P8-6).
  2. **Locations** — User can create, edit, and archive **flat named stock locations** (e.g.
     "Main", "Receiving", "WIP"). No bins, zones, or hierarchy (deferred to GELATO-01, D-P8-3).
  3. **On-hand by location** — For any item, user can see quantity-on-hand **per location** and
     the total across locations. On-hand is **derived** as the signed sum of that item/location's
     transactions (never a directly-mutated column).
  4. **Immutable transactions** — Every quantity change is recorded as an append-only inventory
     transaction carrying: item, location, transaction type (`receipt` | `issue` | `adjustment`
     | `transfer`), signed quantity, unit cost (where applicable), UTC timestamp, acting user,
     and an optional source reference (e.g. a PO-receipt id). Transactions are never updated or
     deleted; corrections are new reversing transactions.
  5. **Moving-average valuation** — Each **receipt** updates the item's moving weighted-average
     unit cost = `(qty_before × avg_before + qty_recv × unit_cost_recv) / (qty_before + qty_recv)`;
     issues and adjustments value at the current average. All money/qty math uses
     `Numeric(18,6)` / Python `Decimal` (D-11), never float. On-hand value (`total_qty × avg_cost`)
     is viewable per item.
  6. **Adjustment & transfer** — User can post a manual stock adjustment (with a reason) and a
     location-to-location transfer; both write transactions, a transfer nets zero across total
     on-hand, and an issue/adjustment/transfer that would drive a location's on-hand **negative
     is rejected** (HTTP 4xx) in v2.0 (backorder/negative-stock policy deferred, D-P8-7).
  7. **Audit** — Item create/edit/archive, location changes, and every transaction emit
     attributable audit events (NFR-1).
  8. **RBAC** — All endpoints are gated by `syerp:<action>` permission codes; an un-permissioned
     API call is refused regardless of UI (CORE-05 pattern).
- **Evidence:** all eight acceptance criteria built in the existing `syerp` module and proven
  end-to-end against live Postgres (Phase 8, branch `feature-syerp-inventory-purchasing`; D-P8-8/9/10,
  D-P8-12/13/14). Backend: migration `0007_syerp_inventory.py` (`syerp_inventory_item` /
  `syerp_stock_location` / append-only `syerp_inventory_txn` ledger, `b5c5c31`); item CRUD +
  numeric-safe `ITEM-####` generator (`511d6ae`); location CRUD + idempotent `Main` seed wired into
  `run_seeds` (`06f318c`); derived on-hand-by-location + valuation + txn-history reads (`e35021e`);
  receipt posting + pure-Decimal `compute_new_moving_avg` scale-6 ROUND_HALF_UP (`8e1b31f`);
  adjustment + per-location negative-stock guard (`0074bf0`); transfer paired-legs net-zero +
  source-underflow guard (`5f2a228`). Frontend (`frontend/src/routes/syerp/`): InventoryItems +
  ItemSheet + archive (`1fd2423`), StockLocations (`8e75af9`), InventoryItemDetail on-hand/valuation/
  ledger (`8b2c748`), StockAdjustDialog (`c9d6952`), StockTransferDialog (`cdf0e6c`) — colocated
  Vitest green, `tsc -b` clean. **Live-DB proof** (the pytest live harness is broken per D-P7-4 —
  truth from standalone scripts): `backend/scripts/verify_inventory.py` **14/14 PASS** (avg
  3.000000, on-hand value 60.000000, negative-adjustment reject, transfer nets-zero, seed idempotent,
  `e309260`); `backend/scripts/verify_e2e_p8.py` **18/18 PASS on a freshly-migrated DB** (alembic
  0001→0008 from empty, `Main` seeded out-of-the-box, `3703c51`). Pure-Decimal + generator unit tests
  green under plain pytest: `backend/tests/syerp/test_inventory.py`. Flow-level HUMAN UI confirmation
  deferred to the milestone UAT (`.zj/UAT-v2.0.md`, D-P7-5 precedent).
- **Verification:** service/router tests for on-hand derivation, moving-average math (Decimal
  exactness), negative-stock rejection, and transfer-nets-to-zero; live UI walk — create item
  (with and without a PLUM link), create locations, receive stock, read on-hand + value per
  location, post an adjustment and a transfer, confirm audit rows written. Backend behavior proven
  by the two verify scripts above; flow-level UI confirmation via the v2.0 milestone UAT.

## SYERP-11: Purchase orders  [traces: PRD-7]  **Status: implemented (backend verified live; UI flow UAT pending)**
- **Verified:** 554c3fe (Phase 08 verify, 2026-07-08 — all 8 ACs proven live incl. receive→inventory
  crux; regression tests deferred to BACKLOG p1, harness repair D-P7-4)
- **Statement:** The system shall support a purchase-order workflow —
  **Draft → Approved → Receiving (partial/complete) → Closed** — where a PO references a SYERP
  **vendor** (`Partner.is_vendor`) and its lines reference **inventory items**; receiving a PO
  line posts SYERP-10 **receipt transactions at the PO line unit cost**, feeding inventory
  on-hand and moving-average valuation. The workflow **stops short of vendor-invoice / AP
  matching and payment** — that remains SYERP-12 (D-P8-5).
- **Acceptance criteria:**
  1. **PO lifecycle** — User can create a PO in `Draft` for a vendor; add/edit/remove lines
     (item, qty ordered, unit cost, optional need-by date) **while Draft**; advance to
     `Approved` (line quantities/costs then locked); and `Close`. Invalid state transitions are
     refused server-side (HTTP 4xx) — the FSM is enforced in the service, not just the UI.
  2. **Numbering** — Each PO receives a unique auto-generated PO number using a numeric-safe
     generator (integer cast, not lexicographic — D-P8-6).
  3. **Vendor link & history** — `PurchaseOrder.vendor_id` FKs to `syerp_partner`; only partners
     with `is_vendor = True` are selectable. A vendor's purchase history is the list of that
     vendor's POs with status and totals.
  4. **Receiving → inventory** — Against an `Approved` PO, user can receive a line fully or
     partially; each receipt writes a SYERP-10 `receipt` transaction (item, into a user-chosen
     location, qty received, unit cost from the PO line) and increments the line's received-qty.
     Partial receipts accumulate. **Over-receipt beyond ordered qty is rejected** (HTTP 4xx) in
     v2.0 (tolerance handling deferred, D-P8-7).
  5. **Status roll-up** — Each line shows ordered / received / outstanding quantities; the PO
     shows an overall status (`Draft` | `Approved` | `Partially Received` | `Received` | `Closed`),
     auto-advancing to `Received` when every line is fully received.
  6. **No AP** — No vendor invoice, three-way match, or payment; the PO's unit costs exist only
     to value received inventory (SYERP-12 owns AP/AR).
  7. **Audit** — PO create, line edits, approve, each receipt, and close emit attributable audit
     events (NFR-1).
  8. **RBAC** — Endpoints gated by `syerp:<action>` permission codes (CORE-05 pattern).
- **Evidence:** all eight acceptance criteria built and proven end-to-end against live Postgres
  (Phase 8, branch `feature-syerp-inventory-purchasing`; D-P8-8/9/10, D-P8-15). Backend: migration
  `0008_syerp_purchasing.py` (`syerp_purchase_order` / `syerp_purchase_order_line`, `cafa93f`); PO
  draft CRUD + numeric-safe `PO-####` generator + vendor-only guard (`b5d7882`); approve/close FSM
  `PO_TRANSITIONS` stamping `approved_at`/`approved_by` (`92896ea`); PO receiving → real SYERP-10
  receipt via `post_receipt` with over-receipt reject + status roll-up in one atomic txn (`79181bd`);
  vendor PO history per-PO total + received roll-up (`ce5f666`). Frontend (`frontend/src/routes/syerp/`):
  PurchaseOrders list (`6d8afcc`), PurchaseOrderCreate (`e21ac2a`), PurchaseOrderDetail approve/close
  (`cd03899`), ReceiveLineDialog (`8aa6b65`) — colocated Vitest green, `tsc -b` clean. **Live-DB
  proof** (pytest live harness broken per D-P7-4 — truth from standalone scripts):
  `backend/scripts/verify_purchasing.py` **18/18 PASS** (PO receive posts real inventory txns,
  moving-avg 5.000000, over-receipt 422, roll-up partially→received, vendor total 50, `451ec7d`);
  `backend/scripts/verify_e2e_p8.py` **18/18 PASS on a freshly-migrated DB** (full Draft→Approved→
  partial-receive→remainder flow, exact on-hand + moving-avg, `3703c51`). Pure FSM + PO-number
  generator unit tests green under plain pytest: `backend/tests/syerp/test_purchasing.py`. Flow-level
  HUMAN UI confirmation deferred to the milestone UAT (`.zj/UAT-v2.0.md`, D-P7-5 precedent).
- **Verification:** service tests for lifecycle-transition enforcement, numeric PO numbering,
  vendor-only line selection, partial-receipt accumulation, and receipt-creates-inventory-
  transaction (integration with SYERP-10 moving-average); live UI walk — raise a PO → approve →
  receive partial then remainder → confirm item on-hand and moving-average updated → vendor
  history lists the PO. Backend behavior proven by the two verify scripts above; flow-level UI
  confirmation via the v2.0 milestone UAT.

---

## SYERP Extended — Financials (v2.0 — Phase 9)

> Expanded from a coarse placeholder 2026-07-11 (`/zj:spec`) ahead of Phase 9 planning.
> Scope decisions: D-P9-1 (full subledger auto-post GL — owner chose the deepest option over
> document-only aging), D-P9-2 (AP = vendor bill matched to PO receipts + payments), D-P9-3
> (GR/IR posting model for receipts and bills), D-P9-4 (AR deferred to the CRUMB milestone →
> new SYERP-13 placeholder). IDs unchanged (append-only): the original SYERP-12 "AP/AR and
> financial reporting" is **narrowed to AP + GL + reporting**; the AR half moves to SYERP-13.

## SYERP-12: General ledger, accounts payable & financial reporting  [traces: PRD-7]  **Status: verified (all 9 ACs — Phase 9a+9b+9c)**
- **Verified (AC1/2/3/8/9):** 8156157 (Phase 09a verify, 2026-07-11 — GL posting engine subset
  live-proven: `verify_gl.py` 28/28 + `verify_gl_api.py` 9/9).
- **Verified (AC4/AC5):** 380c73b (Phase 09b verify, 2026-07-12 — AP bills + PO-receipt match +
  payments live-proven: `verify_ap.py` 24/24 incl. the GR/IR-clears-to-zero crux and two
  concurrency race scenarios, `verify_ap_api.py` audit + 403/401/200 RBAC over live HTTP,
  `test_ap.py` 14; verify fix-loop row-locked the concurrent double-bill/overpayment race).
- **Verified (AC6/AC7):** 0eac5d4 (Phase 09c verify, 2026-07-12 — AP aging + financial statements
  live-proven: `verify_reports.py` 17/17 incl. the **exact-Decimal 2110 subledger↔control tie-out**
  crux with partial-payment and DRAFT-exclusion divergence guards, Trial Balance nets zero, P&L
  in/out-of-period, Balance Sheet balances with the computed current-year net-income line;
  `verify_reports_api.py` 13/13 — 200/401/403 across all 4 report endpoints + 422 missing-bound;
  FE `ApAging.test.tsx` / `FinancialReports.test.tsx` / `BillCreateDialog.test.tsx`).
- **Statement:** The system shall provide a **double-entry general-ledger posting engine**, an
  **accounts-payable workflow** (vendor bills matched to PO receipts, with payments), and
  **financial reporting** — where **inventory receipts (SYERP-11.4) and AP documents auto-post
  balanced journal entries to the GL**, so that AP aging and the core financial statements
  (Trial Balance, P&L, Balance Sheet) derive from **posted GL activity**, not from ad-hoc
  document scans. Accounts receivable is **deferred to the CRUMB milestone** (SYERP-13, D-P9-4):
  AR invoices belong downstream of sales orders, which do not yet exist.
- **Acceptance criteria:**
  1. **Journal & posting engine** — A journal entry has ≥2 lines; each line is a `GLAccount` +
     a debit **or** a credit amount (`Numeric(18,6)` / `Decimal`, never float — D-11). A **posted**
     entry must balance (Σ debits == Σ credits) or is **rejected** (HTTP 4xx). Posted entries are
     **immutable** (append-only, mirroring the inventory ledger — corrections are **reversing
     entries**, never edits/deletes). Each entry carries a date, memo, source reference
     (e.g. a receipt id or bill id), and acting user.
  2. **Derived GL balances & account register** — Each `GLAccount`'s balance is **derived** as the
     signed sum of its posted journal lines (never a directly-mutated column, mirroring on-hand
     derivation D-P8-4). User can view an **account register** — posted lines for one account over
     a date range with a running balance.
  3. **Inventory receipt auto-posts (GR/IR)** — Receiving a PO line (SYERP-11.4) now **also** posts
     a balanced JE at the receipt cost: **Dr Inventory asset, Cr GR/IR** (goods-received-not-
     invoiced accrual). The stock ledger (SYERP-10) remains the source of on-hand; the JE is the
     financial mirror. Receipt posting stays **atomic** — stock txn + JE in one transaction
     (D-P9-3; exact account codes confirmed at planning).
  4. **Vendor bill + PO match** — User creates an AP **bill** for a vendor (`Partner.is_vendor`),
     optionally **matching** it to one or more PO receipts (two/three-way match: bill line qty ×
     unit cost checked against received qty/cost). Posting the bill posts **Dr GR/IR** (matched)
     **or Dr Inventory/Expense** (unmatched), **Cr Accounts Payable**. Bill lifecycle
     **Draft → Posted → Paid**; invalid transitions **refused server-side** (HTTP 4xx), not just
     hidden in the UI (SYERP-11.1 FSM pattern).
  5. **Payments** — User records a **payment** against one or more posted bills (full or partial);
     posting a payment posts **Dr Accounts Payable, Cr Cash/Bank**. A bill's **open balance** =
     billed − paid; a payment that would drive it **negative (overpayment) is rejected** (HTTP 4xx),
     mirroring the over-receipt guard (D-P8-7). A bill auto-advances to `Paid` when its open balance
     reaches zero.
  6. **AP aging report** — Open AP balances **bucketed by age** (current / 31–60 / 61–90 / 90+)
     from bill dates, **per vendor and total**, and the total **ties to the Accounts-Payable
     control-account balance** in the GL (subledger ↔ control-account agreement).
  7. **Financial statements** — From posted GL activity: **Trial Balance** (every account, Σ debits
     == Σ credits), **Profit & Loss** (revenue/expense over a period), and **Balance Sheet**
     (assets == liabilities + equity as of a date). Each is a read-only report derived from posted
     journal lines; the Balance Sheet must balance.
  8. **Audit** — Bill create/post, payment, every journal entry, and every reversal emit
     attributable audit events (NFR-1).
  9. **RBAC** — All endpoints gated by `syerp:<action>` permission codes; an un-permissioned API
     call is refused regardless of UI (CORE-05 / D-P8-10 pattern).
- **Verification:** service tests for balanced-entry enforcement + posted-entry immutability,
  derived account balances, receipt→JE auto-post (Dr Inventory / Cr GR/IR at cost), bill PO-match +
  AP posting, payment posting + open-balance math + overpayment rejection, AP-aging buckets, and
  **statement tie-out** (Trial Balance nets to zero, Balance Sheet balances, AP aging total ==
  AP control-account balance); live UI walk — receive a PO (see the auto-posted JE), enter and
  match a vendor bill, pay it partially then fully, read AP aging and the three statements, confirm
  audit rows. Empirical proof via live-Postgres `backend/scripts/verify_*.py` (D-P7-4 precedent
  until the async pytest harness is repaired) + flow-level human UAT at the v2.0 milestone.
- **Phase 9a evidence (AC1/2/3/8/9 — GL posting engine):** double-entry `JournalEntry`/`JournalLine`
  (append-only, reversal via self-FK), derived balances + account register, and the PO-receipt
  auto-post (Dr 1130 Inventory / Cr 2150 GR/IR, atomic with the stock receipt) built in the `syerp`
  module (migration `0009_syerp_gl_journal.py`). Backend live-verified: **`verify_gl.py` 28/28
  PASS** (balanced-only posting + 422 reject, reversal immutability, derived balances incl. the
  single-sided coalesce fix, atomic receipt→JE, the atomicity-rollback negative path, zero-cost
  receipt, and the double-reversal 409 guard) and **`verify_gl_api.py` 9/9 PASS** (gl.journal_posted
  / gl.journal_reversed audit rows + syerp:read/write 403 & 401 over live HTTP); pure helpers
  `tests/syerp/test_gl_journal.py` (13); FE `JournalEntries.test.tsx` / `AccountRegister.test.tsx`.
  Phase-9a verify fix-loop closed two majors (M1 zero-cost receipt regression, M2 missing
  double-reversal guard) + m5 traceable receipt audit. **AC4/AC5 (AP bills/3-way match/payments)
  landed & verified in Phase 9b (380c73b); AC6/AC7 (AP aging, financial statements) landed &
  verified in Phase 9c (0eac5d4) — all 9 ACs now verified.**

---

## Customer & Logistics — order-to-cash + WMS (v3.0 — Phases 11–13)

> Expanded from coarse placeholders 2026-07-16 (`/zj:spec`) ahead of v3.0 planning. This
> milestone completes the **sell-side + fulfillment loop** (order → ship → invoice → collect) on
> top of the v2.0 operations core, mirroring the buy-side procure-to-pay model built in Phases 8–9.
> Scope decisions (append-only, D-V3-1..9):
> - **D-V3-1** — DoD = three clauses: CRM & sales pipeline (CRUMB-01), warehouse fulfillment
>   (GELATO-01), accounts receivable & sell-side books (SYERP-13).
> - **D-V3-2** — Sell-side GL = **two-event real books**: shipment posts Dr 5100 COGS / Cr 1130
>   Inventory at moving-avg; invoice posts Dr 1120 AR / Cr 4110 Product Revenue; customer receipt
>   posts Dr Cash/Bank / Cr 1120 AR. All accounts already seeded (`coa_seed.py`) — no new CoA
>   codes and **no sell-side clearing account** (the two events touch disjoint accounts, unlike
>   the buy-side GR/IR bridge).
> - **D-V3-3** — Invoices are **shipment-driven** (bill what shipped), mirroring the receipt-driven
>   AP bill (D-P9b-1); partial shipments → partial invoices, matched at sales-order-line grain.
> - **D-V3-4** — **Lot/serial tracking deferred** to a follow-on GELATO phase; v3.0 fulfillment is
>   quantity + cost only (mirrors carving routing out of MOUSSE, D-P10-1).
> - **D-V3-5** — CRUMB depth = **full lean chain** (leads → opportunities → quotes → sales orders
>   + customer communication log); **no** email integration or analytics.
> - **D-V3-6** — Quote/order line pricing = **PLUM-derived default** (part's released cost + an
>   editable markup), editable per line; **no price-list entity** (that is PLUM-16 territory).
> - **D-V3-7** — GELATO scope = **inbound + outbound**: directed putaway-to-bin on receipts AND
>   pick/pack/ship; **bins** are introduced as a sub-level within SYERP's flat stock locations
>   (realizes the D-P8-3 deferral).
> - **D-V3-8** — A confirmed sales order **soft-reserves inventory** (available = on-hand −
>   reserved); shipping converts the reservation to an issue.
> - **D-V3-9** — Module ownership: leads/opportunities/quotes/sales orders = **CRUMB**;
>   bins/putaway/pick/pack/ship = **GELATO**; AR invoices/receipts/aging + **all GL JEs** = SYERP.
>   GELATO ship and the AR invoice **import** SYERP inventory/GL service functions rather than
>   duplicating them (D-P10-6 precedent).
>
> IDs are append-only and unchanged. CRISP-01 remains a coarse placeholder.

## SYERP-13: Accounts receivable & sell-side books  [traces: PRD-7, PRD-8]  **Status: verified (v3.0 — Phase 13)**
- **Verified:** 7610e63
- **Statement:** The system shall support customer **invoices, receipts (customer payments), and
  AR aging**, with sell-side activity **auto-posting balanced journal entries to the GL** on the
  existing SYERP-12 posting engine — **shipment** (GELATO-01.5) posts Dr 5100 COGS / Cr 1130
  Inventory at moving-avg cost, an **invoice** posts Dr 1120 AR / Cr 4110 Product Revenue, and a
  **customer receipt** posts Dr Cash/Bank / Cr 1120 AR — so AR aging and the financial statements
  derive from posted GL activity. Invoices are **created from shipments** (bill what shipped, D-V3-3),
  mirroring the SYERP-12 AP model on the sell side (D-P9-4).
- **Acceptance criteria:**
  1. **Sell-side postings** — All three JE shapes post on the SYERP-12 engine (AC1): ≥2 balanced
     lines, `Numeric(18,6)`/`Decimal` (D-11), append-only/immutable, reversible. The COGS-on-ship
     JE is **atomic** with the inventory issue (one transaction, mirroring the receipt→GR/IR
     atomicity of SYERP-12.3). No new CoA accounts (D-V3-2).
  2. **Invoice from shipment** — User creates an AR **invoice** for a customer by selecting that
     customer's **shipped-but-uninvoiced** quantities (uninvoiced qty = shipped − Σ already-invoiced,
     matched at sales-order-line grain, mirroring D-P9b-1). Invoice auto-numbers `INV-####`
     (numeric-safe generator, D-P8-6); **Draft → Posted → Paid** FSM enforced server-side (invalid
     transitions HTTP 4xx). Posting the invoice posts Dr 1120 AR / Cr 4110 Revenue for the invoiced
     value; the invoice's JE `entry_date` = `invoice_date` (so aging and the control account share
     one date basis, D-P9c-1 pattern).
  3. **Customer receipts** — User records a **receipt** against one or more posted invoices (full or
     partial), modelled as `Receipt` header + `ReceiptAllocation` (one receipt settles N invoices;
     `Receipt.amount` == Σ allocations), mirroring Payment/PaymentAllocation (D-P9b-6). Posting
     posts Dr <selectable cash/bank, default 1110> / Cr 1120 AR. A receipt that would drive an
     invoice's open balance (invoiced − received) **negative is rejected 4xx** (D-P8-7 guard); an
     invoice auto-advances to **Paid** when its open balance reaches zero.
  4. **AR aging** — Open AR balances **bucketed by age** (current / 31–60 / 61–90 / 90+) from
     invoice dates, **per customer and total**; the grand total **ties Decimal-exactly to the 1120
     Accounts-Receivable control-account balance** (subledger ↔ control, the AC6/D-P9c-1 tie-out on
     the sell side).
  5. **Statements** — With AR/revenue/COGS activity posted, the SYERP-12 **Trial Balance still nets
     zero**, **P&L** shows revenue − COGS over a period, and the **Balance Sheet** includes AR under
     assets and still balances. (Extends SYERP-12.7 reports; the only new report screen is AR aging.)
  6. **Audit** — Invoice create/post, receipt, every JE and reversal emit attributable audit events
     (NFR-1).
  7. **RBAC** — All endpoints gated by `syerp:<action>` permission codes; an un-permissioned API
     call is refused regardless of UI (CORE-05 / D-P8-10 pattern).
- **Verification:** live-Postgres `backend/scripts/verify_ar.py` (Decimal-exact AR-control tie-out,
  invoice-from-shipment match, overpayment reject, COGS-on-ship moving-avg, and an `asyncio.gather`
  concurrency scenario on receipt/invoice guards — the D-P9b concurrency lesson) + `verify_ar_api.py`
  (HTTP RBAC + audit rows); full regression suite still exits 0 and the Trial Balance nets zero; FE
  Vitest + `npm run build`. Flow-level human UAT at the v3.0 milestone (D-P7-5 precedent).

## MOUSSE-01: Manufacturing execution core  [traces: PRD-7]  **Status: partially verified (materials-only slice, Phase 10)**
- **Statement:** The system shall support work orders with status workflow, routing (operations/work centers), BOM consumption from PLUM, inventory consumption, shop-floor execution view, and work-order costing flowing to SYERP.
- **Scope note:** Phase 10 delivered the **materials-only slice** (D-P10-1). Routing/operations/work-centers, labor & overhead, and the shop-floor operator view are **deferred** to a later MOUSSE phase — those clauses of the statement remain unverified.
- **Acceptance criteria (materials-only slice, delivered Phase 10):**
  - **AC1** — WO create + single-level (direct) BOM snapshot at release + server-enforced FSM Draft→Released→In Progress→(On Hold⇄In Progress)→Completed, +Cancelled from Draft/Released; no-Released-revision → 4xx; a BOM child with no linked InventoryItem rejects the whole release 4xx (D-P10-7). *(Verify: `verify_mousse.py` A/B/C.)*
  - **AC2** — Explicit component issue posts signed `issue` InventoryTxn rows (negative qty, `source_type="mousse_work_order"`) at moving-avg cost, floor-guarded, atomic with one balanced JE **Dr 1140 / Cr 1130**; first issue → In Progress. *(Verify: `verify_mousse.py` A.)*
  - **AC3** — Completion receives planned qty at accumulated-WIP unit cost (Dr 1130 / Cr 1140) so the WO's **1140 balance returns to its pre-WO value Decimal-exactly**, AND the **1130 control account ties to the inventory subledger** — the residual routes to 5190 Inventory Rounding (D-P10-2 amended). Under-issued completion rejected 4xx unless audited `override_incomplete` (D-P10-9). *(Verify: `verify_mousse.py` A/D.)*
  - **AC4** — Two concurrent issues (`asyncio.gather`) cannot double-consume / drive on-hand negative; contended rows `SELECT … FOR UPDATE` in sorted-id order. *(Verify: `verify_mousse.py` F.)*
  - **AC5** — Every WO mutation writes an attributable audit row and enforces `mousse:write` (403/401/200) at HTTP level; reads gated `mousse:read`. *(Verify: `verify_mousse_api.py`.)*
  - **AC6** — Regression: `verify_inventory`/`verify_purchasing`/`verify_e2e_p8`/`verify_gl`/`verify_ap`/`verify_reports` still exit 0; trial balance nets zero. *(Verify: full suite, 13/13.)*
  - **AC7** — Frontend: WO list, create dialog, detail (snapshot lines + on-hand + issued-so-far), Issue/Hold/Resume/Complete actions with under-issue override warning; TanStack Query invalidation; nav gated on MOUSSE enabled ∩ `mousse:read`. *(Verify: Vitest `routes/mousse/*.test.tsx`, `npm run build`.)*
- **Verification method:** live-Postgres `backend/scripts/verify_mousse.py` (34 assertions incl. the WIP-clears + 1130-subledger-tie + concurrency crux) and `verify_mousse_api.py` (HTTP RBAC + audit); frontend Vitest; full regression suite (13/13 verify_* exit 0). Verified at `/zj:verify 10` (2026-07-16).
- **Verified:** 5cffeeb (AC1–AC7, materials-only slice; deferred clauses remain planned)

## CRUMB-01: CRM core & sales orders  [traces: PRD-8]  **Status: verified (v3.0 — Phase 11a + 11b; all ACs)**
- **Verified:** fec334f
> New module `backend/app/modules/crumb/` + `frontend/src/routes/crumb/`; RBAC codes
> `crumb:read`/`crumb:write` (mirror syerp, D-P10-6). References SYERP customers and PLUM parts.
> Full lean chain, no email/analytics (D-V3-5). See the v3.0 scope preamble (D-V3-1..9).
- **Verified (Phase 11b, AC4 + AC3 SO-conversion tail — CRUMB-01 now complete):** fec334f (2026-07-17
  — sales-order FSM (Draft→Confirmed→Fulfilling→Closed, +Cancelled from Draft/Confirmed, server-enforced
  4xx), `SO-####` numeric-safe numbering, accepted-quote→SO conversion copying lines with item_id
  resolved from the PLUM-part link, and the **soft-reservation crux**: confirm reserves
  `min(qty_ordered, available)` where `available = get_item_on_hand − Σ open reservations ≥ 0`, never
  driven negative, over-order shows derived shortage (not blocked), cancel releases; `InventoryItem`
  rows `FOR UPDATE`-locked in sorted-id order before the read — two concurrent confirms cannot
  over-reserve (verify scenario F, load-bearing). Posts NO GL (TB nets zero). verify_crumb_so 27/27 +
  verify_crumb_so_api 40 + 15/15 regression = 17/17; FE Vitest + build. **Verify fix loop caught a
  blocker the harness hid:** direct-create/edit SO lines never bridged `plum_part_id→item_id` (the UI
  line-editor shape) so UI-created lines reserved 0 — fixed `fec334f`, pinned by new (D2) assertions.)
- **Verified (Phase 11a, AC1/2/3−/5/6/7):** efcf2e6 (2026-07-16 — leads → opportunities (stage FSM)
  → quotes (PLUM-derived line pricing + status FSM) + append-only communication log; server-enforced
  FSMs, router-layer audit, `crumb:read`/`crumb:write` RBAC proven at HTTP level. verify_crumb 22/22
  + verify_crumb_api 54/54 + 13/13 regression + FE Vitest 4/4 + build.)
- **Statement:** The system shall support the sell-side pipeline against SYERP customers — **leads →
  opportunities (pipeline stages) → quotes → sales orders** — plus a **customer communication log**,
  where a confirmed sales order **soft-reserves inventory** and feeds GELATO fulfillment (GELATO-01)
  and SYERP-13 invoicing.
- **Acceptance criteria:**
  1. **Leads** — User can create/view/edit/archive a **lead** (name, company, contact, source,
     status); a qualified lead links to (or creates) a SYERP customer (`Partner.is_customer`) and can
     be converted to an opportunity.
  2. **Opportunity pipeline** — **Opportunities** carry a customer, estimated value, expected close
     date, and a **pipeline stage** (e.g. Qualify → Proposal → Won/Lost); user can view the pipeline
     as a per-stage list and move an opportunity between stages (transitions audited). A won
     opportunity can spawn a quote.
  3. **Quotes** — A **quote** header (customer) + lines (PLUM part or free-text description, qty,
     unit price). Line unit price **defaults from the part's PLUM released cost + an editable markup**
     and is user-editable (D-V3-6); quote shows line + total value. FSM **Draft → Sent →
     Accepted/Rejected/Expired** enforced server-side (4xx invalid); auto-number `QUOTE-####`
     (numeric-safe, D-P8-6). An **accepted quote converts to a sales order**, copying its lines.
  4. **Sales orders** — A **sales order** header (customer, order/required dates) + lines (item, qty,
     unit price); auto-number `SO-####`; FSM **Draft → Confirmed → Fulfilling → Closed** (+ Cancelled
     from Draft/Confirmed) enforced server-side (4xx invalid). **Confirming soft-reserves inventory**
     (D-V3-8): each line reserves `min(qty_ordered, available_on_hand)` against its SYERP inventory
     item; `available = on-hand − Σ reservations` and a reservation **never drives available
     negative**; a line whose ordered qty exceeds available is confirmed with a visible **shortage /
     backorder** indicator (not hard-blocked, single-shop). GELATO shipping (GELATO-01.5) consumes
     the reservation.
  5. **Communication log** — Append-only **interaction log** entries (type call/email/note/meeting,
     UTC timestamp, acting user, body) referencing a SYERP customer and optionally a lead/opportunity/
     quote/order; user can read a per-customer timeline. (Logging only — **no email send/receive
     integration**, D-V3-5.)
  6. **Cross-module integrity** — Leads/opportunities/quotes/orders FK to `syerp_partner`
     (`is_customer`) and PLUM parts; a sales order is the document GELATO fulfills and SYERP-13
     invoices. Deleting/archiving respects downstream references.
  7. **Audit + RBAC** — Every mutation (incl. stage/FSM transitions, quote→order conversion) emits an
     attributable audit event (NFR-1); all endpoints gated by `crumb:read`/`crumb:write`, refused
     server-side regardless of UI (CORE-05).
- **Verification:** live-Postgres `backend/scripts/verify_crumb.py` (FSM enforcement, numeric-safe
  numbering, quote→order conversion copies lines exactly, PLUM-derived price default, and the
  reservation invariant `available = on-hand − reserved ≥ 0` incl. a concurrency scenario) +
  `verify_crumb_api.py` (HTTP RBAC + audit); FE Vitest + `npm run build`; nav gated on CRUMB enabled
  ∩ `crumb:read`. Flow-level human UAT at the v3.0 milestone.

## GELATO-01: Warehouse core  [traces: PRD-8]  **Status: VERIFIED — 12a inbound foundation (AC1/AC2/AC8 + putaway-side AC6/AC7) + 12b outbound pick→pack→ship (AC3/AC4/AC5 + ship-side AC7) both delivered & verified**
> **12a delivered & verified** (`/zj:verify 12a`, 2026-07-18): bins CRUD (AC1), directed
> putaway netting zero at location grain (AC2), per-bin on-hand derives + rolls up Decimal-exact
> to the location total (AC1), quantities-only (AC6), putaway floor guard 4xx (AC7 putaway side),
> audit + RBAC (AC8). NO GL posted (Trial Balance nets zero). Known boundary (BACKLOG p2): only
> putaway was bin-aware, so a bin-blind draw (transfer/adjust/MOUSSE-issue) staled the bin split —
> the OUTBOUND half of that p2 item is now closed by 12b's bin-aware pick/issue; the location
> roll-up stays exact throughout.
> - **Verified (12a subset):** 52eb481
> **12b delivered & verified** (`/zj:verify 12b`, 2026-07-19): pick (AC3) — bin-aware net-zero
> move of reserved lines into a staging bin, stamps `qty_picked`, auto-advances the SO
> confirmed→fulfilling; pack (AC4) — FSM picking→packed, partial packs; ship (AC5) — the accounting
> crux: bin-aware `post_issue` from staging at moving-avg cost ATOMIC with ONE balanced Dr 5100
> COGS / Cr 1130 Inventory JE (single commit), relieves the soft-reservation (`qty_reserved -=`),
> stamps `qty_shipped`, never over-ships/over-issues (AC7), 1130 ties to the subledger + TB nets
> zero with the JE. **Two concurrent ships of one packed shipment cannot double-post COGS** — the
> shipment row is `SELECT … FOR UPDATE`-locked before the FSM gate (verify fix loop, blocker),
> mutation-proven by `verify_gelato_ship.py` scenario (h). Audit + RBAC at HTTP level (AC8).
> - **Verified (12b outbound):** 553bcfb
> New module `backend/app/modules/gelato/` + `frontend/src/routes/gelato/`; RBAC codes
> `gelato:read`/`gelato:write`. Writes the **SYERP inventory ledger** and posts GL JEs via imported
> SYERP service functions (D-V3-9 / D-P10-6). Quantities + cost only — **lot/serial deferred**
> (D-V3-4). See the v3.0 scope preamble (D-V3-1..9).
- **Statement:** The system shall add a **warehouse layer** over SYERP inventory — **bins** within
  the existing flat stock locations, **directed putaway** on inbound receipts, and outbound **pick →
  pack → ship** of CRUMB sales orders — where **shipping relieves reserved inventory** and posts the
  sell-side COGS journal entry, without lot or serial tracking (deferred, D-V3-4).
- **Acceptance criteria:**
  1. **Bins within locations** — User can create/edit/archive **bins** (code, description, active) as
     a **sub-level within a SYERP stock location** (the D-P8-3 bin deferral). Per-bin on-hand is
     **derived** from bin-aware inventory movements and **rolls up to the SYERP location total**,
     which continues to derive per SYERP-10.3.
  2. **Inbound putaway** — A **receiving/putaway** screen directs received stock (a SYERP-11.4 PO
     receipt, or a manual receipt) into a target bin; putaway writes bin-aware inventory transactions
     and **nets zero at the location grain** (moves qty between bins, not into/out of the location).
  3. **Pick** — Against a **Confirmed** CRUMB sales order, the system generates a **pick list** of
     order lines → suggested bins holding sufficient on-hand; user confirms picked qty from bins.
     Picking draws against the order's **reservation** (CRUMB-01.4) and moves stock to a pack/staging
     area (bin-level moves).
  4. **Pack** — User **packs** picked items into a shipment/package for an order; partial packs
     allowed; a pack records what is staged to ship.
  5. **Ship** — Shipping a packed shipment posts SYERP **issue** transactions relieving on-hand at
     moving-avg cost, **clears the consumed reservation**, and is **atomic** with a balanced GL JE
     **Dr 5100 COGS / Cr 1130 Inventory** (D-V3-2; imports SYERP inventory/GL service fns, D-V3-9).
     Partial shipments accumulate and stamp each order line's shipped qty; the shipment is the
     document SYERP-13 invoices from (D-V3-3).
  6. **Quantities only** — No lot or serial capture in v3.0 (D-V3-4); every movement is quantity +
     cost.
  7. **Floor & reservation guards** — A putaway/pick/ship that would drive a **bin or location
     on-hand negative is rejected 4xx** (D-P8-7 floor-guard pattern); a ship **never over-ships** an
     order line beyond its picked/ordered qty. *(The cross-path inventory-ledger row-lock is the
     standing BACKLOG p2 race item — GELATO ship now joins MOUSSE issue and SYERP adjust/receive as a
     writer of this ledger; lock contended rows FOR UPDATE per the D-P9b template.)*
  8. **Audit + RBAC** — Bin changes, putaway, pick, pack, and ship emit attributable audit events
     (NFR-1); endpoints gated by `gelato:read`/`gelato:write` (CORE-05).
- **Verification:** live-Postgres `backend/scripts/verify_gelato.py` (per-bin on-hand rolls up to the
  location total; putaway nets zero at location grain; negative-stock reject; putaway concurrency
  Barrier) + `verify_gelato_api.py` (inbound HTTP RBAC + audit) for the 12a inbound half;
  **`verify_gelato_ship.py`** (ship relieves inventory + posts the COGS JE Decimal-exact + clears the
  reservation + ties 1130 to the subledger; over-pick/over-ship/staging-floor rejects; scenario (g)
  two ships cannot over-issue a scarce staging bin; **scenario (h) two concurrent ships of ONE packed
  shipment cannot double-post COGS — shipment-row FOR UPDATE lock, mutation-proven**) +
  **`verify_gelato_ship_api.py`** (ship HTTP RBAC + attributable audit incl. int-PK `target_id` str
  guard) for the 12b outbound half; full regression (all `verify_*` exit 0, Trial Balance nets zero
  WITH the COGS JE); FE Vitest + `npm run build`. Flow-level human UAT at the v3.0 milestone.

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

## v4.0 — Infra-debt & quality paydown (NFR-4..8)  [traces: PRD-12]

> Non-functional, no new end-user capability. Scope confirmed by the owner at the v4.0 spec
> (D-M4-1: CI + lint + harness + ledger race-safety + human UAT; CRISP/offline deferred).

## NFR-4: Continuous integration on every push  [traces: PRD-12]  **Status: planned**
- **Statement:** On every push and pull request to the GitHub repository, an automated pipeline
  (**GitHub Actions**, D-M4-2) shall run, and report a pass/fail status on the commit/PR, all of:
  backend lint (`ruff check .`), frontend lint (`npm run lint`), type-check (`tsc -b`), frontend
  unit tests (`vitest run`), frontend build (`npm run build`), and the backend `pytest` suite
  **against a live PostgreSQL service container** (so the DB-backed / integration tests of NFR-5
  actually execute in CI, not skip). A failing job shall produce a red (blocking) status.
- **Verification:** a pushed commit shows the pipeline executing every named job; a branch with a
  deliberately-broken test **and** a branch with a deliberately-introduced lint violation each turn
  the status red; a clean branch shows all jobs green. Demonstrated on a real PR.
- **Source:** BACKLOG p1 (no CI anywhere — no `.github/`); D-M3-3. The `SyerpPartner` 500 shipped
  through four plans precisely because these checks never ran automatically.

## NFR-5: Runnable integration coverage — pytest harness repair + ported cruxes  [traces: PRD-12, PRD-7, PRD-8]  **Status: done (v4.0 Phase 2 — 2a harness repaired + 2b DoD-named cruxes (formerly proven only by standalone `verify_*` scripts) ported into the pytest suite; full suite 232 passed / 0 skipped twice back-to-back, 23/23 `verify_*` scripts still exit 0)**
- **Verified (2a portion):** a2bb5a6 (Phase 02a verify, 2026-07-22 — `/zj:verify 2a`: all 6 SCs PASS empirically; full suite 219 passed / 0 skipped twice back-to-back, `git diff -- backend/app/` empty (zero product-code changes), non-vacuity re-driven, 23/23 verify_* exit 0, cold boot ok; tag `zj/good-02a-pytest-harness-repair`. The four D-P7-4 root causes (DSN, event loop, admin-user seed, isolation) are fixed.)
- **Delivered (2b portion, `chore-port-verify-cruxes`):** the DoD-named crux behaviors now run inside the ordinary `pytest` suite as NEW service-layer tests — inventory moving-avg via the SERVICE path (`test_inventory_service.py::test_moving_average_service_crux`), GL posting ties (`test_gl_posting.py::test_gl_posting_ties_crux`), AP GR/IR-clears + control↔subledger equality (`test_ap_posting.py::test_ap_posting_ties_crux`), AR aging↔1120 tie via the REAL ship flow (`test_ar.py::test_ar_posting_ties_crux`), MOUSSE WIP-clears + 5190 residual tie (`tests/mousse/test_work_orders.py`), CRUMB reservation cap (`tests/crumb/test_sales_orders.py::test_reservation_math_crux`), GELATO ship-COGS (`tests/gelato/test_shipments.py::test_gelato_ship_cogs_crux`) — plus one HTTP audit/RBAC test per new module surface (MOUSSE/CRUMB/GELATO/AR) + inventory (401/403/2xx + attributable `AuditLog`). **Non-vacuity proven per crux:** a documented product mutation flips each NAMED pytest test RED, revert restores green (SC2 table in `docs/tasks/chore-port-verify-cruxes.md`). Concurrency mutation-proofs stay in `verify_*` (D-P2a-2/D-P2b-1). Evidence: full suite **232 passed / 0 skipped** ×2, 23/23 verify_* exit 0, ruff exit 0, cold boot ok, `git diff -- backend/app/` empty (TEST-ONLY phase).
- **Statement:** The backend `pytest` suite shall execute its DB-backed tests against a live
  PostgreSQL database with **zero silent skips**, and the crux behaviors currently proven only by
  standalone `backend/scripts/verify_*.py` shall be covered by tests that run inside the ordinary
  suite. The four confirmed root causes of the silent skip (D-P7-4) shall be fixed: (1) the
  `psycopg2` DSN passed the SQLAlchemy `+psycopg2` URL; (2) the module-level async engine bound to
  a foreign event loop; (3) no seeded `admin-user`; (4) no per-test isolation.
- **Verification:** `pytest -q` reports **0 skipped** among the DB-backed tests (the ~100 formerly
  silently-skipped now run — auth/plum/syerp/core); the ported crux assertions (inventory
  moving-average + audit + RBAC, GL/AP/AR posting ties, MOUSSE WIP-clears, CRUMB reservation,
  GELATO ship COGS) are present and pass; reverting a crux turns a **pytest** test red (not only a
  `verify_*` script). The module SRD rows' remaining "UI-flow UAT-pending" caveats are **NFR-8**
  scope (human UAT), not this requirement, and stay.
- **Source:** D-P7-4 (BACKLOG p1); "port Phase-8 verify-script assertions into runnable integration
  tests" (BACKLOG p1). Enables NFR-4's live-DB CI job to be meaningful.

## NFR-6: Enforced static-analysis (lint) gates  [traces: PRD-12]  **Status: verified (v4.0 Phase 1 — both gates fixed-to-clean + enforcing; CI-wiring clause pending NFR-4/Phase 3)**
- **Verified:** ee11674 (Phase 01 verify, 2026-07-21 — `/zj:verify 1`: verifier re-ran both red→green enforce proofs independently, 23/23 `verify_*` + Vitest 131/131 + `tsc -b && vite build` + cold-boot all green, reviewer 0 findings; tag `zj/good-01-lint-gates-clean`. CI-wiring clause remains deferred to Phase 3/NFR-4.)
- **Statement:** Both lint gates shall run and pass clean and be enforced in CI (NFR-4): the
  frontend on an ESLint **flat config** (`frontend/eslint.config.js`) with the
  `@typescript-eslint` parser/plugin installed as dev dependencies, and the backend on `ruff`
  (installed in the dev environment / image). Existing violations shall be **fixed to a
  zero-violation baseline** (D-M4-3, owner — not baseline-and-ratchet).
- **Verification:** `npm run lint` and `ruff check .` each exit 0 on the clean tree; introducing a
  violation of each makes the respective command exit non-zero; both are wired as CI jobs that go
  red on violation.
- **Source:** BACKLOG p1 (recurring Phases 6/7/8 — ESLint 10 flat-config gap; `ruff` absent). Folds
  into NFR-4 once both commands work.
- **Evidence (v4.0 Phase 1, `chore-lint-gates-clean`):** FE — flat `frontend/eslint.config.js`
  (js+typescript-eslint+react-hooks@5 [D-P1-1]+react-refresh recommended, `no-unused-vars ^_`),
  `.eslintrc.cjs` deleted, `lint` script de-`--ext`'d; `npm run lint` **exit 0**. BE — `ruff` dev-venv
  `0.15.18`, ~1159 violations fixed-to-clean (1139 safe-autofix + F821×4 via TYPE_CHECKING, F811 seeded_db
  → `tests/auth/conftest.py`, E741/F841 hand-fixed, 51 load-bearing syerp re-exports `# noqa: F401`);
  `ruff check .` from `backend/` **exit 0**. Enforce-proof: each gate exits **non-zero** on a planted
  violation, **0** after revert. No regression: **23/23 `verify_*` exit 0** in-container + cold boot
  (`/health/ready` 200 + `import app.main` BOOT_OK) + Vitest **131/131 tests pass** (44 files, 0 fail/skip) + `tsc -b && vite build` exit 0.
  **Pending for NFR-4/Phase 3:** wiring both as CI jobs + ruff into the container image + `.npmrc`
  `legacy-peer-deps=true` for reproducible `npm ci`.

## NFR-7: Concurrency-safe inventory ledger  [traces: PRD-12, PRD-7, PRD-8]  **Status: planned**
- **Statement:** Every floor-guarded write to the inventory ledger — issue, adjust, receive,
  transfer, ship — shall serialize on the contended row(s) under one shared `SELECT … FOR UPDATE`
  lock discipline (sorted-id order, the `create_bill`/`record_payment` template) so the hard
  invariants hold under concurrent writers: per-location on-hand `≥ 0`, `qty_received ≤ qty_ordered`.
  The remaining **bin-blind** draw primitives (`post_transfer`, `post_adjustment`, MOUSSE
  `issue_components`) shall become **bin-aware** so the bin dimension stays consistent with location
  totals (closing the inbound half of the bin-blind-desync gap; the outbound half closed in 12b).
- **Verification:** an `asyncio`-concurrent two-writer scenario across *mixed* paths (e.g. a MOUSSE
  issue racing a SYERP adjust on the same item/location) cannot drive derived on-hand negative —
  **mutation-proven** (remove the shared lock → invariant breaches; restore → exactly one succeeds,
  the other rejects); and a bin-blind draw after a putaway no longer leaves the bin overstated /
  the unbinned pool negative (revises `verify_gelato.py` scenario E). Regression: all `verify_*`
  stay green, Trial Balance nets zero.
- **Source:** BACKLOG p2 (inventory-ledger read-check-write race, trigger now live with 3+ writers;
  bin-blind-desync inbound half). Accepted-risk single-shop until now; hardened as the multi-writer
  DoD clause.

## NFR-8: Human-verified release readiness  [traces: PRD-12, PRD-5, PRD-7, PRD-8]  **Status: planned**
- **Statement:** Before the milestone closes, every shipped user-facing flow — v1.0 PLUM
  (parts/BOM/costing/AVL/import-export), v2.0 SYERP operations + MOUSSE, v3.0 CRUMB + GELATO + AR —
  shall be exercised by a **documented human click-through** against the running stack, with a
  pass/defect result recorded per flow.
- **Verification:** the consolidated UAT checklist (`.zj/UAT-v1.0.md` round-2 + `.zj/UAT-v2.0.md`
  extended with GL/AP/reports/MOUSSE + new CRUMB/GELATO/AR checks) is complete; each defect found is
  fixed or homed to BACKLOG with an ID.
- **Source:** D-M2-2 (deferred at the v2.0 close; owed v1.0 round-2 is 2/12) + owner include-decision
  at the v4.0 spec (D-M4-1). The long-standing pre-public-release gate.

---

## Traceability

| PRD | Covered by | Gaps |
|-----|------------|------|
| PRD-1 | CORE-01, CORE-09 | — |
| PRD-2 | CORE-02..05 | — |
| PRD-3 | CORE-06..08 | — |
| PRD-4 | SYERP-01..05, PLUM-07 | — |
| PRD-5 | PLUM-01..16 | Phase-7 **verified** 2026-07-09 (`8975eeb`): fixes `5c33ed8`/`1b8bfa1`/`37b5f97` proven live, plus blocker `7562a02` (int4 overflow bricked auto-numbering) found and fixed in the verify fix loop; PLUM-01/07/10 backends now guarded by `verify_plum_vendor_paths.py`, `verify_part_numbering.py`, `test_part_number.py`, `ImportExport.test.tsx`. PLUM-04..10 flow-level UI confirmation still deferred to v1.0 milestone UAT (`.zj/UAT-v1.0.md`, 2/12 done, D-P7-5) |
| PRD-6 | FLAN-01 | expand at milestone planning |
| PRD-7 | SYERP-10..13, MOUSSE-01 | SYERP-10/11 backend built & live-verified (Phase 8: migrations 0007/0008; `verify_inventory`/`verify_purchasing`/`verify_e2e_p8` scripts), UI flow UAT deferred to v2.0 milestone (D-P7-5); **SYERP-12 built & verified (Phases 9a/9b/9c, all 9 ACs)**; **SYERP-13 (AR) expanded 2026-07-16 for v3.0 Phase 13 (7 ACs — sell-side books, invoice-from-shipment, AR aging tie-out; D-V3-1..9)**; **MOUSSE-01 materials-only slice built & live-verified (Phase 10, verified 2026-07-16 `5cffeeb`: `verify_mousse.py`/`verify_mousse_api.py`; migration 0012); routing/labor/shop-floor deferred (D-P10-1)** |
| PRD-8 | CRUMB-01, GELATO-01, SYERP-13 | **expanded 2026-07-16 (v3.0 spec, D-V3-1..9)** — CRUMB-01 (CRM + sales orders, Phase 11), GELATO-01 (warehouse core, Phase 12), SYERP-13 (AR + sell-side books, Phase 13); all `planned`, full ACs written. SYERP-13 now also traces PRD-8 (invoices flow from CRUMB sales orders). Lot/serial + email/analytics + price lists explicitly deferred |
| PRD-9 | CRISP-01, NFR-1 | CRISP coarse |
| PRD-10 | NFR-3 | — |
| PRD-11 | NFR-2 | license audit outstanding |
| PRD-12 | NFR-4, NFR-5, NFR-6, NFR-7, NFR-8 | **v4.0 spec (2026-07-20, D-M4-1..3)** — all `planned`. Infra/quality, no new end-user capability: CI on every push (GitHub Actions), pytest harness repair so the ~100 DB-backed tests run + verify_* ported into the suite, both lint gates fixed-to-clean, shared FOR-UPDATE lock across every inventory writer + inbound bin-blind fix, human UAT of all shipped flows. CRISP-01 + NFR-3 groundwork deferred (D-M4-1). |

**v3.0 spec update (2026-07-16):** SYERP-13, CRUMB-01, and GELATO-01 moved from *coarse
placeholder* to *fully-specified `planned`* (7 / 7 / 8 acceptance criteria respectively), targeting
Phases 13 / 11 / 12 of the v3.0 "Customer & logistics" milestone. No IDs renumbered (append-only);
CRISP-01 and NFR-3 remain the only coarse placeholders left. The historical counts below predate
this and the v2.0 build-out (they are left as a provenance snapshot, not re-tallied here).

**Counts (2026-07-09, post-Phase-7-verify):** implemented 19 (CORE-01..09, SYERP-01..05, PLUM-01..03 —
PLUM-01 defect **resolved** & proven live, `1b8bfa1`, and the int4-overflow blocker its fix
introduced now closed, `7562a02`; plus **SYERP-10 & SYERP-11**, whose backend
is built & **live-verified** in Phase 8 by `verify_inventory.py` (15/15), `verify_purchasing.py`
(18/18), and a fresh-DB `verify_e2e_p8.py` (18/18) — only flow-level HUMAN UI confirmation is
deferred to the v2.0 milestone UAT, D-P7-5) + 2 NFR foundations · partial 7 (PLUM-04..10 — all three
Phase-7 runtime/cache fixes landed, **verified live and guarded** by `verify_plum_vendor_paths.py`
(8/8) + `verify_part_numbering.py` (7/7) + `ImportExport.test.tsx`; flow-level UI confirmation
deferred to v1.0 milestone UAT per D-P7-5) · planned 14 (PLUM-11..16, FLAN-01, **SYERP-12 now
expanded to 9 ACs for Phase 9**, SYERP-13 [AR, split to CRUMB], MOUSSE/CRUMB/GELATO/CRISP-01,
NFR-3 — the rest coarse placeholders until their milestones near).

> **Honest caveat (do not lose):** the v1.0 human-UAT is **2/12** (`.zj/UAT-v1.0.md`; checks 1 & 8
> passed). Nothing above is marked `implemented` on the strength of a check that never ran — PLUM-04..10
> remain `partial` for exactly that reason. The live-DB pytest harness is still broken (BACKLOG p1,
> D-P7-4), so DB tests silently skip; the regression protection cited above lives in the
> `scripts/verify_*.py` live-DB gates and the frontend Vitest suite, all of which do run.
>
> **The skip is not PLUM-only** (corrected by the v1.0 milestone audit, 2026-07-09): `pytest -q`
> reports **90 passed, 98 skipped**, and the 98 span **auth 38, plum 34, syerp 17, core 7** — every
> module's DB-backed tests, not just `tests/plum/*`. Earlier wording here and in `STATE.md` understated
> the blast radius by ~3×. Gap **G3** in `.zj/MILESTONE-v1.0-AUDIT.md`.
>
> **A milestone-audit lesson:** "live-confirmed by audit" for PLUM-06 meant the *API* was confirmed.
> The UI silently discarded the API's answer (gap G1). API-level proof does not transfer to the
> component that consumes it — see `.zj/LEARNINGS.md`, Milestone v1.0.
