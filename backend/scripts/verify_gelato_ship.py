# ABOUTME: Standalone live-DB verification for the GELATO outbound pick/pack/ship
# ABOUTME: engine (Phase 12b, GELATO-02). Builds its OWN async engine from POSTGRES_*
# ABOUTME: env (no conftest fixtures) and drives the REAL shipments service through the
# ABOUTME: SAME PickRequest/PackRequest schemas the router sends — proving the ship
# ABOUTME: accounting crux (one balanced COGS JE, Dr 5100 == Cr 1130 == Σ qty*avg), the
# ABOUTME: reservation-relief accuracy, the partial-ship over-ship guard, the negative
# ABOUTME: space, the control↔subledger tie, and THE CRUX — two concurrent ships that
# ABOUTME: cannot over-issue the staging bin; exits non-zero on FAIL and self-cleans.
"""
Standalone live-DB verification script for the GELATO ship engine (Phase 12b).

WHY THIS EXISTS (GELATO-02 / the outbound accounting crux, SC2/SC3/SC4; SYERP-13 AC1):
  Phase 12b layers outbound fulfilment over the 12a bin engine: a CRUMB sales order
  is picked (bin-aware net-zero move into a staging bin), packed (state + staged
  qty), and shipped. SHIP is the accounting crux — in ONE atomic unit of work it
  issues stock out of the staging bin (SYERP post_issue), posts exactly ONE balanced
  COGS journal entry (Dr 5100 COGS / Cr 1130 Inventory for Σ qty*moving_avg), relieves
  the CRUMB soft-reservation for the shipped qty, and advances the shipment to
  'shipped' — never partially. The load-bearing invariants:

    * BALANCED JE (SC4, SYERP-13 AC1): a ship posts EXACTLY one JournalEntry
      source_type='gelato_shipment' for the shipment, with Dr 5100 == Cr 1130 ==
      Σ(qty * moving_avg_cost) Decimal-EXACT; the issue InventoryTxn(s) and the JE
      share the shipment as source and are committed together (all or nothing).
    * RESERVATION RELIEF (SC4, D-P12b-5): shipping relieves the SO line's
      qty_reserved by exactly the shipped qty, which keeps _reserved_by_other_open_sos
      accurate — the on-hand issue and the relief move together so a second open SO's
      availability is conserved (without the relief it would understate by the shipped
      qty).
    * PARTIAL-SHIP ACCUMULATION (SC3): two shipments against one SO line accumulate
      qty_shipped; a ship that would push qty_shipped past qty_ordered is rejected 422.
    * NEGATIVE SPACE: over-pick beyond bin on-hand → 4xx; a staging over-issue at ship
      → 422; picking a non-stock (item_id NULL) line → 422; re-shipping a shipped
      shipment → 409 with NO second reservation relief.
    * CONTROL↔SUBLEDGER TIE (mirrors verify_reports.py, not merely "TB nets zero"):
      the ship's move of the 1130 control account equals the move of the inventory
      subledger valuation (Σ qty*moving_avg across on-hand) to the cent.
    * CONCURRENCY (THE CRUX): post_issue LOCKS the item-master row FOR UPDATE before
      the per-bin floor read, so two concurrent ships drawing the same scarce staging
      bin serialize — exactly one succeeds and the staging bin never goes negative.

  THE KEEPER (11a/11b lesson): two prior phases certified GREEN while the headline
  feature was dead through the UI, because the verify script hand-fed inputs in a
  shape the router/UI never sends. This script therefore drives the service ONLY
  through the REAL PickRequest / PackRequest schemas exactly as the pick/pack/ship
  routes construct them — never hand-assembling ShipmentLine legs nor calling
  post_issue directly for the headline assertions.

  None of that can be proven by the pure unit tests, and the backend live-DB pytest
  harness is broken (D-P7-4), so DB-dependent tests skip under plain ``pytest``.
  Verifiable truth must come from a STANDALONE run against LIVE Postgres. This script
  stands up its own async engine + sessionmaker from the ``POSTGRES_*`` environment
  variables — it deliberately does NOT import the broken test conftest fixtures — and
  drives the REAL gelato service functions end-to-end.

HOW TO RUN (the compose ``db`` service is not host-published):
  podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db api
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_gelato_ship.py

SCENARIO (each line prints PASS:/FAIL:; exits non-zero on any FAIL):
  (a) HAPPY PATH (SC2/SC3/SC4): build_pick_list → execute_pick (real PickRequest with
      PickLineRequests + staging_bin_id) → execute_pack → execute_ship the full order.
      The location total falls by exactly the shipped qty and the staging bin nets to
      zero at the end.
  (b) BALANCED JE (SC4, SYERP-13 AC1): exactly one JournalEntry source_type=
      'gelato_shipment' for the shipment; Dr 5100 == Cr 1130 == Σ(qty*moving_avg)
      Decimal-EXACT; the issue InventoryTxn(s) and the JE share the shipment as source
      and were committed together.
  (c) RESERVATION RELIEF (D-P12b-5): a SECOND open SO's availability (via the same
      _reserved_by_other_open_sos calc confirm uses) is captured before/after shipping
      the first SO; the first SO line's qty_reserved falls by EXACTLY the shipped qty,
      the reservation held by the first (as the "other" open SO) falls by exactly that
      too, and the second SO's availability is CONSERVED (the relief exactly offsets
      the on-hand issue — without it availability would understate by the shipped qty).
  (d) PARTIAL-SHIP ACCUMULATION (SC3): two shipments against ONE SO line accumulate
      qty_shipped (6 then 4 == 10); a further ship (1) that would push qty_shipped past
      qty_ordered raises 422.
  (e) NEGATIVE SPACE: over-pick beyond bin on-hand → 4xx; a ship over-issuing the
      staging bin (drained after pack) → 422; picking a non-stock (item_id NULL) SO
      line → 422; re-shipping an already-shipped shipment → 409, with qty_reserved NOT
      dropping a second time (no double relief).
  (f) CONTROL↔SUBLEDGER TIE (mirrors verify_reports.py): after a ship, the change in
      the 1130 control balance (Σ debit−credit of its JournalLines) equals the change
      in the inventory subledger valuation (Σ qty*moving_avg across on-hand), Decimal-
      EXACT — NOT merely a trial balance that nets to zero.
  (g) CONCURRENCY BARRIER (THE CRUX): two execute_ship on INDEPENDENT sessions, both
      drawing the same staging bin seeded so only ONE can succeed, synchronized on
      asyncio.Barrier(2) + asyncio.gather. Exactly one succeeds and one is rejected;
      the staging bin never goes negative. Repeated several iterations.

LOAD-BEARING PROOF (concurrency, scenario g) — HOW TO REPRODUCE THE FAIL:
  The serialization point under test is the item-master FOR UPDATE lock. The ship
  path is guarded in TWO places: execute_ship() itself locks the distinct item rows
  FOR UPDATE up front (shipments.py step 3), AND post_issue() re-locks the item row
  before its per-bin floor read (inventory.py). To observe a genuine over-issue you
  must remove BOTH locks: comment out the ``select(InventoryItem.id)...
  .with_for_update()`` in app/modules/syerp/service/inventory.py::post_issue AND the
  matching up-front lock loop in app/modules/gelato/service/shipments.py::execute_ship,
  rerun this script, and scenario (g) FAILS (both ships succeed and the staging bin
  goes negative). Restore both and it PASSES. This was exercised once during
  development; the code is left in the LOCKED (passing) state.

The script uses uniquely-suffixed throwaway partners / SYERP items / GELATO bins /
sales orders / shipments and CLEANS UP after itself (shipment lines -> shipments ->
gelato_shipment journal lines/entries -> SO lines -> sales orders -> inventory txns ->
bins -> inventory items -> partners) in a finally block, so it is safe to re-run. The
seeded "Main" stock location and the 1130/5100 GL accounts are reused and left in
place (real deploy state).
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Make the backend root importable when run as a bare `python scripts/verify_gelato_ship.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app — the sibling verify_*.py scripts require that env var).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the central model aggregator FIRST so Base.metadata is fully populated
# (the gelato_shipment FKs reference crumb_* / syerp_* tables that must be registered
# before the FKs resolve — the Task-8 lesson from MOUSSE).
import app.core.models  # noqa: F401
from app.modules.crumb.models import SalesOrder, SalesOrderLine
from app.modules.crumb.schemas import SalesOrderCreate, SalesOrderLineCreate
from app.modules.crumb.service import confirm_sales_order, create_sales_order
from app.modules.crumb.service.sales_orders import _reserved_by_other_open_sos
from app.modules.gelato.models import Bin, Shipment, ShipmentLine
from app.modules.gelato.schemas import (
    BinCreate,
    PackRequest,
    PickLineRequest,
    PickRequest,
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
from app.modules.gelato.schemas import PutawayRequest
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME, seed_default_location
from app.modules.syerp.models import (
    GLAccount,
    InventoryItem,
    InventoryTxn,
    JournalEntry,
    JournalLine,
    Partner,
    StockLocation,
)
from app.modules.syerp.schemas import InventoryItemCreate, PartnerCreate
from app.modules.syerp.service import (
    create_item,
    get_item_on_hand,
    get_item_onhand,
    post_receipt,
)
from app.modules.syerp.service.partners import create_partner

_COST_QUANTUM = Decimal("0.000001")

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


# ---------------------------------------------------------------------------
# Registries for the finally cleanup (populated as fixtures are created)
# ---------------------------------------------------------------------------


class Registry:
    """Throwaway-row id registries swept, in FK-safe order, by _cleanup."""

    def __init__(self) -> None:
        self.partner_ids: set[str] = set()
        self.item_ids: set[str] = set()
        self.bin_ids: set[int] = set()
        self.so_ids: set[str] = set()
        self.shipment_ids: set[int] = set()


# ---------------------------------------------------------------------------
# Fixture builders + independent oracles (the assertion's OWN truth)
# ---------------------------------------------------------------------------


async def _make_item(session_factory, unique: str, tag: str) -> str:
    """Create a throwaway SYERP InventoryItem (no PLUM link) via the REAL service."""
    async with session_factory() as session:
        item = await create_item(
            session,
            InventoryItemCreate(name=f"VERIFY-GELATO-SHIP {tag} {unique}", unit_of_measure="ea"),
        )
        return item.id


async def _make_bin(session_factory, location_id: int, code: str) -> int:
    """Create a throwaway GELATO bin via the REAL create_bin service; return its id."""
    async with session_factory() as session:
        bin_ = await create_bin(session, BinCreate(location_id=location_id, code=code))
        return bin_.id


async def _make_customer(session_factory, unique: str, tag: str) -> str:
    """Create a SYERP customer partner via the REAL service; return its id."""
    async with session_factory() as session:
        partner = await create_partner(
            session, PartnerCreate(name=f"VERIFY-GELATO-SHIP {tag} {unique}", is_customer=True)
        )
        return partner.id


async def _item_moving_avg(session_factory, item_id: str) -> Decimal:
    """Read the item's current moving_avg_cost straight from the master row (oracle)."""
    async with session_factory() as session:
        return (
            await session.execute(
                select(InventoryItem.moving_avg_cost).where(InventoryItem.id == item_id)
            )
        ).scalar()


