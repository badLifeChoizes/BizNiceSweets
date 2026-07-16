# Milestone Audit — v2.0 "Operations"
Date: 2026-07-16 | Auditor: ZJ milestone-close verifier
Scope: goal-backward, integration-focused audit of the four DoD clauses against CURRENT code + live stack (`compose_db_1` / `compose_api_1`, alembic head 0012).

## Verdict: GAPS FOUND — 1 minor (non-blocking)

All four definition-of-done clauses are genuinely delivered end-to-end and wired backend↔frontend↔DB. Trial balance nets zero at the whole-DB level, control accounts tie to their subledgers within a clean scope, and the MOUSSE cross-module seam clears WIP Decimal-exactly with the 5190 residual routing (5cffeeb) confirmed empirically. No v1.0-class contract-drift defect (UI keying off a field the API never sends) was found — every frontend interface checked matches its backend schema, and every route is mounted and in-nav. One minor UX gap in the Profit & Loss report (below) does not block the milestone.

## DoD clauses

| Clause | Verdict | Evidence checked |
|--------|---------|------------------|
| **Track inventory** | PASS | SYERP-10. Routes `/syerp/inventory/{items,items/:id,locations}` mounted (`App.tsx:56-58`) + in SyerpNav (`SyerpNav.tsx:18-19`). Derived on-hand-by-location contract aligned: FE `OnHandByLocation{location_id,location_name,quantity}` (`InventoryItemDetail.tsx:54`) ↔ BE `OnHandByLocation` joins `StockLocation.name` (`service/inventory.py:104,122`; `schemas.py:286-296`). Whole-DB: 0 negative on-hand rows. `verify_inventory` 14/14, `verify_e2e_p8` 18/18 (fresh-DB). |
| **Raise purchase orders** | PASS | SYERP-11. Routes `/syerp/purchasing/orders{,/new,/:id}` mounted (`App.tsx:59-62`) + in-nav. Receive→inventory→GR/IR seam real: `receive_line` calls `post_receipt` then `post_journal_entry` Dr 1130 / Cr 2150 at qty×unit_cost, source-linked, atomic (`service/purchasing.py:582-695`). Over-receipt guard + status roll-up present. `verify_purchasing` 18/18. |
| **Keep real books (GL+AP+statements)** | PASS | SYERP-12, all 9 ACs. Whole-DB trial balance = 0.000000; only non-zero accounts a clean 1130/2150 GR/IR pair (+1400/−1400) — internally consistent, no anomalous untied account. Reports contract aligned exactly incl. param aliases `from`/`to` (`router.py:1318-1319` ↔ `FinancialReports.tsx:128`) and line fields `account_id/code/name/amount` (`schemas.py:1009-1048`). Re-ran empirically: `verify_reports` 17/17 (2110 subledger↔control tie, Balance Sheet identity, out-of-period exclusion), `verify_ap` 24/24 (GR/IR clears, double-bill + overpayment races row-locked). |
| **Execute WO consuming PLUM BOM + inventory** | PASS | MOUSSE-01 materials-only slice. Full trace clean: cross-module imports (`_COST_QUANTUM`, `_adjustment_violates_floor`, `_gl_account_id_by_code`, `post_journal_entry`, `post_receipt`, `get_released_revision`) all resolve from `syerp/service/__init__.py` + `plum.service`. Module registered (`main.py:81`), permissions seeded (`auth/seed.py:38-39`), enabled in DB, nav gated enabled∩`mousse:read` (`AppShell.tsx:38-43`). FE contract mirrors schemas incl. derived `on_hand`/`issued_so_far` (`hooks.ts:41-53`); FSM buttons mirror server (`WorkOrderDetail.tsx:187-191`). Whole-DB 1140 WIP = 0. Re-ran `verify_mousse`: 1140 clears to pre-WO snapshot Decimal-exact, 1130 debited by exact FG receipt value (3×33.333333), sub-quantum residual parked in 5190 — never stranded (fix 5cffeeb confirmed real). |

## Cross-cutting "real books" invariant
- Whole-DB trial balance nets **0.000000** (every JE balances by construction).
- 1140 Work-in-Process clears to **0** across the whole DB — no WO stranded WIP.
- 1130↔inventory-subledger and 2110↔AP-subledger ties: NOT checkable on this shared dirty dev DB (Phase-8 inventory-only scripts post receipts with no JE; `verify_gl` posts JEs with no stock), so the raw whole-DB 1130 (1400) ≠ Σ on-hand·avg (375) is a **dev-DB artifact, not a defect**. The ties hold within clean scope and are pinned by `verify_mousse` (1130 tie), `verify_reports` (2110 tie), `verify_e2e_p8` (fresh-DB) — all re-run/confirmed PASS.

## SRD-truth check — all statuses honest
- **SYERP-12 "verified (all 9 ACs)"** — confirmed empirically (verify_reports/verify_ap re-run PASS; trial balance zero; contracts aligned). Truthful.
- **SYERP-10 / SYERP-11 "implemented (backend verified; UI flow UAT pending)"** — routes+nav+contracts confirmed wired; honest that human UAT is pending.
- **MOUSSE-01 "partially verified (materials-only slice)"** — deferrals (routing/labor/shop-floor, D-P10-1) correctly excluded from the statement; delivered slice verified. Truthful.
- No requirement marked implemented/verified that the current code fails to deliver.

## New gaps (not in the approved-deferral list)

### G1 — minor — Profit & Loss report errors on first tab open (empty `from` date)
- **Where:** `frontend/src/routes/syerp/FinancialReports.tsx:333` (`useState('')` for `from`) + `ProfitLossBody` query has no `enabled` guard (`:252-256`); backend `date_from: date = Query(alias="from")` is required (`router.py:1318`).
- **Failure scenario:** User opens Financial Reports → clicks the "Profit & Loss" tab. `from` is still `''`, so the query fires `GET /reports/profit-loss?from=&to=<today>` → FastAPI 422 (cannot parse empty date) → the tab renders "Failed to load the profit and loss report" instead of an empty/prompt state. The report works correctly once a From date is entered; Trial Balance and Balance Sheet default to today and are unaffected.
- **Suggested fix:** default `from` to a sensible period start (e.g. year-start), or gate the query with `enabled: !!from` and show a "pick a start date" placeholder. Add an assertion to `FinancialReports.test.tsx` for the no-from-date render path.
- **Severity rationale:** cosmetic first-render error state, not a data-integrity or wiring defect; the P&L clause is fully deliverable. Does not block v2.0.

## Regression protection (given accepted no-CI / broken pytest-harness state, BACKLOG p1)
| Clause | Pinned by |
|--------|-----------|
| Inventory | `verify_inventory.py`, `verify_e2e_p8.py`, FE `InventoryItemDetail.test.tsx` |
| Purchase orders | `verify_purchasing.py`, `verify_e2e_p8.py`, FE `PurchaseOrder*.test.tsx`, `ReceiveLineDialog.test.tsx` |
| Real books | `verify_gl(_api)`, `verify_ap(_api)`, `verify_reports(_api)`, FE `FinancialReports/ApAging/BillCreateDialog.test.tsx` |
| WO / BOM+inventory | `verify_mousse.py` (34 assertions), `verify_mousse_api.py`, FE `WorkOrderDetail/IssueComponentsDialog/WorkOrderCreateDialog.test.tsx` |
All 13 verify_* scripts exit 0; the milestone's regression coverage is adequate within the accepted manual-run frame. (No new automated-coverage gap beyond G1's suggested test.)
