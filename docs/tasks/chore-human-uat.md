# Task: chore-human-uat

**Branch:** `chore-human-uat` (cut off `c02d80b` per D-P5-9, then fast-forwarded to the
plan-carrying tip `4171605` — docs-only, code-identical to `c02d80b`; trivial deviation,
same pattern as Phases 3/4/13)
**Phase:** v4.0 Phase 5 — Human click-through UAT (NFR-8) — **final v4.0 phase**
**Plan:** `.zj/phases/05-human-uat/PLAN.md`

Every shipped UI flow — CORE, PLUM, SYERP (inventory/purchasing/GL/AP/AR/reports), MOUSSE,
CRUMB, GELATO — passes a documented human click-through against the hardened v4.0 stack,
with every defect fixed (blocker/major, pinned by an automated test) or homed to BACKLOG
with a `U#` ID.

**[OWNER]** tasks are click-through sittings run by the owner, not the engineer. Per the
plan's hand-back protocol, an engineer must never tick an owner check or infer a pass.

## Checklist

### Fixtures (SC2)

- [x] 0. Cut branch and checklist
- [x] 1. Seed-script skeleton: idempotency contract + manifest (`seed_uat_fixtures.py`)
- [x] 2. Seed the CORE + partners fixture layer
- [x] 3. Seed the PLUM fixture layer
- [x] 4. Seed the SYERP inventory + purchasing fixture layer
- [x] 5. Seed the GELATO bins fixture layer
- [x] 6. Seed the MOUSSE + CRUMB fixture layer
- [x] 7. Seed the SYERP GL / AP / AR fixture layer
- [x] 8. Prove the seed idempotent on a genuinely fresh volume
- [x] 8a. Fix `U0` — fresh-volume deploy blocker, dedicated `.env.db` (D-P5-10, added mid-build)

### Pre-flight (SC3)

- [x] 9. Write the check → machine-assertion map (`PREFLIGHT.md`)
- [x] 10. Add probes for the machine-unproven surfaces worth probing
- [x] 10a. Fix `U1` — HTTP 500 on duplicate-email user creation (added mid-build)

### The checklist (SC1)

- [x] 11. Author `.zj/UAT-v4.0.md`: preamble, fixture table, ordering rule, defect ledger
- [x] 12. Author the CORE + PLUM checks
- [x] 13. Author the SYERP checks
- [x] 14. Author the MOUSSE, CRUMB and GELATO checks
- [x] 15. Author the SC6 bin-picker checks, including the GELATO-off degraded path
- [x] 16. Execute every command in the runbook once, at build time
- [x] 17. Add pointer lines to the v1.0 and v2.0 UAT docs

### The SC8 validation check

- [ ] 18. Add the positive-adjust bin existence + membership check
- [ ] 19. Pin the membership check with a new `verify_gelato.py` scenario (G)

### The owner run (SC4/SC6) — read-only before mutating

- [ ] 20. **[OWNER]** CORE platform click-through
- [ ] 21. **[OWNER]** PLUM read-only click-through
- [ ] 22. **[OWNER]** PLUM mutating click-through
- [ ] 23. **[OWNER]** SYERP financial read-only click-through (GL, AP, AR, reports)
- [ ] 24. **[OWNER]** SYERP inventory read-only click-through
- [ ] 25. **[OWNER]** SYERP inventory mutating click-through + adjust/transfer bin pickers
- [ ] 26. **[OWNER]** Module-toggle propagation and the GELATO-off degraded path
- [ ] 27. **[OWNER]** SYERP purchasing click-through
- [ ] 28. **[OWNER]** MOUSSE click-through + the per-line issue bin picker
- [ ] 29. **[OWNER]** CRUMB click-through
- [ ] 30. **[OWNER]** GELATO click-through
- [ ] 31. **[OWNER]** SYERP money-loop tail click-through

### Close-out

- [ ] 32. Reconcile the checklist: zero `todo`, every defect homed
- [ ] 33. Run the full regression gate
- [ ] 34. Rebuild `frontend/dist` and the API container image
- [ ] 35. Bring the prod stack up on a fresh volume at :8000
- [ ] 36. **[OWNER]** Prod-stack deploy smoke at :8000
- [ ] 37. Bookkeeping: SRD NFR-8 and requirements-progress
- [ ] 38. Bookkeeping: ROADMAP, BACKLOG, DECISIONS, and archive the checklist

## Records

### Task 8 — fresh-volume idempotency manifests