async def _location_total(session_factory, item_id: str, location_id: int) -> Decimal:
    """The item's per-location on-hand as get_item_onhand derives it (missing row == 0)."""
    async with session_factory() as session:
        onhand = await get_item_onhand(session, item_id)
    return next(
        (loc.quantity for loc in onhand.locations if loc.location_id == location_id),
        Decimal("0"),
    )


async def _account_balance(session_factory, code: str) -> Decimal:
    """
    Σ (debit − credit) over every JournalLine posted to the GL account `code`.

    The signed control-account balance derived straight from the append-only
    journal — the independent oracle the ship's Cr 1130 must move, mirroring the
    2110 control read verify_reports.py ties the AP subledger against.
    """
    async with session_factory() as session:
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


async def _subledger_valuation(session_factory, item_id: str) -> Decimal:
    """
    The inventory subledger valuation for one item: on-hand qty * moving_avg_cost.

    The subledger side of the control↔subledger tie (SYERP values on-hand at the
    item's moving average — get_item_onhand.onhand_value). Computed here as the
    scalar on-hand times the current average so the tie can be delta-checked
    around a single ship in isolation.
    """
    async with session_factory() as session:
        on_hand = await get_item_on_hand(session, item_id)
    avg = await _item_moving_avg(session_factory, item_id)
    return on_hand * avg


async def _so_line_reserved(session_factory, line_id: str) -> Decimal:
    """The live qty_reserved on one SO line (oracle for reservation relief)."""
    async with session_factory() as session:
        return (
            await session.execute(
                select(SalesOrderLine.qty_reserved).where(SalesOrderLine.id == line_id)
            )
        ).scalar()


async def _so_line_shipped(session_factory, line_id: str) -> Decimal:
    """The live qty_shipped on one SO line (oracle for double-stamp detection)."""
    async with session_factory() as session:
        return (
            await session.execute(
                select(SalesOrderLine.qty_shipped).where(SalesOrderLine.id == line_id)
            )
        ).scalar()


