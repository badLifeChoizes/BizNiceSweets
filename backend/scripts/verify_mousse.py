# ABOUTME: Standalone live-DB verification for the MOUSSE work-order engine (Phase 10).
# ABOUTME: Builds its OWN async engine from POSTGRES_* env (no conftest fixtures) and drives
# ABOUTME: the REAL mousse service create/release/issue/complete + hold/resume end-to-end,
# ABOUTME: proving the single-level BOM snapshot, the signed-issue Dr1140/Cr1130 posting, and
# ABOUTME: THE CRUX — the WO's 1140 WIP balance clears back to its pre-issue value Decimal-exactly;
# ABOUTME: exits non-zero on FAIL and self-cleans so it is safe to re-run.
"""
Standalone live-DB verification script for the MOUSSE work-order engine (Phase 10).

WHY THIS EXISTS (the MOUSSE materials-only crux, MOUSSE-01 / SC1..SC5):
  A work order (WO) consumes a PLUM single-level BOM and SYERP inventory to
  produce a finished good, booking actual moving-average material cost through
  the 1140 Work-in-Process clearing account:

    * ISSUE    posts one signed `issue` InventoryTxn per component at the item's
               moving_avg_cost and ONE balanced JE Dr 1140 WIP / Cr 1130 Inventory
               for Σ(qty × moving_avg), all in one atomic commit.
    * COMPLETE receives the planned output at accumulated-WIP unit cost via
               post_receipt(commit=False) and posts the mirror JE Dr 1130 / Cr 1140,
               crediting 1140 for EXACTLY the accumulated WIP debits so the WO's
               1140-attributable balance returns to its pre-issue value.

  The load-bearing invariant (SC3, THE CRUX) is that a WO's 1140-attributable
  balance returns to its pre-issue snapshot **Decimal-exactly** after completion —
  no rounding residual may strand WIP, even when accumulated_wip / planned_qty does
  not divide evenly (the completion JE credits the exact accumulated WIP to 1140).
  The mirror invariant (D-P10-2 amended) is that the 1130 control account ties to
  the inventory subledger: the JE debits 1130 by EXACTLY the FG receipt value
  (planned_qty × fg_unit_cost) and routes the sub-quantum residual to 5190 Inventory
  Rounding, so neither 1140 strands WIP nor 1130 silently drifts. None of that can be proven
  by the pure unit tests, and the backend live-DB pytest harness is broken (D-P7-4),
  so DB-dependent tests skip under plain ``pytest``. Verifiable truth must therefore
  come from a STANDALONE run against LIVE Postgres. This script stands up its own
  async engine + sessionmaker from the ``POSTGRES_*`` environment variables — it
  deliberately does NOT import the broken test conftest fixtures — and drives the
  REAL service functions end-to-end.

HOW TO RUN (the compose ``db`` service is not host-published):
  podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d db api
  podman exec -e PYTHONPATH=/app compose_api_1 python scripts/verify_mousse.py

SCENARIO (each line prints PASS:/FAIL:; exits non-zero on any FAIL):
  (A) HAPPY PATH + WIP CLEARS TO ZERO (SC1/SC2/SC3/SC1b): create a WO against a
      PLUM part with a Released revision whose direct BOM has two children (each
      linked to a stocked InventoryItem) and a linked FG item. Release snapshots
      exactly the BOM child lines with qty_required == qty_per * planned_qty; the
      WO's 1140-attributable balance is snapshotted BEFORE any issue. Issuing all
      components decrements each item's on-hand per location, posts ONE Dr 1140 /
      Cr 1130 JE for Σ(qty × moving_avg), flips the WO to In Progress, and writes a
      WorkOrderIssue row per component. Pausing (In Progress -> On Hold) rejects a
      further issue (must resume first) and resuming returns to In Progress.
      Completion receives planned_qty of FG at the accumulated-WIP unit cost
      (updating the FG moving average) and — THE CRUX — the WO's 1140-attributable
      balance equals its pre-issue snapshot Decimal-exactly.
  (B) RELEASE REJECTS (SC1 / D-P10-7): a WO whose part has NO Released revision is
      rejected 4xx with nothing persisted; a WO whose BOM has a child with NO linked
      InventoryItem is rejected 4xx with NO partial snapshot (no component rows).
  (C) ISSUE FLOOR + FSM (SC2/SC1): issuing beyond on-hand is rejected 4xx with the
      on-hand unchanged and zero issue rows written; illegal FSM transitions
      (complete a Released WO, hold a Released WO, resume an In-Progress WO) are 4xx.
  (D) UNDER-ISSUE COMPLETION (D-P10-9): completing an under-issued WO WITHOUT
      override is rejected 4xx and the WO stays In Progress; WITH
      override_incomplete=True it completes AND — even though accumulated_wip /
      planned_qty leaves a per-unit residual — the WO's 1140-attributable balance
      still clears to its pre-issue snapshot Decimal-exactly.
  (E) TRIAL BALANCE (SC4): after all WO activity the trial balance still nets zero
      (total_debit == total_credit), a global double-entry invariant.
  (F) CONCURRENCY (SC5, task 13): two identical concurrent issues against a WO whose
      component has on-hand enough for exactly ONE cannot both succeed — the FOR
      UPDATE row lock serializes them, on-hand never goes negative, no double-
      consume, and the WO's WIP reflects only the ONE successful issue.
  (G) BINNED ISSUE (Phase 4 / D-P4-1) + LEGACY-DESYNC LOCATION FLOOR: (G1) at a
      fully-binned component location (receive 10, putaway ALL into a bin) an
      issue with bin_id=None draws ONLY the empty UNBINNED pool and is rejected
      422 with ZERO ledger/issue rows; naming the bin succeeds — the issue txn
      rows carry the bin_id, the bin pool draws to the exact remainder, and the
      WIP/JE amounts are IDENTICAL to the unbinned equivalent (bins are a
      quantity dimension, never a valuation one). (G2) the location floor is
      kept ALONGSIDE the pool floor: against a legacy pre-Phase-4 desync (bin
      pool reads 10, unbinned pool -10, location total 0 — simulated by a
      raw-inserted bin-blind issue row) a bin-named issue of 10 passes the pool
      guard but MUST be rejected 422 by the location floor with zero rows
      written — the pool floors imply the location floor only on clean
      post-Phase-4 data.

The script uses uniquely-suffixed throwaway PLUM parts / SYERP items / GELATO bins /
work orders and CLEANS UP after itself (issues -> mousse JEs -> components -> work
orders -> inventory txns -> bins -> items -> BOM items -> revisions -> parts) in a
finally block, so it is safe to re-run against the same database. The seeded "Main"
stock location and the seeded 1130/1140 GL accounts are reused and left in place
(real deploy state).
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Make the backend root importable when run as a bare `python scripts/verify_mousse.py`
# (sys.path[0] is the scripts/ dir, so `app` would otherwise not resolve without an
# explicit PYTHONPATH=/app — the sibling verify_*.py scripts require that env var).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the central model aggregator FIRST so Base.metadata is fully populated
# (the mousse_* FKs reference plum_* and syerp_* tables that must be registered
# before the FKs resolve — the Task-8 lesson).
import app.core.models  # noqa: F401
from app.modules.gelato.models import Bin
from app.modules.gelato.schemas import BinCreate, PutawayRequest
from app.modules.gelato.service import create_bin, execute_putaway, get_bin_on_hand
from app.modules.mousse.models import WorkOrder, WorkOrderComponent, WorkOrderIssue
from app.modules.mousse.schemas import (
    IssueComponentLine,
    IssueComponentsRequest,
    WorkOrderCreate,
)
from app.modules.mousse.service import (
    complete_work_order,
    create_work_order,
    get_work_order_detail,
    hold_work_order,
    issue_components,
    release_work_order,
    resume_work_order,
)
from app.modules.plum.models import PlumBomItem, PlumPart, PlumPartRevision
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME, seed_default_location
from app.modules.syerp.models import (
    GLAccount,
    InventoryItem,
    InventoryTxn,
    JournalEntry,
    JournalLine,
    StockLocation,
)
from app.modules.syerp.schemas import InventoryItemCreate
from app.modules.syerp.service import create_item, get_item, post_receipt, trial_balance

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
# Shared derivations (independent of the service — the assertion's own truth)
# ---------------------------------------------------------------------------


async def _account_id_by_code(session, code: str) -> int:
    """Resolve a seeded GL account id by its Chart-of-Accounts `code`."""
    result = await session.execute(select(GLAccount.id).where(GLAccount.code == code))
    return result.scalar()


async def _onhand(session, item_id: str, location_id: int) -> Decimal:
    """Derive an item's on-hand at a location (signed SUM of its InventoryTxns)."""
    result = await session.execute(
        select(func.coalesce(func.sum(InventoryTxn.quantity), 0)).where(
            InventoryTxn.item_id == item_id,
            InventoryTxn.location_id == location_id,
        )
    )
    return Decimal(result.scalar() or 0)


