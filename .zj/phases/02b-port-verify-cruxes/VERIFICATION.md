# Verification: Phase 02b — Port the DoD-named verify_* cruxes into the repaired pytest suite (NFR-5)
Date: 2026-07-24 | Commits: 3f71900..db0df05 (branch chore-port-verify-cruxes, 18 commits)
Verdict: PASS

All work verified empirically in-container against the running compose stack
(`compose_api_1`, `compose_db_1` healthy). TEST-ONLY constraint holds: `git diff
3f71900..HEAD -- backend/app/` is empty and the working tree has no `backend/app/`
change. All 16 changed files are under `backend/tests/` (3906 insertions).

## Criteria

### SC1 — the 7 cruxes present, wired, and green in pytest (0 skips) — PASS
Read every crux body; each asserts the HEADLINE Decimal from its source `verify_*` script
via the REAL service path, not a vacuous stand-in.

| Crux | Truth (headline assert) | Exists | Wired | Works | Evidence |
|---|---|---|---|---|---|
| inventory moving-avg | `item.moving_avg_cost == Decimal("3.000000")` via `post_receipt` (service path, not the pure helper) | ✓ | ✓ (service `post_receipt`/`get_item`/`get_item_onhand`/`post_adjustment`/`post_transfer`) | ✓ | `test_inventory_service.py:76,85` + reject (no row) + transfer avg-unchanged |
| GL ties | receipt auto-post ONE `po_receipt` JE Dr 1130 / Cr 2150 == `20.000000`, both legs | ✓ | ✓ (`receive_line`, `post_journal_entry`, `derive_account_balance`, `get_account_register`) | ✓ | `test_gl_posting.py:228,235,236,242,243`; balanced/unbalanced-422, register [10,30,60], reversal |
| AP ties | GR/IR crux `grir_post == grir_pre` (Decimal-exact); AP control ↔ subledger `subledger_open == 55` | ✓ | ✓ (`create_bill`/`post_bill`/`record_payment`) | ✓ | `test_ap_posting.py:199,250` + payment legs + overpay-422 |
| AR ties | aging `grand_total == control` at STAGE 1/2/3 Decimal-exact vs debit-normal 1120 | ✓ | ✓ (drives REAL ship flow → `create_invoice`/`post_invoice`/`record_receipt`, D-P2b-5) | ✓ | `test_ar.py:286,327,348,368`; over-invoice/over-receipt 422 |
| MOUSSE WIP-clears | `wip_post == wip_pre == Decimal("0")`; 1130 debit == FG receipt `99.999999`; 5190 residual ties | ✓ | ✓ (`issue_components`/`complete_work_order`, override path) | ✓ | `test_work_orders.py:301,391,422,425` |
| CRUMB reservation | `qty_reserved == min(qty, avail) == 4`, non-stock reserves 0, cancel releases | ✓ | ✓ (`confirm_sales_order`/`cancel_sales_order`) | ✓ | `test_sales_orders.py:173,200,201,203,208,216,235` |
| GELATO ship-COGS | one JE Dr 5100 == Cr 1130 == 8×7.5 == `60.000000`; reservation relief; 1130↔subledger move | ✓ | ✓ (REAL `execute_pick`/`pack`/`ship`) | ✓ | `test_shipments.py:337,355,368-371,431,432` |

### SC2 — non-vacuity per crux (red-on-regress) — PASS
Independently re-drove 3 of 7 documented mutations (host edit → run named test in-container →
`git checkout --` revert). Each turned the NAMED pytest test RED; reverted clean:
- inventory: `compute_new_moving_avg` general branch → `avg_before` ⇒ `test_moving_average_service_crux` FAILED (1 failed).
- CRUMB: `confirm_sales_order` `take = line.qty_ordered` ⇒ `test_reservation_math_crux` FAILED (AssertionError).
- GELATO: `execute_ship` value at `so_line.unit_price` ⇒ `test_gelato_ship_cogs_crux` FAILED (AssertionError).
After all three, `git diff -- backend/app/` empty. This corroborates the build's full 7-row
table in `docs/tasks/chore-port-verify-cruxes.md` (the other 4 — GL/AP/AR/MOUSSE — read as
genuine red-on-regress assertions; MOUSSE is honestly flagged: the happy-path
`test_wip_clears_to_zero_crux` is vacuous for the documented mutation, but the residual test
`test_under_issue_override_clears_wip_and_ties_subledger` is the true catcher — verified present and asserting).