async def _shipment_je_count(session_factory, shipment_id: int) -> int:
    """Count the COGS journal entries source-linked to one shipment (oracle for
    double-post detection — a shipment must post EXACTLY one Dr 5100 / Cr 1130 JE)."""
    async with session_factory() as session:
        return len(
            (
                await session.execute(
                    select(JournalEntry.id).where(
                        JournalEntry.source_type == "gelato_shipment",
                        JournalEntry.source_id == str(shipment_id),
                    )
                )
            )
            .scalars()
            .all()
        )


async def _seed_confirmed_order(
    session_factory,
    reg: Registry,
    unique: str,
    tag: str,
    actor_id: str,
    location_id: int,
    cust_id: str,
    *,
    receipts: list[tuple[Decimal, Decimal]],
    into_bin_qty: Decimal,
    order_qty: Decimal,
) -> dict:
    """
    Seed one shippable order: an item with receipts (moving its moving_avg off 1.0),
    a pick bin holding `into_bin_qty`, a staging bin, and a CONFIRMED single-line SO
    ordering `order_qty`. Returns the handles the scenario drives pick/pack/ship with.
    """
    item_id = await _make_item(session_factory, unique, tag)
    reg.item_ids.add(item_id)
    for qty, cost in receipts:
        async with session_factory() as session:
            await post_receipt(session, item_id, location_id, qty, cost, actor_id)

    pick_bin = await _make_bin(session_factory, location_id, f"{tag}-PICK-{unique}")
    staging_bin = await _make_bin(session_factory, location_id, f"{tag}-STAGE-{unique}")
    reg.bin_ids.update({pick_bin, staging_bin})

    async with session_factory() as session:
        await execute_putaway(
            session,
            PutawayRequest(
                item_id=item_id, location_id=location_id, to_bin_id=pick_bin,
                qty=into_bin_qty, from_bin_id=None,
            ),
            actor_id,
        )

    async with session_factory() as session:
        so = await create_sales_order(
            session,
            SalesOrderCreate(
                partner_id=cust_id,
                lines=[
                    SalesOrderLineCreate(
                        item_id=item_id, qty_ordered=order_qty, unit_price=Decimal("20")
                    )
                ],
            ),
            actor_id,
        )
    reg.so_ids.add(so.id)
    async with session_factory() as session:
        confirmed = await confirm_sales_order(session, so.id, actor_id)

    return {
        "item_id": item_id,
        "pick_bin": pick_bin,
        "staging_bin": staging_bin,
        "so_id": so.id,
        "so_line_id": confirmed.lines[0].id,
        "moving_avg": await _item_moving_avg(session_factory, item_id),
    }