**Environment.** `podman-compose -f compose/compose.yml -f compose/compose.dev.yml down -v`
(volume `compose_pgdata` destroyed), then a clean bring-up. Confirmed genuinely empty
before seeding: `gl_accounts=47`, `stock_locations=1` (`Main`), `partners=0`,
`journal_entries=0`, `plum_parts=0` — i.e. only the startup seeds had run.

```
$ podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && alembic current'
0017 (head)
```

**Result.** Both runs exited 0 and their manifests are byte-identical:

```
$ diff manifest1 manifest2
$ echo $?
0
```

Run 1 exercised every *create* path (empty database); run 2 every *get* path. The live
dev stack was then reset to a clean fresh volume and seeded once more, and its manifest
matches the record below exactly — so these literals describe the running stack.

> **These are the authoritative literals for `.zj/UAT-v4.0.md`.** They differ from every
> earlier dev-database manifest, because the dev volume carried 4950.00 of orphaned
> `po_receipt` GR/IR journal entries left behind by repeated `verify_purchasing.py` runs
> (that script's cleanup drops the PO, its lines and its stock txns, but not the
> auto-posted receipt JE). Anything quoting the old totals is stale.
>
> **Caveat for whoever reads the TB/BS off the screen (Task 23):** the aggregate
> `trial_balance` and `balance_sheet` totals below are whole-ledger figures and shift if
> any `verify_*.py` script is run against the same database — measured: running the
> twelve verify scripts added exactly 50.00 to total debit, total credit and total
> liabilities. The fixture-specific literals (bill/invoice numbers, aging buckets, the
> 1120/2110 controls) were unaffected. Re-seed on a fresh volume before quoting the
> aggregates.

#### Manifest — run 1 and run 2 (identical)

