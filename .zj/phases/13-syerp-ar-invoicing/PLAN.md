# Plan: Phase 13 — SYERP-13 Accounts Receivable & sell-side books
Goal: A shop can invoice what it shipped, receive customer payments, and read an AR aging report that ties Decimal-exactly to the 1120 control account — all auto-posting balanced JEs on the SYERP-12 GL engine with the Trial Balance still netting zero.
Status: draft

### Phase facts (header block)
- **Branch:** `feature-syerp-ar-invoicing`, cut fresh off the verified 12b tip — tag `zj/good-12b-gelato-pick-pack-ship` (`553bcfb`). 11a/11b/12a/12b are unmerged; 13 stacks on 12b (D-V3-19 / D-P9b-8 / D-P10-8 precedent).
- **Migration:** `0017` (head is `0016_gelato_shipments`, confirmed via `alembic/versions/`).
- **Checklist:** `docs/tasks/feature-syerp-ar-invoicing.md`.
- **Module:** extend `backend/app/modules/syerp/`; new service submodule `service/ar.py` (D-V3-9 — AR is SYERP). Do NOT bloat `bills.py` / `reports.py` beyond the aging function.
- **This is the final v3.0 phase**; it closes v3.0 DoD clause 3. It is the **sell-side mirror** of shipped AP (9b bills/payments + 9c aging/statements). Copy proven in-repo patterns; invent nothing.

## Success criteria
Each maps to SYERP-13's 7 ACs (`.zj/SRD.md` lines 486-514). Every task cites the AC/SC it serves.
- **SC1 (AC1) — sell-side postings:** invoice JE (Dr 1120 / Cr 4110) and receipt JE (Dr cash / Cr 1120) post via `post_journal_entry` — ≥2 balanced lines, `Numeric(18,6)`/Decimal, append-only, reversible. The COGS-on-ship JE (Dr 5100 / Cr 1130) **already exists** in `gelato/service/shipments.py::execute_ship` (Phase 12b) — Phase 13 asserts it in the tie-out, does NOT rebuild it. No new CoA accounts.
- **SC2 (AC2) — invoice from shipment:** invoice a customer by selecting shipped-but-uninvoiced qty (`qty_shipped − qty_invoiced` at SO-line grain); partial shipments → partial invoices; `INV-####` numeric-safe; Draft→Posted→Paid FSM (invalid → 4xx); posting posts Dr 1120 / Cr 4110 with JE `entry_date = invoice_date`; **invoice line price LOCKS to `crumb_sales_order_line.unit_price`** (owner decision — not editable at invoice time).
- **SC3 (AC3) — customer receipts:** `Receipt` + `ReceiptAllocation` (one receipt settles N invoices, `amount == Σ allocations`); posting posts Dr <selectable cash/bank, default 1110> / Cr 1120; a receipt driving an invoice open balance negative → 4xx; invoice auto-advances to Paid at zero open.
- **SC4 (AC4) — AR aging:** open balances bucketed current / 31-60 / 61-90 / 90+ from invoice dates, per customer and total; grand total ties **Decimal-exactly** to the 1120 control balance.
- **SC5 (AC5) — statements:** with AR/revenue/COGS posted, the SYERP-12 Trial Balance still nets zero, P&L shows revenue − COGS, Balance Sheet includes AR and still balances. AR aging is the only NEW report screen; TB/P&L/BS are verified as regression.
- **SC6 (AC6) — audit:** invoice create/post, receipt, every JE + reversal emit attributable router-layer audit rows.
- **SC7 (AC7) — RBAC:** every endpoint gated `syerp:read` / `syerp:write`; un-permissioned call refused at HTTP (401/403) regardless of UI.

## Context

