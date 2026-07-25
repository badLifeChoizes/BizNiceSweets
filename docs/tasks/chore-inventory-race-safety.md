# Task: chore-inventory-race-safety

**Branch:** `chore-inventory-race-safety` (cut off `7a71fd0`, plan-carrying tip code-identical to `db725fd` — D-P4-4)
**Phase:** v4.0 Phase 4 — Inventory ledger race-safety (NFR-7)
**Plan:** `.zj/phases/04-inventory-race-safety/PLAN.md`

Every floor-guarded inventory-ledger write serializes on the shared sorted-id
`SELECT … FOR UPDATE` discipline, and the three remaining bin-blind draw primitives
(`post_adjustment`, `post_transfer`, MOUSSE `issue_components`) become bin-aware
(explicit-or-unbinned, D-P4-1).

## Checklist

- [x] 0. Cut branch and checklist
- [x] 1. Serialize the three unlocked inventory.py writers on the item-master lock (SC1)
- [x] 2. Serialize receive_line on the PO-header lock (SC1)
- [x] 3. Make post_adjustment bin-aware, wired schema→router (SC3)
- [x] 4. Make post_transfer bin-aware (from_bin_id), wired schema→router (SC3)
- [x] 5. Make MOUSSE issue_components bin-aware, wired schema→router (SC3)
- [x] 6. Truth-up the bin trust-boundary documentation (SC3 closure)
- [x] 7. Write verify_inventory_race.py — mixed-path concurrency, mutation-proven (SC2, SC1)
- [x] 8. Revise verify_gelato.py scenario (E) to assert the fix (SC3)
- [ ] 9. Behavior-change regression sweep — reconcile every breakage (SC5)
- [ ] 10. FE: bin picker on StockAdjustDialog + Vitest payload assertion (SC4)
- [ ] 11. FE: from-bin picker on StockTransferDialog + Vitest payload assertion (SC4)
- [ ] 12. FE: per-line bin picker on IssueComponentsDialog + Vitest payload assertion (SC4)
- [ ] 13. Full-gate run + bookkeeping (SC5, SC6)

## Mutation-proof record (Task 7 — fill during build)

| # | Lock removed (revert) | RED observed | GREEN restored |
|---|---|---|---|
| M1 | Task-1 lock in `post_adjustment` | (A) both writers succeeded, on-hand driven to −4 (loc and pool) at iter 0 — MOUSSE's own lock could not save it; (B) collaterally breached too (−4, shares the adjust path) | (A) exactly one 422, on-hand 3; all 5 scenarios PASS, exit 0 |
| M2 | Task-1 lock in `post_transfer` | (B) both writers succeeded, source on-hand −4 (loc and pool) at iter 0; (A)/(C)/(D) stayed green (mutation isolated) | (B) exactly one 422, source on-hand 3; exit 0 |
| M3 | Task-2 PO lock in `receive_line` (`for_update=True` → `False`) | (C) BOTH receives succeeded (successes=2, no 422) at iter 0: 14 units + two GL posts landed against an order of 10, while the `qty_received` accumulator itself lost an update (read 7, not 14) | (C) exactly one success + one over-receipt 422, qty_received 7 ≤ 10, ONE receipt txn; exit 0 |
| M4 | Task-1 lock in `post_receipt` | Lock ALONE removed (refresh kept): (D) RED at iter 0 — moving_avg_cost 10.000000 instead of 9.583333 (lost update; on-hand still 12). Lock + refresh both removed: identical RED signature. Documented: the lock alone was sufficient to go RED; refresh without the lock cannot serialize | (D) both receipts succeed, final avg 9.583333 == 115/12 exactly; exit 0 |

## Task-9 reconciliation log

<!-- every breakage classified (a) D-P4-1 intended change vs (b) regression -->
