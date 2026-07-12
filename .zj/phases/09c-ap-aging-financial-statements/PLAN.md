# Plan: Phase 09c — AP aging + financial statements
Goal: A user can read an AP aging report (per-vendor + grand total, aged from bill_date, tying to the 2110 control account) and the three core financial statements (Trial Balance, P&L, Balance Sheet) — all derived read-only from posted GL activity, RBAC-gated, proven over live Postgres and live HTTP.
Status: draft
Branch: `feature-syerp-financial-reports`, cut fresh off the verified 09b tip (tag `zj/good-09b-ap-bills-match-payments`) — per-sub-phase branch precedent D-P9b-8/D-P9a-2, and keeps the branch name honest (the current `feature-syerp-ap-bills` describes 09b's work). First build action: cut the branch (D-P9c-3).

## Success criteria
<!-- From the phase brief; each implements a SYERP-12 acceptance criterion, noted inline. -->
- **SC1** (SYERP-12 AC6): An AP aging report buckets each vendor's open bill balances by age (current[0–30] / 31–60 / 61–90 / 90+) from **bill_date**, reported **per vendor and as a grand total**, as of a caller-suppliable "as-of" date (default today). Per-bill open balance = Σ billed − Σ paid, each side coalesced (D-P8-4).
- **SC2** (SYERP-12 AC6, the crux): The aging grand total **equals `derive_account_balance(2110)` as of the same date** — subledger ↔ control-account agreement — asserted exact-Decimal in `verify_reports.py` (snapshot 2110, assert equality with Σ open balances).
- **SC3** (SYERP-12 AC7): A Trial Balance lists each posting account's derived debit/credit balance as of a date; **Σ debits == Σ credits** (nets to zero), asserted exact-Decimal.
- **SC4** (SYERP-12 AC7): A Profit & Loss report sums REVENUE and EXPENSE activity over `[date_from, date_to]` and reports **net income = revenue − expense**.
- **SC5** (SYERP-12 AC7): A Balance Sheet as of a date reports assets, liabilities, equity where **assets == liabilities + equity** exact-Decimal, equity including a **computed current-year net income** line (Σ revenue − Σ expense to date) so it balances with no closing entries posted.
- **SC6** (SYERP-12 AC8/AC9): Every new report endpoint is gated by `syerp:read` — 401 unauthenticated, 403 without permission, 200 with — proven at the HTTP layer (`verify_reports_api.py`). Read-only reports emit no mutation-audit rows; RBAC status codes are the SC6 gate.

## Context
Key files (all paths absolute from repo root `/home/zack/Projects/BizNiceSweets/`):
- `backend/app/modules/syerp/service.py` (~133 KB) — **REUSE `derive_account_balance(db, account_id)` (service.py:2322)**: `coalesce(Σdebit,0) − coalesce(Σcredit,0)` over all `JournalLine`, no date filter. **All statement/aging balances must instead filter by `JournalEntry.entry_date <= as_of` (or within `[from,to]`) using the join pattern in `get_account_register` (service.py:2345–2405): `select(...).select_from(JournalLine).join(JournalEntry, JournalLine.entry_id == JournalEntry.id).where(JournalEntry.entry_date <= as_of)` — coalesce each side INDEPENDENTLY (09a NULL-propagation bug).** Bill open-balance derivation already exists: `_bill_paid_amount` (service.py:2908), `_bill_to_read` (service.py:2925), `list_bills` (service.py:2967), `list_payments` (service.py:3324). Account lookup `_gl_account_id_by_code` (service.py:1821) resolves 2110/etc by code. `post_bill` posts its JE at `entry_date=date.today()` (service.py:3113) — **Task 3 changes this to `bill.bill_date`** so the subledger (aged by bill_date) and the 2110 control account (aged by entry_date) share a date basis (SC2). Models declare NO ORM relationships (async MissingGreenlet avoidance) — child-load via ordered SELECTs.
- `backend/app/modules/syerp/models.py` — `GLAccount` (:120: id, `code` String(10), name, `account_type` ASSET|LIABILITY|EQUITY|REVENUE|EXPENSE, `parent_id` self-FK, active); `JournalEntry` (:407: `entry_date`, `created_at`, `memo`); `JournalLine` (:461: account_id, debit, credit, line_no); `Bill` (:504: status draft|posted|paid, `posted_at`, **no bill_date yet** — Task 1 adds it); `BillLine` (:561); `Payment` (:618: `payment_date`); `PaymentAllocation` (:661). Money `Numeric(18,6)` Decimal, never float (D-11).
- `backend/app/modules/syerp/coa_seed.py` — hierarchical CoA (`_STANDARD_COA` :40). Rollup parents (1000/1100/2000/2100/3000/…) carry NO postings; all postings hit leaves. Relevant leaves: **2110 Accounts Payable (LIABILITY, :58)**, 2150 GR/IR (:63), 1130 Inventory (:48), 1110 Cash (:44) / 1111 Bank (:46), **3120 Retained Earnings (:71) & 3130 Current Year Net Income (:72) — both EQUITY, currently unposted/empty**, REVENUE 4xxx (:75–80), EXPENSE 5xxx (:83–97). Statements sum over accounts and present type-grouped subtotals — do NOT double-count parents (parents have zero direct lines, so summing leaf-level derived balances is inherently safe; a per-account trial balance naturally excludes them).
- `backend/app/modules/syerp/router.py` — endpoint style `@router.get("/gl/accounts", ...)` + `Depends(require_permission("syerp:read"))` (router.py:935); journal-post endpoint at :959 is the write+audit template (`from app.modules.auth.service import write_audit`, self-commits, called AFTER the service commit). New report endpoints are READ-only → `syerp:read`, no mutation audit.
- `backend/app/modules/syerp/schemas.py` — `BillCreate` (:784), `BillRead` (:822), `POLineRead`/`PORead`, `AccountRegisterRead`/`AccountRegisterRow` (register read shape). Add report read schemas here.
- `backend/alembic/versions/` — head is `0010_syerp_ap_bills.py` (`revision="0010"`). Add **`0011_syerp_bill_date.py`** (`revision="0011"`, `down_revision="0010"`). Models use Python-side timestamp defaults (no `server_default`); but the `bill_date` NOT-NULL add on an existing table REQUIRES a server-side backfill (D-P9c-1). Pre-existing repo `alembic check` drift is accepted (09a/09b Deviations) — the criterion is "no NEW spurious ops," not clean check.
- `backend/scripts/` — `verify_ap.py`, `verify_gl.py`, `verify_purchasing.py`, `verify_inventory.py`, `verify_e2e_p8.py` (service-level, own async engine from `POSTGRES_*`, no conftest, PASS/FAIL prints, non-zero exit, self-cleanup); `verify_ap_api.py`/`verify_gl_api.py` (HTTP-level via httpx, RBAC + audit). Model the two NEW scripts on these. DB-backed pytest is BROKEN (D-P7-4) → verify scripts are the backend regression gate.
- Frontend: `frontend/src/routes/syerp/` — `Bills.tsx`, `BillDetail.tsx`, `GLAccounts.tsx`, `AccountRegister.tsx`, `JournalEntries.tsx`; nav `components/SyerpNav.tsx` (`TABS` array :15); routes `frontend/src/App.tsx`; dialogs `components/BillCreateDialog.tsx`, `PayBillDialog.tsx`; single axios client `src/api/client.ts`; TanStack Query; sonner toasts; shadcn/ui in `components/ui/`; colocated `*.test.tsx` (Vitest).

Prior decisions honored: D-11 (Decimal money), D-P8-4 (derived sums, coalesce each side), D-P7-4 (broken DB-pytest → verify scripts are backend truth), D-P9-1 (subledger auto-post GL over document-only aging), and the 09a/09b learnings (statement balances filter posted activity by `entry_date`; RBAC lives in the router → HTTP verify). Cite `D-P9c-1/2` in new code.

## Decisions
<!-- Resolved by the owner at planning; append to DECISIONS.md as D-P9c-1 / D-P9c-2. -->
1. **D-P9c-1 — Add a real `bill_date`.** Add `Bill.bill_date` (SQLAlchemy `Date`, NOT NULL) via **Alembic migration 0011**. `create_bill` accepts it on `BillCreate` (defaulting to `date.today()` when omitted — backward-compatible with existing 09b callers/tests), and the 09b `BillCreateDialog.tsx` create flow gains an optional bill-date field. AP aging buckets from `bill_date`. Migration 0011 adds the column nullable, backfills existing rows with `created_at::date` (server-side), then sets NOT NULL. **The bill JE's `entry_date` is set from `bill.bill_date`** (not `date.today()`) so the subledger and the 2110 control account age on the same date basis (SC2 tie-out).
2. **D-P9c-2 — Reports UI = one tabbed page + AP Aging nav item.** A single **Financial Reports** SYERP nav item hosts Trial Balance / P&L / Balance Sheet (tabs sharing date controls); **AP Aging** is its own nav item near Bills.
3. **D-P9c-3 — Fresh branch `feature-syerp-financial-reports`** cut off the verified 09b tip (tag `zj/good-09b-ap-bills-match-payments`), mirroring the per-sub-phase branching of D-P9a-2 / D-P9b-8 and keeping the branch name descriptive of the reports work. All of Phase 9 remains unmerged and stacks; the tag marks the 09b rollback point.

## Decisions needed
None — all three choices above are settled.

## Tasks

### [ ] 1. Add `Bill.bill_date` column to the model (D-P9c-1, AC6)
- **Files:** `backend/app/modules/syerp/models.py`
- **Do:** Add `bill_date: Mapped[date] = mapped_column(Date, nullable=False)` to `Bill` (models.py:504), placed with the identity fields (after `vendor_invoice_ref`, before `status`). `date`/`Date` are already imported (used by `Payment.payment_date`, models.py:639). Update the `Bill` docstring to note bill_date is the invoice date that AP aging buckets from (D-P9c-1). Do NOT add a Python default here — the value is always supplied by `create_bill` (Task 3); the migration handles existing rows (Task 2).
- **Done when:** `from app.modules.syerp.models import Bill; 'bill_date' in Bill.__table__.columns` is True from `backend/`.
- **Verify:** `cd backend && python -c "import app.core.models; from app.modules.syerp.models import Bill; print('bill_date' in Bill.__table__.columns)"`
- **Parallel-ok:** no (blocks 2, 3)

### [ ] 2. Add migration 0011_syerp_bill_date with NOT-NULL backfill (D-P9c-1, AC6)
- **Files:** `backend/alembic/versions/0011_syerp_bill_date.py` (new)
- **Do:** Hand-write mirroring `0010_syerp_ap_bills.py` (`revision="0011"`, `down_revision="0010"`). `upgrade()`: three steps to satisfy NOT NULL on a populated table — (1) `op.add_column("syerp_bill", sa.Column("bill_date", sa.Date(), nullable=True))`; (2) backfill `op.execute("UPDATE syerp_bill SET bill_date = created_at::date WHERE bill_date IS NULL")` (server-side; `created_at::date` is the D-P9c-1 backfill default); (3) `op.alter_column("syerp_bill", "bill_date", nullable=False)`. `downgrade()`: `op.drop_column("syerp_bill", "bill_date")`.
- **Done when:** against the dev DB, `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` all succeed; every existing `syerp_bill` row has a non-null `bill_date`; `alembic check` shows no NEW spurious ops beyond the accepted pre-existing drift.
- **Verify:** in the api container: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` then `python -c "import asyncio,os; ..."` (or a `verify_reports.py` pre-check) confirms `SELECT count(*) FROM syerp_bill WHERE bill_date IS NULL` == 0.
- **Parallel-ok:** no (depends on 1; blocks the live verify scripts)

### [ ] 3. Wire bill_date through BillCreate + create_bill + post_bill JE (D-P9c-1, AC4/AC6)
- **Files:** `backend/app/modules/syerp/schemas.py`, `backend/app/modules/syerp/service.py`
- **Do:**
  - `schemas.py`: add `bill_date: Optional[date] = None` to `BillCreate` (schemas.py:784) with a docstring note that it defaults to today server-side; add `bill_date: date` to `BillRead` (schemas.py:822) so callers can read it. (`date` import: confirm/add `from datetime import date`.)
  - `service.py`: change `create_bill` (service.py:2676) signature to accept `bill_date: date | None = None` (keyword) and persist `Bill(bill_date=bill_date or date.today(), ...)` — the `or date.today()` keeps existing 09b callers/tests working (D-P9c-1). Include `bill_date` in `_bill_to_read` (service.py:2925) output.
  - `service.py`: in `post_bill` (service.py:3096–3123) change the JE `entry_date=date.today()` (service.py:3113) to `entry_date=bill.bill_date` — so 2110's `entry_date`-aged balance matches the subledger's `bill_date` aging (SC2 crux). Add a one-line comment citing D-P9c-1 and the tie-out rationale.
- **Done when:** creating a bill with an explicit `bill_date` persists it; omitting it defaults to today; posting the bill produces a JE whose `entry_date == bill.bill_date`; `BillRead.bill_date` is returned. (DB behavior proven by Task 10.)
- **Verify:** `cd backend && python -c "from app.modules.syerp.schemas import BillCreate, BillRead; from app.modules.syerp.service import create_bill, post_bill"` imports clean; full behavior via `verify_reports.py`.
- **Parallel-ok:** no (depends on 1)

### [ ] 4. Add report Pydantic schemas (AC6/AC7)
- **Files:** `backend/app/modules/syerp/schemas.py`
- **Do:** Add read schemas (money `Decimal`, D-11), mirroring `AccountRegisterRead` construction style:
  - **AP aging:** `ApAgingBucketRow` (`vendor_id`, `vendor_name`, `current`, `d31_60`, `d61_90`, `d90_plus`, `total`); `ApAgingReport` (`as_of: date`, `vendors: list[ApAgingBucketRow]`, `grand_total` with the same five sums, `control_balance: Decimal` (the 2110 derived balance for the tie-out), `in_balance: bool`).
  - **Trial Balance:** `TrialBalanceRow` (`account_id`, `code`, `name`, `account_type`, `debit`, `credit`); `TrialBalanceReport` (`as_of: date`, `rows`, `total_debit`, `total_credit`, `in_balance: bool`).
  - **P&L:** `ProfitLossLine` (`account_id`, `code`, `name`, `amount`); `ProfitLossReport` (`date_from`, `date_to`, `revenue: list[ProfitLossLine]`, `total_revenue`, `expense: list[ProfitLossLine]`, `total_expense`, `net_income`).
  - **Balance Sheet:** `BalanceSheetLine` (`account_id`, `code`, `name`, `amount`); `BalanceSheetReport` (`as_of: date`, `assets: list[...]`, `total_assets`, `liabilities: list[...]`, `total_liabilities`, `equity: list[...]` (includes the computed net-income line), `total_equity`, `in_balance: bool`).
- **Done when:** all schemas import; construct cleanly with Decimal fields.
- **Verify:** `cd backend && python -c "from app.modules.syerp.schemas import ApAgingReport, TrialBalanceReport, ProfitLossReport, BalanceSheetReport"`
- **Parallel-ok:** yes (align field names with Tasks 5–8)

### [ ] 5. Service: AP aging report + 2110 tie-out (SC1, SC2, AC6)
- **Files:** `backend/app/modules/syerp/service.py`
- **Do:** Add `ap_aging_report(db, as_of: date | None = None) -> ApAgingReport` (default `as_of = date.today()`). For every bill with `status in ('posted','paid')` and `bill_date <= as_of` (DRAFT bills are NOT posted to 2110 and MUST be excluded — this is the divergence guard): compute per-bill open balance = `line total` − `coalesce(Σ PaymentAllocation.amount for payments with payment_date <= as_of, 0)` (each side coalesced independently, D-P8-4; join `PaymentAllocation`→`Payment` to filter by `payment_date`). Bucket by `age = (as_of − bill_date).days`: current 0–30, 31–60, 61–90, 90+ (skip bills whose open balance is ≤ 0). Group per `vendor_id` (join `Partner` for `vendor_name`), roll up a grand total. Then compute `control_balance` = a date-filtered 2110 derived balance — `coalesce(Σdebit,0) − coalesce(Σcredit,0)` over `JournalLine` joined to `JournalEntry` where `entry_date <= as_of` and `account_id == _gl_account_id_by_code(db,'2110')` (NOT the unfiltered `derive_account_balance`; the join pattern is `get_account_register`, service.py:2374). 2110 is credit-normal so its raw Σdr−Σcr is negative; normalize (negate) so `control_balance` is the positive outstanding payable. Set `in_balance = (grand_total.total == control_balance)`. Cite D-P9c-1, D-P8-4.
- **Done when:** function imports; a report over known bills/payments returns per-vendor buckets summing to a grand total, and `control_balance` equals that grand total for posted-and-unpaid bills. (Proven by Task 10.)
- **Verify:** `cd backend && python -c "from app.modules.syerp.service import ap_aging_report"`; behavior + tie-out via `verify_reports.py`.
- **Parallel-ok:** no (depends on 3)

### [ ] 6. Service: Trial Balance (SC3, AC7)
- **Files:** `backend/app/modules/syerp/service.py`
- **Do:** Add `trial_balance(db, as_of: date | None = None) -> TrialBalanceReport`. In ONE grouped aggregate, sum `debit` and `credit` per `account_id` over `JournalLine` joined to `JournalEntry` where `entry_date <= as_of` (the `get_account_register` join, service.py:2374), coalescing each side. Join `GLAccount` for `code`/`name`/`account_type`; include only accounts with a posting (a `HAVING` or in-Python filter). For each account emit a `TrialBalanceRow` with net debit/credit: if `Σdr − Σcr >= 0` put it in `debit` (credit 0), else in `credit` as the positive magnitude (debit 0). `total_debit`/`total_credit` are the column sums; `in_balance = (total_debit == total_credit)`. Order rows by `code`. Rollup parents have no direct lines so they never appear (no double-count). All exact Decimal.
- **Done when:** function imports; over any posted set, `total_debit == total_credit` exactly.
- **Verify:** `cd backend && python -c "from app.modules.syerp.service import trial_balance"`; nets-to-zero via `verify_reports.py`.
- **Parallel-ok:** no (depends on 3; independent of 5 — but same file, sequence to avoid edit conflicts)

### [ ] 7. Service: Profit & Loss (SC4, AC7)
- **Files:** `backend/app/modules/syerp/service.py`
- **Do:** Add `profit_loss(db, date_from: date, date_to: date) -> ProfitLossReport`. Group-sum `Σdebit`/`Σcredit` per posting account over `JournalLine`⋈`JournalEntry` where `date_from <= entry_date <= date_to` (inclusive both bounds), joined to `GLAccount`, filtered to `account_type in ('REVENUE','EXPENSE')`. REVENUE is credit-normal → its period activity is `Σcr − Σdr` (present as positive revenue); EXPENSE is debit-normal → `Σdr − Σcr` (positive expense). Emit `ProfitLossLine` per account (ordered by code), `total_revenue`, `total_expense`, and `net_income = total_revenue − total_expense`. Exact Decimal.
- **Done when:** function imports; `net_income == total_revenue − total_expense`; a period with no activity yields zeros, not NULL.
- **Verify:** `cd backend && python -c "from app.modules.syerp.service import profit_loss"`; net-income math via `verify_reports.py`.
- **Parallel-ok:** no (depends on 3; sequence after 6 — same file)

### [ ] 8. Service: Balance Sheet with computed net income (SC5, AC7)
- **Files:** `backend/app/modules/syerp/service.py`
- **Do:** Add `balance_sheet(db, as_of: date | None = None) -> BalanceSheetReport`. Group-sum derived balances per posting account (as-of `entry_date <= as_of`, the same join). Partition by `account_type`: ASSET (debit-normal → present `Σdr − Σcr`), LIABILITY & EQUITY (credit-normal → present `Σcr − Σdr`). `total_assets` = Σ asset lines; `total_liabilities` = Σ liability lines; posted `total_equity` = Σ equity lines. Then ADD a **computed** equity line — `{code:'3130', name:'Current Year Net Income', amount: (Σ REVENUE − Σ EXPENSE for entry_date <= as_of)}` — because no closing entries are posted so ledger 3130 is empty (reuse the P&L period logic with `date_from=None`/beginning-of-time, or compute inline). Add that amount into `total_equity`. Set `in_balance = (total_assets == total_liabilities + total_equity)`. Order each section by code. Exact Decimal — be careful with sign normalization so the equation uses consistent signs (assets positive; liabilities+equity positive).
- **Done when:** function imports; over any posted set `total_assets == total_liabilities + total_equity` exactly, with the computed net-income line making it balance despite empty ledger 3130.
- **Verify:** `cd backend && python -c "from app.modules.syerp.service import balance_sheet"`; balances via `verify_reports.py`.
- **Parallel-ok:** no (depends on 3, 7 (shares P&L period logic); sequence after 7 — same file)

### [ ] 9. Router: 4 report endpoints with RBAC (SC1–SC6, AC6/AC7/AC8/AC9)
- **Files:** `backend/app/modules/syerp/router.py`
- **Do:** Add a "SYERP reports (Phase 9c)" section mirroring the read-endpoint style (router.py:935). All `Depends(require_permission("syerp:read"))`, read-only (NO mutation, NO `write_audit`):
  - `GET /ap/aging?as_of=<date>` (`as_of` optional `Query(default=None)`) → `ApAgingReport`, calls `ap_aging_report`.
  - `GET /reports/trial-balance?as_of=<date>` → `TrialBalanceReport`, calls `trial_balance`.
  - `GET /reports/profit-loss?from=<date>&to=<date>` (`Query(alias="from"/"to")`, mirroring the journal-list endpoint router.py:999) → `ProfitLossReport`, calls `profit_loss` (require both bounds; 422 if missing).
  - `GET /reports/balance-sheet?as_of=<date>` → `BalanceSheetReport`, calls `balance_sheet`.
- **Done when:** OpenAPI shows the 4 routes; each returns 200 with a `syerp:read` token, 401 unauthenticated, 403 with a no-permission token; there are no write/audit side effects.
- **Verify:** curl the dev api (or `verify_reports_api.py`): each GET → 200 with read token, 401 without, 403 with a wrong-perm token.
- **Parallel-ok:** no (depends on 5, 6, 7, 8, 4)

### [ ] 10. Write verify_reports.py live-Postgres verification (SC1–SC5 + tie-out crux)
- **Files:** `backend/scripts/verify_reports.py` (new)
- **Do:** Model on `backend/scripts/verify_ap.py` (own async engine from `POSTGRES_*`, no conftest, PASS/FAIL prints, non-zero exit, self-cleanup in `finally`, in-container run header). Reuse the AP setup helpers to stand up: a vendor, item, location, PO → approve → receive, then bills/payments. Scenarios:
  - (a) **AP aging buckets (SC1):** create bills with distinct `bill_date`s straddling the 30/60/90 boundaries relative to a fixed `as_of`; assert each lands in the right bucket and the per-vendor row sums to the grand total.
  - (b) **Tie-out (SC2, the crux):** snapshot the date-filtered 2110 derived balance as of `as_of`; assert `ap_aging_report(as_of).grand_total.total == control_balance` exactly. Include a partially-paid bill (payment reduces both the open balance AND the 2110 Dr leg) and confirm the equality still holds. Include a DRAFT bill (excluded from both) to prove no divergence.
  - (c) **Trial Balance (SC3):** assert `total_debit == total_credit` exactly over the built ledger; assert rollup-parent accounts do not appear.
  - (d) **P&L (SC4):** post revenue+expense activity in-period and out-of-period; assert `net_income == total_revenue − total_expense` and that out-of-period entries are excluded.
  - (e) **Balance Sheet (SC5):** assert `total_assets == total_liabilities + total_equity` exactly, and that the computed net-income equity line equals Σrevenue − Σexpense to date (ledger 3130 stays empty).
- **Done when:** `python scripts/verify_reports.py` prints all PASS and exits 0 against the live dev DB; re-runnable (self-cleans).
- **Verify:** `podman-compose -f compose/compose.yml -f compose/compose.dev.yml exec -e PYTHONPATH=/app api python scripts/verify_reports.py` → exit 0.
- **Parallel-ok:** no (depends on 2, 5, 6, 7, 8)

### [ ] 11. Write verify_reports_api.py HTTP-level RBAC verification (SC6, AC8/AC9)
- **Files:** `backend/scripts/verify_reports_api.py` (new)
- **Do:** Model on `backend/scripts/verify_ap_api.py` — httpx against the running api, a `syerp:read` token and a no-`syerp:read` token. For each of the 4 endpoints (`/ap/aging`, `/reports/trial-balance`, `/reports/profit-loss?from=..&to=..`, `/reports/balance-sheet`): assert 200 with the read token, 401 unauthenticated, 403 with the wrong-perm token. Optionally assert a 422 on `/reports/profit-loss` with a missing bound. (Read-only reports emit no mutation-audit rows, so no audit-log assertions — SC6 is RBAC status codes; note this explicitly in the script header.) Include the in-container run header.
- **Done when:** `python scripts/verify_reports_api.py` prints all PASS and exits 0; every RBAC assertion holds.
- **Verify:** `podman-compose -f compose/compose.yml -f compose/compose.dev.yml exec -e PYTHONPATH=/app api python scripts/verify_reports_api.py` → exit 0.
- **Parallel-ok:** no (depends on 9)

### [ ] 12. Regression: re-run 9a/9b + Phase-8 verify scripts unchanged (SC-gate; bill_date migration risk)
- **Files:** none (validation only) — exercises `backend/scripts/verify_ap.py`, `verify_gl.py`, `verify_purchasing.py`, `verify_inventory.py`, `verify_e2e_p8.py`
- **Do:** After Tasks 2–3 (the only write-path changes — the `bill_date` column + the `post_bill` JE `entry_date` switch), run all five. `verify_ap.py` is the primary risk: it calls `create_bill` without `bill_date` (must default to today) and asserts the bill JE / GR/IR-to-zero (must still hold with `entry_date=bill.bill_date==today`). If any fails, the bill_date change regressed a shared path — fix before proceeding.
- **Done when:** all five scripts exit 0 with unchanged PASS counts.
- **Verify:** in the api container: `python scripts/verify_ap.py && python scripts/verify_gl.py && python scripts/verify_purchasing.py && python scripts/verify_inventory.py && python scripts/verify_e2e_p8.py`
- **Parallel-ok:** no (depends on 3; run again after 5–8 if service edits touched shared code)

### [ ] 13. Frontend: AP Aging screen + nav item (SC1, AC6, D-P9c-2)
- **Files:** `frontend/src/routes/syerp/ApAging.tsx` (new), `frontend/src/routes/syerp/ApAging.test.tsx` (new)
- **Do:** List screen (TanStack Query GET `/api/v1/syerp/ap/aging?as_of=`) reusing the `Bills.tsx` / `JournalEntries.tsx` layout (`p-8 space-y-6`, `SyerpNav`). An "as of" date input (default today) drives the query. Table: one row per vendor with columns Current / 31–60 / 61–90 / 90+ / Total, plus a grand-total footer row. Show the `in_balance` / `control_balance` tie-out as a small badge or note (green when equal). Vitest: renders buckets from mocked data, changing the as-of date refetches, grand-total row present.
- **Done when:** `npm run test -- ApAging` passes; the screen renders per-vendor buckets + grand total.
- **Verify:** `cd frontend && npm run test -- ApAging && npx tsc -b`
- **Parallel-ok:** yes (after 9 defines the contract; UI mockable)

### [ ] 14. Frontend: Financial Reports tabbed page (SC3, SC4, SC5, AC7, D-P9c-2)
- **Files:** `frontend/src/routes/syerp/FinancialReports.tsx` (new), `frontend/src/routes/syerp/FinancialReports.test.tsx` (new)
- **Do:** One screen with shared date controls hosting three tabs/sub-sections (shadcn/ui tabs or simple button toggle, matching existing patterns): **Trial Balance** (as-of date; GET `/reports/trial-balance`; account rows + debit/credit columns + a totals footer showing Σdebit==Σcredit), **Profit & Loss** (from/to date range; GET `/reports/profit-loss`; revenue lines, expense lines, net income), **Balance Sheet** (as-of date; GET `/reports/balance-sheet`; assets / liabilities / equity sections incl. the computed net-income line + the balanced total). TanStack Query per tab. Vitest: each tab renders its mocked report; TB shows balanced totals; BS shows assets == liabilities+equity.
- **Done when:** `npm run test -- FinancialReports` passes; all three reports render with correct totals from mocked data.
- **Verify:** `cd frontend && npm run test -- FinancialReports && npx tsc -b`
- **Parallel-ok:** yes (after 9 defines the contract; UI mockable)

### [ ] 15. Frontend: register routes + nav items + BillCreateDialog bill-date field (SC5 UI, D-P9c-1/2)
- **Files:** `frontend/src/App.tsx`, `frontend/src/routes/syerp/components/SyerpNav.tsx`, `frontend/src/routes/syerp/components/BillCreateDialog.tsx`, `frontend/src/routes/syerp/components/BillCreateDialog.test.tsx` (if present)
- **Do:**
  - `App.tsx`: import + add routes `/syerp/ap/aging` → `ApAging` and `/syerp/reports` → `FinancialReports` (beside the existing SYERP routes).
  - `SyerpNav.tsx`: add two `TABS` entries (SyerpNav.tsx:15) — `{ to: '/syerp/ap/aging', label: 'AP Aging' }` right after the `Bills` tab, and `{ to: '/syerp/reports', label: 'Financial Reports' }` after it (D-P9c-2).
  - `BillCreateDialog.tsx`: add an OPTIONAL bill-date input (date picker, defaults to today) to the create form and include `bill_date` in the POST `/ap/bills` body (D-P9c-1). Keep it optional — the server defaults to today when omitted.
- **Done when:** both nav tabs render and navigate; the bill-date field appears in the create dialog and posts through; `tsc -b` clean; the full frontend suite passes.
- **Verify:** `cd frontend && npx tsc -b && npm run test`
- **Parallel-ok:** no (depends on 13, 14)

## Risks
- **Aging-vs-2110 divergence (highest, the phase crux — SC2).** If aging includes DRAFT bills (not posted to 2110), or ages payments/bills on a different date basis than 2110's `entry_date`, the tie-out silently breaks — an AP mis-statement. Early warning: `verify_reports.py` (b) grand_total != control_balance. Mitigation: aging includes only `posted`/`paid` bills with `bill_date <= as_of`; payments filtered by `payment_date <= as_of`; **Task 3 sets the bill JE `entry_date = bill.bill_date`** so both subledger and control account age identically; the (b) assertion is the gate — do not weaken it to fit output (the exact defect class the broken DB-pytest, D-P7-4, would mask).
- **Balance-sheet sign-convention error (SC5).** Mixing debit-normal (assets) and credit-normal (liabilities/equity/revenue) signs makes `assets == liabilities + equity` fail or falsely pass. Early warning: `verify_reports.py` (e) imbalance, or a P&L net income with the wrong sign. Mitigation: normalize per `account_type` at presentation (assets positive `Σdr−Σcr`; liabilities/equity/revenue positive `Σcr−Σdr`); the computed net-income line is Σrevenue−Σexpense; assert exact-Decimal equality.
- **Migration backfill on existing bill rows (D-P9c-1).** Adding `bill_date` NOT NULL directly fails on populated tables; a bad backfill leaves NULLs and boot fails. Mitigation: Task 2's three-step add-nullable → `UPDATE ... created_at::date` → alter NOT NULL; Task 2 verify asserts zero NULLs; Task 12 re-runs `verify_ap.py` end-to-end.
- **`post_bill` entry_date change regresses 09b (SC-gate).** Switching the bill JE from `date.today()` to `bill.bill_date` could shift `verify_ap.py`'s date-sensitive assertions. Early warning: `verify_ap.py` fails after Task 3. Mitigation: default `bill_date` to today so existing callers are unchanged; Task 12 is a first-class gate.
- **Large `service.py` (~133 KB).** New report functions add ~200 lines to an already-flagged file (BACKLOG: split at Phase 10). Mitigation: keep the 4 report functions cohesive in one clearly-bannered "Phase 9c reports" section; do NOT split now (out of scope).
- **NULL-propagation on single-sided sums (recurring 09a bug).** A statement account posted on only one side yields NULL for the empty side; `Σdr − NULL` is NULL in SQL. Mitigation: coalesce each side independently in every report aggregate (the `derive_account_balance` pattern).

## Out of scope
- Concurrency / row-locking: this phase is read-only except the additive `bill_date` column, which guards no invariant — no new lock scenarios (called out per the phase brief; nothing to build here).
- Multi-period / comparative statements, prior-year columns, fiscal-period close, retained-earnings roll-forward posting (3130 stays a computed line, never a posted closing entry this phase).
- Cash-flow statement, statement of changes in equity, budget-vs-actual, drill-down from a statement line to the register.
- AR aging (SYERP-13, CRUMB milestone), tax/1099 reporting, multi-currency, statement export to Excel/PDF.
- Splitting `service.py` (BACKLOG, Phase 10).
- Offline/Service-Worker support for the new screens (standing cross-module concern).

## Noticed
<!-- Populated during build: unrelated issues found, not fixed mid-task. -->

## Deviations
<!-- Populated during build: where the plan proved wrong and what was done instead. -->
