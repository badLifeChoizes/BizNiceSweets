"""
SYERP API router.

Phase 4: Partner CRUD + GL accounts browse endpoints.
Phase 8: Inventory item CRUD endpoints (SYERP inventory & purchasing).

Endpoints (all prefixed with /api/v1/syerp by registry.py mount_all):
  GET    /syerp/partners               — list/search partners (syerp:read)
  POST   /syerp/partners               — create partner (syerp:write)
  GET    /syerp/partners/{partner_id}  — get partner (syerp:read)
  PATCH  /syerp/partners/{partner_id}  — update/archive partner (syerp:write)
  GET    /syerp/inventory/items            — list/search items (syerp:read)
  POST   /syerp/inventory/items            — create item (syerp:write)
  GET    /syerp/inventory/items/{item_id}  — get item (syerp:read)
  PATCH  /syerp/inventory/items/{item_id}  — update/archive item (syerp:write)
  GET    /syerp/inventory/items/{item_id}/onhand        — derived on-hand + value (syerp:read)
  GET    /syerp/inventory/items/{item_id}/transactions  — ledger history (syerp:read)
  POST   /syerp/inventory/items/{item_id}/receipts       — post costed receipt (syerp:write)
  POST   /syerp/inventory/items/{item_id}/adjustments    — post stock adjustment (syerp:write)
  POST   /syerp/inventory/items/{item_id}/transfers       — post stock transfer (syerp:write)
  GET    /syerp/inventory/locations              — list locations (syerp:read)
  POST   /syerp/inventory/locations              — create location (syerp:write)
  GET    /syerp/inventory/locations/{location_id}  — get location (syerp:read)
  PATCH  /syerp/inventory/locations/{location_id}  — update/archive (syerp:write)
  GET    /syerp/purchasing/orders             — list POs (+?vendor_id=) (syerp:read)
  POST   /syerp/purchasing/orders             — create PO draft (syerp:write)
  GET    /syerp/purchasing/orders/{po_id}     — get PO + lines (syerp:read)
  POST   /syerp/purchasing/orders/{po_id}/lines            — add line (syerp:write)
  PATCH  /syerp/purchasing/orders/{po_id}/lines/{line_id}  — update line (syerp:write)
  DELETE /syerp/purchasing/orders/{po_id}/lines/{line_id}  — remove line (syerp:write)
  GET    /syerp/gl/accounts            — list GL accounts (syerp:read)

mount_all() in registry.py adds the /api/v1 prefix — do NOT include it here.
Full paths are therefore /api/v1/syerp/partners, /api/v1/syerp/gl/accounts, etc.

Permission gating (D-09):
  - All write (POST, PATCH) endpoints require syerp:write.
  - All read (GET) endpoints require syerp:read.
  - Unauthenticated requests return 401; wrong permission returns 403.
  - Admin role is wildcard (handled inside require_permission).

Audit logging (D-10, T-04-08):
  - partner.created: on POST /partners success.
  - partner.updated: on PATCH when active does not change to False.
  - partner.archived: on PATCH when patch sets active=False.
  - item.created: on POST /inventory/items success.
  - item.updated: on PATCH when active does not change to False.
  - item.archived: on PATCH when patch sets active=False.
  - location.created: on POST /inventory/locations success.
  - location.updated: on PATCH when active does not change to False.
  - location.archived: on PATCH when patch sets active=False.
  - inventory.receipt: on POST /inventory/items/{id}/receipts success.
  - inventory.adjustment: on POST /inventory/items/{id}/adjustments success.
  - inventory.transfer: on POST /inventory/items/{id}/transfers success.
  - po.created: on POST /purchasing/orders success.
  - po.line_added: on POST /purchasing/orders/{id}/lines success.
  - po.line_updated: on PATCH /purchasing/orders/{id}/lines/{line_id} success.
  - po.line_removed: on DELETE /purchasing/orders/{id}/lines/{line_id} success.

Archive strategy (RESEARCH.md Pattern 4):
  Archive flows through PATCH with {active: false}. The router compares
  the current active state before applying the update to select the correct
  audit action string.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.auth.service import write_audit
from app.modules.syerp.schemas import (
    AdjustmentCreate,
    GLAccountRead,
    InventoryItemCreate,
    InventoryItemRead,
    InventoryItemUpdate,
    ItemOnHandRead,
    PartnerCreate,
    PartnerRead,
    PartnerUpdate,
    POCreate,
    POLineCreate,
    POLineRead,
    POLineUpdate,
    PORead,
    ReceiptCreate,
    StockLocationCreate,
    StockLocationRead,
    StockLocationUpdate,
    TransactionRead,
    TransferCreate,
)
from app.modules.syerp.service import (
    add_line,
    archive_partner,
    create_item,
    create_location,
    create_partner,
    create_po,
    get_item,
    get_item_onhand,
    get_location,
    get_partner,
    get_po,
    list_gl_accounts,
    list_item_transactions,
    list_items,
    list_locations,
    list_partners,
    list_pos,
    post_adjustment,
    post_receipt,
    post_transfer,
    remove_line,
    update_item,
    update_line,
    update_location,
    update_partner,
)

router = APIRouter(prefix="/syerp", tags=["syerp"])


# ---------------------------------------------------------------------------
# Partners
# ---------------------------------------------------------------------------


@router.get("/partners", response_model=list[PartnerRead])
async def list_partners_endpoint(
    role: str | None = None,
    q: str | None = None,
    include_archived: bool = False,
    current_user=Depends(require_permission("syerp:read")),
    db: AsyncSession = Depends(get_db),
) -> list[PartnerRead]:
    """
    List / search partners.

    Query params:
      role: "vendor" | "customer" — filter by role flag.
      q: substring search across name, code, contact_name (server-side, parameterized).
      include_archived: when true, includes active=False partners (default false).

    Requires syerp:read permission.
    """
    partners = await list_partners(db, role=role, q=q, include_archived=include_archived)
    return partners


@router.post("/partners", response_model=PartnerRead, status_code=status.HTTP_201_CREATED)
async def create_partner_endpoint(
    data: PartnerCreate,
    current_user=Depends(require_permission("syerp:write")),
    db: AsyncSession = Depends(get_db),
) -> PartnerRead:
    """
    Create a new partner.

    Auto-generates a unique P-#### code if not supplied in the payload.
    Requires syerp:write permission. Writes a partner.created audit log row.
    """
    partner = await create_partner(db, data)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="partner.created",
        target_type="partner",
        target_id=str(partner.id),
        detail=f"Partner created: {partner.name}",
    )
    return partner


@router.get("/partners/{partner_id}", response_model=PartnerRead)
async def get_partner_endpoint(
    partner_id: str,
    current_user=Depends(require_permission("syerp:read")),
    db: AsyncSession = Depends(get_db),
) -> PartnerRead:
    """
    Get a single partner by id.

    Requires syerp:read permission. Returns 404 if partner does not exist.
    """
    return await get_partner(db, partner_id)


@router.patch("/partners/{partner_id}", response_model=PartnerRead)
async def update_partner_endpoint(
    partner_id: str,
    data: PartnerUpdate,
    current_user=Depends(require_permission("syerp:write")),
    db: AsyncSession = Depends(get_db),
) -> PartnerRead:
    """
    Partially update a partner (PATCH semantics).

    Sending {active: false} archives the partner (D-05 soft-delete).
    Requires syerp:write permission. Writes audit log with correct action:
      - "partner.archived" when active transitions True → False
      - "partner.updated" for all other mutations

    Returns 404 if partner does not exist.
    """
    # Read current state before mutation to detect archive transition
    existing = await get_partner(db, partner_id)
    was_active = existing.active

    partner = await update_partner(db, partner_id, data)

    # Select audit action based on active state transition
    is_archiving = data.active is False and was_active is True
    audit_action = "partner.archived" if is_archiving else "partner.updated"

    await write_audit(
        db,
        actor_id=str(current_user.id),
        action=audit_action,
        target_type="partner",
        target_id=str(partner.id),
        detail=f"Partner {audit_action.split('.')[1]}: {partner.name}",
    )
    return partner


# ---------------------------------------------------------------------------
# Inventory items (Phase 8)
# ---------------------------------------------------------------------------


@router.get("/inventory/items", response_model=list[InventoryItemRead])
async def list_items_endpoint(
    q: str | None = None,
    include_archived: bool = False,
    current_user=Depends(require_permission("syerp:read")),
    db: AsyncSession = Depends(get_db),
) -> list[InventoryItemRead]:
    """
    List / search inventory items.

    Query params:
      q: substring search across code and name (server-side, parameterized).
      include_archived: when true, includes active=False items (default false).

    Requires syerp:read permission.
    """
    return await list_items(db, q=q, include_archived=include_archived)


@router.post(
    "/inventory/items",
    response_model=InventoryItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_item_endpoint(
    data: InventoryItemCreate,
    current_user=Depends(require_permission("syerp:write")),
    db: AsyncSession = Depends(get_db),
) -> InventoryItemRead:
    """
    Create a new inventory item.

    Auto-generates a numeric-safe ITEM-#### code if not supplied in the payload.
    Requires syerp:write permission. Writes an item.created audit log row.
    """
    item = await create_item(db, data)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="item.created",
        target_type="inventory_item",
        target_id=str(item.id),
        detail=f"Inventory item created: {item.code} ({item.name})",
    )
    return item


@router.get("/inventory/items/{item_id}", response_model=InventoryItemRead)
async def get_item_endpoint(
    item_id: str,
    current_user=Depends(require_permission("syerp:read")),
    db: AsyncSession = Depends(get_db),
) -> InventoryItemRead:
    """
    Get a single inventory item by id.

    Requires syerp:read permission. Returns 404 if the item does not exist.
    """
    return await get_item(db, item_id)


@router.patch("/inventory/items/{item_id}", response_model=InventoryItemRead)
async def update_item_endpoint(
    item_id: str,
    data: InventoryItemUpdate,
    current_user=Depends(require_permission("syerp:write")),
    db: AsyncSession = Depends(get_db),
) -> InventoryItemRead:
    """
    Partially update an inventory item (PATCH semantics).

    Sending {active: false} archives the item (soft-delete), dropping it from
    the default list. Requires syerp:write permission. Writes audit log with
    the correct action:
      - "item.archived" when active transitions True → False
      - "item.updated" for all other mutations

    Returns 404 if the item does not exist.
    """
    # Read current state before mutation to detect archive transition
    existing = await get_item(db, item_id)
    was_active = existing.active

    item = await update_item(db, item_id, data)

    is_archiving = data.active is False and was_active is True
    audit_action = "item.archived" if is_archiving else "item.updated"

    await write_audit(
        db,
        actor_id=str(current_user.id),
        action=audit_action,
        target_type="inventory_item",
        target_id=str(item.id),
        detail=f"Inventory item {audit_action.split('.')[1]}: {item.code}",
    )
    return item


@router.get("/inventory/items/{item_id}/onhand", response_model=ItemOnHandRead)
async def get_item_onhand_endpoint(
    item_id: str,
    current_user=Depends(require_permission("syerp:read")),
    db: AsyncSession = Depends(get_db),
) -> ItemOnHandRead:
    """
    Return derived on-hand-by-location + valuation for an inventory item.

    On-hand is a derived aggregate — SUM(InventoryTxn.quantity) grouped by
    location (AC10-3), never a stored quantity column. Value is
    total_quantity * moving_avg_cost (AC10-5). Zero-net locations are omitted.

    Read-only: no audit row. Requires syerp:read. Returns 404 if the item does
    not exist.
    """
    return await get_item_onhand(db, item_id)


@router.get("/inventory/items/{item_id}/transactions", response_model=list[TransactionRead])
async def list_item_transactions_endpoint(
    item_id: str,
    current_user=Depends(require_permission("syerp:read")),
    db: AsyncSession = Depends(get_db),
) -> list[TransactionRead]:
    """
    Return an item's inventory-ledger rows (append-only history, AC10-4).

    Newest-first (created_at DESC). Each row includes its location name via a
    join to StockLocation. Read-only immutable history: no audit row.
    Requires syerp:read. Returns 404 if the item does not exist.
    """
    return await list_item_transactions(db, item_id)


@router.post(
    "/inventory/items/{item_id}/receipts",
    response_model=TransactionRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_receipt_endpoint(
    item_id: str,
    data: ReceiptCreate,
    current_user=Depends(require_permission("syerp:write")),
    db: AsyncSession = Depends(get_db),
) -> TransactionRead:
    """
    Post a costed receipt against an inventory item (AC10-5).

    Appends one immutable `receipt` ledger row (positive quantity, unit_cost set)
    and recomputes the item-level moving-average cost, atomically. `qty` must be
    > 0 and `unit_cost` >= 0 (422 otherwise). Requires syerp:write. Returns 404 if
    the item or location does not exist. Writes an inventory.receipt audit row.
    """
    txn = await post_receipt(
        db,
        item_id=item_id,
        location_id=data.location_id,
        qty=data.qty,
        unit_cost=data.unit_cost,
        actor_id=str(current_user.id),
        source_type=data.source_type,
        source_id=data.source_id,
    )
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="inventory.receipt",
        target_type="inventory_txn",
        target_id=str(txn.id),
        detail=(
            f"Receipt: {data.qty} @ {data.unit_cost} of item {item_id} "
            f"to location {data.location_id}"
        ),
    )
    return txn


@router.post(
    "/inventory/items/{item_id}/adjustments",
    response_model=TransactionRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_adjustment_endpoint(
    item_id: str,
    data: AdjustmentCreate,
    current_user=Depends(require_permission("syerp:write")),
    db: AsyncSession = Depends(get_db),
) -> TransactionRead:
    """
    Post a stock adjustment against an inventory item (AC10-6, D-P8-7).

    Appends one immutable signed `adjustment` ledger row with a required `reason`.
    A negative `qty_delta` covers the manual write-off / "issue" case (the `issue`
    txn_type stays reserved for MOUSSE). Rejects with 422 if the resulting
    location on-hand would go below zero (per-location negative-stock guard) —
    no row is written. The item's moving-average is left untouched (only receipts
    move it, AC10-5). Requires syerp:write. Returns 404 if the item or location
    does not exist. Writes an inventory.adjustment audit row.
    """
    txn = await post_adjustment(
        db,
        item_id=item_id,
        location_id=data.location_id,
        qty_delta=data.qty_delta,
        reason=data.reason,
        actor_id=str(current_user.id),
    )
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="inventory.adjustment",
        target_type="inventory_txn",
        target_id=str(txn.id),
        detail=(
            f"Adjustment: {data.qty_delta} of item {item_id} at location "
            f"{data.location_id} ({data.reason})"
        ),
    )
    return txn


@router.post(
    "/inventory/items/{item_id}/transfers",
    response_model=list[TransactionRead],
    status_code=status.HTTP_201_CREATED,
)
async def post_transfer_endpoint(
    item_id: str,
    data: TransferCreate,
    current_user=Depends(require_permission("syerp:write")),
    db: AsyncSession = Depends(get_db),
) -> list[TransactionRead]:
    """
    Post a stock transfer between two locations (AC10-4,6; D-P8-7).

    Appends TWO paired immutable `transfer` ledger legs sharing one
    transfer_group_id — a `-qty` leg at `from_location_id` and a `+qty` leg at
    `to_location_id`, both valued at the item's current moving-average cost. Total
    item on-hand nets to zero and the moving-average is left untouched (only
    receipts move it, AC10-5). Rejects with 422 if the source and destination are
    the same, `qty` <= 0, or the transfer would over-draw the source location
    (per-location negative-stock guard) — no rows are written. Requires
    syerp:write. Returns 404 if the item or either location does not exist. Writes
    an inventory.transfer audit row.
    """
    txns = await post_transfer(
        db,
        item_id=item_id,
        from_location_id=data.from_location_id,
        to_location_id=data.to_location_id,
        qty=data.qty,
        actor_id=str(current_user.id),
    )
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="inventory.transfer",
        target_type="inventory_txn",
        target_id=str(txns[0].id),
        detail=(
            f"Transfer: {data.qty} of item {item_id} from location "
            f"{data.from_location_id} to location {data.to_location_id}"
        ),
    )
    return txns


# ---------------------------------------------------------------------------
# Stock locations (Phase 8)
# ---------------------------------------------------------------------------


@router.get("/inventory/locations", response_model=list[StockLocationRead])
async def list_locations_endpoint(
    include_archived: bool = False,
    current_user=Depends(require_permission("syerp:read")),
    db: AsyncSession = Depends(get_db),
) -> list[StockLocationRead]:
    """
    List stock locations.

    Query params:
      include_archived: when true, includes active=False locations (default false).

    Requires syerp:read permission.
    """
    return await list_locations(db, include_archived=include_archived)


@router.post(
    "/inventory/locations",
    response_model=StockLocationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_location_endpoint(
    data: StockLocationCreate,
    current_user=Depends(require_permission("syerp:write")),
    db: AsyncSession = Depends(get_db),
) -> StockLocationRead:
    """
    Create a new stock location.

    `name` is the unique key; a duplicate name returns 409 Conflict.
    Requires syerp:write permission. Writes a location.created audit log row.
    """
    location = await create_location(db, data)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="location.created",
        target_type="stock_location",
        target_id=str(location.id),
        detail=f"Stock location created: {location.name}",
    )
    return location


@router.get("/inventory/locations/{location_id}", response_model=StockLocationRead)
async def get_location_endpoint(
    location_id: int,
    current_user=Depends(require_permission("syerp:read")),
    db: AsyncSession = Depends(get_db),
) -> StockLocationRead:
    """
    Get a single stock location by id.

    Requires syerp:read permission. Returns 404 if the location does not exist.
    """
    return await get_location(db, location_id)


@router.patch("/inventory/locations/{location_id}", response_model=StockLocationRead)
async def update_location_endpoint(
    location_id: int,
    data: StockLocationUpdate,
    current_user=Depends(require_permission("syerp:write")),
    db: AsyncSession = Depends(get_db),
) -> StockLocationRead:
    """
    Partially update a stock location (PATCH semantics).

    Sending {active: false} archives the location (soft-delete), dropping it
    from the default list. Requires syerp:write permission. Writes audit log
    with the correct action:
      - "location.archived" when active transitions True → False
      - "location.updated" for all other mutations

    Returns 404 if the location does not exist.
    """
    # Read current state before mutation to detect archive transition
    existing = await get_location(db, location_id)
    was_active = existing.active

    location = await update_location(db, location_id, data)

    is_archiving = data.active is False and was_active is True
    audit_action = "location.archived" if is_archiving else "location.updated"

    await write_audit(
        db,
        actor_id=str(current_user.id),
        action=audit_action,
        target_type="stock_location",
        target_id=str(location.id),
        detail=f"Stock location {audit_action.split('.')[1]}: {location.name}",
    )
    return location


# ---------------------------------------------------------------------------
# Purchase orders (Phase 8, Task 15)
# ---------------------------------------------------------------------------


@router.get("/purchasing/orders", response_model=list[PORead])
async def list_pos_endpoint(
    vendor_id: str | None = None,
    current_user=Depends(require_permission("syerp:read")),
    db: AsyncSession = Depends(get_db),
) -> list[PORead]:
    """
    List purchase orders (newest-first), each with its lines nested.

    Query params:
      vendor_id: when supplied, restricts the list to POs for that vendor.

    Requires syerp:read permission.
    """
    return await list_pos(db, vendor_id=vendor_id)


@router.post(
    "/purchasing/orders",
    response_model=PORead,
    status_code=status.HTTP_201_CREATED,
)
async def create_po_endpoint(
    data: POCreate,
    current_user=Depends(require_permission("syerp:write")),
    db: AsyncSession = Depends(get_db),
) -> PORead:
    """
    Create a new purchase order (Draft, empty of lines).

    Auto-generates a numeric-safe PO-#### number. `vendor_id` must reference an
    existing Partner with is_vendor=True (422 otherwise, AC11-3). Requires
    syerp:write permission. Writes a po.created audit log row.
    """
    po = await create_po(db, data)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="po.created",
        target_type="purchase_order",
        target_id=str(po.id),
        detail=f"Purchase order created: {po.po_number} (vendor {po.vendor_id})",
    )
    return po


@router.get("/purchasing/orders/{po_id}", response_model=PORead)
async def get_po_endpoint(
    po_id: str,
    current_user=Depends(require_permission("syerp:read")),
    db: AsyncSession = Depends(get_db),
) -> PORead:
    """
    Get a single purchase order (header + nested lines) by id.

    Requires syerp:read permission. Returns 404 if the PO does not exist.
    """
    return await get_po(db, po_id)


@router.post(
    "/purchasing/orders/{po_id}/lines",
    response_model=POLineRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_po_line_endpoint(
    po_id: str,
    data: POLineCreate,
    current_user=Depends(require_permission("syerp:write")),
    db: AsyncSession = Depends(get_db),
) -> POLineRead:
    """
    Append a line to a purchase order (Draft-only, AC11-1).

    line_no is auto-assigned sequentially. Rejects with 422 if the PO is not in
    Draft, and with 404 if the PO or the referenced item does not exist. Requires
    syerp:write permission. Writes a po.line_added audit log row.
    """
    line = await add_line(db, po_id, data)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="po.line_added",
        target_type="purchase_order_line",
        target_id=str(line.id),
        detail=(
            f"PO {po_id} line {line.line_no} added: "
            f"{line.qty_ordered} @ {line.unit_cost} of item {line.item_id}"
        ),
    )
    return line


@router.patch(
    "/purchasing/orders/{po_id}/lines/{line_id}",
    response_model=POLineRead,
)
async def update_po_line_endpoint(
    po_id: str,
    line_id: str,
    data: POLineUpdate,
    current_user=Depends(require_permission("syerp:write")),
    db: AsyncSession = Depends(get_db),
) -> POLineRead:
    """
    Partially update a PO line (PATCH semantics, Draft-only, AC11-1).

    Only provided fields are applied. Rejects with 422 if the PO is not in Draft,
    and with 404 if the PO, the line, or a reassigned item does not exist.
    Requires syerp:write permission. Writes a po.line_updated audit log row.
    """
    line = await update_line(db, po_id, line_id, data)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="po.line_updated",
        target_type="purchase_order_line",
        target_id=str(line.id),
        detail=f"PO {po_id} line {line.line_no} updated",
    )
    return line


@router.delete(
    "/purchasing/orders/{po_id}/lines/{line_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_po_line_endpoint(
    po_id: str,
    line_id: str,
    current_user=Depends(require_permission("syerp:write")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Remove a line from a purchase order (Draft-only, AC11-1).

    Rejects with 422 if the PO is not in Draft, and with 404 if the PO or line
    does not exist. Requires syerp:write permission. Writes a po.line_removed
    audit log row (with the line_id from the path). Returns 204 No Content.
    """
    await remove_line(db, po_id, line_id)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="po.line_removed",
        target_type="purchase_order_line",
        target_id=str(line_id),
        detail=f"PO {po_id} line {line_id} removed",
    )


# ---------------------------------------------------------------------------
# GL Accounts (read-only, D-11)
# ---------------------------------------------------------------------------


@router.get("/gl/accounts", response_model=list[GLAccountRead])
async def list_gl_accounts_endpoint(
    current_user=Depends(require_permission("syerp:read")),
    db: AsyncSession = Depends(get_db),
) -> list[GLAccountRead]:
    """
    Return all GL accounts ordered by code.

    Read-only in Phase 4 (D-11 scope guard). Seeded at startup.
    Requires syerp:read permission. Unauthenticated → 401. Wrong perm → 403.
    """
    return await list_gl_accounts(db)
