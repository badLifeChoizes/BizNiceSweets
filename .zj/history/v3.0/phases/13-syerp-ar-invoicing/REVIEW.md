# Review: Phase 13 — SYERP-13 Accounts Receivable (`zj/good-12b-gelato-pick-pack-ship..HEAD`)
Date: 2026-07-19

## Findings

### 1. [major] Unvalidated invoice header `sales_order_id` FK turns the number-collision retry into unbounded recursion
- **Where:** `backend/app/modules/syerp/service/ar.py:337-359` (Invoice built with `sales_order_id=sales_order_id`; `except sqlalchemy.exc.IntegrityError` → `db.rollback()` → recursive `create_invoice(...)`).
- **Failure:** `InvoiceCreate.sales_order_id` is `Optional[str]` and is passed straight into `Invoice()` with **no existence check** — unlike `customer_id` (validated by SELECT) and each line's `sales_order_line_id` (404 if missing). `sales_order_id` is a real FK to `crumb_sales_order.id`. A `syerp:write` caller (the field is part of the documented request contract; the FE never sends it, so this is API-reachable only) POSTs an invoice with a non-existent `sales_order_id`. `await db.flush()` at line 347 raises `IntegrityError` on the FK — **not** an invoice-number collision. The broad `except IntegrityError` treats it as a collision, rolls back, and re-invokes `create_invoice` with the identical bogus `sales_order_id`. Every recursion re-locks the SO lines, re-validates, re-bumps `qty_invoiced`, re-flushes, and hits the same FK violation → deterministic unbounded recursion ending in `RecursionError` (HTTP 500) after ~1000 iterations, each doing several DB round-trips (a mild self-inflicted DoS). No clean 422; nothing persists, but the caller gets a 500 and the DB takes ~1000× the load.
- **Fix:** Validate `sales_order_id` up front when provided — `SELECT 1 FROM crumb_sales_order WHERE id = :sid`, raise 422 if absent (mirroring the customer gate) — before building the header. Additionally, narrow the retry so it only re-runs on the `invoice_number` unique violation (inspect the constraint name / `orig`) and bound it (retry-once, like `create_bill`) rather than recursing unboundedly on any `IntegrityError`.

## Questions
None.

## Verified clean (high-risk areas checked, no defect)
- **Aging control-tie sign:** `ar_aging_report` takes `control_balance = Decimal(control_raw)` with the 2110 negation removed (reports.py:377-395); 1120 debit-normal ties `grand_total == Σdr−Σcr`. Correct per the load-bearing risk.
- **JE direction/balance:** invoice post Dr 1120 / Cr 4110 (ar.py:590-593); receipt Dr cash / Cr 1120 (ar.py:803-806); both single balanced JE via `post_journal_entry(commit=False)` riding one caller `commit`. `entry_date = invoice_date` on post (aging crux). Money is `Decimal`/`Numeric(18,6)` throughout — no float; FE sends amounts as raw strings.
- **Concurrency:** `create_invoice` locks target SO-line ids FOR UPDATE in sorted order *before* the uninvoiced read (ar.py:266-272); `record_receipt` locks target invoice ids FOR UPDATE in sorted order *before* the overpayment read (ar.py:732-733). Over-collect guard accumulates `claimed_by_id` per invoice against live `open_balance` (draft+posted counted via `qty_invoiced` bump at draft create). `expire_on_commit=False` — post-commit attribute reads are safe.
- **FSM/guards:** `INVOICE_TRANSITIONS` draft→posted→paid enforced server-side; re-post → 422; over-invoice (`invoiced_qty > qty_shipped−qty_invoiced`) → 422; over-receipt via reused `bills._is_overpayment` → 422; price locked to `so_line.unit_price` (client cannot supply `unit_price`/`amount`); `invoiced_qty`/allocation `amount` constrained `gt=0` in schemas.
- **Integration:** `qty_invoiced` added to model, read schema, FE type + render; increments only, no decrement path (matches out-of-scope void); migration 0017 up/down reverse-FK order matches models; `ArReceiptCreate` rename avoids shadowing the inventory `ReceiptCreate`.
- **RBAC/audit:** all 8 AR routes gated `syerp:read`/`syerp:write`; write audit rows emitted after service commit with `str()`-coerced `target_id` and `str(current_user.id)` actor.
- **Async:** no ORM relationships (lines/allocations loaded via explicit ordered SELECTs) — no MissingGreenlet exposure.

## Summary
1 major (unvalidated `sales_order_id` → recursive 500 on the create-invoice retry path); 0 blockers, 0 minor. All money/ledger, concurrency, FSM, and RBAC targets are otherwise correct.
