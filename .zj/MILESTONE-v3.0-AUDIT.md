# Milestone v3.0 "Customer & logistics" — goal-backward close-out audit

Date: 2026-07-19 | Auditor: ZJ verifier (adversarial, evidence-only)
Method: drove the WHOLE money loop on ONE sales order end-to-end against the live
container `compose_api_1`, then probed the cross-phase seams the five green phase
verifications (11a/11b/12a/12b/13) each individually owned but none owned together.
All test data was created through the REAL service layer and cleaned up; the DB was
returned to its pre-audit baseline (TB 3600=3600, AR aging in_balance, zero residue).

## Resolution (2026-07-19, at close): BOTH GAPS FIXED (owner chose fix-both-now)

`97b977b` — **GAP-1** fixed at the report layer: `ar_aging_report` now adds back the
1120 credit legs of receipts allocated to invoices dated after `as_of` (prepayment
reclassification), so the tie-out holds and `in_balance` stays true for every date
ordering while `control_balance` remains GL-sourced. **GAP-2** fixed: the
uninvoiced-shipments picker carries a resolved `item_label` ("code — name") and the
invoice dialog renders that, never a bare UUID. Both pinned load-bearing by `verify_ar`
scenario (G) (revert the `prepay_adjust` block → the `as_of=today` tie-out fails) and by
FE render assertions. Re-verified: 23/23 `verify_*` exit 0, whole-DB TB nets zero,
`npm run build` clean, 131 Vitest green. Decisions D-M3-1 (GAP-1 fix) / D-M3-2 (GAP-2 fix).

## Overall verdict: GAPS (one MINOR) — milestone may close with the gap logged

The Definition of Done holds end-to-end. A single sales order flowed
order → reserve → pick → pack → (partial) ship → uninvoiced-picker →
invoice-from-shipment (price locked) → post → partial receipt → full receipt →
auto-Paid, with COGS/AR/Revenue/Cash journal entries all correct, AR aging tying
Decimal-exact to the 1120 control at every stage, and the whole-DB Trial Balance
still netting zero afterward (19/19 assertions PASS). One real defect the phase
verifications missed: the AR aging tie-out badge breaks (reports a nonsensical
NEGATIVE 1120 control and `in_balance=False`) when a receipt is dated before its
invoice's `invoice_date` and aging is viewed as-of a date between the two. This is
the v3.0 equivalent of the v1.0 Where-Used mislabel / v2.0 P&L-empty-date gap —
narrow, non-corrupting, report-display only. Not a blocker.

---

## DoD clause verdicts

### Clause 1 — CRM & sales pipeline (CRUMB-01): MET
| Truth | Evidence |
|---|---|
| Confirming an order soft-reserves inventory | e2e: confirm SO(40) → `qty_reserved==40` |
| available = on-hand − reserved | e2e: on-hand 100 − reserved 40 = 60 |
| PLUM-derived editable line pricing, then locked | SO line `unit_price=25` carried through the uninvoiced picker and locked onto the invoice line (`InvoiceLineRead.unit_price==25`) |
| Cancel releases the reservation | `cancel_sales_order` zeroes `qty_reserved` (sales_orders.py:673-675); `_reserved_by_other_open_sos` filters status ∈ {confirmed, fulfilling} so `closed`/`cancelled` reservations never strand availability (sales_orders.py:566-570) |

### Clause 2 — Warehouse fulfillment (GELATO-01): MET
| Truth | Evidence |
|---|---|
| Bins within stock locations; directed putaway on receipt | `execute_putaway` net-adds to a bin; pick list suggests source bins |
| Outbound pick → pack → ship of a sales order | e2e drove all three FSM stages on one SO |
| Shipping relieves the reserved inventory (qty only) | **PARTIAL ship of 30/40**: `qty_shipped==30`, `qty_reserved` fell 40→10 EXACTLY; relief clamped `max(0, …)` (shipments.py:655-657) |
| No double-relief / double-COGS | double-ship blocked by shipment-row `FOR UPDATE` + FSM gate (shipments.py:582-599, the 12b blocker fix is in place) |

### Clause 3 — Accounts receivable & sell-side books (SYERP-13): MET, with GAP-1 (minor)
| Truth | Evidence |
|---|---|
| Shipment posts Dr 5100 COGS / Cr 1130 Inventory at moving-avg | e2e: ΔCOGS +300, ΔInventory −300 (30 units × $10 mavg) |
| Invoice-from-shipment posts Dr 1120 AR / Cr 4110 Revenue | e2e: ΔAR +750, ΔRevenue −750 (30 × locked $25) |
| Uninvoiced-shipments query surfaces the shipped-but-uninvoiced SO line | e2e: picker returned the line at `uninvoiced_qty=30`, `unit_price=25` |
| Customer receipt posts Dr Cash / Cr 1120 AR; auto-Paid at zero | e2e: partial 300 → still `posted` open 450; full 450 → `paid` open 0; 1120 back to baseline |
| AR aging ties Decimal-exactly to the 1120 control (debit-normal, NO negation) | e2e: grand_total == control_balance and `in_balance` at every stage (post, partial, full); control taken WITHOUT negation (reports.py:377-395) |
| Trial Balance still nets zero after the full loop | e2e: TB `in_balance` true, 4350=4350 mid-loop, 3600=3600 after cleanup |
| **Aging tie-out under receipt_date < invoice_date** | **BROKEN — see GAP-1** |

