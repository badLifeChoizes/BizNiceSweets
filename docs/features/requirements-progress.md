# Requirements Progress

Tracks completed requirements by phase, with implementing plans and evidence.

> **Evidence caveat (Phase 7, D-P7-4):** the PLUM pytest files below (`test_bom.py`,
> `test_avl.py`, `test_costing.py`, `test_import_export.py`, `test_parts.py`) have **never
> actually run** — a broken `skip_if_no_db` probe silently skipped them, which is how the
> `SyerpPartner` 500 shipped through Phase 6 marked "Complete". Harness repair is BACKLOG p1.
> Phase-7 status below reflects *verified* reality: code fixes proven by live-DB standalone
> proofs, and flow-level UI confirmation deferred to the v1.0 milestone UAT
> (`.zj/UAT-v1.0.md`, D-P7-5) — **not** claimed Complete on an unrun test.

---

## PLUM Module

| Requirement | Description | Phase | Plans | Evidence | Status |
|-------------|-------------|-------|-------|----------|--------|
| PLUM-01 | User can create, view, edit, and delete parts | Phase 5, 7 | 05-01, 05-02, 07 | Phase-7 numeric part# fix `1b8bfa1` — **proven live** (DB had `P100000` → generator returned `P100001`). `/zj:verify 07` found that fix cast the suffix to int4: a legal `P9999999999` row made every auto-numbered create 500 **permanently** — fixed `7562a02` (`Numeric` cast). Guarded by `scripts/verify_part_numbering.py` (7/7 live, red/green proven) + `tests/plum/test_part_number.py` (4 pure tests that actually run) | Complete |
| PLUM-02 | User can search and filter parts | Phase 5 | 05-01, 05-02 | test_parts.py (Phase-5 UAT 10/10) | Complete |
| PLUM-03 | User can create part revisions and advance a part through its status workflow | Phase 5 | 05-01, 05-02 | test_revisions.py (Phase-5 UAT); Released-immutability spot-checked Phase-7 (UAT check 8) | Complete |
| PLUM-04 | User can build a multi-level BOM and view it as an expandable tree | Phase 6, 7 | 06-01, 06-02, 06-04, 06-05 | BomTree.tsx; UAT check 1 (Add Part on Draft) **passed** Phase-7; test_bom.py pending harness | Code done; UI UAT pending (check 2 for flat view) |
| PLUM-05 | User can view a flat BOM with quantity roll-up across levels | Phase 6 | 06-01, 06-02, 06-04, 06-05 | BomTree.tsx flat mode; test_bom.py pending harness | Code done; UI UAT pending (check 2) |
| PLUM-06 | User can run where-used analysis to see which assemblies consume a part | Phase 6 | 06-01, 06-02, 06-05 | PartDetail.tsx Where-Used card; test_bom.py pending harness | Code done; UI UAT pending (check 3) |
| PLUM-07 | User can link a part to one or more vendors (FK to SYERP vendors / AVL) | Phase 6, 7 | 06-01, 06-02, 06-04, 06-05, 07 | Runtime 500 fixed `5c33ed8` (Partner alias); AvlLinkSheet.tsx. `/zj:verify 07`: `add_avl_link` accepts an `is_vendor=True` Partner and 422s a non-vendor — proven live and guarded by `scripts/verify_plum_vendor_paths.py` (red/green proven per alias site) | Runtime fix landed, backend verified live & guarded; UI UAT pending (checks 4, 9) |
| PLUM-08 | User can set part pricing/cost and see cost roll-up across a BOM | Phase 6 | 06-01, 06-02, 06-05 | Cost & Margin card; manual+roll-up live-verified (audit); vendor-price source now reachable (PLUM-07 fixed) | Code done; UI UAT pending (check 5) |
| PLUM-09 | User can view margin analysis for a product | Phase 6 | 06-01, 06-02, 06-05 | Cost & Margin card; margin calc live-verified (audit) | Code done; UI UAT pending (check 6) |
| PLUM-10 | User can import and export PLUM data as JSON and Excel | Phase 6, 7 | 06-01, 06-03, 06-05, 07 | Vendor-path 500 fixed `5c33ed8`; cache invalidation on commit `37b5f97`. `/zj:verify 07`: `build_json_export`/`validate_import`/`commit_import` vendor paths proven live and guarded by `scripts/verify_plum_vendor_paths.py`; invalidation pinned by `ImportExport.test.tsx` (positive **and** negative path) | Fixes landed, backend verified live & guarded; UI UAT pending (checks 7, 10, 11) |

---

## SYERP Module