**Exemplar files read (mirror these exactly):**
- `backend/app/modules/syerp/service/bills.py` — THE sell-side mirror source:
  - `_next_bill_number` / `generate_bill_number` (lines 80-206) — numeric-safe `BILL-####`; note the regex `~ '^BILL-[0-9]+$'` filter *before* `cast(func.substring(bill_number, 6), Integer)` (6 = first digit after the 5-char `BILL-` prefix). For `INV-` the prefix is 4 chars → `substring(invoice_number, 5)` and regex `^INV-[0-9]+$`.
  - `BILL_TRANSITIONS` + `_bill_transition_allowed` (146-162) — draft→posted→paid FSM, paid terminal.
  - `create_bill` (300-497) — vendor gate, **FOR UPDATE lock on matched PO-line ids in sorted order BEFORE the read** (352-360), validate-all-before-write, dup-line guard, retry-once on number collision.
  - `_already_billed_qty` / `list_unbilled_receipts` (209-286) — the matched-picker shape (uninvoiced analog).
  - `post_bill` (684-758) — one balanced JE via `post_journal_entry(commit=False)`, status flip + `posted_at`, **single commit**, JE `entry_date = bill.bill_date` (the aging tie-out crux, D-P9c-1).
  - `record_payment` (761-953) — `Payment`+`PaymentAllocation`, ASSET-account guard, positive-amount guard, **FOR UPDATE lock on target bill rows in sorted id order (840-848)**, `_is_overpayment` guard with per-bill accumulation, one balanced JE, auto-Paid via `advance_bill_status`, single commit. `_is_overpayment` (105-115) is pure/generic — **reuse it** for the receipt guard (import from `.bills`) rather than duplicating.
- `backend/app/modules/syerp/service/journal.py::post_journal_entry` (249-...) — kwargs `entry_date, memo, lines=[{account_id,debit,credit}], actor_id, source_type, source_id, commit`. Balanced-lines 422 guard; `commit=False` rides the caller's transaction.
- `backend/app/modules/syerp/service/reports.py::ap_aging_report` (77-237) — buckets + control tie. Copy for AR: `2110→1120`, `Bill→Invoice`, `Payment→Receipt`, `PaymentAllocation→ReceiptAllocation`, `vendor→customer`, `bill_date→invoice_date`. **Remove the negation** at line 229: 2110 is credit-normal (raw Σdr−Σcr negated); 1120 is **debit-normal** so `control_balance = Σdr − Σcr` (positive receivable, no negation).
- `backend/app/modules/gelato/service/shipments.py::execute_ship` (517-699) — the existing COGS JE (Dr 5100 / Cr 1130 at moving-avg, `entry_date=date.today()`); stamps `so_line.qty_shipped`; imports `crumb.models.SalesOrderLine` and `syerp.service` functions. **Precedent for the cross-module write below** (a non-owning module stamping a crumb SO-line accumulator).
- `backend/app/modules/syerp/models.py` — `Bill`/`BillLine`/`Payment`/`PaymentAllocation` (510-705) are the ORM templates. All PKs are `String(36)` uuid; money `Numeric(18,6)`; no ORM relationships (async MissingGreenlet — Pitfall 2). GLAccount PK is `Integer`.
- `backend/app/modules/crumb/models.py::SalesOrderLine` (380-441) — has `unit_price`, `qty_shipped`, `qty_reserved` accumulators. **Needs a `qty_invoiced` accumulator** (mirror `qty_shipped`, D-P8-15). `crumb_sales_order` header carries `partner_id` (the customer), `so_number`, `status`.
- Router audit/RBAC template: `backend/app/modules/syerp/router.py` AP endpoints (1107-1298) — `Depends(require_permission("syerp:read|write"))`, `write_audit(db, actor_id=str(current_user.id), action=..., target_type=..., target_id=str(x.id), detail=...)` AFTER the service commit. **Coerce `target_id` with `str()`** (12a int-PK bug); Invoice/Receipt PKs are uuid strings so `str()` is a no-op but keep it for uniformity.
- Verify templates: `backend/scripts/verify_ap.py`, `verify_ap_api.py`, `verify_reports.py`, `verify_reports_api.py`.
- Frontend AP templates: `frontend/src/routes/syerp/{Bills,BillDetail,ApAging,FinancialReports}.tsx` + `components/{BillCreateDialog,PayBillDialog}.tsx` + `components/SyerpNav.tsx`; routes wired in `src/App.tsx` (25-86); SO-line accumulators render in `src/routes/crumb/components/SalesOrderDetailLines.tsx:165` and are typed in `src/routes/crumb/hooks.ts:527`.

**Cross-module coupling (flagged, not a blocker):** `qty_invoiced` lives on `crumb_sales_order_line` but is **stamped by SYERP's `create_invoice`** — SYERP writes a CRUMB column, the mirror direction of GELATO's `execute_ship` stamping `qty_shipped`. Justified by D-V3-9 (AR invoices import/reference CRUMB SO lines rather than duplicating). No invoice cancellation exists in v3.0, so the accumulator only ever increments (no decrement path needed).

