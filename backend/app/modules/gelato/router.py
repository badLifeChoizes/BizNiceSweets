# ABOUTME: GELATO (Warehouse Management) API router — bins CRUD + directed
# ABOUTME: putaway + outbound pick/pack/ship (list/create/patch/archive bins,
# ABOUTME: unbinned stock, target-bin suggestion, execute putaway; pick list,
# ABOUTME: pick/pack/ship a shipment, shipment detail). Thin: each delegates to
# ABOUTME: gelato/service, gates on gelato:read (GET) / gelato:write (mutations),
# ABOUTME: and writes an attributable audit row AFTER the service commit.
"""
GELATO API router — bins & directed putaway (GELATO-01) + pick/pack/ship (GELATO-02).

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
  GET   /gelato/sales-orders/{so_id}/pick-list    — build the pick list for a SO (gelato:read)
  POST  /gelato/shipments/pick                    — pick a SO into staging (gelato:write)
  POST  /gelato/shipments/{shipment_id}/pack      — pack a picked shipment (gelato:write)
  POST  /gelato/shipments/{shipment_id}/ship      — ship a packed shipment (gelato:write)
  GET   /gelato/shipments/{shipment_id}           — read one shipment + lines (gelato:read)

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
  - shipment.picked   on POST /gelato/shipments/pick         (target_type="shipment",
    target_id=str(shipment.id))
  - shipment.packed   on POST /gelato/shipments/{id}/pack    (target_type="shipment",
    target_id=str(shipment_id))
  - shipment.shipped  on POST /gelato/shipments/{id}/ship    (target_type="shipment",
    target_id=str(shipment_id), detail names the posted COGS JE id)
GET routes (bin lists, unbinned stock, suggestion, pick-list, shipment detail) are
read-only and write no audit row.
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
    PackRequest,
    PickListRead,
    PickRequest,
    PutawayRequest,
    PutawayResult,
    ShipmentRead,
    ShipRequest,
    UnbinnedStockRead,
)
from app.modules.gelato.service import (
    archive_bin,
    build_pick_list,
    create_bin,
    execute_pack,
    execute_pick,
    execute_putaway,
    execute_ship,
    get_shipment,
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


# ---------------------------------------------------------------------------
# Shipments — pick/pack/ship (GELATO-02)
# ---------------------------------------------------------------------------


@router.get(
    "/gelato/sales-orders/{so_id}/pick-list",
    response_model=PickListRead,
)
async def build_pick_list_endpoint(
    so_id: str,
    current_user=Depends(require_permission("gelato:read")),
    db: AsyncSession = Depends(get_db),
) -> PickListRead:
    """
    Build the pick list for a sales order — the pick suggestion screen (SC2).

    Per stock line, surfaces ordered/reserved/picked/shipped quantities plus the
    fulfilling location's active bins holding the item (candidate sources) and a
    suggested source bin. Rejects a missing SO (404) or an SO not in
    {confirmed, fulfilling} (422). Read-only: no audit row. Requires gelato:read.
    """
    return await build_pick_list(db, so_id)


@router.post("/gelato/shipments/pick", response_model=ShipmentRead)
async def execute_pick_endpoint(
    data: PickRequest,
    current_user=Depends(require_permission("gelato:write")),
    db: AsyncSession = Depends(get_db),
) -> ShipmentRead:
    """
    Pick a sales order into its staging bin — bin-aware, net-zero (SC2).

    Get-or-creates the SO's open picking shipment for the staging bin, moves each
    pick line from its pick bin into staging via the SYERP hub, stamps qty_picked,
    and advances the SO confirmed → fulfilling on the first pick — all in one
    atomic commit. Requires gelato:write. Writes a shipment.picked audit row after
    the pick commits.
    """
    shipment = await execute_pick(db, data, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="shipment.picked",
        target_type="shipment",
        target_id=str(shipment.id),
        detail=(
            f"Pick: {len(data.lines)} line(s) of SO {data.sales_order_id} into "
            f"staging bin {data.staging_bin_id} (shipment {shipment.id})"
        ),
    )
    return shipment


@router.post("/gelato/shipments/{shipment_id}/pack", response_model=ShipmentRead)
async def execute_pack_endpoint(
    shipment_id: int,
    data: PackRequest,
    current_user=Depends(require_permission("gelato:write")),
    db: AsyncSession = Depends(get_db),
) -> ShipmentRead:
    """
    Pack a picked shipment — advance picking → packed and record the staged qty.

    A pure state + staged-qty record (no ledger/GL movement); optional per-line
    overrides trim the staged qty down. Rejects a missing shipment (404) or a
    non-picking shipment (409). Requires gelato:write. Writes a shipment.packed
    audit row after the pack commits.
    """
    shipment = await execute_pack(db, shipment_id, data, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="shipment.packed",
        target_type="shipment",
        target_id=str(shipment_id),
        detail=f"Pack: shipment {shipment_id} packed ({len(data.overrides)} override(s))",
    )
    return shipment


@router.post("/gelato/shipments/{shipment_id}/ship", response_model=ShipmentRead)
async def execute_ship_endpoint(
    shipment_id: int,
    data: ShipRequest,
    current_user=Depends(require_permission("gelato:write")),
    db: AsyncSession = Depends(get_db),
) -> ShipmentRead:
    """
    Ship a packed shipment — the accounting crux (GELATO-02, SC4; SYERP-13 AC1).

    Issues each line out of the staging bin, relieves the SO reservation, stamps
    qty_shipped, and posts ONE balanced COGS JE — all in one atomic commit.
    Rejects a missing shipment (404), a non-packed shipment (409), an empty or
    zero-value shipment (422). Requires gelato:write. Writes a shipment.shipped
    audit row (naming the posted JE) after the ship commits.
    """
    shipment = await execute_ship(db, shipment_id, str(current_user.id))
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="shipment.shipped",
        target_type="shipment",
        target_id=str(shipment_id),
        detail=(
            f"Ship: shipment {shipment_id} shipped (SO {shipment.sales_order_id}, "
            f"JE {shipment.journal_entry_id})"
        ),
    )
    return shipment


@router.get("/gelato/shipments/{shipment_id}", response_model=ShipmentRead)
async def get_shipment_endpoint(
    shipment_id: int,
    current_user=Depends(require_permission("gelato:read")),
    db: AsyncSession = Depends(get_db),
) -> ShipmentRead:
    """
    Read one shipment with its lines (404 if it does not exist).

    Read-only: no ledger movement, no audit row. Requires gelato:read permission.
    """
    return await get_shipment(db, shipment_id)
