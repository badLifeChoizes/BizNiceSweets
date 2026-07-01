"""
PLUM API router.

Phase 5: Part CRUD + revision FSM endpoints.
Phase 6: BOM/AVL/cost/where-used endpoints.

Endpoints (all prefixed with /api/v1/plum by registry.py mount_all):
  GET    /plum/parts                                      — list/search parts (plum:read)
  GET    /plum/parts/next-number                          — next auto-generated part number (plum:read)
  POST   /plum/parts                                      — create part + first Draft revision (plum:write)
  GET    /plum/parts/{part_id}                            — get part + revision history (plum:read)
  PATCH  /plum/parts/{part_id}                            — update/archive part (plum:write)
  POST   /plum/parts/{part_id}/revisions                  — create new revision (plum:write)
  POST   /plum/parts/{part_id}/revisions/{rev_id}/advance — advance revision status (plum:write)

  Phase 6 — BOM (PLUM-04/05/06):
  GET    /plum/parts/{part_id}/bom                        — BOM tree (plum:read)
  GET    /plum/parts/{part_id}/bom/flat                   — flat BOM with rolled-up qty (plum:read)
  GET    /plum/parts/{part_id}/where-used                 — reverse traversal (plum:read)
  POST   /plum/parts/{part_id}/bom                        — add BOM line to Draft revision (plum:write)
  PATCH  /plum/parts/{part_id}/bom/{line_id}              — update BOM line (plum:write)
  DELETE /plum/parts/{part_id}/bom/{line_id}              — remove BOM line (plum:write)

  Phase 6 — AVL (PLUM-07):
  GET    /plum/parts/{part_id}/avl                        — list AVL links (plum:read)
  POST   /plum/parts/{part_id}/avl                        — link part to vendor (plum:write)
  PATCH  /plum/parts/{part_id}/avl/{link_id}              — update AVL link (plum:write)
  DELETE /plum/parts/{part_id}/avl/{link_id}              — soft-delete AVL link (plum:write)
  POST   /plum/parts/{part_id}/avl/{link_id}/price-breaks — add price break (plum:write)

  Phase 6 — Costing (PLUM-08/09):
  GET    /plum/parts/{part_id}/revisions/{rev_id}/cost    — effective cost read (plum:read)
  PATCH  /plum/parts/{part_id}/revisions/{rev_id}/cost    — update cost fields on Draft (plum:write)

mount_all() in registry.py adds the /api/v1 prefix — do NOT include it here.
Full paths are therefore /api/v1/plum/parts, etc.

Permission gating (D-10):
  - All write (POST, PATCH, DELETE) endpoints require plum:write.
  - All read (GET) endpoints require plum:read.
  - Unauthenticated requests return 401; wrong permission returns 403.

Audit logging:
  Phase 5 audit (part.created / part.updated / part.archived / revision.created /
    revision.submitted / revision.released / revision.rejected / revision.obsoleted).
  Phase 6 audit is written inside the service functions to keep the transaction
    atomic — the router only passes actor_id=str(current_user.id).
  Phase 6 actions: bom.line_added / bom.line_updated / bom.line_removed /
    avl.link_added / avl.link_updated / avl.link_removed / part.cost_updated.

Archive strategy:
  Archive flows through PATCH with {active: false}. The router compares the
  current active state before applying the update to select the correct audit
  action string (mirrors syerp/router.py was_active pattern).
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.auth.service import write_audit
from app.modules.plum.schemas import (
    AvlLinkCreate,
    AvlLinkRead,
    AvlLinkUpdate,
    BomItemCreate,
    BomItemRead,
    BomItemUpdate,
    BomTreeNode,
    CostRead,
    CostUpdate,
    FlatBomRow,
    ImportCommitResponse,
    ImportPreviewResponse,
    PartCreate,
    PartDetailRead,
    PartRead,
    PartUpdate,
    PriceBreakCreate,
    PriceBreakRead,
    RevisionCreate,
    RevisionRead,
    WhereUsedRow,
)
from app.modules.plum.service import (
    add_avl_link,
    add_bom_line,
    add_price_break,
    advance_revision_status,
    build_json_export,
    commit_import,
    create_part,
    create_revision,
    generate_excel_export,
    generate_part_number,
    get_cost_read,
    get_part,
    get_part_with_revisions,
    get_revision,
    get_where_used,
    list_avl_links,
    list_parts,
    load_bom_tree,
    load_flat_bom,
    parse_excel_import,
    parse_json_import,
    remove_avl_link,
    remove_bom_line,
    update_avl_link,
    update_bom_line,
    update_cost,
    update_part,
    validate_import,
)

router = APIRouter(prefix="/plum", tags=["plum"])


# ---------------------------------------------------------------------------
# Parts list + search
# ---------------------------------------------------------------------------


@router.get("/parts", response_model=list[PartRead])
async def list_parts_endpoint(
    q: str | None = None,
    status: str | None = None,
    include_archived: bool = False,
    current_user=Depends(require_permission("plum:read")),
    db: AsyncSession = Depends(get_db),
) -> list[PartRead]:
    """
    List / search parts.

    Query params:
      q: substring search across part_number + current revision description
         (server-side, parameterized ilike — T-05-06).
      status: filter by current revision status (draft / in_review / released / obsolete).
      include_archived: when true, includes active=False parts (default false).

    Returns parts ordered by part_number ascending.
    Requires plum:read permission.
    """
    parts = await list_parts(
        db, q=q, status_filter=status, include_archived=include_archived
    )
    return parts


# ---------------------------------------------------------------------------
# Next part number (prefill helper)
# ---------------------------------------------------------------------------


@router.get("/parts/next-number")
async def next_part_number_endpoint(
    current_user=Depends(require_permission("plum:read")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Return the next auto-generated part number for use as a create-sheet prefill.

    This is a read-only query — it does NOT reserve the number. The actual number
    assigned is decided at create time (which may generate a different number if
    a concurrent create occurs between this call and the POST /parts call).

    Requires plum:read permission.
    """
    part_number = await generate_part_number(db)
    return {"part_number": part_number}