> **Evidence caveat (Phase 8, D-P7-4):** the backend live-DB pytest harness is still broken, so
> Phase-8 truth comes from **standalone async scripts run against live Postgres** (`backend/scripts/
> verify_inventory.py`, `verify_purchasing.py`, `verify_e2e_p8.py`) plus pure-Decimal/FSM/generator
> unit tests that need no DB. No SYERP-10/11 status below rests on an unrun live pytest. Flow-level
> HUMAN UI confirmation (in-browser click-through) is deferred to the v2.0 milestone UAT
> (`.zj/UAT-v2.0.md`, D-P7-5), exactly as Phase 7 did for PLUM.

| Requirement | Description | Phase | Plans | Evidence | Status |
|-------------|-------------|-------|-------|----------|--------|
| SYERP-10 | Inventory: items, flat locations, immutable txn ledger, on-hand-by-location, moving-average valuation, adjust/transfer with negative-stock reject | Phase 8 | 08 | Migration `0007_syerp_inventory.py` (`b5c5c31`); item CRUD + numeric-safe `ITEM-####` (`511d6ae`); location CRUD + idempotent `Main` seed (`06f318c`); derived on-hand/valuation/ledger reads (`e35021e`); receipt + pure-Decimal `compute_new_moving_avg` (`8e1b31f`); adjustment + negative guard (`0074bf0`); transfer nets-zero + underflow guard (`5f2a228`); UI `1fd2423`/`8e75af9`/`8b2c748`/`c9d6952`/`cdf0e6c`. **Live-DB: `verify_inventory.py` 14/14 PASS (`e309260`); `verify_e2e_p8.py` 18/18 PASS on fresh DB (`3703c51`).** Unit: `backend/tests/syerp/test_inventory.py` | Backend built & live-verified; UI flow UAT pending (v2.0 milestone) |
| SYERP-11 | Purchase orders: Draft→Approved→Receiving→Closed FSM, numeric PO#, vendor-only, receiving posts SYERP-10 receipts, status roll-up, over-receipt reject, vendor history | Phase 8 | 08 | Migration `0008_syerp_purchasing.py` (`cafa93f`); PO draft CRUD + numeric-safe `PO-####` + vendor-only guard (`b5d7882`); approve/close FSM (`92896ea`); receiving → real inventory receipt + over-receipt reject + roll-up (`79181bd`); vendor history totals (`ce5f666`); UI `6d8afcc`/`e21ac2a`/`cd03899`/`8aa6b65`. **Live-DB: `verify_purchasing.py` 18/18 PASS (`451ec7d`); `verify_e2e_p8.py` 18/18 PASS on fresh DB (`3703c51`).** Unit: `backend/tests/syerp/test_purchasing.py` | Backend built & live-verified; UI flow UAT pending (v2.0 milestone) |
| SYERP-12 (AC1/2/3/8/9) | GL posting engine: balanced-only double-entry `JournalEntry`/`JournalLine` (append-only, reversal via self-FK), derived account balances + register, PO-receipt auto-posts a balanced Dr 1130 / Cr 2150 GR/IR entry atomically with the stock receipt, audit + RBAC on all GL endpoints | Phase 9a | 09a | Seed GR/IR `2150` (`8b97fc2`); pure balance helpers (`9844b3e`); `JournalEntry`/`JournalLine` models (`f570f68`); migration `0009_syerp_gl_journal.py` (`343b334`); post/reverse/register services (`fd9adf1`, uuid-str schema fix `89daadc`); endpoints + audit + RBAC (`dee9820`); receipt auto-post (`0d9eb98`); UI journal list/post/reverse + register (`38d65b1`/`c2bde3d`/`706432c`). **Verify-loop fixes:** zero-cost receipt no longer self-rejects (M1), double-reversal refused 409 (M2), receipt audit is entry-targeted (m5). **Live-DB: `verify_gl.py` 28/28 PASS** (balanced/reject/reverse, derived balances + coalesce fix, atomic receipt→JE, atomicity rollback, zero-cost, double-reversal guard); **`verify_gl_api.py` 9/9 PASS** (gl.journal_posted/reversed audit rows + 403/401 RBAC over live HTTP). Unit: `backend/tests/syerp/test_gl_journal.py` (13). FE: `JournalEntries.test.tsx`, `AccountRegister.test.tsx`. | AC1/2/3/8/9 backend built & live-verified; **AC4–7 (AP bills/match/payments, aging, statements) pending Phase 9b/9c**; UI flow UAT pending (v2.0 milestone) |
| SYERP-12 (AC4/AC5) | Accounts payable: receipt-driven vendor bill w/ exact PO-line match (Dr GR/IR 2150) + non-PO expense lines (Dr chosen EXPENSE/ASSET), one balanced JE via the 09a engine (Cr AP 2110), Draft→Posted→Paid FSM, payments (Dr AP / Cr chosen cash-or-bank 1110/1111) with partial + overpayment 4xx + auto-Paid, audit + RBAC on all AP endpoints | Phase 9b | 09b | Pure Decimal helpers + `test_ap.py` 14 (`c1b431b`); `Bill`/`BillLine`/`Payment`/`PaymentAllocation` models (`1697973`); migration `0010_syerp_ap_bills.py` (`b91ed73`); seed `1111 Bank – Checking` (`5502445`); unbilled-receipts + `create_bill` match (`52d9a83`, in-payload dup guard `13ca4cd`); `post_bill` balanced JE + FSM (`3b8eb33`); `record_payment` + allocations + overpay guard (`be0a774`); schemas (`ff39967`); bill + payment routers w/ audit + RBAC (`7ef302b`/`e7bb9b2`/`99ef164`); UI Bills list + create/match dialog (`4e25ab2`), bill detail + post + pay (`bb57463`), routes + nav (`72cfd82`). **Verify fix-loop:** row-locked the concurrent double-bill/overpayment race (`380c73b`, REVIEW #1). **Live-DB: `verify_ap.py` 24/24 PASS** (unbilled surface, exact-match accept/422, non-PO expense, balanced post, **GR/IR-clears-to-zero crux Decimal-exact**, partial/full/auto-Paid payments, overpayment persists-nothing, 1110-vs-1111 cash select, **two concurrency race scenarios**); **`verify_ap_api.py` PASS** (bill.created/posted + payment.recorded audit + 403/401/200 RBAC over live HTTP). Unit: `test_ap.py` (14). FE: `Bills.test.tsx`, `BillDetail.test.tsx`. | AC4/AC5 backend + UI built & live-verified; **AC6/7 (AP aging, financial statements) pending Phase 9c**; UI flow UAT pending (v2.0 milestone) |
| SYERP-12 (AC6/AC7) | AP aging (per-vendor + grand-total buckets current/31–60/61–90/90+ from `bill_date`, tied out to the derived 2110 control) + the three core financial statements (Trial Balance Σdebit==Σcredit, P&L revenue−expense over a range, Balance Sheet assets==liabilities+equity with a computed current-year net-income equity line); all derived read-only from posted GL activity filtered by `entry_date`, RBAC-gated | Phase 9c | 09c | `Bill.bill_date` model col (`f6b9635`); migration `0011_syerp_bill_date.py` NOT NULL + `created_at::date` backfill (`cab8531`); `bill_date` wired through `BillCreate`/`create_bill` + `post_bill` JE `entry_date=bill.bill_date` for subledger↔2110 tie-out (`729ec00`); report read schemas (`69e4724`); `ap_aging_report` + 2110 tie-out (`c24c9f6`); `trial_balance` (`7aecf7c`); `profit_loss` (`1d38ddb`); `balance_sheet` w/ computed 3130 net income (`6f79047`); 4 read-only report endpoints + `syerp:read` RBAC (`a9cae54`). **Live-DB: `verify_reports.py` 17/17 PASS** (aging buckets, **tie-out crux `grand_total==control_balance` Decimal-exact** incl. partial-payment & draft-exclusion, TB nets zero + parents absent, P&L in/out-of-period net income, BS balances w/ computed net-income line); **`verify_reports_api.py` PASS** (200/401/403 across all 4 endpoints + 422 missing-bound, read-only → no mutation audit). Regression: `verify_ap`/`gl`/`purchasing`/`inventory`/`e2e_p8` all exit 0 unchanged. UI: AP Aging screen (`c6b47d3`), Financial Reports tabbed page (`8994f5c`), routes+nav+bill-date field (`48c8453`). FE: `ApAging.test.tsx` (4), `FinancialReports.test.tsx` (3); full suite 79/79. | AC6/AC7 backend + UI built & live-proven by verify scripts; verified `/zj:verify 09c` (`ca8ce98`); UI flow UAT pending (v2.0 milestone) |

---

## MOUSSE Module

> **Evidence caveat (D-P7-4):** as with SYERP, the backend live-DB pytest harness is still broken, so
> MOUSSE truth comes from **standalone async scripts run against live Postgres** (`verify_mousse.py`,
> `verify_mousse_api.py`) plus the frontend Vitest suite. No status below rests on an unrun live pytest.

| Requirement | Description | Phase | Plans | Evidence | Status |
|-------------|-------------|-------|-------|----------|--------|
| MOUSSE-01 (materials-only slice) | Work orders that consume a PLUM single-level BOM + SYERP inventory to produce a finished good: create → release (direct-BOM snapshot) → issue (Dr 1140 WIP / Cr 1130 at moving-avg, floor-guarded, row-locked) → complete (Dr 1130 / Cr 1140 so **1140 clears to zero** AND **1130 ties to the inventory subledger**, residual to 5190 Inventory Rounding — D-P10-2 amended); FSM Draft→Released→In Progress→(On Hold⇄In Progress)→Completed + Cancel; under-issue completion blocked unless audited `override_incomplete` (D-P10-9); RBAC + audit on every mutation | Phase 10 | 10 | New `backend/app/modules/mousse/` module: models (`162c463`), migration `0012_mousse_work_orders.py` (`dd40197`), schemas (`f94c5a9`), service create/list/detail (`09c5a64`), FSM+release+cancel+hold/resume (`c84bf2b`), issue Dr1140/Cr1130 (`21ad021`), complete WIP-clears+FG receipt (`83b4d0e`), router+RBAC+audit (`1f75d62`), register (`2e04ffc`); perms seeded (`0ce67ae`). **Verify fix-loop (`/zj:verify 10`):** completion residual routed to new **5190 Inventory Rounding** so the 1130 control account ties to the subledger (was a permanent sub-quantum drift on non-divisible WIP) — `5cffeeb`. **Live-DB: `verify_mousse.py` 34/34 PASS** (release snapshot, issue Dr1140/Cr1130, **WIP-clears-to-zero crux Decimal-exact**, **1130-subledger tie + 5190 residual**, hold/resume, under-issue override, **concurrent-issue race via `asyncio.Barrier`**); **`verify_mousse_api.py` 34/34 PASS** (403/401/200 RBAC + attributable audit on every route). Regression: full 13/13 verify_* exit 0, TB nets zero. FE: `WorkOrders.tsx`/`WorkOrderDetail.tsx` + dialogs, `routes/mousse/*.test.tsx` (Vitest), `npm run build` clean. | **Materials-only slice built & live-verified (`/zj:verify 10`, 2026-07-16, `5cffeeb`)**; routing/labor/shop-floor deferred (D-P10-1); UI flow UAT pending (v2.0 milestone) |

---

## CRUMB Module

> **Evidence caveat (D-P7-4):** as with SYERP/MOUSSE, the backend live-DB pytest harness is still broken
> (pytest is not even installed in the api container — BACKLOG p1), so CRUMB truth comes from **standalone
> async scripts run against live Postgres** (`verify_crumb.py`, `verify_crumb_api.py`) plus the frontend
> Vitest suite. No status below rests on an unrun live pytest.

| Requirement | Description | Phase | Plans | Evidence | Status |
|-------------|-------------|-------|-------|----------|--------|
| CRUMB-01 (inventory-free portion) | New `crumb` CRM module against SYERP customers: **leads** (create/edit/archive → link-or-create a `Partner.is_customer` → convert to an opportunity); **opportunity pipeline** (customer, estimated value, expected close, server-enforced stage FSM Qualify→Proposal→Won/Lost, per-stage grouped list, a Won opportunity spawns a quote — D-V3-15); **quotes** (header + PLUM-part or free-text lines; line `unit_price` defaults from the part's PLUM released `released_cost_snapshot` × (1 + 30% markup, D-V3-14) and is per-line editable; numeric-safe `QUOTE-####`; FSM Draft→Sent→Accepted/Rejected/Expired); append-only **communication log** (call/email/note/meeting, UTC-stamped, per-customer timeline). Router-layer audit on every mutation; `crumb:read`/`crumb:write` RBAC. **(Sales orders + soft-reservation = AC4, deferred to 11b — D-V3-10.)** | Phase 11a | 11a | New `backend/app/modules/crumb/` module (mirrors MOUSSE new-module pattern): models 5 tables (`e57459c`), migration `0013_crumb_crm_pipeline.py` (`5391918`), `crumb:read`/`crumb:write` perms (`79fcf31`), schemas (`3cd5b1f`), `crumb/service/` package + FSM/markup helpers (`6bbb5d5`), quotes service PLUM-priced lines + `QUOTE-####` gen + FSM (`e145998`), leads service (`67744c1`), interactions service (`8154c7c`), opportunities service stage FSM + pipeline + spawn-quote (`0dc2ddd`), router + self-registration + router-layer audit (`ff88aeb`). **Live-DB: `verify_crumb.py` 20/20 PASS** (both link-existing & create-new customer, conversion stamps both sides + no-customer 422, stage FSM valid walk + invalid/terminal reject + won-only spawn gate, quote FSM valid+invalid, **PLUM cost×1.30 default + override + null-snapshot→0**, **numeric-safe `QUOTE-####` boundary + junk-row survival (D-P8-6)**, Σ line totals == `total_value` Decimal-exact, interaction append + newest-first timeline); **`verify_crumb_api.py` 50/50 PASS** (writer/reader/noperm — mutations 2xx/403/401, reads 200/403/401 + attributable `AuditLog` rows per mutation type — the SC6 HTTP gate). Regression: 13/13 existing verify_* exit 0. FE: `routes/crumb/` nav+hooks+routes (`402d0482`), leads (`d409d4d`), pipeline (`2fef975`), quote builder+line editor (`3550f69`), comm-log timeline (`1a6fbcd`), 4 colocated Vitest + build gate (`326dd4a`); full FE suite 95/95, `npm run build` exit 0. | **Inventory-free portion VERIFIED (`/zj:verify 11a`, 2026-07-16, `efcf2e6`, tag `zj/good-11a-crumb-crm-pipeline`)** — verify_crumb 22/22 + verify_crumb_api 54/54 (counts grew after the fix loop added the free-text-guard + spawn-audit + bad-opportunity-id assertions) + 13/13 regression + FE 4/4 + build. 4 verify/review gaps fixed at close (`a697c69`): free-text-line description guard, convert re-resolves customer, bad opportunity_id → 404, spawned quote gets its own `quote.created` audit row. AC4 (sales orders + soft-reservation) + accepted-quote→SO conversion deferred to Phase 11b; UI flow UAT pending (v3.0 milestone) |
| CRUMB-01 (sales orders + soft-reservation — AC4 + AC3 SO-conversion tail) | Extends `crumb` with **sales orders**: `SalesOrder`/`SalesOrderLine` models + migration `0014`; `SO-####` numeric-safe numbering; direct create (header + Draft-only editable lines) + FSM Draft→Confirmed→Fulfilling→Closed (+Cancelled from Draft/Confirmed), server-enforced 4xx; **accepted-quote→SO conversion** copying lines with `item_id` resolved from the PLUM-part link; the **soft-reservation crux** — confirming reserves `min(qty_ordered, available)` per line where `available = get_item_on_hand − Σ open (confirmed/fulfilling) reservations ≥ 0` (never negative), over-order shows derived shortage (not blocked), non-stock line reserves 0, cancel releases; `InventoryItem` rows `FOR UPDATE`-locked in sorted-id order before the read so concurrent confirms cannot over-reserve. Router-layer audit + `crumb:read`/`crumb:write` RBAC. **Posts NO GL** (soft quantity — TB nets zero). | Phase 11b | 11b | models `SalesOrder`/`SalesOrderLine` (`3f37d72`), migration `0014` (`567a48d`), `SO_TRANSITIONS` (`c6b5b64`), SYERP `get_item_on_hand` helper (`f19964e`), schemas (`ce3d13f`), SO service create/FSM (`a80bba1`), conversion (`b69034e`), **confirm/cancel soft-reservation** (`692dbda`, mandated adversarial review PASS `REVIEW-task8.md`), router+audit (`9f5c563`), `verify_crumb_so.py` (`0ab87bf`) + `verify_crumb_so_api.py` (`d8515f4`), FE hooks/routes/nav (`73030eb`), convert button (`ed1cb59`), list+create (`69cbc48`), detail (`1233aea`), tests (`888ffc6`). **Verify fix loop (`fec334f`)**: direct-create/edit SO lines never bridged `plum_part_id→item_id` (the UI line-editor shape) so UI-created orders reserved 0 — fixed + pinned by new (D2) assertions. | **VERIFIED (`/zj:verify 11b`, 2026-07-17, `fec334f`, tag `zj/good-11b-crumb-sales-orders`)** — verify_crumb_so 27/27 (incl. concurrency scenario F, load-bearing) + verify_crumb_so_api 40 + 15/15 regression = **17/17**; FE Vitest + `npm run build` exit 0; TB nets zero. **CRUMB-01 now complete (all ACs).** UI flow UAT pending (v3.0 milestone) |

---

## GELATO Module

> **Evidence caveat (D-P7-4):** as with SYERP/MOUSSE/CRUMB, the backend live-DB pytest harness is still
> broken (pytest is not installed in the api container — BACKLOG p1), so GELATO truth comes from
> **standalone async scripts run against live Postgres** (`verify_gelato.py`, `verify_gelato_api.py`)
> plus the frontend Vitest suite. No status below rests on an unrun live pytest.

| Requirement | Description | Phase | Plans | Evidence | Status |
|-------------|-------------|-------|-------|----------|--------|
| GELATO-01 (inbound foundation — bins + directed putaway; AC1/AC2/AC6 + putaway-side AC7/AC8) | New `gelato` module (mirrors MOUSSE/CRUMB new-module package shape) self-registering at `/api/v1/gelato`; migration **0015** adds a `gelato_bin` table (int PK) + a nullable `bin_id` column on the SYERP-core `syerp_inventory_txn` ledger via a **string table-name FK** (hub-direction inversion, no import cycle — D-P12a-3). **Bins CRUD** scoped to a SYERP stock location (unique-within-location, archive-hides). **Per-bin on-hand derives** from the shared ledger (`get_bin_on_hand` = Σ signed qty for `(item, location, bin_id)`, null-aware for the unbinned pool) and **rolls up Decimal-exact** to the SYERP per-location total (existing on-hand SUMs never filter `bin_id`, so the roll-up is automatic — SC3). **Directed putaway** (`post_putaway`, a SYERP-owned bin-aware clone of `post_transfer`, D-P12a-7) moves qty unbinned→bin / bin→bin as two paired `txn_type="putaway"` legs sharing a fresh `transfer_group_id`, **net-zero at location grain**; source-pool floor guard 4xx; **`InventoryItem` FOR UPDATE-locked** in sorted-id order before the floor read so two concurrent putaways cannot over-draw (D-P12a-6). Directed target-bin suggestion (heuristic, user-confirmable). Router-layer audit + `gelato:read`/`gelato:write` RBAC. **Posts NO GL** (inbound-only — TB nets zero). **(Pick/pack/ship + COGS JE + reservation relief = AC3/AC4/AC5 + ship-side AC7, deferred to 12b — D-P12a-1.)** | Phase 12a | 12a | New `backend/app/modules/gelato/` module: `Bin` model + `bin_id` ledger column + package (`b0b0dcd`), module wiring + model aggregation (`2cc1161`), migration `0015_gelato_bins.py` (`7449fb4`), `gelato:read`/`gelato:write` perms (`57745e5`), schemas (`24c47ed`), SYERP `post_putaway`+`get_bin_on_hand` primitives (`5de6ea6`), GELATO bin-CRUD+putaway-orchestration service (`f548f2e`), router+RBAC+audit (`f8dd454`), **audit `target_id` int→str fix** for the first int-PK audited entity (`136e98d`), `verify_gelato.py` (`b77b781`) + `verify_gelato_api.py` (`6417e48`), full regression (`cd911e5`); FE hooks/nav/routes (`f46bce4`), Bins screen (`7ab258c`), Putaway screen (`82e37c5`). **Verify fix loop (`/zj:verify 12a`)**: review MAJOR — bin split desyncs after any bin-blind draw (transfer/adjust/MOUSSE-issue) — documented as the known 12a→12b boundary (`get_bin_on_hand` trust-boundary docstring + BACKLOG p2), and **pinned by `verify_gelato.py` scenario (E)** which proves the SC3 location roll-up survives a bin-blind draw exactly (split lies, location truth intact). **Live-DB: `verify_gelato.py` 11/11 PASS** (net-zero across putaways, **roll-up equality Decimal-exact**, over-draw 422 + no rows, **concurrency Barrier load-bearing** — FOR UPDATE, mutation-proven, scenario D, **bin-blind boundary** scenario E); **`verify_gelato_api.py` 29/29 PASS** (401/403/200 RBAC + attributable audit incl. the `str(bin_.id)` fix). Regression: full **17/17** verify_* exit 0, TB `in_balance` True. FE: `routes/gelato/` nav+hooks+routes, Bins + Putaway screens + colocated Vitest, `npm run build` exit 0. | **Inbound foundation VERIFIED (`/zj:verify 12a`, 2026-07-18, `52eb481`, tag `zj/good-12a-gelato-bins-putaway`)** — 11/11 + 29/29 + 17/17 regression + FE Vitest/build; TB nets zero. AC3/AC4/AC5 (pick/pack/ship + COGS JE + reservation relief) + ship-side AC7 deferred to Phase 12b; bin-split-after-bin-blind-movement is the documented 12a boundary (BACKLOG p2, closed by 12b bin-aware pick/issue); UI flow UAT pending (v3.0 milestone) |
| GELATO-01 (outbound — pick → pack → ship + COGS JE + reservation relief; AC3/AC4/AC5 + ship-side AC7) | Migration **0016** adds `gelato_shipment` + `gelato_shipment_line` (int PK, string table-name FKs) and `qty_picked`/`qty_shipped` accumulators on `crumb_sales_order_line` (server_default 0, backfills existing rows). New SYERP bin-aware **`post_issue`** primitive (clones `post_putaway`'s FOR UPDATE lock-before-floor-read + cumulative per-bin guard into a single signed `-qty` `issue` leg, `commit` param). GELATO `service/shipments.py`: **pick** = bin-aware net-zero pick-bin→staging via `post_putaway` (stamps `qty_picked`, auto-advances SO confirmed→fulfilling, D-P12b-10); **pack** = FSM picking→packed, partial packs trim staged qty; **ship** = `post_issue` from staging at moving-avg cost ATOMIC with ONE balanced **Dr 5100 COGS / Cr 1130 Inventory** JE (single `db.commit()`, inner calls `commit=False`), relieves `qty_reserved` (floored ≥0, keeps `_reserved_by_other_open_sos` accurate), stamps `qty_shipped`, over-ship 422, staging-floor 422, FSM 409 on re-ship. **SHIPMENT_TRANSITIONS** FSM (picking→packed→shipped, cancelled from picking). Thin RBAC-gated router with `write_audit(target_id=str(shipment.id))` (int-PK→str). | Phase 12b | 12b | SO-line accumulators (`61a695e`), Shipment/ShipmentLine models (`6515f50`), schemas (`074d1c0`, FK-type fix `6fa9c0f`), migration 0016 (`9a0c867`), SYERP `post_issue` (`2940d61`) + `post_putaway` `commit` param (`9b87e14`), pick service (`53b3b88`), pack service (`3f06ed3`), ship service (`0082f9d`), router (`c248fdf`), `verify_gelato_ship.py` (`51466dd`) + `verify_gelato_ship_api.py` (`79197f3`); FE shipment hooks/nav/route (`304f78a`), Fulfillment pick/pack/ship screen (`6d319b2`), SO-detail Fulfill/Ship affordance + qty_shipped (`da3f5d7`), `SalesOrderLineRead` qty_picked/qty_shipped serialization fix (`65a1425`). **Verify fix loop (`/zj:verify 12b`)**: review BLOCKER — two concurrent ships of ONE packed shipment gated on an UNLOCKED shipment status → double COGS post; **fixed** by loading the shipment `SELECT … FOR UPDATE` before the FSM gate, and **pinned by `verify_gelato_ship.py` scenario (h)** (mutation-proven: removing the lock regresses to 2 JEs / qty_shipped 10 / staging drawn twice). **Live-DB: `verify_gelato_ship.py` 21/21 PASS** (COGS JE Decimal-exact, control↔subledger tie, reservation relief, partial-ship accumulation, over-pick/over-ship/staging-floor rejects, scenario (g) scarce-bin concurrency + scenario (h) same-shipment double-ship, both mutation-proven); **`verify_gelato_ship_api.py` 23/23 PASS** (401/403/200 + attributable audit + int-PK `target_id` str guard). Regression: full **21/21** verify_* exit 0, TB nets zero WITH the ship COGS JE, 1130 ties to subledger. FE: Fulfillment screen + SO-detail affordance + colocated Vitest asserting the real POST payload, `npm run build` exit 0. | **Outbound VERIFIED (`/zj:verify 12b`, 2026-07-19, `553bcfb`, tag `zj/good-12b-gelato-pick-pack-ship`)** — 21/21 + 23/23 + 21/21 regression + FE Vitest/build; TB nets zero with the COGS JE. Closes the OUTBOUND half of the BACKLOG p2 bin-blind-draw item; the cross-path ledger row-lock + inbound-path bin-blindness remain p2. UI flow UAT pending (v3.0 milestone) |

---

*Last updated: 2026-07-19 — Phase 12b verified (`/zj:verify 12b`): GELATO outbound pick→pack→ship +
COGS JE (Dr 5100 / Cr 1130) + reservation relief (GELATO-01 AC3/AC4/AC5 + ship-side AC7). Verify fix
loop caught + fixed a BLOCKER (concurrent same-shipment double-ship → double COGS post; shipment-row
FOR UPDATE lock added, mutation-pinned by verify_gelato_ship scenario h). 21/21 verify_gelato_ship +
23/23 verify_gelato_ship_api + 21/21 regression + FE Vitest/build; TB nets zero with the JE. See prior
entry for Phase 12a.*

<!-- superseded 2026-07-18 --> *Phase 12a verified (`/zj:verify 12a`, `52eb481`, tag
`zj/good-12a-gelato-bins-putaway`): GELATO inbound foundation — bins CRUD + directed putaway, per-bin
on-hand rolls up Decimal-exact to the location total, putaway nets zero at location grain, FOR UPDATE
concurrency crux load-bearing (GELATO-01 AC1/AC2/AC6 + putaway-side AC7/AC8). 11/11 verify_gelato (incl.
bin-blind boundary scenario E) + 29/29 verify_gelato_api + 17/17 regression + FE Vitest/build; TB nets zero
(no GL). Verify fix loop documented + pinned the one review MAJOR (bin split desyncs after a bin-blind
draw) as the known 12a→12b boundary (BACKLOG p2). Pick/pack/ship + COGS JE = Phase 12b. Live pytest
harness still broken (D-P7-4, BACKLOG p1) — no criterion depends on it.*

*Prior: 2026-07-17 — Phase 11b verified (`/zj:verify 11b`, `fec334f`, tag
`zj/good-11b-crumb-sales-orders`): CRUMB sales orders + soft-reservation + accepted-quote→SO conversion
(CRUMB-01 AC4 + AC3 tail) — **CRUMB-01 now complete (all ACs)**. 17/17 verify_* (incl. concurrency
scenario F) + FE Vitest/build; TB nets zero (no GL). Verify fix loop caught + fixed a blocker the harness
hid (direct-create SO lines never resolved `plum_part_id→item_id` → UI orders reserved 0), pinned by new
(D2) assertions. Live pytest harness still broken (D-P7-4, BACKLOG p1) — no criterion depends on it.*

*Prior: 2026-07-16 — `/zj:verify 10` (Phase 10 MOUSSE materials-only WO core) **Verdict PASS**
after a fix loop closing one major: WO completion debited 1130 and credited 1140 for the same
`accumulated_wip`, but the FG receipt capitalises only `planned_qty × fg_unit_cost` into the inventory
subledger, so on non-divisible WIP (100/3) the 1130 control account permanently drifted from the
subledger by a sub-quantum residual. Fixed by a 3-line completion JE routing the residual to a new
seeded **5190 Inventory Rounding** account (D-P10-2 amended) — 1140 still clears to zero AND 1130 now
ties to the subledger, both Decimal-exact; pinned by `verify_mousse.py` scenario D (`5cffeeb`). MOUSSE-01
materials-only slice (AC1–AC7) delivered & live-verified; routing/labor/shop-floor deferred (D-P10-1).*

*Prior: 2026-07-12 — `/zj:build 09c` (Phase 9c AP aging + financial statements) **build complete**
on branch `feature-syerp-financial-reports`. All 15 PLAN tasks done, atomic commits. Delivers SYERP-12
AC6/AC7: AP aging (per-vendor + grand total, aged from a new `Bill.bill_date`, tied out to the derived
2110 control) and Trial Balance / P&L / Balance Sheet, all read-only from posted GL filtered by
`entry_date`, `syerp:read`-gated. The tie-out crux (`aging grand_total == derived 2110`, Decimal-exact,
draft-excluded) is proven in `verify_reports.py` (17/17); RBAC in `verify_reports_api.py`; 5 prior verify
scripts + backend pytest 117/100-skip + FE 79/79 all unchanged. Next: `/zj:verify 09c`.*

*Prior: 2026-07-12 — `/zj:verify 09b` (Phase 9b AP bills, PO match & payments). Verdict PASS
after a fix loop closing one major: concurrent `create_bill`/`record_payment` could defeat the
double-bill/overpayment guards under READ COMMITTED (read-then-write, no row lock) — now
`SELECT … FOR UPDATE`-serialized in sorted id order and pinned by two durable `verify_ap.py`
concurrency scenarios (24/24). Two minor edge-cases logged to the phase PLAN `## Noticed`
(fractional multi-lot GR/IR sub-micro residue; a zero-qty matched line yields an unpostable draft).
SYERP-12 AC4/AC5 delivered + live-verified; AC6/7 remain in Phase 9c.*

*Prior: 2026-07-11 — `/zj:verify 09a` (Phase 9a GL posting engine). Verdict PASS after a
fix loop closing two majors — the zero-cost PO-receipt regression (an all-zero auto-post 422'd the
whole receipt, M1) and a missing double-reversal guard (re-reversal diverged the derived control
account from inventory, now 409, M2) — plus a traceable receipt audit target (m5). The two
MISSING-regression-protection criteria became durable tests: `verify_gl.py` gained the atomicity-
rollback, zero-cost, and double-reversal scenarios (28/28), and a new `verify_gl_api.py` pins the
audit rows + 403/401 RBAC over live HTTP (9/9). SYERP-12 AC1/2/3/8/9 delivered; AC4–7 remain in 9b/9c.*

*Prior: 2026-07-09 — `/zj:verify 07` (Phase 7 verified, tag `zj/good-07-close-v1-0-gaps`).
Verdict PASS after a fix loop that closed one **blocker**: the phase's own numeric part-number fix
cast the suffix to int4, so a legal `P9999999999` row made every auto-numbered `create_part` return
500 permanently (`7562a02`). Each code criterion now has an executable, red/green-proven guard:
`verify_plum_vendor_paths.py` (8/8), `verify_part_numbering.py` (7/7), `tests/plum/test_part_number.py`
(4 pure), `ImportExport.test.tsx`. Live pytest harness still broken (D-P7-4, BACKLOG p1) but no
criterion depends on it. **v1.0 human-UAT remains 2/12** — owed at `/zj:milestone`.*

*Prior: 2026-07-06 — Phase 8 (SYERP inventory & purchasing): SYERP-10/11 backend built and
**live-verified** by three standalone Postgres scripts (`verify_inventory` 15/15, `verify_purchasing`
18/18, fresh-DB `verify_e2e_p8` 18/18); flow-level UI confirmation deferred to the v2.0 milestone UAT
(D-P7-5). Live pytest harness still broken (D-P7-4).*

*Prior: 2026-07-04 — Phase 7 (close v1.0 gaps): PLUM-01 defect resolved & proven live;
PLUM-04..10 code fixes landed & code-verified, flow-level UI confirmation deferred to v1.0
milestone UAT (D-P7-5). Prior "Complete" marks rested on tests that never ran (D-P7-4).*