```
# BizNiceSweets UAT fixture manifest
# fixture prefix: UAT-

## tables

| table | rows |
| --- | --- |
| crumb_interaction (UAT-) | 2 |
| crumb_lead (UAT-) | 1 |
| crumb_opportunity (UAT-) | 2 |
| crumb_quote (UAT-) | 2 |
| crumb_sales_order (UAT-) | 2 |
| gelato_bin (UAT-) | 4 |
| gelato_shipment (UAT-) | 1 |
| mousse_work_order (UAT-P) | 2 |
| plum_avl_link (UAT-P) | 2 |
| plum_bom_item (UAT-P) | 10 |
| plum_part (UAT-P) | 15 |
| roles (UAT-) | 1 |
| syerp_bill (UAT-) | 2 |
| syerp_inventory_item (UAT-) | 10 |
| syerp_inventory_txn (UAT-) | 25 |
| syerp_invoice (UAT-) | 1 |
| syerp_partner (UAT-) | 5 |
| syerp_payment (UAT-) | 1 |
| syerp_purchase_order (UAT-) | 3 |
| syerp_purchase_order_line (UAT-) | 4 |
| syerp_receipt (UAT-) | 1 |
| syerp_stock_location (UAT-) | 3 |
| users (uat-) | 1 |

## fixture keys

| category | key |
| --- | --- |
| auth.role | UAT-PLUM-ONLY |
| auth.user | uat-plum-user@example.invalid |
| crumb.lead | UAT-LEAD-1 |
| crumb.opportunity | UAT-OPP-1 |
| crumb.opportunity | UAT-OPP-2 |
| gelato.bin | UAT-BIN-A1 |
| gelato.bin | UAT-BIN-A2 |
| gelato.bin | UAT-BIN-A3 |
| gelato.bin | UAT-BIN-STAGE |
| plum.part | UAT-P101 |
| plum.part | UAT-P102 |
| plum.part | UAT-P103 |
| plum.part | UAT-P104 |
| plum.part | UAT-P105 |
| plum.part | UAT-P201 |
| plum.part | UAT-P202 |
| plum.part | UAT-P203 |
| plum.part | UAT-P301 |
| plum.part | UAT-P302 |
| plum.part | UAT-P401 |
| plum.part | UAT-P402 |
| plum.part | UAT-P501 |
| plum.part | UAT-P502 |
| plum.part | UAT-P503 |
| syerp.bill_ref | UAT-BILL-DRAFT |
| syerp.bill_ref | UAT-BILL-POSTED |
| syerp.item | UAT-ITEM-1 |
| syerp.item | UAT-ITEM-10 |
| syerp.item | UAT-ITEM-2 |
| syerp.item | UAT-ITEM-3 |
| syerp.item | UAT-ITEM-4 |
| syerp.item | UAT-ITEM-5 |
| syerp.item | UAT-ITEM-6 |
| syerp.item | UAT-ITEM-7 |
| syerp.item | UAT-ITEM-8 |
| syerp.item | UAT-ITEM-9 |
| syerp.location | UAT-LOC-A |
| syerp.location | UAT-LOC-ARCH |
| syerp.location | UAT-LOC-NOBIN |
| syerp.partner | UAT-CUST-1 |
| syerp.partner | UAT-CUST-2 |
| syerp.partner | UAT-VEND-1 |
| syerp.partner | UAT-VEND-2 |
| syerp.partner | UAT-VEND-ARCH |
| syerp.payment_ref | UAT-BILL-POSTED-PAY-1 |
| syerp.receipt_ref | UAT-SO-2-RCPT-1 |

## derived literals

| label | value |
| --- | --- |
| auth.role.UAT-PLUM-ONLY.permissions | plum:read |
| auth.user.uat-plum-user@example.invalid.full_name | UAT PLUM-only User |
| auth.user.uat-plum-user@example.invalid.is_active | true |
| auth.user.uat-plum-user@example.invalid.password | uat-plum-user-pw |
| auth.user.uat-plum-user@example.invalid.permissions | plum:read |
| auth.user.uat-plum-user@example.invalid.roles | UAT-PLUM-ONLY |
| crumb.interactions.count | 2 |
| crumb.interactions.newest_first | email: UAT-COMM-2 follow-up email with the quote; call: UAT-COMM-1 first contact call |
| crumb.lead.UAT-LEAD-1.company | UAT Prospect Co |
| crumb.lead.UAT-LEAD-1.status | new |
| crumb.opportunity.UAT-OPP-1.estimated_value | 4250 |
| crumb.opportunity.UAT-OPP-1.stage | proposal |
| crumb.opportunity.UAT-OPP-2.estimated_value | 1875 |
| crumb.opportunity.UAT-OPP-2.stage | qualify |
| crumb.quote.accepted.line0 | qty 5 @ 20 markup none = 100 |
| crumb.quote.accepted.quote_number | QUOTE-0002 |
| crumb.quote.accepted.status | accepted |
| crumb.quote.accepted.total_value | 100 |
| crumb.quote.open.line0 | qty 7 @ 38.28 markup 45 = 267.96 |
| crumb.quote.open.line1 | qty 3 @ 18.85 markup 30 = 56.55 |
| crumb.quote.open.quote_number | QUOTE-0001 |
| crumb.quote.open.status | sent |
| crumb.quote.open.total_value | 324.51 |
| crumb.sales_order.line.UAT-ITEM-8 | ordered 11 @ 9.75 reserved 11 shortage 0 |
| crumb.sales_order.so_number | SO-0001 |
| crumb.sales_order.status | confirmed |
| crumb.sales_order.total_value | 107.25 |
| gelato.bin.UAT-BIN-A1.active | true |
| gelato.bin.UAT-BIN-A1.location | UAT-LOC-A |
| gelato.bin.UAT-BIN-A1.onhand.UAT-ITEM-4 | 9 |
| gelato.bin.UAT-BIN-A2.active | true |
| gelato.bin.UAT-BIN-A2.location | UAT-LOC-A |
| gelato.bin.UAT-BIN-A2.onhand.UAT-ITEM-4 | 6 |
| gelato.bin.UAT-BIN-A3.active | false |
| gelato.bin.UAT-BIN-A3.location | UAT-LOC-A |
| gelato.bin.UAT-BIN-A3.onhand.UAT-ITEM-4 | 0 |
| gelato.bin.UAT-BIN-STAGE.active | true |
| gelato.bin.UAT-BIN-STAGE.location | UAT-LOC-A |
| gelato.bin.UAT-BIN-STAGE.onhand.UAT-ITEM-4 | 0 |
| gelato.binned.UAT-LOC-A.UAT-ITEM-5 | UAT-BIN-A1=20 |
| gelato.binned.UAT-LOC-A.UAT-ITEM-8 | UAT-BIN-A2=25 |
| gelato.bins_at.UAT-LOC-A | 4 |
| gelato.bins_at.UAT-LOC-NOBIN | 0 |
| gelato.rollup.UAT-LOC-A.UAT-ITEM-4 | bins 15 + unbinned 0 == location total 15 |
| gelato.unbinned.UAT-LOC-A.UAT-ITEM-1 | 6 |
| gelato.unbinned.UAT-LOC-A.UAT-ITEM-4 | 0 |
| gelato.unbinned.UAT-LOC-NOBIN.UAT-ITEM-4 | 4 |
| mousse.wo.plan2.component_count | 0 |
| mousse.wo.plan2.full_issue_wip_value | n/a — components snapshot at release |
| mousse.wo.plan2.planned_qty | 2 |
| mousse.wo.plan2.status | draft |
| mousse.wo.plan2.target_location | UAT-LOC-NOBIN |
| mousse.wo.plan2.wo_number | WO-000002 |
| mousse.wo.plan4.component.UAT-ITEM-5 | qty_per 2 required 8 |
| mousse.wo.plan4.component.UAT-ITEM-5.pool | unbinned 0 at UAT-LOC-A — bin REQUIRED |
| mousse.wo.plan4.component.UAT-ITEM-6 | qty_per 3 required 12 |
| mousse.wo.plan4.component.UAT-ITEM-6.pool | unbinned 30 at UAT-LOC-A — no bin needed |
| mousse.wo.plan4.component_count | 2 |
| mousse.wo.plan4.full_issue_wip_value | 58 |
| mousse.wo.plan4.planned_qty | 4 |
| mousse.wo.plan4.status | released |
| mousse.wo.plan4.target_location | UAT-LOC-A |
| mousse.wo.plan4.wo_number | WO-000001 |
| plum.avl.UAT-P401.link_count | 0 |
| plum.avl.UAT-P402.UAT-VEND-1.preferred | true |
| plum.avl.UAT-P402.UAT-VEND-1.price_breaks | qty>=1:7.3, qty>=100:6.15 |
| plum.avl.UAT-P402.UAT-VEND-2.preferred | false |
| plum.avl.UAT-P402.UAT-VEND-2.price_breaks | none |
| plum.avl.UAT-P402.link_count | 2 |
| plum.cost.UAT-P104.below_cost | true |
| plum.cost.UAT-P104.bom_rollup_cost | 99.15 |
| plum.cost.UAT-P104.effective_cost | 99.15 |
| plum.cost.UAT-P104.effective_cost_source | roll-up |
| plum.cost.UAT-P104.margin | -59.15 |
| plum.cost.UAT-P104.margin_pct | -59.65708522440746343923348462 |
| plum.cost.UAT-P104.margin_pct_2dp | -59.66 |
| plum.cost.UAT-P104.sale_price | 40 |
| plum.cost.UAT-P402.effective_cost | 6.15 |
| plum.cost.UAT-P402.effective_cost_source | vendor price |
| plum.cost.UAT-P402.margin | 5.85 |
| plum.cost.UAT-P402.material_cost | 9.99 |
| plum.cost.UAT-P402.sale_price | 12 |
| plum.cost.UAT-P402.selected_price_break_index | 1 |
| plum.flat_bom.UAT-P104.UAT-P101.extended_cost | 90.75 |
| plum.flat_bom.UAT-P104.UAT-P101.total_qty | 33 |
| plum.flat_bom.UAT-P104.UAT-P102.extended_cost | 90.75 |
| plum.flat_bom.UAT-P104.UAT-P102.total_qty | 11 |
| plum.flat_bom.UAT-P104.UAT-P103.extended_cost | 49.5 |
| plum.flat_bom.UAT-P104.UAT-P103.total_qty | 3 |
| plum.flat_bom.UAT-P104.UAT-P105.extended_cost | 8.4 |
| plum.flat_bom.UAT-P104.UAT-P105.total_qty | 7 |
| plum.flat_bom.UAT-P104.row_count | 4 |
| plum.part.UAT-P101.revision | A (draft) |
| plum.part.UAT-P102.revision | A (draft) |
| plum.part.UAT-P103.revision | A (draft) |
| plum.part.UAT-P104.revision | A (draft) |
| plum.part.UAT-P105.revision | A (draft) |
| plum.part.UAT-P201.revision | A (draft) |
| plum.part.UAT-P202.revision | A (draft) |
| plum.part.UAT-P203.revision | A (draft) |
| plum.part.UAT-P301.revision | A (released) |
| plum.part.UAT-P302.revision | A (draft) |
| plum.part.UAT-P401.revision | A (draft) |
| plum.part.UAT-P402.revision | A (draft) |
| plum.part.UAT-P501.revision | A (released) |
| plum.part.UAT-P502.revision | A (draft) |
| plum.part.UAT-P503.revision | A (draft) |
| plum.released.UAT-P301.bom_rollup_cost | 26.4 |
| plum.released.UAT-P301.label | A |
| plum.released.UAT-P301.margin | 8.6 |
| plum.released.UAT-P301.released_cost_snapshot | 26.4 |
| plum.released.UAT-P301.sale_price | 35 |
| plum.released.UAT-P301.status | released |
| plum.where_used.UAT-P203.parents | UAT-P202=direct; UAT-P201=indirect via UAT-P202 |
| syerp.ap.bill.draft.bill_number | BILL-0002 |
| syerp.ap.bill.draft.open_balance | 264.5 |
| syerp.ap.bill.draft.paid_amount | 0 |
| syerp.ap.bill.draft.status | draft |
| syerp.ap.bill.draft.total | 264.5 |
| syerp.ap.bill.posted.bill_number | BILL-0001 |
| syerp.ap.bill.posted.open_balance | 57.75 |
| syerp.ap.bill.posted.paid_amount | 36.5 |
| syerp.ap.bill.posted.status | posted |
| syerp.ap.bill.posted.total | 94.25 |
| syerp.ap.payment.allocations | 1 |
| syerp.ap.payment.amount | 36.5 |
| syerp.ar.invoice.invoice_number | INV-0001 |
| syerp.ar.invoice.open_balance | 84.25 |
| syerp.ar.invoice.status | posted |
| syerp.ar.invoice.total | 139.5 |
| syerp.ar.receipt.allocations | 1 |
| syerp.ar.receipt.amount | 55.25 |
| syerp.ar.sales_order.line | ordered 9 shipped 9 invoiced 9 @ 15.5 |
| syerp.ar.sales_order.so_number | SO-0002 |
| syerp.ar.sales_order.status | fulfilling |
| syerp.gl.manual_je.line_count | 2 |
| syerp.gl.manual_je.memo | UAT-JE-1 manual journal entry (professional services accrual) |
| syerp.gl.manual_je.total_credit | 412.75 |
| syerp.gl.manual_je.total_debit | 412.75 |
| syerp.gl.opening_capital.amount | 8250 |
| syerp.gl.opening_capital.memo | UAT-JE-0 opening capital contribution |
| syerp.item.UAT-ITEM-1.active | true |
| syerp.item.UAT-ITEM-1.moving_avg_cost | 6.669231 |
| syerp.item.UAT-ITEM-1.name | UAT PLUM-linked stock item |
| syerp.item.UAT-ITEM-1.onhand.Main | 7 |
| syerp.item.UAT-ITEM-1.onhand.UAT-LOC-A | 6 |
| syerp.item.UAT-ITEM-1.onhand_value | 86.700003 |
| syerp.item.UAT-ITEM-1.plum_linked | true |
| syerp.item.UAT-ITEM-1.total_quantity | 13 |
| syerp.item.UAT-ITEM-10.active | true |
| syerp.item.UAT-ITEM-10.moving_avg_cost | 4.75 |
| syerp.item.UAT-ITEM-10.name | UAT AR-invoiced stock item |
| syerp.item.UAT-ITEM-10.onhand.UAT-LOC-A | 11 |
| syerp.item.UAT-ITEM-10.onhand_value | 52.25 |
| syerp.item.UAT-ITEM-10.plum_linked | false |
| syerp.item.UAT-ITEM-10.total_quantity | 11 |
| syerp.item.UAT-ITEM-2.active | true |
| syerp.item.UAT-ITEM-2.moving_avg_cost | 12.25 |
| syerp.item.UAT-ITEM-2.name | UAT standalone stock item |
| syerp.item.UAT-ITEM-2.onhand.Main | 4 |
| syerp.item.UAT-ITEM-2.onhand_value | 49 |
| syerp.item.UAT-ITEM-2.plum_linked | false |
| syerp.item.UAT-ITEM-2.total_quantity | 4 |
| syerp.item.UAT-ITEM-3.active | false |
| syerp.item.UAT-ITEM-3.moving_avg_cost | 0 |
| syerp.item.UAT-ITEM-3.name | UAT archived stock item |
| syerp.item.UAT-ITEM-3.onhand_value | 0 |
| syerp.item.UAT-ITEM-3.plum_linked | false |
| syerp.item.UAT-ITEM-3.total_quantity | 0 |
| syerp.item.UAT-ITEM-4.active | true |
| syerp.item.UAT-ITEM-4.moving_avg_cost | 3.1 |
| syerp.item.UAT-ITEM-4.name | UAT fully-binned stock item |
| syerp.item.UAT-ITEM-4.onhand.UAT-LOC-A | 15 |
| syerp.item.UAT-ITEM-4.onhand.UAT-LOC-NOBIN | 4 |
| syerp.item.UAT-ITEM-4.onhand_value | 58.9 |
| syerp.item.UAT-ITEM-4.plum_linked | false |
| syerp.item.UAT-ITEM-4.total_quantity | 19 |
| syerp.item.UAT-ITEM-5.active | true |
| syerp.item.UAT-ITEM-5.moving_avg_cost | 5 |
| syerp.item.UAT-ITEM-5.name | UAT MOUSSE component A stock |
| syerp.item.UAT-ITEM-5.onhand.UAT-LOC-A | 20 |
| syerp.item.UAT-ITEM-5.onhand.UAT-LOC-NOBIN | 10 |
| syerp.item.UAT-ITEM-5.onhand_value | 150 |
| syerp.item.UAT-ITEM-5.plum_linked | true |
| syerp.item.UAT-ITEM-5.total_quantity | 30 |
| syerp.item.UAT-ITEM-6.active | true |
| syerp.item.UAT-ITEM-6.moving_avg_cost | 1.5 |
| syerp.item.UAT-ITEM-6.name | UAT MOUSSE component B stock |
| syerp.item.UAT-ITEM-6.onhand.UAT-LOC-A | 30 |
| syerp.item.UAT-ITEM-6.onhand.UAT-LOC-NOBIN | 15 |
| syerp.item.UAT-ITEM-6.onhand_value | 67.5 |
| syerp.item.UAT-ITEM-6.plum_linked | true |
| syerp.item.UAT-ITEM-6.total_quantity | 45 |
| syerp.item.UAT-ITEM-7.active | true |
| syerp.item.UAT-ITEM-7.moving_avg_cost | 0 |
| syerp.item.UAT-ITEM-7.name | UAT MOUSSE finished good |
| syerp.item.UAT-ITEM-7.onhand_value | 0 |
| syerp.item.UAT-ITEM-7.plum_linked | true |
| syerp.item.UAT-ITEM-7.total_quantity | 0 |
| syerp.item.UAT-ITEM-8.active | true |
| syerp.item.UAT-ITEM-8.moving_avg_cost | 6.4 |
| syerp.item.UAT-ITEM-8.name | UAT sellable stock item |
| syerp.item.UAT-ITEM-8.onhand.UAT-LOC-A | 25 |
| syerp.item.UAT-ITEM-8.onhand_value | 160 |
| syerp.item.UAT-ITEM-8.plum_linked | false |
| syerp.item.UAT-ITEM-8.total_quantity | 25 |
| syerp.item.UAT-ITEM-9.active | true |
| syerp.item.UAT-ITEM-9.moving_avg_cost | 7.25 |
| syerp.item.UAT-ITEM-9.name | UAT AP-matched stock item |
| syerp.item.UAT-ITEM-9.onhand.Main | 13 |
| syerp.item.UAT-ITEM-9.onhand_value | 94.25 |
| syerp.item.UAT-ITEM-9.plum_linked | false |
| syerp.item.UAT-ITEM-9.total_quantity | 13 |
| syerp.location.UAT-LOC-A.active | true |
| syerp.location.UAT-LOC-ARCH.active | false |
| syerp.location.UAT-LOC-NOBIN.active | true |
| syerp.partner.UAT-CUST-1.active | true |
| syerp.partner.UAT-CUST-1.name | UAT Customer One |
| syerp.partner.UAT-CUST-1.role | customer |
| syerp.partner.UAT-CUST-2.active | true |
| syerp.partner.UAT-CUST-2.name | UAT Customer Two |
| syerp.partner.UAT-CUST-2.role | customer |
| syerp.partner.UAT-VEND-1.active | true |
| syerp.partner.UAT-VEND-1.name | UAT Vendor One |
| syerp.partner.UAT-VEND-1.role | vendor |
| syerp.partner.UAT-VEND-2.active | true |
| syerp.partner.UAT-VEND-2.name | UAT Vendor Two |
| syerp.partner.UAT-VEND-2.role | vendor |
| syerp.partner.UAT-VEND-ARCH.active | false |
| syerp.partner.UAT-VEND-ARCH.name | UAT Vendor Archived |
| syerp.partner.UAT-VEND-ARCH.role | vendor |
| syerp.po.UAT-PO-APPROVED.line1 | UAT-ITEM-2 ordered=9 @ 8 received=0 |
| syerp.po.UAT-PO-APPROVED.line_count | 1 |
| syerp.po.UAT-PO-APPROVED.outstanding_qty | 9 |
| syerp.po.UAT-PO-APPROVED.po_number | PO-0002 |
| syerp.po.UAT-PO-APPROVED.status | approved |
| syerp.po.UAT-PO-APPROVED.total | 72 |
| syerp.po.UAT-PO-APPROVED.total_ordered_qty | 9 |
| syerp.po.UAT-PO-APPROVED.total_received_qty | 0 |
| syerp.po.UAT-PO-DRAFT.line1 | UAT-ITEM-1 ordered=10 @ 5 received=0 |
| syerp.po.UAT-PO-DRAFT.line2 | UAT-ITEM-2 ordered=3 @ 12 received=0 |
| syerp.po.UAT-PO-DRAFT.line_count | 2 |
| syerp.po.UAT-PO-DRAFT.outstanding_qty | 13 |
| syerp.po.UAT-PO-DRAFT.po_number | PO-0001 |
| syerp.po.UAT-PO-DRAFT.status | draft |
| syerp.po.UAT-PO-DRAFT.total | 86 |
| syerp.po.UAT-PO-DRAFT.total_ordered_qty | 13 |
| syerp.po.UAT-PO-DRAFT.total_received_qty | 0 |
| syerp.report.ap_aging.control_2110 | 57.75 |
| syerp.report.ap_aging.current | 0 |
| syerp.report.ap_aging.d31_60 | 57.75 |
| syerp.report.ap_aging.d61_90 | 0 |
| syerp.report.ap_aging.d90_plus | 0 |
| syerp.report.ap_aging.in_balance | true |
| syerp.report.ap_aging.total | 57.75 |
| syerp.report.ar_aging.control_1120 | 84.25 |
| syerp.report.ar_aging.current | 0 |
| syerp.report.ar_aging.d31_60 | 0 |
| syerp.report.ar_aging.d61_90 | 84.25 |
| syerp.report.ar_aging.d90_plus | 0 |
| syerp.report.ar_aging.in_balance | true |
| syerp.report.ar_aging.total | 84.25 |
| syerp.report.balance_sheet.in_balance | true |
| syerp.report.balance_sheet.total_assets | 7991.75 |
| syerp.report.balance_sheet.total_equity | 7934 |
| syerp.report.balance_sheet.total_liabilities | 57.75 |
| syerp.report.income_statement.net_income | -316 |
| syerp.report.income_statement.total_expense | 455.5 |
| syerp.report.income_statement.total_revenue | 139.5 |
| syerp.report.income_statement.window_days | 365 |
| syerp.report.trial_balance.in_balance | true |
| syerp.report.trial_balance.net | 0 |
| syerp.report.trial_balance.row_count | 9 |
| syerp.report.trial_balance.total_credit | 8447.25 |
| syerp.report.trial_balance.total_debit | 8447.25 |
```