---

## Ranked gaps

### GAP-1 (MINOR) — AR aging tie-out reports a false out-of-balance + negative 1120 control when a receipt predates its invoice_date
- **Where:** `backend/app/modules/syerp/service/reports.py::ar_aging_report`. The
  subledger `grand_total` only counts invoices with `invoice_date <= as_of`
  (reports.py:277-282), but `control_balance` sums *every* 1120 journal line with
  `entry_date <= as_of` (reports.py:381-394) — including a receipt's Cr-1120 leg
  (`entry_date = receipt_date`) whose matching invoice Dr-1120 leg
  (`entry_date = invoice_date`) is excluded because the invoice is dated after
  `as_of`. The two sides then diverge.
- **Reproduced live (throwaway data, cleaned up):** ship 10 @ $10 cost / $100 price;
  post an invoice with `invoice_date = today+10`; record a $400 receipt with
  `receipt_date = today`; run `ar_aging(as_of=today)`:
  `grand_total=0, control_balance=-400.00, in_balance=False`. At `as_of=today+10`
  it ties again (`600 == 600, in_balance=True`).
- **Failure scenario (reachable through the normal API):** a customer prepayment /
  advance deposit, or any future-dated (or later-dated) invoice against an
  earlier-recorded receipt. The AR Aging screen then shows a red "out of balance"
  tie-out badge and a physically-impossible negative receivable for that as-of date,
  even though the GL and the underlying data are correct. `record_receipt` does not
  guard `receipt_date >= invoice_date`, and neither `create_invoice` nor
  `post_invoice` rejects a future `invoice_date`.
- **Why the phase verifications missed it:** `verify_ar.py` / `verify_ar_api.py`
  exercise the tie-out with invoices dated on/before their receipts (the normal
  ordering), which always ties. No test drives `receipt_date < invoice_date`.
- **Not a blocker:** the normal ordering ties exactly (19/19 e2e + verify_ar green),
  no data is corrupted, and the whole-DB Trial Balance always nets zero.
- **Suggested fix (pick one):** in `ar_aging_report`, exclude from `control_balance`
  the 1120 legs of receipts allocated to invoices dated after `as_of` (compute the
  control from the same invoice population the subledger uses); and/or guard
  `receipt_date >= min(invoice_date)` in `record_receipt`; and/or reject a future
  `invoice_date`. Pin whichever with a `verify_ar` scenario that dates a receipt
  before its invoice.

### GAP-2 (trivial nit) — invoice picker shows a raw item UUID
- `frontend/src/routes/syerp/components/InvoiceCreateDialog.tsx:334` renders
  `s.item_id ?? s.description`, i.e. a bare item UUID when the SO line has an item.
  Cosmetic; an item name/SKU would read better. No functional impact.

---

## Seams probed that held (adversarial, no gap found)
- **The money loop as ONE story:** driven end-to-end on ONE order incl. a partial
  ship — each stage consumed the prior stage's state (reserve → pick → pack → ship →
  qty_shipped → uninvoiced picker → invoice → qty_invoiced → post → receipt →
  auto-Paid). 19/19 assertions PASS.
- **Reservation integrity across the seam:** partial ship relieved exactly (40→10),
  never negative (`max(0, …)`); double-ship blocked by shipment `FOR UPDATE` + FSM;
  cancel releases; `closed`/`cancelled` excluded from availability by status filter,
  so residual `qty_reserved` on a closed order cannot strand stock.
- **Cross-phase contract drift (frontend↔backend):** `InvoiceCreateDialog` fields
  (`sales_order_line_id, so_number, item_id, description, uninvoiced_qty,
  unit_price`), routes (`/ar/uninvoiced-shipments?customer_id=`, `/ar/invoices`),
  and the `partners?role=customer` filter all match the backend
  schemas/router — no drift. Invoice line price is read-only, locked to the SO line.
- **Boundary-input on the new report (v2.0 P&L class):** the AR Aging screen guards
  an empty `as_of` with `enabled: !!asOf` (ArAging.tsx:96), so it never fires the
  empty-date request that 422'd the P&L in v2.0.
- **Sign / tie-out:** 1120 control taken WITHOUT negation (debit-normal), `grand ==
  control` verified at post / partial-receipt / full-receipt; 1120 returns to
  baseline after full collection.

## What was run
- Whole-loop driver (create partner + item + stock → putaway → SO → confirm →
  pick → pack → partial ship → list uninvoiced → invoice-from-shipment → post →
  partial + full receipt → aging + TB tie-outs), then a targeted date-seam probe;
  both self-cleaned. Post-audit baseline reconfirmed: TB 3600=3600,
  AR aging `in_balance`, no PROBE/AUDIT residue.
- (Pre-established, not re-derived) all 23 `backend/scripts/verify_*.py` exit 0;
  whole-DB TB nets zero.