**Seeded CoA (confirmed by owner, no migration):** 1110 Cash, 1111 Bank, 1120 AR, 1130 Inventory, 4110 Product Revenue, 5100 COGS. A verify preflight asserts `_gl_account_id_by_code` resolves each.

**Concurrency applies to TWO guards** (both read-modify-write on a ledger invariant): `create_invoice` (two drafts double-invoicing one shipped SO line) and `record_receipt` (two receipts over-allocating one invoice). Both must lock the contended rows FOR UPDATE in sorted-id order before the guard read (copy `create_bill` / `record_payment`). The load-bearing verify scenario targets `record_receipt` (the D-P9b headline); a second scenario covers `create_invoice`.

## Decisions needed
None. All architecture choices are pinned by the owner (single phase; price locks to SO-line `unit_price`; branch/migration; AR-in-SYERP; UI in-plan). Two implementation choices resolved in this plan (not owner-visible): **reuse** `bills._is_overpayment` for the receipt guard rather than duplicating; **increment `qty_invoiced` at draft create** (not at post) so a second draft cannot double-claim shipped qty — consistent with `create_bill` counting draft+posted.

## Tasks

### Wave A — schema

### [x] 1. Add Invoice + InvoiceLine ORM models
- **Files:** `backend/app/modules/syerp/models.py`
- **Do:** Mirror `Bill`/`BillLine` (510-623). `Invoice(String(36) pk, invoice_number String(30) unique index, customer_id FK→syerp_partner.id, sales_order_id String(36) FK→crumb_sales_order.id nullable, invoice_date Date not-null, status String(20) default 'draft', memo, posted_at DateTime nullable, actor_id, created_at, updated_at)`. `InvoiceLine(String(36) pk, invoice_id FK→syerp_invoice.id index, line_no Integer, sales_order_line_id String(36) FK→crumb_sales_order_line.id, invoiced_qty Numeric(18,6), unit_price Numeric(18,6), amount Numeric(18,6))`. No ORM relationships (Pitfall 2). Cite AC1/AC2.
- **Done when:** `python -c "from app.modules.syerp.models import Invoice, InvoiceLine"` imports clean; both tables appear in `Base.metadata`.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "from app.modules.syerp.models import Invoice, InvoiceLine; print(Invoice.__tablename__, InvoiceLine.__tablename__)"`
- **Parallel-ok:** yes

### [x] 2. Add Receipt + ReceiptAllocation ORM models
- **Files:** `backend/app/modules/syerp/models.py`
- **Do:** Mirror `Payment`/`PaymentAllocation` (631-705). `Receipt(String(36) pk, receipt_date Date, cash_account_id Integer FK→syerp_gl_account.id, amount Numeric(18,6), reference String(200) nullable, actor_id, created_at)`. `ReceiptAllocation(String(36) pk, receipt_id FK→syerp_receipt.id index, invoice_id FK→syerp_invoice.id index, amount Numeric(18,6))`. Cite AC1/AC3.
- **Done when:** both classes import clean and register on `Base.metadata`.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "from app.modules.syerp.models import Receipt, ReceiptAllocation; print('ok')"`
- **Parallel-ok:** yes

