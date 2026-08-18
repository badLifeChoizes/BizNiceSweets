# ABOUTME: SERVICE-path port of verify_mousse.py scenarios (A)+(D) (SC1e) — the MOUSSE WIP-clears crux.
# ABOUTME: Drives the real mousse service (create/release/issue/complete) + the 1140-clears-exact and 1130↔subledger+5190 invariants on the test DB.
"""
MOUSSE WIP-clears SERVICE crux — ported from ``backend/scripts/verify_mousse.py``
scenario (A) happy-path issue→complete WIP-clears and scenario (D) under-issue
override with the 5190 rounding residual (SC1e).

WHY THIS EXISTS:
  A work order consumes a PLUM single-level BOM and SYERP inventory to produce a
  finished good, booking actual moving-average material cost through the 1140
  Work-in-Process clearing account. ISSUE posts ONE balanced JE Dr 1140 / Cr 1130
  for Σ(qty × moving_avg); COMPLETE receives the FG at accumulated-WIP unit cost
  and posts the mirror JE that credits 1140 for EXACTLY the accumulated WIP so the
  WO's 1140-attributable balance returns to its pre-issue value. The load-bearing
  invariant (THE CRUX) is that a WO's 1140-attributable balance clears back to its
  pre-issue snapshot **Decimal-exactly** — even when accumulated_wip / planned_qty
  does not divide evenly, the completion JE debits 1130 by EXACTLY the FG receipt
  value and parks the sub-quantum residual in 5190 so neither 1140 strands WIP nor
  1130 silently drifts from the inventory subledger. That end-to-end path only ever
  ran against the live ``biznice`` DB via the standalone verify script; this test
  closes that gap through the same service functions on the truncate-fresh test DB.

SC2 red-on-revert: crediting 1140 by ``planned_qty × fg_unit_cost`` (the rounded FG
receipt value) instead of the EXACT accumulated WIP in mousse completion strands a
sub-quantum residual on 1140 — it turns the scenario (D) test
``test_under_issue_override_clears_wip_and_ties_subledger`` RED (its 100/3 case makes
the two credit sources diverge). The scenario (A) happy path below divides evenly
(210/10 == 21.000000), so the two credit sources coincide and it does NOT independently
catch that mutation — (D) is this crux's regression guard.

Concurrency mutation-proof (verify_mousse scenario F) stays in the script per
D-P2a-2; only the sequential cruxes are ported here (D-P2b-2).

All amounts are Decimal — never float (D-11).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.modules.mousse.models import WorkOrder, WorkOrderIssue
from app.modules.mousse.schemas import (
    IssueComponentLine,
    IssueComponentsRequest,
    WorkOrderCreate,
)
from app.modules.mousse.service import (
    complete_work_order,
    create_work_order,
    get_work_order_detail,
    issue_components,
    release_work_order,
)
from app.modules.plum.models import PlumBomItem, PlumPart, PlumPartRevision
from app.modules.syerp.inventory_seed import DEFAULT_LOCATION_NAME
from app.modules.syerp.models import (
    GLAccount,
    InventoryTxn,
    JournalEntry,
    JournalLine,
    StockLocation,
)
from app.modules.syerp.schemas import InventoryItemCreate
from app.modules.syerp.service import create_item, get_item, post_receipt

ACTOR_ID = "admin-user"  # a real seeded admin identity (see conftest _isolate)


# ---------------------------------------------------------------------------
# Shared derivations — lifted verbatim from verify_mousse.py so the crux is the
# assertion's OWN computation over the journal lines, not the service's helper.
# ---------------------------------------------------------------------------


async def _account_id_by_code(session, code: str) -> int | None:
    """Resolve a seeded GL account id by its Chart-of-Accounts `code`."""
    result = await session.execute(select(GLAccount.id).where(GLAccount.code == code))
    return result.scalars().first()


async def _onhand(session, item_id: str, location_id: int) -> Decimal:
    """Derive an item's on-hand at a location (signed SUM of its InventoryTxns)."""
    result = await session.execute(
        select(func.coalesce(func.sum(InventoryTxn.quantity), 0)).where(
            InventoryTxn.item_id == item_id,
            InventoryTxn.location_id == location_id,
        )
    )
    return Decimal(result.scalar() or 0)


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


