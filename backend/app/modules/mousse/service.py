# ABOUTME: MOUSSE (Manufacturing Execution) service layer — work-order create,
# ABOUTME: lifecycle (release/hold/resume/cancel/complete), component issue, and
# ABOUTME: the reads/detail loader. Thin router, business logic here (SYERP shape).
# ABOUTME: Material cost flows through 1140 WIP: Dr1140/Cr1130 on issue, the mirror
# ABOUTME: Dr1130/Cr1140 on completion, so a WO's WIP clears to zero (Decimal-exact).
"""
MOUSSE service layer (business logic) — MOUSSE-01.

A work order (WO) consumes a PLUM single-level BOM and SYERP inventory to
produce a finished good. The materials-only slice (D-P10-1/2) books actual
moving-average material cost through the 1140 Work-in-Process clearing account:

  * ISSUE   posts one signed `issue` InventoryTxn per component at the item's
            moving_avg_cost and ONE balanced JE Dr 1140 WIP / Cr 1130 Inventory
            for Σ(qty × moving_avg), all in one atomic commit.
  * COMPLETE receives the planned output at accumulated-WIP unit cost via
            post_receipt(commit=False) and posts the mirror JE Dr 1130 / Cr 1140,
            crediting 1140 for exactly the accumulated WIP debits so the WO's
            1140-attributable balance returns to its pre-WO value Decimal-exactly.

Cross-module surfaces are imported from the SYERP hub service package and PLUM
service by their public names (D-P10-4 — the syerp/service.py split preserves
them). Model + cross-module imports are done lazily inside functions, mirroring
syerp/service/*, to keep this module import-clean and free of import cycles.
All money/qty arithmetic is Decimal (never float — D-11).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.modules.mousse.models import WorkOrder
    from app.modules.mousse.schemas import (
        IssueComponentsRequest,
        IssueResultRead,
        WorkOrderCompleteResult,
        WorkOrderCreate,
        WorkOrderDetailRead,
        WorkOrderRead,
    )


# ---------------------------------------------------------------------------
# Work-order number generation (MOUSSE-01)
# ---------------------------------------------------------------------------
#
# WO numbers follow the numeric-safe WO-###### series, mirroring
# _next_bill_number / _next_po_number: the highest strictly-NUMERIC suffix + 1,
# zero-padded — never a lexicographic MAX (which would re-issue a number once the
# suffix crosses a digit-width boundary, D-P9b-1). The DB unique constraint on
# mousse_work_order.wo_number is the authoritative backstop; this generator is
# best-effort and can race under concurrent draft creation (acceptable — the
# unique constraint rejects a collision, PLAN Risks).

_WO_NUMBER_RE = re.compile(r"^WO-[0-9]+$")


def _next_wo_number(existing_numbers: "Iterable[str]") -> str:
    """
    Compute the next WO-###### number from the set of existing WO numbers.

    Pure (no DB) so the digit-boundary guarantee is unit-testable in isolation.
    Considers only strictly-numeric WO-series numbers (matching ``^WO-[0-9]+$``),
    selects the *numerically* highest suffix, and returns that value + 1
    zero-padded to 6 digits. Returns "WO-000001" when no WO-series numbers exist.
    """
    suffixes = [
        int(number.split("-", 1)[1])
        for number in existing_numbers
        if _WO_NUMBER_RE.match(number)
    ]
    if not suffixes:
        return "WO-000001"
    return f"WO-{max(suffixes) + 1:06d}"


async def generate_wo_number(db: AsyncSession) -> str:
    """
    Generate the next work-order number in the WO-###### series (MOUSSE-01).

    Finds the current highest *numeric* suffix among strictly-numeric WO-series
    numbers by casting the digits after "WO-" to an integer and ordering
    numerically, then delegates the increment to the pure _next_wo_number helper
    (mirrors generate_bill_number). The regex filter MUST precede the cast (a bare
    cast over ``LIKE 'WO-%'`` would throw on a non-numeric number);
    ``func.substring(wo_number, 4)`` skips the 3-character "WO-" prefix (Postgres
    substring is 1-indexed). The DB unique constraint is the authoritative guard;
    create_work_order retries once on an IntegrityError collision.
    """
    from app.modules.mousse.models import WorkOrder

    result = await db.execute(
        select(WorkOrder.wo_number)
        .where(WorkOrder.wo_number.op("~")(r"^WO-[0-9]+$"))
        .order_by(cast(func.substring(WorkOrder.wo_number, 4), Integer).desc())
        .limit(1)
    )
    max_number: str | None = result.scalar()

    return _next_wo_number([max_number] if max_number is not None else [])


# ---------------------------------------------------------------------------
# Work-order create + reads (MOUSSE-01, SC1)
# ---------------------------------------------------------------------------


async def _get_work_order_row(db: AsyncSession, wo_id: str) -> "WorkOrder":
    """Load a WorkOrder ORM row by id, raising HTTP 404 if it does not exist."""
    from app.modules.mousse.models import WorkOrder

    result = await db.execute(select(WorkOrder).where(WorkOrder.id == wo_id))
    wo = result.scalars().first()
    if wo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Work order {wo_id} not found.",
        )
    return wo


async def create_work_order(
    db: AsyncSession, data: "WorkOrderCreate", actor_id: str
) -> "WorkOrderRead":
    """
    Create a Draft work order to build a PLUM part (MOUSSE-01, SC1).

    Validates the build target BEFORE any write (no partial WO):
      - planned_qty must be > 0 (422) — defends the service against non-HTTP
        callers even though WorkOrderCreate already guards it with Field(gt=0);
      - plum_part_id must reference an existing PLUM part (404).

    The WO is created in status "draft" with a server-generated WO-###### number
    (retried once on a unique-constraint collision, mirroring create_bill) and
    `wo_date` defaulting to today when omitted — the single accounting-date basis
    for every JE this WO later posts. released_revision_id / output_item_id stay
    NULL until release. Returns the created WO as a WorkOrderRead.
    """
    import sqlalchemy.exc

    from app.modules.mousse.models import WorkOrder
    from app.modules.mousse.schemas import WorkOrderRead
    from app.modules.plum.models import PlumPart

    if data.planned_qty <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Work-order planned quantity must be greater than zero.",
        )

    # Build target must exist (404) — the WO is anchored to a real PLUM part.
    part_result = await db.execute(
        select(PlumPart.id).where(PlumPart.id == data.plum_part_id)
    )
    if part_result.scalar() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PLUM part {data.plum_part_id} not found.",
        )

    wo_number = await generate_wo_number(db)
    wo = WorkOrder(
        wo_number=wo_number,
        plum_part_id=data.plum_part_id,
        planned_qty=data.planned_qty,
        target_location_id=data.target_location_id,
        status="draft",
        wo_date=data.wo_date or date.today(),
        actor_id=actor_id,
    )
    db.add(wo)
    try:
        await db.commit()
    except sqlalchemy.exc.IntegrityError:
        # Best-effort number generation raced a concurrent draft create — retry
        # once with a freshly derived number (mirrors create_bill / create_po).
        await db.rollback()
        wo_number = await generate_wo_number(db)
        wo = WorkOrder(
            wo_number=wo_number,
            plum_part_id=data.plum_part_id,
            planned_qty=data.planned_qty,
            target_location_id=data.target_location_id,
            status="draft",
            wo_date=data.wo_date or date.today(),
            actor_id=actor_id,
        )
        db.add(wo)
        await db.commit()

    await db.refresh(wo)
    return WorkOrderRead.model_validate(wo)


async def list_work_orders(
    db: AsyncSession, status_filter: str | None = None
) -> "list[WorkOrderRead]":
    """
    List work orders (newest-first), optionally filtered by status (MOUSSE-01).

    Ordered by created_at DESC then wo_number DESC for a stable tie-break
    (mirrors list_bills). Each row is returned as a WorkOrderRead header.
    """
    from app.modules.mousse.models import WorkOrder
    from app.modules.mousse.schemas import WorkOrderRead

    stmt = select(WorkOrder)
    if status_filter is not None:
        stmt = stmt.where(WorkOrder.status == status_filter)
    stmt = stmt.order_by(WorkOrder.created_at.desc(), WorkOrder.wo_number.desc())

    result = await db.execute(stmt)
    return [WorkOrderRead.model_validate(wo) for wo in result.scalars().all()]


async def _component_onhand(
    db: AsyncSession, item_id: str | None, location_id: int
) -> Decimal:
    """
    Derive a component item's on-hand at a location (signed SUM of its txns).

    Returns Decimal("0") when the component has no linked item yet (pre-release)
    or when it has no movements at that location — on-hand is DERIVED, never
    stored (mirrors get_item_onhand / post_adjustment's per-location read).
    """
    from app.modules.syerp.models import InventoryTxn

    if item_id is None:
        return Decimal("0")
    result = await db.execute(
        select(func.coalesce(func.sum(InventoryTxn.quantity), 0)).where(
            InventoryTxn.item_id == item_id,
            InventoryTxn.location_id == location_id,
        )
    )
    return Decimal(result.scalar() or 0)


async def _component_issued_so_far(db: AsyncSession, component_id: str) -> Decimal:
    """
    Sum the positive quantity already issued against a component (MOUSSE-01).

    Σ WorkOrderIssue.quantity for the component, coalesced to Decimal("0") so a
    not-yet-issued component reads 0 rather than NULL (D-P8-4). This is the
    authoritative issued-so-far basis (per-component, not per-item) — two
    components resolving to the same InventoryItem stay distinguishable.
    """
    from app.modules.mousse.models import WorkOrderIssue

    result = await db.execute(
        select(func.coalesce(func.sum(WorkOrderIssue.quantity), 0)).where(
            WorkOrderIssue.component_id == component_id
        )
    )
    return Decimal(result.scalar() or 0)


async def _load_components(
    db: AsyncSession, wo_id: str
) -> "list":
    """Return a WO's components ordered by sort_order (no ORM relationship)."""
    from app.modules.mousse.models import WorkOrderComponent

    result = await db.execute(
        select(WorkOrderComponent)
        .where(WorkOrderComponent.work_order_id == wo_id)
        .order_by(WorkOrderComponent.sort_order)
    )
    return list(result.scalars().all())


async def get_work_order_detail(db: AsyncSession, wo_id: str) -> "WorkOrderDetailRead":
    """
    Load a work order (header + resolved components + derived figures) by id.

    Raises HTTP 404 if the WO does not exist. Each component carries its
    service-DERIVED `on_hand` (the item's live stock at the WO's target location)
    and `issued_so_far` (Σ quantity already issued against that component), so a
    single GET returns enough state to render the issue / under-issue UI (SC1).
    """
    from app.modules.mousse.schemas import WorkOrderComponentRead, WorkOrderDetailRead

    wo = await _get_work_order_row(db, wo_id)
    components = await _load_components(db, wo_id)

    component_reads: list[WorkOrderComponentRead] = []
    for comp in components:
        on_hand = await _component_onhand(db, comp.item_id, wo.target_location_id)
        issued_so_far = await _component_issued_so_far(db, comp.id)
        read = WorkOrderComponentRead.model_validate(comp)
        read.on_hand = on_hand
        read.issued_so_far = issued_so_far
        component_reads.append(read)

    detail = WorkOrderDetailRead.model_validate(wo)
    detail.components = component_reads
    return detail


# ---------------------------------------------------------------------------
# Work-order lifecycle FSM (MOUSSE-01, SC1/SC1b, D-P10-9)
# ---------------------------------------------------------------------------
#
# The lifecycle is pinned in a PURE transition table (no DB, no FastAPI) so the
# legality decision is unit-testable in isolation, exactly like SYERP's
# BILL_TRANSITIONS / PO_TRANSITIONS. The service layer raises HTTP 409 on top of
# a False decision (a state conflict — the WO is not in a status from which the
# requested action is legal). Business-rule rejections that are NOT pure state
# (no released revision, an unlinked component, an under-issued completion) raise
# 422 instead — the transition itself would be legal, the payload/preconditions
# are not.
#
#   draft       -> released | cancelled
#   released    -> in_progress (first issue) | cancelled
#   in_progress -> on_hold | completed
#   on_hold     -> in_progress (resume)
#   completed / cancelled : terminal

_WO_TRANSITIONS: dict[str, set[str]] = {
    "draft":       {"released", "cancelled"},
    "released":    {"in_progress", "cancelled"},
    "in_progress": {"on_hold", "completed"},
    "on_hold":     {"in_progress"},
    "completed":   set(),  # terminal
    "cancelled":   set(),  # terminal
}


def _validate_transition(current: str, target: str) -> bool:
    """
    Pure WO-lifecycle FSM predicate (no DB — unit-testable).

    Returns True when `target` is an allowed successor of `current` per
    _WO_TRANSITIONS (draft->released->in_progress->(on_hold<->in_progress)->
    completed, plus draft/released->cancelled; completed & cancelled terminal).
    The service layer raises HTTP 409 on top of a False result; this helper only
    decides truth (mirrors _bill_transition_allowed).
    """
    return target in _WO_TRANSITIONS.get(current, set())


def _require_transition(wo: "WorkOrder", target: str) -> None:
    """
    Guard a WO state transition, raising HTTP 409 when it is illegal.

    Wraps the pure _validate_transition: a WO can only move to `target` from a
    status _WO_TRANSITIONS permits; otherwise the request conflicts with the WO's
    current state and is rejected 409 (nothing is mutated at the call site).
    """
    if not _validate_transition(wo.status, target):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot transition work order {wo.wo_number} from '{wo.status}' "
                f"to '{target}'. Allowed: {sorted(_WO_TRANSITIONS.get(wo.status, set()))}."
            ),
        )


