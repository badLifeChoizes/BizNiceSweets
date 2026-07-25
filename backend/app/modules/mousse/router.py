# ABOUTME: MOUSSE (Manufacturing Execution) API router — the nine work-order
# ABOUTME: endpoints (list/create/detail + release/issue/hold/resume/complete/
# ABOUTME: cancel). Thin: each delegates to mousse/service.py, gates on
# ABOUTME: mousse:read (GET) / mousse:write (mutations), and writes an
# ABOUTME: attributable audit row AFTER the service commit (write_audit self-commits).
"""
MOUSSE API router — work-order lifecycle (MOUSSE-01, SC1/SC1b/SC6).

Endpoints (mount_all in registry.py adds the /api/v1 prefix — full paths are
/api/v1/mousse/work-orders, etc.; this router carries no prefix and spells the
/mousse/... path on each route):

  GET    /mousse/work-orders                  — list work orders (mousse:read)
  POST   /mousse/work-orders                  — create a Draft WO (mousse:write)
  GET    /mousse/work-orders/{wo_id}          — detail (+ on-hand/issued) (mousse:read)
  POST   /mousse/work-orders/{wo_id}/release  — snapshot BOM, → Released (mousse:write)
  POST   /mousse/work-orders/{wo_id}/issue    — consume components into WIP (mousse:write)
  POST   /mousse/work-orders/{wo_id}/hold     — In Progress → On Hold (mousse:write)
  POST   /mousse/work-orders/{wo_id}/resume   — On Hold → In Progress (mousse:write)
  POST   /mousse/work-orders/{wo_id}/complete — clear WIP, receive FG (mousse:write)
  POST   /mousse/work-orders/{wo_id}/cancel   — cancel from Draft/Released (mousse:write)

Permission gating (D-P10-6):
  - Every mutation (POST) requires mousse:write; every read (GET) requires
    mousse:read. Unauthenticated → 401, wrong permission → 403 (admin is
    wildcard, handled inside require_permission).

Audit logging (D-10, SC6): every mutation writes one AuditLog row with
target_type="work_order" and target_id=wo.id AFTER the service's own commit
(write_audit self-commits, mirroring the SYERP router order):
  - work_order.created   on POST /work-orders
  - work_order.released  on POST /work-orders/{id}/release
  - work_order.issued    on POST /work-orders/{id}/issue
  - work_order.held      on POST /work-orders/{id}/hold
  - work_order.resumed   on POST /work-orders/{id}/resume
  - work_order.completed on POST /work-orders/{id}/complete (records
    override_incomplete + the short components when the override is used, D-P10-9)
  - work_order.cancelled on POST /work-orders/{id}/cancel
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.auth.service import write_audit
from app.modules.mousse.schemas import (
    IssueComponentsRequest,
    IssueResultRead,
    WorkOrderCompleteRequest,
    WorkOrderCompleteResult,
    WorkOrderCreate,
    WorkOrderDetailRead,
    WorkOrderRead,
)
from app.modules.mousse.service import (
    cancel_work_order,
    complete_work_order,
    create_work_order,
    get_work_order_detail,
    hold_work_order,
    issue_components,
    list_work_orders,
    release_work_order,
    resume_work_order,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Work orders — reads (MOUSSE-01, SC1)
# ---------------------------------------------------------------------------


@router.get("/mousse/work-orders", response_model=list[WorkOrderRead])
async def list_work_orders_endpoint(
    status: str | None = None,
    current_user=Depends(require_permission("mousse:read")),
    db: AsyncSession = Depends(get_db),
) -> list[WorkOrderRead]:
    """
    List work orders (newest-first), optionally filtered by status.

    Query param `status` (optional) restricts to one lifecycle status
    (draft | released | in_progress | on_hold | completed | cancelled).
    Read-only: no audit row. Requires mousse:read permission.
    """
    return await list_work_orders(db, status_filter=status)


@router.get("/mousse/work-orders/{wo_id}", response_model=WorkOrderDetailRead)
async def get_work_order_endpoint(
    wo_id: str,
    current_user=Depends(require_permission("mousse:read")),
    db: AsyncSession = Depends(get_db),
) -> WorkOrderDetailRead:
    """
    Get a single work order (header + resolved components) by id.

    Each component carries its service-derived `on_hand` (live stock at the WO's
    target location) and `issued_so_far`, so one GET returns enough state to
    render the issue / under-issue UI. Read-only: no audit row. Requires
    mousse:read. Returns 404 if the work order does not exist.
    """
    return await get_work_order_detail(db, wo_id)


# ---------------------------------------------------------------------------
# Work orders — create + lifecycle mutations (MOUSSE-01, SC1/SC1b/SC6)
# ---------------------------------------------------------------------------


@router.post(
    "/mousse/work-orders",
    response_model=WorkOrderRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_work_order_endpoint(
    data: WorkOrderCreate,
    current_user=Depends(require_permission("mousse:write")),
    db: AsyncSession = Depends(get_db),
) -> WorkOrderRead:
    """
    Create a Draft work order to build a PLUM part.

    Validates planned_qty > 0 (422) and the build-target part (404) before any
    write, then persists a Draft WO with a server-generated WO-###### number.
    Requires mousse:write. Writes a work_order.created audit row after the create
    commits.
    """
    wo = await create_work_order(db, data, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="work_order.created",
        target_type="work_order",
        target_id=wo.id,
        detail=f"Work order created: {wo.wo_number} (build {wo.planned_qty} of {wo.plum_part_id})",
    )
    return wo


@router.post("/mousse/work-orders/{wo_id}/release", response_model=WorkOrderRead)
async def release_work_order_endpoint(
    wo_id: str,
    current_user=Depends(require_permission("mousse:write")),
    db: AsyncSession = Depends(get_db),
) -> WorkOrderRead:
    """
    Release a Draft work order: snapshot its single-level BOM (D-P10-5/7).

    Rejects (nothing persisted) a non-Draft WO (409), a part with no Released
    revision (422), an unstocked finished good (422), or any BOM child with no
    linked inventory item (422 — no partial snapshot). On success snapshots the
    direct BOM into component rows and moves the WO to Released. Requires
    mousse:write. Writes a work_order.released audit row after the release commits.
    """
    wo = await release_work_order(db, wo_id, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="work_order.released",
        target_type="work_order",
        target_id=wo.id,
        detail=f"Work order released: {wo.wo_number} (status: {wo.status})",
    )
    return wo


@router.post("/mousse/work-orders/{wo_id}/issue", response_model=IssueResultRead)
async def issue_components_endpoint(
    wo_id: str,
    data: IssueComponentsRequest,
    current_user=Depends(require_permission("mousse:write")),
    db: AsyncSession = Depends(get_db),
) -> IssueResultRead:
    """
    Issue one or more components against a work order (consume stock into WIP).

    Atomically posts a signed `issue` InventoryTxn per line (at each item's
    moving-average cost, floor-guarded per POOL — each line's optional bin_id is
    explicit-or-unbinned, D-P4-1: a concrete bin draws that bin, None draws only
    the location's unbinned pool) and ONE balanced JE Dr 1140 WIP / Cr 1130
    Inventory for the total; a released WO flips to In Progress on the first
    issue. Rejects (nothing persisted) a WO not in Released/In Progress (409),
    an unknown component (404), or an insufficient-pool line (422 naming the
    pool). Requires mousse:write. Writes a work_order.issued audit row after
    the issue commits.
    """
    result = await issue_components(db, wo_id, data, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="work_order.issued",
        target_type="work_order",
        target_id=wo_id,
        detail=(
            f"Work order {wo_id} issued: {result.lines_issued} component line(s), "
            f"{result.total_issued_value} booked into WIP"
        ),
    )
    return result


@router.post("/mousse/work-orders/{wo_id}/hold", response_model=WorkOrderRead)
async def hold_work_order_endpoint(
    wo_id: str,
    current_user=Depends(require_permission("mousse:write")),
    db: AsyncSession = Depends(get_db),
) -> WorkOrderRead:
    """
    Put an In-Progress work order On Hold (pause) — SC1b, D-P10-9.

    Only an In-Progress WO can be paused (else 409); issuing is disallowed while
    On Hold (the WO must be resumed first). Requires mousse:write. Writes a
    work_order.held audit row after the hold commits.
    """
    wo = await hold_work_order(db, wo_id, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="work_order.held",
        target_type="work_order",
        target_id=wo.id,
        detail=f"Work order put on hold: {wo.wo_number}",
    )
    return wo


@router.post("/mousse/work-orders/{wo_id}/resume", response_model=WorkOrderRead)
async def resume_work_order_endpoint(
    wo_id: str,
    current_user=Depends(require_permission("mousse:write")),
    db: AsyncSession = Depends(get_db),
) -> WorkOrderRead:
    """
    Resume an On-Hold work order back to In Progress — SC1b, D-P10-9.

    Only an On-Hold WO can be resumed (else 409). Requires mousse:write. Writes a
    work_order.resumed audit row after the resume commits.
    """
    wo = await resume_work_order(db, wo_id, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="work_order.resumed",
        target_type="work_order",
        target_id=wo.id,
        detail=f"Work order resumed: {wo.wo_number}",
    )
    return wo


@router.post("/mousse/work-orders/{wo_id}/complete", response_model=WorkOrderCompleteResult)
async def complete_work_order_endpoint(
    wo_id: str,
    data: WorkOrderCompleteRequest,
    current_user=Depends(require_permission("mousse:write")),
    db: AsyncSession = Depends(get_db),
) -> WorkOrderCompleteResult:
    """
    Complete an In-Progress work order — clear WIP, receive the finished good.

    Receives planned_qty of the FG at accumulated-WIP unit cost and posts the
    mirror JE Dr 1130 / Cr 1140 so the WO's 1140 balance clears to zero (SC3).
    Completion is rejected 422 while any component is under-issued UNLESS
    `override_incomplete=true` is passed — the override, and which components were
    short, are recorded in the audit detail (D-P10-9). The short components are
    read from the WO detail BEFORE the service call (completion does not change
    issued-so-far). Requires mousse:write. Writes a work_order.completed audit row
    after the completion commits.
    """
    # Capture which components are short BEFORE completing, for the audited
    # override trail (D-P10-9) — completion never mutates issued-so-far.
    short_component_ids: list[str] = []
    if data.override_incomplete:
        detail = await get_work_order_detail(db, wo_id)
        short_component_ids = [
            comp.id for comp in detail.components if comp.issued_so_far < comp.qty_required
        ]

    result = await complete_work_order(
        db, wo_id, str(current_user.id), override_incomplete=data.override_incomplete
    )

    audit_detail = (
        f"Work order {wo_id} completed: received {result.quantity_received} of "
        f"item {result.output_item_id}, cleared {result.wip_cleared_value} from WIP"
    )
    if data.override_incomplete:
        audit_detail += (
            f" (override_incomplete=true; short components: {short_component_ids})"
        )
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="work_order.completed",
        target_type="work_order",
        target_id=result.work_order_id,
        detail=audit_detail,
    )
    return result


@router.post("/mousse/work-orders/{wo_id}/cancel", response_model=WorkOrderRead)
async def cancel_work_order_endpoint(
    wo_id: str,
    current_user=Depends(require_permission("mousse:write")),
    db: AsyncSession = Depends(get_db),
) -> WorkOrderRead:
    """
    Cancel a work order — allowed only from Draft or Released (else 409).

    An In-Progress / On-Hold / Completed WO has already consumed or produced stock
    and cannot be cancelled; cancellation is terminal. Requires mousse:write.
    Writes a work_order.cancelled audit row after the cancel commits.
    """
    wo = await cancel_work_order(db, wo_id, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="work_order.cancelled",
        target_type="work_order",
        target_id=wo.id,
        detail=f"Work order cancelled: {wo.wo_number}",
    )
    return wo