### SC3 — new packages + one HTTP audit/RBAC test per new surface — PASS
Packages `tests/mousse`, `tests/crumb`, `tests/gelato` exist (each with `__init__.py` ABOUTME).
All 5 HTTP tests assert the 401/403/2xx triad AND a genuinely attributable `AuditLog` row —
`action`, `actor_id == writer_id`, `target_type`, `target_id` (not a status-only check):
- MOUSSE `work_order.created`/`work_order` (`test_api.py:288-296`); CRUMB `sales_order.created`/`sales_order` (`:252-260`);
  GELATO `shipment.picked`/`shipment` + int-PK→str round-trip guard (`:306-315`); AR `invoice.created`/`invoice` (`:321-329`);
  inventory `inventory.receipt`/`inventory_txn` (`:225-233`, newly added — no prior HTTP coverage found, per Task 13).

### SC4 — full suite GREEN, 0 skipped, back-to-back rerunnable — PASS
`python -m pytest -q` ran twice: **run 1 = 232 passed, 0 skipped (195.46s)**; **run 2 = 232
passed, 0 skipped (193.55s)** — no skips reported either run, isolation holds across reruns.
`tests/test_harness_selfcheck.py` = 2 passed.

### SC5 — scripts & product unchanged — PASS
All 23 `backend/scripts/verify_*.py` exit 0 (`ran 23 verify scripts`, no FAIL lines).
`git diff 3f71900..HEAD -- backend/app/` empty; working tree `backend/app/` clean (re-confirmed
after the SC2 mutations were reverted). `ruff check .` = "All checks passed!" (needs a writable
`RUFF_CACHE_DIR` in-container — environment quirk, not a code issue). Cold `import app.main` = boot-ok.

### SC6 — SRD caveats dropped, docs updated — PASS
`.zj/SRD.md` NFR-5 = **Status: done** with evidence (232 passed/0 skipped ×2, 23/23 verify_*).
Grep for stale `script-only | 2b pending | verify_*-only` on ported modules returns nothing.
`docs/features/requirements-progress.md` NFR-5 row updated to Done with the full ported-crux
commit map. `.zj/DECISIONS.md` records D-P2b-1..6. (Note: the "UI flow UAT pending" caveats
remaining on SYERP-12/MOUSSE-01/CRUMB-01 rows are NFR-8 human-UAT deferrals — a distinct,
still-legitimate concern — not the verify_*-only crux caveat NFR-5 required dropping.)

## Regression protection
| Criterion | Pinned by |
|---|---|
| SC1a inventory moving-avg | `tests/syerp/test_inventory_service.py::test_moving_average_service_crux` |
| SC1b GL ties | `tests/syerp/test_gl_posting.py::test_gl_posting_ties_crux` |
| SC1c AP GR/IR-clears | `tests/syerp/test_ap_posting.py::test_ap_posting_ties_crux` |
| SC1d AR aging↔1120 | `tests/syerp/test_ar.py::test_ar_posting_ties_crux` |
| SC1e MOUSSE WIP-clears | `tests/mousse/test_work_orders.py::{test_wip_clears_to_zero_crux, test_under_issue_override_clears_wip_and_ties_subledger}` |
| SC1f CRUMB reservation | `tests/crumb/test_sales_orders.py::test_reservation_math_crux` |
| SC1g GELATO ship-COGS | `tests/gelato/test_shipments.py::test_gelato_ship_cogs_crux` |
| SC3 audit/RBAC (5 surfaces) | `tests/{mousse,crumb,gelato}/test_api.py`, `tests/syerp/{test_ar_api,test_inventory_api}.py` |
| SC4 zero-silent-skip | `tests/test_harness_selfcheck.py` |
Every criterion is pinned by an automated pytest test — the tests ARE the deliverable. No
feasible-but-missing regression test identified.

## Test suite
- `python -m pytest -q` ×2 → 232 passed, 0 skipped both runs (195.46s / 193.55s).
- `tests/test_harness_selfcheck.py` → 2 passed.
- New-coverage set + all 5 HTTP tests included in the 232.
- 23/23 `verify_*.py` exit 0. `ruff check .` clean. `import app.main` ok.

## Gaps
None (blocker/major/minor). Observations only, no action required for this phase:
- **(minor, cosmetic)** 247 warnings, dominated by `HTTP_422_UNPROCESSABLE_ENTITY`
  Starlette deprecation — pre-existing across the suite, not introduced here.
- **(minor, environment)** `ruff`/`pytest` need a writable cache dir in-container
  (`RUFF_CACHE_DIR=/tmp/...`, `.pytest_cache` Permission denied) — does not affect exit codes.
- **CRUMB FK-cycle TRUNCATE risk (PLAN `## Noticed`) — mitigated, not a gap.** The CRUMB ported
  tests deliberately build sales orders via partner+item, creating NO `crumb_lead`/
  `crumb_opportunity` rows (confirmed `tests/crumb/test_api.py:34-35,153`), so the unresolvable
  FK-cycle that drops those two tables from the TRUNCATE sort cannot pollute across tests. The
  0-skip suite passing twice back-to-back confirms no cross-test pollution.
