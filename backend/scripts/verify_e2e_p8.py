# ABOUTME: Fresh-DB end-to-end integration proof for Phase 8 (D-P8-8 cross-requirement flow).
# ABOUTME: Builds its OWN async engine from POSTGRES_* env and drives the REAL SYERP services
# ABOUTME: receipt→on-hand→moving-average, on a freshly-migrated+seeded live DB; exits non-zero on FAIL.
"""
Fresh-DB end-to-end integration proof for SYERP inventory + purchasing (Phase 8).

WHY THIS EXISTS (the phase's definition-of-done proof, D-P8-8):
  This is the single most important Phase 8 proof and it deliberately does NOT
  rely on the broken backend live-DB pytest harness (D-P7-4). It composes the
  Task-8 inventory scenario and the Task-19 purchasing/receiving scenario into
  one flow and runs it against a FRESHLY-MIGRATED live Postgres (``alembic
  upgrade head`` from an empty database → migrations 0001…0008 with no error),
  proving the full cross-requirement path end-to-end:

      create item + ``Main`` location + vendor → PO → approve → partial receive
      → remainder → item on-hand and moving-average updated EXACTLY, and the
      vendor's PO history lists the received PO.

  Like ``verify_inventory.py`` and ``verify_purchasing.py`` it stands up its own
  async engine + sessionmaker from the ``POSTGRES_*`` environment variables — it
  never imports the broken test conftest fixtures — and calls the REAL service
  functions (``create_partner``, ``create_item``, ``create_po``, ``add_line``,
  ``advance_po_status``, ``receive_line``, ``get_item_onhand``, ``list_pos``)
  rather than reimplementing them.

FRESH-DB READINESS (Decision 3, D-P8-14):
  On a freshly-migrated+seeded deploy the default ``Main`` stock location is
  present with no manual step, so receiving works out-of-the-box. This script
  first calls ``seed_default_location`` — the exact idempotent seed the app runs
  at lifespan startup (app.core.seed.run_seeds) — then ASSERTS exactly one
  ``Main`` exists, and reuses that seeded location for every receipt. Seeding the
  app's own startup seed is the automated deploy step, not a manual insert; on a
  DB where the app has already booted, the seed is an idempotent no-op.

HOW TO RUN (from an empty DB — the compose ``db`` service is not host-published):
  # 1. Recreate the dev DB volume so migrations run from empty:
  podman-compose -f compose/compose.yml -f compose/compose.dev.yml down -v
  podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db
  # 2. Migrate from empty (0001…0008) and run this proof in one one-off
  #    container on the compose network so it can resolve host `db`:
  podman run --rm --network compose_default --env-file .env -e POSTGRES_HOST=db \
      -e PYTHONPATH=/app -v ./backend:/app -w /app localhost/compose_api:latest \
      sh -c "alembic upgrade head && python scripts/verify_e2e_p8.py"

SCENARIO (each line prints PASS:/FAIL:; exits non-zero on any FAIL):
  0. FRESH-DB state: seed + assert exactly one seeded ``Main`` location.
  1. Create a vendor (is_vendor=True) + an item; reuse the seeded ``Main``.
  2. Create PO → add line qty 10 @ unit_cost 5 → approve.
  3. Partial receive 4 into ``Main`` → PO `partially_received`, on-hand 4,
     moving-avg 5.000000, line.qty_received 4.
  4. Receive remainder 6 → PO `received`, on-hand 10, moving-avg 5.000000,
     line.qty_received 10.
  5. On-hand VALUE == 10 * 5.000000 == 50.000000; the two receipts are REAL
     `receipt` InventoryTxns source-linked to the PO line (source_type
     `po_receipt`).
  6. Vendor history: list_pos(vendor_id) lists the PO with total == 50 and
     status `received`.
  7. Weighted moving-average moves: a SECOND item received 10@2 then 10@4 lands
     moving_avg_cost at exactly 3.000000 (reuses the verify_inventory scenario).

The script uses uniquely-named throwaway data and CLEANS UP after itself (PO
lines → PO → ledger rows → both items → vendor) in a finally block, so it is safe
to re-run against the same database. The seeded ``Main`` location is reused and
left in place (it is real deploy state).
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Import the central model aggregator FIRST so Base.metadata is fully populated
# (PurchaseOrderLine.item_id / InventoryItem.plum_part_id FKs reference tables
# that must be registered before the FKs resolve — the Task-8 lesson).
import app.core.models  # noqa: F401
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME, seed_default_location
from app.modules.syerp.models import (
    InventoryItem,
    InventoryTxn,
    Partner,
    PurchaseOrder,
    PurchaseOrderLine,
    StockLocation,
)
from app.modules.syerp.schemas import (
    InventoryItemCreate,
    PartnerCreate,
    POCreate,
    POLineCreate,
)
from app.modules.syerp.service import (
    add_line,
    advance_po_status,
    create_item,
    create_partner,
    create_po,
    get_item,
    get_item_onhand,
    list_pos,
    post_receipt,
    receive_line,
)

# ---------------------------------------------------------------------------
# PASS/FAIL bookkeeping
# ---------------------------------------------------------------------------

_FAILURES = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    """Print PASS/FAIL for one assertion and record failures for the exit code."""
    global _FAILURES
    if condition:
        print(f"PASS: {label}")
    else:
        _FAILURES += 1
        suffix = f" — {detail}" if detail else ""
        print(f"FAIL: {label}{suffix}")


# ---------------------------------------------------------------------------
# Own async engine from POSTGRES_* env (NOT the broken conftest fixtures)
# ---------------------------------------------------------------------------


def build_dsn() -> str:
    """
    Assemble the asyncpg DSN directly from POSTGRES_* environment variables.

    Mirrors app.core.config.Settings.database_url but reads os.environ itself so
    the script is fully self-contained and never touches the test conftest.
    """
    host = os.environ.get("POSTGRES_HOST", "db")
    port = os.environ.get("POSTGRES_PORT", "5432")
    database = os.environ.get("POSTGRES_DB", "biznice")
    user = os.environ.get("POSTGRES_USER", "app")
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        print("FAIL: POSTGRES_PASSWORD is not set in the environment.")
        sys.exit(2)
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


def _line_by_id(po_read, line_id: str):
    """Return the nested POLineRead with the given id from a PORead."""
    return next((ln for ln in po_read.lines if ln.id == line_id), None)


def _loc_qty(onhand, loc_id: int):
    """Return the on-hand quantity at a location from an on-hand read (or None)."""
    return next((loc.quantity for loc in onhand.locations if loc.location_id == loc_id), None)


async def run() -> None:
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    actor_id = str(uuid.uuid4())  # stand-in for the acting user
    unique = uuid.uuid4().hex[:8]
    vendor_id: str | None = None
    item_id: str | None = None
    item2_id: str | None = None
    main_id: int | None = None
    po_id: str | None = None
    line_id: str | None = None

    try:
        # -------------------------------------------------------------------
        # 0. FRESH-DB state: seed (as app startup does) then ASSERT exactly one
        #    seeded "Main" location exists — receiving works out-of-the-box.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            # Idempotent: on a fresh DB this inserts Main; on a booted DB it is a
            # no-op. Either way it mirrors app.core.seed.run_seeds' startup seed.
            await seed_default_location(session)
        async with session_factory() as session:
            result = await session.execute(
                select(StockLocation).where(StockLocation.name == DEFAULT_LOCATION_NAME)
            )
            main_rows = result.scalars().all()
        check(
            "fresh-DB state: exactly one seeded 'Main' stock location is present "
            "(out-of-the-box receiving, D-P8-14)",
            len(main_rows) == 1,
            f"got {len(main_rows)} 'Main' rows",
        )
        if len(main_rows) == 1:
            main_id = main_rows[0].id

        # -------------------------------------------------------------------
        # 1. Create a vendor (is_vendor=True) + an item; reuse seeded "Main".
        # -------------------------------------------------------------------
        async with session_factory() as session:
            vendor = await create_partner(
                session,
                PartnerCreate(name=f"VERIFY-E2E Vendor {unique}", is_vendor=True),
            )
            vendor_id = vendor.id
        async with session_factory() as session:
            item = await create_item(
                session,
                InventoryItemCreate(name=f"VERIFY-E2E Widget {unique}", unit_of_measure="ea"),
            )
            item_id = item.id
        check(
            "create_partner(vendor) + create_item built the fixtures; reusing seeded 'Main'",
            vendor_id is not None and item_id is not None and main_id is not None,
            f"vendor={vendor_id!r} item={item_id!r} main={main_id!r}",
        )

        # -------------------------------------------------------------------
        # 2. Create PO → add line qty 10 @ 5 → approve.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            po = await create_po(session, POCreate(vendor_id=vendor_id))
            po_id = po.id
        check(
            "create_po opens a Draft PO for the vendor",
            po.status == "draft" and po.vendor_id == vendor_id,
            f"status={po.status!r} vendor_id={po.vendor_id!r}",
        )
        async with session_factory() as session:
            line = await add_line(
                session,
                po_id,
                POLineCreate(
                    item_id=item_id, qty_ordered=Decimal("10"), unit_cost=Decimal("5")
                ),
            )
            line_id = line.id
        check(
            "add_line appended a line qty 10 @ 5 (qty_received starts at 0)",
            line.qty_ordered == Decimal("10")
            and line.unit_cost == Decimal("5")
            and line.qty_received == Decimal("0"),
            f"qty_ordered={line.qty_ordered!r} unit_cost={line.unit_cost!r} "
            f"qty_received={line.qty_received!r}",
        )
        async with session_factory() as session:
            po = await advance_po_status(session, po_id, "approved", actor_id)
        check(
            "advance_po_status draft → approved (stamps approver)",
            po.status == "approved" and po.approved_by == actor_id,
            f"status={po.status!r} approved_by={po.approved_by!r}",
        )

        # -------------------------------------------------------------------
        # 3. Partial receive 4 into "Main" → partially_received, on-hand 4,
        #    moving-avg 5.000000, line.qty_received 4.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            po = await receive_line(session, po_id, line_id, main_id, Decimal("4"), actor_id)
        check(
            "after receiving 4 the PO is 'partially_received'",
            po.status == "partially_received",
            f"got {po.status!r}",
        )
        recv_line = _line_by_id(po, line_id)
        check(
            "line.qty_received accumulated to 4 after the partial receipt",
            recv_line is not None and recv_line.qty_received == Decimal("4"),
            f"got {recv_line.qty_received if recv_line else None!r}",
        )
        async with session_factory() as session:
            onhand = await get_item_onhand(session, item_id)
            item = await get_item(session, item_id)
        check(
            "item on-hand at 'Main' == 4 after receiving 4",
            _loc_qty(onhand, main_id) == Decimal("4"),
            f"got {_loc_qty(onhand, main_id)!r}",
        )
        check(
            "moving_avg_cost after the first receipt == 5.000000",
            item.moving_avg_cost == Decimal("5.000000"),
            f"got {item.moving_avg_cost!r}",
        )

        # -------------------------------------------------------------------
        # 4. Receive remainder 6 → received, on-hand 10, moving-avg 5.000000,
        #    line.qty_received 10.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            po = await receive_line(session, po_id, line_id, main_id, Decimal("6"), actor_id)
        check(
            "after receiving the remaining 6 the PO is 'received'",
            po.status == "received",
            f"got {po.status!r}",
        )
        final_line = _line_by_id(po, line_id)
        check(
            "line.qty_received accumulated to 10 (fully received)",
            final_line is not None and final_line.qty_received == Decimal("10"),
            f"got {final_line.qty_received if final_line else None!r}",
        )
        async with session_factory() as session:
            onhand = await get_item_onhand(session, item_id)
            item = await get_item(session, item_id)
        check(
            "item on-hand at 'Main' == 10 after receiving the full order",
            _loc_qty(onhand, main_id) == Decimal("10"),
            f"got {_loc_qty(onhand, main_id)!r}",
        )
        check(
            "moving_avg_cost after the full receipt still == 5.000000",
            item.moving_avg_cost == Decimal("5.000000"),
            f"got {item.moving_avg_cost!r}",
        )

        # -------------------------------------------------------------------
        # 5. On-hand VALUE == 10 * 5.000000 == 50.000000; the two receipts are
        #    REAL 'receipt' InventoryTxns source-linked to the PO line.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            onhand_final = await get_item_onhand(session, item_id)
            receipts = (
                await session.execute(
                    select(InventoryTxn).where(
                        InventoryTxn.item_id == item_id,
                        InventoryTxn.txn_type == "receipt",
                    )
                )
            ).scalars().all()
        check(
            "on-hand value == 10 * 5.000000 == Decimal('50.000000')",
            onhand_final.onhand_value == Decimal("50.000000"),
            f"got {onhand_final.onhand_value!r}",
        )
        check(
            "exactly two real 'receipt' inventory txns were written, source-linked "
            "to the PO line (source_type='po_receipt')",
            len(receipts) == 2
            and all(
                r.source_type == "po_receipt" and r.source_id == line_id for r in receipts
            ),
            f"count={len(receipts)} "
            f"sources={[(r.source_type, r.source_id == line_id) for r in receipts]}",
        )

        # -------------------------------------------------------------------
        # 6. Vendor history: list_pos(vendor_id) lists the PO (total 50,
        #    status received).
        # -------------------------------------------------------------------
        async with session_factory() as session:
            vendor_pos = await list_pos(session, vendor_id=vendor_id)
        listed = next((p for p in vendor_pos if p.id == po_id), None)
        check(
            "vendor history: list_pos(vendor_id) lists the PO with total == 50 "
            "and status 'received'",
            listed is not None
            and listed.total == Decimal("50")
            and listed.status == "received",
            f"listed={listed is not None} "
            f"total={listed.total if listed else None!r} "
            f"status={listed.status if listed else None!r}",
        )

        # -------------------------------------------------------------------
        # 7. Weighted moving-average MOVES: a second item received 10@2 then
        #    10@4 lands moving_avg_cost at exactly 3.000000 (verify_inventory
        #    scenario, into the seeded 'Main').
        # -------------------------------------------------------------------
        async with session_factory() as session:
            item2 = await create_item(
                session,
                InventoryItemCreate(
                    name=f"VERIFY-E2E Widget2 {unique}", unit_of_measure="ea"
                ),
            )
            item2_id = item2.id
        async with session_factory() as session:
            await post_receipt(session, item2_id, main_id, Decimal("10"), Decimal("2"), actor_id)
        async with session_factory() as session:
            await post_receipt(session, item2_id, main_id, Decimal("10"), Decimal("4"), actor_id)
        async with session_factory() as session:
            item2 = await get_item(session, item2_id)
            onhand2 = await get_item_onhand(session, item2_id)
        check(
            "weighted moving-average moves: 10@2 then 10@4 → moving_avg_cost == 3.000000",
            item2.moving_avg_cost == Decimal("3.000000"),
            f"got {item2.moving_avg_cost!r}",
        )
        check(
            "second item on-hand value == 20 * 3.000000 == Decimal('60.000000')",
            onhand2.total_quantity == Decimal("20")
            and onhand2.onhand_value == Decimal("60.000000"),
            f"total={onhand2.total_quantity!r} value={onhand2.onhand_value!r}",
        )

    finally:
        # -------------------------------------------------------------------
        # Clean up the throwaway rows (PO lines → PO → ledger → items → vendor).
        # The seeded "Main" location is left in place (it is real deploy state).
        # -------------------------------------------------------------------
        async with session_factory() as session:
            if po_id is not None:
                await session.execute(
                    delete(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po_id)
                )
                await session.execute(delete(PurchaseOrder).where(PurchaseOrder.id == po_id))
            item_ids = [iid for iid in (item_id, item2_id) if iid is not None]
            if item_ids:
                await session.execute(
                    delete(InventoryTxn).where(InventoryTxn.item_id.in_(item_ids))
                )
                await session.execute(
                    delete(InventoryItem).where(InventoryItem.id.in_(item_ids))
                )
            if vendor_id is not None:
                await session.execute(delete(Partner).where(Partner.id == vendor_id))
            await session.commit()
        await engine.dispose()


def main() -> int:
    asyncio.run(run())
    if _FAILURES:
        print(f"\n{_FAILURES} assertion(s) FAILED.")
        return 1
    print("\nAll assertions PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
