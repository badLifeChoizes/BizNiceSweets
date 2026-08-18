# ABOUTME: SERVICE-path port of verify_gelato_ship.py scenarios (a)(b)(c)(d)(f) (SC1g) — the ship-COGS crux.
# ABOUTME: Drives the REAL pick→pack→ship flow + the balanced COGS JE and 1130↔inventory-subledger tie on the test DB.
"""
GELATO ship-COGS SERVICE crux — ported from ``backend/scripts/verify_gelato_ship.py``
scenarios (a) happy pick→pack→ship, (b) the balanced-COGS JE crux, (c) reservation
relief accuracy, (d) partial-ship accumulation + over-ship 422, and (f) the
control↔subledger valuation tie (SC1g).

WHY THIS EXISTS (GELATO-02 / the outbound accounting crux, SYERP-13 AC1):
  SHIP is the accounting crux — in ONE atomic unit of work ``execute_ship`` issues
  stock out of the staging bin, posts EXACTLY ONE balanced COGS journal entry
  (Dr 5100 COGS / Cr 1130 Inventory for Σ qty*moving_avg), relieves the CRUMB
  soft-reservation for the shipped qty, and advances the shipment to 'shipped' —
  never partially. The load-bearing invariants ported here:

    * BALANCED JE (SC4, SYERP-13 AC1): a ship posts EXACTLY one JournalEntry
      source_type='gelato_shipment', Dr 5100 == Cr 1130 == Σ(qty*moving_avg)
      Decimal-EXACT; the −8 issue InventoryTxn and the JE share the shipment as
      source and are committed together (all or nothing).
    * RESERVATION RELIEF (D-P12b-5): shipping relieves the SO line's qty_reserved by
      exactly the shipped qty so a second open SO's availability is CONSERVED.
    * PARTIAL-SHIP ACCUMULATION (SC3): two shipments against one SO line accumulate
      qty_shipped (6 then 4 == 10); a ship past qty_ordered is rejected 422.
    * CONTROL↔SUBLEDGER TIE (mirrors verify_reports.py, not merely "TB nets zero"):
      the ship's move of the 1130 control account equals the move of the inventory
      subledger valuation (on-hand qty * moving_avg) Decimal-EXACT.

D-P2b-5 (hard rule): the shipment is produced by GENUINELY driving the REAL GELATO
  flow — post_receipt → execute_putaway → create_sales_order / confirm_sales_order →
  execute_pick (REAL PickRequest with PickLineRequests + staging_bin_id) → execute_pack
  → execute_ship — so qty_shipped is stamped and the 12b COGS JE posted by the product
  code, NOT hand-stamped and NOT hand-posted.

SC2 red-on-revert: valuing COGS at the SO line's ``unit_price`` (20) instead of the
  item's ``moving_avg`` (7.5) in ``gelato/service/shipments.py::execute_ship`` must turn
  the (b) balanced-COGS assertion RED — Dr 5100 / Cr 1130 would be 8*20 == 160, not the
  8*7.5 == 60.000000 the subledger values the issue at.

The (e) negative-space cases and the (g)/(h) concurrency mutation-proofs stay in the
standalone script per D-P2a-2; only the sequential accounting ties are ported here
(D-P2b-2). All amounts are Decimal — never float (D-11).
"""
from decimal import ROUND_HALF_UP, Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.modules.crumb.models import SalesOrderLine
from app.modules.crumb.schemas import SalesOrderCreate, SalesOrderLineCreate
from app.modules.crumb.service import confirm_sales_order, create_sales_order
from app.modules.crumb.service.sales_orders import _reserved_by_other_open_sos
from app.modules.gelato.schemas import (
    BinCreate,
    PackRequest,
    PickLineRequest,
    PickRequest,
    PutawayRequest,
)
from app.modules.gelato.service import (
    build_pick_list,
    create_bin,
    execute_pack,
    execute_pick,
    execute_putaway,
    execute_ship,
    get_bin_on_hand,
)
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME
from app.modules.syerp.models import (
    GLAccount,
    InventoryItem,
    InventoryTxn,
    JournalEntry,
    JournalLine,
    StockLocation,
)
from app.modules.syerp.schemas import InventoryItemCreate, PartnerCreate
from app.modules.syerp.service import (
    create_item,
    create_partner,
    get_item_on_hand,
    get_item_onhand,
    post_receipt,
)

