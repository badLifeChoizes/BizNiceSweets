# Review: 7a71fd0..3126c48 (Phase 4 — inventory ledger race-safety, NFR-7)
Date: 2026-07-25

Scope reviewed: item-master/PO-header FOR UPDATE locking (T1/T2), bin-aware
draws in post_adjustment / post_transfer / MOUSSE issue_components (D-P4-1),
the three FE bin pickers, both verify scripts, and a broad sweep of every
InventoryTxn writer and every `with_for_update()` site for lock-order cycles.

The core locking work is correct: in all three SYERP writers and receive_line
the lock now precedes every floor/aggregate read; `post_receipt`'s
`db.refresh(item)` correctly defeats the identity-map staleness on
`moving_avg_cost` (a bare `select(...).with_for_update()` of the id column
does not repopulate the mapped object); commit=False callers (receive_line,
GELATO ship/pick) hold the lock to their single commit; all 422 guards fire
before any `db.add`, and rejected requests roll back with zero ledger/GL rows.
Lock ordering across receive_line (PO → item), MOUSSE issue (sorted items),
create_bill (sorted items), confirm-SO (sorted items) and ship_shipment
(shipment → sorted items) is acyclic. FE payloads match the schemas
(`bin_id`/`from_bin_id: null` explicit), both SYERP dialogs reset the bin on
location change, and the degraded-bins path correctly falls back to null.

## Findings

### 1. [major] MOUSSE issue_components dropped its per-location floor guard — a bin-named issue on legacy-desynced data can drive location (and total item) on-hand negative
- **Where:** `backend/app/modules/mousse/service.py:698-748` (guard loop; pool-only since 455cf5c)
- **Failure:** The old guard was location-level (`_component_onhand`); the new one is pool-level
  only (`get_bin_on_hand` keyed `(item, location, bin)`). This same phase deliberately KEPT the
  location floor *alongside* the pool floor in `post_adjustment` and `post_transfer`
  (inventory.py:426-443, 592-611), with the stated rationale "defends legacy data whose per-bin
  split has already desynced from the location total" — but the exact writer that *created* those
  desyncs lost its location floor. Concrete scenario: pre-Phase-4 history at location L —
  putaway of 10 into bin B (bin pool +10), then a bin-blind MOUSSE issue of 10 (bin_id NULL,
  unbinned pool −10). Location total = 0, bin B still reads +10. Post-Phase-4, an operator
  issues 10 from bin B via the new picker: pool guard passes (10−10 = 0 ≥ 0), no location
  guard runs → location on-hand −10, total item on-hand −10 (AC10-6 broken), plus a
  Dr 1140 WIP / Cr 1130 Inventory JE booking value out of stock that does not exist. On clean
  post-Phase-4 data the pool guards imply the location floor (Σ pools ≥ 0), so this only bites
  on legacy rows — which is precisely the case the sibling SYERP functions were hardened for.
  (Same latent exposure exists in pre-existing `post_issue`, but that predates this diff.)
- **Fix:** Restore the location-level accumulate-and-guard next to the pool guard, mirroring
  post_adjustment: a second `base/consumed` map keyed `(item_id, location_id)` checked with
  `_adjustment_violates_floor` before appending each txn.

### 2. [minor] Positive adjustments accept an unvalidated bin_id — first public write path that can strand stock in a foreign-location bin pool
- **Where:** `backend/app/modules/syerp/service/inventory.py:445-470` (positive-delta path takes
  no pool read at all); exposed via `POST /syerp/inventory/items/{id}/adjustments`
- **Failure:** D-P12a-3 (no bin membership validation in SYERP, FK backstop) was safe pre-Phase-4
  because every public bin write went through GELATO, which *does* validate location-membership
  (execute_putaway, pick_for_shipment shipments.py:348-355). The draw side of the new endpoints
  self-guards (a mismatched `(location, bin)` pool reads 0 → 422). But a POSITIVE adjustment
  `{location_id: B, bin_id: 7}` where bin 7 belongs to location A passes the FK (bin exists),
  writes a ledger row at `(B, bin 7)`, and the 10 units then appear in location B's total while
  belonging to no pool GELATO will ever display (B's bin list omits bin 7; B's unbinned pool
  reads 0; bin 7's on-hand is computed against location A). Stock is stranded/invisible until
  someone manually posts a negative adjustment naming the same mismatched pair. The FE dialogs
  prevent it (bin resets on location change), but any API caller with a stale bin id hits it.
- **Fix:** On a non-null bin_id, one cheap raw-SQL existence+membership check against
  `gelato_bin (id, location_id)` (no model import, so D-P12a-3's no-gelato-imports rule holds),
  422 on mismatch — or an explicit decision entry accepting stranded-positive-adjustment stock.

### 3. [minor] post_transfer stamps both legs with a moving_avg_cost read before the lock — a racing receipt writes a stale unit_cost into the audit ledger
- **Where:** `backend/app/modules/syerp/service/inventory.py:580` (get_item) vs :588-590 (lock)
  vs :629 (`unit_cost = item.moving_avg_cost`)
- **Failure:** `get_item` populates the identity map before the FOR UPDATE (which selects only
  the id column and does not repopulate `item`). If a concurrent receipt commits a new average
  between the load and lock acquisition, the transfer — which the lock has serialized *after*
  that receipt — records both legs at the pre-receipt cost. No quantity or GL corruption (legs
  net to zero, transfers post no JE, valuation reports use the live `item.moving_avg_cost`),
  but the ledger's cost provenance is wrong for a movement that demonstrably happened after the
  receipt — a defect in a project where audit trail is a first-class constraint, and exactly the
  staleness `post_receipt` was given `db.refresh(item)` to fix in the same commit (73e45c2).
- **Fix:** `await db.refresh(item)` after the lock, as in post_receipt (post_issue has the same
  pattern pre-existing; worth folding in if touched).

## Questions
- **GELATO pick_for_shipment acquires item locks incrementally in request-line order**
  (`shipments.py:387` — post_putaway per line, unsorted), unlike every other multi-item path
  (sorted). Two concurrent picks whose lines order shared items oppositely (or a pick racing a
  MOUSSE issue over the same two items) can deadlock; Postgres aborts one with a 500 rather than
  a clean 409/422. Pre-existing (Phase 12b), not introduced here — but it is the one remaining
  writer outside the phase's lock discipline and probably belongs on the backlog with the other
  trust-boundary closures.
- **`TransactionRead` still omits `bin_id`**, so the transactions API/FE cannot show which pool
  a post-Phase-4 row hit; the SYERP audit `detail` strings cover adjust/transfer, but the MOUSSE
  `work_order.issued` audit row records only line count + value, leaving the per-line bins
  reconstructable only from raw ledger rows. Pre-existing schema; flagging since the phase made
  bin_id load-bearing.
