# SRD — BizNiceSweets
Updated: 2026-07-05

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
- **Verified:** 8975eeb (Phase 07 verify, 2026-07-09 — numeric successor proven live past the
  5→6-digit boundary; guarded by `scripts/verify_part_numbering.py` + `tests/plum/test_part_number.py`)
- **Statement:** User can create, view, edit, and delete parts.
- **Evidence:** `backend/app/modules/plum/` models/service/router, migration 0005; `frontend/src/routes/plum/PartsList.tsx`, `PartSheet.tsx`; `backend/tests/plum/test_parts.py`; human UAT 10/10 in Phase 5.
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

## Future Suites (coarse placeholders — expand via /zj:spec at milestone planning)

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
| PRD-5 | PLUM-01..16 | Phase-7 **verified** 2026-07-09 (`8975eeb`): fixes `5c33ed8`/`1b8bfa1`/`37b5f97` proven live, plus blocker `7562a02` (int4 overflow bricked auto-numbering) found and fixed in the verify fix loop; PLUM-01/07/10 backends now guarded by `verify_plum_vendor_paths.py`, `verify_part_numbering.py`, `test_part_number.py`, `ImportExport.test.tsx`. PLUM-04..10 flow-level UI confirmation still deferred to v1.0 milestone UAT (`.zj/UAT-v1.0.md`, 2/12 done, D-P7-5) |
| PRD-6 | FLAN-01 | expand at milestone planning |
| PRD-7 | SYERP-10..12, MOUSSE-01 | SYERP-10/11 backend built & live-verified (Phase 8: migrations 0007/0008; `verify_inventory`/`verify_purchasing`/`verify_e2e_p8` scripts), UI flow UAT deferred to v2.0 milestone (D-P7-5); SYERP-12 + MOUSSE-01 still coarse |
| PRD-8 | CRUMB-01, GELATO-01 | coarse — expand via /zj:spec |
| PRD-9 | CRISP-01, NFR-1 | CRISP coarse |
| PRD-10 | NFR-3 | — |
| PRD-11 | NFR-2 | license audit outstanding |

**Counts (2026-07-09, post-Phase-7-verify):** implemented 19 (CORE-01..09, SYERP-01..05, PLUM-01..03 —
PLUM-01 defect **resolved** & proven live, `1b8bfa1`, and the int4-overflow blocker its fix
introduced now closed, `7562a02`; plus **SYERP-10 & SYERP-11**, whose backend
is built & **live-verified** in Phase 8 by `verify_inventory.py` (15/15), `verify_purchasing.py`
(18/18), and a fresh-DB `verify_e2e_p8.py` (18/18) — only flow-level HUMAN UI confirmation is
deferred to the v2.0 milestone UAT, D-P7-5) + 2 NFR foundations · partial 7 (PLUM-04..10 — all three
Phase-7 runtime/cache fixes landed, **verified live and guarded** by `verify_plum_vendor_paths.py`
(8/8) + `verify_part_numbering.py` (7/7) + `ImportExport.test.tsx`; flow-level UI confirmation
deferred to v1.0 milestone UAT per D-P7-5) · planned 13 (PLUM-11..16, FLAN-01, SYERP-12,
MOUSSE/CRUMB/GELATO/CRISP-01, NFR-3 — coarse placeholders until their milestones near).

> **Honest caveat (do not lose):** the v1.0 human-UAT is **2/12** (`.zj/UAT-v1.0.md`; checks 1 & 8
> passed). Nothing above is marked `implemented` on the strength of a check that never ran — PLUM-04..10
> remain `partial` for exactly that reason. The PLUM pytest harness is still broken (BACKLOG p1), so
> `tests/plum/*` DB tests silently skip; the regression protection cited above lives in the
> `scripts/verify_*.py` live-DB gates and the frontend Vitest suite, all of which do run.
