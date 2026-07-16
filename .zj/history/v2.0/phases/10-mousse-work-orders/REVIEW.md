# Review: Phase 10 — MOUSSE work orders (d9da607..c263d90)
Date: 2026-07-14
Scope: syerp service/ AST split (6293c96 + 3d59068), MOUSSE module (models/schemas/service/router/__init__), alembic 0012, auth seed perms, verify_mousse[_api], frontend routes/mousse/.

## Summary
The diff is substantially clean. The AST split is intact (verified below), the WIP-clearing
invariant holds Decimal-exactly, the FSM admits no stranded-WIP path, the issue-vs-issue
concurrency lock is sound, cross-module imports all resolve, FK column types match their
referenced PKs, and every mutation is RBAC-gated with audit written after the service commit.
No blocker or major defects found. One minor accounting-reconciliation drift and two questions.

## AST-split verification (the class of bug that already bit once)
Reconstructed `6293c96^:service.py` and diffed all module-level constructs against the new
package. Result: **no other silently dropped names.**
- 89 top-level defs/classes in old == 89 across the new submodules (set-equal, none missing).
- Every old def name appears in `service/__init__.py` re-exports.
- All module-level `Assign` constants preserved: `_ITEM_CODE_RE` (items.py:59), `_COST_QUANTUM`
  (_common.py:18), `_PO_NUMBER_RE` (purchasing.py:71), `_BILL_NUMBER_RE` (bills.py:77).
- Both `AnnAssign` maps preserved and now re-exported after 3d59068: `PO_TRANSITIONS`
  (purchasing.py:483), `BILL_TRANSITIONS` (bills.py:146).
- The module-level `if TYPE_CHECKING:` block was re-created per submodule (not dropped).
- Runtime smoke test: `from app.modules.syerp.service import (_COST_QUANTUM,
  _adjustment_violates_floor, _gl_account_id_by_code, post_journal_entry, post_receipt,
  PO_TRANSITIONS, BILL_TRANSITIONS)` and `import app.modules.mousse.{service,router}` all import
  clean. MOUSSE is wired into `main.py:81` and `core/models.py:29`.

## Findings

### 1. [minor] Completion strands a sub-cent 1130-GL vs inventory-subledger discrepancy; the docstring claims it is "absorbed" when it is not
- **Where:** `backend/app/modules/mousse/service.py:854-914` (complete_work_order costing + receipt/JE); docstring lines 850-858.
- **Failure:** accumulated_wip=100, planned_qty=3 (verify_mousse scenario D2). `fg_unit_cost =
  quantize(100/3) = 33.333333`. The clearing JE debits **1130 by exactly 100** (accumulated_wip),
  but `post_receipt` values the FG receipt InventoryTxn at `planned_qty × fg_unit_cost =
  3 × 33.333333 = 99.999999` and moves the item's moving-average by that amount. After
  completion the 1130 control account (GL) exceeds the perpetual-inventory valuation
  (Σ on_hand × moving_avg) by 0.000001. The residual is **not** "absorbed into the moving-average
  receipt" as the docstring states — it becomes a permanent GL-to-subledger break on the
  inventory control account, recurring on every WO whose WIP is not evenly divisible by
  planned_qty. 1140 does clear to zero exactly (the stated Phase-10 invariant holds), and the
  trial balance still nets zero (both are Σdebit==Σcredit properties, which don't detect a
  control-account/subledger mismatch), so verify_mousse does not catch it. Given the
  medical-device audit/traceability posture, control-account reconciliation is a real concern.
- **Fix:** Either debit 1130 by `planned_qty × fg_unit_cost` and credit 1140 by the same, then
  book the residual (accumulated_wip − planned_qty×fg_unit_cost) to a rounding/variance account
  so 1140 still clears exactly AND 1130 ties to the subledger; or, at minimum, correct the
  docstring to state the residual lands as a 1130 GL/subledger difference, not in the moving
  average. (Same class of drift exists on fractional-quantity issues at service.py:712, where the
  JE credits `quantize(qty×moving_avg)` while the txn reduces stock by the unrounded product.)

## Questions

- **Issue lock only serializes issue-vs-issue, not issue-vs-adjustment.** `issue_components`
  takes `InventoryItem ... FOR UPDATE` (service.py:679-685), but SYERP `post_adjustment`
  (inventory.py:384-411) and `post_receipt` (inventory.py:276-293) read the on-hand SUM and
  write **without** locking the item row. Two concurrent transactions — a MOUSSE issue of -10 and
  a SYERP negative adjustment of -10 against the same item/location starting from on-hand 10 —
  can both pass their floor guards and drive derived on-hand to -10. The phase's own claim ("two
  concurrent issues can never overdraw") is honored, but the broader floor guarantee is not.
  Is this an accepted pre-existing SYERP limitation, or should the floor-guarded paths share a
  common lock?

- **A legitimately zero-cost component can never be issued on its own.** When an issued line's
  moving_avg_cost is 0 and it is the only line, `total_value <= 0` rejects the whole issue 422
  (service.py:731-738), so the component's stock is never consumed and it stays under-issued —
  forcing an `override_incomplete` at completion for a genuinely free/nominal part. Documented as
  intentional ("no GL meaning"), but is that the desired operator experience?

---

## Resolution (manager, /zj:verify 10, 2026-07-16)

- **Finding #1 (1130 vs subledger drift) — FIXED `5cffeeb`, raised to MAJOR.** Owner chose the
  rounding-sink remedy: completion now posts a 3-line JE routing the sub-quantum residual to a new
  seeded **5190 Inventory Rounding** account, so 1140 clears to zero AND 1130 ties to the inventory
  subledger, both Decimal-exact. D-P10-2 amended. Pinned by `verify_mousse.py` scenario D (1130 debit
  == FG receipt value; 5190 == residual). Full regression re-run: 13/13 verify_* exit 0.
- **AST-split verification — no action needed.** Confirmed clean by reconstruction diff.
- **Zero-cost lone-component question** logged to PLAN `## Noticed` as a deferred minor (the override
  path handles it; free/nominal parts are unusual). Revisit if it bites a real workflow.