ACTOR_ID = "admin-user"  # a real seeded admin identity (see conftest _isolate)
_COST_QUANTUM = Decimal("0.000001")


# ---------------------------------------------------------------------------
# Independent oracles (the assertion's OWN truth) — lifted from verify_gelato_ship.py,
# collapsed onto the single test session (the _seed_* pattern from test_ar.py).
# ---------------------------------------------------------------------------


async def _main_location_id(session) -> int:
    """Resolve the single seeded 'Main' stock location id (seeded_ledger_db)."""
    return (
        await session.execute(
            select(StockLocation.id).where(StockLocation.name == DEFAULT_LOCATION_NAME)
        )
    ).scalars().one()


async def _item_moving_avg(session, item_id: str) -> Decimal:
    """Read the item's current moving_avg_cost straight from the master row (oracle)."""
    return (
        await session.execute(
            select(InventoryItem.moving_avg_cost).where(InventoryItem.id == item_id)
        )
    ).scalar()


async def _location_total(session, item_id: str, location_id: int) -> Decimal:
    """The item's per-location on-hand as get_item_onhand derives it (missing row == 0)."""
    onhand = await get_item_onhand(session, item_id)
    return next(
        (loc.quantity for loc in onhand.locations if loc.location_id == location_id),
        Decimal("0"),
    )


async def _account_balance(session, code: str) -> Decimal:
    """
    Σ (debit − credit) over every JournalLine posted to the GL account `code`.

    The signed control-account balance derived straight from the append-only
    journal — the independent oracle the ship's Cr 1130 must move, mirroring the
    2110 control read verify_reports.py ties the AP subledger against.
    """
    result = await session.execute(
        select(
            func.coalesce(func.sum(JournalLine.debit), 0)
            - func.coalesce(func.sum(JournalLine.credit), 0)
        )
        .select_from(JournalLine)
        .join(GLAccount, GLAccount.id == JournalLine.account_id)
        .where(GLAccount.code == code)
    )
    return Decimal(result.scalar() or 0)


async def _subledger_valuation(session, item_id: str) -> Decimal:
    """
    The inventory subledger valuation for one item: on-hand qty * moving_avg_cost.

    The subledger side of the control↔subledger tie (SYERP values on-hand at the
    item's moving average — get_item_onhand.onhand_value). Computed here as the
    scalar on-hand times the current average so the tie can be delta-checked around
    a single ship in isolation.
    """
    on_hand = await get_item_on_hand(session, item_id)
    avg = await _item_moving_avg(session, item_id)
    return on_hand * avg


async def _so_line_reserved(session, line_id: str) -> Decimal:
    """The live qty_reserved on one SO line (oracle for reservation relief)."""
    return (
        await session.execute(
            select(SalesOrderLine.qty_reserved).where(SalesOrderLine.id == line_id)
        )
    ).scalar()


