# ABOUTME: Standalone live-DB verification for v4.0 Phase 4 inventory race-safety (NFR-7).
# ABOUTME: Builds its OWN async engine from POSTGRES_* env (no conftest fixtures) and fires
# ABOUTME: MIXED-PATH concurrent writers through the REAL request schemas the routers use —
# ABOUTME: MOUSSE issue × SYERP adjust, adjust × transfer, receive_line × receive_line, and
# ABOUTME: receipt × receipt — proving the shared item-master / PO-header FOR UPDATE lock
# ABOUTME: discipline: exactly one contended draw wins, derived on-hand never goes negative,
# ABOUTME: qty_received never exceeds qty_ordered, and the moving average never loses an
# ABOUTME: update; exits non-zero on FAIL and self-cleans so it is safe to re-run.
"""
Standalone live-DB verification script for inventory-ledger race-safety
(v4.0 Phase 4, NFR-7, SC1/SC2).

WHY THIS EXISTS (the Phase-4 crux):
  On-hand is a DERIVED aggregate (signed SUM over the append-only InventoryTxn
  ledger), so the ledger rows themselves cannot be locked to serialize
  concurrent floor-guarded writes. Phase 4 therefore serializes EVERY
  floor-guarded inventory writer on one shared discipline: an item-master
  ``SELECT … FOR UPDATE`` taken BEFORE any aggregate/floor read
  (post_receipt / post_adjustment / post_transfer / post_putaway / post_issue /
  MOUSSE issue_components), plus a PO-header FOR UPDATE in receive_line for the
  qty_received accumulator + status roll-up. The discipline is only worth
  anything if it holds ACROSS paths: MOUSSE's own lock cannot save the ledger
  when the SYERP adjust path is unlocked — both writers must queue on the SAME
  item-master row. This script proves exactly that, with MIXED-path pairs, not
  same-path pairs only.

  THE KEEPER (11a/11b lesson): the services are driven ONLY through the REAL
  request schemas / service signatures the routers use — AdjustmentCreate /
  TransferCreate / ReceiptCreate / ReceiveLine unpacked exactly as
  syerp/router.py unpacks them, IssueComponentsRequest passed exactly as
  mousse/router.py passes it — never hand-assembled InventoryTxn legs.

  FIXTURE RULE (12b keeper): every scenario provisions AMPLE stock everywhere
  except the ONE contended invariant, so only the guard under test can reject;
  quantities are chosen with an INDIVISIBLE remainder (2b keeper — pool 10,
  competing draws of 7: 7+7 == 14 > 10, remainder 3) so a lost update is
  arithmetically visible, never masked by a divisible coincidence.

  None of this can be proven by pure unit tests, and the backend live-DB pytest
  harness is broken (D-P7-4), so DB-dependent tests skip under plain
  ``pytest``. Verifiable truth must come from a STANDALONE run against LIVE
  Postgres: this script stands up its own async engine + sessionmaker from the
  ``POSTGRES_*`` environment variables and fires the REAL service functions
  concurrently (asyncio.Barrier(2), two INDEPENDENT pre-warmed sessions,
  several iterations per race — the verify_gelato scenario-D recipe).

HOW TO RUN (the compose ``db`` service is not host-published):
  podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db api
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_inventory_race.py

SCENARIOS (each prints PASS:/FAIL:; exits non-zero on any FAIL):
  (A) MOUSSE ISSUE × SYERP ADJUST (SC2 — the SRD's named mixed pair): a WO
      component with plentiful stock at a second location; the contended
      item/location (unbinned pool) holds 10. MOUSSE issues 7 while
      post_adjustment draws -7 CONCURRENTLY. Exactly ONE succeeds, the other
      is floor-rejected 422; final contended-location on-hand == 3 EXACTLY
      (the single winner's draw) and derived on-hand NEVER goes negative.
      This is the cross-module proof: both writers queue on the SAME
      item-master row.
  (B) ADJUST × TRANSFER on the same source pool (SC2): same 10/7/7 shape —
      post_adjustment(-7) races post_transfer(7 → second location). Exactly
      one wins, one 422s, final source on-hand == 3, never negative.
  (C) RECEIVE_LINE × RECEIVE_LINE on ONE PO line (SC1): line ordered 10, two
      concurrent receives of 7. The PO-header FOR UPDATE serializes them:
      exactly one succeeds, the loser re-reads qty_received == 7 and is
      over-receipt-rejected 422; qty_received (7) <= qty_ordered (10) holds,
      the header status is 'partially_received', and exactly ONE receipt txn
      is source-linked to the line.
  (D) RECEIPT × RECEIPT moving-average integrity (SC1): two concurrent
      post_receipts (7 @ 10 and 5 @ 9) on an item with zero prior stock. Both
      succeed (receipts take no floor), but the item-master lock + refresh
      serialize the read-recompute-write, so the final moving_avg_cost equals
      the sequential two-receipt computation EXACTLY:
      (7*10 + 5*9) / 12 == 115/12 → 9.583333 (indivisible remainder, so a
      lost update — final avg 10.000000 or 9.000000 — is unmistakable).
      Starting from zero stock makes the expected figure order-independent.

MUTATION-PROOF PROCEDURE (executed during the Phase-4 Task-7 build; results
recorded in docs/tasks/chore-inventory-race-safety.md). For each mutation:
temporarily revert ONLY the named lock in the bind-mounted source, run this
script (the named scenario must go RED — if it still passes the scenario is
vacuous and must be strengthened), then ``git checkout -- <file>`` and re-run
to GREEN:

  | #  | Lock removed (revert)                                   | Expected RED                              |
  |----|---------------------------------------------------------|-------------------------------------------|
  | M1 | item-master FOR UPDATE in post_adjustment (inventory.py)| (A) both succeed, on-hand driven to -4    |
  | M2 | item-master FOR UPDATE in post_transfer (inventory.py)  | (B) both succeed, source on-hand -4       |
  | M3 | PO-header for_update=True in receive_line (purchasing.py)| (C) both succeed, qty_received 14 > 10   |
  | M4 | item-master FOR UPDATE + refresh in post_receipt        | (D) moving-avg lost update (10 or 9,      |
  |    | (inventory.py — lock AND refresh: the refresh is the    |     not 9.583333)                         |
  |    | identity-map half of the same serialization)            |                                           |

  M1's RED also proves the discipline is SHARED: MOUSSE issue_components keeps
  its own lock throughout, yet (A) still breaches when only the adjust path is
  unlocked — one unlocked writer defeats every locked one.

The script uses uniquely-suffixed throwaway PLUM parts / SYERP items / vendors /
locations / POs / work orders and CLEANS UP after itself in a finally block
(issues → source-linked JEs → components → WOs → PO lines → POs → inventory
txns → items → BOM items → revisions → parts → locations → vendors), so it is
safe to re-run and CI-safe on a fresh database (it seeds everything it needs;
the seeded "Main" location and GL accounts are reused and left in place).
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Make the backend root importable when run as a bare `python scripts/verify_inventory_race.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app — the sibling verify_*.py scripts require that env var).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the central model aggregator FIRST so Base.metadata is fully populated
# (the mousse_* FKs reference plum_* and syerp_* tables that must be registered
# before the FKs resolve — the Task-8 lesson).
import app.core.models  # noqa: F401
from app.modules.mousse.models import WorkOrder, WorkOrderComponent, WorkOrderIssue
from app.modules.mousse.schemas import (
    IssueComponentLine,
    IssueComponentsRequest,
    WorkOrderCreate,
)
from app.modules.mousse.service import (
    create_work_order,
    get_work_order_detail,
    issue_components,
    release_work_order,
)
from app.modules.plum.models import PlumBomItem, PlumPart, PlumPartRevision
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME, seed_default_location
from app.modules.syerp.models import (
    GLAccount,
    InventoryItem,
    InventoryTxn,
    JournalEntry,
    JournalLine,
    Partner,
    PurchaseOrder,
    PurchaseOrderLine,
    StockLocation,
)
from app.modules.syerp.schemas import (
    AdjustmentCreate,
    InventoryItemCreate,
    PartnerCreate,
    POCreate,
    POLineCreate,
    ReceiptCreate,
    ReceiveLine,
    StockLocationCreate,
    TransferCreate,
)
from app.modules.syerp.service import (
    add_line,
    advance_po_status,
    create_item,
    create_location,
    create_partner,
    create_po,
    get_bin_on_hand,
    get_item,
    get_po,
    post_adjustment,
    post_receipt,
    post_transfer,
    receive_line,
)

# ---------------------------------------------------------------------------
# PASS/FAIL bookkeeping
# ---------------------------------------------------------------------------

_FAILURES = 0

# Iterations per race (verify_gelato scenario-D calibration: enough repetitions
# that a removed lock reliably shows RED, while the whole script stays well
# under the CI timebox).
_ITERATIONS = 5


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
# Independent oracles (the assertion's OWN truth — never the service's figure)
# ---------------------------------------------------------------------------


async def _location_onhand(session_factory, item_id: str, location_id: int) -> Decimal:
    """Derive an item's on-hand at a location (signed SUM of its InventoryTxns)."""
    async with session_factory() as session:
        result = await session.execute(
            select(func.coalesce(func.sum(InventoryTxn.quantity), 0)).where(
                InventoryTxn.item_id == item_id,
                InventoryTxn.location_id == location_id,
            )
        )
        return Decimal(result.scalar() or 0)


