# ABOUTME: MOUSSE (Manufacturing Execution) Pydantic request/response schemas —
# ABOUTME: work-order create/read/detail, the resolved-component read, the
# ABOUTME: component-issue request/result, and the completion request/result.
# ABOUTME: Pure Pydantic (never imports the ORM); Read models fill from ORM via
# ABOUTME: from_attributes, service-derived figures are plain Decimal fields.
"""
MOUSSE Pydantic schemas (request/response models) — MOUSSE-01.

Separation (mirrors syerp/schemas.py):
  - Input schemas (Create/Request): no from_attributes — validate incoming JSON.
  - Response schemas (Read/Result): from_attributes=True where they serialize an
    ORM instance; service-CONSTRUCTED reads (with derived figures the service
    computes, e.g. WorkOrderComponentRead.on_hand / issued_so_far) are plain
    models the service fills.

All quantity/money fields are fixed-point `Decimal` (never float — D-11),
matching the Numeric(18,6) columns in mousse/models.py. Positive-quantity guards
(`planned_qty` > 0, issue `quantity` > 0) are enforced at the boundary with
`Field(gt=0)` exactly as syerp/schemas.py enforces its positive amounts.

`status` walks the controlled WO lifecycle:
    draft | released | in_progress | on_hold | completed | cancelled
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Work-order create (MOUSSE-01)
# ---------------------------------------------------------------------------


class WorkOrderCreate(BaseModel):
    """
    Work-order creation payload (POST /mousse/work-orders).

    `plum_part_id` is the FG PLUM part to build; `target_location_id` is the
    SYERP stock location the finished goods will land in. `planned_qty` is the
    quantity to build and must be > 0 (a zero/negative build is meaningless) —
    enforced here with Field(gt=0), mirroring the model's service-layer guard.

    `wo_date` is optional: it is the single accounting-date basis for every
    journal entry this WO posts; the service defaults it to today when omitted.
    `wo_number` and every released/resolved field (revision, output item,
    status) are server-owned and so are absent here.
    """

    plum_part_id: str = Field(..., max_length=36)
    planned_qty: Decimal = Field(..., gt=0)
    target_location_id: int
    wo_date: Optional[date] = None


# ---------------------------------------------------------------------------
# Work-order component read — resolved BOM line (MOUSSE-01)
# ---------------------------------------------------------------------------


class WorkOrderComponentRead(BaseModel):
    """
    One resolved BOM line of a work order, returned to API callers.

    Serialized from a WorkOrderComponent ORM instance (from_attributes=True) for
    the stored fields; `on_hand` and `issued_so_far` are DERIVED figures the
    service populates (they are not ORM columns): `on_hand` is the item's live
    stock at the WO's location, `issued_so_far` is the SUM of quantities already
    issued against this component. Exposing `qty_required` alongside
    `issued_so_far` lets the UI show under-issue at a glance.

    `item_id` is NULL until the WO is released and the component resolves to a
    stockable SYERP item. All quantities are fixed-point Decimals (never float).
    """

    id: str
    work_order_id: str
    child_part_id: str
    item_id: Optional[str] = None
    qty_per: Decimal
    qty_required: Decimal
    unit_of_measure: str
    sort_order: int

    # Service-derived (not ORM columns) — filled by the detail loader.
    on_hand: Decimal = Decimal("0")
    issued_so_far: Decimal = Decimal("0")

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Work-order read (header) + detail (header + components) (MOUSSE-01)
# ---------------------------------------------------------------------------


class WorkOrderRead(BaseModel):
    """
    Work-order header returned to API callers (list rows).

    Serialized from a WorkOrder ORM instance via from_attributes=True. `status`
    walks draft | released | in_progress | on_hold | completed | cancelled;
    `released_revision_id` / `output_item_id` are NULL until release and
    `completed_at` is NULL until completion. `planned_qty` is a fixed-point
    Decimal (Numeric(18,6)), never float.
    """

    id: str
    wo_number: str
    plum_part_id: str
    released_revision_id: Optional[str] = None
    output_item_id: Optional[str] = None
    planned_qty: Decimal
    target_location_id: int
    status: str
    wo_date: date
    actor_id: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WorkOrderDetailRead(WorkOrderRead):
    """
    Work-order detail — the header plus its resolved BOM components nested.

    Extends WorkOrderRead with `components`, each a WorkOrderComponentRead
    carrying its service-derived `on_hand` / `issued_so_far`, so a single GET
    returns the whole order with enough state to render the issue/under-issue UI.
    """

    components: list[WorkOrderComponentRead] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Issue components request / result (MOUSSE-01)
# ---------------------------------------------------------------------------


class IssueComponentLine(BaseModel):
    """
    One line of an issue-components request — a component to consume.

    `quantity` (> 0) of component `component_id` is issued off `location_id`; a
    zero/negative issue is not a consumption, so the > 0 guard is enforced here
    (Field(gt=0)). `location_id` is optional — the service defaults it to the
    work order's `target_location_id` when omitted. Decimal (never float — D-11).
    """

    component_id: str
    quantity: Decimal = Field(..., gt=0)
    location_id: Optional[int] = None


class IssueComponentsRequest(BaseModel):
    """
    Issue-components payload (POST /mousse/work-orders/{id}/issue).

    Consumes one or more components against the work order in a single atomic
    posting. Each line names a component, a positive quantity, and optionally the
    location to draw from (defaulting to the WO's target_location_id).
    """

    lines: list[IssueComponentLine] = Field(..., min_length=1)


class IssueResultRead(BaseModel):
    """
    Result of an issue-components posting returned to API callers.

    Reports the number of component lines issued and the total material value
    consumed (SUM of quantity * unit_cost across the issued lines), booked
    Dr 1140 WIP / Cr 1130 Raw Materials. `total_issued_value` is a fixed-point
    Decimal (never float — D-11).
    """

    work_order_id: str
    lines_issued: int
    total_issued_value: Decimal


# ---------------------------------------------------------------------------
# Work-order complete request / result (MOUSSE-01, D-P10-9)
# ---------------------------------------------------------------------------


class WorkOrderCompleteRequest(BaseModel):
    """
    Work-order completion payload (POST /mousse/work-orders/{id}/complete).

    Completion clears the WO's WIP to zero and receives the finished good into
    stock (Dr 1130 / Cr 1140). By default the service rejects completion while
    any component is under-issued (issued_so_far < qty_required); setting
    `override_incomplete=True` acknowledges the shortfall and completes anyway
    (D-P10-9).
    """

    override_incomplete: bool = False


class WorkOrderCompleteResult(BaseModel):
    """
    Result of a work-order completion returned to API callers.

    Reports the finished-good quantity received into stock and the total value
    cleared out of WIP (Dr 1130 / Cr 1140), which equals the WO's accumulated
    1140 balance so it returns to zero (Decimal-exact — D-11). `output_item_id`
    is the SYERP FG item the build stocked; `completed_at` is the completion
    timestamp.
    """

    work_order_id: str
    output_item_id: str
    quantity_received: Decimal
    wip_cleared_value: Decimal
    completed_at: datetime