# ---------------------------------------------------------------------------
# Release — snapshot the single-level BOM (MOUSSE-01, SC1, D-P10-5/7)
# ---------------------------------------------------------------------------


async def _resolve_item_by_part(db: AsyncSession, part_id: str) -> "object | None":
    """Return the InventoryItem linked to a PLUM part (advisory link), or None."""
    from app.modules.syerp.models import InventoryItem

    result = await db.execute(
        select(InventoryItem).where(InventoryItem.plum_part_id == part_id)
    )
    return result.scalars().first()


async def release_work_order(
    db: AsyncSession, wo_id: str, actor_id: str
) -> "WorkOrderRead":
    """
    Release a Draft work order: snapshot its single-level BOM (MOUSSE-01, SC1).

    Guards (each rejects with NOTHING persisted — no partial snapshot, D-P10-7):
      - the WO must be in 'draft' (else 409, FSM);
      - the WO's PLUM part must have a Released revision (else 422, SC1);
      - the WO's OUTPUT finished-good must resolve to a SYERP InventoryItem via
        plum_part_id (else 422 — completion cannot receive an unstocked FG);
      - EVERY direct BOM child must resolve to a linked InventoryItem (else 422 —
        an unstocked component cannot be issued; reject the WHOLE release,
        D-P10-7).

    The snapshot is SINGLE-LEVEL (D-P10-5): only the Released revision's DIRECT
    children (PlumBomItem at parent_revision_id), NOT a multi-level leaf
    explosion — sub-assemblies are issued from stock as components. Each child
    becomes a WorkOrderComponent with qty_per = bom.qty, qty_required = qty_per *
    planned_qty, its resolved item_id, and a unit_of_measure (the child's Released
    revision UoM, falling back to the stock item's UoM). All validation happens
    BEFORE any write; then released_revision_id / output_item_id / status are set
    and the component rows persisted in ONE commit. Returns the WO as a
    WorkOrderRead.
    """
    from app.modules.mousse.models import WorkOrderComponent
    from app.modules.mousse.schemas import WorkOrderRead
    from app.modules.plum.models import PlumBomItem
    from app.modules.plum.service import get_released_revision

    wo = await _get_work_order_row(db, wo_id)
    _require_transition(wo, "released")  # 409 if not draft.

    # SC1: the build target must have a Released revision to snapshot.
    released_rev = await get_released_revision(db, wo.plum_part_id)
    if released_rev is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"PLUM part {wo.plum_part_id} has no Released revision; "
                f"a work order can only be released against a Released revision."
            ),
        )

    # The finished good must resolve to a stockable SYERP item (else completion
    # could never receive it).
    output_item = await _resolve_item_by_part(db, wo.plum_part_id)
    if output_item is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"PLUM part {wo.plum_part_id} has no linked SYERP inventory item; "
                f"the finished good cannot be received into stock on completion."
            ),
        )

    # Single-level BOM: the Released revision's DIRECT children only (D-P10-5).
    bom_result = await db.execute(
        select(PlumBomItem)
        .where(PlumBomItem.parent_revision_id == released_rev.id)
        .order_by(PlumBomItem.sort_order)
    )
    bom_items = list(bom_result.scalars().all())

    # Validate & resolve EVERY component first (no partial snapshot, D-P10-7).
    prepared: list[dict[str, object]] = []
    for bom in bom_items:
        component_item = await _resolve_item_by_part(db, bom.child_part_id)
        if component_item is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"BOM component part {bom.child_part_id} has no linked SYERP "
                    f"inventory item; the whole release is rejected (no partial "
                    f"snapshot, D-P10-7)."
                ),
            )
        # UoM from the child's Released revision when available, else the stock
        # item's UoM (always present) so the snapshot line always has a unit.
        child_rev = await get_released_revision(db, bom.child_part_id)
        uom = (
            child_rev.unit_of_measure
            if child_rev is not None and child_rev.unit_of_measure
            else component_item.unit_of_measure
        )
        prepared.append(
            {
                "child_part_id": bom.child_part_id,
                "item_id": component_item.id,
                "qty_per": bom.qty,
                "qty_required": bom.qty * wo.planned_qty,
                "unit_of_measure": uom,
                "sort_order": bom.sort_order,
            }
        )

    # Persist: header snapshot fields + component rows, in one commit.
    wo.released_revision_id = released_rev.id
    wo.output_item_id = output_item.id
    wo.status = "released"
    for p in prepared:
        db.add(
            WorkOrderComponent(
                work_order_id=wo.id,
                child_part_id=p["child_part_id"],
                item_id=p["item_id"],
                qty_per=p["qty_per"],
                qty_required=p["qty_required"],
                unit_of_measure=p["unit_of_measure"],
                sort_order=p["sort_order"],
            )
        )

    await db.commit()
    await db.refresh(wo)
    return WorkOrderRead.model_validate(wo)