### [x] 3. Add `qty_invoiced` accumulator to SalesOrderLine (model + read schema + FE type/render)
- **Files:** `backend/app/modules/crumb/models.py` (SalesOrderLine, ~439); `backend/app/modules/crumb/schemas.py` (SalesOrderLineRead, 394-410); `frontend/src/routes/crumb/hooks.ts` (~527); `frontend/src/routes/crumb/components/SalesOrderDetailLines.tsx` (~165); `frontend/src/routes/crumb/SalesOrderDetail.test.tsx`.
- **Do:** Add `qty_invoiced: Mapped[Decimal] = mapped_column(Numeric(18,6), nullable=False, default=Decimal("0"))` mirroring `qty_shipped`. Add `qty_invoiced: Decimal` to `SalesOrderLineRead`. Add `qty_invoiced: string` to the FE line type and render a mono `<TableCell>` next to `qty_shipped`. Update the SO-detail Vitest fixture + assertion (mirror `qty_shipped: '4'`). **This is the dead-through-UI keeper** — the field must serialize AND render. Cite AC2/AC4.
- **Done when:** `SalesOrderLineRead.model_fields` contains `qty_invoiced`; the SO-detail Vitest asserts the value renders and passes.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "from app.modules.syerp import models; from app.modules.crumb.schemas import SalesOrderLineRead; print('qty_invoiced' in SalesOrderLineRead.model_fields)"` → `True`; then `cd frontend && npx vitest run src/routes/crumb/SalesOrderDetail.test.tsx`
- **Parallel-ok:** no (blocks migration 0017 and the AR service)

### [x] 4. Migration 0017 — create AR tables + add qty_invoiced column
- **Files:** `backend/alembic/versions/0017_syerp_ar_invoicing.py` (new)
- **Do:** `revision="0017", down_revision="0016"`. `upgrade`: create `syerp_invoice`, `syerp_invoice_line`, `syerp_receipt`, `syerp_receipt_allocation` (columns/FKs/indexes matching Tasks 1-2); `op.add_column("crumb_sales_order_line", Column("qty_invoiced", Numeric(18,6), nullable=False, server_default="0"))`. `downgrade`: drop the column then the four tables in reverse-FK order. Match the hand-written style of `0010_syerp_ap_bills.py`.
- **Done when:** `alembic upgrade head` reaches 0017 and a full `downgrade -1` / `upgrade head` round-trip succeeds with no diff.
- **Verify:** `podman exec compose_api_1 alembic upgrade head && podman exec compose_api_1 alembic downgrade -1 && podman exec compose_api_1 alembic upgrade head`
- **Parallel-ok:** no (depends on Tasks 1-3)

### [x] 5. Add Pydantic schemas for AR
- **Files:** `backend/app/modules/syerp/schemas.py`
- **Do:** Mirror the Bill/Payment/ApAging schema families. `UninvoicedShipmentRead(sales_order_line_id, so_number, item_id|description, uninvoiced_qty, unit_price)`. `InvoiceLineCreate(sales_order_line_id, invoiced_qty)` / `InvoiceCreate(customer_id, sales_order_id|None, invoice_date|None, lines)`. `InvoiceLineRead` + `InvoiceRead(id, invoice_number, customer_id, invoice_date, status, posted_at, total, open_balance, lines, created_at)` with `total`/`open_balance` DERIVED (constructed explicitly, mirror `BillRead`). `ReceiptAllocationCreate/Read`, `ReceiptCreate(receipt_date, cash_account_id, reference, allocations)`, `ReceiptRead`. `ArAgingBucketRow(customer_id, customer_name, current, d31_60, d61_90, d90_plus, total)`, `ArAgingTotals`, `ArAgingReport(as_of, customers, grand_total, control_balance, in_balance)`. Cite AC2/AC3/AC4.
- **Done when:** all schema classes import clean; `InvoiceRead.model_fields` has `open_balance`.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "from app.modules.syerp.schemas import InvoiceCreate, InvoiceRead, ReceiptCreate, ArAgingReport, UninvoicedShipmentRead; print('ok')"`
- **Parallel-ok:** yes (after Tasks 1-2)

### Wave B — backend service

