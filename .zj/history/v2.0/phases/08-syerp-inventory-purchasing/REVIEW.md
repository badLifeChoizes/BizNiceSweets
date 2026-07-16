# Review: Phase 08 — SYERP Extended: inventory & purchasing (`b5c5c31~1..e1b7f84`)
Date: 2026-07-08

Scope reviewed: backend `syerp/{models,schemas,service,router}.py`, migrations 0007/0008,
frontend inventory + purchasing screens/dialogs. Focus per task brief: moving-average recompute,
negative-stock guards, PO receiving atomicity, FSM, numeric generators, RBAC/audit, migrations,
frontend 4xx/array handling.

## Findings

### 1. [major] `create_item` / `update_item` 500 on a non-existent `plum_part_id`; retry logic misclassifies the FK error
- **Where:** `backend/app/modules/syerp/service.py:497-542` (`create_item`), `602-625` (`update_item`); `plum_part_id` FK declared `models.py:177-179`, enforced in migration `0007_syerp_inventory.py:100-104`.
- **Failure:** POST `/syerp/inventory/items` with `{"name":"x","unit_of_measure":"ea","plum_part_id":"<id not in plum_part>"}` (auto code, so `user_supplied_code=False`). The first `await db.flush()` raises `IntegrityError` — but from the **FK** violation, not a code collision. The `except IntegrityError` branch treats it as an auto-code race: it rolls back, regenerates the code, re-adds the row with the *same* bad `plum_part_id`, and flushes again. The second flush raises the identical FK `IntegrityError`, now **unhandled**, surfacing as HTTP 500. `update_item` has no try/except at all, so PATCHing an item's `plum_part_id` to a bad value also 500s on commit. Reachable via a stale/deleted part id from the picker, PLUM disabled with a cached id, or any direct API caller — exactly the "PLUM link is advisory, must degrade" case D-P8-2 exists to protect. `add_line` avoids this by pre-validating `item_id` via `get_item` (service.py:1482); the item's own FK is the one input that is never existence-checked.
- **Fix:** Before insert/update, if `data.plum_part_id` is not None, verify the part exists (or that PLUM is enabled) and reject with 404/422; and/or distinguish the FK violation from the unique-code collision in the `except` (inspect `err.orig` / constraint name) so a non-code error is not "retried" with a fresh code that cannot fix it.

## Questions / accepted-risk confirmations

- **Concurrency windows are genuinely windows, not single-threaded logic bugs (confirmed).** The moving-average read-modify-write (`post_receipt` reads `SUM(quantity)` then writes `moving_avg_cost`, service.py:862-880), the over-receipt guard (`receive_line` reads `line.qty_received` then increments, service.py:1750-1772), and the negative-stock guards (`post_adjustment`/`post_transfer` read per-location SUM then insert) each read-check-write without a row lock. Single-threaded every path is correct (verified: `qty_before` excludes the in-flight txn; boundaries are exact Decimal; first-receipt `qty_before==0` short-circuits div-by-zero). Under concurrent writers the last-writer-wins average *drifts* (self-healing on next receipt) but — worth an explicit owner note — the over-receipt and negative-stock races can breach the two hard invariants this phase is built to guarantee (`qty_received > qty_ordered`, per-location on-hand `< 0`). The plan accepts this for single-shop (Risk #4). No code change requested; flagging that "no negative stock / no over-receipt" is not enforced under concurrency, only under serialized access.

- **Audit rows are written in a separate transaction after the mutation commits.** Every service mutation commits, then the router calls `write_audit`, which does its own `db.commit()` (`auth/service.py:342`). So a process death (or a `write_audit` failure) between the two commits persists the mutation with no audit row. This is the inherited Phase-4 pattern, consistent across the module, and `expire_on_commit=False` (`core/db.py:19`) keeps the returned ORM objects serializable — so it is not a new defect. Noting only because traceability is a first-class, medical-device-origin concern: if strict audit-with-mutation atomicity is desired, the audit insert should share the mutation's transaction (pass `commit=False`-style through, single commit).

## Verified clean

- **Moving-average** (`compute_new_moving_avg`, service.py:773-801): item-level `qty_before` = SUM over ALL locations (no location filter, 862-864), quantized scale-6 `ROUND_HALF_UP`, first-receipt guard correct, all Decimal.
- **Negative-stock / transfer** (`post_adjustment` 934-1013, `post_transfer` 1036-1162): per-location floor correct (`current + delta < 0`), boundary-to-zero allowed, guards reject before any write, transfer writes exactly two legs sharing a fresh `transfer_group_id` netting to zero, average untouched.
- **PO receiving** (`receive_line` 1686-1783): guard order (status → qty>0 → over-receipt) all reject before mutation; over-receipt boundary `==` allowed; `post_receipt(commit=False)` + `qty_received` increment + status roll-up share one commit; roll-up (`_po_rollup_status`) uses Decimal `>=` across all lines.
- **FSM** (`PO_TRANSITIONS`, `advance_po_status` 1587-1638): illegal transitions 422; `_require_draft` enforced on add/update/remove line (service.py:1480,1543,1568).
- **Generators** (`_next_item_code` 428-448, `_next_po_number` 1178-1200): regex-filter then integer-cast ordering, numeric not lexicographic, digit-boundary correct; DB unique constraint + retry-once is the real guard.
- **RBAC + audit coverage:** every mutating endpoint gated `syerp:write`, every read `syerp:read`, `write_audit` after each mutation — full coverage across all 17 mutating endpoints.
- **Migrations 0007/0008:** chain 0006→0007→0008; FK/unique/index present; downgrades drop child-before-parent; all money/qty `Numeric(18,6)`, no Float.
- **Frontend:** dialogs default `locations`/options to `[]`, `getApiErrorMessage` handles array `detail`, 422 surfaces `toast.error` and keeps dialog open (only `onSuccess` closes); PLUM part Select degrades to empty when `/plum/parts` is empty/disabled; PO create's non-atomic header-then-lines flow routes to the created Draft on partial failure (deliberate, not data loss).