# ---------------------------------------------------------------------------
# Cancel / hold / resume (MOUSSE-01, SC1/SC1b, D-P10-9)
# ---------------------------------------------------------------------------


async def cancel_work_order(
    db: AsyncSession, wo_id: str, actor_id: str
) -> "WorkOrderRead":
    """
    Cancel a work order — allowed only from Draft or Released (MOUSSE-01, SC1).

    An in-progress / on-hold / completed WO has already consumed or produced
    stock and cannot simply be cancelled (409, FSM); cancellation is terminal.
    Sets status='cancelled' in one commit. Returns the WO as a WorkOrderRead.
    """
    from app.modules.mousse.schemas import WorkOrderRead

    wo = await _get_work_order_row(db, wo_id)
    _require_transition(wo, "cancelled")  # 409 unless draft/released.
    wo.status = "cancelled"
    await db.commit()
    await db.refresh(wo)
    return WorkOrderRead.model_validate(wo)


async def hold_work_order(
    db: AsyncSession, wo_id: str, actor_id: str
) -> "WorkOrderRead":
    """
    Put an In-Progress work order On Hold (pause) — MOUSSE-01, SC1b, D-P10-9.

    Only an 'in_progress' WO can be paused (else 409, FSM). Issuing is disallowed
    while On Hold — the WO must be resumed first. Sets status='on_hold' in one
    commit. Returns the WO as a WorkOrderRead.
    """
    from app.modules.mousse.schemas import WorkOrderRead

    wo = await _get_work_order_row(db, wo_id)
    _require_transition(wo, "on_hold")  # 409 unless in_progress.
    wo.status = "on_hold"
    await db.commit()
    await db.refresh(wo)
    return WorkOrderRead.model_validate(wo)