### [ ] 6. Create `service/ar.py` — pure helpers + uninvoiced-shipments query
- **Files:** `backend/app/modules/syerp/service/ar.py` (new); `backend/app/modules/syerp/service/__init__.py` (re-export)
- **Do:** Pure helpers mirroring bills: `_INVOICE_NUMBER_RE = ^INV-[0-9]+$`, `_next_invoice_number`, `INVOICE_TRANSITIONS = {"draft":{"posted"},"posted":{"paid"},"paid":set()}`, `_invoice_transition_allowed`, `_uninvoiced_qty(qty_shipped, qty_invoiced)`. `async generate_invoice_number(db)` — regex filter then `cast(func.substring(invoice_number, 5), Integer)` (INV- is 4 chars). `async list_uninvoiced_shipments(db, customer_id)` — join `SalesOrderLine`→`SalesOrder` where `SalesOrder.partner_id == customer_id` and `qty_shipped - qty_invoiced > 0`; return `UninvoicedShipmentRead` rows carrying the locked `unit_price`. Re-export the public surface from `service/__init__.py`. Cite AC2.
- **Done when:** `from app.modules.syerp.service import list_uninvoiced_shipments, generate_invoice_number` works; `_next_invoice_number(["INV-9","INV-10"]) == "INV-0011"` (numeric, not lexicographic).
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "from app.modules.syerp.service.ar import _next_invoice_number; assert _next_invoice_number(['INV-9','INV-10'])=='INV-0011'; print('ok')"`
- **Parallel-ok:** no (foundation for Tasks 7-9)

### [ ] 7. `create_invoice` + invoice read layer (get_invoice / list_invoices)
- **Files:** `backend/app/modules/syerp/service/ar.py`
- **Do:** Mirror `create_bill` + `get_bill`/`list_bills`/`_bill_to_read`. `create_invoice(db, *, customer_id, sales_order_id, invoice_date, lines, actor_id)`: (1) customer gate — Partner exists AND `is_customer` (422 else); (2) **lock target SO-line rows FOR UPDATE in sorted id order BEFORE the read** (copy `create_bill` 352-360); (3) per line validate-before-write: load SO line (404), confirm it belongs to a SO with `partner_id == customer_id` (422 else), dup-line guard (422), compute `uninvoiced = qty_shipped − qty_invoiced`, reject `invoiced_qty > uninvoiced` (422, the negative-open guard D-P8-7), lock `unit_price = so_line.unit_price`, `amount = invoiced_qty * unit_price`; (4) `so_line.qty_invoiced += invoiced_qty`; (5) persist `Invoice` (`INV-####`, retry-once on IntegrityError) + `InvoiceLine`s, status 'draft', `invoice_date or date.today()`; single commit; return `get_invoice`. `get_invoice`/`list_invoices` derive `total = Σ line.amount`, `open_balance = total − Σ ReceiptAllocation.amount` (each side coalesced, D-P8-4). Cite AC2.
- **Done when:** creating an invoice against a shipped SO line returns an `InvoiceRead` with `INV-0001`, correct `total`, and bumps `so_line.qty_invoiced`; over-invoicing a line returns 422.
- **Verify:** exercised by `verify_ar.py` Task 12 (invoice-from-shipment match).
- **Parallel-ok:** no

### [ ] 8. `post_invoice` — Dr 1120 / Cr 4110 JE + FSM
- **Files:** `backend/app/modules/syerp/service/ar.py`
- **Do:** Mirror `post_bill` (684-758). Load invoice (404); FSM guard — only 'draft' posts (422 via `_invoice_transition_allowed`); build ONE balanced JE `[{1120, debit=total}, {4110, credit=total}]` where `total = Σ InvoiceLine.amount`; `post_journal_entry(commit=False, entry_date=invoice.invoice_date, source_type="ar_invoice", source_id=invoice.id)`; set `status='posted'`, `posted_at=now`; **single commit**. `entry_date = invoice_date` is the aging tie-out crux (D-P9c-1). Cite AC1/AC2.
- **Done when:** posting a draft invoice flips it to 'posted', writes a balanced JE that raises the 1120 balance by `total`; re-posting a posted invoice → 422.
- **Verify:** exercised by `verify_ar.py` (control-tie + TB nets zero).
- **Parallel-ok:** no

### [ ] 9. `record_receipt` — allocations + FOR-UPDATE guard + Dr cash / Cr 1120 JE + auto-Paid
- **Files:** `backend/app/modules/syerp/service/ar.py`
- **Do:** Mirror `record_payment` (761-953). `record_receipt(db, *, receipt_date, cash_account_id, reference, allocations, actor_id)`: guard cash account is ASSET (422); every allocation amount > 0 and Σ > 0 (422); **lock target invoice rows FOR UPDATE in sorted id order BEFORE the guard read**; per invoice: exists (404), status == 'posted' (422 for draft/paid), live `open_balance = total − Σ prior ReceiptAllocation` (coalesced), reject overpayment via reused `bills._is_overpayment` with per-invoice accumulation for same-invoice allocations; persist `Receipt` (`amount = Σ allocations`) + `ReceiptAllocation`s; ONE balanced JE `[{cash_account_id, debit=total},{1120, credit=total}]` (`commit=False`, `source_type="ar_receipt"`); re-derive each touched invoice open balance, flip 'posted'→'paid' at exactly zero via the FSM; **single commit**; return `ReceiptRead`. Cite AC1/AC3.
- **Done when:** a full receipt drives the invoice to 'paid' and 1120 down by the amount; an over-allocation returns 422 with nothing persisted; a partial receipt leaves 'posted' with reduced open balance.
- **Verify:** exercised by `verify_ar.py` (overpayment reject + concurrency scenario).
- **Parallel-ok:** no

