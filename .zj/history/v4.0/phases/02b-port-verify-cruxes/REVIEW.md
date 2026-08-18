# Review: Phase 2b — Port the DoD-named verify_* cruxes into the repaired pytest suite (`3f71900..db0df05`)
Date: 2026-07-24

Scope: TEST-ONLY phase. Verified `git diff 3f71900..HEAD -- backend/app/` is **empty** — SC5
(no product change) holds. 20 new test files + one additive `conftest.py` fixture
(`seeded_ledger_db`) + docs. Existing pure/no-DB tests (`test_ap.py`, `test_gl.py`, …) are
untouched (D-P2b-6). Each ported crux was cross-checked assertion-by-assertion against the
PLAN crux-source map; the SC2 mutation table in `docs/tasks/chore-port-verify-cruxes.md` was
audited for real red-on-revert.

## Findings

### 1. [minor] MOUSSE happy-path WIP-clears test is vacuous for its own advertised regression
- **Where:** `backend/tests/mousse/test_work_orders.py:166-302` (`test_wip_clears_to_zero_crux`)
- **Failure:** The docstring and header comment claim "crediting 1140 by planned_qty ×
  fg_unit_cost instead of the EXACT accumulated WIP … must turn this WIP-clears assertion RED."
  It does not. With planned_qty 10 and accumulated WIP 210, `210/10 == 21.000000` divides
  evenly, so the rounded-FG-value credit equals the exact accumulated-WIP credit and
  `wip_post_complete == 0` stays green. The team's own SC2 table confirms this: the documented
  mutation left this test GREEN and only `test_under_issue_override_clears_wip_and_ties_subledger`
  (the 100/3 residual case) flipped RED. So this test provides no independent regression
  protection for the WIP-clearing credit-source logic it names.
- **Fix:** The crux IS protected by the sibling residual test, so no coverage gap remains —
  but correct the docstring to point the red-on-revert claim at the residual test, or give this
  test a non-evenly-dividing planned_qty so it actually catches the mutation it advertises.

## Questions
- `docs/tasks/chore-port-verify-cruxes.md` `## Noticed` was left as the placeholder
  "(populate during Wave A/B)". PLAN required recording any *sequential* verify_* assertion
  intentionally dropped under D-P2b-2 so the coverage delta is explicit. None is recorded —
  either nothing was dropped (plausible; the ports are faithful) or the delta went undocumented.
  Not a test-correctness defect; worth a one-line confirmation.

## Assessment
The deliverable is strong. Every headline Decimal invariant in the crux-source map is asserted
against an **independent oracle** and anchored to a **literal** so it cannot be self-fulfilling:
inventory `moving_avg == 3.000000` via the service path (not the helper); GL receipt JE Dr 1130
/ Cr 2150 both legs `== 20.000000`; AP GR/IR `grir_post == grir_pre` Decimal-exact + 2110 ↔ bill
subledger `== -55`; AR aging `grand_total == derive_account_balance(1120)` tied at three
settlement stages (aging from Invoice rows, control from JournalLine rows — genuinely
independent); MOUSSE 1140 clears to 0 + 1130 debit `== 99.999999` with the 5190 residual tie;
CRUMB `min(8,4)==4` cap with shortage 4 and the `on_hand − Σ open` formula; GELATO COGS Dr 5100
== Cr 1130 `== 60.000000` + Δ1130 == Δsubledger `== -80.000000`. Negative paths (422 +
persists-nothing) are asserted with row-count guards. The four HTTP RBAC tests get genuine 403s
from real limited DB users (reader/noperm), 401 only for no-token, and assert AuditLog
attribution (actor_id/action/target_type/target_id) — not mere existence. D-P2b-5 is honored:
`test_ar.py` and `test_ar_api.py` drive the REAL execute_pick/pack/ship flow rather than
hand-stamping qty_shipped/COGS. The CRUMB pollution risk (`_isolate` not truncating
crumb_lead/crumb_opportunity) is deliberately avoided — no test creates leads/opportunities.
The SC2 table documents a real red-on-revert per crux.
