# Task: feature-syerp-ar-invoicing (Phase 13 — SYERP-13 AR & sell-side books)

Plan: `.zj/phases/13-syerp-ar-invoicing/PLAN.md`. Closes v3.0 DoD clause 3.
Branch cut off the verified 12b tip (code-identical to tag `zj/good-12b-gelato-pick-pack-ship`).

## Wave A — schema
- [x] 1. Add Invoice + InvoiceLine ORM models
- [x] 2. Add Receipt + ReceiptAllocation ORM models
- [x] 3. Add `qty_invoiced` accumulator to SalesOrderLine (model + read schema + FE type/render)
- [x] 4. Migration 0017 — create AR tables + add qty_invoiced column
- [x] 5. Add Pydantic schemas for AR

## Wave B — backend service
- [x] 6. Create `service/ar.py` — pure helpers + uninvoiced-shipments query
- [ ] 7. `create_invoice` + invoice read layer (get_invoice / list_invoices)
- [ ] 8. `post_invoice` — Dr 1120 / Cr 4110 JE + FSM
- [ ] 9. `record_receipt` — allocations + FOR-UPDATE guard + Dr cash / Cr 1120 JE + auto-Paid
- [ ] 10. `ar_aging_report` in reports.py
- [ ] 11. AR router endpoints — RBAC-gated, audit-after-commit

## Wave C — verify
- [ ] 12. `verify_ar.py` — service-level tie-out + match + reject + COGS tie + concurrency
- [ ] 13. `verify_ar_api.py` — HTTP RBAC + attributable audit rows
- [ ] 14. Full regression suite + Trial Balance nets zero with AR JEs

## Wave D — frontend
- [ ] 15. Invoices list + create-from-shipment dialog
- [ ] 16. Invoice detail — Post action + Paid status + open balance
- [ ] 17. Receipts — record receipt against posted invoices
- [ ] 18. AR Aging screen + nav + routes + build
