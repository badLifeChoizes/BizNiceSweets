# Review: CRUMB sales-order soft-reservation crux (commit 692dbda)
Date: 2026-07-17
Scope: `backend/app/modules/crumb/service/sales_orders.py` — `confirm_sales_order`,
`cancel_sales_order`, `advance_sales_order_status` dispatch, `_reserved_by_other_open_sos`,
`service/__init__.py` re-exports. Compared against `syerp/service/bills.py` (`create_bill`
lock template) and `syerp/service/inventory.py` (`get_item_on_hand`).

## Verdict summary
The concurrent-**confirm** invariant holds. The proxy-mutex on `InventoryItem` is a faithful
mirror of the `bills.py` PO-line lock, and I could not construct a two-confirm interleaving
that drives `on_hand − Σqty_reserved` negative. The findings below are real but sit at the
edges of the crux, not inside it; none is a confirm-vs-confirm over-reserve.

## Findings

### 1. [medium] Soft-reservation does not serialize against inventory-reducing writes — availability can go negative after confirm
- **Where:** `sales_orders.py:604-617` (lock loop + availability read) vs
  `syerp/service/inventory.py:369-448` (`post_adjustment`), `:471-597` (`post_transfer`) — verified
  none of these take `InventoryItem ... FOR UPDATE` (grep: no `with_for_update` in `inventory.py`).
- **Failure:** Item X on_hand=100, no reservations. Confirm SO-A (orders 100) acquires the
  `InventoryItem` lock, reads `on_hand=100`, reserves 100, commits. Concurrently a write-off
  `post_adjustment(X, −50)` runs; it never contends the `InventoryItem` lock, so it commits
  freely. Now `get_item_on_hand(X)=50` while `Σqty_reserved=100` → `available = 50 − 100 = −50`.
  The literal invariant "`available` must NEVER go negative under concurrency" is violated along
  the inventory-mutation axis, not the confirm axis.
- **Assessment:** This is almost certainly *intended* soft-reservation behaviour — reservations
  are advisory, "shortage is derived, never stored, never blocks," and the adjustment guard is a
  per-*location* on-hand floor that is reservation-unaware by design. A hard lock would not change
  this unless adjustments were made to respect reservations (they explicitly are not). Flagged so
  the intent is recorded, not because the confirm path is wrong.
- **Fix:** None required for this phase if the design is "soft." If the invariant is meant to be
  absolute, it must be enforced at the inventory-issue boundary (a future GELATO/MOUSSE concern),
  not in confirm — document that the phase-11b invariant is "no over-reserve among competing
  confirms," which is what the code actually delivers.

### 2. [low] Sales-order confirm/cancel/create surface is not reachable via HTTP (no SO router)
- **Where:** `crumb/router.py` — grep for `sales_order` / `SalesOrder` / `confirm` returns
  nothing; the only `add_line`/`update_line`/`delete_line` call sites (`router.py:427,452,478`)
  are the **quote** editors. `service/__init__.py:54-59` documents a "sales-order router [that]
  imports them from the submodule directly," but no such router exists.
- **Failure:** A client cannot confirm, cancel, create, or list a sales order — the entire
  reservation feature is dead code from the API's perspective, and there are zero tests exercising
  it (grep: no `sales_order` under `tests/`). The 20-green-assertions gap from 11a can recur here
  because nothing drives `confirm_sales_order` end-to-end.
- **Fix:** Wire the SO router (import the SO `add_line`/`update_line`/`delete_line` from
  `service.sales_orders` directly as the `__init__` comment promises) and add concurrency tests,
  if that is not already scheduled as a later 11b task.

### 3. [low] Closed sales orders retain stale, uncounted `qty_reserved`
- **Where:** `advance_sales_order_status:524-527` — the `fulfilling → closed` plain write does not
  zero `qty_reserved`; `_reserved_by_other_open_sos:556` only counts `{confirmed, fulfilling}`.
- **Failure:** After close, the line rows still carry their old `qty_reserved` while no longer
  contributing to availability. Availability *correctly* frees up (closed is excluded from the
  sum), but `shortage` (`get_sales_order_detail:373`) on a closed order is computed against stale
  reserved figures. Cosmetic only — no invariant impact — but the stale value is a latent trap if
  a later phase starts summing closed lines.
- **Fix:** Either zero `qty_reserved` on close, or leave a comment that closed reserved values are
  intentionally frozen/uncounted.

## Adversarial checklist results (what I verified holds)
1. **Lock ordering / TOCTOU:** PASS. `item_ids = sorted({...})` (`:603`); `SELECT ... FOR UPDATE`
   loop (`:604-607`) runs BEFORE any `get_item_on_hand`/`_reserved_by_other_open_sos` read
   (`:613-617`). Sorted-id order = deadlock-safe. Empty `item_ids` (all non-stock) skips the lock
   AND reserves nothing — safe.
2. **Σ-reserved filter:** PASS. `_reserved_by_other_open_sos` filters exactly
   `status.in_(("confirmed","fulfilling"))` and `SalesOrder.id != exclude_so_id` (`:554-556`);
   join is line→SO on `sales_order_id`. Draft/closed/cancelled correctly excluded; the confirming
   SO excluded.
3. **Same-item multi-line:** PASS. `remaining[item_id]` is decremented per line (`:628`); two
   lines of one item share the running remainder and cannot jointly over-reserve (traced 60+60
   against 100 → 60 then 40).
4. **NULL item_id lines:** PASS. Excluded from `item_ids` (`:603` filter), reserve 0 with no lock
   attempt (`:620-622`).
5. **Lock scope vs read consistency:** PASS. Locked set == availability-read set == reserve-loop
   read set (all keyed on the same non-null `item_id`s).
6. **Cancel/release:** PASS. Release only when `status == "confirmed"` (`:660`); 422 guard rejects
   anything but draft/confirmed (`:651`), matching `SO_TRANSITIONS` (fulfilling/closed cannot
   cancel). Draft cancel is a no-op; release only decreases Σreserved, so it can never break the
   floor.
7. **Decimal discipline:** PASS. All math in `Decimal`; `min`/clamp via comparison preserve
   Decimal; `scalar() or Decimal("0")` coalesces None and a falsy Decimal("0") to the same value.
8. **Commit/lock lifetime:** PASS. Single `db.commit()` per operation; locks held from acquisition
   to that commit. No intermediate commit/flush in confirm or cancel.
9. **Dispatch/FSM:** PASS. `→cancelled` routes to `cancel_sales_order`; `draft→confirmed` routes to
   `confirm_sales_order` (`:519-522`), gated by the `SO_TRANSITIONS` 422 check (`:506-514`).
   `confirmed` is reachable only from `draft` in the table, so no plain-write path bypasses reserve.
10. **`__init__` collision:** PASS. SO `add_line`/`update_line`/`delete_line` are deliberately NOT
    re-exported; quote editors keep those names; `router.py` uses them only for quotes. No shadow.

## VERDICT: PASS — the concurrent-confirm over-reserve invariant holds. Finding #1 (soft
reservation does not serialize against stock write-offs) is a real but by-design scope boundary;
#2 (no SO router / no tests) and #3 (stale reserved on close) are non-blocking. Recommend
confirming #1 is intended and closing #2 before this phase is called done.
