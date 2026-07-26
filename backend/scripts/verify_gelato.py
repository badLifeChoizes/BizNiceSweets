# ABOUTME: Standalone live-DB verification for the GELATO putaway engine (Phase 12a).
# ABOUTME: Builds its OWN async engine from POSTGRES_* env (no conftest fixtures) and drives
# ABOUTME: the REAL gelato putaway service through the SAME PutawayRequest schema the router
# ABOUTME: sends — proving location net-zero, the bin roll-up equality (Decimal-exact), the
# ABOUTME: per-bin over-draw floor, and THE CRUX — two concurrent putaways drawing the same
# ABOUTME: unbinned pool cannot over-draw (the item-master FOR UPDATE lock serializes them);
# ABOUTME: exits non-zero on FAIL and self-cleans so it is safe to re-run.
"""
Standalone live-DB verification script for the GELATO putaway engine (Phase 12a).

WHY THIS EXISTS (GELATO-01 / directed-putaway crux, SC3 / SC4 / AC7 / D-P12a-6):
  Phase 12a layers storage bins over a SYERP stock location and directs on-hand
  into precise bins via putaway. A putaway moves `qty` of an item inside ONE
  location, from a source bin (or the location's *unbinned* pool, from_bin_id=None)
  into a target bin. SYERP's post_putaway books two mirrored `putaway` ledger legs
  sharing a transfer_group_id — a `-qty` leg on the source bin and a `+qty` leg on
  the target — BOTH at the same location_id, so the signed pair nets to zero at
  location grain. The load-bearing invariants:

    * NET-ZERO (SC4): a putaway never changes the item's per-location total; only
      the per-bin split shifts.
    * ROLL-UP (SC3): Σ over the location's bins + the unbinned pool == the
      per-location total, EXACTLY (Decimal, no float, no rounding).
    * FLOOR (SC4/AC7): a putaway drawing more than the source pool's on-hand is
      rejected 422 with NO ledger rows written (the per-bin negative-stock guard).
    * CONCURRENCY (SC4, D-P12a-6, THE CRUX): post_putaway LOCKS the item-master
      row FOR UPDATE before the floor read, so two concurrent putaways competing
      for the same scarce unbinned pool serialize — exactly one succeeds and the
      other is floor-rejected 422; the pool and the bin never go negative.

  THE KEEPER (11a/11b lesson): two prior phases certified GREEN while the headline
  feature was dead through the UI, because the verify script hand-fed inputs in a
  shape the router/UI never sends. This script therefore drives the service ONLY
  through the REAL `PutawayRequest` schema exactly as `POST /gelato/putaway`
  constructs it — `await execute_putaway(session, PutawayRequest(...), actor_id)`
  — never hand-assembling InventoryTxn legs nor calling post_putaway directly for
  the headline assertions.

  None of that can be proven by the pure unit tests, and the backend live-DB
  pytest harness is broken (D-P7-4), so DB-dependent tests skip under plain
  ``pytest``. Verifiable truth must come from a STANDALONE run against LIVE
  Postgres. This script stands up its own async engine + sessionmaker from the
  ``POSTGRES_*`` environment variables — it deliberately does NOT import the broken
  test conftest fixtures — and drives the REAL gelato service functions end-to-end.

HOW TO RUN (the compose ``db`` service is not host-published):
  podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db api
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_gelato.py

SCENARIO (each line prints PASS:/FAIL:; exits non-zero on any FAIL):
  (A) NET-ZERO AT LOCATION (SC4): receive N unbinned; putaway unbinned→bin1, then
      bin1→bin2, then unbinned→bin2. After EACH the per-location total (from
      get_item_onhand) is UNCHANGED == N; the target bin rises and the source pool
      falls by exactly qty.
  (B) ROLL-UP EQUALITY, DECIMAL-EXACT (SC3): after the putaways,
      Σ get_bin_on_hand(item, location, bin) over the location's bins
      + get_bin_on_hand(item, location, None)  ==  the per-location total, using
      `==` on Decimal (exact — no float, no rounding). The load-bearing invariant.
  (C) OVER-DRAW REJECTED (SC4/AC7): a putaway moving more than the source pool's
      on-hand raises HTTPException 422 and writes NO rows (the item's ledger row
      count is unchanged after the rejected call).
  (D) CONCURRENCY BARRIER (SC4, D-P12a-6, THE CRUX): unbinned pool 10, two workers
      each with its OWN session pre-warm, both wait on an asyncio.Barrier(2), then
      EACH putaways 7 from the SAME unbinned pool into the same target bin. Exactly
      ONE succeeds and the other raises 422 (7+7 > 10); the pool and bin never go
      negative; final unbinned == 3 and bin == 7 EXACTLY. Repeated several
      iterations (fresh item each) to make the race reliable.
  (E) BIN-AWARE ADJUSTMENT (SC3, D-P4-1 — the Phase 4 fix): receive 10 unbinned,
      putaway all 10 into bin E1. (E1) a bin-blind post_adjustment(-10,
      bin_id=None) draws ONLY the now-empty UNBINNED pool and is rejected 422
      with NO ledger rows written; (E2) naming the bin — post_adjustment(-10,
      bin_id=E1) — succeeds: the bin pool falls to 0, the unbinned pool stays 0,
      neither ever negative; (E3) the roll-up identity Σ bins + unbinned ==
      per-location total == 0 still holds Decimal-EXACT.
  (F) BIN-AWARE TRANSFER + POSITIVE ADJUST INTO A BIN (SC3, D-P4-1/5/6 — the
      Phase 4 fix): fresh item + fresh destination location; receive 10 unbinned
      at Main, putaway ALL 10 into bin F1. (F1) a bin-blind post_transfer(5,
      from_bin_id=None) draws ONLY the now-empty UNBINNED source pool and is
      rejected 422 with NO ledger rows written (row-count oracle as in E1);
      (F2) naming the bin — from_bin_id=F1 — succeeds: the OUT leg carries
      bin_id=F1 and the IN leg lands UNBINNED at the destination (bin_id NULL,
      D-P4-5); source bin pool and BOTH location totals are Decimal-EXACT;
      (F3) a POSITIVE post_adjustment(+4, bin_id=F1) lands directly in that bin
      (D-P4-6): the bin's get_bin_on_hand rises by exactly 4 with no floor
      guard fired.
  (G) BIN EXISTENCE + LOCATION MEMBERSHIP (SC8, D-P5-5 — the v4.0 Phase 5 fix):
      two throwaway locations, each with its own bin (G_A at location A, G_B at
      location B), stock received at B. (G1) a POSITIVE post_adjustment(+5) at
      location B naming location A's bin is rejected 422 and writes NO ledger
      rows (row-count oracle as in E1/F1) — before this check the mismatched pair
      was trusted outright and silently booked stock into a bin at the OTHER
      location, corrupting the per-bin split at both while the location totals,
      computed from location_id alone, hid it. (G2) a bin id that does not exist
      at all is rejected the same way. (G3) the MATCHING pair (+5 at B naming
      B's own bin) still succeeds and raises that bin's get_bin_on_hand by
      exactly 5, so the guard rejects a MISMATCHED bin and not a legitimate one
      (D-P4-6 is preserved). (G4) bin_id=None is untouched: it still means the
      location's unbinned pool and still posts, so D-P4-1's explicit-or-unbinned
      contract — and the SC6 zero-pool fixture that depends on it — is intact.

The script uses uniquely-suffixed throwaway SYERP items / GELATO bins / stock
locations and CLEANS UP after itself (inventory txns -> bins -> inventory items ->
locations) in a finally block, so it is safe to re-run against the same database.
The seeded "Main" stock location is reused and left in place (real deploy state).
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

# Make the backend root importable when run as a bare `python scripts/verify_gelato.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app — the sibling verify_*.py scripts require that env var).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the central model aggregator FIRST so Base.metadata is fully populated
# (the gelato_bin FK references syerp_stock_location and syerp_inventory_txn.bin_id
# soft-links back to gelato_bin — every table must be registered before the FKs
# resolve; the Task-8 lesson from MOUSSE).
import app.core.models  # noqa: F401
from app.modules.gelato.models import Bin
from app.modules.gelato.schemas import BinCreate, PutawayRequest
from app.modules.gelato.service import create_bin, execute_putaway, get_bin_on_hand
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME, seed_default_location
from app.modules.syerp.models import InventoryItem, InventoryTxn, StockLocation
from app.modules.syerp.schemas import InventoryItemCreate, StockLocationCreate
from app.modules.syerp.service import (
    create_item,
    create_location,
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


# ---------------------------------------------------------------------------
# Fixture builders + independent oracles (the assertion's OWN truth)
# ---------------------------------------------------------------------------


async def _make_item(session_factory, unique: str, tag: str) -> str:
    """Create a throwaway SYERP InventoryItem (no PLUM link) via the REAL service."""
    async with session_factory() as session:
        item = await create_item(
            session,
            InventoryItemCreate(
                name=f"VERIFY-GELATO {tag} {unique}",
                unit_of_measure="ea",
            ),
        )
        return item.id


async def _make_bin(session_factory, location_id: int, code: str) -> int:
    """Create a throwaway GELATO bin via the REAL create_bin service; return its id."""
    async with session_factory() as session:
        bin_ = await create_bin(session, BinCreate(location_id=location_id, code=code))
        return bin_.id


async def _location_total(session_factory, item_id: str, location_id: int) -> Decimal:
    """
    The item's per-location on-hand as get_item_onhand derives it — the exact
    figure the putaway result reports for location_total. Zero-net locations are
    omitted from its rows, so a missing row means Decimal("0").
    """
    async with session_factory() as session:
        onhand = await get_item_onhand(session, item_id)
    return next(
        (loc.quantity for loc in onhand.locations if loc.location_id == location_id),
        Decimal("0"),
    )


async def _ledger_rows(session_factory, item_id: str) -> int:
    """Independent oracle: the count of ledger rows for an item (over-draw guard)."""
    async with session_factory() as session:
        return (
            await session.execute(
                select(func.count()).select_from(InventoryTxn).where(
                    InventoryTxn.item_id == item_id
                )
            )
        ).scalar()


async def run() -> None:  # noqa: C901 - one long linear verification scenario
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    actor_id = str(uuid.uuid4())  # stand-in for the acting user
    unique = uuid.uuid4().hex[:8]

    # Throwaway-row registries for the finally cleanup.
    item_ids: set[str] = set()
    bin_ids: set[int] = set()
    loc_ids: set[int] = set()

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

        # ===================================================================
        # (A) NET-ZERO AT LOCATION (SC4) — every putaway leaves the per-location
        #     total unchanged; target bin rises, source pool falls by exactly qty.
        # ===================================================================
        n = Decimal("100")
        item_a = await _make_item(session_factory, unique, "A")
        item_ids.add(item_a)
        async with session_factory() as session:
            await post_receipt(session, item_a, main_id, n, Decimal("4"), actor_id)

        bin1 = await _make_bin(session_factory, main_id, f"A1-{unique}")
        bin2 = await _make_bin(session_factory, main_id, f"A2-{unique}")
        bin_ids.update({bin1, bin2})

        # Pre-putaway: everything is in the unbinned pool; the location total is N.
        total_pre = await _location_total(session_factory, item_a, main_id)
        async with session_factory() as session:
            unbinned_pre = await get_bin_on_hand(session, item_a, main_id, None)
        check(
            "(A/SC4) before any putaway the whole receipt sits in the unbinned pool "
            "(pool == 100) and the per-location total == 100",
            total_pre == n and unbinned_pre == n,
            f"total={total_pre!r} unbinned={unbinned_pre!r}",
        )

        # Putaway 1: unbinned pool -> bin1, qty 40. Through the REAL PutawayRequest
        # schema, exactly as POST /gelato/putaway constructs it (the 11a/11b keeper).
        async with session_factory() as session:
            r1 = await execute_putaway(
                session,
                PutawayRequest(
                    item_id=item_a, location_id=main_id, to_bin_id=bin1,
                    qty=Decimal("40"), from_bin_id=None,
                ),
                actor_id,
            )
        total_1 = await _location_total(session_factory, item_a, main_id)
        async with session_factory() as session:
            unbinned_1 = await get_bin_on_hand(session, item_a, main_id, None)
            bin1_1 = await get_bin_on_hand(session, item_a, main_id, bin1)
        check(
            "(A/SC4) putaway unbinned→bin1 (qty 40): per-location total UNCHANGED "
            "(== 100), target bin1 rose to 40, unbinned pool fell to 60",
            total_1 == n
            and bin1_1 == Decimal("40")
            and unbinned_1 == Decimal("60")
            and r1.location_total == n
            and r1.bin_on_hand == Decimal("40"),
            f"total={total_1!r} bin1={bin1_1!r} unbinned={unbinned_1!r} "
            f"result.location_total={r1.location_total!r} result.bin_on_hand={r1.bin_on_hand!r}",
        )

        # Putaway 2: bin1 -> bin2, qty 15. A bin→bin move (from_bin_id set).
        async with session_factory() as session:
            r2 = await execute_putaway(
                session,
                PutawayRequest(
                    item_id=item_a, location_id=main_id, to_bin_id=bin2,
                    qty=Decimal("15"), from_bin_id=bin1,
                ),
                actor_id,
            )
        total_2 = await _location_total(session_factory, item_a, main_id)
        async with session_factory() as session:
            bin1_2 = await get_bin_on_hand(session, item_a, main_id, bin1)
            bin2_2 = await get_bin_on_hand(session, item_a, main_id, bin2)
        check(
            "(A/SC4) putaway bin1→bin2 (qty 15): per-location total STILL 100, "
            "source bin1 fell to 25, target bin2 rose to 15",
            total_2 == n
            and bin1_2 == Decimal("25")
            and bin2_2 == Decimal("15")
            and r2.location_total == n,
            f"total={total_2!r} bin1={bin1_2!r} bin2={bin2_2!r} "
            f"result.location_total={r2.location_total!r}",
        )

        # Putaway 3: unbinned pool -> bin2, qty 10.
        async with session_factory() as session:
            r3 = await execute_putaway(
                session,
                PutawayRequest(
                    item_id=item_a, location_id=main_id, to_bin_id=bin2,
                    qty=Decimal("10"), from_bin_id=None,
                ),
                actor_id,
            )
        total_3 = await _location_total(session_factory, item_a, main_id)
        check(
            "(A/SC4) putaway unbinned→bin2 (qty 10): per-location total STILL 100 "
            "(net-zero holds across every move)",
            total_3 == n and r3.location_total == n,
            f"total={total_3!r} result.location_total={r3.location_total!r}",
        )

        # ===================================================================
        # (B) ROLL-UP EQUALITY, DECIMAL-EXACT (SC3) — the load-bearing invariant.
        # ===================================================================
        # After A: bin1 25, bin2 25, unbinned 50 -> Σ bins + unbinned == 100.
        async with session_factory() as session:
            b_bin1 = await get_bin_on_hand(session, item_a, main_id, bin1)
            b_bin2 = await get_bin_on_hand(session, item_a, main_id, bin2)
            b_unbinned = await get_bin_on_hand(session, item_a, main_id, None)
        rollup = b_bin1 + b_bin2 + b_unbinned
        loc_total = await _location_total(session_factory, item_a, main_id)
        check(
            "(B/SC3 CRUX) roll-up equality Decimal-EXACT: Σ get_bin_on_hand over the "
            "location's bins + the unbinned pool == the per-location total "
            "(25 + 25 + 50 == 100), using == on Decimal (no float, no rounding)",
            rollup == loc_total and isinstance(rollup, Decimal) and isinstance(loc_total, Decimal),
            f"rollup={rollup!r} (bin1={b_bin1!r} bin2={b_bin2!r} unbinned={b_unbinned!r}) "
            f"location_total={loc_total!r}",
        )

        # ===================================================================
        # (C) OVER-DRAW REJECTED (SC4/AC7) — 422 and NO rows written.
        # ===================================================================
        item_c = await _make_item(session_factory, unique, "C")
        item_ids.add(item_c)
        async with session_factory() as session:
            await post_receipt(session, item_c, main_id, Decimal("10"), Decimal("4"), actor_id)
        bin_c = await _make_bin(session_factory, main_id, f"C1-{unique}")
        bin_ids.add(bin_c)

        rows_before = await _ledger_rows(session_factory, item_c)
        try:
            async with session_factory() as session:
                await execute_putaway(
                    session,
                    PutawayRequest(
                        item_id=item_c, location_id=main_id, to_bin_id=bin_c,
                        qty=Decimal("15"), from_bin_id=None,
                    ),
                    actor_id,
                )
            check("(C/SC4/AC7) putaway of 15 from an unbinned pool of 10 is rejected",
                  False, "putaway succeeded over the floor")
        except HTTPException as exc:
            check(
                "(C/SC4/AC7) putaway of 15 from an unbinned pool of 10 is rejected 422",
                exc.status_code == 422,
                f"status={exc.status_code}",
            )
        rows_after = await _ledger_rows(session_factory, item_c)
        check(
            "(C/SC4/AC7) the rejected over-draw wrote NO ledger rows "
            "(row count unchanged after the rejected call)",
            rows_after == rows_before == 1,
            f"before={rows_before!r} after={rows_after!r}",
        )

        # ===================================================================
        # (D) CONCURRENCY BARRIER (SC4, D-P12a-6, THE CRUX)
        # ===================================================================
        await run_concurrency(session_factory, unique, actor_id, main_id, item_ids, bin_ids)

        # ===================================================================
        # (E) BIN-AWARE ADJUSTMENT (SC3, D-P4-1 — the Phase 4 fix)
        # ===================================================================
        # Phase 4 (NFR-7 / D-P4-1) made post_adjustment bin-aware under the
        # explicit-or-unbinned contract: bin_id=None draws ONLY the location's
        # UNBINNED pool (and floor-guards it), and a negative delta naming a bin
        # floor-guards THAT bin's pool — the server never auto-allocates across
        # bins, so a write-off at a fully-binned location must name the bin.
        # This replaces the 12a-era pin of the old bin-blind behavior (stale bin
        # figure + negative unbinned pool): the desync path is now a 422.
        item_e = await _make_item(session_factory, unique, "E")
        item_ids.add(item_e)
        bin_e = await _make_bin(session_factory, main_id, f"E1-{unique}")
        bin_ids.add(bin_e)
        async with session_factory() as session:
            await post_receipt(session, item_e, main_id, Decimal("10"), Decimal("5"), actor_id)
        async with session_factory() as session:
            await execute_putaway(
                session,
                PutawayRequest(
                    item_id=item_e, location_id=main_id, to_bin_id=bin_e,
                    qty=Decimal("10"), from_bin_id=None,
                ),
                actor_id,
            )
        # (E1) A bin-blind draw of the full 10 (bin_id=None) targets the now-EMPTY
        # unbinned pool — rejected 422 with NO ledger rows written. Row-count
        # oracle as in (C): receipt + two putaway legs == 3 rows before and after.
        e_rows_before = await _ledger_rows(session_factory, item_e)
        try:
            async with session_factory() as session:
                await post_adjustment(
                    session, item_e, main_id, Decimal("-10"),
                    "bin-blind draw against an empty unbinned pool", actor_id,
                    bin_id=None,
                )
            check(
                "(E1/SC3/D-P4-1) bin-blind adjustment (-10, bin_id=None) against an "
                "empty unbinned pool is rejected",
                False, "adjustment succeeded over the unbinned-pool floor",
            )
        except HTTPException as exc:
            check(
                "(E1/SC3/D-P4-1) bin-blind adjustment (-10, bin_id=None) draws ONLY "
                "the empty unbinned pool and is rejected 422",
                exc.status_code == 422,
                f"status={exc.status_code}",
            )
        e_rows_after = await _ledger_rows(session_factory, item_e)
        check(
            "(E1/SC3) the rejected bin-blind adjustment wrote NO ledger rows "
            "(row count unchanged after the rejected call)",
            e_rows_after == e_rows_before == 3,
            f"before={e_rows_before!r} after={e_rows_after!r}",
        )
        # (E2) Naming the bin succeeds: the bin pool falls to 0 and the unbinned
        # pool stays 0 — neither ever goes negative.
        async with session_factory() as session:
            await post_adjustment(
                session, item_e, main_id, Decimal("-10"),
                "bin-aware write-off from bin E1", actor_id,
                bin_id=bin_e,
            )
        async with session_factory() as session:
            e_bin = await get_bin_on_hand(session, item_e, main_id, bin_e)
            e_unbinned = await get_bin_on_hand(session, item_e, main_id, None)
        e_loc_total = await _location_total(session_factory, item_e, main_id)
        check(
            "(E2/SC3/D-P4-1) bin-aware adjustment (-10, bin_id=E1) succeeds: the bin "
            "pool falls to 0 and the unbinned pool stays 0 — never negative",
            e_bin == Decimal("0") and e_unbinned == Decimal("0"),
            f"bin_e={e_bin!r} unbinned={e_unbinned!r}",
        )
        check(
            "(E3/SC3) the roll-up identity holds after the bin-aware draw: "
            "Σ bins + unbinned == per-location total == 0 Decimal-EXACT",
            (e_bin + e_unbinned) == e_loc_total == Decimal("0"),
            f"rollup={(e_bin + e_unbinned)!r} location_total={e_loc_total!r}",
        )

        # ===================================================================
        # (F) BIN-AWARE TRANSFER + POSITIVE ADJUST INTO A BIN (SC3, D-P4-1/5/6)
        # ===================================================================
        # Phase 4 made post_transfer bin-aware under the same explicit-or-
        # unbinned contract as adjustments (D-P4-1): from_bin_id=None draws
        # ONLY the source location's UNBINNED pool (and floor-guards it); a
        # named bin draws that single bin. The IN leg always lands UNBINNED at
        # the destination — putaway directs it later (D-P4-5). And a POSITIVE
        # adjustment may target a bin directly (cycle-count "found in bin",
        # D-P4-6) with no floor guard on additions. Pins the behaviors the
        # Phase-4 verification could only hand-check.
        item_f = await _make_item(session_factory, unique, "FT")
        item_ids.add(item_f)
        bin_f = await _make_bin(session_factory, main_id, f"FT1-{unique}")  # "bin F1"
        bin_ids.add(bin_f)
        async with session_factory() as session:
            dest = await create_location(
                session, StockLocationCreate(name=f"VERIFY-GELATO dest {unique}")
            )
        dest_id = dest.id
        loc_ids.add(dest_id)
        async with session_factory() as session:
            await post_receipt(session, item_f, main_id, Decimal("10"), Decimal("6"), actor_id)
        async with session_factory() as session:
            await execute_putaway(
                session,
                PutawayRequest(
                    item_id=item_f, location_id=main_id, to_bin_id=bin_f,
                    qty=Decimal("10"), from_bin_id=None,
                ),
                actor_id,
            )
        # (F1) A bin-blind transfer of 5 (from_bin_id=None) draws the now-EMPTY
        # unbinned source pool — rejected 422 with NO ledger rows written.
        # Row-count oracle as in (E1): receipt + two putaway legs == 3 rows.
        f_rows_before = await _ledger_rows(session_factory, item_f)
        try:
            async with session_factory() as session:
                await post_transfer(
                    session, item_f, main_id, dest_id, Decimal("5"), actor_id,
                    from_bin_id=None,
                )
            check(
                "(F1/SC3/D-P4-1) bin-blind transfer (5, from_bin_id=None) out of a "
                "fully-binned source is rejected",
                False, "transfer succeeded over the unbinned-pool floor",
            )
        except HTTPException as exc:
            check(
                "(F1/SC3/D-P4-1) bin-blind transfer (5, from_bin_id=None) draws ONLY "
                "the empty unbinned source pool and is rejected 422",
                exc.status_code == 422,
                f"status={exc.status_code}",
            )
        f_rows_after = await _ledger_rows(session_factory, item_f)
        check(
            "(F1/SC3) the rejected bin-blind transfer wrote NO ledger rows "
            "(row count unchanged after the rejected call)",
            f_rows_after == f_rows_before == 3,
            f"before={f_rows_before!r} after={f_rows_after!r}",
        )
        # (F2) Naming the bin succeeds: the OUT leg carries bin_id=F1, the IN
        # leg lands UNBINNED at the destination (bin_id NULL, D-P4-5); the
        # source bin pool and BOTH location totals are Decimal-exact.
        async with session_factory() as session:
            legs = await post_transfer(
                session, item_f, main_id, dest_id, Decimal("5"), actor_id,
                from_bin_id=bin_f,
            )
        # TransactionRead omits bin_id, so read the legs' bin_ids straight off
        # the ledger rows by the returned ids (the assertion's own truth).
        async with session_factory() as session:
            out_bin = (
                await session.execute(
                    select(InventoryTxn.bin_id).where(InventoryTxn.id == legs[0].id)
                )
            ).scalar()
            in_bin = (
                await session.execute(
                    select(InventoryTxn.bin_id).where(InventoryTxn.id == legs[1].id)
                )
            ).scalar()
            f_bin_pool = await get_bin_on_hand(session, item_f, main_id, bin_f)
            f_unbinned = await get_bin_on_hand(session, item_f, main_id, None)
        f_src_total = await _location_total(session_factory, item_f, main_id)
        f_dest_total = await _location_total(session_factory, item_f, dest_id)
        check(
            "(F2/SC3/D-P4-5) bin-aware transfer (5, from_bin_id=F1) succeeds: the OUT "
            "leg carries bin_id=F1 and the IN leg lands UNBINNED (bin_id NULL) at the "
            "destination",
            legs[0].quantity == Decimal("-5") and out_bin == bin_f
            and legs[1].quantity == Decimal("5") and in_bin is None,
            f"out_qty={legs[0].quantity!r} out_bin={out_bin!r} "
            f"in_qty={legs[1].quantity!r} in_bin={in_bin!r}",
        )
        check(
            "(F2/SC3) source bin pool and BOTH location totals are Decimal-EXACT "
            "after the transfer (bin 10-5==5, unbinned 0, source total 5, dest total 5)",
            f_bin_pool == Decimal("5") and f_unbinned == Decimal("0")
            and f_src_total == Decimal("5") and f_dest_total == Decimal("5"),
            f"bin={f_bin_pool!r} unbinned={f_unbinned!r} "
            f"src_total={f_src_total!r} dest_total={f_dest_total!r}",
        )
        # (F3) A POSITIVE adjustment naming the bin lands directly in that bin
        # (D-P4-6): the bin's pool rises by exactly the delta, no floor guard
        # fires on an addition.
        async with session_factory() as session:
            await post_adjustment(
                session, item_f, main_id, Decimal("4"),
                "cycle count found stock in bin F1", actor_id,
                bin_id=bin_f,
            )
        async with session_factory() as session:
            f_bin_after = await get_bin_on_hand(session, item_f, main_id, bin_f)
            f_unbinned_after = await get_bin_on_hand(session, item_f, main_id, None)
        check(
            "(F3/SC3/D-P4-6) a POSITIVE adjustment (+4, bin_id=F1) raises that bin's "
            "get_bin_on_hand by exactly 4 (5+4==9) with no floor guard fired; the "
            "unbinned pool is untouched (0)",
            f_bin_after == Decimal("9") and f_unbinned_after == Decimal("0"),
            f"bin={f_bin_after!r} unbinned={f_unbinned_after!r}",
        )

        # ===================================================================
        # (G) BIN EXISTENCE + LOCATION MEMBERSHIP (SC8, D-P5-5)
        # ===================================================================
        # post_adjustment validates a NON-NULL bin_id against gelato_bin with ONE
        # raw-SQL existence+membership probe (SYERP must not import gelato models,
        # D-P12a-3). Two locations each with their own bin make the mismatch
        # expressible at all: with a single location every bin trivially belongs to
        # it, which is exactly why the hole survived Phase 4's bin-awareness work.
        item_g = await _make_item(session_factory, unique, "G")
        item_ids.add(item_g)
        async with session_factory() as session:
            loc_g_a = await create_location(
                session, StockLocationCreate(name=f"VERIFY-GELATO G-A {unique}")
            )
            loc_g_b = await create_location(
                session, StockLocationCreate(name=f"VERIFY-GELATO G-B {unique}")
            )
        loc_ids.update({loc_g_a.id, loc_g_b.id})
        bin_g_a = await _make_bin(session_factory, loc_g_a.id, f"GA1-{unique}")
        bin_g_b = await _make_bin(session_factory, loc_g_b.id, f"GB1-{unique}")
        bin_ids.update({bin_g_a, bin_g_b})
        async with session_factory() as session:
            await post_receipt(
                session, item_g, loc_g_b.id, Decimal("10"), Decimal("2"), actor_id
            )

        g_rows_before = await _ledger_rows(session_factory, item_g)

        # (G1) MISMATCH: adjust at location B while naming location A's bin.
        g1_status = None
        async with session_factory() as session:
            try:
                await post_adjustment(
                    session, item_g, loc_g_b.id, Decimal("5"),
                    "SC8 mismatched bin", actor_id,
                    bin_id=bin_g_a,
                )
            except HTTPException as exc:
                g1_status = exc.status_code
        g_rows_after_mismatch = await _ledger_rows(session_factory, item_g)
        check(
            "(G1/SC8/D-P5-5) a POSITIVE adjustment (+5) at location B naming location "
            "A's bin is REJECTED 422 and writes NO ledger rows — the bin must belong to "
            "the location. Reverting the membership probe in post_adjustment regresses "
            "this to a silent success that books stock into a bin at the WRONG location.",
            g1_status == 422 and g_rows_after_mismatch == g_rows_before,
            f"status={g1_status!r} rows {g_rows_before}->{g_rows_after_mismatch}",
        )

        # (G2) A bin id that does not exist at all — the FK's half of the guard.
        g2_status = None
        async with session_factory() as session:
            try:
                await post_adjustment(
                    session, item_g, loc_g_b.id, Decimal("5"),
                    "SC8 nonexistent bin", actor_id,
                    bin_id=-1,
                )
            except HTTPException as exc:
                g2_status = exc.status_code
        check(
            "(G2/SC8) a bin_id that does not exist at all is REJECTED 422 (not a raw "
            "IntegrityError/500 from the FK) and writes NO ledger rows",
            g2_status == 422
            and await _ledger_rows(session_factory, item_g) == g_rows_before,
            f"status={g2_status!r}",
        )

        # (G3) The MATCHING pair still succeeds — the guard must reject a MISMATCHED
        # bin, never a legitimate one (D-P4-6 preserved).
        async with session_factory() as session:
            g_bin_before = await get_bin_on_hand(session, item_g, loc_g_b.id, bin_g_b)
        async with session_factory() as session:
            await post_adjustment(
                session, item_g, loc_g_b.id, Decimal("5"),
                "SC8 matching bin", actor_id,
                bin_id=bin_g_b,
            )
        async with session_factory() as session:
            g_bin_after = await get_bin_on_hand(session, item_g, loc_g_b.id, bin_g_b)
        check(
            "(G3/SC8/D-P4-6) the MATCHING (location B, bin of B) pair still SUCCEEDS and "
            "raises that bin's get_bin_on_hand by exactly 5 — the new guard rejects a "
            "mismatched bin, not a legitimate binned adjustment",
            g_bin_after - g_bin_before == Decimal("5"),
            f"bin {g_bin_before!r}->{g_bin_after!r}",
        )

        # (G4) bin_id=None must be COMPLETELY untouched by the membership probe: it
        # still means the unbinned pool (D-P4-1). The SC6 zero-pool fixture design
        # rests on this — if NULL started 422-ing, every "must name a bin" check in
        # the UAT runbook would pass for the wrong reason.
        async with session_factory() as session:
            g_pool_before = await get_bin_on_hand(session, item_g, loc_g_b.id, None)
        async with session_factory() as session:
            await post_adjustment(
                session, item_g, loc_g_b.id, Decimal("3"),
                "SC8 unbinned pool still valid", actor_id,
                bin_id=None,
            )
        async with session_factory() as session:
            g_pool_after = await get_bin_on_hand(session, item_g, loc_g_b.id, None)
        check(
            "(G4/SC8/D-P4-1) bin_id=None is UNTOUCHED by the membership probe — it still "
            "means the location's unbinned pool and still posts, raising that pool by "
            "exactly 3. The SC6 zero-pool fixtures depend on NULL keeping this meaning.",
            g_pool_after - g_pool_before == Decimal("3"),
            f"pool {g_pool_before!r}->{g_pool_after!r}",
        )

    finally:
        await _cleanup(session_factory, item_ids, bin_ids, loc_ids)
        await engine.dispose()


# ---------------------------------------------------------------------------
# (D) Concurrency scenario (D-P12a-6) — the FOR UPDATE lock is what makes this hold
# ---------------------------------------------------------------------------
#
# post_putaway locks the item-master row `SELECT ... FOR UPDATE` BEFORE reading the
# source bin's on-hand, so two concurrent putaways drawing the same unbinned pool
# serialize: the first reserves min(qty, pool), commits (releasing the lock), and
# the second then re-reads the now-depleted pool and the per-bin floor guard rejects
# it 422. Removing that FOR UPDATE lets both read the original pool under READ
# COMMITTED and both draw their full 7 — driving the pool NEGATIVE (over-draw) — i.e.
# this scenario FAILS. A sequential test cannot surface that race; only firing both
# with asyncio.gather on TWO INDEPENDENT sessions can. Repeated over several
# iterations for confidence.


async def run_concurrency(
    session_factory,
    unique: str,
    actor_id: str,
    main_id: int,
    item_ids: set[str],
    bin_ids: set[int],
) -> None:
    """
    For each iteration: a fresh item with an unbinned pool of 10 and one target
    bin. Two workers, each on an INDEPENDENT session, each putaway 7 (> half) from
    the SAME unbinned pool. Fire both concurrently through the REAL PutawayRequest
    schema and prove EXACTLY ONE succeeds and the other is rejected 422 — the pool
    and bin never go negative, final pool == 3 and bin == 7 EXACTLY.
    """
    pool = Decimal("10")
    move_qty = Decimal("7")  # 7 + 7 == 14 > 10, so two full moves would over-draw
    iterations = 5

    all_ok = True
    detail = ""
    for i in range(iterations):
        item_f = await _make_item(session_factory, unique, f"F{i}")
        item_ids.add(item_f)
        async with session_factory() as session:
            await post_receipt(session, item_f, main_id, pool, Decimal("4"), actor_id)
        target_bin = await _make_bin(session_factory, main_id, f"F{i}-{unique}")
        bin_ids.add(target_bin)

        # Barrier makes the race deterministic: each worker owns an INDEPENDENT
        # session, pre-warms its connection, then both enter execute_putaway together.
        barrier = asyncio.Barrier(2)

        async def _putaway_once():
            from sqlalchemy import text

            async with session_factory() as session:
                await session.execute(text("SELECT 1"))  # pre-warm the connection
                await barrier.wait()
                return await execute_putaway(
                    session,
                    PutawayRequest(
                        item_id=item_f, location_id=main_id, to_bin_id=target_bin,
                        qty=move_qty, from_bin_id=None,
                    ),
                    actor_id,
                )

        results = await asyncio.gather(
            _putaway_once(), _putaway_once(), return_exceptions=True
        )
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]
        http_422 = [
            r for r in failures if isinstance(r, HTTPException) and r.status_code == 422
        ]

        if not (len(successes) == 1 and len(http_422) == 1):
            all_ok = False
            detail = (
                f"iter {i}: successes={len(successes)} "
                f"failures={[type(f).__name__ for f in failures]} "
                f"(expected exactly 1 success + 1 HTTP 422)"
            )
            break

        async with session_factory() as session:
            final_pool = await get_bin_on_hand(session, item_f, main_id, None)
            final_bin = await get_bin_on_hand(session, item_f, main_id, target_bin)
        if final_pool < 0 or final_bin < 0:
            all_ok = False
            detail = f"iter {i}: negative on-hand pool={final_pool} bin={final_bin}"
            break
        if not (final_pool == Decimal("3") and final_bin == move_qty):
            all_ok = False
            detail = (
                f"iter {i}: final pool={final_pool} (want 3) bin={final_bin} (want 7)"
            )
            break

    check(
        "(D/SC4/D-P12a-6 CRUX) two concurrent putaways (each own session) drawing the "
        f"SAME unbinned pool of 10 (each moving 7) never over-draw — EXACTLY one "
        f"succeeds and one is rejected 422, pool/bin never negative, final pool == 3 "
        f"and bin == 7 EXACTLY across {iterations} iterations",
        all_ok,
        detail,
    )


# ---------------------------------------------------------------------------
# Cleanup — delete only the throwaway rows, in FK-safe order
# ---------------------------------------------------------------------------


async def _cleanup(
    session_factory, item_ids: set[str], bin_ids: set[int], loc_ids: set[int]
) -> None:
    """
    Delete the throwaway rows in FK-safe order: inventory txns (they FK into both
    items and bins) -> bins (FK into the location) -> inventory items -> throwaway
    stock locations (scenario F's destination). The seeded "Main" stock location is
    reused and left in place (real deploy state).
    """
    async with session_factory() as session:
        item_list = list(item_ids)
        bin_list = list(bin_ids)
        loc_list = list(loc_ids)

        if item_list:
            await session.execute(
                delete(InventoryTxn).where(InventoryTxn.item_id.in_(item_list))
            )
        if bin_list:
            await session.execute(delete(Bin).where(Bin.id.in_(bin_list)))
        if item_list:
            await session.execute(
                delete(InventoryItem).where(InventoryItem.id.in_(item_list))
            )
        if loc_list:
            await session.execute(
                delete(StockLocation).where(StockLocation.id.in_(loc_list))
            )

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