### [ ] 10. `ar_aging_report` in reports.py
- **Files:** `backend/app/modules/syerp/service/reports.py`; `service/__init__.py` (re-export)
- **Do:** Copy `ap_aging_report` (77-237). Substitute `Bill→Invoice`, `Payment→Receipt`, `PaymentAllocation→ReceiptAllocation`, `vendor_id→customer_id`, `bill_date→invoice_date`, `2110→1120`. Include only invoices with `status in ('posted','paid')` and `invoice_date <= as_of` (drafts excluded — not on 1120). Bucket `open_balance = Σ line.amount − Σ ReceiptAllocation.amount` (receipts dated ≤ as_of). **`control_balance = Σdr − Σcr` over 1120, NO negation** (1120 is debit-normal). `in_balance = grand_total == control_balance`. Cite AC4.
- **Done when:** `ar_aging_report` returns buckets per customer + grand total; `in_balance` is True in a mixed shipped/invoiced/partially-received scenario.
- **Verify:** exercised by `verify_ar.py` (Decimal-exact control tie).
- **Parallel-ok:** no (after Tasks 8-9)

### [ ] 11. AR router endpoints — RBAC-gated, audit-after-commit
- **Files:** `backend/app/modules/syerp/router.py`
- **Do:** Mirror the AP endpoints (1107-1298). Add: `GET /syerp/ar/uninvoiced-shipments?customer_id=` (read); `POST /syerp/ar/invoices` (write, 201, audit `invoice.created`); `GET /syerp/ar/invoices` (+`customer_id`/`status`) and `GET /syerp/ar/invoices/{id}` (read); `POST /syerp/ar/invoices/{id}/post` (write, audit `invoice.posted`); `POST /syerp/ar/receipts` (write, 201, audit `receipt.recorded`); `GET /syerp/ar/receipts` (read); `GET /syerp/ar/aging?as_of=` (read, no audit). All writes `Depends(require_permission("syerp:write"))`, reads `syerp:read`. `write_audit(..., target_id=str(x.id))` AFTER each service commit. Cite AC2/AC3/AC6/AC7.
- **Done when:** the 8 routes appear in OpenAPI (`/api/v1/syerp/ar/...`); a write route with a read-only token → 403, no token → 401.
- **Verify:** `podman exec compose_api_1 python -c "from app.main import create_app; app=create_app(); print([r.path for r in app.routes if '/ar/' in getattr(r,'path','')])"` shows all 8 paths.
- **Parallel-ok:** no (after Tasks 6-10)

### Wave C — verify

### [ ] 12. `verify_ar.py` — service-level tie-out + match + reject + COGS tie + concurrency
- **Files:** `backend/scripts/verify_ar.py` (new)
- **Do:** Mirror `verify_ap.py`. Build inputs in **real router/payload shape**. Scenarios: (A) preflight — assert 1110/1111/1120/1130/4110/5100 resolve; (B) end-to-end tie-out — receive→ship (asserts the 12b COGS-on-ship Dr 5100/Cr 1130 moving-avg JE exists) → create_invoice from the shipped SO line (assert uninvoiced match, price locked to SO `unit_price`) → post_invoice → record partial + full receipt → assert AR aging **grand_total == 1120 control balance Decimal-exactly** on one date basis (invoice_date), and invoice auto-Paid at zero; (C) over-invoice rejected 422; (D) over-receipt rejected 422; (E) **load-bearing concurrency** — two `asyncio.gather` receipts against one invoice whose combined amount exceeds open balance: exactly one succeeds, one 422s; construct the fixture so ONLY the over-allocation guard can reject (give amount/FSM guards slack), and mutation-prove (revert the FOR-UPDATE lock → two successes); (F) second concurrency scenario — two concurrent `create_invoice` against one shipped SO line cannot jointly over-invoice. Exit non-zero on any failure. Cite AC1/AC2/AC3/AC4.
- **Done when:** `verify_ar.py` exits 0 on the built stack; reverting either FOR-UPDATE lock makes scenario E or F fail (load-bearing proof recorded).
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_ar.py; echo $?`
- **Parallel-ok:** no

### [ ] 13. `verify_ar_api.py` — HTTP RBAC + attributable audit rows
- **Files:** `backend/scripts/verify_ar_api.py` (new)
- **Do:** Mirror `verify_ap_api.py`. Over HTTP: each write route with no token → 401, read-only token → 403, `syerp:write` → 200/201; each read route gated `syerp:read`. After a successful invoice create/post and receipt, assert an attributable audit row (`invoice.created` / `invoice.posted` / `receipt.recorded`) exists with the actor id. Cite AC6/AC7.
- **Done when:** script exits 0; every AR route proves the 401/403/200 triad and audit rows are present.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_ar_api.py; echo $?`
- **Parallel-ok:** no

