"""
PLUM API router.

Phase 5: Part CRUD + revision FSM endpoints.

Endpoints (all prefixed with /api/v1/plum by registry.py mount_all):
  GET    /plum/parts                              — list/search parts (plum:read)
  GET    /plum/parts/next-number                  — next auto-generated part number (plum:read)
  POST   /plum/parts                              — create part + first Draft revision (plum:write)
  GET    /plum/parts/{part_id}                    — get part + revision history (plum:read)
  PATCH  /plum/parts/{part_id}                    — update/archive part (plum:write)
  POST   /plum/parts/{part_id}/revisions          — create new revision (plum:write)
  POST   /plum/parts/{part_id}/revisions/{rev_id}/advance — advance revision status (plum:write)

mount_all() in registry.py adds the /api/v1 prefix — do NOT include it here.
Full paths are therefore /api/v1/plum/parts, etc.

Permission gating (D-10):
  - All write (POST, PATCH) endpoints require plum:write.
  - All read (GET) endpoints require plum:read.
  - Unauthenticated requests return 401; wrong permission returns 403.

Audit logging (D-10, T-05-09):
  - part.created: on POST /parts success.
  - part.updated: on PATCH when active does not change to False.
  - part.archived: on PATCH when patch sets active=False.
  - revision.created: on POST /parts/{id}/revisions success.
  - revision.submitted: on advance to in_review (written inside service).
  - revision.released: on advance to released (written inside service).
  - revision.rejected: on advance back to draft (written inside service).
  - revision.obsoleted: on supersede of prior released (written inside service).

Archive strategy:
  Archive flows through PATCH with {active: false}. The router compares the
  current active state before applying the update to select the correct audit
  action string (mirrors syerp/router.py was_active pattern).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.auth.service import write_audit
from app.modules.plum.schemas import (
    PartCreate,
    PartDetailRead,
    PartRead,
    PartUpdate,
    RevisionCreate,
    RevisionRead,
)
from app.modules.plum.service import (
    advance_revision_status,
    create_part,
    create_revision,
    generate_part_number,
    get_part,
    get_part_with_revisions,
    list_parts,
    update_part,
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


class AdvanceStatusPayload(dict):
    """Runtime body type for advance-status endpoint. Defined inline to avoid
    a separate schema file for a single-field body."""


from pydantic import BaseModel


class AdvanceStatusBody(BaseModel):
    """Request body for POST /parts/{part_id}/revisions/{rev_id}/advance."""

    target_status: str


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
    revision = await advance_revision_status(
        db,
        part_id=part_id,
        revision_id=rev_id,
        target_status=body.target_status,
        actor_id=str(current_user.id),
    )
    return revision  # type: ignore[return-value]