async def _seed_confirmed_order(
    session,
    location_id: int,
    cust_id: str,
    tag: str,
    *,
    receipts: list[tuple[Decimal, Decimal]],
    into_bin_qty: Decimal,
    order_qty: Decimal,
    unit_price: Decimal = Decimal("20"),
) -> dict:
    """
    Seed one shippable order: an item with `receipts` (moving its moving_avg off 1.0),
    a pick bin holding `into_bin_qty`, a staging bin, and a CONFIRMED single-line SO
    ordering `order_qty`. Returns the handles the scenario drives pick/pack/ship with.
    Lifted from verify_gelato_ship.py::_seed_confirmed_order onto the single test session.
    """
    item = await create_item(
        session, InventoryItemCreate(name=f"SC1g GELATO {tag} Widget", unit_of_measure="ea")
    )
    for qty, cost in receipts:
        await post_receipt(session, item.id, location_id, qty, cost, ACTOR_ID)

    pick_bin = await create_bin(session, BinCreate(location_id=location_id, code=f"{tag}-PICK"))
    staging_bin = await create_bin(
        session, BinCreate(location_id=location_id, code=f"{tag}-STAGE")
    )
    await execute_putaway(
        session,
        PutawayRequest(
            item_id=item.id, location_id=location_id, to_bin_id=pick_bin.id,
            qty=into_bin_qty, from_bin_id=None,
        ),
        ACTOR_ID,
    )

    so = await create_sales_order(
        session,
        SalesOrderCreate(
            partner_id=cust_id,
            lines=[
                SalesOrderLineCreate(
                    item_id=item.id, qty_ordered=order_qty, unit_price=unit_price
                )
            ],
        ),
        ACTOR_ID,
    )
    confirmed = await confirm_sales_order(session, so.id, ACTOR_ID)

    return {
        "item_id": item.id,
        "pick_bin": pick_bin.id,
        "staging_bin": staging_bin.id,
        "so_id": so.id,
        "so_line_id": confirmed.lines[0].id,
        "moving_avg": await _item_moving_avg(session, item.id),
    }