async def _txn_rows(session, item_id: str) -> int:
    """Independent oracle: the count of ledger rows for an item (a rejected issue
    must write NOTHING — row count unchanged)."""
    result = await session.execute(
        select(func.count()).select_from(InventoryTxn).where(InventoryTxn.item_id == item_id)
    )
    return result.scalar()


async def _wo_account_balance(session, account_id: int, wo_id: str) -> Decimal:
    """
    Derive a WO's balance on a GL account (Σdebit − Σcredit) — the assertion's OWN
    computation over the journal lines of every JE soft-linked to THIS work order
    (source_type='mousse_work_order', source_id=wo_id). Independent of the service's
    internal helper so the crux (1140 clears to zero) is proven, not assumed.
    """
    result = await session.execute(
        select(
            func.coalesce(func.sum(JournalLine.debit), 0)
            - func.coalesce(func.sum(JournalLine.credit), 0)
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .where(
            JournalLine.account_id == account_id,
            JournalEntry.source_type == "mousse_work_order",
            JournalEntry.source_id == wo_id,
        )
    )
    return Decimal(result.scalar() or 0)


# ---------------------------------------------------------------------------
# Fixture builders — PLUM part + Released revision, BOM, linked SYERP items
# ---------------------------------------------------------------------------


async def _make_part_with_revision(
    session, part_number: str, *, released: bool, uom: str = "ea"
) -> tuple[str, str]:
    """
    Insert a PLUM part + its revision 1 directly via the ORM, returning
    (part_id, revision_id). `released=True` writes a Released revision (the WO
    release snapshots against it); `released=False` leaves it Draft (used to prove
    the no-Released-revision rejection). Direct ORM inserts keep the fixture fully
    controllable rather than driving the whole draft->in_review->released FSM.
    """
    part = PlumPart(id=str(uuid.uuid4()), part_number=part_number, active=True)
    session.add(part)
    await session.flush()
    rev = PlumPartRevision(
        id=str(uuid.uuid4()),
        part_id=part.id,
        revision_number=1,
        revision_label="A",
        status="released" if released else "draft",
        description=f"verify_mousse {part_number}",
        unit_of_measure=uom,
        released_at=datetime.now(UTC) if released else None,
    )
    session.add(rev)
    await session.flush()
    return part.id, rev.id


async def _link_item(session_factory, unique: str, tag: str, part_id: str | None) -> str:
    """
    Create a SYERP InventoryItem (optionally linked to a PLUM part) and return its
    id. create_item auto-generates the ITEM-#### code and commits its own unit of
    work, so this runs in its own session.
    """
    async with session_factory() as session:
        item = await create_item(
            session,
            InventoryItemCreate(
                name=f"VERIFY-MOUSSE {tag} {unique}",
                unit_of_measure="ea",
                plum_part_id=part_id,
            ),
        )
        return item.id


async def run() -> None:  # noqa: C901 - one long linear verification scenario
    engine = create_async_engine(build_dsn(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    actor_id = str(uuid.uuid4())  # stand-in for the acting user
    unique = uuid.uuid4().hex[:8]

    # Throwaway-row registries for the finally cleanup.
    part_ids: set[str] = set()
    item_ids: set[str] = set()
    wo_ids: set[str] = set()
    bin_ids: set[int] = set()

    def _pn(*parts: object) -> str:
        # Non-numeric part numbers never disturb PLUM auto-numbering (P##### series).
        return f"P-MO-{unique}-" + "-".join(str(p) for p in parts)

    try:
        # -------------------------------------------------------------------
        # Setup: seed (idempotent) + reuse the "Main" stock location; resolve
        # the seeded 1130 Inventory / 1140 WIP GL accounts.
        # -------------------------------------------------------------------
        async with session_factory() as session:
            await seed_default_location(session)
        async with session_factory() as session:
            main_rows = (
                await session.execute(
                    select(StockLocation).where(StockLocation.name == DEFAULT_LOCATION_NAME)
                )
            ).scalars().all()
            acct_1130 = await _account_id_by_code(session, "1130")
            acct_1140 = await _account_id_by_code(session, "1140")
            acct_5190 = await _account_id_by_code(session, "5190")
        check(
            "setup: exactly one seeded 'Main' location and 1130/1140/5190 GL accounts resolve",
            len(main_rows) == 1 and acct_1130 is not None and acct_1140 is not None
            and acct_5190 is not None,
            f"main={len(main_rows)} 1130={acct_1130!r} 1140={acct_1140!r} 5190={acct_5190!r}",
        )
        main_id = main_rows[0].id

        # ===================================================================
        # (A) HAPPY PATH + WIP CLEARS TO ZERO (SC1/SC2/SC3/SC1b)
        # ===================================================================
        planned_qty = Decimal("10")
        # Two BOM children: A qty_per 2 @ moving_avg 3, B qty_per 3 @ moving_avg 5.
        #   qty_required: A 20, B 30. Issue value: A 60, B 150 -> WIP 210.
        #   fg_unit_cost = 210 / 10 = 21.000000 (exact).
        async with session_factory() as session:
            fg_part_id, fg_rev_id = await _make_part_with_revision(
                session, _pn("A", "fg"), released=True
            )
            child_a_id, _ = await _make_part_with_revision(session, _pn("A", "ca"), released=True)
            child_b_id, _ = await _make_part_with_revision(session, _pn("A", "cb"), released=True)
            part_ids.update({fg_part_id, child_a_id, child_b_id})
            session.add(
                PlumBomItem(
                    parent_revision_id=fg_rev_id, child_part_id=child_a_id,
                    qty=Decimal("2"), sort_order=0,
                )
            )
            session.add(
                PlumBomItem(
                    parent_revision_id=fg_rev_id, child_part_id=child_b_id,
                    qty=Decimal("3"), sort_order=1,
                )
            )
            await session.commit()

        fg_item_id = await _link_item(session_factory, unique, "A-FG", fg_part_id)
        item_a_id = await _link_item(session_factory, unique, "A-CA", child_a_id)
        item_b_id = await _link_item(session_factory, unique, "A-CB", child_b_id)
        item_ids.update({fg_item_id, item_a_id, item_b_id})

        # Give the components on-hand stock (also establishes their moving averages).
        async with session_factory() as session:
            await post_receipt(session, item_a_id, main_id, Decimal("100"), Decimal("3"), actor_id)
        async with session_factory() as session:
            await post_receipt(session, item_b_id, main_id, Decimal("100"), Decimal("5"), actor_id)

        # --- create ---
        async with session_factory() as session:
            wo = await create_work_order(
                session,
                WorkOrderCreate(
                    plum_part_id=fg_part_id, planned_qty=planned_qty, target_location_id=main_id
                ),
                actor_id,
            )
        wo_a_id = wo.id
        wo_ids.add(wo_a_id)
        check(
            "(A) create_work_order opens a Draft WO with a WO-###### number",
            wo.status == "draft" and wo.wo_number.startswith("WO-"),
            f"status={wo.status!r} number={wo.wo_number!r}",
        )

        # --- release (single-level BOM snapshot) ---
        async with session_factory() as session:
            released = await release_work_order(session, wo_a_id, actor_id)
        async with session_factory() as session:
            detail = await get_work_order_detail(session, wo_a_id)
        comps = {c.child_part_id: c for c in detail.components}
        check(
            "(A) release snapshots exactly the direct-BOM children (2 lines) and "
            "sets status Released with the FG output item resolved",
            released.status == "released"
            and len(detail.components) == 2
            and released.output_item_id == fg_item_id
            and released.released_revision_id == fg_rev_id,
            f"status={released.status!r} lines={len(detail.components)} "
            f"output={released.output_item_id!r}",
        )
        check(
            "(A) qty_required == qty_per * planned_qty for each snapshot line "
            "(A: 2*10==20, B: 3*10==30)",
            child_a_id in comps and child_b_id in comps
            and comps[child_a_id].qty_required == Decimal("20")
            and comps[child_a_id].qty_per == Decimal("2")
            and comps[child_b_id].qty_required == Decimal("30")
            and comps[child_b_id].qty_per == Decimal("3"),
            f"A={comps.get(child_a_id) and comps[child_a_id].qty_required!r} "
            f"B={comps.get(child_b_id) and comps[child_b_id].qty_required!r}",
        )
        comp_a_id = comps[child_a_id].id
        comp_b_id = comps[child_b_id].id

        # --- snapshot the WO's 1140-attributable balance BEFORE any issue ---
        async with session_factory() as session:
            wip_pre_issue = await _wo_account_balance(session, acct_1140, wo_a_id)
        check(
            "(A) the WO's 1140-attributable balance is 0 before any issue "
            "(no JE posted yet) — the pre-issue snapshot",
            wip_pre_issue == Decimal("0"),
            f"pre_issue_1140={wip_pre_issue!r}",
        )

        # --- issue all components ---
        async with session_factory() as session:
            issue_result = await issue_components(
                session,
                wo_a_id,
                IssueComponentsRequest(
                    lines=[
                        IssueComponentLine(component_id=comp_a_id, quantity=Decimal("20")),
                        IssueComponentLine(component_id=comp_b_id, quantity=Decimal("30")),
                    ]
                ),
                actor_id,
            )
        expected_wip = Decimal("60") + Decimal("150")  # 20*3 + 30*5 == 210
        check(
            "(A) issuing all components booked Σ(qty × moving_avg) == 210.000000 "
            "into WIP and reports both lines issued",
            issue_result.total_issued_value == Decimal("210.000000")
            and issue_result.lines_issued == 2,
            f"value={issue_result.total_issued_value!r} lines={issue_result.lines_issued}",
        )

        async with session_factory() as session:
            onhand_a = await _onhand(session, item_a_id, main_id)
            onhand_b = await _onhand(session, item_b_id, main_id)
            wip_after_issue = await _wo_account_balance(session, acct_1140, wo_a_id)
            inv_after_issue = await _wo_account_balance(session, acct_1130, wo_a_id)
            issue_rows = (
                await session.execute(
                    select(func.count()).select_from(WorkOrderIssue).where(
                        WorkOrderIssue.work_order_id == wo_a_id
                    )
                )
            ).scalar()
            wo_after_issue = (
                await session.execute(select(WorkOrder.status).where(WorkOrder.id == wo_a_id))
            ).scalar()
        check(
            "(A) issue decremented each component's on-hand per location "
            "(A: 100-20==80, B: 100-30==70)",
            onhand_a == Decimal("80") and onhand_b == Decimal("70"),
            f"onhand_a={onhand_a!r} onhand_b={onhand_b!r}",
        )
        check(
            "(A) the issue posted ONE balanced JE Dr 1140 210 / Cr 1130 210 "
            "attributable to the WO (1140 == +210, 1130 == -210)",
            wip_after_issue == expected_wip and inv_after_issue == -expected_wip,
            f"1140={wip_after_issue!r} 1130={inv_after_issue!r}",
        )
        check(
            "(A) issuing wrote a WorkOrderIssue row per component (2) and flipped the "
            "WO to In Progress",
            issue_rows == 2 and wo_after_issue == "in_progress",
            f"issue_rows={issue_rows!r} status={wo_after_issue!r}",
        )

        # --- hold / resume (SC1b) + issue-while-on-hold rejection ---
        async with session_factory() as session:
            held = await hold_work_order(session, wo_a_id, actor_id)
        check(
            "(A/SC1b) In Progress -> hold -> On Hold",
            held.status == "on_hold",
            f"status={held.status!r}",
        )
        try:
            async with session_factory() as session:
                await issue_components(
                    session,
                    wo_a_id,
                    IssueComponentsRequest(
                        lines=[IssueComponentLine(component_id=comp_a_id, quantity=Decimal("1"))]
                    ),
                    actor_id,
                )
            check("(A/SC1b) issuing while On Hold is rejected (must resume first)", False,
                  "issue succeeded while On Hold")
        except HTTPException as exc:
            check(
                "(A/SC1b) issuing while On Hold is rejected 4xx (must resume first)",
                400 <= exc.status_code < 500,
                f"status={exc.status_code}",
            )
        async with session_factory() as session:
            resumed = await resume_work_order(session, wo_a_id, actor_id)
        check(
            "(A/SC1b) On Hold -> resume -> In Progress",
            resumed.status == "in_progress",
            f"status={resumed.status!r}",
        )

        # --- complete: FG receipt + WIP clears to the pre-issue snapshot (CRUX) ---
        async with session_factory() as session:
            complete_result = await complete_work_order(session, wo_a_id, actor_id)
        async with session_factory() as session:
            fg_item = await get_item(session, fg_item_id)
            wip_post_complete = await _wo_account_balance(session, acct_1140, wo_a_id)
            wo_final = (
                await session.execute(select(WorkOrder).where(WorkOrder.id == wo_a_id))
            ).scalars().first()
        fg_unit_cost = (expected_wip / planned_qty).quantize(Decimal("0.000001"))
        check(
            "(A) completion received planned_qty (10) of FG at the accumulated-WIP unit "
            "cost (210/10 == 21.000000) and updated the FG moving average",
            complete_result.quantity_received == planned_qty
            and fg_item.moving_avg_cost == fg_unit_cost
            and fg_item.moving_avg_cost == Decimal("21.000000"),
            f"received={complete_result.quantity_received!r} fg_avg={fg_item.moving_avg_cost!r} "
            f"expected={fg_unit_cost!r}",
        )
        check(
            "(A) CRUX (SC3): the WO's 1140-attributable balance returns to its "
            "pre-issue snapshot Decimal-EXACTLY after completion (WIP clears to zero)",
            wip_post_complete == wip_pre_issue and wip_post_complete == Decimal("0"),
            f"pre_issue={wip_pre_issue!r} post_complete={wip_post_complete!r}",
        )
        print(
            f"      (crux detail) 1140 pre_issue={wip_pre_issue} after_issue={wip_after_issue} "
            f"post_complete={wip_post_complete}"
        )
        check(
            "(A) the WO is Completed with completed_at stamped",
            wo_final is not None and wo_final.status == "completed"
            and wo_final.completed_at is not None,
            f"status={wo_final.status if wo_final else None!r}",
        )
        # Completed is terminal: completing again is an illegal FSM transition.
        try:
            async with session_factory() as session:
                await complete_work_order(session, wo_a_id, actor_id)
            check("(A) completing an already-Completed WO is rejected (terminal)", False,
                  "second completion succeeded")
        except HTTPException as exc:
            check(
                "(A) completing an already-Completed WO is rejected 4xx (terminal state)",
                400 <= exc.status_code < 500,
                f"status={exc.status_code}",
            )

        # ===================================================================
        # (B) RELEASE REJECTS (SC1 / D-P10-7)
        # ===================================================================
        # (B1) part with NO Released revision -> release 4xx, nothing persisted.
        async with session_factory() as session:
            norev_part_id, _ = await _make_part_with_revision(
                session, _pn("B1", "part"), released=False
            )
            part_ids.add(norev_part_id)
            await session.commit()
        norev_item_id = await _link_item(session_factory, unique, "B1", norev_part_id)
        item_ids.add(norev_item_id)
        async with session_factory() as session:
            wo_b1 = await create_work_order(
                session,
                WorkOrderCreate(
                    plum_part_id=norev_part_id, planned_qty=Decimal("1"),
                    target_location_id=main_id,
                ),
                actor_id,
            )
        wo_ids.add(wo_b1.id)
        try:
            async with session_factory() as session:
                await release_work_order(session, wo_b1.id, actor_id)
            check("(B1) releasing a WO whose part has no Released revision is rejected", False,
                  "release succeeded")
        except HTTPException as exc:
            check(
                "(B1) releasing a WO whose part has no Released revision is rejected 4xx",
                400 <= exc.status_code < 500,
                f"status={exc.status_code}",
            )
        async with session_factory() as session:
            b1_status = (
                await session.execute(select(WorkOrder.status).where(WorkOrder.id == wo_b1.id))
            ).scalar()
            b1_comps = (
                await session.execute(
                    select(func.count()).select_from(WorkOrderComponent).where(
                        WorkOrderComponent.work_order_id == wo_b1.id
                    )
                )
            ).scalar()
        check(
            "(B1) the rejected release persisted NOTHING (WO still Draft, zero components)",
            b1_status == "draft" and b1_comps == 0,
            f"status={b1_status!r} components={b1_comps!r}",
        )

        # (B2) a BOM child with NO linked InventoryItem -> release 4xx, NO partial snapshot.
        async with session_factory() as session:
            b2_fg_id, b2_fg_rev = await _make_part_with_revision(
                session, _pn("B2", "fg"), released=True
            )
            b2_linked_child, _ = await _make_part_with_revision(
                session, _pn("B2", "linked"), released=True
            )
            b2_unlinked_child, _ = await _make_part_with_revision(
                session, _pn("B2", "unlinked"), released=True
            )
            part_ids.update({b2_fg_id, b2_linked_child, b2_unlinked_child})
            session.add(
                PlumBomItem(parent_revision_id=b2_fg_rev, child_part_id=b2_linked_child,
                            qty=Decimal("1"), sort_order=0)
            )
            session.add(
                PlumBomItem(parent_revision_id=b2_fg_rev, child_part_id=b2_unlinked_child,
                            qty=Decimal("1"), sort_order=1)
            )
            await session.commit()
        b2_fg_item = await _link_item(session_factory, unique, "B2-FG", b2_fg_id)
        b2_child_item = await _link_item(session_factory, unique, "B2-LINK", b2_linked_child)
        item_ids.update({b2_fg_item, b2_child_item})
        # b2_unlinked_child intentionally has NO linked InventoryItem.
        async with session_factory() as session:
            wo_b2 = await create_work_order(
                session,
                WorkOrderCreate(
                    plum_part_id=b2_fg_id, planned_qty=Decimal("1"), target_location_id=main_id
                ),
                actor_id,
            )
        wo_ids.add(wo_b2.id)
        try:
            async with session_factory() as session:
                await release_work_order(session, wo_b2.id, actor_id)
            check("(B2) release with an unlinked BOM child is rejected", False,
                  "release succeeded")
        except HTTPException as exc:
            check(
                "(B2/D-P10-7) release with an unlinked BOM child is rejected 4xx",
                400 <= exc.status_code < 500,
                f"status={exc.status_code}",
            )
        async with session_factory() as session:
            b2_comps = (
                await session.execute(
                    select(func.count()).select_from(WorkOrderComponent).where(
                        WorkOrderComponent.work_order_id == wo_b2.id
                    )
                )
            ).scalar()
            b2_status = (
                await session.execute(select(WorkOrder.status).where(WorkOrder.id == wo_b2.id))
            ).scalar()
        check(
            "(B2/D-P10-7) NO partial snapshot — the whole release rejected with zero "
            "component rows and the WO still Draft",
            b2_comps == 0 and b2_status == "draft",
            f"components={b2_comps!r} status={b2_status!r}",
        )

        # ===================================================================
        # (C) ISSUE FLOOR + ILLEGAL FSM (SC2 / SC1)
        # ===================================================================
        async with session_factory() as session:
            c_fg_id, c_fg_rev = await _make_part_with_revision(
                session, _pn("C", "fg"), released=True
            )
            c_child_id, _ = await _make_part_with_revision(session, _pn("C", "child"), released=True)
            part_ids.update({c_fg_id, c_child_id})
            session.add(
                PlumBomItem(parent_revision_id=c_fg_rev, child_part_id=c_child_id,
                            qty=Decimal("1"), sort_order=0)
            )
            await session.commit()
        c_fg_item = await _link_item(session_factory, unique, "C-FG", c_fg_id)
        c_child_item = await _link_item(session_factory, unique, "C-CH", c_child_id)
        item_ids.update({c_fg_item, c_child_item})
        async with session_factory() as session:
            await post_receipt(session, c_child_item, main_id, Decimal("5"), Decimal("2"), actor_id)
        async with session_factory() as session:
            wo_c = await create_work_order(
                session,
                WorkOrderCreate(
                    plum_part_id=c_fg_id, planned_qty=Decimal("10"), target_location_id=main_id
                ),
                actor_id,
            )
        wo_ids.add(wo_c.id)

        # Illegal FSM: complete/hold a Released (not In Progress) WO -> 4xx.
        try:
            async with session_factory() as session:
                await complete_work_order(session, wo_c.id, actor_id)
            check("(C) completing a Released (not In Progress) WO is rejected", False,
                  "completion succeeded")
        except HTTPException as exc:
            check(
                "(C/SC1) completing a Released (not In Progress) WO is rejected 4xx",
                400 <= exc.status_code < 500,
                f"status={exc.status_code}",
            )
        try:
            async with session_factory() as session:
                await hold_work_order(session, wo_c.id, actor_id)
            check("(C) holding a Released (not In Progress) WO is rejected", False,
                  "hold succeeded")
        except HTTPException as exc:
            check(
                "(C/SC1) holding a Released (not In Progress) WO is rejected 4xx",
                400 <= exc.status_code < 500,
                f"status={exc.status_code}",
            )
        try:
            async with session_factory() as session:
                await resume_work_order(session, wo_c.id, actor_id)
            check("(C) resuming a WO that is not On Hold is rejected", False,
                  "resume succeeded")
        except HTTPException as exc:
            check(
                "(C/SC1) resuming a WO that is not On Hold is rejected 4xx",
                400 <= exc.status_code < 500,
                f"status={exc.status_code}",
            )

        # Now release wo_c and try to issue beyond on-hand (qty_required 10, on-hand 5).
        async with session_factory() as session:
            await release_work_order(session, wo_c.id, actor_id)
        async with session_factory() as session:
            c_detail = await get_work_order_detail(session, wo_c.id)
        c_comp_id = c_detail.components[0].id
        async with session_factory() as session:
            onhand_before = await _onhand(session, c_child_item, main_id)
        try:
            async with session_factory() as session:
                await issue_components(
                    session,
                    wo_c.id,
                    IssueComponentsRequest(
                        lines=[IssueComponentLine(component_id=c_comp_id, quantity=Decimal("10"))]
                    ),
                    actor_id,
                )
            check("(C) issuing 10 against on-hand 5 is rejected", False, "issue succeeded")
        except HTTPException as exc:
            check(
                "(C/SC2) issuing beyond on-hand (10 vs 5) is rejected 4xx",
                400 <= exc.status_code < 500,
                f"status={exc.status_code}",
            )
        async with session_factory() as session:
            onhand_after = await _onhand(session, c_child_item, main_id)
            c_issue_rows = (
                await session.execute(
                    select(func.count()).select_from(WorkOrderIssue).where(
                        WorkOrderIssue.work_order_id == wo_c.id
                    )
                )
            ).scalar()
        check(
            "(C/SC2) the rejected over-issue persisted NOTHING — on-hand unchanged (5) "
            "and zero WorkOrderIssue rows",
            onhand_after == onhand_before == Decimal("5") and c_issue_rows == 0,
            f"before={onhand_before!r} after={onhand_after!r} rows={c_issue_rows!r}",
        )

        # ===================================================================
        # (D) UNDER-ISSUE COMPLETION (D-P10-9) — override still clears WIP exactly
        # ===================================================================
        # A genuinely under-issued WO: two components, only ONE issued (the other is
        # never issued, so issued_so_far < qty_required for it). planned_qty 3; the
        # sole issue is 10 units off a 100-on-hand stock @ moving_avg 10 ->
        # accumulated_wip 100, which does NOT divide evenly by 3 (100/3 ==
        # 33.333333) — so completion must credit the EXACT 100 back to 1140 and
        # absorb the per-unit residual into the FG moving-average receipt (SC3 Risk).
        async with session_factory() as session:
            d2_fg_id, d2_fg_rev = await _make_part_with_revision(
                session, _pn("D2", "fg"), released=True
            )
            d2_ca, _ = await _make_part_with_revision(session, _pn("D2", "ca"), released=True)
            d2_cb, _ = await _make_part_with_revision(session, _pn("D2", "cb"), released=True)
            part_ids.update({d2_fg_id, d2_ca, d2_cb})
            session.add(
                PlumBomItem(parent_revision_id=d2_fg_rev, child_part_id=d2_ca,
                            qty=Decimal("1"), sort_order=0)
            )
            session.add(
                PlumBomItem(parent_revision_id=d2_fg_rev, child_part_id=d2_cb,
                            qty=Decimal("1"), sort_order=1)
            )
            await session.commit()
        d2_fg_item = await _link_item(session_factory, unique, "D2-FG", d2_fg_id)
        d2_ca_item = await _link_item(session_factory, unique, "D2-CA", d2_ca)
        d2_cb_item = await _link_item(session_factory, unique, "D2-CB", d2_cb)
        item_ids.update({d2_fg_item, d2_ca_item, d2_cb_item})
        async with session_factory() as session:
            await post_receipt(session, d2_ca_item, main_id, Decimal("100"), Decimal("10"), actor_id)
        async with session_factory() as session:
            await post_receipt(session, d2_cb_item, main_id, Decimal("100"), Decimal("7"), actor_id)
        async with session_factory() as session:
            wo_d2 = await create_work_order(
                session,
                WorkOrderCreate(
                    plum_part_id=d2_fg_id, planned_qty=Decimal("3"), target_location_id=main_id
                ),
                actor_id,
            )
        wo_ids.add(wo_d2.id)
        async with session_factory() as session:
            await release_work_order(session, wo_d2.id, actor_id)
        async with session_factory() as session:
            d2_detail = await get_work_order_detail(session, wo_d2.id)
        d2_comps = {c.child_part_id: c for c in d2_detail.components}
        d2_ca_comp = d2_comps[d2_ca].id  # qty_required 3
        # Snapshot the WO's pre-issue 1140 balance (0), then partially issue ONE
        # component only (10 units of A) -> accumulated_wip 100, component B never
        # issued so the WO is genuinely under-issued.
        async with session_factory() as session:
            wip_d2_pre = await _wo_account_balance(session, acct_1140, wo_d2.id)
        async with session_factory() as session:
            await issue_components(
                session,
                wo_d2.id,
                IssueComponentsRequest(
                    lines=[IssueComponentLine(component_id=d2_ca_comp, quantity=Decimal("10"))]
                ),
                actor_id,
            )
        # complete WITHOUT override -> 4xx, WO stays In Progress.
        try:
            async with session_factory() as session:
                await complete_work_order(session, wo_d2.id, actor_id)
            check("(D/D-P10-9) completing an under-issued WO without override is rejected",
                  False, "completion succeeded without override")
        except HTTPException as exc:
            check(
                "(D/D-P10-9) completing an under-issued WO WITHOUT override is rejected 4xx",
                400 <= exc.status_code < 500,
                f"status={exc.status_code}",
            )
        async with session_factory() as session:
            d2_status_mid = (
                await session.execute(select(WorkOrder.status).where(WorkOrder.id == wo_d2.id))
            ).scalar()
        check(
            "(D/D-P10-9) the rejected completion left the WO In Progress",
            d2_status_mid == "in_progress",
            f"status={d2_status_mid!r}",
        )
        # complete WITH override -> completes AND 1140 clears to the pre-issue snapshot.
        async with session_factory() as session:
            d2_complete = await complete_work_order(
                session, wo_d2.id, actor_id, override_incomplete=True
            )
        async with session_factory() as session:
            wip_d2_post = await _wo_account_balance(session, acct_1140, wo_d2.id)
            d2_status_final = (
                await session.execute(select(WorkOrder.status).where(WorkOrder.id == wo_d2.id))
            ).scalar()
        check(
            "(D/D-P10-9) override_incomplete=True COMPLETES the under-issued WO",
            d2_status_final == "completed" and d2_complete.wip_cleared_value == Decimal("100"),
            f"status={d2_status_final!r} cleared={d2_complete.wip_cleared_value!r}",
        )
        check(
            "(D/D-P10-9 CRUX) the override path clears 1140 to the pre-issue snapshot "
            "Decimal-EXACTLY even though 100/3 leaves a per-unit residual",
            wip_d2_post == wip_d2_pre and wip_d2_post == Decimal("0"),
            f"pre={wip_d2_pre!r} post={wip_d2_post!r}",
        )
        # D-P10-2 (amended): the MIRROR invariant — 1130 must tie to the inventory
        # subledger. The completion debits 1130 by EXACTLY the FG receipt value
        # (planned_qty × fg_unit_cost) and parks the sub-quantum residual in 5190,
        # so the control account never silently drifts from the subledger.
        async with session_factory() as session:
            fg_txn = (
                await session.execute(
                    select(InventoryTxn.quantity, InventoryTxn.unit_cost).where(
                        InventoryTxn.item_id == d2_fg_item,
                        InventoryTxn.source_id == wo_d2.id,
                        InventoryTxn.txn_type == "receipt",
                    )
                )
            ).first()
            fg_receipt_value = (fg_txn.quantity * fg_txn.unit_cost).quantize(Decimal("0.000001"))
            comp_1130_debit = Decimal(
                (
                    await session.execute(
                        select(func.coalesce(func.sum(JournalLine.debit), 0))
                        .select_from(JournalLine)
                        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
                        .where(
                            JournalLine.account_id == acct_1130,
                            JournalEntry.source_type == "mousse_work_order",
                            JournalEntry.source_id == wo_d2.id,
                        )
                    )
                ).scalar()
                or 0
            )
            wo_5190 = await _wo_account_balance(session, acct_5190, wo_d2.id)
        check(
            "(D/D-P10-2 amended) completion debits 1130 by EXACTLY the FG receipt value "
            "(3 × 33.333333 == 99.999999) — 1130 control ties to the inventory subledger",
            comp_1130_debit == fg_receipt_value and fg_receipt_value == Decimal("99.999999"),
            f"1130_debit={comp_1130_debit!r} fg_receipt_value={fg_receipt_value!r}",
        )
        check(
            "(D/D-P10-2 amended) the sub-quantum residual is parked in 5190 Inventory "
            "Rounding (receipt_value + 5190 == accumulated_wip 100), never stranded/drifting",
            wo_5190 == Decimal("100") - fg_receipt_value
            and (fg_receipt_value + wo_5190) == Decimal("100")
            and abs(wo_5190) < Decimal("3") * Decimal("0.000001"),
            f"5190={wo_5190!r} receipt+5190={fg_receipt_value + wo_5190!r}",
        )

        # ===================================================================
        # (E) TRIAL BALANCE NETS ZERO after all WO activity (SC4)
        # ===================================================================
        async with session_factory() as session:
            tb = await trial_balance(session)
        check(
            "(E/SC4) after all WO activity the trial balance still nets zero "
            "(total_debit == total_credit, in_balance True)",
            tb.total_debit == tb.total_credit and tb.in_balance is True,
            f"debit={tb.total_debit!r} credit={tb.total_credit!r} in_balance={tb.in_balance!r}",
        )

        # ===================================================================
        # (F) CONCURRENCY (SC5) — two concurrent issues, exactly one wins (task 13)
        # ===================================================================
        await run_concurrency(session_factory, unique, actor_id, main_id, acct_1140,
                              part_ids, item_ids, wo_ids)

        # ===================================================================
        # (G) BINNED ISSUE (Phase 4 / D-P4-1) + LEGACY-DESYNC LOCATION FLOOR
        # ===================================================================
        # Phase 4 made issue_components bin-aware under the explicit-or-unbinned
        # contract (D-P4-1): bin_id=None draws ONLY the location's UNBINNED pool
        # (and floor-guards it); a named bin draws that single bin's pool. The
        # LOCATION floor is kept ALONGSIDE the pool floor (mirrors
        # post_adjustment / post_transfer): the pool floors imply the location
        # floor only on clean post-Phase-4 data — the location floor defends
        # legacy rows whose per-bin split has already desynced from the
        # location total. Pins the behaviors the Phase-4 verification could
        # only hand-check.
        #
        # (G1) fixture: FG + one child (qty_per 1), child stocked 10 @ 4 and
        # putaway ENTIRELY into bin G1 — the draw location is fully binned.
        async with session_factory() as session:
            g1_fg_id, g1_fg_rev = await _make_part_with_revision(
                session, _pn("G1", "fg"), released=True
            )
            g1_child_id, _ = await _make_part_with_revision(
                session, _pn("G1", "child"), released=True
            )
            part_ids.update({g1_fg_id, g1_child_id})
            session.add(
                PlumBomItem(parent_revision_id=g1_fg_rev, child_part_id=g1_child_id,
                            qty=Decimal("1"), sort_order=0)
            )
            await session.commit()
        g1_fg_item = await _link_item(session_factory, unique, "G1-FG", g1_fg_id)
        g1_child_item = await _link_item(session_factory, unique, "G1-CH", g1_child_id)
        item_ids.update({g1_fg_item, g1_child_item})
        async with session_factory() as session:
            await post_receipt(
                session, g1_child_item, main_id, Decimal("10"), Decimal("4"), actor_id
            )
        async with session_factory() as session:
            bin_g1 = (
                await create_bin(session, BinCreate(location_id=main_id, code=f"G1-{unique}"))
            ).id
        bin_ids.add(bin_g1)
        async with session_factory() as session:
            await execute_putaway(
                session,
                PutawayRequest(
                    item_id=g1_child_item, location_id=main_id, to_bin_id=bin_g1,
                    qty=Decimal("10"), from_bin_id=None,
                ),
                actor_id,
            )
        async with session_factory() as session:
            wo_g1 = await create_work_order(
                session,
                WorkOrderCreate(
                    plum_part_id=g1_fg_id, planned_qty=Decimal("10"),
                    target_location_id=main_id,
                ),
                actor_id,
            )
        wo_ids.add(wo_g1.id)
        async with session_factory() as session:
            await release_work_order(session, wo_g1.id, actor_id)
        async with session_factory() as session:
            g1_detail = await get_work_order_detail(session, wo_g1.id)
        g1_comp_id = g1_detail.components[0].id

        # (G1a) bin_id=None at the fully-binned location draws ONLY the empty
        # unbinned pool -> 422 with ZERO ledger/issue rows. Row-count oracle:
        # receipt + two putaway legs == 3 rows before and after.
        async with session_factory() as session:
            g1_rows_before = await _txn_rows(session, g1_child_item)
        try:
            async with session_factory() as session:
                await issue_components(
                    session,
                    wo_g1.id,
                    IssueComponentsRequest(
                        lines=[IssueComponentLine(
                            component_id=g1_comp_id, quantity=Decimal("10"), bin_id=None,
                        )]
                    ),
                    actor_id,
                )
            check("(G1/D-P4-1) issuing with bin_id=None at a fully-binned location "
                  "is rejected", False, "issue succeeded over the unbinned-pool floor")
        except HTTPException as exc:
            check(
                "(G1/D-P4-1) issuing 10 with bin_id=None at a fully-binned location "
                "draws ONLY the empty unbinned pool and is rejected 422",
                exc.status_code == 422,
                f"status={exc.status_code}",
            )
        async with session_factory() as session:
            g1_rows_after = await _txn_rows(session, g1_child_item)
            g1_issue_rows = (
                await session.execute(
                    select(func.count()).select_from(WorkOrderIssue).where(
                        WorkOrderIssue.work_order_id == wo_g1.id
                    )
                )
            ).scalar()
        check(
            "(G1/D-P4-1) the rejected bin-blind issue wrote NO ledger rows and NO "
            "issue rows (receipt + two putaway legs == 3 before and after)",
            g1_rows_after == g1_rows_before == 3 and g1_issue_rows == 0,
            f"before={g1_rows_before!r} after={g1_rows_after!r} issues={g1_issue_rows!r}",
        )

        # (G1b) naming the bin succeeds: the issue txn carries the bin_id, the
        # bin pool draws to the exact remainder (10-6==4), and the WIP/JE
        # amount is IDENTICAL to the unbinned equivalent (6 × moving_avg 4 ==
        # 24.000000) — bins are a quantity dimension, never a valuation one.
        async with session_factory() as session:
            g1_result = await issue_components(
                session,
                wo_g1.id,
                IssueComponentsRequest(
                    lines=[IssueComponentLine(
                        component_id=g1_comp_id, quantity=Decimal("6"), bin_id=bin_g1,
                    )]
                ),
                actor_id,
            )
        async with session_factory() as session:
            g1_issue_txns = (
                await session.execute(
                    select(InventoryTxn.bin_id, InventoryTxn.quantity).where(
                        InventoryTxn.item_id == g1_child_item,
                        InventoryTxn.txn_type == "issue",
                        InventoryTxn.source_id == wo_g1.id,
                    )
                )
            ).all()
            g1_pool = await get_bin_on_hand(session, g1_child_item, main_id, bin_g1)
            g1_unbinned = await get_bin_on_hand(session, g1_child_item, main_id, None)
            g1_wip = await _wo_account_balance(session, acct_1140, wo_g1.id)
        check(
            "(G1/D-P4-1) the bin-named issue succeeds and its issue txn row CARRIES "
            "the bin_id (one -6 row on bin G1)",
            g1_result.lines_issued == 1 and len(g1_issue_txns) == 1
            and g1_issue_txns[0].bin_id == bin_g1
            and g1_issue_txns[0].quantity == Decimal("-6"),
            f"lines={g1_result.lines_issued!r} txns={g1_issue_txns!r}",
        )
        check(
            "(G1/D-P4-1) the bin pool draws to the exact remainder (10-6==4), the "
            "unbinned pool stays 0, and the WIP/JE amount equals the unbinned "
            "equivalent (6 × 4 == 24.000000)",
            g1_pool == Decimal("4") and g1_unbinned == Decimal("0")
            and g1_wip == Decimal("24.000000")
            and g1_result.total_issued_value == Decimal("24.000000"),
            f"pool={g1_pool!r} unbinned={g1_unbinned!r} wip={g1_wip!r} "
            f"value={g1_result.total_issued_value!r}",
        )

        # (G2) LEGACY-DESYNC LOCATION FLOOR — pins the Phase-4 review fix
        # (finding 1). Fixture: stock 10 @ 5, putaway ALL into bin G2, then
        # RAW-INSERT the pre-Phase-4 history the review's concrete scenario
        # describes: a legacy bin-blind issue (-10, bin_id NULL). The ledger
        # now reads bin pool 10, unbinned pool -10, location total 0 — the
        # bin split is desynced from the location total.
        async with session_factory() as session:
            g2_fg_id, g2_fg_rev = await _make_part_with_revision(
                session, _pn("G2", "fg"), released=True
            )
            g2_child_id, _ = await _make_part_with_revision(
                session, _pn("G2", "child"), released=True
            )
            part_ids.update({g2_fg_id, g2_child_id})
            session.add(
                PlumBomItem(parent_revision_id=g2_fg_rev, child_part_id=g2_child_id,
                            qty=Decimal("1"), sort_order=0)
            )
            await session.commit()
        g2_fg_item = await _link_item(session_factory, unique, "G2-FG", g2_fg_id)
        g2_child_item = await _link_item(session_factory, unique, "G2-CH", g2_child_id)
        item_ids.update({g2_fg_item, g2_child_item})
        async with session_factory() as session:
            await post_receipt(
                session, g2_child_item, main_id, Decimal("10"), Decimal("5"), actor_id
            )
        async with session_factory() as session:
            bin_g2 = (
                await create_bin(session, BinCreate(location_id=main_id, code=f"G2-{unique}"))
            ).id
        bin_ids.add(bin_g2)
        async with session_factory() as session:
            await execute_putaway(
                session,
                PutawayRequest(
                    item_id=g2_child_item, location_id=main_id, to_bin_id=bin_g2,
                    qty=Decimal("10"), from_bin_id=None,
                ),
                actor_id,
            )
        async with session_factory() as session:
            session.add(
                InventoryTxn(
                    item_id=g2_child_item,
                    location_id=main_id,
                    txn_type="issue",
                    quantity=Decimal("-10"),
                    unit_cost=Decimal("5"),
                    actor_id=actor_id,
                    bin_id=None,
                )
            )
            await session.commit()
        async with session_factory() as session:
            g2_pool = await get_bin_on_hand(session, g2_child_item, main_id, bin_g2)
            g2_unbinned = await get_bin_on_hand(session, g2_child_item, main_id, None)
            g2_loc = await _onhand(session, g2_child_item, main_id)
        check(
            "(G2) fixture: the legacy desync is in place — bin pool 10, unbinned "
            "pool -10, location total 0",
            g2_pool == Decimal("10") and g2_unbinned == Decimal("-10")
            and g2_loc == Decimal("0"),
            f"pool={g2_pool!r} unbinned={g2_unbinned!r} loc={g2_loc!r}",
        )
        async with session_factory() as session:
            wo_g2 = await create_work_order(
                session,
                WorkOrderCreate(
                    plum_part_id=g2_fg_id, planned_qty=Decimal("10"),
                    target_location_id=main_id,
                ),
                actor_id,
            )
        wo_ids.add(wo_g2.id)
        async with session_factory() as session:
            await release_work_order(session, wo_g2.id, actor_id)
        async with session_factory() as session:
            g2_detail = await get_work_order_detail(session, wo_g2.id)
        g2_comp_id = g2_detail.components[0].id

        # The bin-named issue of 10 PASSES the pool guard (bin pool 10-10==0)
        # but MUST be rejected 422 by the LOCATION floor (location total 0-10
        # < 0) with ZERO rows written. Without the location floor this issue
        # would succeed and drive the location — and total item — on-hand to
        # -10 while booking Dr 1140 / Cr 1130 value out of stock that does
        # not exist.
        async with session_factory() as session:
            g2_rows_before = await _txn_rows(session, g2_child_item)
        try:
            async with session_factory() as session:
                await issue_components(
                    session,
                    wo_g2.id,
                    IssueComponentsRequest(
                        lines=[IssueComponentLine(
                            component_id=g2_comp_id, quantity=Decimal("10"), bin_id=bin_g2,
                        )]
                    ),
                    actor_id,
                )
            check(
                "(G2/CRUX) a bin-named issue of 10 against the desynced location "
                "(total 0) is rejected by the LOCATION floor",
                False,
                "issue succeeded — the per-location floor beside the pool floor is gone",
            )
        except HTTPException as exc:
            check(
                "(G2/CRUX) a bin-named issue of 10 against the desynced location "
                "(bin pool 10, location total 0) passes the pool guard but is "
                "rejected 422 by the LOCATION floor",
                exc.status_code == 422,
                f"status={exc.status_code}",
            )
        async with session_factory() as session:
            g2_rows_after = await _txn_rows(session, g2_child_item)
            g2_issue_rows = (
                await session.execute(
                    select(func.count()).select_from(WorkOrderIssue).where(
                        WorkOrderIssue.work_order_id == wo_g2.id
                    )
                )
            ).scalar()
            g2_loc_after = await _onhand(session, g2_child_item, main_id)
        check(
            "(G2/CRUX) the rejected issue wrote NOTHING — ledger row count unchanged "
            "(receipt + two putaway legs + raw legacy issue == 4), zero issue rows, "
            "location total still 0 (never negative)",
            g2_rows_after == g2_rows_before == 4 and g2_issue_rows == 0
            and g2_loc_after == Decimal("0"),
            f"before={g2_rows_before!r} after={g2_rows_after!r} "
            f"issues={g2_issue_rows!r} loc={g2_loc_after!r}",
        )

    finally:
        await _cleanup(session_factory, part_ids, item_ids, wo_ids, bin_ids)
        await engine.dispose()


# ---------------------------------------------------------------------------
# (F) Concurrency scenario (SC5) — task 13
# ---------------------------------------------------------------------------
#
# THE LOCK IS WHAT MAKES THIS HOLD. issue_components locks the contended
# InventoryItem row `SELECT ... FOR UPDATE` BEFORE reading on-hand, so two
# concurrent issues against the same item serialize: the loser blocks until the
# winner commits, then re-reads the now-depleted on-hand and the per-location
# floor guard rejects it 4xx. Removing that FOR UPDATE from
# app.modules.mousse.service.issue_components makes BOTH read the original
# on-hand under READ COMMITTED and both succeed — driving on-hand negative and
# double-consuming (WIP == 2× one issue) — i.e. this scenario FAILS. A sequential
# test cannot surface that race; only firing both with asyncio.gather on TWO
# INDEPENDENT sessions can.


async def run_concurrency(
    session_factory,
    unique: str,
    actor_id: str,
    main_id: int,
    acct_1140: int,
    part_ids: set[str],
    item_ids: set[str],
    wo_ids: set[str],
) -> None:
    """
    Fire two identical issue requests concurrently against a WO whose single
    component has on-hand enough for EXACTLY ONE, and prove exactly one wins.
    """
    # Fixture: FG + one child, on-hand EXACTLY 5 (both requests ask for 5).
    async with session_factory() as session:
        f_fg_id, f_fg_rev = await _make_part_with_revision(
            session, f"P-MO-{unique}-F-fg", released=True
        )
        f_child_id, _ = await _make_part_with_revision(
            session, f"P-MO-{unique}-F-child", released=True
        )
        part_ids.update({f_fg_id, f_child_id})
        session.add(
            PlumBomItem(parent_revision_id=f_fg_rev, child_part_id=f_child_id,
                        qty=Decimal("5"), sort_order=0)
        )
        await session.commit()
    f_fg_item = await _link_item(session_factory, unique, "F-FG", f_fg_id)
    f_child_item = await _link_item(session_factory, unique, "F-CH", f_child_id)
    item_ids.update({f_fg_item, f_child_item})
    async with session_factory() as session:
        await post_receipt(session, f_child_item, main_id, Decimal("5"), Decimal("4"), actor_id)
    async with session_factory() as session:
        wo_f = await create_work_order(
            session,
            WorkOrderCreate(
                plum_part_id=f_fg_id, planned_qty=Decimal("1"), target_location_id=main_id
            ),
            actor_id,
        )
    wo_ids.add(wo_f.id)
    async with session_factory() as session:
        await release_work_order(session, wo_f.id, actor_id)
    async with session_factory() as session:
        f_detail = await get_work_order_detail(session, wo_f.id)
    f_comp_id = f_detail.components[0].id  # qty_required == 5, on-hand == 5

    # A start barrier makes the race DETERMINISTIC rather than timing-dependent: each
    # worker owns an INDEPENDENT session, pre-warms its connection with a throwaway
    # query (so connection-setup asymmetry can't let one worker finish before the
    # other even starts), then both wait on the barrier and enter issue_components
    # together. Aligned like this the two issues interleave await-by-await through the
    # read-check-write window — so WITHOUT the FOR UPDATE lock both would read the same
    # pre-issue on-hand and double-consume; WITH the lock the loser blocks on the item
    # row until the winner commits, re-reads the depleted on-hand, and is floor-rejected.
    barrier = asyncio.Barrier(2)

    async def _issue_once():
        from sqlalchemy import text

        async with session_factory() as session:
            await session.execute(text("SELECT 1"))  # pre-warm the connection
            await barrier.wait()
            return await issue_components(
                session,
                wo_f.id,
                IssueComponentsRequest(
                    lines=[IssueComponentLine(component_id=f_comp_id, quantity=Decimal("5"))]
                ),
                actor_id,
            )

    results = await asyncio.gather(_issue_once(), _issue_once(), return_exceptions=True)
    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]
    http_failures = [r for r in failures if isinstance(r, HTTPException)]
    check(
        "(F/SC5) two concurrent issues (on-hand for exactly one): EXACTLY ONE "
        "succeeds and one fails",
        len(successes) == 1 and len(failures) == 1,
        f"successes={len(successes)} failures={[type(f).__name__ for f in failures]}",
    )
    check(
        "(F/SC5) the loser fails with a 4xx (floor guard / lock serialization), not "
        "an unexpected error",
        len(http_failures) == 1 and 400 <= http_failures[0].status_code < 500,
        f"failure={failures[0]!r}",
    )

    async with session_factory() as session:
        final_onhand = await _onhand(session, f_child_item, main_id)
        issue_rows = (
            await session.execute(
                select(func.count()).select_from(WorkOrderIssue).where(
                    WorkOrderIssue.work_order_id == wo_f.id
                )
            )
        ).scalar()
        wo_f_wip = await _wo_account_balance(session, acct_1140, wo_f.id)
    check(
        "(F/SC5) on-hand never went negative and there was no double-consume "
        "(final on-hand == 0, exactly one WorkOrderIssue row)",
        final_onhand == Decimal("0") and issue_rows == 1,
        f"onhand={final_onhand!r} issue_rows={issue_rows!r}",
    )
    check(
        "(F/SC5) the WO's WIP reflects only the ONE successful issue "
        "(1140 == 5 * 4 == 20.000000, not 40)",
        wo_f_wip == Decimal("20.000000"),
        f"wip={wo_f_wip!r}",
    )


# ---------------------------------------------------------------------------
# Cleanup — delete only the throwaway rows, in FK-safe order
# ---------------------------------------------------------------------------


async def _cleanup(
    session_factory,
    part_ids: set[str],
    item_ids: set[str],
    wo_ids: set[str],
    bin_ids: set[int],
) -> None:
    """
    Delete the throwaway rows in FK-safe order: work-order issues -> the WOs'
    source-linked journal lines/entries -> components -> work orders -> inventory
    txns -> inventory items -> bins -> BOM items -> revisions -> parts. The seeded
    "Main" location and 1130/1140 GL accounts are reused and left in place (real
    deploy state).
    """
    async with session_factory() as session:
        wo_id_list = list(wo_ids)
        item_id_list = list(item_ids)
        part_id_list = list(part_ids)
        bin_id_list = list(bin_ids)

        if wo_id_list:
            await session.execute(
                delete(WorkOrderIssue).where(WorkOrderIssue.work_order_id.in_(wo_id_list))
            )
            entry_ids = (
                await session.execute(
                    select(JournalEntry.id).where(
                        JournalEntry.source_type == "mousse_work_order",
                        JournalEntry.source_id.in_(wo_id_list),
                    )
                )
            ).scalars().all()
            if entry_ids:
                await session.execute(
                    delete(JournalLine).where(JournalLine.entry_id.in_(entry_ids))
                )
                await session.execute(
                    delete(JournalEntry).where(JournalEntry.id.in_(entry_ids))
                )
            await session.execute(
                delete(WorkOrderComponent).where(
                    WorkOrderComponent.work_order_id.in_(wo_id_list)
                )
            )
            await session.execute(delete(WorkOrder).where(WorkOrder.id.in_(wo_id_list)))

        if item_id_list:
            await session.execute(
                delete(InventoryTxn).where(InventoryTxn.item_id.in_(item_id_list))
            )
            await session.execute(
                delete(InventoryItem).where(InventoryItem.id.in_(item_id_list))
            )

        # Bins after the txns that FK into them (scenario G's bins).
        if bin_id_list:
            await session.execute(delete(Bin).where(Bin.id.in_(bin_id_list)))

        if part_id_list:
            await session.execute(
                delete(PlumBomItem).where(PlumBomItem.child_part_id.in_(part_id_list))
            )
            await session.execute(
                delete(PlumPartRevision).where(PlumPartRevision.part_id.in_(part_id_list))
            )
            await session.execute(delete(PlumPart).where(PlumPart.id.in_(part_id_list)))

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