async def resume_work_order(
    db: AsyncSession, wo_id: str, actor_id: str
) -> "WorkOrderRead":
    """
    Resume an On-Hold work order back to In Progress — MOUSSE-01, SC1b, D-P10-9.

    Only an 'on_hold' WO can be resumed (else 409): the FSM also permits
    released->in_progress, but that path is reserved for the first issue, so
    resume requires the WO to currently be On Hold. Sets status='in_progress' in
    one commit. Returns the WO as a WorkOrderRead.
    """
    from app.modules.mousse.schemas import WorkOrderRead

    wo = await _get_work_order_row(db, wo_id)
    if wo.status != "on_hold":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot resume work order {wo.wo_number}: it is '{wo.status}', "
                f"only an 'on_hold' work order can be resumed."
            ),
        )
    wo.status = "in_progress"
    await db.commit()
    await db.refresh(wo)
    return WorkOrderRead.model_validate(wo)


# ---------------------------------------------------------------------------
# Issue components — consume stock into WIP (MOUSSE-01, SC2/SC5, D-P10-3)
# ---------------------------------------------------------------------------


async def issue_components(
    db: AsyncSession,
    wo_id: str,
    request: "IssueComponentsRequest",
    actor_id: str,
) -> "IssueResultRead":
    """
    Issue one or more components against a work order (MOUSSE-01, SC2/SC5).

    The whole issue is ONE atomic unit of work (a single db.commit at the end):
    every guard rejects (404/409/422) with NOTHING persisted, and a successful
    issue lands its inventory movements, ONE balanced JE, and the issue rows
    together — never partially.

    Flow:
      1. The WO must be 'released' or 'in_progress' (else 409) — On Hold must be
         resumed first, and draft/completed/cancelled cannot consume stock.
      2. Resolve each requested component (404 if it is not a line of THIS WO);
         a component with no linked item (not released) is rejected 422. The draw
         location defaults to the WO's target_location_id.
      3. **Lock the contended InventoryItem rows FOR UPDATE in sorted-id order
         BEFORE any on-hand read** (SC5 — copies the create_bill template): a
         concurrent issue against the same item blocks until this transaction
         commits and then re-reads the true on-hand, so two issues can never
         drive on-hand negative or double-consume.
      4. Per line, derive per-location on-hand and apply the SAME per-location
         floor guard SYERP adjustments use (_adjustment_violates_floor); an
         insufficient-stock line is rejected 422. Duplicate (item, location) lines
         within one request accumulate so they cannot jointly overdraw.
      5. Append one signed `issue` InventoryTxn per line (quantity = -qty,
         unit_cost = item.moving_avg_cost, txn_type='issue',
         source_type='mousse_work_order', source_id=wo.id) — added directly, NOT
         via post_adjustment (which lacks commit control and would not value at
         moving_avg).
      6. Post ONE balanced JE Dr 1140 WIP / Cr 1130 Inventory for the total issued
         value = Σ(qty × moving_avg, quantized to _COST_QUANTUM), dated wo.wo_date,
         source-linked to the WO (post_journal_entry(commit=False)).
      7. Write a WorkOrderIssue row per line linking its txn + the JE, flip a
         'released' WO to 'in_progress' (first issue), and take the single commit.

    Returns an IssueResultRead (lines issued + total value booked into WIP).
    """
    from app.modules.mousse.models import WorkOrderComponent, WorkOrderIssue
    from app.modules.mousse.schemas import IssueResultRead
    from app.modules.syerp.models import InventoryItem, InventoryTxn
    from app.modules.syerp.service import (
        _COST_QUANTUM,
        _adjustment_violates_floor,
        _gl_account_id_by_code,
        post_journal_entry,
    )

    wo = await _get_work_order_row(db, wo_id)

    # Only a released or in-progress WO can consume stock (409 otherwise). On Hold
    # is deliberately excluded — the WO must be resumed before issuing (D-P10-9).
    if wo.status not in ("released", "in_progress"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot issue components to work order {wo.wo_number}: it is "
                f"'{wo.status}', only a 'released' or 'in_progress' work order "
                f"can be issued to."
            ),
        )

    # Resolve every requested component against THIS WO before any write.
    resolved: list[tuple[WorkOrderComponent, Decimal, int]] = []
    for line in request.lines:
        comp_result = await db.execute(
            select(WorkOrderComponent).where(
                WorkOrderComponent.id == line.component_id,
                WorkOrderComponent.work_order_id == wo.id,
            )
        )
        comp = comp_result.scalars().first()
        if comp is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Component {line.component_id} is not a line of work order "
                    f"{wo.wo_number}."
                ),
            )
        if comp.item_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Component {comp.id} has no linked inventory item; the work "
                    f"order must be released before its components can be issued."
                ),
            )
        location_id = line.location_id if line.location_id is not None else wo.target_location_id
        resolved.append((comp, line.quantity, location_id))

    # SC5: lock the contended InventoryItem rows FOR UPDATE in sorted-id order
    # BEFORE any on-hand read (create_bill template). Loading the full row also
    # gives the moving_avg_cost each issue values at.
    item_by_id: dict[str, InventoryItem] = {}
    for locked_id in sorted({comp.item_id for comp, _, _ in resolved}):
        item = (
            await db.execute(
                select(InventoryItem).where(InventoryItem.id == locked_id).with_for_update()
            )
        ).scalars().first()
        item_by_id[locked_id] = item

    # Per-location floor guard, then append the signed issue txns. Base on-hand is
    # read once per (item, location); duplicate lines accumulate consumed qty so
    # they cannot jointly overdraw (D-P8-7 per-location floor).
    base_onhand: dict[tuple[str, int], Decimal] = {}
    consumed: dict[tuple[str, int], Decimal] = {}
    total_value = Decimal("0")
    created: list[tuple[WorkOrderComponent, Decimal, int, Decimal, InventoryTxn]] = []
    for comp, qty, location_id in resolved:
        key = (comp.item_id, location_id)
        if key not in base_onhand:
            base_onhand[key] = await _component_onhand(db, comp.item_id, location_id)
            consumed[key] = Decimal("0")
        available = base_onhand[key] - consumed[key]
        if _adjustment_violates_floor(available, -qty):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Issue of {qty} for component {comp.id} exceeds location "
                    f"{location_id} on-hand ({available}) for item {comp.item_id}."
                ),
            )
        consumed[key] += qty

        item = item_by_id[comp.item_id]
        unit_cost = item.moving_avg_cost
        line_value = (qty * unit_cost).quantize(_COST_QUANTUM, rounding=ROUND_HALF_UP)
        total_value += line_value

        txn = InventoryTxn(
            item_id=comp.item_id,
            location_id=location_id,
            txn_type="issue",
            quantity=-qty,
            unit_cost=unit_cost,
            actor_id=actor_id,
            source_type="mousse_work_order",
            source_id=wo.id,
        )
        db.add(txn)
        created.append((comp, qty, location_id, unit_cost, txn))

    # The issue rows require a linked JE (NOT NULL), so the batch must carry a
    # posted, balanced JE — which needs a strictly positive total (a zero-value
    # issue cannot post a balanced Dr/Cr and has no GL meaning here).
    if total_value <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Issue has no material value (components have zero moving-average "
                "cost); nothing to post to WIP."
            ),
        )

    # Materialize the txn ids (and PKs/timestamps) for the issue-row soft links.
    await db.flush()

    # ONE balanced JE: Dr 1140 WIP / Cr 1130 Inventory for the total issued value,
    # dated on the WO's single accounting date and source-linked to the WO. Rides
    # this transaction's single commit (commit=False).
    wip_account_id = await _gl_account_id_by_code(db, "1140")
    inventory_account_id = await _gl_account_id_by_code(db, "1130")
    je = await post_journal_entry(
        db,
        entry_date=wo.wo_date,
        memo=f"WO {wo.wo_number} component issue",
        lines=[
            {"account_id": wip_account_id, "debit": total_value, "credit": 0},
            {"account_id": inventory_account_id, "debit": 0, "credit": total_value},
        ],
        actor_id=actor_id,
        source_type="mousse_work_order",
        source_id=wo.id,
        commit=False,
    )

    # One WorkOrderIssue row per line, linking its txn + the shared JE.
    now = datetime.now(timezone.utc)
    for comp, qty, location_id, unit_cost, txn in created:
        db.add(
            WorkOrderIssue(
                work_order_id=wo.id,
                component_id=comp.id,
                item_id=comp.item_id,
                location_id=location_id,
                quantity=qty,
                unit_cost=unit_cost,
                inventory_txn_id=txn.id,
                journal_entry_id=je.id,
                actor_id=actor_id,
                created_at=now,
            )
        )

    # First issue flips Released -> In Progress (the FSM permits it).
    if wo.status == "released":
        wo.status = "in_progress"

    await db.commit()

    return IssueResultRead(
        work_order_id=wo.id,
        lines_issued=len(created),
        total_issued_value=total_value,
    )