async def _pool_onhand(
    session_factory, item_id: str, location_id: int, bin_id: int | None
) -> Decimal:
    """The named pool's on-hand via the null-aware get_bin_on_hand derivation."""
    async with session_factory() as session:
        return await get_bin_on_hand(session, item_id, location_id, bin_id)


# ---------------------------------------------------------------------------
# Fixture builders — throwaway items / PLUM parts / locations via REAL services
# ---------------------------------------------------------------------------


async def _make_item(
    session_factory, unique: str, tag: str, part_id: str | None = None
) -> str:
    """Create a throwaway SYERP InventoryItem (optionally PLUM-linked) via create_item."""
    async with session_factory() as session:
        item = await create_item(
            session,
            InventoryItemCreate(
                name=f"VERIFY-RACE {tag} {unique}",
                unit_of_measure="ea",
                plum_part_id=part_id,
            ),
        )
        return item.id


async def _make_part_with_revision(session, part_number: str) -> tuple[str, str]:
    """
    Insert a PLUM part + a RELEASED revision 1 directly via the ORM, returning
    (part_id, revision_id). Direct ORM inserts keep the fixture controllable
    rather than driving the whole draft->in_review->released FSM (mirrors
    verify_mousse). Non-numeric part numbers never disturb PLUM auto-numbering.
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
        description=f"verify_inventory_race {part_number}",
        unit_of_measure="ea",
        released_at=datetime.now(UTC),
    )
    session.add(rev)
    await session.flush()
    return part.id, rev.id


def _classify(results: list) -> tuple[list, list, list]:
    """
    Split gather(return_exceptions=True) results into (successes, http_422s,
    unexpected). Only a 422 counts as the expected floor-rejected loser; any
    other exception is "unexpected" and the scenario must FAIL on it — a crash
    (e.g. a deadlock) must never masquerade as correct serialization.
    """
    successes = [r for r in results if not isinstance(r, Exception)]
    http_422 = [
        r
        for r in results
        if isinstance(r, HTTPException) and r.status_code == 422
    ]
    unexpected = [
        r
        for r in results
        if isinstance(r, Exception)
        and not (isinstance(r, HTTPException) and r.status_code == 422)
    ]
    return successes, http_422, unexpected


# ---------------------------------------------------------------------------
# (A) MOUSSE issue × SYERP adjust — the SRD's named MIXED pair (SC2)
# ---------------------------------------------------------------------------
#
# THE LOCK IS WHAT MAKES THIS HOLD — and it must be the SAME lock on both paths.
# issue_components locks the component's InventoryItem row FOR UPDATE before its
# pool floor read; post_adjustment (Phase 4 Task 1) locks the SAME item-master
# row before ITS floor reads. Two concurrent 7-draws from a pool of 10 therefore
# serialize: the winner commits, the loser re-reads pool == 3 and is
# floor-rejected 422. Remove ONLY the adjust-path lock (mutation M1) and the
# adjust no longer queues — both writers read pool == 10 under READ COMMITTED,
# both append -7, and the derived on-hand lands at -4: MOUSSE's own lock alone
# cannot save a shared ledger from one unlocked writer.


async def scenario_a(
    session_factory,
    unique: str,
    actor_id: str,
    main_id: int,
    alt_id: int,
    part_ids: set[str],
    item_ids: set[str],
    wo_ids: set[str],
) -> None:
    """
    Per iteration: a fresh released WO whose single component holds 10 at the
    contended location (Main, unbinned) and 100 at a second location (ample
    everywhere but the contended pool — 12b fixture rule). Fire MOUSSE
    issue_components(7) and post_adjustment(-7) concurrently; exactly one wins.
    """
    all_ok = True
    detail = ""
    for i in range(_ITERATIONS):
        # Fixture: FG + one child (qty_per 7 × planned 1 → qty_required 7).
        async with session_factory() as session:
            fg_part_id, fg_rev_id = await _make_part_with_revision(
                session, f"P-RACE-{unique}-A{i}-fg"
            )
            child_part_id, _ = await _make_part_with_revision(
                session, f"P-RACE-{unique}-A{i}-ch"
            )
            part_ids.update({fg_part_id, child_part_id})
            session.add(
                PlumBomItem(
                    parent_revision_id=fg_rev_id, child_part_id=child_part_id,
                    qty=Decimal("7"), sort_order=0,
                )
            )
            await session.commit()
        fg_item_id = await _make_item(session_factory, unique, f"A{i}-FG", fg_part_id)
        child_item_id = await _make_item(session_factory, unique, f"A{i}-CH", child_part_id)
        item_ids.update({fg_item_id, child_item_id})

        # Contended pool: 10 at Main (unbinned). Ample elsewhere: 100 at the
        # second location — only the contended pool's floor can reject.
        async with session_factory() as session:
            await post_receipt(session, child_item_id, main_id, Decimal("10"),
                               Decimal("2"), actor_id)
        async with session_factory() as session:
            await post_receipt(session, child_item_id, alt_id, Decimal("100"),
                               Decimal("2"), actor_id)

        async with session_factory() as session:
            wo = await create_work_order(
                session,
                WorkOrderCreate(
                    plum_part_id=fg_part_id, planned_qty=Decimal("1"),
                    target_location_id=main_id,
                ),
                actor_id,
            )
        wo_ids.add(wo.id)
        async with session_factory() as session:
            await release_work_order(session, wo.id, actor_id)
        async with session_factory() as session:
            wo_detail = await get_work_order_detail(session, wo.id)
        comp_id = wo_detail.components[0].id

        # Barrier makes the race deterministic: each worker owns an INDEPENDENT
        # session, pre-warms its connection, then both enter their write together.
        barrier = asyncio.Barrier(2)

        async def _mousse_issue():
            # REAL router shape: IssueComponentsRequest exactly as
            # POST /mousse/work-orders/{id}/issue passes it (11a/11b keeper).
            request = IssueComponentsRequest(
                lines=[IssueComponentLine(component_id=comp_id, quantity=Decimal("7"))]
            )
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))  # pre-warm the connection
                await barrier.wait()
                return await issue_components(session, wo.id, request, actor_id)

        async def _syerp_adjust():
            # REAL router shape: AdjustmentCreate unpacked exactly as
            # post_adjustment_endpoint unpacks it (11a/11b keeper).
            data = AdjustmentCreate(
                location_id=main_id, qty_delta=Decimal("-7"),
                reason="verify_inventory_race (A) concurrent write-off",
            )
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))  # pre-warm the connection
                await barrier.wait()
                return await post_adjustment(
                    session,
                    item_id=child_item_id,
                    location_id=data.location_id,
                    qty_delta=data.qty_delta,
                    reason=data.reason,
                    actor_id=actor_id,
                    bin_id=data.bin_id,
                )

        results = await asyncio.gather(
            _mousse_issue(), _syerp_adjust(), return_exceptions=True
        )
        successes, http_422, unexpected = _classify(results)

        final_loc = await _location_onhand(session_factory, child_item_id, main_id)
        final_pool = await _pool_onhand(session_factory, child_item_id, main_id, None)

        if unexpected:
            all_ok = False
            detail = f"iter {i}: unexpected failure(s) {[repr(u) for u in unexpected]}"
            break
        if final_loc < 0 or final_pool < 0:
            all_ok = False
            detail = f"iter {i}: NEGATIVE on-hand loc={final_loc} pool={final_pool}"
            break
        if not (len(successes) == 1 and len(http_422) == 1):
            all_ok = False
            detail = (
                f"iter {i}: successes={len(successes)} http422={len(http_422)} "
                f"final loc on-hand={final_loc} (expected exactly 1 win + 1 422)"
            )
            break
        if not (final_loc == Decimal("3") and final_pool == Decimal("3")):
            all_ok = False
            detail = f"iter {i}: final loc={final_loc} pool={final_pool} (want 3/3)"
            break

    check(
        "(A/SC2 CRUX) MOUSSE issue(7) × SYERP adjust(-7) on a contended pool of 10: "
        "EXACTLY one succeeds and one is floor-rejected 422, final contended on-hand "
        f"== 3 EXACTLY, never negative — across {_ITERATIONS} iterations "
        "(the SHARED item-master lock serializes both modules)",
        all_ok,
        detail,
    )


# ---------------------------------------------------------------------------
# (B) adjust × transfer on the same source pool (SC2)
# ---------------------------------------------------------------------------


async def scenario_b(
    session_factory,
    unique: str,
    actor_id: str,
    main_id: int,
    alt_id: int,
    item_ids: set[str],
) -> None:
    """
    Per iteration: a fresh item with 10 at the source (Main, unbinned) and 100
    already at the destination (ample elsewhere). post_adjustment(-7) races
    post_transfer(7 → destination); exactly one wins the source pool.
    """
    all_ok = True
    detail = ""
    for i in range(_ITERATIONS):
        item_id = await _make_item(session_factory, unique, f"B{i}")
        item_ids.add(item_id)
        async with session_factory() as session:
            await post_receipt(session, item_id, main_id, Decimal("10"),
                               Decimal("3"), actor_id)
        async with session_factory() as session:
            await post_receipt(session, item_id, alt_id, Decimal("100"),
                               Decimal("3"), actor_id)

        barrier = asyncio.Barrier(2)

        async def _adjust():
            # REAL router shape (post_adjustment_endpoint unpacking).
            data = AdjustmentCreate(
                location_id=main_id, qty_delta=Decimal("-7"),
                reason="verify_inventory_race (B) concurrent write-off",
            )
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))  # pre-warm the connection
                await barrier.wait()
                return await post_adjustment(
                    session,
                    item_id=item_id,
                    location_id=data.location_id,
                    qty_delta=data.qty_delta,
                    reason=data.reason,
                    actor_id=actor_id,
                    bin_id=data.bin_id,
                )

        async def _transfer():
            # REAL router shape (post_transfer_endpoint unpacking).
            data = TransferCreate(
                from_location_id=main_id, to_location_id=alt_id, qty=Decimal("7"),
            )
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))  # pre-warm the connection
                await barrier.wait()
                return await post_transfer(
                    session,
                    item_id=item_id,
                    from_location_id=data.from_location_id,
                    to_location_id=data.to_location_id,
                    qty=data.qty,
                    actor_id=actor_id,
                    from_bin_id=data.from_bin_id,
                )

        results = await asyncio.gather(_adjust(), _transfer(), return_exceptions=True)
        successes, http_422, unexpected = _classify(results)

        final_src = await _location_onhand(session_factory, item_id, main_id)
        final_src_pool = await _pool_onhand(session_factory, item_id, main_id, None)

        if unexpected:
            all_ok = False
            detail = f"iter {i}: unexpected failure(s) {[repr(u) for u in unexpected]}"
            break
        if final_src < 0 or final_src_pool < 0:
            all_ok = False
            detail = f"iter {i}: NEGATIVE source on-hand loc={final_src} pool={final_src_pool}"
            break
        if not (len(successes) == 1 and len(http_422) == 1):
            all_ok = False
            detail = (
                f"iter {i}: successes={len(successes)} http422={len(http_422)} "
                f"final source on-hand={final_src} (expected exactly 1 win + 1 422)"
            )
            break
        if not (final_src == Decimal("3") and final_src_pool == Decimal("3")):
            all_ok = False
            detail = f"iter {i}: final source loc={final_src} pool={final_src_pool} (want 3/3)"
            break

    check(
        "(B/SC2) adjust(-7) × transfer(7) racing the SAME source pool of 10: EXACTLY "
        "one succeeds and one is floor-rejected 422, final source on-hand == 3 "
        f"EXACTLY, never negative — across {_ITERATIONS} iterations",
        all_ok,
        detail,
    )


# ---------------------------------------------------------------------------
# (C) receive_line × receive_line on ONE PO line (SC1)
# ---------------------------------------------------------------------------
#
# receive_line locks the PO HEADER row FOR UPDATE at load (_get_po_row
# for_update=True), before the status guard and the over-receipt read, so all
# concurrent receives on one PO serialize: the winner bumps qty_received to 7
# and commits; the loser then re-reads the line and 7 + 7 > 10 is
# over-receipt-rejected 422. Remove the for_update (mutation M3) and both read
# qty_received == 0, both pass the guard, and the line lands at 14 of 10.


async def scenario_c(
    session_factory,
    unique: str,
    actor_id: str,
    main_id: int,
    vendor_id: str,
    item_id: str,
    po_ids: set[str],
    line_ids: set[str],
) -> None:
    """
    Per iteration: a fresh approved PO with ONE line (ordered 10 @ 5). Two
    concurrent receives of 7 race the qty_received accumulator; exactly one
    lands, qty_received <= qty_ordered holds, and the header status is correct.
    """
    all_ok = True
    detail = ""
    for i in range(_ITERATIONS):
        async with session_factory() as session:
            po = await create_po(session, POCreate(vendor_id=vendor_id))
        po_ids.add(po.id)
        async with session_factory() as session:
            line = await add_line(
                session,
                po.id,
                POLineCreate(item_id=item_id, qty_ordered=Decimal("10"),
                             unit_cost=Decimal("5")),
            )
        line_ids.add(line.id)
        async with session_factory() as session:
            await advance_po_status(session, po.id, "approved", actor_id)

        barrier = asyncio.Barrier(2)

        async def _receive():
            # REAL router shape: ReceiveLine unpacked exactly as the
            # /receive endpoint unpacks it (11a/11b keeper).
            data = ReceiveLine(location_id=main_id, qty=Decimal("7"))
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))  # pre-warm the connection
                await barrier.wait()
                return await receive_line(
                    session,
                    po_id=po.id,
                    line_id=line.id,
                    location_id=data.location_id,
                    qty=data.qty,
                    actor_id=actor_id,
                )

        results = await asyncio.gather(_receive(), _receive(), return_exceptions=True)
        successes, http_422, unexpected = _classify(results)
        if unexpected:
            all_ok = False
            detail = f"iter {i}: unexpected failure(s) {[repr(u) for u in unexpected]}"
            break

        async with session_factory() as session:
            final_po = await get_po(session, po.id)
            line_receipts = (
                await session.execute(
                    select(func.count()).select_from(InventoryTxn).where(
                        InventoryTxn.source_type == "po_receipt",
                        InventoryTxn.source_id == line.id,
                    )
                )
            ).scalar()
        final_line = final_po.lines[0]

        if final_line.qty_received > final_line.qty_ordered:
            all_ok = False
            detail = (
                f"iter {i}: OVER-RECEIPT qty_received={final_line.qty_received} > "
                f"qty_ordered={final_line.qty_ordered}"
            )
            break
        if not (len(successes) == 1 and len(http_422) == 1):
            all_ok = False
            detail = (
                f"iter {i}: successes={len(successes)} http422={len(http_422)} "
                f"qty_received={final_line.qty_received} (expected exactly 1 win + 1 422)"
            )
            break
        if not (
            final_line.qty_received == Decimal("7")
            and final_po.status == "partially_received"
            and line_receipts == 1
        ):
            all_ok = False
            detail = (
                f"iter {i}: qty_received={final_line.qty_received} (want 7) "
                f"status={final_po.status!r} (want 'partially_received') "
                f"line receipt txns={line_receipts} (want 1)"
            )
            break

    check(
        "(C/SC1) two concurrent receive_line(7) on ONE PO line ordered 10: EXACTLY one "
        "succeeds and one is over-receipt-rejected 422, qty_received == 7 <= 10, header "
        f"'partially_received', ONE source-linked receipt txn — across {_ITERATIONS} "
        "iterations (the PO-header lock serializes the accumulator)",
        all_ok,
        detail,
    )


# ---------------------------------------------------------------------------
# (D) receipt × receipt — moving-average integrity (SC1)
# ---------------------------------------------------------------------------
#
# Receipts take no floor, so BOTH concurrent receipts succeed — the contended
# invariant is the item-level moving average's read-recompute-write. post_receipt
# locks the item-master row FOR UPDATE and then REFRESHES the identity-mapped
# item under the lock, so the second receipt reads the first's committed
# qty_before/avg and computes the true weighted average. Starting from ZERO
# stock makes the expected figure order-independent: whichever receipt lands
# first sets avg = its own unit cost exactly, and the second computes
# (7*10 + 5*9) / 12 == 115/12 → 9.583333 (quantized, indivisible remainder).
# Remove the lock + refresh (mutation M4) and both read qty_before == 0: each
# computes avg = its OWN unit cost and the last commit wins — final avg
# 10.000000 or 9.000000, a lost update the 9.583333 assertion catches.


async def scenario_d(
    session_factory,
    unique: str,
    actor_id: str,
    main_id: int,
    item_ids: set[str],
) -> None:
    """
    Per iteration: a fresh zero-stock item; post_receipt(7 @ 10) races
    post_receipt(5 @ 9). Both must succeed and the final moving_avg_cost must
    equal the sequential two-receipt computation EXACTLY (115/12 → 9.583333).
    """
    expected_avg = ((Decimal("7") * Decimal("10") + Decimal("5") * Decimal("9"))
                    / Decimal("12")).quantize(Decimal("0.000001"))

    all_ok = True
    detail = ""
    for i in range(_ITERATIONS):
        item_id = await _make_item(session_factory, unique, f"D{i}")
        item_ids.add(item_id)

        barrier = asyncio.Barrier(2)

        async def _receipt(qty: str, unit_cost: str, item_id=item_id, barrier=barrier):
            # REAL router shape: ReceiptCreate unpacked exactly as
            # post_receipt_endpoint unpacks it (11a/11b keeper).
            data = ReceiptCreate(
                location_id=main_id, qty=Decimal(qty), unit_cost=Decimal(unit_cost),
            )
            async with session_factory() as session:
                await session.execute(text("SELECT 1"))  # pre-warm the connection
                await barrier.wait()
                return await post_receipt(
                    session,
                    item_id=item_id,
                    location_id=data.location_id,
                    qty=data.qty,
                    unit_cost=data.unit_cost,
                    actor_id=actor_id,
                    source_type=data.source_type,
                    source_id=data.source_id,
                )

        results = await asyncio.gather(
            _receipt("7", "10"), _receipt("5", "9"), return_exceptions=True
        )
        successes = [r for r in results if not isinstance(r, Exception)]
        if len(successes) != 2:
            failures = [r for r in results if isinstance(r, Exception)]
            all_ok = False
            detail = (
                f"iter {i}: only {len(successes)} of 2 receipts succeeded "
                f"(failures={[type(f).__name__ for f in failures]})"
            )
            break

        async with session_factory() as session:
            item = await get_item(session, item_id)
        final_onhand = await _location_onhand(session_factory, item_id, main_id)

        if not (item.moving_avg_cost == expected_avg and final_onhand == Decimal("12")):
            all_ok = False
            detail = (
                f"iter {i}: moving_avg_cost={item.moving_avg_cost!r} "
                f"(want {expected_avg!r} — a lost update reads 10.000000 or 9.000000) "
                f"on-hand={final_onhand!r} (want 12)"
            )
            break

    check(
        "(D/SC1 CRUX) two concurrent receipts (7 @ 10, 5 @ 9) on a zero-stock item: "
        "both succeed and the final moving_avg_cost equals the sequential computation "
        f"EXACTLY (115/12 → {expected_avg}) — no lost update, across {_ITERATIONS} "
        "iterations (the item-master lock + refresh serialize the recompute)",
        all_ok,
        detail,
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def run() -> None:
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    actor_id = str(uuid.uuid4())  # stand-in for the acting user
    unique = uuid.uuid4().hex[:8]

    # Throwaway-row registries for the finally cleanup.
    part_ids: set[str] = set()
    item_ids: set[str] = set()
    wo_ids: set[str] = set()
    po_ids: set[str] = set()
    line_ids: set[str] = set()
    loc_ids: set[int] = set()
    vendor_ids: set[str] = set()

    try:
        # Seed (idempotent) + reuse the "Main" stock location; resolve the seeded
        # GL accounts the issue/receive paths post JEs against (fresh-CI-DB safe:
        # CI runs run_seeds before the scripts, and the api container seeds at
        # boot — this only VERIFIES they resolve).
        async with session_factory() as session:
            await seed_default_location(session)
        async with session_factory() as session:
            main_rows = (
                await session.execute(
                    select(StockLocation).where(StockLocation.name == DEFAULT_LOCATION_NAME)
                )
            ).scalars().all()
            acct_codes = ["1130", "1140", "2150"]
            accts = {
                code: (
                    await session.execute(select(GLAccount.id).where(GLAccount.code == code))
                ).scalar()
                for code in acct_codes
            }
        check(
            "setup: exactly one seeded 'Main' location and the 1130/1140/2150 GL "
            "accounts resolve (the issue/receive JEs need them)",
            len(main_rows) == 1 and all(accts[c] is not None for c in acct_codes),
            f"main={len(main_rows)} accts={accts!r}",
        )
        main_id = main_rows[0].id

        # A throwaway SECOND location: (A)'s ample-elsewhere stock and (B)'s
        # transfer destination.
        async with session_factory() as session:
            alt = await create_location(
                session, StockLocationCreate(name=f"VERIFY-RACE-{unique}")
            )
        alt_id = alt.id
        loc_ids.add(alt_id)

        # Shared (C) fixtures: one vendor + one PO-line item across iterations
        # (each iteration gets its own fresh PO + line — the contended rows).
        async with session_factory() as session:
            vendor = await create_partner(
                session, PartnerCreate(name=f"VERIFY-RACE Vendor {unique}", is_vendor=True)
            )
        vendor_ids.add(vendor.id)
        po_item_id = await _make_item(session_factory, unique, "C-PO")
        item_ids.add(po_item_id)

        await scenario_a(session_factory, unique, actor_id, main_id, alt_id,
                         part_ids, item_ids, wo_ids)
        await scenario_b(session_factory, unique, actor_id, main_id, alt_id, item_ids)
        await scenario_c(session_factory, unique, actor_id, main_id, vendor.id,
                         po_item_id, po_ids, line_ids)
        await scenario_d(session_factory, unique, actor_id, main_id, item_ids)

    finally:
        await _cleanup(session_factory, part_ids, item_ids, wo_ids, po_ids,
                       line_ids, loc_ids, vendor_ids)
        await engine.dispose()


# ---------------------------------------------------------------------------
# Cleanup — delete only the throwaway rows, in FK-safe order
# ---------------------------------------------------------------------------


async def _cleanup(
    session_factory,
    part_ids: set[str],
    item_ids: set[str],
    wo_ids: set[str],
    po_ids: set[str],
    line_ids: set[str],
    loc_ids: set[int],
    vendor_ids: set[str],
) -> None:
    """
    Delete the throwaway rows in FK-safe order: WO issues → the WOs'/PO lines'
    source-linked journal lines/entries → WO components → work orders → PO
    lines → POs → inventory txns → inventory items → BOM items → revisions →
    parts → locations → vendors. The seeded "Main" location and GL accounts are
    reused and left in place (real deploy state).
    """
    async with session_factory() as session:
        wo_list = list(wo_ids)
        po_list = list(po_ids)
        line_list = list(line_ids)
        item_list = list(item_ids)
        part_list = list(part_ids)

        if wo_list:
            await session.execute(
                delete(WorkOrderIssue).where(WorkOrderIssue.work_order_id.in_(wo_list))
            )

        # JEs soft-linked to the throwaway WOs (mousse issue) and PO lines
        # (receive_line's Dr 1130 / Cr 2150 posting).
        je_filters = []
        if wo_list:
            je_filters.append(
                (JournalEntry.source_type == "mousse_work_order")
                & JournalEntry.source_id.in_(wo_list)
            )
        if line_list:
            je_filters.append(
                (JournalEntry.source_type == "po_receipt")
                & JournalEntry.source_id.in_(line_list)
            )
        if je_filters:
            entry_ids = (
                await session.execute(select(JournalEntry.id).where(or_(*je_filters)))
            ).scalars().all()
            if entry_ids:
                await session.execute(
                    delete(JournalLine).where(JournalLine.entry_id.in_(entry_ids))
                )
                await session.execute(
                    delete(JournalEntry).where(JournalEntry.id.in_(entry_ids))
                )

        if wo_list:
            await session.execute(
                delete(WorkOrderComponent).where(
                    WorkOrderComponent.work_order_id.in_(wo_list)
                )
            )
            await session.execute(delete(WorkOrder).where(WorkOrder.id.in_(wo_list)))

        if po_list:
            await session.execute(
                delete(PurchaseOrderLine).where(PurchaseOrderLine.po_id.in_(po_list))
            )
            await session.execute(
                delete(PurchaseOrder).where(PurchaseOrder.id.in_(po_list))
            )

        if item_list:
            await session.execute(
                delete(InventoryTxn).where(InventoryTxn.item_id.in_(item_list))
            )
            await session.execute(
                delete(InventoryItem).where(InventoryItem.id.in_(item_list))
            )

        if part_list:
            await session.execute(
                delete(PlumBomItem).where(PlumBomItem.child_part_id.in_(part_list))
            )
            await session.execute(
                delete(PlumPartRevision).where(PlumPartRevision.part_id.in_(part_list))
            )
            await session.execute(delete(PlumPart).where(PlumPart.id.in_(part_list)))

        if loc_ids:
            await session.execute(
                delete(StockLocation).where(StockLocation.id.in_(list(loc_ids)))
            )

        if vendor_ids:
            await session.execute(
                delete(Partner).where(Partner.id.in_(list(vendor_ids)))
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