async def run() -> None:  # noqa: C901 - one long linear verification scenario
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    actor_id = str(uuid.uuid4())  # stand-in for the acting user
    unique = uuid.uuid4().hex[:8]
    reg = Registry()

    try:
        # Seed (idempotent) + reuse the "Main" stock location for on-hand receipts.
        async with session_factory() as session:
            await seed_default_location(session)
        async with session_factory() as session:
            main_rows = (
                await session.execute(
                    select(StockLocation).where(StockLocation.name == DEFAULT_LOCATION_NAME)
                )
            ).scalars().all()
        check(
            "setup: exactly one seeded 'Main' stock location resolves",
            len(main_rows) == 1,
            f"main={len(main_rows)}",
        )
        main_id = main_rows[0].id

        cust_id = await _make_customer(session_factory, unique, "CUST")
        reg.partner_ids.add(cust_id)

        # ===================================================================
        # (a) HAPPY PATH — pick → pack → ship the full order (SC2/SC3/SC4)
        # ===================================================================
        # Two receipts (100@6 then 100@9 → moving_avg 7.5, off 1.0) so COGS is
        # non-trivial. Pick bin holds 50; order/ship 8.
        a = await _seed_confirmed_order(
            session_factory, reg, unique, "A", actor_id, main_id, cust_id,
            receipts=[(Decimal("100"), Decimal("6")), (Decimal("100"), Decimal("9"))],
            into_bin_qty=Decimal("50"), order_qty=Decimal("8"),
        )
        check(
            "(a/SC4) the fixture receipt moved moving_avg_cost off 1.0 "
            "(100@6 then 100@9 → weighted 7.500000) so COGS math is non-trivial",
            a["moving_avg"] == Decimal("7.500000"),
            f"moving_avg={a['moving_avg']!r}",
        )

        # build_pick_list — the REAL pick suggestion screen.
        async with session_factory() as session:
            pick_list = await build_pick_list(session, a["so_id"])
        pl_line = next(
            (ln for ln in pick_list.lines if ln.sales_order_line_id == a["so_line_id"]), None
        )
        check(
            "(a/SC2) build_pick_list surfaces the stock line with the pick bin as a "
            "candidate (on_hand 50) and suggests it (covers the remaining 8)",
            pl_line is not None
            and pl_line.suggested_from_bin_id == a["pick_bin"]
            and any(b.bin_id == a["pick_bin"] and b.on_hand == Decimal("50")
                    for b in pl_line.available_bins),
            f"line={pl_line!r}",
        )

        loc_before = await _location_total(session_factory, a["item_id"], main_id)

        # execute_pick — REAL PickRequest with PickLineRequest(s) + staging_bin_id,
        # exactly as POST /gelato/shipments/pick constructs it (the 11a/11b keeper).
        async with session_factory() as session:
            picked = await execute_pick(
                session,
                PickRequest(
                    sales_order_id=a["so_id"],
                    staging_bin_id=a["staging_bin"],
                    lines=[
                        PickLineRequest(
                            sales_order_line_id=a["so_line_id"],
                            from_bin_id=a["pick_bin"],
                            qty=Decimal("8"),
                        )
                    ],
                ),
                actor_id,
            )
        a_shipment_id = picked.id
        reg.shipment_ids.add(a_shipment_id)

        loc_after_pick = await _location_total(session_factory, a["item_id"], main_id)
        check(
            "(a/SC2) pick is net-zero at the location (a bin-aware move into staging "
            "leaves the per-location total unchanged == 200)",
            loc_after_pick == loc_before == Decimal("200"),
            f"before={loc_before!r} after_pick={loc_after_pick!r}",
        )

        async with session_factory() as session:
            await execute_pack(session, a_shipment_id, PackRequest(), actor_id)
        async with session_factory() as session:
            shipped = await execute_ship(session, a_shipment_id, actor_id)

        loc_after_ship = await _location_total(session_factory, a["item_id"], main_id)
        async with session_factory() as session:
            staging_final = await get_bin_on_hand(session, a["item_id"], main_id, a["staging_bin"])
        check(
            "(a/SC4) after ship the location total fell by exactly the shipped qty "
            "(200 → 192) and the staging bin nets to zero (8 in at pick, 8 out at ship)",
            shipped.status == "shipped"
            and loc_before - loc_after_ship == Decimal("8")
            and loc_after_ship == Decimal("192")
            and staging_final == Decimal("0"),
            f"status={shipped.status!r} loc_before={loc_before!r} loc_after={loc_after_ship!r} "
            f"staging={staging_final!r}",
        )

        # ===================================================================
        # (b) BALANCED JE — one COGS entry, Dr 5100 == Cr 1130 == Σ qty*avg
        # ===================================================================
        expected_cogs = (Decimal("8") * a["moving_avg"]).quantize(_COST_QUANTUM, ROUND_HALF_UP)
        async with session_factory() as session:
            je_rows = (
                await session.execute(
                    select(JournalEntry).where(
                        JournalEntry.source_type == "gelato_shipment",
                        JournalEntry.source_id == str(a_shipment_id),
                    )
                )
            ).scalars().all()
        check(
            "(b/SC4) the ship posts EXACTLY ONE JournalEntry source_type='gelato_shipment' "
            "for this shipment",
            len(je_rows) == 1,
            f"entries={len(je_rows)}",
        )
        if je_rows:
            entry = je_rows[0]
            async with session_factory() as session:
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
            check(
                "(b/SC4 CRUX) the COGS entry balances Decimal-EXACT: Dr 5100 == Cr 1130 == "
                "Σ(qty*moving_avg) == 8 * 7.5 == 60.000000",
                Decimal(dr_5100) == Decimal(cr_1130) == expected_cogs,
                f"dr_5100={dr_5100!r} cr_1130={cr_1130!r} expected={expected_cogs!r}",
            )

        # The issue leg(s) and the JE share the shipment as source and rode one commit.
        async with session_factory() as session:
            issue_txns = (
                await session.execute(
                    select(InventoryTxn).where(
                        InventoryTxn.source_type == "gelato_shipment",
                        InventoryTxn.source_id == str(a_shipment_id),
                        InventoryTxn.txn_type == "issue",
                    )
                )
            ).scalars().all()
        check(
            "(b/SC4) the issue InventoryTxn(s) and the JE share the shipment as source and "
            "were committed together (exactly one -8 issue leg, and the shipment carries its "
            "journal_entry_id — the whole ship is atomic)",
            len(issue_txns) == 1
            and issue_txns[0].quantity == Decimal("-8")
            and shipped.journal_entry_id is not None
            and len(je_rows) == 1
            and shipped.journal_entry_id == je_rows[0].id,
            f"issue_legs={len(issue_txns)} qty={issue_txns[0].quantity if issue_txns else None!r} "
            f"shipment.je={shipped.journal_entry_id!r}",
        )

        # ===================================================================
        # (c) RESERVATION RELIEF — accuracy, not just "decreased" (D-P12b-5)
        # ===================================================================
        # One scarce item, on-hand 10 (10 into the pick bin). Two open SOs each order 5
        # → SO1 reserves 5, SO2 reserves 5. Ship SO1 fully (5) and prove the second SO's
        # availability is CONSERVED because the relief exactly offsets the on-hand issue.
        c = await _seed_confirmed_order(
            session_factory, reg, unique, "C", actor_id, main_id, cust_id,
            receipts=[(Decimal("10"), Decimal("4"))],
            into_bin_qty=Decimal("10"), order_qty=Decimal("5"),
        )
        async with session_factory() as session:
            so_c2 = await create_sales_order(
                session,
                SalesOrderCreate(
                    partner_id=cust_id,
                    lines=[
                        SalesOrderLineCreate(
                            item_id=c["item_id"], qty_ordered=Decimal("5"),
                            unit_price=Decimal("20"),
                        )
                    ],
                ),
                actor_id,
            )
        reg.so_ids.add(so_c2.id)
        async with session_factory() as session:
            c2_conf = await confirm_sales_order(session, so_c2.id, actor_id)
        check(
            "(c/setup) both open SOs reserved against the scarce item (SO1 5, SO2 5 of "
            "on-hand 10) — the item is fully reserved before the ship",
            await _so_line_reserved(session_factory, c["so_line_id"]) == Decimal("5")
            and c2_conf.lines[0].qty_reserved == Decimal("5"),
        )

        # Availability the SECOND SO sees = on_hand − reserved-by-OTHER-open-SOs (excl SO2).
        async def _avail_for_c2() -> tuple[Decimal, Decimal, Decimal]:
            async with session_factory() as session:
                on_hand = await get_item_on_hand(session, c["item_id"])
                reserved_others = await _reserved_by_other_open_sos(
                    session, c["item_id"], so_c2.id
                )
            return on_hand, reserved_others, on_hand - reserved_others

        oh_before, others_before, avail_before = await _avail_for_c2()

        # Pick / pack / ship SO1 for its full 5.
        async with session_factory() as session:
            c_pick = await execute_pick(
                session,
                PickRequest(
                    sales_order_id=c["so_id"], staging_bin_id=c["staging_bin"],
                    lines=[PickLineRequest(
                        sales_order_line_id=c["so_line_id"], from_bin_id=c["pick_bin"],
                        qty=Decimal("5"),
                    )],
                ),
                actor_id,
            )
        reg.shipment_ids.add(c_pick.id)
        async with session_factory() as session:
            await execute_pack(session, c_pick.id, PackRequest(), actor_id)
        async with session_factory() as session:
            await execute_ship(session, c_pick.id, actor_id)

        c1_reserved_after = await _so_line_reserved(session_factory, c["so_line_id"])
        oh_after, others_after, avail_after = await _avail_for_c2()
        # Counterfactual (buggy) availability had the relief NOT happened: on_hand still
        # dropped by 5 but reserved-by-others would still be 5 → it would understate by 5.
        avail_after_no_relief = oh_after - others_before
        check(
            "(c/D-P12b-5) shipping SO1 relieves its line's qty_reserved by EXACTLY the "
            "shipped qty (5 → 0) and drops the reservation SO2 sees from that 'other' open "
            "SO by exactly 5 (accurate, not merely 'decreased')",
            c1_reserved_after == Decimal("0")
            and others_before - others_after == Decimal("5"),
            f"c1_reserved={c1_reserved_after!r} others {others_before!r}->{others_after!r}",
        )
        check(
            "(c/D-P12b-5) the second SO's availability is CONSERVED across the ship "
            "(the relief exactly offsets the on-hand issue: Δon_hand −5 == Δreserved_others "
            "−5, so avail 5 → 5) — and the relief RAISED it by exactly the shipped qty vs the "
            "no-relief counterfactual (5 vs 0)",
            avail_before == avail_after == Decimal("5")
            and oh_before - oh_after == Decimal("5")
            and avail_after - avail_after_no_relief == Decimal("5"),
            f"avail {avail_before!r}->{avail_after!r} oh {oh_before!r}->{oh_after!r} "
            f"no_relief={avail_after_no_relief!r}",
        )

        # ===================================================================
        # (d) PARTIAL-SHIP ACCUMULATION — two ships accrue, third over-ships 422
        # ===================================================================
        # One SO line ordered 10; pick bin holds 20. Ship 6 then 4 (accrues to 10); a
        # third ship of 1 would push qty_shipped past qty_ordered → 422.
        d = await _seed_confirmed_order(
            session_factory, reg, unique, "D", actor_id, main_id, cust_id,
            receipts=[(Decimal("20"), Decimal("5"))],
            into_bin_qty=Decimal("20"), order_qty=Decimal("10"),
        )

        async def _ship_portion(qty: Decimal) -> int:
            """Pick `qty` of the D order into a fresh staging bin, pack, ship; return id."""
            stage = await _make_bin(
                session_factory, main_id, f"D-STAGE-{qty}-{uuid.uuid4().hex[:6]}"
            )
            reg.bin_ids.add(stage)
            async with session_factory() as session:
                sh = await execute_pick(
                    session,
                    PickRequest(
                        sales_order_id=d["so_id"], staging_bin_id=stage,
                        lines=[PickLineRequest(
                            sales_order_line_id=d["so_line_id"], from_bin_id=d["pick_bin"],
                            qty=qty,
                        )],
                    ),
                    actor_id,
                )
            reg.shipment_ids.add(sh.id)
            async with session_factory() as session:
                await execute_pack(session, sh.id, PackRequest(), actor_id)
            async with session_factory() as session:
                await execute_ship(session, sh.id, actor_id)
            return sh.id

        await _ship_portion(Decimal("6"))
        await _ship_portion(Decimal("4"))
        async with session_factory() as session:
            d_line = await session.get(SalesOrderLine, d["so_line_id"])
            d_qty_shipped = d_line.qty_shipped
        check(
            "(d/SC3) two shipments against ONE SO line accumulate qty_shipped "
            "(6 then 4 == 10 == qty_ordered)",
            d_qty_shipped == Decimal("10"),
            f"qty_shipped={d_qty_shipped!r}",
        )

        # A third ship of 1 more would push qty_shipped (10) past qty_ordered (10) → 422.
        d_stage3 = await _make_bin(session_factory, main_id, f"D-STAGE3-{unique}")
        reg.bin_ids.add(d_stage3)
        async with session_factory() as session:
            d_sh3 = await execute_pick(
                session,
                PickRequest(
                    sales_order_id=d["so_id"], staging_bin_id=d_stage3,
                    lines=[PickLineRequest(
                        sales_order_line_id=d["so_line_id"], from_bin_id=d["pick_bin"],
                        qty=Decimal("1"),
                    )],
                ),
                actor_id,
            )
        reg.shipment_ids.add(d_sh3.id)
        async with session_factory() as session:
            await execute_pack(session, d_sh3.id, PackRequest(), actor_id)
        try:
            async with session_factory() as session:
                await execute_ship(session, d_sh3.id, actor_id)
            check("(d/SC3) an over-ship past qty_ordered is rejected", False,
                  "ship succeeded past qty_ordered")
        except HTTPException as exc:
            check(
                "(d/SC3) a ship that would push qty_shipped past qty_ordered is rejected 422",
                exc.status_code == 422,
                f"status={exc.status_code}",
            )

        # ===================================================================
        # (e) NEGATIVE SPACE — each raises the right status
        # ===================================================================
        # (e1) over-pick beyond bin on-hand → 4xx (post_putaway per-bin floor).
        e = await _seed_confirmed_order(
            session_factory, reg, unique, "E", actor_id, main_id, cust_id,
            receipts=[(Decimal("10"), Decimal("5"))],
            into_bin_qty=Decimal("4"), order_qty=Decimal("10"),
        )
        try:
            async with session_factory() as session:
                await execute_pick(
                    session,
                    PickRequest(
                        sales_order_id=e["so_id"], staging_bin_id=e["staging_bin"],
                        lines=[PickLineRequest(
                            sales_order_line_id=e["so_line_id"], from_bin_id=e["pick_bin"],
                            qty=Decimal("5"),  # bin holds only 4
                        )],
                    ),
                    actor_id,
                )
            check("(e1) over-pick beyond bin on-hand is rejected", False, "pick succeeded")
        except HTTPException as exc:
            check(
                "(e1/SC2) an over-pick (5 from a pick bin holding 4) is rejected 4xx "
                "(the per-bin floor guard)",
                400 <= exc.status_code < 500,
                f"status={exc.status_code}",
            )

        # (e2) ship over-issuing the staging bin → 422. Pick 4 into staging (staging 4,
        #      ShipmentLine.qty 4), pack, then DRAIN the staging bin (putaway 4 out) so
        #      the staged qty exceeds the staging on-hand → ship floor-rejects 422.
        async with session_factory() as session:
            e2_pick = await execute_pick(
                session,
                PickRequest(
                    sales_order_id=e["so_id"], staging_bin_id=e["staging_bin"],
                    lines=[PickLineRequest(
                        sales_order_line_id=e["so_line_id"], from_bin_id=e["pick_bin"],
                        qty=Decimal("4"),
                    )],
                ),
                actor_id,
            )
        reg.shipment_ids.add(e2_pick.id)
        async with session_factory() as session:
            await execute_pack(session, e2_pick.id, PackRequest(), actor_id)
        # Drain the staging bin back into the pick bin so staging on-hand (0) < staged qty (4).
        async with session_factory() as session:
            await execute_putaway(
                session,
                PutawayRequest(
                    item_id=e["item_id"], location_id=main_id, to_bin_id=e["pick_bin"],
                    qty=Decimal("4"), from_bin_id=e["staging_bin"],
                ),
                actor_id,
            )
        try:
            async with session_factory() as session:
                await execute_ship(session, e2_pick.id, actor_id)
            check("(e2) a ship over-issuing the staging bin is rejected", False,
                  "ship succeeded over the staging floor")
        except HTTPException as exc:
            check(
                "(e2/SC4) shipping a packed shipment whose staging bin was drained below the "
                "staged qty is rejected 422 (the per-bin over-issue floor)",
                exc.status_code == 422,
                f"status={exc.status_code}",
            )

        # (e3) picking a non-stock (item_id NULL) SO line → 422.
        async with session_factory() as session:
            so_ns = await create_sales_order(
                session,
                SalesOrderCreate(
                    partner_id=cust_id,
                    lines=[
                        SalesOrderLineCreate(
                            description="Non-stock service", qty_ordered=Decimal("1"),
                            unit_price=Decimal("9"),
                        )
                    ],
                ),
                actor_id,
            )
        reg.so_ids.add(so_ns.id)
        async with session_factory() as session:
            ns_conf = await confirm_sales_order(session, so_ns.id, actor_id)
        ns_line_id = ns_conf.lines[0].id
        ns_stage = await _make_bin(session_factory, main_id, f"NS-STAGE-{unique}")
        ns_pick = await _make_bin(session_factory, main_id, f"NS-PICK-{unique}")
        reg.bin_ids.update({ns_stage, ns_pick})
        try:
            async with session_factory() as session:
                await execute_pick(
                    session,
                    PickRequest(
                        sales_order_id=so_ns.id, staging_bin_id=ns_stage,
                        lines=[PickLineRequest(
                            sales_order_line_id=ns_line_id, from_bin_id=ns_pick,
                            qty=Decimal("1"),
                        )],
                    ),
                    actor_id,
                )
            check("(e3) picking a non-stock line is rejected", False, "pick succeeded")
        except HTTPException as exc:
            check(
                "(e3/SC2) picking a non-stock (item_id NULL) SO line is rejected 422 "
                "(a free-text line cannot be bin-picked)",
                exc.status_code == 422,
                f"status={exc.status_code}",
            )

        # (e4) re-ship an already-shipped shipment → 409, with NO double reservation relief.
        reserved_before_reship = await _so_line_reserved(session_factory, a["so_line_id"])
        try:
            async with session_factory() as session:
                await execute_ship(session, a_shipment_id, actor_id)
            check("(e4) re-shipping a shipped shipment is rejected", False, "re-ship succeeded")
        except HTTPException as exc:
            check(
                "(e4/SC4) re-shipping an already-shipped shipment is rejected 409 (the FSM "
                "blocks double-ship)",
                exc.status_code == 409,
                f"status={exc.status_code}",
            )
        reserved_after_reship = await _so_line_reserved(session_factory, a["so_line_id"])
        check(
            "(e4/D-P12b-5) the rejected re-ship did NOT relieve the reservation a second time "
            "(qty_reserved unchanged across the 409)",
            reserved_before_reship == reserved_after_reship,
            f"reserved {reserved_before_reship!r}->{reserved_after_reship!r}",
        )

        # ===================================================================
        # (f) CONTROL↔SUBLEDGER TIE (mirrors verify_reports.py)
        # ===================================================================
        # A fresh order shipped in isolation: the change in the 1130 control balance
        # equals the change in the item's inventory subledger valuation, to the cent.
        f = await _seed_confirmed_order(
            session_factory, reg, unique, "F", actor_id, main_id, cust_id,
            receipts=[(Decimal("50"), Decimal("8"))],
            into_bin_qty=Decimal("20"), order_qty=Decimal("10"),
        )
        bal_1130_before = await _account_balance(session_factory, "1130")
        subval_before = await _subledger_valuation(session_factory, f["item_id"])
        async with session_factory() as session:
            f_pick = await execute_pick(
                session,
                PickRequest(
                    sales_order_id=f["so_id"], staging_bin_id=f["staging_bin"],
                    lines=[PickLineRequest(
                        sales_order_line_id=f["so_line_id"], from_bin_id=f["pick_bin"],
                        qty=Decimal("10"),
                    )],
                ),
                actor_id,
            )
        reg.shipment_ids.add(f_pick.id)
        async with session_factory() as session:
            await execute_pack(session, f_pick.id, PackRequest(), actor_id)
        async with session_factory() as session:
            await execute_ship(session, f_pick.id, actor_id)
        bal_1130_after = await _account_balance(session_factory, "1130")
        subval_after = await _subledger_valuation(session_factory, f["item_id"])
        expected_move = (Decimal("10") * f["moving_avg"]).quantize(_COST_QUANTUM, ROUND_HALF_UP)
        check(
            "(f) CONTROL↔SUBLEDGER TIE: the ship moves the 1130 control balance and the "
            "inventory subledger valuation by the SAME amount, Decimal-EXACT "
            "(Δ1130 == Δsubledger == −(10 * 8) == −80.000000) — not merely 'TB nets zero'",
            bal_1130_after - bal_1130_before == subval_after - subval_before == -expected_move,
            f"Δ1130={bal_1130_after - bal_1130_before!r} "
            f"Δsub={subval_after - subval_before!r} expected=-{expected_move!r}",
        )

        # ===================================================================
        # (g) CONCURRENCY BARRIER (THE CRUX) — two ships cannot over-issue staging
        # ===================================================================
        await run_concurrency(session_factory, reg, unique, actor_id, main_id, cust_id)

        # ===================================================================
        # (h) SAME-SHIPMENT DOUBLE-SHIP — one shipment shipped twice concurrently
        #     against an AMPLE staging bin must post COGS exactly once
        # ===================================================================
        await run_same_shipment_double_ship(
            session_factory, reg, unique, actor_id, main_id, cust_id
        )

    finally:
        await _cleanup(session_factory, reg)
        await engine.dispose()


