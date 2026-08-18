# Task: chore-port-verify-cruxes (v4.0 Phase 2b)

Port the DoD-named `verify_*` cruxes into the repaired pytest suite (NFR-5, 2b half of the
D-P2a-2 split) so reverting a crux turns a *pytest* test RED — not only a `verify_*` script.
TEST-ONLY phase: zero `backend/app/` change expected.

Plan: `.zj/phases/02b-port-verify-cruxes/PLAN.md`

## Checklist

- [x] 0. Cut branch `chore-port-verify-cruxes` and open this checklist
- [x] 1. Scaffold new packages (mousse/crumb/gelato) + shared `seeded_ledger_db` fixture (`521648f`)
- [x] 2. Port inventory moving-average SERVICE crux (SC1a) — `tests/syerp/test_inventory_service.py` (`6a50420`)
- [x] 3. Port GL posting-ties crux (SC1b) — `tests/syerp/test_gl_posting.py` (`0ae185b`)
- [x] 4. Port AP posting-ties crux incl. GR/IR-clears-to-zero (SC1c) — `tests/syerp/test_ap_posting.py` (`0777467`)
- [x] 5. Port AR posting-ties crux incl. aging↔1120 tie-out (SC1d) — `tests/syerp/test_ar.py` (`e589bbd`)
- [x] 6. Port MOUSSE WIP-clears crux (SC1e) — `tests/mousse/test_work_orders.py` (`0335fb0`)
- [x] 7. Port CRUMB reservation crux (SC1f) — `tests/crumb/test_sales_orders.py` (`6a63194`)
- [x] 8. Port GELATO ship-COGS crux (SC1g) — `tests/gelato/test_shipments.py` (`e7fcb3a`)
- [x] 9. MOUSSE HTTP audit/RBAC test (SC3) — `tests/mousse/test_api.py` (`6241fa3`)
- [x] 10. CRUMB HTTP audit/RBAC test (SC3) — `tests/crumb/test_api.py` (`beff018`)
- [x] 11. GELATO HTTP audit/RBAC test (SC3) — `tests/gelato/test_api.py` (`0cadde4`)
- [x] 12. AR HTTP audit/RBAC test (SC3) — `tests/syerp/test_ar_api.py` (`8cde0fe`)
- [x] 13. Confirm/add inventory audit/RBAC HTTP test (SC3) — `tests/syerp/test_inventory_api.py` (`13a27cf`, new — no prior HTTP coverage found)
- [x] 14. Prove non-vacuity per crux (SC2) — 7 mutations each flip a NAMED pytest RED, revert green (transient product mutations, all reverted; `git diff -- backend/app/` empty)
- [x] 15. Full-suite regression + verify_* still-green + selfcheck (SC4 + SC5) — suite 232 passed ×2 (0 skipped), 23/23 verify_*, ruff exit 0 (fixed I001 `56ae777`), cold boot ok, `backend/app/` clean
- [x] 16. Drop the SRD caveats + update requirements-progress + record D-P2b (SC6)

## Non-vacuity table (Task 14)

Method: one crux at a time against the in-container shared test DB (never two pytest
processes at once). For each — confirm `git diff -- backend/app/` empty, apply a minimal
semantically-wrong-but-runnable mutation, run ONLY the named test and capture the failing
assertion, `git checkout --` the file, re-run and confirm green. All mutations reverted;
final `git diff --stat -- backend/app/` is empty (SC5).