### [ ] 14. Full regression suite + Trial Balance nets zero with AR JEs
- **Files:** none (runs existing scripts)
- **Do:** Run the full `verify_*` suite AFTER the AR chain has posted invoice + receipt JEs; every script exits 0 and the SYERP-12 Trial Balance still nets zero. Suite: `verify_gelato_ship`, `verify_gelato_ship_api`, `verify_ap`, `verify_ap_api`, `verify_reports`, `verify_reports_api`, `verify_gl` (if present), `verify_mousse`, `verify_inventory`, `verify_purchasing`, `verify_crumb`, `verify_crumb_so`, `verify_e2e_p8` (whichever exist under `backend/scripts/`), plus `verify_ar` + `verify_ar_api`. Cite AC5.
- **Done when:** every script exits 0; `reports/trial-balance` `in_balance == True` and balance sheet balances with AR present.
- **Verify:** `for s in $(ls backend/scripts/verify_*.py | xargs -n1 basename); do podman exec -e PYTHONPATH=/app compose_api_1 python scripts/$s || echo "FAIL $s"; done`
- **Parallel-ok:** no (final gate)

### Wave D — frontend

### [ ] 15. Invoices list + create-from-shipment dialog
- **Files:** `frontend/src/routes/syerp/Invoices.tsx` (+ `.test.tsx`); `frontend/src/routes/syerp/components/InvoiceCreateDialog.tsx` (+ `.test.tsx`); `frontend/src/api/` hook (mirror Bills hooks)
- **Do:** Mirror `Bills.tsx` + `BillCreateDialog.tsx`. List invoices with number/customer/date/status/total/open_balance. Create dialog: pick a customer (reuse Customers source), fetch `/syerp/ar/uninvoiced-shipments?customer_id=`, select lines + qty (price shown read-only, locked to SO `unit_price`), POST `/syerp/ar/invoices`. Vitest asserts the picker renders `uninvoiced_qty` and the read-only locked price from the **real payload shape**. Cite AC2.
- **Done when:** Vitest passes; dialog builds the real create payload.
- **Verify:** `cd frontend && npx vitest run src/routes/syerp/Invoices.test.tsx src/routes/syerp/components/InvoiceCreateDialog.test.tsx`
- **Parallel-ok:** yes (after Task 11)

### [ ] 16. Invoice detail — Post action + Paid status + open balance
- **Files:** `frontend/src/routes/syerp/InvoiceDetail.tsx` (+ `.test.tsx`)
- **Do:** Mirror `BillDetail.tsx`. Header + lines + derived total/open_balance; a Post button (draft only) calling `/syerp/ar/invoices/{id}/post`; status badge draft/posted/paid. Vitest asserts open_balance renders and Post is hidden once posted. Cite AC2.
- **Done when:** Vitest passes.
- **Verify:** `cd frontend && npx vitest run src/routes/syerp/InvoiceDetail.test.tsx`
- **Parallel-ok:** yes (after Task 11)