# ---------------------------------------------------------------------------
# (g) Concurrency scenario — the item-master FOR UPDATE lock is what makes this hold
# ---------------------------------------------------------------------------
#
# execute_ship locks the contended InventoryItem rows FOR UPDATE up front and
# post_issue re-locks the item row before its per-bin floor read, so two concurrent
# ships drawing the SAME staging bin serialize: the first issues, commits (releasing
# the lock), and the second then re-reads the now-depleted staging bin and the per-bin
# floor guard rejects it. Removing BOTH locks lets both read the original staging
# on-hand under READ COMMITTED and both draw their full qty — driving the staging bin
# NEGATIVE (over-issue) — i.e. this scenario FAILS. A sequential test cannot surface
# that race; only firing both with asyncio.gather on TWO INDEPENDENT sessions can.
# Repeated over several iterations for confidence.


async def run_concurrency(
    session_factory, reg: Registry, unique: str, actor_id: str, main_id: int, cust_id: str
) -> None:
    """
    For each iteration: a fresh item with a staging bin holding EXACTLY 5, and two
    packed shipments (distinct SOs, distinct SO lines) each staged to ship 5. Fire
    both execute_ship concurrently on INDEPENDENT sessions and prove EXACTLY ONE
    succeeds and the other is rejected — the staging bin never goes negative and ends
    at 0 (exactly one 5-unit issue).
    """
    iterations = 5
    all_ok = True
    detail = ""

    for i in range(iterations):
        item_id = await _make_item(session_factory, unique, f"G{i}")
        reg.item_ids.add(item_id)
        async with session_factory() as session:
            await post_receipt(session, item_id, main_id, Decimal("10"), Decimal("5"), actor_id)
        pick_bin = await _make_bin(session_factory, main_id, f"G{i}-PICK-{unique}")
        staging_bin = await _make_bin(session_factory, main_id, f"G{i}-STAGE-{unique}")
        reg.bin_ids.update({pick_bin, staging_bin})
        async with session_factory() as session:
            await execute_putaway(
                session,
                PutawayRequest(
                    item_id=item_id, location_id=main_id, to_bin_id=pick_bin,
                    qty=Decimal("10"), from_bin_id=None,
                ),
                actor_id,
            )

        # Two SOs each ordering 5; pick each 5 into the SAME staging bin, pack both.
        shipment_ids: list[int] = []
        for k in range(2):
            async with session_factory() as session:
                so = await create_sales_order(
                    session,
                    SalesOrderCreate(
                        partner_id=cust_id,
                        lines=[SalesOrderLineCreate(
                            item_id=item_id, qty_ordered=Decimal("5"), unit_price=Decimal("20")
                        )],
                    ),
                    actor_id,
                )
            reg.so_ids.add(so.id)
            async with session_factory() as session:
                conf = await confirm_sales_order(session, so.id, actor_id)
            so_line_id = conf.lines[0].id
            async with session_factory() as session:
                sh = await execute_pick(
                    session,
                    PickRequest(
                        sales_order_id=so.id, staging_bin_id=staging_bin,
                        lines=[PickLineRequest(
                            sales_order_line_id=so_line_id, from_bin_id=pick_bin, qty=Decimal("5")
                        )],
                    ),
                    actor_id,
                )
            reg.shipment_ids.add(sh.id)
            shipment_ids.append(sh.id)
            async with session_factory() as session:
                await execute_pack(session, sh.id, PackRequest(), actor_id)

        # Drain the staging bin down to EXACTLY 5 so only ONE ship can succeed.
        async with session_factory() as session:
            await execute_putaway(
                session,
                PutawayRequest(
                    item_id=item_id, location_id=main_id, to_bin_id=pick_bin,
                    qty=Decimal("5"), from_bin_id=staging_bin,
                ),
                actor_id,
            )

        # Barrier makes the race deterministic: each worker owns an INDEPENDENT session,
        # pre-warms its connection, then both enter execute_ship together.
        barrier = asyncio.Barrier(2)

        async def _ship_once(shipment_id: int):
            from sqlalchemy import text

            async with session_factory() as session:
                await session.execute(text("SELECT 1"))  # pre-warm the connection
                await barrier.wait()
                return await execute_ship(session, shipment_id, actor_id)

        results = await asyncio.gather(
            _ship_once(shipment_ids[0]), _ship_once(shipment_ids[1]),
            return_exceptions=True,
        )
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]
        http_failures = [
            r for r in failures if isinstance(r, HTTPException) and 400 <= r.status_code < 500
        ]

        if not (len(successes) == 1 and len(http_failures) == 1):
            all_ok = False
            detail = (
                f"iter {i}: successes={len(successes)} "
                f"failures={[type(f).__name__ for f in failures]} "
                f"(expected exactly 1 success + 1 HTTP 4xx)"
            )
            break

        async with session_factory() as session:
            staging_final = await get_bin_on_hand(session, item_id, main_id, staging_bin)
        if staging_final < 0:
            all_ok = False
            detail = f"iter {i}: staging bin went NEGATIVE ({staging_final}) — over-issue!"
            break
        if staging_final != Decimal("0"):
            all_ok = False
            detail = f"iter {i}: staging final {staging_final} (want 0 — exactly one 5-unit issue)"
            break

    check(
        "(g/THE CRUX) two concurrent ships (each own session) drawing the SAME staging bin "
        f"seeded with EXACTLY 5 never over-issue — EXACTLY one succeeds and one is rejected "
        f"4xx, the staging bin never goes negative and ends at 0, across {iterations} "
        "iterations",
        all_ok,
        detail,
    )