# ---------------------------------------------------------------------------
# Complete — clear WIP to zero, receive the finished good (MOUSSE-01, SC3)
# ---------------------------------------------------------------------------


async def _wo_wip_balance(db: AsyncSession, wip_account_id: int, wo_id: str) -> Decimal:
    """
    Derive a work order's 1140-attributable balance (Σdebit − Σcredit).

    Sums the WIP-account journal lines of every JE soft-linked to THIS WO
    (source_type='mousse_work_order', source_id=wo_id), each side coalesced to
    zero independently (D-P8-4). Before completion this equals the accumulated WIP
    (issue debits only); after the clearing entry it returns to zero. This is the
    EXACT figure the completion JE credits back, so 1140 clears by construction
    (SC3) — no rounding residual can strand WIP.
    """
    from app.modules.syerp.models import JournalEntry, JournalLine

    result = await db.execute(
        select(
            func.coalesce(func.sum(JournalLine.debit), 0)
            - func.coalesce(func.sum(JournalLine.credit), 0)
        )
        .select_from(JournalLine)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .where(
            JournalLine.account_id == wip_account_id,
            JournalEntry.source_type == "mousse_work_order",
            JournalEntry.source_id == wo_id,
        )
    )
    return Decimal(result.scalar() or 0)


async def complete_work_order(
    db: AsyncSession,
    wo_id: str,
    actor_id: str,
    override_incomplete: bool = False,
) -> "WorkOrderCompleteResult":
    """
    Complete an In-Progress work order — clear WIP, receive the FG (MOUSSE-01, SC3).

    The whole completion is ONE atomic unit of work (a single db.commit): every
    guard rejects with NOTHING persisted, and success lands the FG receipt, the
    clearing JE, and the status flip together.

    Guards:
      - the WO must be 'in_progress' (else 409, FSM);
      - **under-issue guard (D-P10-9):** if ANY component has issued_so_far <
        qty_required the completion is rejected 422 UNLESS override_incomplete is
        True; when overridden the completion proceeds and the router audits the
        override + the short components (this service returns them for that audit).

    Costing (D-P10-2 as amended, SC3):
      - accumulated_wip = the WO's 1140-attributable balance (Σ issue debits) —
        read from the GL, so it EQUALS what was actually posted;
      - fg_unit_cost = (accumulated_wip / planned_qty) quantized to _COST_QUANTUM
        with ROUND_HALF_UP (exactly as compute_new_moving_avg quantizes);
      - the FG is received via post_receipt(commit=False) at fg_unit_cost, which
        capitalises EXACTLY receipt_value = planned_qty × fg_unit_cost into
        inventory (updates the FG moving average);
      - ONE balanced JE clears WIP AND ties the inventory control account to the
        subledger, both Decimal-exactly:
          * Cr 1140 WIP for EXACTLY accumulated_wip  → 1140 returns to its pre-WO
            balance (SC3),
          * Dr 1130 Inventory for EXACTLY receipt_value → the 1130 control-account
            debit equals what the FG receipt actually put into the subledger (the
            same qty × unit_cost basis the PO-receive path uses), so 1130 GL ties
            to the inventory subledger,
          * a balancing Dr/Cr 5190 Inventory Rounding for the sub-quantum residual
            (accumulated_wip − receipt_value), which is non-zero only when
            accumulated_wip does not divide evenly by planned_qty under 6-dp
            costing. The residual is routed to an explicit account (D-P10-2 amended
            to add 5190) — NEVER stranded in WIP and NEVER silently breaking the
            1130 control-vs-subledger tie-out. When it is zero the JE has two lines.

    Returns a WorkOrderCompleteResult (FG qty received + WIP value cleared).
    """
    from app.modules.mousse.schemas import WorkOrderCompleteResult
    from app.modules.syerp.service import (
        _COST_QUANTUM,
        _gl_account_id_by_code,
        post_journal_entry,
        post_receipt,
    )

    wo = await _get_work_order_row(db, wo_id)
    _require_transition(wo, "completed")  # 409 unless in_progress.

    # Under-issue guard (D-P10-9): a component short of its required qty blocks
    # completion unless explicitly overridden (the router audits the override).
    components = await _load_components(db, wo_id)
    short_component_ids: list[str] = []
    for comp in components:
        issued = await _component_issued_so_far(db, comp.id)
        if issued < comp.qty_required:
            short_component_ids.append(comp.id)
    if short_component_ids and not override_incomplete:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Work order {wo.wo_number} has under-issued components "
                f"{short_component_ids}; pass override_incomplete=true to complete "
                f"anyway (the override is audited)."
            ),
        )

    wip_account_id = await _gl_account_id_by_code(db, "1140")
    inventory_account_id = await _gl_account_id_by_code(db, "1130")
    rounding_account_id = await _gl_account_id_by_code(db, "5190")

    # Accumulated WIP = the WO's 1140-attributable balance (exact GL figure).
    accumulated_wip = await _wo_wip_balance(db, wip_account_id, wo.id)

    # Per-unit FG cost for the moving-average receipt (quantized like costing).
    fg_unit_cost = (accumulated_wip / wo.planned_qty).quantize(
        _COST_QUANTUM, rounding=ROUND_HALF_UP
    )

    # Receive the planned output into stock at the FG unit cost (updates the FG
    # moving average). commit=False — rides this transaction's single commit.
    await post_receipt(
        db,
        wo.output_item_id,
        wo.target_location_id,
        wo.planned_qty,
        fg_unit_cost,
        actor_id,
        source_type="mousse_work_order",
        source_id=wo.id,
        commit=False,
    )

    # The value the FG receipt actually capitalises into inventory — quantity ×
    # unit_cost, exactly the basis on which post_receipt records the txn and the
    # PO-receive path ties Dr 1130 to the subledger. The 1130 GL debit must equal
    # THIS, not accumulated_wip, or the control account diverges from the subledger.
    receipt_value = (wo.planned_qty * fg_unit_cost).quantize(
        _COST_QUANTUM, rounding=ROUND_HALF_UP
    )
    # Sub-quantum residual: non-zero only when accumulated_wip does not divide
    # evenly by planned_qty under 6-dp costing (e.g. 100 / 3). Routed to 5190 so
    # 1140 clears to zero AND 1130 ties to the subledger — both exactly.
    rounding_residual = accumulated_wip - receipt_value

    # Clearing JE: Cr 1140 for EXACTLY accumulated_wip (WIP clears, SC3), Dr 1130
    # for EXACTLY receipt_value (1130 ties to the subledger), and a balancing
    # Dr/Cr 5190 for the residual. Skipped only in the degenerate zero-WIP case
    # (nothing was issued under an override) — a zero entry cannot balance.
    if accumulated_wip > 0:
        lines: list[dict] = []
        if receipt_value > 0:
            lines.append(
                {"account_id": inventory_account_id, "debit": receipt_value, "credit": 0}
            )
        lines.append({"account_id": wip_account_id, "debit": 0, "credit": accumulated_wip})
        if rounding_residual > 0:
            # WIP consumed exceeds FG capitalised — debit the shortfall to rounding.
            lines.append(
                {"account_id": rounding_account_id, "debit": rounding_residual, "credit": 0}
            )
        elif rounding_residual < 0:
            # FG capitalised exceeds WIP consumed — credit the excess to rounding.
            lines.append(
                {"account_id": rounding_account_id, "debit": 0, "credit": -rounding_residual}
            )
        await post_journal_entry(
            db,
            entry_date=wo.wo_date,
            memo=f"WO {wo.wo_number} completion (WIP -> finished goods)",
            lines=lines,
            actor_id=actor_id,
            source_type="mousse_work_order",
            source_id=wo.id,
            commit=False,
        )

    wo.status = "completed"
    wo.completed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(wo)

    return WorkOrderCompleteResult(
        work_order_id=wo.id,
        output_item_id=wo.output_item_id,
        quantity_received=wo.planned_qty,
        wip_cleared_value=accumulated_wip,
        completed_at=wo.completed_at,
    )
