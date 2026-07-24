# ABOUTME: SERVICE-path port of verify_inventory.py scenarios 3-6 (SC1a) — the moving-average crux.
# ABOUTME: Drives the real inventory service (post_receipt/adjustment/transfer) against the test DB.
"""
SYERP inventory moving-average SERVICE crux — ported from
``backend/scripts/verify_inventory.py`` scenarios 3-6 (SC1a).

WHY THIS EXISTS:
  ``test_inventory.py`` covers the PURE ``compute_new_moving_avg`` helper (no DB).
  The weighted-average that a shop actually sees, however, is produced by the
  SERVICE path — ``post_receipt`` sums prior on-hand, calls the helper, writes the
  ledger row, and updates ``item.moving_avg_cost``. That end-to-end path only ever
  ran against the live ``biznice`` DB via the standalone verify script. This test
  closes that gap by mirroring the script's sequential scenarios through the same
  service functions on the truncate-fresh test database.
"""
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.modules.syerp.models import InventoryTxn
from app.modules.syerp.schemas import InventoryItemCreate, StockLocationCreate
from app.modules.syerp.service import (
    create_item,
    create_location,
    get_item,
    get_item_onhand,
    post_adjustment,
    post_receipt,
    post_transfer,
)

ACTOR_ID = "admin-user"  # a real seeded admin identity (see conftest _isolate)


async def _txn_count(session, item_id: str) -> int:
    """Count ledger rows for an item (proves no row is appended on a rejected op)."""
    result = await session.execute(
        select(func.count()).select_from(InventoryTxn).where(InventoryTxn.item_id == item_id)
    )
    return int(result.scalar() or 0)


async def test_moving_average_service_crux(seeded_ledger_db) -> None:
    """
    Port of verify_inventory.py scenarios 3-6 through the SERVICE path.

    Sequential, state-building, exactly as the standalone verify script runs:
      3. Receive 10@2 then 10@4 at A → item.moving_avg_cost == Decimal("3.000000").
      4. get_item_onhand → A qty 20, total 20, value Decimal("60.000000").
      5. A negative adjustment below zero is REJECTED — NO ledger row appended
         AND moving_avg_cost unchanged.
      6. A valid transfer A→B: total on-hand unchanged (20), per-location stock
         moved, moving_avg_cost unchanged, and the two legs share one non-null
         transfer_group_id.
    """
    session = seeded_ledger_db

    # -- Scenario 2 (setup): one item + two locations (A, B) -----------------
    item = await create_item(
        session, InventoryItemCreate(name="SC1a Widget", unit_of_measure="ea")
    )
    item_id = item.id
    loc_a = await create_location(session, StockLocationCreate(name="SC1a-A"))
    loc_b = await create_location(session, StockLocationCreate(name="SC1a-B"))

    # -- Scenario 3: 10@2 then 10@4 at A → moving_avg_cost == 3.000000 --------
    # This is the SERVICE-path moving-average crux: the value flows through
    # post_receipt (prior-on-hand sum → compute_new_moving_avg → item update),
    # NOT the pure helper. SC2 red-on-revert: breaking the weighted-average in
    # the service layer must turn THIS assertion RED.
    await post_receipt(session, item_id, loc_a.id, Decimal("10"), Decimal("2"), ACTOR_ID)
    await post_receipt(session, item_id, loc_a.id, Decimal("10"), Decimal("4"), ACTOR_ID)
    item = await get_item(session, item_id)
    assert item.moving_avg_cost == Decimal("3.000000")

    # -- Scenario 4: on-hand → A qty 20, total 20, value 60.000000 -----------
    onhand = await get_item_onhand(session, item_id)
    loc_a_qty = next(
        (loc.quantity for loc in onhand.locations if loc.location_id == loc_a.id), None
    )
    assert loc_a_qty == Decimal("20")
    assert onhand.total_quantity == Decimal("20")
    assert onhand.onhand_value == Decimal("60.000000")  # 20 * 3.000000

    # -- Scenario 5: negative adjustment below zero is REJECTED --------------
    count_before = await _txn_count(session, item_id)
    with pytest.raises(HTTPException):
        await post_adjustment(
            session, item_id, loc_a.id, Decimal("-999"), "over-issue", ACTOR_ID
        )
    count_after = await _txn_count(session, item_id)
    assert count_after == count_before  # NO ledger row appended by the reject
    item = await get_item(session, item_id)
    assert item.moving_avg_cost == Decimal("3.000000")  # avg untouched

    # -- Scenario 6: valid transfer A→B ---------------------------------------
    await post_transfer(session, item_id, loc_a.id, loc_b.id, Decimal("5"), ACTOR_ID)
    onhand2 = await get_item_onhand(session, item_id)
    a_qty2 = next(
        (loc.quantity for loc in onhand2.locations if loc.location_id == loc_a.id), None
    )
    b_qty2 = next(
        (loc.quantity for loc in onhand2.locations if loc.location_id == loc_b.id), None
    )
    assert onhand2.total_quantity == Decimal("20")  # total unchanged
    assert a_qty2 == Decimal("15")  # 20 → 15 (5 out)
    assert b_qty2 == Decimal("5")  # 0 → 5 (5 in)
    item = await get_item(session, item_id)
    assert item.moving_avg_cost == Decimal("3.000000")  # transfer never moves avg

    result = await session.execute(
        select(InventoryTxn).where(
            InventoryTxn.item_id == item_id,
            InventoryTxn.txn_type == "transfer",
        )
    )
    legs = list(result.scalars().all())
    group_ids = {leg.transfer_group_id for leg in legs}
    assert len(legs) == 2
    assert None not in group_ids
    assert len(group_ids) == 1  # two legs share one transfer_group_id
