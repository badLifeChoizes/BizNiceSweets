"""SYERP service — on-hand derivation, moving-average costing, receipts, adjustments, transfers."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.modules.syerp.models import (
        InventoryTxn,
    )
    from app.modules.syerp.schemas import (
        ItemOnHandRead,
        TransactionRead,
    )

from app.modules.syerp.service._common import _COST_QUANTUM
from app.modules.syerp.service.items import get_item
from app.modules.syerp.service.locations import get_location

# ---------------------------------------------------------------------------
# On-hand & valuation reads (Phase 8, Task 4)
# ---------------------------------------------------------------------------
#
# On-hand is a DERIVED aggregate (AC10-3): it is ALWAYS computed as the signed
# SUM(InventoryTxn.quantity) grouped by location — there is no stored quantity
# column to read. Value uses the item's moving_avg_cost (AC10-5). All arithmetic
# is Decimal (fixed-point), never float (D-11).
#
# Zero-net policy (documented choice): a location whose signed transactions net
# to exactly zero is OMITTED from the per-location rows and does not contribute
# to the grand total. Only locations currently holding stock (nonzero net) are
# returned. This keeps the on-hand view a picture of *where stock actually is*.


def _derive_onhand(
    location_rows: Iterable[tuple[int, str, Decimal]],
    moving_avg_cost: Decimal,
) -> tuple[list[tuple[int, str, Decimal]], Decimal, Decimal]:
    """
    Pure valuation core for on-hand derivation (no DB — unit-testable).

    Given per-location (location_id, location_name, net_quantity) rows and an
    item's moving-average unit cost, returns:
      - the subset of rows with a NONZERO net quantity (zero-net locations
        omitted — documented policy above),
      - the grand-total quantity summed across those nonzero rows,
      - the on-hand value = grand_total_qty * moving_avg_cost.

    All sums/products are Decimal so there is no float drift: e.g. summing
    Decimal("0.1") three times yields exactly Decimal("0.3"). The grand total
    seeds from Decimal("0") so an item with no movements returns Decimal("0"),
    not an int.
    """
    nonzero = [(lid, name, qty) for lid, name, qty in location_rows if qty != 0]
    total_qty = sum((qty for _, _, qty in nonzero), Decimal("0"))
    value = total_qty * moving_avg_cost
    return nonzero, total_qty, value


async def get_item_onhand(db: AsyncSession, item_id: str) -> ItemOnHandRead:
    """
    Return the derived on-hand-by-location + valuation for an inventory item.

    On-hand is derived, never stored (AC10-3):
      select(txn.location_id, StockLocation.name, func.sum(txn.quantity))
        .join(StockLocation).where(item_id==).group_by(location_id, name)

    The per-location rows carry the signed SUM of every InventoryTxn.quantity
    for the item at that location (positive receipts + negative issues). Value
    is grand_total_qty * item.moving_avg_cost (AC10-5), computed in Decimal.

    Zero-net locations are omitted (see module note above). Raises HTTP 404 if
    the item does not exist (mirrors get_item).
    """
    from app.modules.syerp.models import InventoryTxn, StockLocation
    from app.modules.syerp.schemas import ItemOnHandRead, OnHandByLocation

    item = await get_item(db, item_id)

    stmt = (
        select(
            InventoryTxn.location_id,
            StockLocation.name,
            func.sum(InventoryTxn.quantity),
        )
        .join(StockLocation, StockLocation.id == InventoryTxn.location_id)
        .where(InventoryTxn.item_id == item_id)
        .group_by(InventoryTxn.location_id, StockLocation.name)
        .order_by(StockLocation.name)
    )
    result = await db.execute(stmt)
    location_rows = [(lid, name, qty) for lid, name, qty in result.all()]

    nonzero, total_qty, value = _derive_onhand(location_rows, item.moving_avg_cost)

    return ItemOnHandRead(
        item_id=item.id,
        moving_avg_cost=item.moving_avg_cost,
        locations=[
            OnHandByLocation(location_id=lid, location_name=name, quantity=qty)
            for lid, name, qty in nonzero
        ],
        total_quantity=total_qty,
        onhand_value=value,
    )


async def get_item_on_hand(db: AsyncSession, item_id: str) -> Decimal:
    """
    Return the total signed on-hand quantity for an item across ALL locations.

    Scalar counterpart to get_item_onhand: the single item-level SUM of every
    InventoryTxn.quantity (positive receipts + negative issues), coalescing a
    None result (item has no ledger rows) to Decimal("0"). This is the same
    aggregate inlined by post_receipt for its qty_before, exposed as the reusable
    public source so callers (e.g. CRUMB soft-reservation) do not duplicate it.

    Unlike get_item / get_item_onhand this does NOT 404: a caller may probe a
    non-stock or freshly-created item, and item existence is resolved separately.
    """
    from app.modules.syerp.models import InventoryTxn

    result = await db.execute(
        select(func.sum(InventoryTxn.quantity)).where(InventoryTxn.item_id == item_id)
    )
    return result.scalar() or Decimal("0")


async def list_item_transactions(db: AsyncSession, item_id: str) -> list[TransactionRead]:
    """
    Return an item's inventory-ledger rows, newest-first (Task 11 read half).

    Thin read-only projection over the append-only InventoryTxn ledger (AC10-4):
    each row is joined to its StockLocation for the human-readable location name.
    Ordered by created_at DESC, then id DESC for a stable tie-break (a transfer
    posts two rows sharing a timestamp).

    Raises HTTP 404 if the item does not exist (mirrors get_item).
    """
    from app.modules.syerp.models import InventoryTxn, StockLocation
    from app.modules.syerp.schemas import TransactionRead

    await get_item(db, item_id)

    stmt = (
        select(InventoryTxn, StockLocation.name)
        .join(StockLocation, StockLocation.id == InventoryTxn.location_id)
        .where(InventoryTxn.item_id == item_id)
        .order_by(InventoryTxn.created_at.desc(), InventoryTxn.id.desc())
    )
    result = await db.execute(stmt)

    return [
        TransactionRead(
            id=txn.id,
            item_id=txn.item_id,
            location_id=txn.location_id,
            location_name=name,
            txn_type=txn.txn_type,
            quantity=txn.quantity,
            unit_cost=txn.unit_cost,
            reason=txn.reason,
            created_at=txn.created_at,
        )
        for txn, name in result.all()
    ]


def compute_new_moving_avg(
    qty_before: Decimal,
    avg_before: Decimal,
    qty_recv: Decimal,
    unit_cost: Decimal,
) -> Decimal:
    """
    Recompute the item-level moving-average unit cost after a costed receipt.

    PURE (no DB, no float) so the valuation core is unit-testable in isolation.

    Weighted formula (AC10-5, D-11):
        avg_new = (qty_before * avg_before + qty_recv * unit_cost)
                  / (qty_before + qty_recv)

    First receipt (qty_before == 0) short-circuits to `unit_cost` — there is no
    prior stock to weight against, and this avoids any division-by-zero edge.
    (The general formula also collapses to unit_cost when qty_before is 0, since
    qty_recv is always > 0; the explicit guard just makes that intent obvious.)

    The quotient is quantized to scale 6 (Decimal("0.000001")) with ROUND_HALF_UP
    so non-terminating results (e.g. 20/15 → 1.333333) are deterministic and fit
    the Numeric(18,6) column with no float drift.
    """
    if qty_before == 0:
        new_avg = unit_cost
    else:
        new_avg = (qty_before * avg_before + qty_recv * unit_cost) / (qty_before + qty_recv)
    return new_avg.quantize(_COST_QUANTUM, rounding=ROUND_HALF_UP)


async def post_receipt(
    db: AsyncSession,
    item_id: str,
    location_id: int,
    qty: Decimal,
    unit_cost: Decimal,
    actor_id: str,
    source_type: str | None = None,
    source_id: str | None = None,
    commit: bool = True,
) -> TransactionRead:
    """
    Post a costed receipt: append one ledger row and recompute the moving average.

    In a single transaction (AC10-4,5,7,8; NFR-7):
      1. LOCK the item-master row FOR UPDATE *before* the on-hand read (mirrors
         post_putaway step 3). The append-only InventoryTxn rows cannot be locked
         to serialize concurrent inserts — the item-master row is the correct
         single contention point. One item, so the sorted-id ordering is trivial,
         but the lock must precede the read. The lock also serializes the
         moving-average read-recompute-write (steps 2-3 + 5): the item row is
         refreshed once the lock is held, so a concurrent receipt cannot lose an
         update to item.moving_avg_cost. With commit=False the lock rides the
         CALLER's transaction (receive_line holds it until its single commit —
         correct: the receipt + accumulator bump stay serialized end to end).
      2. Derive `qty_before` = the item's TOTAL on-hand across ALL locations
         (SUM of every InventoryTxn.quantity for the item) — the moving average
         is item-level, not per-location.
      3. Compute the new item-level moving average via compute_new_moving_avg.
      4. Append ONE immutable `receipt` InventoryTxn (positive signed quantity,
         unit_cost set, actor + optional source link).
      5. Update item.moving_avg_cost to the recomputed value.

    Rejects qty <= 0 or unit_cost < 0 with 422 (mirrors the ReceiptCreate schema
    guard; defends the service against non-HTTP callers too). Raises 404 if the
    item or location does not exist (via get_item / get_location).

    `commit` (default True) controls whether this function commits the unit of
    work itself. Standalone receipt posting commits (True). PO-driven receiving
    (Task 17, receive_line) passes commit=False so the receipt row, the
    moving-average update, the line's qty_received increment, and the PO status
    roll-up all land in ONE atomic transaction — the shared write is flushed (so
    the row + PK/timestamp exist for the refresh) but the single commit is owned
    by receive_line. This is the "one commit at the end" refactor that guarantees
    a receipt can never be persisted without its accumulator bump.

    Returns the created row as a TransactionRead (joined location name), mirroring
    list_item_transactions. The router writes the inventory.receipt audit row.
    """
    from app.modules.syerp.models import InventoryItem, InventoryTxn
    from app.modules.syerp.schemas import TransactionRead

    if qty <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Receipt quantity must be greater than zero.",
        )
    if unit_cost < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Receipt unit cost must not be negative.",
        )

    # 404s if either does not exist (mirrors get_item / get_location).
    item = await get_item(db, item_id)
    location = await get_location(db, location_id)

    # LOCK the item-master row FOR UPDATE *before* the on-hand read (mirror
    # post_putaway). Locking the append-only ledger rows would not serialize
    # concurrent inserts; the item-master row is the single contention point.
    # Held until the single commit — the CALLER's commit when commit=False
    # (receive_line holds it through its one atomic transaction).
    await db.execute(
        select(InventoryItem.id).where(InventoryItem.id == item_id).with_for_update()
    )
    # Re-read the item NOW the lock is held: a concurrent receipt may have
    # committed a new moving_avg_cost between get_item's load and lock
    # acquisition, and the identity-mapped `item` would still carry that stale
    # value. The refresh makes the read-recompute-write below race-free (no
    # lost update on the moving average).
    await db.refresh(item)

    # qty_before = total on-hand across ALL locations (item-level average).
    result = await db.execute(
        select(func.sum(InventoryTxn.quantity)).where(InventoryTxn.item_id == item_id)
    )
    qty_before: Decimal = result.scalar() or Decimal("0")

    avg_new = compute_new_moving_avg(qty_before, item.moving_avg_cost, qty, unit_cost)

    txn = InventoryTxn(
        item_id=item_id,
        location_id=location_id,
        txn_type="receipt",
        quantity=qty,
        unit_cost=unit_cost,
        actor_id=actor_id,
        source_type=source_type,
        source_id=source_id,
    )
    db.add(txn)
    item.moving_avg_cost = avg_new

    # commit=True: standalone receipt owns the commit. commit=False: caller
    # (receive_line) owns a single atomic commit; flush so the row + PK/timestamp
    # exist for the refresh below without ending the transaction.
    if commit:
        await db.commit()
    else:
        await db.flush()
    await db.refresh(txn)

    return TransactionRead(
        id=txn.id,
        item_id=txn.item_id,
        location_id=txn.location_id,
        location_name=location.name,
        txn_type=txn.txn_type,
        quantity=txn.quantity,
        unit_cost=txn.unit_cost,
        reason=txn.reason,
        created_at=txn.created_at,
    )


# ---------------------------------------------------------------------------
# Stock adjustments (Phase 8, Task 6, AC10-6, D-P8-7)
# ---------------------------------------------------------------------------
#
# An adjustment corrects an item's on-hand at ONE location by a SIGNED delta.
# A negative delta covers the manual write-off / "issue" case in v2.0 — the
# `issue` txn_type stays RESERVED for MOUSSE, so manual stock-out is posted as
# a negative `adjustment` here.
#
# Negative-stock guard is PER-LOCATION (D-P8-7): a delta may not drive that
# location's on-hand below zero. On-hand is derived (AC10-3), so the guard sums
# the item's signed txn quantities AT the given location and checks
# current_loc_onhand + qty_delta >= 0. Adjustments NEVER move moving_avg_cost —
# only receipts do (AC10-5); positive adjustments add stock at the current
# average, leaving the average unchanged.


def _adjustment_violates_floor(current_loc_onhand: Decimal, qty_delta: Decimal) -> bool:
    """
    Pure per-location negative-stock predicate (no DB — unit-testable).

    Returns True when applying `qty_delta` to the current location on-hand would
    drive it below zero (`current_loc_onhand + qty_delta < 0`), i.e. the
    adjustment must be REJECTED (AC10-6, D-P8-7). A delta that lands exactly on
    zero is allowed (it empties the location, which is valid). All arithmetic is
    Decimal so the boundary is exact with no float drift.
    """
    return current_loc_onhand + qty_delta < 0


async def post_adjustment(
    db: AsyncSession,
    item_id: str,
    location_id: int,
    qty_delta: Decimal,
    reason: str,
    actor_id: str,
    bin_id: int | None = None,
) -> TransactionRead:
    """
    Post a stock adjustment: append one signed `adjustment` ledger row.

    In a single transaction (AC10-4,6; D-P8-7; D-P4-1; D-P4-6; NFR-7):
      1. LOCK the item-master row FOR UPDATE *before* the floor reads (mirrors
         post_putaway step 3). The append-only InventoryTxn rows cannot be
         locked to serialize concurrent inserts — the item-master row is the
         correct single contention point, so two concurrent negative
         adjustments cannot both pass the floor. One item, so the sorted-id
         ordering is trivial, but the lock must precede the reads. Held until
         this function's single commit.
      2. Derive `current_loc_onhand` = the item's on-hand AT `location_id`
         (SUM of that item's InventoryTxn.quantity WHERE location_id matches).
      3. Reject with 422 if the resulting location on-hand
         (`current_loc_onhand + qty_delta`) would be < 0 — NO row is appended
         (per-location negative-stock guard, _adjustment_violates_floor). This
         location-level floor is kept alongside the pool floor (D-P8-7
         contract): it defends legacy data whose per-bin split has already
         desynced from the location total.
      4. For a NEGATIVE delta only, ALSO floor-guard the NAMED pool (D-P4-1
         explicit-or-unbinned): derive that pool's on-hand via get_bin_on_hand
         (bin_id=None is the location's UNBINNED pool) and reject with 422 if
         the delta would drive it below zero — the server never auto-allocates
         across bins, so a write-off at a fully-binned location must name the
         bin. Positive deltas take NO pool floor (D-P4-6): they simply land
         stock in the named bin or the unbinned pool.
      5. Append ONE immutable `adjustment` InventoryTxn with the SIGNED
         `qty_delta`, the `bin_id` (or None for the unbinned pool), no
         unit_cost, the `reason`, and the actor.

    The item's moving_avg_cost is deliberately left UNTOUCHED — only costed
    receipts move the average (AC10-5); a positive adjustment adds quantity at
    the current average. Raises 404 if the item or location does not exist (via
    get_item / get_location). The BIN is NOT validated here: bin existence +
    location-membership is GELATO's domain and the caller's job (D-P12a-3);
    the DB FK on bin_id is the backstop. The 422 status mirrors the receipt
    guard.

    Returns the created row as a TransactionRead (joined location name). The
    router writes the inventory.adjustment audit row.
    """
    from app.modules.syerp.models import InventoryItem, InventoryTxn
    from app.modules.syerp.schemas import TransactionRead

    # 404s if either does not exist (mirrors get_item / get_location).
    item = await get_item(db, item_id)  # noqa: F841 — loaded to 404 on missing item
    location = await get_location(db, location_id)

    # LOCK the item-master row FOR UPDATE *before* the floor read (mirror
    # post_putaway). Locking the append-only ledger rows would not serialize
    # concurrent inserts; the item-master row is the single contention point.
    # Held until this function's single commit.
    await db.execute(
        select(InventoryItem.id).where(InventoryItem.id == item_id).with_for_update()
    )

    # Per-location on-hand: signed SUM of this item's txns AT this location.
    result = await db.execute(
        select(func.sum(InventoryTxn.quantity)).where(
            InventoryTxn.item_id == item_id,
            InventoryTxn.location_id == location_id,
        )
    )
    current_loc_onhand: Decimal = result.scalar() or Decimal("0")

    if _adjustment_violates_floor(current_loc_onhand, qty_delta):
        # Reject BEFORE any mutation — no row is appended on rejection.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Adjustment of {qty_delta} would drive location {location_id} "
                f"on-hand below zero (current {current_loc_onhand})."
            ),
        )

    # A NEGATIVE delta draws the NAMED pool only (D-P4-1): bin_id=None is the
    # location's unbinned pool, a concrete bin_id that single bin. Same floor
    # predicate as the location guard, applied at pool grain. Positive deltas
    # take no pool floor (D-P4-6) — they add stock to the named pool.
    if qty_delta < 0:
        pool_onhand = await get_bin_on_hand(db, item_id, location_id, bin_id)
        if _adjustment_violates_floor(pool_onhand, qty_delta):
            pool_label = "the unbinned pool" if bin_id is None else f"bin {bin_id}"
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Adjustment of {qty_delta} exceeds {pool_label} at location "
                    f"{location_id} (current {pool_onhand})."
                ),
            )

    txn = InventoryTxn(
        item_id=item_id,
        location_id=location_id,
        txn_type="adjustment",
        quantity=qty_delta,
        unit_cost=None,
        actor_id=actor_id,
        reason=reason,
        bin_id=bin_id,
    )
    db.add(txn)
    # moving_avg_cost is intentionally NOT touched — only receipts move it (AC10-5).

    await db.commit()
    await db.refresh(txn)

    return TransactionRead(
        id=txn.id,
        item_id=txn.item_id,
        location_id=txn.location_id,
        location_name=location.name,
        txn_type=txn.txn_type,
        quantity=txn.quantity,
        unit_cost=txn.unit_cost,
        reason=txn.reason,
        created_at=txn.created_at,
    )


# ---------------------------------------------------------------------------
# Stock transfers (Phase 8, Task 7, AC10-6)
# ---------------------------------------------------------------------------
#
# A transfer moves quantity between two locations WITHOUT changing the item's
# total on-hand or its moving-average cost (transfers never move the average —
# only receipts do, AC10-5). It is recorded as TWO paired InventoryTxn legs that
# share a freshly-generated transfer_group_id (AC10-4): a `-qty` leg at the source
# location and a `+qty` leg at the destination, both txn_type='transfer', both
# valued at the item's CURRENT moving_avg_cost. The signed pair nets to exactly
# zero, so total item on-hand is unchanged and per-location on-hand shifts.
#
# The source-underflow guard is the SAME per-location floor as adjustments: the
# `-qty` leg must not drive the source location's on-hand below zero. That is
# exactly _adjustment_violates_floor(current_from_onhand, -qty) — the source leg
# IS a negative adjustment of the source location (current_from_onhand - qty < 0
# ⟺ current_from_onhand < qty). Reusing the predicate keeps the floor semantics
# identical to Task 6 (D-P8-7).


async def post_transfer(
    db: AsyncSession,
    item_id: str,
    from_location_id: int,
    to_location_id: int,
    qty: Decimal,
    actor_id: str,
    from_bin_id: int | None = None,
) -> list[TransactionRead]:
    """
    Post a stock transfer: append the two paired `transfer` ledger legs.

    In a single transaction (AC10-4,6; D-P8-7; D-P4-1; D-P4-5; NFR-7):
      1. Reject with 422 if from_location_id == to_location_id (a self-transfer is
         a no-op) or qty <= 0 (a transfer is a positive movement) — NO rows.
      2. LOCK the item-master row FOR UPDATE *before* the floor reads (mirrors
         post_putaway step 3). The append-only InventoryTxn rows cannot be
         locked to serialize concurrent inserts — the item-master row is the
         correct single contention point, so two concurrent out-transfers
         cannot both pass the source floor. One item, so the sorted-id ordering
         is trivial, but the lock must precede the reads. Held until this
         function's single commit.
      3. Derive `current_from_onhand` = the item's on-hand AT from_location_id
         (SUM of that item's InventoryTxn.quantity WHERE location_id matches).
      4. Reject with 422 if the `-qty` leg would drive the source location on-hand
         below zero (over-draw, _adjustment_violates_floor(from_onhand, -qty)) —
         NO rows are appended. This location-level floor is kept alongside the
         pool floor (D-P8-7 contract): it defends legacy data whose per-bin
         split has already desynced from the location total.
      5. ALSO floor-guard the SOURCE pool named by `from_bin_id` (D-P4-1
         explicit-or-unbinned): derive its on-hand via get_bin_on_hand
         (from_bin_id=None is the source location's UNBINNED pool) and reject
         with 422 if the `-qty` leg would drive it below zero. The server never
         auto-allocates across bins — transferring out of a fully-binned
         location requires naming the bin.
      6. Append EXACTLY TWO immutable `transfer` InventoryTxn rows sharing a fresh
         transfer_group_id: `-qty` at from_location_id carrying
         bin_id=from_bin_id, `+qty` at to_location_id carrying bin_id=None —
         the in leg always lands in the destination's UNBINNED pool, and
         putaway directs it into a bin later (D-P4-5). Both legs are valued at
         the item's CURRENT moving_avg_cost.

    The signed pair nets to zero, so total item on-hand is unchanged; the item's
    moving_avg_cost is deliberately left UNTOUCHED (only receipts move it, AC10-5).
    Raises 404 if the item or either location does not exist (via get_item /
    get_location). The BIN is NOT validated here: bin existence +
    location-membership is GELATO's domain and the caller's job (D-P12a-3); the
    DB FK on bin_id is the backstop. The 422 status mirrors the
    receipt/adjustment guards.

    Returns the two created rows as TransactionRead (joined location names), out
    leg first then in leg. The router writes the inventory.transfer audit row.
    """
    import uuid

    from app.modules.syerp.models import InventoryItem, InventoryTxn
    from app.modules.syerp.schemas import TransactionRead

    if from_location_id == to_location_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Transfer source and destination locations must differ.",
        )
    if qty <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Transfer quantity must be greater than zero.",
        )

    # 404s if the item or either location does not exist.
    item = await get_item(db, item_id)
    from_location = await get_location(db, from_location_id)
    to_location = await get_location(db, to_location_id)

    # LOCK the item-master row FOR UPDATE *before* the floor read (mirror
    # post_putaway). Locking the append-only ledger rows would not serialize
    # concurrent inserts; the item-master row is the single contention point.
    # Held until this function's single commit.
    await db.execute(
        select(InventoryItem.id).where(InventoryItem.id == item_id).with_for_update()
    )

    # Per-location source on-hand: signed SUM of this item's txns AT the source.
    result = await db.execute(
        select(func.sum(InventoryTxn.quantity)).where(
            InventoryTxn.item_id == item_id,
            InventoryTxn.location_id == from_location_id,
        )
    )
    current_from_onhand: Decimal = result.scalar() or Decimal("0")

    # The `-qty` source leg is a negative adjustment of the source location, so the
    # over-draw guard is the same per-location floor (current_from_onhand - qty < 0
    # ⟺ current_from_onhand < qty). Reject BEFORE any mutation — no rows on reject.
    if _adjustment_violates_floor(current_from_onhand, -qty):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Transfer of {qty} exceeds location {from_location_id} on-hand "
                f"(current {current_from_onhand})."
            ),
        )

    # The `-qty` leg draws the NAMED source pool only (D-P4-1): from_bin_id=None
    # is the source location's unbinned pool, a concrete from_bin_id that single
    # bin. Same floor predicate as the location guard, applied at pool grain.
    source_pool_onhand = await get_bin_on_hand(db, item_id, from_location_id, from_bin_id)
    if _adjustment_violates_floor(source_pool_onhand, -qty):
        pool_label = "the unbinned pool" if from_bin_id is None else f"bin {from_bin_id}"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Transfer of {qty} exceeds {pool_label} at location "
                f"{from_location_id} (current {source_pool_onhand})."
            ),
        )

    # Both legs share one freshly-generated group id and the CURRENT average cost.
    transfer_group_id = str(uuid.uuid4())
    unit_cost = item.moving_avg_cost

    out_leg = InventoryTxn(
        item_id=item_id,
        location_id=from_location_id,
        txn_type="transfer",
        quantity=-qty,
        unit_cost=unit_cost,
        actor_id=actor_id,
        bin_id=from_bin_id,
        transfer_group_id=transfer_group_id,
    )
    # The in leg lands UNBINNED at the destination (bin_id=None) — putaway
    # directs it into a bin later (D-P4-5).
    in_leg = InventoryTxn(
        item_id=item_id,
        location_id=to_location_id,
        txn_type="transfer",
        quantity=qty,
        unit_cost=unit_cost,
        actor_id=actor_id,
        bin_id=None,
        transfer_group_id=transfer_group_id,
    )
    db.add(out_leg)
    db.add(in_leg)
    # moving_avg_cost is intentionally NOT touched — only receipts move it (AC10-5).

    await db.commit()
    await db.refresh(out_leg)
    await db.refresh(in_leg)

    return [
        TransactionRead(
            id=out_leg.id,
            item_id=out_leg.item_id,
            location_id=out_leg.location_id,
            location_name=from_location.name,
            txn_type=out_leg.txn_type,
            quantity=out_leg.quantity,
            unit_cost=out_leg.unit_cost,
            reason=out_leg.reason,
            created_at=out_leg.created_at,
        ),
        TransactionRead(
            id=in_leg.id,
            item_id=in_leg.item_id,
            location_id=in_leg.location_id,
            location_name=to_location.name,
            txn_type=in_leg.txn_type,
            quantity=in_leg.quantity,
            unit_cost=in_leg.unit_cost,
            reason=in_leg.reason,
            created_at=in_leg.created_at,
        ),
    ]


# ---------------------------------------------------------------------------
# Bin-aware putaway (Phase 12a, GELATO — bin-dimensioned intra-location move)
# ---------------------------------------------------------------------------
#
# A putaway relocates quantity between two BINS inside the SAME stock location
# WITHOUT changing the item's total on-hand, its per-LOCATION on-hand, or its
# moving-average cost (putaways never move the average — only receipts do,
# AC10-5). It is recorded as TWO paired InventoryTxn legs sharing a freshly
# generated transfer_group_id: a `-qty` leg on the source bin and a `+qty` leg
# on the destination bin, both txn_type='putaway', both at the SAME location, and
# both valued at the item's CURRENT moving_avg_cost. Because both legs carry the
# same location_id the signed pair nets to exactly zero at LOCATION grain — the
# location total is unchanged and only the per-bin split shifts.
#
# bin_id is nullable: bin_id=None is the location's UNBINNED pool (stock received
# straight to a location, not yet put away). A putaway moves from that pool (or
# another bin) into a target bin. The bin dimension is GELATO's domain — SYERP
# stores bin_id as an integer FK (gelato_bin.id) but deliberately does NOT import
# gelato models (D-P12a-3). Bin existence + location-membership is validated by
# GELATO's execute_putaway BEFORE it calls this primitive; the DB FK on bin_id is
# the backstop. This function's contract is the same per-BIN floor and net-zero
# ledger pair that post_transfer gives per-location.


async def get_bin_on_hand(
    db: AsyncSession,
    item_id: str,
    location_id: int,
    bin_id: int | None,
) -> Decimal:
    """
    Return the signed on-hand quantity for an item in one bin of one location.

    Scalar per-bin counterpart to get_item_on_hand / get_item_onhand: the signed
    SUM of every InventoryTxn.quantity for the item WHERE location_id matches AND
    the row's bin matches, coalescing a None result (no ledger rows in that bin)
    to Decimal("0").

    The bin match is null-aware: `bin_id is None` selects the UNBINNED pool via
    `InventoryTxn.bin_id.is_(None)` (SQL `IS NULL`, since `= NULL` never matches);
    a concrete `bin_id` selects that single bin via equality. This distinction is
    load-bearing — the unbinned pool is a real, drawable location of stock.

    A pure derivation like get_item_on_hand — it takes NO lock. Callers that must
    serialize a bin draw (post_putaway) lock the item-master row themselves first.

    TRUST BOUNDARY (closed v4.0 Phase 4, NFR-7): every draw primitive is now
    bin-aware — post_transfer / post_adjustment / MOUSSE issue_components take an
    optional bin_id and draw ONLY the named pool (None = the unbinned pool)
    behind a per-POOL floor guard (D-P4-1 explicit-or-unbinned), matching
    post_putaway / post_issue. The per-bin split therefore no longer rots: for
    post-Phase-4 data every pool stays >= 0 and Σ(bins)+unbinned == location
    total holds at pool grain. Rows written before Phase 4, when draws were
    still bin-blind (historical), may have left a bin overstated and the
    unbinned pool negative — those desyncs are legacy data artifacts the
    current primitives cannot newly create (the location total and roll-up
    were always exact).
    """
    from app.modules.syerp.models import InventoryTxn

    bin_match = (
        InventoryTxn.bin_id.is_(None) if bin_id is None else InventoryTxn.bin_id == bin_id
    )
    result = await db.execute(
        select(func.sum(InventoryTxn.quantity)).where(
            InventoryTxn.item_id == item_id,
            InventoryTxn.location_id == location_id,
            bin_match,
        )
    )
    return result.scalar() or Decimal("0")


async def post_putaway(
    db: AsyncSession,
    item_id: str,
    location_id: int,
    from_bin_id: int | None,
    to_bin_id: int | None,
    qty: Decimal,
    actor_id: str,
    *,
    commit: bool = True,
) -> list[TransactionRead]:
    """
    Post a bin putaway: append the two paired `putaway` ledger legs.

    In a single transaction (AC10-4,6; D-P8-7; D-P12a-3):
      1. Reject with 422 if from_bin_id == to_bin_id (a no-op move — including the
         None→None unbinned self-move) or qty <= 0 — NO rows.
      2. 404 if the item or location does not exist (via get_item / get_location).
         The BINS are NOT validated here: bin existence + location-membership is
         GELATO's domain (it owns gelato_bin) and is checked by execute_putaway
         before this call — SYERP must not import gelato models (D-P12a-3). The DB
         FK on bin_id is the backstop.
      3. LOCK the item-master row FOR UPDATE *before* the floor read (mirrors the
         soft-reservation lock in crumb/service/sales_orders.py). The append-only
         InventoryTxn rows cannot be locked to serialize concurrent inserts — the
         item-master row is the correct single contention point. One item, so the
         sorted-id ordering is trivial, but the lock must precede the read.
      4. Derive `source_onhand` = the item's on-hand in the SOURCE bin at this
         location (get_bin_on_hand). Reject with 422 if the `-qty` leg would drive
         that source pool below zero (over-draw, _adjustment_violates_floor) — NO
         rows are appended.
      5. Append EXACTLY TWO immutable `putaway` InventoryTxn rows sharing a fresh
         transfer_group_id, BOTH at location_id: `-qty` on from_bin_id, `+qty` on
         to_bin_id, both valued at the item's CURRENT moving_avg_cost.

    Both legs carry the SAME location_id, so the signed pair nets to zero at the
    location grain — the item's total and per-location on-hand are unchanged; only
    the per-bin split moves. The item's moving_avg_cost is deliberately left
    UNTOUCHED (only receipts move it, AC10-5). The 422 status mirrors the
    receipt/adjustment/transfer guards.

    Returns the two created rows as TransactionRead (joined location name — both
    the same location), out leg first then in leg. The router / GELATO caller
    writes the audit row.
    """
    import uuid

    from app.modules.syerp.models import InventoryItem, InventoryTxn
    from app.modules.syerp.schemas import TransactionRead

    if from_bin_id == to_bin_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Putaway source and destination bins must differ.",
        )
    if qty <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Putaway quantity must be greater than zero.",
        )

    # 404s if the item or location does not exist. Bins are NOT validated here —
    # that is GELATO's responsibility (D-P12a-3); the DB FK is the backstop.
    item = await get_item(db, item_id)
    location = await get_location(db, location_id)

    # LOCK the item-master row FOR UPDATE *before* the floor read (mirror the
    # soft-reservation lock in sales_orders.py). Locking the append-only ledger
    # rows would not serialize concurrent inserts; the item-master row is the
    # single contention point. Held until this function's single commit.
    await db.execute(
        select(InventoryItem.id).where(InventoryItem.id == item_id).with_for_update()
    )

    # Per-bin source on-hand: signed SUM of this item's txns in the source bin.
    source_onhand = await get_bin_on_hand(db, item_id, location_id, from_bin_id)

    # The `-qty` source leg is a negative adjustment of the source bin, so the
    # over-draw guard is the same per-bin floor (source_onhand - qty < 0 ⟺
    # source_onhand < qty). Reject BEFORE any mutation — no rows on reject.
    if _adjustment_violates_floor(source_onhand, -qty):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Putaway of {qty} exceeds bin {from_bin_id} on-hand "
                f"(current {source_onhand})."
            ),
        )

    # Both legs share one freshly-generated group id and the CURRENT average cost.
    transfer_group_id = str(uuid.uuid4())
    unit_cost = item.moving_avg_cost

    out_leg = InventoryTxn(
        item_id=item_id,
        location_id=location_id,
        txn_type="putaway",
        quantity=-qty,
        unit_cost=unit_cost,
        actor_id=actor_id,
        bin_id=from_bin_id,
        transfer_group_id=transfer_group_id,
    )
    in_leg = InventoryTxn(
        item_id=item_id,
        location_id=location_id,
        txn_type="putaway",
        quantity=qty,
        unit_cost=unit_cost,
        actor_id=actor_id,
        bin_id=to_bin_id,
        transfer_group_id=transfer_group_id,
    )
    db.add(out_leg)
    db.add(in_leg)
    # moving_avg_cost is intentionally NOT touched — only receipts move it (AC10-5).

    # `commit=False` lets a caller (e.g. GELATO pick) batch several putaway legs
    # plus its own rows into ONE atomic transaction; the caller owns the commit.
    await db.flush()
    if commit:
        await db.commit()
    await db.refresh(out_leg)
    await db.refresh(in_leg)

    return [
        TransactionRead(
            id=out_leg.id,
            item_id=out_leg.item_id,
            location_id=out_leg.location_id,
            location_name=location.name,
            txn_type=out_leg.txn_type,
            quantity=out_leg.quantity,
            unit_cost=out_leg.unit_cost,
            reason=out_leg.reason,
            created_at=out_leg.created_at,
        ),
        TransactionRead(
            id=in_leg.id,
            item_id=in_leg.item_id,
            location_id=in_leg.location_id,
            location_name=location.name,
            txn_type=in_leg.txn_type,
            quantity=in_leg.quantity,
            unit_cost=in_leg.unit_cost,
            reason=in_leg.reason,
            created_at=in_leg.created_at,
        ),
    ]


# ---------------------------------------------------------------------------
# Bin-aware issue (Phase 12b, GELATO — bin-dimensioned stock-out primitive)
# ---------------------------------------------------------------------------
#
# An issue draws quantity OUT of a single BIN at a single stock location: one
# `-qty` `issue` InventoryTxn leg valued at the item's CURRENT moving_avg_cost.
# It shares the MOUSSE issue leg's shape (mousse/service.py): same signed `-qty`
# / txn_type='issue', and — since v4.0 Phase 4 made issue_components bin-aware
# too (D-P4-1) — the same per-POOL floor guard; the differences are the soft
# source_type/source_id provenance link and the commit=False composition hook.
# This is the pick/ship stock-out primitive GELATO composes over (Phase 12b) —
# receipts still own the moving average (AC10-5); an issue never moves it.
#
# The per-bin floor + item-master lock mirror post_putaway exactly: bin_id=None
# draws the location's UNBINNED pool, a concrete bin_id draws that single bin.
# Bin existence + location-membership is GELATO's domain and is validated by the
# caller before this primitive runs (D-P12a-3); the DB FK on bin_id is the
# backstop. commit=False lets a GELATO caller fold the issue leg into one atomic
# transaction with its own writes.


async def post_issue(
    db: AsyncSession,
    item_id: str,
    location_id: int,
    bin_id: int | None,
    qty: Decimal,
    actor_id: str,
    *,
    source_type: str,
    source_id: str,
    commit: bool = True,
) -> tuple[InventoryTxn, Decimal]:
    """
    Post a bin-aware issue: append ONE `-qty` `issue` ledger leg and value it.

    In a single transaction (AC10-4,6; D-P8-7; D-P12a-3):
      1. Reject with 422 if qty <= 0 (an issue is a positive draw) — NO row.
      2. 404 if the item or location does not exist (via get_item / get_location).
         The BIN is NOT validated here: bin existence + location-membership is
         GELATO's domain (it owns gelato_bin) and is checked by the caller before
         this call — SYERP must not import gelato models (D-P12a-3). The DB FK on
         bin_id is the backstop.
      3. LOCK the item-master row FOR UPDATE *before* the floor read (mirrors
         post_putaway). The append-only InventoryTxn rows cannot be locked to
         serialize concurrent inserts — the item-master row is the correct single
         contention point. Held until this function's single commit.
      4. Derive `source_onhand` = the item's on-hand in the SOURCE bin at this
         location (get_bin_on_hand). Reject with 422 if the `-qty` draw would drive
         that bin pool below zero (over-issue, _adjustment_violates_floor) — NO row.
      5. Append EXACTLY ONE immutable `issue` InventoryTxn: `-qty` on bin_id at
         location_id, valued at the item's CURRENT moving_avg_cost, with the soft
         source_type / source_id provenance link.

    The item's moving_avg_cost is deliberately left UNTOUCHED — only receipts move
    it (AC10-5). `line_value` is the positive extended cost of the draw
    (qty * moving_avg_cost) quantized to scale 6, ROUND_HALF_UP, mirroring the
    MOUSSE issue leg's valuation.

    `commit` (default True) controls whether this function commits the unit of
    work itself. A standalone issue commits (True); a GELATO caller that folds the
    issue into a larger atomic write passes commit=False, so the row is flushed
    (PK/timestamp exist) but the single commit is owned by the caller.

    Returns `(txn, line_value)` — the created InventoryTxn and its positive
    extended cost. The router / GELATO caller writes the audit row.
    """
    from app.modules.syerp.models import InventoryItem, InventoryTxn

    if qty <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Issue quantity must be greater than zero.",
        )

    # 404s if the item or location does not exist. The bin is NOT validated here —
    # that is GELATO's responsibility (D-P12a-3); the DB FK is the backstop.
    item = await get_item(db, item_id)
    await get_location(db, location_id)

    # LOCK the item-master row FOR UPDATE *before* the floor read (mirror
    # post_putaway). Locking the append-only ledger rows would not serialize
    # concurrent inserts; the item-master row is the single contention point.
    await db.execute(
        select(InventoryItem.id).where(InventoryItem.id == item_id).with_for_update()
    )

    # Per-bin source on-hand: signed SUM of this item's txns in the source bin.
    source_onhand = await get_bin_on_hand(db, item_id, location_id, bin_id)

    # The `-qty` draw is a negative adjustment of the source bin, so the over-issue
    # guard is the same per-bin floor (source_onhand - qty < 0 ⟺ source_onhand <
    # qty). Reject BEFORE any mutation — no row on reject.
    if _adjustment_violates_floor(source_onhand, -qty):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Issue of {qty} exceeds bin {bin_id} on-hand "
                f"(current {source_onhand})."
            ),
        )

    unit_cost = item.moving_avg_cost
    line_value = (qty * unit_cost).quantize(_COST_QUANTUM, rounding=ROUND_HALF_UP)

    txn = InventoryTxn(
        item_id=item_id,
        location_id=location_id,
        txn_type="issue",
        quantity=-qty,
        unit_cost=unit_cost,
        actor_id=actor_id,
        bin_id=bin_id,
        source_type=source_type,
        source_id=source_id,
    )
    db.add(txn)
    # moving_avg_cost is intentionally NOT touched — only receipts move it (AC10-5).

    await db.flush()
    if commit:
        await db.commit()

    return (txn, line_value)