async def test_gelato_ship_cogs_crux(seeded_ledger_db) -> None:
    """
    Port of verify_gelato_ship.py (a)(b)(c)(d)(f) through the SERVICE path.

    Sequential, state-building, exactly as the standalone verify script runs:
      (a) HAPPY PATH — receive 100@6 then 100@9 (moving_avg 7.5), putaway 50, confirm an
          8 @ 20 SO, build_pick_list surfaces the pick bin, execute_pick (REAL PickRequest
          net-zero at location) → execute_pack → execute_ship (all REAL flow, D-P2b-5);
          the location total falls by exactly the shipped 8 (200 → 192) and the staging
          bin nets to zero.
      (b/CRUX) BALANCED JE — the ship posts EXACTLY one JournalEntry
          source_type='gelato_shipment', Dr 5100 == Cr 1130 == Σ(qty*moving_avg) ==
          8*7.5 == 60.000000 Decimal-EXACT; the single −8 issue InventoryTxn and the JE
          share the shipment source and the shipment carries the journal_entry_id (atomic).
      (c) RESERVATION RELIEF — two open SOs fully reserve a scarce item (5+5 of 10);
          shipping SO1's 5 relieves its qty_reserved by exactly 5 and a second SO's
          availability is CONSERVED (the relief exactly offsets the on-hand issue).
      (d) PARTIAL-SHIP — two ships against ONE SO line accumulate qty_shipped (6 then 4
          == 10 == qty_ordered); a third ship of 1 past qty_ordered raises 422.
      (f/keeper) CONTROL↔SUBLEDGER TIE — a ship moves the 1130 control balance and the
          inventory subledger valuation by the SAME amount, Decimal-EXACT (Δ1130 ==
          Δsubledger == −(10*8) == −80.000000) — not merely 'TB nets zero'.

    SC2 red-on-revert: valuing COGS at the SO line unit_price (20) instead of the item's
    moving_avg (7.5) in gelato/service/shipments.py::execute_ship turns (b) RED (Dr 5100 /
    Cr 1130 would be 160, not 60.000000).
    """
    session = seeded_ledger_db

    main_id = await _main_location_id(session)
    customer = await create_partner(
        session, PartnerCreate(name="SC1g GELATO Customer", is_customer=True)
    )

    # ======================================================================
    # (a) HAPPY PATH — pick → pack → ship the full order (SC2/SC3/SC4)
    # ======================================================================
    # Two receipts (100@6 then 100@9 → moving_avg 7.5, off 1.0) so COGS is non-trivial.
    # Pick bin holds 50; order/ship 8.
    a = await _seed_confirmed_order(
        session, main_id, customer.id, "A",
        receipts=[(Decimal("100"), Decimal("6")), (Decimal("100"), Decimal("9"))],
        into_bin_qty=Decimal("50"), order_qty=Decimal("8"),
    )
    # The weighted receipts moved moving_avg off 1.0 → 7.500000 (ship COGS non-trivial).
    assert a["moving_avg"] == Decimal("7.500000")

    # build_pick_list — the REAL pick suggestion screen surfaces the pick bin (on_hand 50)
    # and suggests it (covers the remaining 8).
    pick_list = await build_pick_list(session, a["so_id"])
    pl_line = next(
        (ln for ln in pick_list.lines if ln.sales_order_line_id == a["so_line_id"]), None
    )
    assert pl_line is not None
    assert pl_line.suggested_from_bin_id == a["pick_bin"]
    assert any(
        b.bin_id == a["pick_bin"] and b.on_hand == Decimal("50")
        for b in pl_line.available_bins
    )

    loc_before = await _location_total(session, a["item_id"], main_id)

    # execute_pick — REAL PickRequest with PickLineRequest(s) + staging_bin_id, exactly as
    # POST /gelato/shipments/pick constructs it (the 11a/11b keeper).
    picked = await execute_pick(
        session,
        PickRequest(
            sales_order_id=a["so_id"],
            staging_bin_id=a["staging_bin"],
            lines=[
                PickLineRequest(
                    sales_order_line_id=a["so_line_id"], from_bin_id=a["pick_bin"],
                    qty=Decimal("8"),
                )
            ],
        ),
        ACTOR_ID,
    )
    a_shipment_id = picked.id

    # Pick is net-zero at the location (a bin-aware move into staging leaves the
    # per-location total unchanged == 200).
    loc_after_pick = await _location_total(session, a["item_id"], main_id)
    assert loc_after_pick == loc_before == Decimal("200")

    await execute_pack(session, a_shipment_id, PackRequest(), ACTOR_ID)
    shipped = await execute_ship(session, a_shipment_id, ACTOR_ID)

    # After ship the location total fell by exactly the shipped qty (200 → 192) and the
    # staging bin nets to zero (8 in at pick, 8 out at ship).
    loc_after_ship = await _location_total(session, a["item_id"], main_id)
    staging_final = await get_bin_on_hand(session, a["item_id"], main_id, a["staging_bin"])
    assert shipped.status == "shipped"
    assert loc_before - loc_after_ship == Decimal("8")
    assert loc_after_ship == Decimal("192")
    assert staging_final == Decimal("0")

    # ======================================================================
    # (b) BALANCED JE — one COGS entry, Dr 5100 == Cr 1130 == Σ qty*avg (CRUX)
    # ======================================================================
    expected_cogs = (Decimal("8") * a["moving_avg"]).quantize(_COST_QUANTUM, ROUND_HALF_UP)
    je_rows = (
        await session.execute(
            select(JournalEntry).where(
                JournalEntry.source_type == "gelato_shipment",
                JournalEntry.source_id == str(a_shipment_id),
            )
        )
    ).scalars().all()
    # The ship posts EXACTLY ONE JournalEntry source_type='gelato_shipment'.
    assert len(je_rows) == 1
    entry = je_rows[0]

    dr_5100 = (
        await session.execute(
            select(func.coalesce(func.sum(JournalLine.debit), 0))
            .join(GLAccount, GLAccount.id == JournalLine.account_id)
            .where(JournalLine.entry_id == entry.id, GLAccount.code == "5100")
        )
    ).scalar()
    cr_1130 = (
        await session.execute(
            select(func.coalesce(func.sum(JournalLine.credit), 0))
            .join(GLAccount, GLAccount.id == JournalLine.account_id)
            .where(JournalLine.entry_id == entry.id, GLAccount.code == "1130")
        )
    ).scalar()
    # CRUX: Dr 5100 == Cr 1130 == Σ(qty*moving_avg) == 8 * 7.5 == 60.000000 Decimal-EXACT.
    assert Decimal(dr_5100) == Decimal(cr_1130) == expected_cogs == Decimal("60.000000")

    # The issue leg and the JE share the shipment as source and rode one commit: exactly
    # one −8 issue leg, and the shipment carries its journal_entry_id (the ship is atomic).
    issue_txns = (
        await session.execute(
            select(InventoryTxn).where(
                InventoryTxn.source_type == "gelato_shipment",
                InventoryTxn.source_id == str(a_shipment_id),
                InventoryTxn.txn_type == "issue",
            )
        )
    ).scalars().all()
    assert len(issue_txns) == 1
    assert issue_txns[0].quantity == Decimal("-8")
    assert shipped.journal_entry_id is not None
    assert shipped.journal_entry_id == entry.id

    # ======================================================================
    # (c) RESERVATION RELIEF — accuracy, not just "decreased" (D-P12b-5)
    # ======================================================================
    # One scarce item, on-hand 10 (10 into the pick bin). Two open SOs each order 5 → SO1
    # reserves 5, SO2 reserves 5. Ship SO1 fully (5) and prove SO2's availability is
    # CONSERVED because the relief exactly offsets the on-hand issue.
    c = await _seed_confirmed_order(
        session, main_id, customer.id, "C",
        receipts=[(Decimal("10"), Decimal("4"))],
        into_bin_qty=Decimal("10"), order_qty=Decimal("5"),
    )
    so_c2 = await create_sales_order(
        session,
        SalesOrderCreate(
            partner_id=customer.id,
            lines=[
                SalesOrderLineCreate(
                    item_id=c["item_id"], qty_ordered=Decimal("5"), unit_price=Decimal("20")
                )
            ],
        ),
        ACTOR_ID,
    )
    c2_conf = await confirm_sales_order(session, so_c2.id, ACTOR_ID)
    # Both open SOs reserved against the scarce item (SO1 5, SO2 5 of on-hand 10).
    assert await _so_line_reserved(session, c["so_line_id"]) == Decimal("5")
    assert c2_conf.lines[0].qty_reserved == Decimal("5")

    # Availability the SECOND SO sees = on_hand − reserved-by-OTHER-open-SOs (excl SO2).
    async def _avail_for_c2() -> tuple[Decimal, Decimal, Decimal]:
        on_hand = await get_item_on_hand(session, c["item_id"])
        reserved_others = await _reserved_by_other_open_sos(session, c["item_id"], so_c2.id)
        return on_hand, reserved_others, on_hand - reserved_others

    oh_before, others_before, avail_before = await _avail_for_c2()

    # Pick / pack / ship SO1 for its full 5.
    c_pick = await execute_pick(
        session,
        PickRequest(
            sales_order_id=c["so_id"], staging_bin_id=c["staging_bin"],
            lines=[PickLineRequest(
                sales_order_line_id=c["so_line_id"], from_bin_id=c["pick_bin"],
                qty=Decimal("5"),
            )],
        ),
        ACTOR_ID,
    )
    await execute_pack(session, c_pick.id, PackRequest(), ACTOR_ID)
    await execute_ship(session, c_pick.id, ACTOR_ID)

    c1_reserved_after = await _so_line_reserved(session, c["so_line_id"])
    oh_after, others_after, avail_after = await _avail_for_c2()
    # Counterfactual (buggy) availability had the relief NOT happened: on_hand still
    # dropped by 5 but reserved-by-others would still be 5 → it would understate by 5.
    avail_after_no_relief = oh_after - others_before
    # Shipping SO1 relieves its line's qty_reserved by EXACTLY the shipped qty (5 → 0) and
    # drops the reservation SO2 sees from that 'other' open SO by exactly 5.
    assert c1_reserved_after == Decimal("0")
    assert others_before - others_after == Decimal("5")
    # The second SO's availability is CONSERVED across the ship (Δon_hand −5 ==
    # Δreserved_others −5, so avail 5 → 5) — the relief RAISED it by exactly the shipped
    # qty vs the no-relief counterfactual (5 vs 0).
    assert avail_before == avail_after == Decimal("5")
    assert oh_before - oh_after == Decimal("5")
    assert avail_after - avail_after_no_relief == Decimal("5")

    # ======================================================================
    # (d) PARTIAL-SHIP ACCUMULATION — two ships accrue, third over-ships 422
    # ======================================================================
    # One SO line ordered 10; pick bin holds 20. Ship 6 then 4 (accrues to 10); a third
    # ship of 1 would push qty_shipped past qty_ordered → 422.
    d = await _seed_confirmed_order(
        session, main_id, customer.id, "D",
        receipts=[(Decimal("20"), Decimal("5"))],
        into_bin_qty=Decimal("20"), order_qty=Decimal("10"),
    )

    async def _ship_portion(qty: Decimal) -> int:
        """Pick `qty` of the D order into a fresh staging bin, pack, ship; return id."""
        stage = await create_bin(
            session, BinCreate(location_id=main_id, code=f"D-STAGE-{qty}")
        )
        sh = await execute_pick(
            session,
            PickRequest(
                sales_order_id=d["so_id"], staging_bin_id=stage.id,
                lines=[PickLineRequest(
                    sales_order_line_id=d["so_line_id"], from_bin_id=d["pick_bin"], qty=qty,
                )],
            ),
            ACTOR_ID,
        )
        await execute_pack(session, sh.id, PackRequest(), ACTOR_ID)
        await execute_ship(session, sh.id, ACTOR_ID)
        return sh.id

    await _ship_portion(Decimal("6"))
    await _ship_portion(Decimal("4"))
    d_line = await session.get(SalesOrderLine, d["so_line_id"])
    await session.refresh(d_line)
    # Two shipments against ONE SO line accumulate qty_shipped (6 then 4 == 10 == ordered).
    assert d_line.qty_shipped == Decimal("10")

    # A third ship of 1 more would push qty_shipped (10) past qty_ordered (10) → 422.
    d_stage3 = await create_bin(session, BinCreate(location_id=main_id, code="D-STAGE3"))
    d_sh3 = await execute_pick(
        session,
        PickRequest(
            sales_order_id=d["so_id"], staging_bin_id=d_stage3.id,
            lines=[PickLineRequest(
                sales_order_line_id=d["so_line_id"], from_bin_id=d["pick_bin"],
                qty=Decimal("1"),
            )],
        ),
        ACTOR_ID,
    )
    await execute_pack(session, d_sh3.id, PackRequest(), ACTOR_ID)
    with pytest.raises(HTTPException) as over_ship_exc:
        await execute_ship(session, d_sh3.id, ACTOR_ID)
    assert over_ship_exc.value.status_code == 422

    # ======================================================================
    # (f) CONTROL↔SUBLEDGER TIE (mirrors verify_reports.py)
    # ======================================================================
    # A fresh order shipped in isolation: the change in the 1130 control balance equals
    # the change in the item's inventory subledger valuation, to the cent.
    f = await _seed_confirmed_order(
        session, main_id, customer.id, "F",
        receipts=[(Decimal("50"), Decimal("8"))],
        into_bin_qty=Decimal("20"), order_qty=Decimal("10"),
    )
    bal_1130_before = await _account_balance(session, "1130")
    subval_before = await _subledger_valuation(session, f["item_id"])
    f_pick = await execute_pick(
        session,
        PickRequest(
            sales_order_id=f["so_id"], staging_bin_id=f["staging_bin"],
            lines=[PickLineRequest(
                sales_order_line_id=f["so_line_id"], from_bin_id=f["pick_bin"],
                qty=Decimal("10"),
            )],
        ),
        ACTOR_ID,
    )
    await execute_pack(session, f_pick.id, PackRequest(), ACTOR_ID)
    await execute_ship(session, f_pick.id, ACTOR_ID)
    bal_1130_after = await _account_balance(session, "1130")
    subval_after = await _subledger_valuation(session, f["item_id"])
    expected_move = (Decimal("10") * f["moving_avg"]).quantize(_COST_QUANTUM, ROUND_HALF_UP)
    # CONTROL↔SUBLEDGER TIE: the ship moves the 1130 control balance and the inventory
    # subledger valuation by the SAME amount, Decimal-EXACT (Δ1130 == Δsubledger ==
    # −(10 * 8) == −80.000000) — not merely 'TB nets zero'.
    assert bal_1130_after - bal_1130_before == subval_after - subval_before == -expected_move
    assert -expected_move == Decimal("-80.000000")