# ---------------------------------------------------------------------------
# Create part
# ---------------------------------------------------------------------------


@router.post("/parts", response_model=PartRead, status_code=status.HTTP_201_CREATED)
async def create_part_endpoint(
    data: PartCreate,
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> PartRead:
    """
    Create a new part.

    Auto-generates a unique P##### part number if not supplied in the payload.
    Auto-creates the first revision in Draft status with revision_number=1 (D-03).
    Requires plum:write permission. Writes a part.created audit log row.
    Returns 409 if a user-supplied part_number already exists (D-06).
    """
    part = await create_part(db, data)

    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="part.created",
        target_type="part",
        target_id=str(part.id),
        detail=f"Part created: {part.part_number}",
    )

    # Build PartRead response (list_parts returns dicts; create_part returns ORM)
    # Fetch the current revision info for the response
    detail = await get_part_with_revisions(db, part.id)
    revisions = detail["revisions"]
    current_rev = revisions[0] if revisions else None

    return {  # type: ignore[return-value]
        "id": part.id,
        "part_number": part.part_number,
        "active": part.active,
        "created_at": part.created_at,
        "updated_at": part.updated_at,
        "current_revision_label": current_rev.revision_label if current_rev else None,
        "current_revision_status": current_rev.status if current_rev else None,
        "tags": detail["tags"],
    }


# ---------------------------------------------------------------------------
# Get part detail
# ---------------------------------------------------------------------------


@router.get("/parts/{part_id}", response_model=PartDetailRead)
async def get_part_detail_endpoint(
    part_id: str,
    current_user=Depends(require_permission("plum:read")),
    db: AsyncSession = Depends(get_db),
) -> PartDetailRead:
    """
    Get a single part with its full revision history.

    Returns PartDetailRead (part fields + revisions list ordered newest-first).
    Requires plum:read permission. Returns 404 if part does not exist.
    """
    return await get_part_with_revisions(db, part_id)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Update / archive part
# ---------------------------------------------------------------------------