async def _make_part_with_revision(
    session, part_number: str, *, released: bool, uom: str = "ea"
) -> tuple[str, str]:
    """
    Insert a PLUM part + its revision 1 directly via the ORM, returning
    (part_id, revision_id). `released=True` writes a Released revision (the WO
    release snapshots against it). Direct ORM inserts keep the fixture fully
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
        description=f"SC1e {part_number}",
        unit_of_measure=uom,
        released_at=datetime.now(UTC) if released else None,
    )
    session.add(rev)
    await session.flush()
    return part.id, rev.id


async def _link_item(session, tag: str, part_id: str | None) -> str:
    """Create a SYERP InventoryItem linked to a PLUM part and return its id."""
    item = await create_item(
        session,
        InventoryItemCreate(
            name=f"SC1e {tag} {uuid.uuid4().hex[:8]}",
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


async def test_wip_clears_to_zero_crux(seeded_ledger_db) -> None:
    """
    Port of verify_mousse.py (A): the happy-path WIP-clears-to-zero crux.

    A WO against a PLUM part with a Released revision whose direct BOM has two
    children (qty_per 2 & 3, linked to stocked SYERP items @ moving_avg 3 & 5):
      - release snapshots exactly the 2 BOM child lines with qty_required ==
        qty_per × planned_qty (2*10==20, 3*10==30);
      - the WO's 1140-attributable balance is snapshotted at 0 BEFORE any issue;
      - issuing all components posts ONE balanced JE — Dr 1140 210 / Cr 1130 −210
        (BOTH legs asserted) — for Σ(qty × moving_avg) == 20*3 + 30*5 == 210, and
        reports both lines issued;
      - completion receives planned_qty (10) of FG at 210/10 == 21.000000 and —
        THE CRUX (SC3) — the WO's 1140-attributable balance returns to its
        pre-issue snapshot Decimal-EXACTLY (== 0), WIP fully cleared.

    SC2 red-on-revert: crediting 1140 by planned_qty × fg_unit_cost instead of the
    EXACT accumulated WIP in mousse completion must turn this WIP-clears assertion
    RED (here it happens to divide evenly, but the (D) under-issue path forces the
    residual case that makes the two credit sources diverge).
    """
    session = seeded_ledger_db
    main_id = await _main_location_id(session)
    acct_1130 = await _account_id_by_code(session, "1130")  # Inventory (control)
    acct_1140 = await _account_id_by_code(session, "1140")  # WIP (the crux account)
    assert acct_1130 is not None and acct_1140 is not None

    planned_qty = Decimal("10")

    # FG part + Released revision, two BOM children A (qty_per 2) & B (qty_per 3).
    fg_part_id, fg_rev_id = await _make_part_with_revision(session, "A-fg", released=True)
    child_a_id, _ = await _make_part_with_revision(session, "A-ca", released=True)
    child_b_id, _ = await _make_part_with_revision(session, "A-cb", released=True)
    session.add(
        PlumBomItem(
            parent_revision_id=fg_rev_id, child_part_id=child_a_id, qty=Decimal("2"), sort_order=0
        )
    )
    session.add(
        PlumBomItem(
            parent_revision_id=fg_rev_id, child_part_id=child_b_id, qty=Decimal("3"), sort_order=1
        )
    )
    await session.flush()

    fg_item_id = await _link_item(session, "A-FG", fg_part_id)
    item_a_id = await _link_item(session, "A-CA", child_a_id)
    item_b_id = await _link_item(session, "A-CB", child_b_id)

    # Stock the components (also establishes their moving averages: A 3, B 5).
    await post_receipt(session, item_a_id, main_id, Decimal("100"), Decimal("3"), ACTOR_ID)
    await post_receipt(session, item_b_id, main_id, Decimal("100"), Decimal("5"), ACTOR_ID)

    # --- create ---
    wo = await create_work_order(
        session,
        WorkOrderCreate(
            plum_part_id=fg_part_id, planned_qty=planned_qty, target_location_id=main_id
        ),
        ACTOR_ID,
    )
    wo_id = wo.id
    assert wo.status == "draft" and wo.wo_number.startswith("WO-")

    # --- release: single-level BOM snapshot ---
    released = await release_work_order(session, wo_id, ACTOR_ID)
    detail = await get_work_order_detail(session, wo_id)
    comps = {c.child_part_id: c for c in detail.components}
    assert released.status == "released"
    assert len(detail.components) == 2
    assert released.output_item_id == fg_item_id
    assert released.released_revision_id == fg_rev_id
    # qty_required == qty_per × planned_qty for each snapshot line (2*10==20, 3*10==30).
    assert comps[child_a_id].qty_required == Decimal("20")
    assert comps[child_a_id].qty_per == Decimal("2")
    assert comps[child_b_id].qty_required == Decimal("30")
    assert comps[child_b_id].qty_per == Decimal("3")
    comp_a_id = comps[child_a_id].id
    comp_b_id = comps[child_b_id].id

    # --- snapshot the WO's 1140-attributable balance BEFORE any issue (== 0) ---
    wip_pre_issue = await _wo_account_balance(session, acct_1140, wo_id)
    assert wip_pre_issue == Decimal("0")

    # --- issue all components ---
    issue_result = await issue_components(
        session,
        wo_id,
        IssueComponentsRequest(
            lines=[
                IssueComponentLine(component_id=comp_a_id, quantity=Decimal("20")),
                IssueComponentLine(component_id=comp_b_id, quantity=Decimal("30")),
            ]
        ),
        ACTOR_ID,
    )
    expected_wip = Decimal("60") + Decimal("150")  # 20*3 + 30*5 == 210
    assert issue_result.total_issued_value == Decimal("210.000000")
    assert issue_result.lines_issued == 2

    onhand_a = await _onhand(session, item_a_id, main_id)
    onhand_b = await _onhand(session, item_b_id, main_id)
    wip_after_issue = await _wo_account_balance(session, acct_1140, wo_id)
    inv_after_issue = await _wo_account_balance(session, acct_1130, wo_id)
    issue_rows = (
        await session.execute(
            select(func.count()).select_from(WorkOrderIssue).where(
                WorkOrderIssue.work_order_id == wo_id
            )
        )
    ).scalar()
    wo_after_issue = (
        await session.execute(select(WorkOrder.status).where(WorkOrder.id == wo_id))
    ).scalar()
    # Issue decremented each component's on-hand (100-20==80, 100-30==70).
    assert onhand_a == Decimal("80") and onhand_b == Decimal("70")
    # ONE balanced JE Dr 1140 210 / Cr 1130 210 attributable to the WO — BOTH legs.
    assert wip_after_issue == expected_wip
    assert inv_after_issue == -expected_wip
    # One WorkOrderIssue row per component and the WO flips to In Progress.
    assert issue_rows == 2 and wo_after_issue == "in_progress"

    # --- complete: FG receipt + WIP clears to the pre-issue snapshot (CRUX) ---
    complete_result = await complete_work_order(session, wo_id, ACTOR_ID)
    fg_item = await get_item(session, fg_item_id)
    wip_post_complete = await _wo_account_balance(session, acct_1140, wo_id)
    wo_final = (
        await session.execute(select(WorkOrder).where(WorkOrder.id == wo_id))
    ).scalars().first()
    fg_unit_cost = (expected_wip / planned_qty).quantize(Decimal("0.000001"))
    # Completion received planned_qty (10) of FG at 210/10 == 21.000000.
    assert complete_result.quantity_received == planned_qty
    assert fg_item.moving_avg_cost == fg_unit_cost == Decimal("21.000000")
    # CRUX (SC3): the WO's 1140-attributable balance returns to its pre-issue
    # snapshot Decimal-EXACTLY after completion — WIP clears to zero.
    assert wip_post_complete == wip_pre_issue == Decimal("0")
    assert wo_final.status == "completed" and wo_final.completed_at is not None


async def test_under_issue_override_clears_wip_and_ties_subledger(seeded_ledger_db) -> None:
    """
    Port of verify_mousse.py (D): the under-issue override + 5190 residual crux.

    A genuinely under-issued WO (two components, only ONE issued): planned_qty 3,
    the sole issue is 10 units @ moving_avg 10 → accumulated_wip 100, which does
    NOT divide evenly by 3 (100/3 == 33.333333). Completing WITHOUT override is
    rejected (422) and the WO stays In Progress. WITH override_incomplete=True it
    completes AND:
      - the WO's 1140-attributable balance clears to its pre-issue snapshot
        Decimal-EXACTLY (== 0) even though the per-unit cost leaves a residual;
      - completion debits 1130 by EXACTLY the FG receipt value
        (3 × 33.333333 == 99.999999) — the 1130 control ties to the inventory
        subledger;
      - the sub-quantum residual is parked in 5190 Inventory Rounding so
        receipt_value + 5190 == accumulated_wip 100 Decimal-exact (asserted
        DIRECTLY, not merely "the trial balance nets to zero").
    """
    session = seeded_ledger_db
    main_id = await _main_location_id(session)
    acct_1130 = await _account_id_by_code(session, "1130")  # Inventory (control)
    acct_1140 = await _account_id_by_code(session, "1140")  # WIP (the crux account)
    acct_5190 = await _account_id_by_code(session, "5190")  # Inventory Rounding (residual)
    assert acct_1130 is not None and acct_1140 is not None and acct_5190 is not None

    # FG + two children A & B (qty_per 1 each), planned_qty 3.
    fg_id, fg_rev = await _make_part_with_revision(session, "D2-fg", released=True)
    ca_id, _ = await _make_part_with_revision(session, "D2-ca", released=True)
    cb_id, _ = await _make_part_with_revision(session, "D2-cb", released=True)
    session.add(
        PlumBomItem(parent_revision_id=fg_rev, child_part_id=ca_id, qty=Decimal("1"), sort_order=0)
    )
    session.add(
        PlumBomItem(parent_revision_id=fg_rev, child_part_id=cb_id, qty=Decimal("1"), sort_order=1)
    )
    await session.flush()

    fg_item = await _link_item(session, "D2-FG", fg_id)
    ca_item = await _link_item(session, "D2-CA", ca_id)
    cb_item = await _link_item(session, "D2-CB", cb_id)
    await post_receipt(session, ca_item, main_id, Decimal("100"), Decimal("10"), ACTOR_ID)
    await post_receipt(session, cb_item, main_id, Decimal("100"), Decimal("7"), ACTOR_ID)

    wo = await create_work_order(
        session,
        WorkOrderCreate(plum_part_id=fg_id, planned_qty=Decimal("3"), target_location_id=main_id),
        ACTOR_ID,
    )
    wo_id = wo.id
    await release_work_order(session, wo_id, ACTOR_ID)
    detail = await get_work_order_detail(session, wo_id)
    comps = {c.child_part_id: c for c in detail.components}
    ca_comp = comps[ca_id].id  # qty_required 3

    # Snapshot pre-issue 1140 (== 0), then issue ONLY component A (10 units) →
    # accumulated_wip 100; component B is never issued so the WO is under-issued.
    wip_pre = await _wo_account_balance(session, acct_1140, wo_id)
    assert wip_pre == Decimal("0")
    await issue_components(
        session,
        wo_id,
        IssueComponentsRequest(
            lines=[IssueComponentLine(component_id=ca_comp, quantity=Decimal("10"))]
        ),
        ACTOR_ID,
    )

    # complete WITHOUT override → 4xx, WO stays In Progress.
    with pytest.raises(HTTPException) as under_exc:
        await complete_work_order(session, wo_id, ACTOR_ID)
    assert 400 <= under_exc.value.status_code < 500
    status_mid = (
        await session.execute(select(WorkOrder.status).where(WorkOrder.id == wo_id))
    ).scalar()
    assert status_mid == "in_progress"

    # complete WITH override → completes AND 1140 clears to the pre-issue snapshot.
    d_complete = await complete_work_order(session, wo_id, ACTOR_ID, override_incomplete=True)
    wip_post = await _wo_account_balance(session, acct_1140, wo_id)
    status_final = (
        await session.execute(select(WorkOrder.status).where(WorkOrder.id == wo_id))
    ).scalar()
    assert status_final == "completed"
    assert d_complete.wip_cleared_value == Decimal("100")
    # CRUX: the override path clears 1140 to the pre-issue snapshot Decimal-EXACTLY
    # even though 100/3 leaves a per-unit residual.
    assert wip_post == wip_pre == Decimal("0")

    # MIRROR invariant: the completion debits 1130 by EXACTLY the FG receipt value
    # (planned_qty × fg_unit_cost) and parks the sub-quantum residual in 5190.
    fg_txn = (
        await session.execute(
            select(InventoryTxn.quantity, InventoryTxn.unit_cost).where(
                InventoryTxn.item_id == fg_item,
                InventoryTxn.source_id == wo_id,
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
                    JournalEntry.source_id == wo_id,
                )
            )
        ).scalar()
        or 0
    )
    wo_5190 = await _wo_account_balance(session, acct_5190, wo_id)
    # 1130 debit == FG receipt value == 3 × 33.333333 == 99.999999 (control ties to subledger).
    assert comp_1130_debit == fg_receipt_value == Decimal("99.999999")
    # The residual is parked in 5190 so receipt_value + 5190 == accumulated_wip 100 exactly.
    assert wo_5190 == Decimal("100") - fg_receipt_value
    assert (fg_receipt_value + wo_5190) == Decimal("100")
    assert abs(wo_5190) < Decimal("3") * Decimal("0.000001")