| Crux | File + mutation | RED test name | Failing-assertion evidence | Revert → green |
|---|---|---|---|---|
| inventory | `syerp/service/inventory.py` — in `compute_new_moving_avg`, general branch returns `avg_before` instead of the weighted `(qty_before*avg_before + qty_recv*unit_cost)/(qty_before+qty_recv)` | `tests/syerp/test_inventory_service.py::test_moving_average_service_crux` | `test_inventory_service.py:76` — `AssertionError: assert Decimal('2.000000') == Decimal('3.000000')` (moving_avg stuck at first cost) | ✅ 1 passed after revert |
| GL | `syerp/service/purchasing.py` — in `receive_line`, gate the receipt auto-post with `if False:` (JE never posts) | `tests/syerp/test_gl_posting.py::test_gl_posting_ties_crux` | `test_gl_posting.py:228` — `assert 0 == 1` (where `0 = len([])`, no `po_receipt` JE found) | ✅ 1 passed after revert |
| AP | `syerp/service/bills.py` — in `post_bill`, resolve the matched-line debit account as `1110` (Cash) instead of `2150` GR/IR (kept a real account so the JE stays balanced and the test's GR/IR-leg assertion, not an unbalance error, fails) | `tests/syerp/test_ap_posting.py::test_ap_posting_ties_crux` | `test_ap_posting.py:176` — `assert (None is not None)` (no Dr 2150 GR/IR leg on the bill JE) | ✅ 1 passed after revert |
| AR | `syerp/service/ar.py` — in `record_receipt`, credit `4110` (Revenue) instead of `1120` AR (real account, JE still balances but 1120 control no longer falls with the receipt) | `tests/syerp/test_ar.py::test_ar_posting_ties_crux` | `test_ar.py:348` — STAGE 2 aging↔1120 tie: `AssertionError: assert Decimal('100.000000') == Decimal('160.000000')` (aging fell to 100, control stuck at 160) | ✅ 1 passed after revert |
| MOUSSE | `mousse/service.py` — in `complete_work_order`, credit 1140 by `receipt_value` (planned_qty×fg_unit_cost) instead of the exact `accumulated_wip`, and drop the 5190 residual legs so the JE stays balanced | `tests/mousse/test_work_orders.py::test_under_issue_override_clears_wip_and_ties_subledger` (the even-dividing happy-path `test_wip_clears_to_zero_crux` is vacuous for this mutation and stayed green — the residual case is the true catcher) | `test_work_orders.py:391` — `AssertionError: assert Decimal('0.000001') == Decimal('0')` (sub-quantum WIP residual stranded in 1140) | ✅ 2 passed after revert (both MOUSSE cruxes) |
| CRUMB | `crumb/service/sales_orders.py` — in `confirm_sales_order`, set `take = line.qty_ordered` instead of `min(qty_ordered, available)` | `tests/crumb/test_sales_orders.py::test_reservation_math_crux` | `test_sales_orders.py:200` — `AssertionError: assert Decimal('8.000000') == Decimal('4')` (reserved the full 8, cap not engaged) | ✅ 1 passed after revert |
| GELATO | `gelato/service/shipments.py` — in `execute_ship`, accumulate `total_value += line.qty * so_line.unit_price` (sales price) instead of `line_value` (qty×moving_avg from post_issue) | `tests/gelato/test_shipments.py::test_gelato_ship_cogs_crux` | `test_shipments.py:355` — `AssertionError: assert Decimal('160.000000') == Decimal('60.000000')` (COGS valued at 8×20 price, not 8×7.5 avg) | ✅ 1 passed after revert |

Final: `git diff --stat -- backend/app/` empty — every mutation reverted (SC5).

## Deviations

- **Task 0 branch point:** plan Task 0 names `f97b21a`, but PLAN.md was committed in the
  later plan-doc commit `3f71900` (the actual current tip). Cut off `3f71900` instead so
  PLAN.md travels onto the build branch — honoring the plan's own Context rationale ("cut
  the tip, not the bare tag, so PLAN.md travels"; 12a/12b/13/2a precedent). Trivial.

## Noticed

- **No sequential `verify_*` assertion was intentionally dropped under D-P2b-2.** Only the
  concurrency scenarios (`asyncio.gather`/`Barrier` + `FOR UPDATE`) stayed in the scripts per
  D-P2a-2/D-P2b-1; every *sequential* crux assertion named in the PLAN crux-source map was
  ported. Coverage delta vs the scripts = concurrency-only, as designed.
- **MOUSSE happy-path `test_wip_clears_to_zero_crux` does not independently catch the WIP
  credit-source mutation** — planned_qty 10 / WIP 210 divides evenly (210/10 == 21.000000), so
  the rounded-FG-value credit coincides with the exact-accumulated-WIP credit. The crux's SC2
  regression guard is the sibling residual test `test_under_issue_override_clears_wip_and_ties_subledger`
  (100/3 case), which flips RED on the mutation (per the Task-14 table). File-header docstring
  corrected at verify to point the red-on-revert claim at the (D) test.
