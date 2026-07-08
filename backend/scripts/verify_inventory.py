# ABOUTME: Standalone live-DB verification for the SYERP inventory backend (Phase 8).
# ABOUTME: Builds its OWN async engine from POSTGRES_* env (no conftest fixtures) and
# ABOUTME: drives the REAL service functions end-to-end and exits non-zero on any failed assertion.
"""
Standalone live-DB verification script for the SYERP inventory backend (Phase 8).

WHY THIS EXISTS (the phase's early-warning gate):
  The backend live-DB pytest harness is broken (D-P7-4), so the DB-dependent
  inventory tests skip under plain ``pytest``. Verifiable truth for the inventory
  service must therefore come from a STANDALONE run against LIVE Postgres. This
  script stands up its own async engine + sessionmaker from the ``POSTGRES_*``
  environment variables — it deliberately does NOT import the broken test
  conftest fixtures — and then calls the REAL service functions
  (``seed_default_location``, ``create_item``, ``create_location``,
  ``post_receipt``, ``get_item_onhand``, ``post_adjustment``, ``post_transfer``),
  proving Tasks 2–7 end-to-end rather than reimplementing them.

HOW TO RUN (the compose ``db`` service is not host-published):
  # 1. Bring up + migrate the dev DB (the api entrypoint runs `alembic upgrade head`)
  podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db api
  # 2. Run this script in a one-off container on the compose network so it can
  #    resolve host `db`:
  podman run --rm --network compose_default --env-file .env -e POSTGRES_HOST=db \
      -v ./backend:/app -w /app localhost/compose_api:latest \
      python scripts/verify_inventory.py

SCENARIO (each line prints PASS:/FAIL:; exits non-zero on any FAIL):
  1. seed_default_location twice → exactly one "Main" location (idempotency).
  2. Create a uniquely-named item + two locations (A, B).
  3. Receive 10@2 then 10@4 at A → item.moving_avg_cost == Decimal("3.000000").
  4. get_item_onhand → A qty == 20, total == 20, value == 60.000000.
  5. A negative adjustment that would drive A below zero is REJECTED — no txn
     row appended AND moving_avg_cost unchanged.
  6. A valid transfer A→B leaves total on-hand unchanged, moves per-location
     stock, leaves moving_avg_cost unchanged, and the two legs share a
     transfer_group_id.

The script uses uniquely-named throwaway data and CLEANS UP after itself
(deletes its item, ledger rows, and the two locations it created) in a finally
block, so it is safe to re-run against the same database.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Import the central model aggregator FIRST so Base.metadata is fully populated
# (InventoryItem.plum_part_id FKs plum_part, whose table must be registered).
import app.core.models  # noqa: F401
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME, seed_default_location
from app.modules.syerp.models import InventoryItem, InventoryTxn, StockLocation
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


async def _txn_count(session_factory: async_sessionmaker, item_id: str) -> int:
    """Count ledger rows for an item (used to prove no row is appended on reject)."""
    async with session_factory() as session:
        result = await session.execute(
            select(func.count()).select_from(InventoryTxn).where(InventoryTxn.item_id == item_id)
        )
        return int(result.scalar() or 0)


async def run() -> None:
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    actor_id = str(uuid.uuid4())  # stand-in for the acting user
    unique = uuid.uuid4().hex[:8]
    item_id: str | None = None
    loc_a_id: int | None = None
    loc_b_id: int | None = None

    try:
        # -------------------------------------------------------------------
        # 1. seed_default_location twice → exactly one "Main" location
        # -------------------------------------------------------------------
        async with session_factory() as session:
            await seed_default_location(session)
        async with session_factory() as session:
            await seed_default_location(session)
        async with session_factory() as session:
            result = await session.execute(
                select(func.count())
                .select_from(StockLocation)
                .where(StockLocation.name == DEFAULT_LOCATION_NAME)
            )
            main_count = int(result.scalar() or 0)
        check(
            "seed_default_location is idempotent (exactly one 'Main' after two runs)",
            main_count == 1,
            f"got {main_count} 'Main' rows",
        )

        # -------------------------------------------------------------------
        # 2. Create an item + two locations (A, B)
        # -------------------------------------------------------------------
        async with session_factory() as session:
            item = await create_item(
                session,
                InventoryItemCreate(
                    name=f"VERIFY Widget {unique}",
                    unit_of_measure="ea",
                ),
            )
            item_id = item.id
        async with session_factory() as session:
            loc_a = await create_location(session, StockLocationCreate(name=f"VERIFY-A-{unique}"))
            loc_a_id = loc_a.id
        async with session_factory() as session:
            loc_b = await create_location(session, StockLocationCreate(name=f"VERIFY-B-{unique}"))
            loc_b_id = loc_b.id
        check(
            "create_item + create_location built one item and two locations",
            item_id is not None and loc_a_id is not None and loc_b_id is not None,
        )

        # -------------------------------------------------------------------
        # 2b. Bad plum_part_id degrades to a clean 4xx, NOT an HTTP 500
        #     (D-P8-2: the PLUM link is advisory — regression guard for the
        #     FK-misclassified-as-code-collision defect fixed in Phase-8 verify).
        # -------------------------------------------------------------------
        bad_link_status = None
        async with session_factory() as session:
            try:
                await create_item(
                    session,
                    InventoryItemCreate(
                        name=f"VERIFY BadLink {unique}",
                        unit_of_measure="ea",
                        plum_part_id="00000000-0000-0000-0000-000000000000",
                    ),
                )
            except HTTPException as exc:
                bad_link_status = exc.status_code
        check(
            "create_item with a non-existent plum_part_id raises 4xx (not 500)",
            bad_link_status is not None and 400 <= bad_link_status < 500,
            f"got status {bad_link_status!r}",
        )

        # -------------------------------------------------------------------
        # 3. Receive 10@2 then 10@4 at A → moving_avg_cost == 3.000000
        # -------------------------------------------------------------------
        async with session_factory() as session:
            await post_receipt(
                session, item_id, loc_a_id, Decimal("10"), Decimal("2"), actor_id
            )
        async with session_factory() as session:
            await post_receipt(
                session, item_id, loc_a_id, Decimal("10"), Decimal("4"), actor_id
            )
        async with session_factory() as session:
            item = await get_item(session, item_id)
            avg_after_receipts = item.moving_avg_cost
        check(
            "moving_avg_cost after 10@2 then 10@4 is exactly Decimal('3.000000')",
            avg_after_receipts == Decimal("3.000000"),
            f"got {avg_after_receipts!r}",
        )

        # -------------------------------------------------------------------
        # 4. get_item_onhand → A qty == 20, total == 20, value == 60.000000
        # -------------------------------------------------------------------
        async with session_factory() as session:
            onhand = await get_item_onhand(session, item_id)
        loc_a_qty = next(
            (loc.quantity for loc in onhand.locations if loc.location_id == loc_a_id), None
        )
        check(
            "on-hand at location A == 20",
            loc_a_qty is not None and loc_a_qty == Decimal("20"),
            f"got {loc_a_qty!r}",
        )
        check(
            "total on-hand quantity == 20",
            onhand.total_quantity == Decimal("20"),
            f"got {onhand.total_quantity!r}",
        )
        check(
            "on-hand value == 20 * 3.000000 == Decimal('60.000000')",
            onhand.onhand_value == Decimal("60.000000"),
            f"got {onhand.onhand_value!r}",
        )

        # -------------------------------------------------------------------
        # 5. Negative adjustment that would drive A below zero is REJECTED
        # -------------------------------------------------------------------
        count_before = await _txn_count(session_factory, item_id)
        rejected = False
        async with session_factory() as session:
            try:
                await post_adjustment(
                    session,
                    item_id,
                    loc_a_id,
                    Decimal("-999"),  # 20 on hand → would be -979 → must reject
                    "verify over-issue",
                    actor_id,
                )
            except HTTPException:
                rejected = True
        count_after = await _txn_count(session_factory, item_id)
        async with session_factory() as session:
            item = await get_item(session, item_id)
            avg_after_reject = item.moving_avg_cost
        check("negative adjustment below zero is rejected (raises HTTPException)", rejected)
        check(
            "rejected adjustment appended NO ledger row",
            count_after == count_before,
            f"count went {count_before} → {count_after}",
        )
        check(
            "moving_avg_cost unchanged after rejected adjustment (still 3.000000)",
            avg_after_reject == Decimal("3.000000"),
            f"got {avg_after_reject!r}",
        )

        # -------------------------------------------------------------------
        # 6. Valid transfer A→B: total unchanged, per-location moved,
        #    avg unchanged, two legs share a transfer_group_id
        # -------------------------------------------------------------------
        async with session_factory() as session:
            await post_transfer(session, item_id, loc_a_id, loc_b_id, Decimal("5"), actor_id)
        async with session_factory() as session:
            onhand2 = await get_item_onhand(session, item_id)
            item = await get_item(session, item_id)
            avg_after_transfer = item.moving_avg_cost
        a_qty2 = next(
            (loc.quantity for loc in onhand2.locations if loc.location_id == loc_a_id), None
        )
        b_qty2 = next(
            (loc.quantity for loc in onhand2.locations if loc.location_id == loc_b_id), None
        )
        check(
            "total on-hand unchanged after transfer (still 20)",
            onhand2.total_quantity == Decimal("20"),
            f"got {onhand2.total_quantity!r}",
        )
        check(
            "location A on-hand moved 20 → 15 after transferring 5 out",
            a_qty2 is not None and a_qty2 == Decimal("15"),
            f"got {a_qty2!r}",
        )
        check(
            "location B on-hand moved 0 → 5 after transferring 5 in",
            b_qty2 is not None and b_qty2 == Decimal("5"),
            f"got {b_qty2!r}",
        )
        check(
            "moving_avg_cost unchanged by transfer (still 3.000000)",
            avg_after_transfer == Decimal("3.000000"),
            f"got {avg_after_transfer!r}",
        )
        async with session_factory() as session:
            result = await session.execute(
                select(InventoryTxn).where(
                    InventoryTxn.item_id == item_id,
                    InventoryTxn.txn_type == "transfer",
                )
            )
            legs = list(result.scalars().all())
        group_ids = {leg.transfer_group_id for leg in legs}
        check(
            "transfer wrote exactly two legs sharing one non-null transfer_group_id",
            len(legs) == 2
            and None not in group_ids
            and len(group_ids) == 1,
            f"legs={len(legs)} group_ids={group_ids}",
        )

    finally:
        # -------------------------------------------------------------------
        # Clean up the throwaway rows (ledger → item → locations). The seeded
        # "Main" location is left in place (it is real deploy state).
        # -------------------------------------------------------------------
        async with session_factory() as session:
            if item_id is not None:
                await session.execute(
                    delete(InventoryTxn).where(InventoryTxn.item_id == item_id)
                )
                await session.execute(
                    delete(InventoryItem).where(InventoryItem.id == item_id)
                )
            loc_ids = [lid for lid in (loc_a_id, loc_b_id) if lid is not None]
            if loc_ids:
                await session.execute(
                    delete(StockLocation).where(StockLocation.id.in_(loc_ids))
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