### Task 16 — runbook command execution log

Every command `.zj/UAT-v4.0.md` §1 asks the owner to run, executed in order **from a clean
shell** (`env -i`, `env | grep -c POSTGRES` → `0`) against a genuinely fresh volume, copy-pasted
exactly as the doc printed it. The Phase-03 keeper: a recipe derived by reading is not a
runnable recipe.

**Three doc bugs found and corrected. One was a real, reproducible failure.**

#### 1. `down -v` — destroy the volume

```
$ podman-compose -f compose/compose.yml -f compose/compose.dev.yml down -v
podman volume rm compose_pgdata
exit=0
```

#### 2. `up -d` — bring the stack up

```
$ podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d
ba34e49ef129… exit code: 0     (db)
a5717a5dd4aa… exit code: 0     (frontend)
9693060c58cb… exit code: 0     (api)
```

#### 3. 🔴 **BUG 1 — the health check as written FAILED**

The doc said *"Wait for ready (a few seconds), then confirm the schema is at head"* — as
**prose** — and then printed a bare `curl`. Run as an owner would (paste the block), it fails:

```
$ curl -sS http://localhost:8000/health/ready
curl: (56) Recv failure: Connection reset by peer          [exit=56]
```

The entrypoint is still waiting on Postgres and running `alembic upgrade head`. The window is
only a few seconds, but an owner pasting the block gets a connection error and reasonably
concludes the stack is broken. **A prose "wait a few seconds" is not a command.**