# ---------------------------------------------------------------------------
# (h) Same-shipment double-ship — the shipment-row FOR UPDATE lock is what holds
# ---------------------------------------------------------------------------
#
# Scenario (g) proves two DIFFERENT shipments cannot jointly over-issue a scarce
# staging bin — but that guard is post_issue's per-bin floor read, which only bites
# when the bin is scarce. It does NOT catch shipping the SAME shipment twice against
# an AMPLE staging bin (a reused outbound-staging bin, or a partial-pack residual):
# there the floor read passes for both, and only the packed→shipped FSM gate stands
# between them and a double COGS post. execute_ship gates on shipment.status; if the
# shipment row is not locked, two concurrent ships both read 'packed' (READ COMMITTED),
# both pass the gate, and the second — after blocking on the item lock — proceeds on
# its stale status and double-issues + posts a SECOND Dr 5100 / Cr 1130 JE + double-
# relieves qty_reserved + double-stamps qty_shipped. execute_ship loading the shipment
# `select(Shipment).with_for_update()` before the gate serializes the two: the loser
# blocks, Postgres re-reads the row after the lock, it sees 'shipped', and the FSM gate
# 409s it. Delete the `.with_for_update()` on that load and this scenario FAILS
# (2 JEs, qty_shipped == 10, staging drawn twice) — mutation-proven, like (g).