### [ ] 17. Receipts — record receipt against posted invoices
- **Files:** `frontend/src/routes/syerp/Receipts.tsx` (+ `.test.tsx`); `frontend/src/routes/syerp/components/RecordReceiptDialog.tsx` (+ `.test.tsx`)
- **Do:** Mirror the `PayBillDialog` pattern. Dialog: pick cash/bank account (default 1110), allocate amounts across one or more posted invoices, POST `/syerp/ar/receipts`. List receipts with allocations. Vitest asserts the allocation payload shape and account default. Cite AC3.
- **Done when:** Vitest passes; payload matches `ReceiptCreate`.
- **Verify:** `cd frontend && npx vitest run src/routes/syerp/Receipts.test.tsx src/routes/syerp/components/RecordReceiptDialog.test.tsx`
- **Parallel-ok:** yes (after Task 11)

### [ ] 18. AR Aging screen + nav + routes + build
- **Files:** `frontend/src/routes/syerp/ArAging.tsx` (+ `.test.tsx`); `frontend/src/routes/syerp/components/SyerpNav.tsx`; `frontend/src/App.tsx`
- **Do:** Mirror `ApAging.tsx` — buckets per customer + grand total + control-balance tie / `in_balance` badge, `as_of` picker. Add nav items (Invoices, Receipts, AR Aging) near the existing AP items in `SyerpNav`; register routes `/syerp/ar/invoices`, `/syerp/ar/invoices/:id`, `/syerp/ar/receipts`, `/syerp/ar/aging` in `App.tsx`. Vitest asserts the aging table + tie badge render. Cite AC4/AC5.
- **Done when:** `npm run build` (`tsc -b && vite build`) succeeds; ArAging Vitest passes; nav shows the three AR items.
- **Verify:** `cd frontend && npx vitest run src/routes/syerp/ArAging.test.tsx && npm run build`
- **Parallel-ok:** no (touches shared App.tsx / SyerpNav — sequence after 15-17)

## Risks
- **Aging sign flip (control tie):** copying `ap_aging_report` verbatim keeps the 2110 negation — 1120 is debit-normal and must NOT be negated. Early warning: `verify_ar.py` scenario B `in_balance == False` or a negative `control_balance`. Fix is the single line at reports.py ~229.
- **Concurrency lock omitted or non-load-bearing (recurring blocker, D-P9b/12b):** if the FOR-UPDATE lock is missing OR the verify fixture lets a bystander guard (amount/FSM) reject, a missing lock hides. Early warning: reverting the lock in scenario E/F still yields one rejection (should yield two successes). Mitigate by mutation-proving both guards.
- **`qty_invoiced` dead-through-UI (12b qty_shipped precedent):** field added to the model but not the read schema / FE type / render — invisible. Early warning: Task 3 Vitest. Non-negotiable per keeper.
- **Cross-module write ordering:** `create_invoice` stamps `crumb_sales_order_line.qty_invoiced` inside SYERP's transaction; if the SO line is loaded without the identity-map/lock, concurrent invoices lose updates. Early warning: scenario F. Mitigated by the FOR-UPDATE lock in Task 7.
- **MAP.md staleness:** the codebase MAP lists head 0012 and omits gelato/AR-era migrations; trust `alembic/versions/` (head 0016) over MAP.

## Out of scope
- Invoice **cancellation / void** and credit memos (no decrement path for `qty_invoiced`; deferred).
- Editing invoice line price at invoice time (owner locked it to SO `unit_price`).
- Re-implementing the COGS-on-ship JE (already shipped in 12b; asserted only).
- New CoA accounts, closing entries, tax lines, multi-currency, statements/PDF export.
- Merging 11a/11b/12a/12b to master (branch stacks on 12b; merge is a milestone concern).

## Noticed
- `service/__init__.py` re-exports the public surface; every new public AR function (Tasks 6-10) must be added there or the router import breaks — fold into each task, don't defer.
- `list_payments_endpoint` (router 1268-1274) still lazy-imports its service read with a P9b workaround note; when mirroring for `list_receipts` prefer the top-of-module import (the `ar.py` read exists by Task 9) — cleaner than repeating the workaround.
- `execute_ship` posts the COGS JE with `entry_date=date.today()`, while the invoice JE uses `invoice_date`. That is correct (COGS ages on ship date, AR on invoice date) but means COGS and revenue can land in different periods for a late invoice — acceptable for v3.0; note for any future revenue-recognition matching work.
- Lint gates are non-functional (BACKLOG p1); correctness rests on `verify_*` + Vitest. No ruff/eslint task added.
