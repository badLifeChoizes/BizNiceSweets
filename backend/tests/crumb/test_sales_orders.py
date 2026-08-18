# ABOUTME: SERVICE-path port of verify_crumb_so.py scenario (E) (SC1f) — the CRUMB soft-reservation crux.
# ABOUTME: Drives the real crumb service (create/confirm/cancel_sales_order) + the min(qty,available) cap, availability formula, non-stock-reserves-0, and cancel-releases behaviors on the test DB.
"""
CRUMB soft-reservation SERVICE crux — ported from ``backend/scripts/verify_crumb_so.py``
scenario (E) RESERVATION MATH (SC1f).

WHY THIS EXISTS:
  ``sales_orders.py`` carries PURE helpers (``_next_sales_order_number``) that
  unit-test in isolation. The reservation engine a shop actually relies on, however,
  is the SERVICE path — ``confirm_sales_order`` reserving
  ``qty_reserved = min(qty_ordered, available)`` per line where
  ``available = on_hand − Σ qty_reserved across OTHER open (confirmed/fulfilling)
  SOs`` for that item, an over-ordered line still confirming with a positive
  shortage, a non-stock line reserving 0, and ``cancel_sales_order`` releasing a
  Confirmed SO's reservation back into availability. That end-to-end path only ever
  ran against the live ``biznice`` DB via the standalone verify script (the harness
  was broken, D-P7-4); this test closes that gap through the same service functions
  on the truncate-fresh test database.

SC2 red-on-revert: reserving ``qty_ordered`` instead of ``min(qty_ordered,
available)`` in ``crumb/service/sales_orders.py::confirm_sales_order`` must turn the
SO_E2 cap assertion (stock line capped at 4 with shortage 4) RED.

Concurrency mutation-proof (verify_crumb_so scenario F) stays in the script per
D-P2a-2; only the sequential reservation crux is ported here (D-P2b-2).

All amounts are Decimal — never float (D-11).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select

from app.modules.crumb.models import SalesOrder, SalesOrderLine
from app.modules.crumb.schemas import SalesOrderCreate, SalesOrderLineCreate
from app.modules.crumb.service import (
    cancel_sales_order,
    confirm_sales_order,
    create_sales_order,
)
from app.modules.plum.models import PlumPart, PlumPartRevision
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME
from app.modules.syerp.models import StockLocation
from app.modules.syerp.schemas import InventoryItemCreate, PartnerCreate
from app.modules.syerp.service import create_item, post_receipt
from app.modules.syerp.service.partners import create_partner

ACTOR_ID = "admin-user"  # a real seeded admin identity (see conftest _isolate)


# ---------------------------------------------------------------------------
# The reservation oracle — lifted near-verbatim from verify_crumb_so.py so the
# assertion computes Σ open reservations itself over the SO lines, not via the
# service's internal helper. Adapted to the single test-DB session (the crux
# functions commit internally, exactly like the AP/MOUSSE sibling ports).
# ---------------------------------------------------------------------------


async def _item_reserved_total(session, item_id: str) -> Decimal:
    """Σ qty_reserved across OPEN (confirmed/fulfilling) SO lines for an item (oracle)."""
    result = await session.execute(
        select(func.coalesce(func.sum(SalesOrderLine.qty_reserved), 0))
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .where(
            SalesOrderLine.item_id == item_id,
            SalesOrder.status.in_(("confirmed", "fulfilling")),
        )
    )
    return Decimal(result.scalar() or 0)


async def _make_part(session, part_number: str) -> str:
    """
    Insert a PLUM part + a Released revision directly via the ORM; return part_id.

    Direct ORM inserts keep the fixture fully controllable rather than driving the
    whole PLUM FSM (mirrors verify_crumb_so._make_part).
    """
    part = PlumPart(id=str(uuid.uuid4()), part_number=part_number, active=True)
    session.add(part)
    await session.flush()
    rev = PlumPartRevision(
        id=str(uuid.uuid4()),
        part_id=part.id,
        revision_number=1,
        revision_label="A",
        status="released",
        description=f"SC1f {part_number}",
        unit_of_measure="ea",
        released_at=datetime.now(UTC),
    )
    session.add(rev)
    await session.flush()
    return part.id


async def _link_item(session, tag: str, part_id: str | None) -> str:
    """Create a SYERP InventoryItem (optionally linked to a PLUM part); return its id."""
    item = await create_item(
        session,
        InventoryItemCreate(
            name=f"SC1f {tag} {uuid.uuid4().hex[:8]}",
            unit_of_measure="ea",
            plum_part_id=part_id,
        ),
    )
    return item.id


async def _main_location_id(session) -> int:
    """Resolve the seeded 'Main' stock location (seeded_ledger_db provisions it)."""
    row = (
        await session.execute(
            select(StockLocation).where(StockLocation.name == DEFAULT_LOCATION_NAME)
        )
    ).scalars().first()
    return row.id


async def test_reservation_math_crux(seeded_ledger_db) -> None:
    """
    Port of verify_crumb_so.py (E): the soft-reservation math crux.

    One scarce stocked item, on-hand 10. Three SOs contend for it in sequence,
    exactly as the standalone verify script runs (sequential, state-building):
      - SO_E1 (qty 6): available 10 → reserved 6 with zero shortage (min(qty,
        available), no cap engaged);
      - SO_E2 (stock qty 8 + a non-stock qty 3): available now 10−6==4 → the stock
        line caps at min(8, 4)==4 with a positive shortage 4 (the over-order still
        confirms), and the non-stock line reserves 0;
      - availability formula: available == on_hand − Σ qty_reserved across OTHER open
        (confirmed/fulfilling) SOs — 10 − (6+4) == 0, the item is fully reserved;
      - cancelling Confirmed SO_E1 zeroes its reservation and releases it (Σ open
        10 → 4);
      - SO_E3 (qty 5): with 4 still reserved, available is 10−4==6 → reserves 5,
        proving the release freed genuine capacity (without it available would be 0
        and this would reserve 0).

    SC2 red-on-revert: reserving qty_ordered instead of min(qty_ordered, available)
    in crumb/service/sales_orders.py::confirm_sales_order must turn the SO_E2 cap
    assertion (reserved 4, shortage 4) RED.
    """
    session = seeded_ledger_db
    main_id = await _main_location_id(session)

    cust = await create_partner(
        session, PartnerCreate(name="SC1f CRUMB Customer", is_customer=True)
    )

    # One scarce item, on-hand 10 (received at unit cost 4).
    part_e = await _make_part(session, f"P-SO-E-{uuid.uuid4().hex[:8]}")
    item_e = await _link_item(session, "E-STOCK", part_e)
    await post_receipt(session, item_e, main_id, Decimal("10"), Decimal("4"), ACTOR_ID)

    # -- SO_E1: qty 6 → available 10 → reserved 6 (full, no shortage) ---------
    so_e1 = await create_sales_order(
        session,
        SalesOrderCreate(
            partner_id=cust.id,
            lines=[
                SalesOrderLineCreate(
                    item_id=item_e, qty_ordered=Decimal("6"), unit_price=Decimal("20")
                )
            ],
        ),
        ACTOR_ID,
    )
    e1 = await confirm_sales_order(session, so_e1.id, ACTOR_ID)
    # min(qty, available) with no cap engaged: reserves the full 6, zero shortage.
    assert e1.lines[0].qty_reserved == Decimal("6")
    assert e1.lines[0].shortage == Decimal("0")

    # -- SO_E2: stock qty 8 + non-stock qty 3 → cap at min(8, available 4) ----
    so_e2 = await create_sales_order(
        session,
        SalesOrderCreate(
            partner_id=cust.id,
            lines=[
                SalesOrderLineCreate(
                    item_id=item_e, qty_ordered=Decimal("8"), unit_price=Decimal("20")
                ),
                SalesOrderLineCreate(
                    description="Non-stock service",
                    qty_ordered=Decimal("3"),
                    unit_price=Decimal("9"),
                ),
            ],
        ),
        ACTOR_ID,
    )
    e2 = await confirm_sales_order(session, so_e2.id, ACTOR_ID)
    e2_lines = sorted(e2.lines, key=lambda ln: ln.sort_order)
    # THE CAP (SC2 red-on-revert target): available is now 10−6==4, so the stock
    # line reserves min(8, 4)==4 with a positive shortage 4 — the over-order still
    # confirms. Reserving qty_ordered (8) instead of min(...) turns this RED.
    assert e2.status == "confirmed"
    assert e2_lines[0].qty_reserved == Decimal("4")
    assert e2_lines[0].shortage == Decimal("4")
    # The non-stock line (item_id NULL) has nothing to reserve → 0.
    assert e2_lines[1].qty_reserved == Decimal("0")

    # -- Availability formula: available == on_hand − Σ open reservations -----
    # 10 − (6 + 4) == 0, the item is fully reserved (oracle over the SO lines).
    reserved_now = await _item_reserved_total(session, item_e)
    assert reserved_now == Decimal("10")
    assert (Decimal("10") - reserved_now) == Decimal("0")

    # -- Cancel SO_E1 → releases its 6 back into availability -----------------
    e1_cancelled = await cancel_sales_order(session, so_e1.id, ACTOR_ID)
    reserved_after_cancel = await _item_reserved_total(session, item_e)
    # Cancelling a Confirmed SO zeroes its reservation: Σ open drops 10 → 4.
    assert e1_cancelled.status == "cancelled"
    assert all(ln.qty_reserved == Decimal("0") for ln in e1_cancelled.lines)
    assert reserved_after_cancel == Decimal("4")

    # -- SO_E3: qty 5 → available now 10−4==6 → reserves 5 --------------------
    so_e3 = await create_sales_order(
        session,
        SalesOrderCreate(
            partner_id=cust.id,
            lines=[
                SalesOrderLineCreate(
                    item_id=item_e, qty_ordered=Decimal("5"), unit_price=Decimal("20")
                )
            ],
        ),
        ACTOR_ID,
    )
    e3 = await confirm_sales_order(session, so_e3.id, ACTOR_ID)
    # The freed capacity is genuinely available again — without the release
    # availability would be 0 and this would reserve 0.
    assert e3.lines[0].qty_reserved == Decimal("5")