async def run_same_shipment_double_ship(
    session_factory, reg: Registry, unique: str, actor_id: str, main_id: int, cust_id: str
) -> None:
    """
    A single packed shipment that PARTIALLY fulfils its SO (order 10, this shipment
    ships 5) picked into an AMPLE staging bin holding 20, fired at execute_ship TWICE
    concurrently on INDEPENDENT sessions, barrier-synced. The partial order is
    deliberate: with qty_ordered (10) > ship qty (5), execute_ship's over-ship guard
    (qty_shipped + qty > qty_ordered) canNOT incidentally reject the duplicate — so the
    ONLY thing standing between two concurrent ships and a persistent double COGS post
    is the shipment-row FOR UPDATE lock. Proves EXACTLY one ship succeeds and the
    duplicate is rejected 409, and — the real oracle — the shipment posts EXACTLY ONE
    COGS JE, stamps qty_shipped exactly once (== 5, not 10), and draws the staging bin
    exactly once (20 → 15, never 10). Without the lock this regresses to 2 JEs /
    qty_shipped 10 / staging 10 (a persistent double-post — money booked twice).
    """
    item_id = await _make_item(session_factory, unique, "H")
    reg.item_ids.add(item_id)
    async with session_factory() as session:
        await post_receipt(session, item_id, main_id, Decimal("20"), Decimal("7"), actor_id)
    pick_bin = await _make_bin(session_factory, main_id, f"H-PICK-{unique}")
    staging_bin = await _make_bin(session_factory, main_id, f"H-STAGE-{unique}")
    reg.bin_ids.update({pick_bin, staging_bin})
    async with session_factory() as session:
        await execute_putaway(
            session,
            PutawayRequest(
                item_id=item_id, location_id=main_id, to_bin_id=pick_bin,
                qty=Decimal("20"), from_bin_id=None,
            ),
            actor_id,
        )

    async with session_factory() as session:
        so = await create_sales_order(
            session,
            SalesOrderCreate(
                partner_id=cust_id,
                lines=[SalesOrderLineCreate(
                    item_id=item_id, qty_ordered=Decimal("10"), unit_price=Decimal("20")
                )],
            ),
            actor_id,
        )
    reg.so_ids.add(so.id)
    async with session_factory() as session:
        conf = await confirm_sales_order(session, so.id, actor_id)
    so_line_id = conf.lines[0].id
    # Pick 5 into the AMPLE staging bin (which keeps 15 spare on-hand after the move),
    # then pack — so the staging floor read can NEVER be what rejects the duplicate ship.
    async with session_factory() as session:
        sh = await execute_pick(
            session,
            PickRequest(
                sales_order_id=so.id, staging_bin_id=staging_bin,
                lines=[PickLineRequest(
                    sales_order_line_id=so_line_id, from_bin_id=pick_bin, qty=Decimal("5")
                )],
            ),
            actor_id,
        )
    reg.shipment_ids.add(sh.id)
    async with session_factory() as session:
        await execute_pack(session, sh.id, PackRequest(), actor_id)
    # Top the staging bin back up to 20 so it holds 4x the ship qty — an ample/reused
    # staging bin the per-bin floor guard cannot police.
    async with session_factory() as session:
        await execute_putaway(
            session,
            PutawayRequest(
                item_id=item_id, location_id=main_id, to_bin_id=staging_bin,
                qty=Decimal("15"), from_bin_id=pick_bin,
            ),
            actor_id,
        )
    async with session_factory() as session:
        staging_before = await get_bin_on_hand(session, item_id, main_id, staging_bin)

    barrier = asyncio.Barrier(2)

    async def _ship_same():
        from sqlalchemy import text

        async with session_factory() as session:
            await session.execute(text("SELECT 1"))  # pre-warm the connection
            await barrier.wait()
            return await execute_ship(session, sh.id, actor_id)

    results = await asyncio.gather(_ship_same(), _ship_same(), return_exceptions=True)
    successes = [r for r in results if not isinstance(r, Exception)]
    conflicts = [
        r for r in results if isinstance(r, HTTPException) and r.status_code == 409
    ]

    je_count = await _shipment_je_count(session_factory, sh.id)
    shipped = await _so_line_shipped(session_factory, so_line_id)
    async with session_factory() as session:
        staging_after = await get_bin_on_hand(session, item_id, main_id, staging_bin)

    check(
        "(h/BLOCKER-REGRESSION) shipping ONE packed shipment TWICE concurrently against an "
        "AMPLE staging bin posts COGS EXACTLY once: one ship succeeds + one is rejected 409, "
        "the shipment has exactly ONE gelato_shipment JE, qty_shipped stamped once (==5 not "
        "10), and the staging bin drawn once (20 -> 15, never 10). Removing execute_ship's "
        "shipment-row FOR UPDATE lock regresses this to 2 JEs / qty_shipped 10 / staging 10.",
        len(successes) == 1
        and len(conflicts) == 1
        and je_count == 1
        and shipped == Decimal("5")
        and staging_before == Decimal("20")
        and staging_after == Decimal("15"),
        f"successes={len(successes)} conflicts={len(conflicts)} je_count={je_count} "
        f"qty_shipped={shipped!r} staging {staging_before!r}->{staging_after!r} "
        f"results={[type(r).__name__ for r in results]}",
    )


