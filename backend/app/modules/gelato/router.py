# ABOUTME: GELATO (Warehouse Management) API router — bins CRUD + directed
# ABOUTME: putaway (list/create/patch/archive bins, unbinned stock, target-bin
# ABOUTME: suggestion, execute putaway). Thin: each delegates to gelato/service,
# ABOUTME: gates on gelato:read (GET) / gelato:write (mutations), and writes an
# ABOUTME: attributable audit row AFTER the service commit (write_audit self-commits).
"""
GELATO API router — bins & directed putaway (GELATO-01).

Endpoints (mount_all in registry.py adds the /api/v1 prefix — full paths are
/api/v1/gelato/bins, etc.; this router carries no prefix and spells the
/gelato/... path on each route):

  GET   /gelato/locations/{location_id}/bins      — list bins in a location (gelato:read)
  POST  /gelato/bins                              — create a bin (gelato:write) → 201
  PATCH /gelato/bins/{bin_id}                     — patch description/active (gelato:write)
  POST  /gelato/bins/{bin_id}/archive             — soft-archive a bin (gelato:write)
  GET   /gelato/locations/{location_id}/unbinned  — list unbinned stock awaiting putaway (gelato:read)
  GET   /gelato/putaway/suggestion                — suggested target bin (gelato:read)
  POST  /gelato/putaway                           — execute a putaway (gelato:write)

Permission gating (D-P10-6, mirrors the MOUSSE router):
  - Every mutation (POST/PATCH) requires gelato:write; every read (GET) requires
    gelato:read. Unauthenticated → 401, wrong permission → 403 (admin is
    wildcard, handled inside require_permission).

Audit logging (D-10): every mutation writes one AuditLog row AFTER the service's
own commit (write_audit self-commits, mirroring the SYERP/MOUSSE router order):
  - bin.created       on POST /gelato/bins              (target_type="bin", target_id=bin.id)
  - bin.updated       on PATCH /gelato/bins/{id}        (target_type="bin", target_id=bin.id)
  - bin.archived      on POST /gelato/bins/{id}/archive (target_type="bin", target_id=bin.id)
  - inventory.putaway on POST /gelato/putaway           (target_type="inventory_txn",
    target_id=result.out_leg.id — PutawayResult exposes no transfer-group id, so the
    OUT leg's txn id identifies the paired posting).
GET routes are read-only and write no audit row.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.auth.service import write_audit
from app.modules.gelato.schemas import (
    BinCreate,
    BinRead,
    BinUpdate,
    PutawayRequest,
    PutawayResult,
    UnbinnedStockRead,
)
from app.modules.gelato.service import (
    archive_bin,
    create_bin,
    execute_putaway,
    list_bins,
    list_unbinned_stock,
    suggest_target_bin,
    update_bin,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Bins — reads (GELATO-01)
# ---------------------------------------------------------------------------


@router.get("/gelato/locations/{location_id}/bins", response_model=list[BinRead])
async def list_bins_endpoint(
    location_id: int,
    include_archived: bool = False,
    current_user=Depends(require_permission("gelato:read")),
    db: AsyncSession = Depends(get_db),
) -> list[BinRead]:
    """
    List the bins in one SYERP stock location, ordered by code.

    Archived (active=False) bins are excluded unless `include_archived=true` —
    downstream putaway pickers must not surface archived bins. Read-only: no audit
    row. Requires gelato:read permission.
    """
    return await list_bins(db, location_id, include_archived=include_archived)


# ---------------------------------------------------------------------------
# Bins — create + mutations (GELATO-01)
# ---------------------------------------------------------------------------


@router.post(
    "/gelato/bins",
    response_model=BinRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_bin_endpoint(
    data: BinCreate,
    current_user=Depends(require_permission("gelato:write")),
    db: AsyncSession = Depends(get_db),
) -> BinRead:
    """
    Create a storage bin inside a SYERP stock location.

    Rejects a missing location (404) and a duplicate (location, code) pair (422)
    before any write, then persists an active bin. Requires gelato:write. Writes a
    bin.created audit row after the create commits.
    """
    bin_ = await create_bin(db, data)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="bin.created",
        target_type="bin",
        target_id=str(bin_.id),
        detail=f"Bin created: {bin_.code} in location {bin_.location_id}",
    )
    return bin_


@router.patch("/gelato/bins/{bin_id}", response_model=BinRead)
async def update_bin_endpoint(
    bin_id: int,
    data: BinUpdate,
    current_user=Depends(require_permission("gelato:write")),
    db: AsyncSession = Depends(get_db),
) -> BinRead:
    """
    Apply a partial update to a bin (PATCH description and/or active).

    Only the supplied fields are written; location_id and code are immutable
    identity. Setting active=False here is the same soft-archive as the archive
    route. Rejects a missing bin (404). Requires gelato:write. Writes a bin.updated
    audit row after the update commits.
    """
    bin_ = await update_bin(db, bin_id, data)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="bin.updated",
        target_type="bin",
        target_id=str(bin_.id),
        detail=f"Bin updated: {bin_.code} (active={bin_.active})",
    )
    return bin_


@router.post("/gelato/bins/{bin_id}/archive", response_model=BinRead)
async def archive_bin_endpoint(
    bin_id: int,
    current_user=Depends(require_permission("gelato:write")),
    db: AsyncSession = Depends(get_db),
) -> BinRead:
    """
    Soft-archive a bin (active=False) — toggle it out of putaway rotation without
    deleting it. Rejects a missing bin (404). Requires gelato:write. Writes a
    bin.archived audit row after the archive commits.
    """
    bin_ = await archive_bin(db, bin_id)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="bin.archived",
        target_type="bin",
        target_id=str(bin_.id),
        detail=f"Bin archived: {bin_.code} in location {bin_.location_id}",
    )
    return bin_


# ---------------------------------------------------------------------------
# Putaway — reads (GELATO-01)
# ---------------------------------------------------------------------------


@router.get("/gelato/locations/{location_id}/unbinned", response_model=list[UnbinnedStockRead])
async def list_unbinned_stock_endpoint(
    location_id: int,
    current_user=Depends(require_permission("gelato:read")),
    db: AsyncSession = Depends(get_db),
) -> list[UnbinnedStockRead]:
    """
    List every item with unbinned on-hand (> 0) at a location, awaiting putaway.

    Each row carries its suggested destination bin (D-P12a-10 heuristic). Read-only:
    no audit row. Requires gelato:read permission.
    """
    return await list_unbinned_stock(db, location_id)


@router.get("/gelato/putaway/suggestion")
async def suggest_target_bin_endpoint(
    item_id: str,
    location_id: int,
    current_user=Depends(require_permission("gelato:read")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Suggest a destination bin for an item at a location (D-P12a-10 heuristic).

    Returns {"suggested_bin_id": <int|null>} — an active bin already holding the
    item (lowest code), else the first active bin, else null. Read-only: no audit
    row. Requires gelato:read permission.
    """
    suggested = await suggest_target_bin(db, item_id, location_id)
    return {"suggested_bin_id": suggested}


# ---------------------------------------------------------------------------
# Putaway — execute (GELATO-01)
# ---------------------------------------------------------------------------


@router.post("/gelato/putaway", response_model=PutawayResult)
async def execute_putaway_endpoint(
    data: PutawayRequest,
    current_user=Depends(require_permission("gelato:write")),
    db: AsyncSession = Depends(get_db),
) -> PutawayResult:
    """
    Execute a putaway: move qty of an item into a bin inside one stock location.

    Validates the source/destination bins belong to the location (404 missing, 422
    wrong location / archived destination) then delegates the two mirrored ledger
    legs to the SYERP hub, whose over-draw / self-move (422) and item / location
    (404) guards propagate. Requires gelato:write. Writes ONE inventory.putaway
    audit row after the posting commits, keyed to the OUT leg's txn id (the result
    exposes no transfer-group id).
    """
    result = await execute_putaway(db, data, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="inventory.putaway",
        target_type="inventory_txn",
        target_id=result.out_leg.id,
        detail=(
            f"Putaway: {data.qty} of item {data.item_id} into bin {data.to_bin_id} "
            f"(location {data.location_id}, from bin {data.from_bin_id})"
        ),
    )
    return result
