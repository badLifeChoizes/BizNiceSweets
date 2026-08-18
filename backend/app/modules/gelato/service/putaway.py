# ABOUTME: GELATO putaway orchestration (GELATO-01) — suggest a target bin
# ABOUTME: (D-P12a-10 heuristic), list a location's unbinned on-hand awaiting
# ABOUTME: putaway, and execute a putaway: validate the bins belong to the
# ABOUTME: location (task 6's deferred check), then delegate to SYERP post_putaway.
"""GELATO putaway service (business logic).

Putaway directs on-hand into precise bins inside a single SYERP stock location:

  * suggest_target_bin — D-P12a-10 heuristic: (a) an ACTIVE bin in the location
    already holding on-hand of the item (lowest code if several), else (b) the
    first ACTIVE bin by code, else (c) None.
  * list_unbinned_stock — every item with unbinned on-hand (> 0) at the location,
    each carrying its suggested destination bin.
  * execute_putaway — validate the source/destination bins belong to the location
    (the membership check task 6 deferred to GELATO, since SYERP must not import
    gelato models — D-P12a-3), then delegate the ledger posting to SYERP
    post_putaway (D-P12a-7) and assemble the PutawayResult.

GELATO stays THIN (D-P10-6): it NEVER writes InventoryTxn itself. Only the SYERP
hub books the two mirrored ledger legs; GELATO reads bin/location on-hand back to
build the result. SYERP model/service imports are lazy (inside functions) so
importing this module never pulls in the hub at module import time. post_putaway's
own 422 (over-draw / self-move) and 404 (item / location) propagate unchanged.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.gelato.service.bins import get_bin, list_bins

if TYPE_CHECKING:
    from app.modules.gelato.schemas import PutawayRequest, PutawayResult, UnbinnedStockRead


# ---------------------------------------------------------------------------
# Target-bin suggestion — D-P12a-10 heuristic (GELATO-01)
# ---------------------------------------------------------------------------


async def suggest_target_bin(
    db: AsyncSession,
    item_id: str,
    location_id: int,
) -> int | None:
    """
    Recommend a destination bin for an item at a location (D-P12a-10 heuristic).

    In order of preference:
      (a) an ACTIVE bin in this location that already holds on-hand (> 0) of the
          item — the lowest-code such bin (consolidate with existing stock);
      (b) otherwise the first ACTIVE bin in the location by code;
      (c) otherwise None (no active bins to suggest).

    Only active bins are considered — list_bins hides archived bins by default,
    already ordered by code, so "first" / "lowest code" is just the first match.
    """
    from app.modules.syerp.service import get_bin_on_hand

    bins = await list_bins(db, location_id)
    if not bins:
        return None

    # (a) prefer an active bin already holding this item (lowest code first).
    for bin_ in bins:
        if await get_bin_on_hand(db, item_id, location_id, bin_.id) > 0:
            return bin_.id

    # (b) else the first active bin by code.
    return bins[0].id


# ---------------------------------------------------------------------------
# Unbinned stock — putaway suggestion screen (GELATO-01)
# ---------------------------------------------------------------------------


async def list_unbinned_stock(
    db: AsyncSession,
    location_id: int,
) -> list[UnbinnedStockRead]:
    """
    Return each item with unbinned on-hand (> 0) at the location, awaiting putaway.

    For every distinct item that has ledger rows at this location, the unbinned
    pool is get_bin_on_hand(item, location, None) — the on-hand not yet assigned
    to any bin. Only items with a positive unbinned pool are included, each with
    its suggested destination bin (suggest_target_bin).

    The > 0 filter cannot hide a LIVE negative pool: since v4.0 Phase 4 (NFR-7,
    D-P4-1) every draw primitive is bin-aware and floor-guards the pool it
    names, so new ledger rows cannot drive the unbinned pool below zero. A
    negative unbinned pool can only be a desync left by the legacy bin-blind
    draws (pre-Phase-4); the filter is kept and simply omits such rows.

    Reading the SYERP ledger (InventoryTxn) directly is fine — only WRITES are
    forbidden to GELATO (D-P12a-3, D-P10-6). Rows are ordered by item_id.
    """
    from app.modules.gelato.schemas import UnbinnedStockRead
    from app.modules.syerp.models import InventoryTxn
    from app.modules.syerp.service import get_bin_on_hand

    # Distinct items with any ledger activity at this location (READ only).
    result = await db.execute(
        select(InventoryTxn.item_id)
        .where(InventoryTxn.location_id == location_id)
        .distinct()
        .order_by(InventoryTxn.item_id)
    )
    item_ids = [row[0] for row in result.all()]

    rows: list[UnbinnedStockRead] = []
    for item_id in item_ids:
        unbinned = await get_bin_on_hand(db, item_id, location_id, None)
        if unbinned > 0:
            rows.append(
                UnbinnedStockRead(
                    item_id=item_id,
                    location_id=location_id,
                    unbinned_qty=unbinned,
                    suggested_bin_id=await suggest_target_bin(db, item_id, location_id),
                )
            )
    return rows


# ---------------------------------------------------------------------------
# Execute putaway — bin membership validation + delegation (GELATO-01)
# ---------------------------------------------------------------------------


async def execute_putaway(
    db: AsyncSession,
    data: PutawayRequest,
    actor_id: str,
) -> PutawayResult:
    """
    Execute a putaway: validate bins, delegate the ledger posting, build the result.

    1. Validate the bins belong to the location — the membership check SYERP
       defers to GELATO (D-P12a-3, since SYERP must not import gelato models):
         * to_bin (data.to_bin_id): 404 if missing, 422 if it belongs to a
           different location, 422 if it is archived (active=False) — you cannot
           put stock into an archived bin.
         * from_bin (data.from_bin_id): when not None, 404 if missing and 422 if
           it belongs to a different location. from_bin_id is None means the
           location's unbinned pool — always valid, no bin to check.
    2. Delegate to SYERP post_putaway (D-P12a-7) — it books the two mirrored
       ledger legs, taking the item-master lock and enforcing the over-draw /
       self-move (422) and item / location (404) guards, which propagate here.
    3. Assemble PutawayResult: the two ledger legs (out then in), the destination
       bin's resulting on-hand, and the location total (unchanged — a putaway
       nets to zero at the location grain).
    """
    from app.modules.syerp.service import (
        get_bin_on_hand,
        get_item_onhand,
        post_putaway,
    )

    # 1a. Destination bin must exist, belong to this location, and be active.
    to_bin = await get_bin(db, data.to_bin_id)
    if to_bin.location_id != data.location_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Destination bin {data.to_bin_id} does not belong to location "
                f"{data.location_id}."
            ),
        )
    if not to_bin.active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Destination bin {data.to_bin_id} is archived.",
        )

    # 1b. Source bin (when given) must exist and belong to this location. A None
    #     from_bin is the unbinned pool — always valid, nothing to validate.
    if data.from_bin_id is not None:
        from_bin = await get_bin(db, data.from_bin_id)
        if from_bin.location_id != data.location_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Source bin {data.from_bin_id} does not belong to location "
                    f"{data.location_id}."
                ),
            )

    # 2. Delegate the ledger posting to the SYERP hub (GELATO never writes txns).
    legs = await post_putaway(
        db,
        item_id=data.item_id,
        location_id=data.location_id,
        from_bin_id=data.from_bin_id,
        to_bin_id=data.to_bin_id,
        qty=data.qty,
        actor_id=actor_id,
    )

    # 3. Read the resulting figures back and assemble the result. post_putaway
    #    returns the out leg first, then the in leg.
    out_leg, in_leg = legs
    bin_on_hand = await get_bin_on_hand(db, data.item_id, data.location_id, data.to_bin_id)

    # Location total: putaway nets to zero at the location grain, so this is the
    # item's on-hand at this location (derived per-location by get_item_onhand;
    # zero-net locations are omitted from its rows, hence the Decimal("0") default).
    onhand = await get_item_onhand(db, data.item_id)
    location_total = next(
        (loc.quantity for loc in onhand.locations if loc.location_id == data.location_id),
        Decimal("0"),
    )

    from app.modules.gelato.schemas import PutawayResult

    return PutawayResult(
        out_leg=out_leg,
        in_leg=in_leg,
        bin_on_hand=bin_on_hand,
        location_total=location_total,
    )