# ---------------------------------------------------------------------------
# Cleanup — delete only the throwaway rows, in FK-safe order
# ---------------------------------------------------------------------------


async def _cleanup(session_factory, reg: Registry) -> None:
    """
    Delete the throwaway rows in FK-safe order: shipment lines (FK shipments, SO
    lines, items, bins, inventory txns) -> shipments (FK SOs, locations, bins, journal
    entries) -> the gelato_shipment journal lines/entries -> SO lines -> sales orders
    -> inventory txns (FK items, bins) -> bins (FK the location) -> inventory items ->
    partners. The seeded "Main" location and 1130/5100 accounts are reused and left in
    place (real deploy state).
    """
    async with session_factory() as session:
        shipment_list = list(reg.shipment_ids)
        so_list = list(reg.so_ids)
        item_list = list(reg.item_ids)
        bin_list = list(reg.bin_ids)
        partner_list = list(reg.partner_ids)

        if shipment_list:
            await session.execute(
                delete(ShipmentLine).where(ShipmentLine.shipment_id.in_(shipment_list))
            )
            await session.execute(delete(Shipment).where(Shipment.id.in_(shipment_list)))
            # gelato_shipment JEs are source-linked by the shipment id (string).
            entry_ids = (
                await session.execute(
                    select(JournalEntry.id).where(
                        JournalEntry.source_type == "gelato_shipment",
                        JournalEntry.source_id.in_([str(s) for s in shipment_list]),
                    )
                )
            ).scalars().all()
            if entry_ids:
                await session.execute(
                    delete(JournalLine).where(JournalLine.entry_id.in_(entry_ids))
                )
                await session.execute(delete(JournalEntry).where(JournalEntry.id.in_(entry_ids)))

        if so_list:
            await session.execute(
                delete(SalesOrderLine).where(SalesOrderLine.sales_order_id.in_(so_list))
            )
            await session.execute(delete(SalesOrder).where(SalesOrder.id.in_(so_list)))
        if item_list:
            await session.execute(delete(InventoryTxn).where(InventoryTxn.item_id.in_(item_list)))
        if bin_list:
            await session.execute(delete(Bin).where(Bin.id.in_(bin_list)))
        if item_list:
            await session.execute(delete(InventoryItem).where(InventoryItem.id.in_(item_list)))
        if partner_list:
            await session.execute(delete(Partner).where(Partner.id.in_(partner_list)))

        await session.commit()


def main() -> int:
    asyncio.run(run())
    if _FAILURES:
        print(f"\n{_FAILURES} assertion(s) FAILED.")
        return 1
    print("\nAll assertions PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
