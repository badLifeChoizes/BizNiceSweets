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
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.modules.mousse.models import WorkOrder
    from app.modules.mousse.schemas import (
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
