# Review: Phase 12a — GELATO bins & directed putaway (`da9474e..db065cf`, backend/ + frontend/)
Date: 2026-07-17

Scope reviewed: `gelato` module (models/schemas/service/router/__init__), SYERP
`post_putaway`/`get_bin_on_hand` + `bin_id` column, migration 0015, auth seed, and the
`frontend/src/routes/gelato/` screens/hooks. Verified against the concurrency, roll-up,
validation, audit, RBAC, and shape-match checks called out in the task.

## Verdict
No **BLOCKER**. The putaway-vs-putaway concurrency crux is implemented correctly. One
**MAJOR** integration finding: the new bin dimension is only maintained by putaway, so
bin-level on-hand becomes wrong the moment any pre-existing (bin-blind) primitive moves stock.

## Findings

### 1. [major] Bin on-hand desyncs from reality after any non-putaway movement — bins overstate, the unbinned pool goes negative
- **Where:** `backend/app/modules/syerp/service/inventory.py` `get_bin_on_hand` (624) / `post_putaway` (661); consumed by `PutawayResult.bin_on_hand` and the unbinned screen. The gap is in the *unchanged* `post_transfer` (471), `post_adjustment` (369), and the MOUSSE issue path — none set `bin_id`, so every leg they write lands in the `bin_id IS NULL` (unbinned) pool.
- **Failure:** Receive 10 of item X to location L (unbinned pool = 10). Putaway 10 into bin A → unbinned = 0, bin A = 10, location total = 10 (correct). Now a stock **transfer** of 10 out of L (or a MOUSSE work-order **issue**) posts a `-10` leg with `bin_id = NULL`. Its floor guard is per-*location* (`current_from_onhand = 10`), so it passes. Result: unbinned pool = **-10**, bin A still reports **10**, location total = 0. `get_bin_on_hand` for bin A now overstates by 10 (a picker directed there finds nothing) and the unbinned pool is negative. Location/total on-hand stay correct — only the bin split lies.
- **Fix:** If bin-aware issue/transfer is deferred to a later phase, document that `get_bin_on_hand` is only trustworthy until the first bin-blind movement, and consider clamping/flagging a negative unbinned pool rather than surfacing it. The durable fix is to make transfer/adjustment/issue bin-aware (draw from a chosen bin) so the ledger's bin dimension stays consistent — otherwise every bin figure this phase surfaces silently rots in normal operation.

## Questions

- **Cross-primitive putaway floor race (could not classify as a defect vs. accepted design).**
  `post_putaway` correctly serializes two concurrent *putaways* on the same source pool
  (the `FOR UPDATE` on the item-master row at inventory.py:729 blocks T2 until T1 commits;
  under READ COMMITTED T2's subsequent `get_bin_on_hand` SELECT then sees T1's committed
  legs — the lock is load-bearing and correctly ordered). But `post_transfer`/`post_adjustment`
  take **no** item lock, so a putaway drawing the unbinned pool can be raced by a concurrent
  transfer/issue drawing the same location, and both pass their floor checks (same
  over-draw as Finding 1, minus the sequencing). This is consistent with the pre-existing
  unlocked transfer/adjustment design (transfers already race each other), so it is not a
  regression this phase introduced — but the phase's lock only defends the putaway↔putaway
  edge, not putaway↔transfer/issue. Flag for whoever owns the inventory concurrency model.

## Checks that passed (no finding)
- **Concurrency crux (putaway↔putaway):** correct — see Question above.
- **Roll-up integrity:** `get_item_onhand`/`get_item_on_hand` remain unfiltered by `bin_id`;
  putaway's two legs share one `location_id` and net to zero, so location/total roll-ups stay
  automatic with no double-count.
- **Bin validation:** `execute_putaway` rejects a missing (404) / wrong-location (422) /
  archived (422) destination bin and a wrong-location source bin; the only write path is
  through it, and the DB FK backstops bin existence. Draining an archived *source* bin is
  intentionally allowed. No gap found.
- **Audit `target_id` int→str:** complete. All three bin routes pass `str(bin_.id)`; the
  putaway route passes `result.out_leg.id`, which is `InventoryTxn.id` — a `String(36)` UUID
  (models.py:261), so no int→VARCHAR(36) mismatch remains. No other int-PK audit target exists.
- **RBAC:** every GET gates `gelato:read`, every POST/PATCH gates `gelato:write`; permissions
  are seeded and granted to admin (auth/seed.py). No read-as-write or unauthenticated hole.
- **Migration 0015:** `gelato_bin` created before the `syerp_inventory_txn.bin_id` FK that
  targets it; downgrade drops FK→index→column then the table (reverse order);
  `down_revision = "0014"`.
- **Frontend shape/invalidation:** `PutawayPayload` matches `PutawayRequest` exactly
  (`item_id, location_id, to_bin_id, qty` as string, `from_bin_id: null`); `qty` sent verbatim
  (no float mangling). `useExecutePutaway` invalidates bins + unbinned + the SYERP on-hand key
  `['syerp','inventory','items',itemId,'onhand']`, which matches `InventoryItemDetail.tsx:152`.