@router.patch("/parts/{part_id}", response_model=PartRead)
async def update_part_endpoint(
    part_id: str,
    data: PartUpdate,
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> PartRead:
    """
    Partially update a part (PATCH semantics).

    Sending {active: false} archives the part (D-11 soft-delete).
    Revision-controlled fields (description, category, unit_of_measure, notes)
    are applied to the current Draft revision; a 422 is returned if the current
    revision is Released (D-07 immutability, T-05-07).

    Requires plum:write permission. Writes audit log with correct action:
      - "part.archived" when active transitions True → False
      - "part.updated" for all other mutations

    Returns 404 if part does not exist.
    """
    # Read current state before mutation to detect archive transition
    existing = await get_part(db, part_id)
    was_active = existing.active

    part_data = await update_part(db, part_id, data)

    # Select audit action based on active state transition
    is_archiving = data.active is False and was_active is True
    audit_action = "part.archived" if is_archiving else "part.updated"

    await write_audit(
        db,
        actor_id=str(current_user.id),
        action=audit_action,
        target_type="part",
        target_id=part_id,
        detail=f"Part {audit_action.split('.')[1]}: {part_data['part_number']}",
    )

    return part_data  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Create revision
# ---------------------------------------------------------------------------


@router.post(
    "/parts/{part_id}/revisions",
    response_model=RevisionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_revision_endpoint(
    part_id: str,
    data: RevisionCreate,
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> RevisionRead:
    """
    Create a new Draft revision for a part.

    Copies attributes forward from the source revision (D-03). Source defaults to
    the latest Released revision; falls back to latest overall revision. Caller may
    specify source_revision_id to clone from a specific prior revision.

    Requires plum:write permission. Writes a revision.created audit log row.
    Returns 404 if part does not exist. Returns 201 with the new RevisionRead.
    """
    revision = await create_revision(db, part_id, data, actor_id=str(current_user.id))
    return revision  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Advance revision status
# ---------------------------------------------------------------------------


class AdvanceStatusBody(BaseModel):
    """Request body for POST /parts/{part_id}/revisions/{rev_id}/advance."""

    target_status: str


class BomAddBody(BomItemCreate):
    """
    Request body for POST /parts/{part_id}/bom.

    Extends BomItemCreate with an optional `revision_id` field. When
    revision_id is omitted the endpoint auto-resolves to the part's latest
    revision (by revision_number). Tests that assert 422 on Released revisions
    rely on this auto-resolution path.
    """

    revision_id: Optional[str] = None


@router.post(
    "/parts/{part_id}/revisions/{rev_id}/advance",
    response_model=RevisionRead,
)
async def advance_revision_status_endpoint(
    part_id: str,
    rev_id: str,
    body: AdvanceStatusBody,
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> RevisionRead:
    """
    Advance a revision through the lifecycle state machine (D-07/D-08).

    Valid transitions:
      draft → in_review        (submit for review)
      in_review → released     (release — auto-obsoletes prior released revision, D-08)
      in_review → draft        (reject / send back)
      released → obsolete      (not directly accessible; only via supersede)

    Returns 422 for invalid transitions or if the target_status is not a valid
    transition from the current status.

    On →released: prior Released revision is auto-obsoleted in the same transaction.
    Audit events are written inside the service (revision.submitted / revision.released /
    revision.rejected / revision.obsoleted).

    Requires plum:write permission. Returns 404 if part or revision not found.
    """
    # Handle "latest" as a sentinel to resolve the most recent revision by
    # revision_number. Tests use /revisions/latest/advance for brevity.
    resolved_rev_id = rev_id
    if rev_id == "latest":
        from app.modules.plum.models import PlumPartRevision

        result = await db.execute(
            select(PlumPartRevision.id).where(
                PlumPartRevision.part_id == part_id
            ).order_by(PlumPartRevision.revision_number.desc()).limit(1)
        )
        row = result.first()
        if row is None:
            from fastapi import HTTPException as _HTTPException
            raise _HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No revisions found for part {part_id}",
            )
        resolved_rev_id = row[0]

    revision = await advance_revision_status(
        db,
        part_id=part_id,
        revision_id=resolved_rev_id,
        target_status=body.target_status,
        actor_id=str(current_user.id),
    )
    return revision  # type: ignore[return-value]


# ===========================================================================
# Phase 6: BOM endpoints (PLUM-04/05/06)
# ===========================================================================


# ---------------------------------------------------------------------------
# GET /parts/{part_id}/bom — BOM tree
# ---------------------------------------------------------------------------


@router.get("/parts/{part_id}/bom", response_model=list[BomTreeNode])
async def get_bom_tree_endpoint(
    part_id: str,
    rev_id: Optional[str] = Query(None, description="Revision ID; defaults to latest"),
    current_user=Depends(require_permission("plum:read")),
    db: AsyncSession = Depends(get_db),
) -> list[BomTreeNode]:
    """
    Return the BOM as a nested tree (PLUM-04/D-02/D-03).

    Children resolve to their latest Released revision (D-02), falling back
    to the latest Draft with is_unreleased=True (D-03).
    Requires plum:read permission.
    """
    if rev_id is None:
        from app.modules.plum.models import PlumPartRevision

        result = await db.execute(
            select(PlumPartRevision.id).where(
                PlumPartRevision.part_id == part_id
            ).order_by(PlumPartRevision.revision_number.desc()).limit(1)
        )
        row = result.first()
        if row is None:
            from fastapi import HTTPException as _HTTPException
            raise _HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No revisions found for part {part_id}",
            )
        rev_id = row[0]

    tree = await load_bom_tree(db, part_id, rev_id)
    return tree  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# GET /parts/{part_id}/bom/flat — flat BOM with rolled-up quantities
# ---------------------------------------------------------------------------


@router.get("/parts/{part_id}/bom/flat", response_model=list[FlatBomRow])
async def get_flat_bom_endpoint(
    part_id: str,
    rev_id: Optional[str] = Query(None, description="Revision ID; defaults to latest"),
    current_user=Depends(require_permission("plum:read")),
    db: AsyncSession = Depends(get_db),
) -> list[FlatBomRow]:
    """
    Return the flat BOM with total quantities rolled up across all paths
    (PLUM-05/D-04). Shared sub-assemblies appear once with summed total_qty.
    Requires plum:read permission.
    """
    if rev_id is None:
        from app.modules.plum.models import PlumPartRevision

        result = await db.execute(
            select(PlumPartRevision.id).where(
                PlumPartRevision.part_id == part_id
            ).order_by(PlumPartRevision.revision_number.desc()).limit(1)
        )
        row = result.first()
        if row is None:
            from fastapi import HTTPException as _HTTPException
            raise _HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No revisions found for part {part_id}",
            )
        rev_id = row[0]

    flat = await load_flat_bom(db, part_id, rev_id)
    return flat  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# GET /parts/{part_id}/where-used — reverse traversal
# ---------------------------------------------------------------------------


@router.get("/parts/{part_id}/where-used", response_model=list[WhereUsedRow])
async def get_where_used_endpoint(
    part_id: str,
    current_user=Depends(require_permission("plum:read")),
    db: AsyncSession = Depends(get_db),
) -> list[WhereUsedRow]:
    """
    Return all parent assemblies that reference this part, direct or indirect
    (PLUM-06). Indirect ancestors have indirect=True.
    Requires plum:read permission.
    """
    rows = await get_where_used(db, part_id)
    return rows  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# POST /parts/{part_id}/bom — add BOM line (Draft-only, 201)
# ---------------------------------------------------------------------------


@router.post(
    "/parts/{part_id}/bom",
    response_model=BomItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_bom_line_endpoint(
    part_id: str,
    data: BomAddBody,
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> BomItemRead:
    """
    Add a child part to a Draft revision's BOM (PLUM-04/D-01/D-05).

    `revision_id` in the body selects the target revision; if omitted the
    latest revision (by revision_number) is used. Returns 422 if the revision
    is not in Draft status (T-06-05) or if adding the child would create a
    cycle (T-06-06). Writes bom.line_added audit event.
    Requires plum:write permission.
    """
    # Resolve revision_id: use body value or auto-resolve to latest
    resolved_rev_id = data.revision_id
    if resolved_rev_id is None:
        from app.modules.plum.models import PlumPartRevision

        result = await db.execute(
            select(PlumPartRevision.id).where(
                PlumPartRevision.part_id == part_id
            ).order_by(PlumPartRevision.revision_number.desc()).limit(1)
        )
        row = result.first()
        if row is None:
            from fastapi import HTTPException as _HTTPException
            raise _HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No revisions found for part {part_id}",
            )
        resolved_rev_id = row[0]

    # Build the BomItemCreate (without revision_id) for the service call
    item_data = BomItemCreate(
        child_part_id=data.child_part_id,
        qty=data.qty,
        ref_des=data.ref_des,
        sort_order=data.sort_order,
    )

    bom_item = await add_bom_line(
        db,
        part_id=part_id,
        data=item_data,
        revision_id=resolved_rev_id,
        actor_id=str(current_user.id),
    )
    return bom_item  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# PATCH /parts/{part_id}/bom/{line_id} — update BOM line
# ---------------------------------------------------------------------------


@router.patch("/parts/{part_id}/bom/{line_id}", response_model=BomItemRead)
async def update_bom_line_endpoint(
    part_id: str,
    line_id: str,
    data: BomItemUpdate,
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> BomItemRead:
    """
    Update qty/ref_des/sort_order of a BOM line (PLUM-04/D-01).

    Returns 422 if the revision is not in Draft status (T-06-05).
    Requires plum:write permission. Writes bom.line_updated audit event.
    """
    bom_item = await update_bom_line(
        db,
        part_id=part_id,
        line_id=line_id,
        data=data,
        actor_id=str(current_user.id),
    )
    return bom_item  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# DELETE /parts/{part_id}/bom/{line_id} — remove BOM line
# ---------------------------------------------------------------------------


@router.delete(
    "/parts/{part_id}/bom/{line_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_bom_line_endpoint(
    part_id: str,
    line_id: str,
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Remove a BOM line from a Draft revision (PLUM-04/D-01).

    Returns 422 if the revision is not in Draft status (T-06-05).
    Requires plum:write permission. Writes bom.line_removed audit event.
    """
    await remove_bom_line(
        db,
        part_id=part_id,
        line_id=line_id,
        actor_id=str(current_user.id),
    )


# ===========================================================================
# Phase 6: AVL endpoints (PLUM-07)
# ===========================================================================


# ---------------------------------------------------------------------------
# GET /parts/{part_id}/avl — list AVL links
# ---------------------------------------------------------------------------


@router.get("/parts/{part_id}/avl", response_model=list[AvlLinkRead])
async def list_avl_links_endpoint(
    part_id: str,
    current_user=Depends(require_permission("plum:read")),
    db: AsyncSession = Depends(get_db),
) -> list[AvlLinkRead]:
    """
    List all AVL links for a part, including embedded price breaks (PLUM-07/D-11).

    Includes active=False links (archived vendors still surface, Pitfall 4).
    Requires plum:read permission.
    """
    links = await list_avl_links(db, part_id)
    return links  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# POST /parts/{part_id}/avl — add AVL link (201)
# ---------------------------------------------------------------------------


@router.post(
    "/parts/{part_id}/avl",
    response_model=AvlLinkRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_avl_link_endpoint(
    part_id: str,
    data: AvlLinkCreate,
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> AvlLinkRead:
    """
    Link a part to a SYERP vendor in the Approved Vendor List (PLUM-07/D-13).

    Validates that the vendor exists with is_vendor=True (T-06-07). Returns 422
    if the vendor is not found or is not a vendor.
    Requires plum:write permission. Writes avl.link_added audit event.
    """
    link = await add_avl_link(
        db,
        part_id=part_id,
        data=data,
        actor_id=str(current_user.id),
    )
    return link  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# PATCH /parts/{part_id}/avl/{link_id} — update AVL link
# ---------------------------------------------------------------------------


@router.patch("/parts/{part_id}/avl/{link_id}", response_model=AvlLinkRead)
async def update_avl_link_endpoint(
    part_id: str,
    link_id: str,
    data: AvlLinkUpdate,
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> AvlLinkRead:
    """
    Update metadata on an AVL link (PLUM-07/D-11).

    vendor_id and price_breaks are immutable via this endpoint.
    Requires plum:write permission. Writes avl.link_updated audit event.
    """
    link = await update_avl_link(
        db,
        part_id=part_id,
        link_id=link_id,
        data=data,
        actor_id=str(current_user.id),
    )
    return link  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# DELETE /parts/{part_id}/avl/{link_id} — soft-delete AVL link
# ---------------------------------------------------------------------------


@router.delete(
    "/parts/{part_id}/avl/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_avl_link_endpoint(
    part_id: str,
    link_id: str,
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Soft-delete an AVL link by setting active=False (PLUM-07/D-11).

    Requires plum:write permission. Writes avl.link_removed audit event.
    """
    await remove_avl_link(
        db,
        part_id=part_id,
        link_id=link_id,
        actor_id=str(current_user.id),
    )


# ---------------------------------------------------------------------------
# POST /parts/{part_id}/avl/{link_id}/price-breaks — add price break (201)
# ---------------------------------------------------------------------------


@router.post(
    "/parts/{part_id}/avl/{link_id}/price-breaks",
    response_model=PriceBreakRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_price_break_endpoint(
    part_id: str,
    link_id: str,
    data: PriceBreakCreate,
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> PriceBreakRead:
    """
    Add a price break to an AVL link (PLUM-07/D-11).

    Price breaks are returned sorted by qty_threshold ascending.
    Requires plum:write permission. Writes avl.price_break_added audit event.
    """
    pb = await add_price_break(
        db,
        part_id=part_id,
        link_id=link_id,
        data=data,
        actor_id=str(current_user.id),
    )
    return pb  # type: ignore[return-value]


# ===========================================================================
# Phase 6: Costing endpoints (PLUM-08/09)
# ===========================================================================


# ---------------------------------------------------------------------------
# GET /parts/{part_id}/revisions/{rev_id}/cost — effective cost read
# ---------------------------------------------------------------------------


@router.get(
    "/parts/{part_id}/revisions/{rev_id}/cost",
    response_model=CostRead,
)
async def get_cost_endpoint(
    part_id: str,
    rev_id: str,
    current_user=Depends(require_permission("plum:read")),
    db: AsyncSession = Depends(get_db),
) -> CostRead:
    """
    Return the full cost summary for a revision (PLUM-08/09/D-07).

    Computes effective_cost via the D-07 chain (vendor price → manual →
    roll-up → uncosted), live bom_rollup_cost, margin, and margin_pct.
    Released revisions also expose released_cost_snapshot (D-14).
    Requires plum:read permission.
    """
    cost = await get_cost_read(db, part_id, rev_id)
    return cost  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# PATCH /parts/{part_id}/revisions/{rev_id}/cost — update cost fields on Draft
# ---------------------------------------------------------------------------


@router.patch(
    "/parts/{part_id}/revisions/{rev_id}/cost",
    response_model=CostRead,
)
async def update_cost_endpoint(
    part_id: str,
    rev_id: str,
    data: CostUpdate,
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> CostRead:
    """
    Update cost fields on a Draft revision (PLUM-08/D-06/D-07).

    Accepted fields: material_cost, sale_price, selected_vendor_link_id,
    selected_price_break_index. Returns 422 if revision is not Draft.
    Requires plum:write permission. Writes part.cost_updated audit event.
    Returns the updated CostRead after applying changes.
    """
    await update_cost(
        db,
        part_id=part_id,
        revision_id=rev_id,
        data=data,
        actor_id=str(current_user.id),
    )
    # Return the updated cost read for the caller
    cost = await get_cost_read(db, part_id, rev_id)
    return cost  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# GET /export/json — lossless JSON export (PLUM-10, D-16/D-19)
# ---------------------------------------------------------------------------


@router.get("/export/json")
async def export_json_endpoint(
    current_user=Depends(require_permission("plum:read")),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Export the full PLUM dataset as a lossless JSON file (PLUM-10, D-16).

    Returns a StreamingResponse with Content-Disposition attachment so the
    browser triggers a file download. The JSON schema is fully round-trip
    compatible with POST /import/commit.

    Requires plum:read permission (D-19).
    Writes audit event plum.exported (D-19).
    """
    data = await build_json_export(db)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="plum.exported",
        target_type="export",
        target_id="",
        detail="json",
    )
    json_bytes = json.dumps(data, default=str).encode("utf-8")

    from io import BytesIO

    return StreamingResponse(
        BytesIO(json_bytes),
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; filename=plum-export.json"
        },
    )


# ---------------------------------------------------------------------------
# GET /export/excel — Excel export (PLUM-10, D-16/D-19)
# ---------------------------------------------------------------------------


@router.get("/export/excel")
async def export_excel_endpoint(
    current_user=Depends(require_permission("plum:read")),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Export the PLUM dataset as a three-sheet Excel (.xlsx) workbook (PLUM-10, D-16).

    Sheets: Parts, BOM, AVL. Human-friendly format for review and bulk-editing.
    The Excel file can be re-imported via POST /import/preview + /import/commit.

    Requires plum:read permission (D-19).
    Writes audit event plum.exported (D-19).
    """
    data = await build_json_export(db)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="plum.exported",
        target_type="export",
        target_id="",
        detail="excel",
    )
    xlsx_bytes = generate_excel_export(data)

    from io import BytesIO

    return StreamingResponse(
        BytesIO(xlsx_bytes),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": "attachment; filename=plum-export.xlsx"
        },
    )


# ---------------------------------------------------------------------------
# POST /import/preview — import preview / dry-run (PLUM-10, D-18 step 1)
# ---------------------------------------------------------------------------


@router.post("/import/preview", response_model=ImportPreviewResponse)
async def import_preview_endpoint(
    file: UploadFile = File(...),
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> ImportPreviewResponse:
    """
    Preview an import file without writing to the DB (PLUM-10, D-18 step 1).

    Accepts .json or .xlsx upload. Validates cross-references, counts new vs.
    updated rows, and returns any row-level errors. No data is written.

    Upload guard: rejects files > 10 MB (T-06-11, 413).
    Format dispatch: .json → parse_json_import; .xlsx → parse_excel_import.
    Unsupported extensions → 422.

    Requires plum:write permission (D-19).
    """
    content = await file.read()

    # T-06-11: 10 MB upload guard
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 10 MB limit.",
        )

    filename = file.filename or ""
    if filename.endswith(".json"):
        data = parse_json_import(content)
    elif filename.endswith(".xlsx"):
        data = parse_excel_import(content)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported file type. Use .json or .xlsx",
        )

    return await validate_import(db, data)


# ---------------------------------------------------------------------------
# POST /import/validate — alias for /import/preview (test stub uses /validate)
# ---------------------------------------------------------------------------


@router.post("/import/validate", response_model=ImportPreviewResponse)
async def import_validate_endpoint(
    file: UploadFile = File(...),
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> ImportPreviewResponse:
    """
    Alias for POST /import/preview (Wave-0 test stubs reference /import/validate).

    Identical behavior to /import/preview — see that endpoint for full docs.
    Requires plum:write permission (D-19).
    """
    content = await file.read()

    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 10 MB limit.",
        )

    filename = file.filename or ""
    if filename.endswith(".json"):
        data = parse_json_import(content)
    elif filename.endswith(".xlsx"):
        data = parse_excel_import(content)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported file type. Use .json or .xlsx",
        )

    return await validate_import(db, data)


# ---------------------------------------------------------------------------
# POST /import/commit — transactional upsert commit (PLUM-10, D-17/D-18 step 2)
# ---------------------------------------------------------------------------


@router.post("/import/commit", response_model=ImportCommitResponse)
async def import_commit_endpoint(
    file: UploadFile = File(...),
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> ImportCommitResponse:
    """
    Commit an import file to the database (PLUM-10, D-17/D-18 step 2).

    Re-parses and re-validates the uploaded file (stateless, D-18 Open Question 2
    resolution: client re-sends the same file). Blocks on any validation errors
    (D-18: any unresolved error blocks commit). Applies upsert in one transaction
    (never hard-deletes parts/revisions/BOM/AVL absent from the file — D-17).

    Upload guard: rejects files > 10 MB (T-06-11, 413).
    Writes audit event plum.imported (D-19, written inside commit_import).

    Requires plum:write permission (D-19).
    """
    content = await file.read()

    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 10 MB limit.",
        )

    filename = file.filename or ""
    if filename.endswith(".json"):
        data = parse_json_import(content)
    elif filename.endswith(".xlsx"):
        data = parse_excel_import(content)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported file type. Use .json or .xlsx",
        )

    return await commit_import(db, data, actor_id=str(current_user.id))
