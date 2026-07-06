# ABOUTME: Standalone live-DB verification for SYERP purchasing + receiving (Phase 8, Wave C).
# ABOUTME: Builds its OWN async engine from POSTGRES_* env (no conftest fixtures) and drives the
# ABOUTME: REAL PO service functions end-to-end, proving receiving posts inventory; exits non-zero on FAIL.
"""
Standalone live-DB verification script for SYERP purchasing + receiving (Phase 8, Wave C).

WHY THIS EXISTS (the receiving→inventory proof, plan Risk #1):
  The receiving path (Task 17, receive_line) posts a REAL costed inventory
  receipt through the Task-5 post_receipt, accumulates against the line's
  qty_received, rolls the PO status forward, and rejects over-receipt — all in
  ONE atomic transaction. That cross-module integration cannot be proven by the
  pure unit tests (which only pin the helper predicates), and the backend live-DB
  pytest harness is broken (D-P7-4), so DB-dependent tests skip under plain
  ``pytest``. Verifiable truth must therefore come from a STANDALONE run against
  LIVE Postgres. This script stands up its own async engine + sessionmaker from
  the ``POSTGRES_*`` environment variables — it deliberately does NOT import the
  broken test conftest fixtures — and then calls the REAL service functions
  (``create_partner``, ``create_item``, ``create_location``, ``create_po``,
  ``add_line``, ``advance_po_status``, ``receive_line``, ``list_pos``,
  ``get_item_onhand``), proving Tasks 15–18 + the Task-17 integration end-to-end
  rather than reimplementing them.

HOW TO RUN (the compose ``db`` service is not host-published):
  # 1. Bring up + migrate the dev DB (the api entrypoint runs `alembic upgrade head`)
  podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db api
  # 2. Run this script in a one-off container on the compose network so it can
  #    resolve host `db`:
  podman run --rm --network compose_default --env-file .env -e POSTGRES_HOST=db \
      -e PYTHONPATH=/app -v ./backend:/app -w /app localhost/compose_api:latest \
      python scripts/verify_purchasing.py

SCENARIO (each line prints PASS:/FAIL:; exits non-zero on any FAIL):
  1. Create a vendor Partner (is_vendor=True), an item, a location.
  2. Create a PO for that vendor; add a line qty 10 @ unit_cost 5; approve it.
  3. Receive 4 → PO `partially_received`, item on-hand +4, moving-avg == 5,
     line.qty_received == 4.
  4. Attempt receive 10 → RAISES (over-receipt 422); nothing changed.
  5. Receive 6 → PO `received`, on-hand == 10, line.qty_received == 10.
  6. list_pos(vendor_id=...) lists that PO with total == 50, status `received`;
     a DIFFERENT vendor's filter does NOT return it.
  7. The receipts created REAL inventory txns: on-hand value == 10 * 5 == 50.

The script uses uniquely-named throwaway data and CLEANS UP after itself
(deletes its PO lines, PO, ledger rows, item, and both throwaway vendors) in a
finally block, so it is safe to re-run against the same database. The seeded
"Main" location is reused and left in place (it is real deploy state).
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Import the central model aggregator FIRST so Base.metadata is fully populated
# (PurchaseOrderLine.item_id FKs syerp_inventory_item, whose table must be
# registered before the FKs resolve — the Task-8 lesson).
import app.core.models  # noqa: F401
from app.modules.syerp.inventory_seed import seed_default_location
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
    StockLocationCreate,
)
from app.modules.syerp.service import (
    add_line,
    advance_po_status,
    create_item,
    create_location,
    create_partner,
    create_po,
    get_item,
    get_item_onhand,
    list_pos,
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


async def run() -> None:
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    actor_id = str(uuid.uuid4())  # stand-in for the acting user
    unique = uuid.uuid4().hex[:8]
    vendor_id: str | None = None
    other_vendor_id: str | None = None
    item_id: str | None = None
    loc_id: int | None = None
    po_id: str | None = None
    line_id: str | None = None

    try:
        # -------------------------------------------------------------------
        # 1. Create a vendor, a throwaway second vendor, an item, a location.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            vendor = await create_partner(
                session,
                PartnerCreate(name=f"VERIFY Vendor {unique}", is_vendor=True),
            )
            vendor_id = vendor.id
        async with session_factory() as session:
            other_vendor = await create_partner(
                session,
                PartnerCreate(name=f"VERIFY Other Vendor {unique}", is_vendor=True),
            )
            other_vendor_id = other_vendor.id
        async with session_factory() as session:
            item = await create_item(
                session,
                InventoryItemCreate(name=f"VERIFY PO Widget {unique}", unit_of_measure="ea"),
            )
            item_id = item.id
        async with session_factory() as session:
            location = await create_location(
                session, StockLocationCreate(name=f"VERIFY-PO-{unique}")
            )
            loc_id = location.id
        check(
            "create_partner (vendor) + create_item + create_location built the fixtures",
            vendor_id is not None
            and other_vendor_id is not None
            and item_id is not None
            and loc_id is not None,
        )

        # -------------------------------------------------------------------
        # 2. Create a PO for the vendor; add a line qty 10 @ 5; approve it.
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
        # 3. Receive 4 → partially_received, on-hand +4, moving-avg == 5.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            po = await receive_line(session, po_id, line_id, loc_id, Decimal("4"), actor_id)
        check(
            "after receiving 4 the PO is 'partially_received'",
            po.status == "partially_received",
            f"got {po.status!r}",
        )
        recv_line = _line_by_id(po, line_id)
        check(
            "line.qty_received accumulated to 4 after the first receipt",
            recv_line is not None and recv_line.qty_received == Decimal("4"),
            f"got {recv_line.qty_received if recv_line else None!r}",
        )
        async with session_factory() as session:
            onhand = await get_item_onhand(session, item_id)
            item = await get_item(session, item_id)
        loc_qty = next(
            (loc.quantity for loc in onhand.locations if loc.location_id == loc_id), None
        )
        check(
            "item on-hand at the location == 4 after receiving 4",
            loc_qty is not None and loc_qty == Decimal("4"),
            f"got {loc_qty!r}",
        )
        check(
            "moving_avg_cost reflects the receipt unit cost (first receipt → 5.000000)",
            item.moving_avg_cost == Decimal("5.000000"),
            f"got {item.moving_avg_cost!r}",
        )

        # -------------------------------------------------------------------
        # 4. Attempt receive 10 → RAISES over-receipt (422); nothing changed.
        # -------------------------------------------------------------------
        over_rejected = False
        over_status = None
        async with session_factory() as session:
            try:
                await receive_line(session, po_id, line_id, loc_id, Decimal("10"), actor_id)
            except HTTPException as exc:
                over_rejected = True
                over_status = exc.status_code
        check(
            "over-receipt (4 + 10 > 10 ordered) RAISES HTTPException 422",
            over_rejected and over_status == 422,
            f"rejected={over_rejected} status={over_status}",
        )
        async with session_factory() as session:
            po_after = next(
                (p for p in await list_pos(session, vendor_id=vendor_id) if p.id == po_id), None
            )
            onhand_after = await get_item_onhand(session, item_id)
        line_after = _line_by_id(po_after, line_id) if po_after else None
        loc_qty_after = next(
            (loc.quantity for loc in onhand_after.locations if loc.location_id == loc_id), None
        )
        check(
            "rejected over-receipt left line.qty_received unchanged (still 4)",
            line_after is not None and line_after.qty_received == Decimal("4"),
            f"got {line_after.qty_received if line_after else None!r}",
        )
        check(
            "rejected over-receipt left on-hand unchanged (still 4)",
            loc_qty_after is not None and loc_qty_after == Decimal("4"),
            f"got {loc_qty_after!r}",
        )

        # -------------------------------------------------------------------
        # 5. Receive 6 → received, on-hand == 10, line.qty_received == 10.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            po = await receive_line(session, po_id, line_id, loc_id, Decimal("6"), actor_id)
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
        loc_qty2 = next(
            (loc.quantity for loc in onhand.locations if loc.location_id == loc_id), None
        )
        check(
            "item on-hand at the location == 10 after receiving the full order",
            loc_qty2 is not None and loc_qty2 == Decimal("10"),
            f"got {loc_qty2!r}",
        )

        # -------------------------------------------------------------------
        # 6. list_pos(vendor_id) lists the PO (total 50, status received); a
        #    different vendor's filter does NOT return it.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            vendor_pos = await list_pos(session, vendor_id=vendor_id)
            other_pos = await list_pos(session, vendor_id=other_vendor_id)
        listed = next((p for p in vendor_pos if p.id == po_id), None)
        check(
            "list_pos(vendor_id) returns the PO with total == Decimal('50') and status 'received'",
            listed is not None
            and listed.total == Decimal("50")
            and listed.status == "received",
            f"listed={listed is not None} "
            f"total={listed.total if listed else None!r} "
            f"status={listed.status if listed else None!r}",
        )
        check(
            "a DIFFERENT vendor's filter does NOT return this PO",
            all(p.id != po_id for p in other_pos),
            f"other vendor returned {len(other_pos)} PO(s)",
        )

        # -------------------------------------------------------------------
        # 7. The receipts created REAL inventory txns: value == 10 * 5 == 50.
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
            "on-hand value == 10 * 5.000000 == Decimal('50.000000') (receipts really posted)",
            onhand_final.onhand_value == Decimal("50.000000"),
            f"got {onhand_final.onhand_value!r}",
        )
        check(
            "exactly two real 'receipt' inventory txns were written, source-linked to the PO line",
            len(receipts) == 2
            and all(
                r.source_type == "po_receipt" and r.source_id == line_id for r in receipts
            ),
            f"count={len(receipts)} "
            f"sources={[(r.source_type, r.source_id == line_id) for r in receipts]}",
        )

    finally:
        # -------------------------------------------------------------------
        # Clean up the throwaway rows (PO lines → PO → ledger → item →
        # location → vendors). The seeded "Main" location is left in place.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            # Idempotent: seed here too so re-runs against a fresh DB still work
            # (mirrors verify_inventory.py's reliance on the seeded 'Main').
            await seed_default_location(session)
            if po_id is not None:
                await session.execute(
                    delete(PurchaseOrderLine).where(PurchaseOrderLine.po_id == po_id)
                )
                await session.execute(
                    delete(PurchaseOrder).where(PurchaseOrder.id == po_id)
                )
            if item_id is not None:
                await session.execute(
                    delete(InventoryTxn).where(InventoryTxn.item_id == item_id)
                )
                await session.execute(
                    delete(InventoryItem).where(InventoryItem.id == item_id)
                )
            if loc_id is not None:
                await session.execute(
                    delete(StockLocation).where(StockLocation.id == loc_id)
                )
            vendor_ids = [vid for vid in (vendor_id, other_vendor_id) if vid is not None]
            if vendor_ids:
                await session.execute(
                    delete(Partner).where(Partner.id.in_(vendor_ids))
                )
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