**Fixed** by giving an actual wait, and by documenting the error so it reads as "not yet"
rather than "broken":

```bash
until curl -sf -o /dev/null http://localhost:8000/health/ready; do sleep 2; done
```

#### 4. Health + schema, once actually ready

```
$ curl -sS http://localhost:8000/health/ready
{"status":"ok","db":"connected"}

$ podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && alembic current'
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
0017 (head)
```

**BUG 3 (cosmetic):** the doc's inline comment implied clean output. `alembic current` emits
two `INFO` lines first. The doc now shows the real three-line output and says the INFO lines
are normal.

#### 5. 🔴 **BUG 2 — the seed is ~5 s, not ~40 s**

```
$ podman exec -e PYTHONPATH=/app compose_api_1 python scripts/seed_uat_fixtures.py
mode: seed + manifest; layers: core+partners, plum, syerp-inventory+purchasing, gelato-bins, mousse+crumb, syerp-gl+ap+ar
exit=0 ; elapsed=5s ; 361 lines of manifest on stdout
```

The runbook (and the Task-8 report's Noticed #3) claimed **~40 s** on an empty database.
Measured on a genuinely fresh volume, exercising every create path: **5 s**. The claim was
simply wrong. Both places in the doc corrected, with the error acknowledged in the
"things that look like defects but are not" table so the number is not re-inflated later.

#### 6. **The manifest matches the Task-8 record of truth — byte for byte**

```
$ diff <task-8 manifest of record> <this run's manifest>
(no output)
IDENTICAL — no document number and no aggregate figure changed
```

So `.zj/UAT-v4.0.md`'s literals and `docs/tasks/chore-human-uat.md`'s manifest still agree.
Nothing to reconcile.

#### 7. `--manifest` — the read-only re-read

```
$ podman exec -e PYTHONPATH=/app compose_api_1 python scripts/seed_uat_fixtures.py --manifest
mode: manifest-only (read-only); layers: …
exit=0
$ diff <seed run stdout> <--manifest stdout>
(no output — same output, writes nothing)
```

#### 8. The `C-SC6-d` restore verifier

```
$ podman exec compose_db_1 psql -U app -d biznice -tAc "select key, enabled from modules where key='gelato'"
gelato|t
```

#### 9. `:5173` serves the SPA; `:8000` deliberately does not

```
$ curl -sSf -o /dev/null -w '%{http_code}\n' http://localhost:5173
200
$ curl -sS http://localhost:5173 | head -c 120
<!doctype html><html lang="en"><head><script type="module">import { injectIntoGlobalHook } …
$ curl -sS -o /dev/null -w '%{http_code}\n' http://localhost:8000/
404          ← expected under the dev overlay; now stated in the doc
```

SPA deep links all serve the shell (client-side routed): `/`, `/login`, `/plum/parts`,
`/gelato/bins`, `/no-such-page` → all `200`.

#### 10. Admin login — and the credentials are still where the doc says

Task 8a moved the **database** keys into `.env.db`; the **admin** keys were checked to be
still in `.env`, which is what §1.2 tells the owner:

```
keys in .env    : POSTGRES_HOST POSTGRES_PORT DEBUG JWT_SECRET BNS_ADMIN_EMAIL BNS_ADMIN_PASSWORD
keys in .env.db : POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD
BNS_ADMIN_EMAIL = admin@example.com   ← matches the default the doc quotes

$ POST /api/v1/auth/login  (form-encoded username/password from .env)   -> HTTP 200
  token_type: bearer | access_token length: 411
$ GET  /api/v1/auth/me                                                  -> 200
  email: admin@example.com | roles: ['admin'] | wildcard: True
```

**And through the browser's own path** — `:5173` serving 200 does not prove login works from
the browser, which needs the Vite `/api` proxy:

```
$ POST http://localhost:5173/api/v1/auth/login   -> HTTP 200  {"access_token":"eyJhbGci…
$ GET  http://localhost:5173/api/v1/core/modules -> HTTP 401  (correctly rejects no auth)
```

#### 11. The corrected block, re-run verbatim end-to-end

The whole of §1.1 as **now written**, pasted into one clean shell against another fresh volume:

```
{"status":"ok","db":"connected"}
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
0017 (head)
mode: seed + manifest; layers: core+partners, plum, syerp-inventory+purchasing, gelato-bins, mousse+crumb, syerp-gl+ap+ar
seed exit=0 ; manifest lines=361
TOTAL elapsed: 29s          (down -v + up -d + wait + migrate + seed)
$ diff <task-8 record> <this manifest>   → identical
```

**Final state — left up and seeded for Task 18:**

```
compose_db_1=Up (healthy)  compose_frontend_1=Up  compose_api_1=Up
:5173 → 200   /health/ready → {"status":"ok","db":"connected"}   admin login via proxy → 200
```

**Whole-runbook bring-up is ~30 s**, not the several minutes the old wording implied.

### Task 19 — scenario (G) RED signature

*(pending)*

### Task 33 — full regression gate results

*(pending)*
