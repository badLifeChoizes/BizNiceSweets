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
| SYERP-12 (AC6/AC7) | AP aging (per-vendor + grand-total buckets current/31–60/61–90/90+ from `bill_date`, tied out to the derived 2110 control) + the three core financial statements (Trial Balance Σdebit==Σcredit, P&L revenue−expense over a range, Balance Sheet assets==liabilities+equity with a computed current-year net-income equity line); all derived read-only from posted GL activity filtered by `entry_date`, RBAC-gated | Phase 9c | 09c | `Bill.bill_date` model col (`f6b9635`); migration `0011_syerp_bill_date.py` NOT NULL + `created_at::date` backfill (`cab8531`); `bill_date` wired through `BillCreate`/`create_bill` + `post_bill` JE `entry_date=bill.bill_date` for subledger↔2110 tie-out (`729ec00`); report read schemas (`69e4724`); `ap_aging_report` + 2110 tie-out (`c24c9f6`); `trial_balance` (`7aecf7c`); `profit_loss` (`1d38ddb`); `balance_sheet` w/ computed 3130 net income (`6f79047`); 4 read-only report endpoints + `syerp:read` RBAC (`a9cae54`). **Live-DB: `verify_reports.py` 17/17 PASS** (aging buckets, **tie-out crux `grand_total==control_balance` Decimal-exact** incl. partial-payment & draft-exclusion, TB nets zero + parents absent, P&L in/out-of-period net income, BS balances w/ computed net-income line); **`verify_reports_api.py` PASS** (200/401/403 across all 4 endpoints + 422 missing-bound, read-only → no mutation audit). Regression: `verify_ap`/`gl`/`purchasing`/`inventory`/`e2e_p8` all exit 0 unchanged. UI: AP Aging screen (`c6b47d3`), Financial Reports tabbed page (`8994f5c`), routes+nav+bill-date field (`48c8453`). FE: `ApAging.test.tsx` (4), `FinancialReports.test.tsx` (3); full suite 79/79. | AC6/AC7 backend + UI built & live-proven by verify scripts; **`/zj:verify 09c` pending**; UI flow UAT pending (v2.0 milestone) |

---

*Last updated: 2026-07-12 — `/zj:build 09c` (Phase 9c AP aging + financial statements) **build complete**
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
