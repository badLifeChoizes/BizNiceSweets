# ABOUTME: GELATO (Warehouse Management) Pydantic request/response schemas —
# ABOUTME: bin create/update/read, per-bin on-hand, the putaway request/result
# ABOUTME: (its two inventory-ledger legs, resulting bin on-hand, location total),
# ABOUTME: the unbinned-stock read that drives the putaway suggestion screen, and
# ABOUTME: the outbound pick/pack/ship request+read schemas and pick-list read.
# ABOUTME: Pure Pydantic (never imports the ORM); Read models fill from ORM via
# ABOUTME: from_attributes, service-derived figures are plain Decimal fields.
"""
GELATO Pydantic schemas (request/response models) — GELATO-01.

Separation (mirrors mousse/schemas.py):
  - Input schemas (Create/Update/Request): no from_attributes — validate incoming
    JSON. Update schemas are all-optional PATCH payloads.
  - Response schemas (Read/Result): from_attributes=True where they serialize an
    ORM instance; service-CONSTRUCTED reads carrying derived figures the service
    computes (BinOnHandRead.quantity, UnbinnedStockRead.unbinned_qty,
    PutawayResult totals) expose those as plain Decimal fields the service fills.

All quantity fields are fixed-point `Decimal` (never float — D-11), matching the
Numeric(18,6) columns in syerp/models.py. Positive-quantity guards (putaway
`qty` > 0) are enforced at the boundary with `Field(gt=0)`.

Putaway moves stock between bins (or out of the unbinned pool) inside a single
SYERP stock location; it posts two mirrored inventory-ledger legs (out of the
source, into the destination) — surfaced here as TransactionRead, reused from
the SYERP hub so GELATO does not redefine the canonical ledger-row shape.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.syerp.schemas import TransactionRead

# ---------------------------------------------------------------------------
# Bin create / update / read (GELATO-01)
# ---------------------------------------------------------------------------


class BinCreate(BaseModel):
    """
    Bin creation payload (POST /gelato/bins).

    `location_id` is the SYERP stock location this bin subdivides (required) and
    `code` is the bin's short label, unique within that location
    (uq_gelato_bin_location_code). `description` is an optional free-text note.
    `active` and `id`/`created_at` are server-owned and so absent here.
    """

    location_id: int
    code: str = Field(..., min_length=1, max_length=50)
    description: str | None = None


class BinUpdate(BaseModel):
    """
    Bin PATCH payload (PATCH /gelato/bins/{id}).

    All fields optional — only the supplied fields are changed. `active=False`
    toggles a bin out of putaway rotation without deleting it. `location_id` and
    `code` are immutable identity and so are not settable here.
    """

    description: str | None = None
    active: bool | None = None


class BinRead(BaseModel):
    """
    Bin returned to API callers, serialized from a Bin ORM instance via
    from_attributes=True.

    `active` toggles the bin in/out of putaway rotation; `description` is NULL
    when unset. `created_at` is the bin's creation timestamp.
    """

    id: int
    location_id: int
    code: str
    description: str | None = None
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BinOnHandRead(BaseModel):
    """
    Per-bin on-hand quantity for an item — a service-CONSTRUCTED read.

    Reports the resolved on-hand `quantity` for one `bin_id` (labelled `code`)
    as the SUM of that bin's inventory-ledger legs. `quantity` is a fixed-point
    Decimal (never float — D-11).
    """

    bin_id: int
    code: str
    quantity: Decimal


# ---------------------------------------------------------------------------
# Putaway request / result (GELATO-01)
# ---------------------------------------------------------------------------


class PutawayRequest(BaseModel):
    """
    Putaway payload (POST /gelato/putaway) — direct `qty` of item into a bin.

    Moves `qty` (> 0) of `item_id` inside stock location `location_id` from
    `from_bin_id` into `to_bin_id`. `from_bin_id` is optional: None means the
    move draws from the location's *unbinned* pool (stock on-hand at the location
    not yet assigned to any bin) rather than from another bin. `qty` is a
    fixed-point Decimal (never float — D-11) and must be > 0 (a zero/negative
    putaway is meaningless), enforced here with Field(gt=0).
    """

    item_id: str = Field(..., max_length=36)
    location_id: int
    to_bin_id: int
    qty: Decimal = Field(..., gt=0)
    from_bin_id: int | None = None


class PutawayResult(BaseModel):
    """
    Result of a putaway posting returned to API callers.

    Reports the two mirrored inventory-ledger legs it booked — `out_leg` (off
    the source bin / unbinned pool) and `in_leg` (into the destination bin) —
    plus the destination bin's resulting on-hand (`bin_on_hand`) and the location
    total (`location_total`), which putaway leaves unchanged since stock only
    moves within the location. Quantities are fixed-point Decimals (never
    float — D-11).
    """

    out_leg: TransactionRead
    in_leg: TransactionRead
    bin_on_hand: Decimal
    location_total: Decimal


# ---------------------------------------------------------------------------
# Unbinned stock read — putaway suggestion (GELATO-01)
# ---------------------------------------------------------------------------


class UnbinnedStockRead(BaseModel):
    """
    Unbinned-stock row driving the putaway screen — a service-CONSTRUCTED read.

    For an `item_id` at `location_id`, `unbinned_qty` is the on-hand not yet
    assigned to any bin (the location total minus the SUM of its bin balances),
    i.e. the quantity awaiting putaway. `suggested_bin_id` is the service's
    recommended destination bin (NULL when it has none to suggest).
    `unbinned_qty` is a fixed-point Decimal (never float — D-11).
    """

    item_id: str
    location_id: int
    unbinned_qty: Decimal
    suggested_bin_id: int | None = None


# ---------------------------------------------------------------------------
# Shipment pick / pack / ship (GELATO-02)
# ---------------------------------------------------------------------------


class PickLineRequest(BaseModel):
    """
    One line of a pick payload — pick `qty` (> 0) of a sales-order line from a bin.

    `sales_order_line_id` identifies the CRUMB sales-order line being fulfilled,
    `from_bin_id` is the GELATO bin the stock is pulled from, and `qty` is the
    quantity picked from that bin (a line may need several PickLineRequests when
    its stock spans multiple bins). `qty` is a fixed-point Decimal (never float —
    D-11) and must be > 0.
    """

    sales_order_line_id: str = Field(..., max_length=36)
    from_bin_id: int
    qty: Decimal = Field(..., gt=0)


class PickRequest(BaseModel):
    """
    Pick payload (POST /gelato/shipments/pick) — pick a sales order into staging.

    Picks the `lines` of sales order `sales_order_id`, moving each line's stock
    out of its `from_bin_id` and into the `staging_bin_id` (the outbound staging
    bin the whole shipment is assembled in). `lines` must be non-empty.
    """

    sales_order_id: str = Field(..., max_length=36)
    staging_bin_id: int
    lines: list[PickLineRequest] = Field(..., min_length=1)


class PackLineOverride(BaseModel):
    """
    A per-line staged-qty override for packing — set the packed `qty` of one
    already-picked shipment line to a value other than the picked quantity.

    `shipment_line_id` is the shipment line being adjusted and `qty` (> 0) is the
    quantity to pack for it. `qty` is a fixed-point Decimal (never float — D-11).
    """

    shipment_line_id: int
    qty: Decimal = Field(..., gt=0)


class PackRequest(BaseModel):
    """
    Pack payload (POST /gelato/shipments/{id}/pack) — confirm the staged shipment.

    `overrides` optionally adjusts individual line quantities away from what was
    picked; an empty list (the default) packs every picked line at its picked
    quantity as-is.
    """

    overrides: list[PackLineOverride] = Field(default_factory=list)


class ShipRequest(BaseModel):
    """
    Ship payload (POST /gelato/shipments/{id}/ship) — ship the packed shipment.

    The shipment ships exactly as staged/packed, so the body carries no fields;
    `shipment_id` comes from the path. Defined as an empty model to keep a
    consistent JSON POST body across the pick/pack/ship endpoints.
    """


class ShipmentLineRead(BaseModel):
    """
    One shipment line returned to API callers, serialized from a ShipmentLine ORM
    instance via from_attributes=True.

    `sales_order_line_id` is the CRUMB line fulfilled, `item_id` the item shipped,
    `from_bin_id` the bin it was picked from, and `qty` the shipped quantity (a
    fixed-point Decimal — D-11). `inventory_txn_id` is the inventory-ledger leg
    booked when the line shipped, NULL until the shipment is shipped.
    """

    id: int
    sales_order_line_id: str
    item_id: str
    from_bin_id: int
    qty: Decimal
    inventory_txn_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ShipmentRead(BaseModel):
    """
    Shipment returned to API callers, serialized from a Shipment ORM instance via
    from_attributes=True.

    `sales_order_id` is the CRUMB order being fulfilled, `location_id` the stock
    location it ships from, and `staging_bin_id` the outbound staging bin it is
    assembled in. `status` is the shipment's FSM state (picked → packed →
    shipped). `journal_entry_id` is the SYERP GL entry posted at ship time, NULL
    until then. `lines` are its shipment lines; `created_at` is when it was
    created.
    """

    id: int
    sales_order_id: str
    location_id: int
    staging_bin_id: int
    status: str
    journal_entry_id: str | None = None
    lines: list[ShipmentLineRead]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Pick-list read — pick suggestion screen (GELATO-02)
# ---------------------------------------------------------------------------


class PickListBinRead(BaseModel):
    """
    One candidate source bin for a pick-list line — a service-CONSTRUCTED read.

    Reports a `bin_id` (labelled `code`) holding the line's item and its current
    `on_hand` in that bin (a fixed-point Decimal — D-11), so the picker can choose
    where to pull from.
    """

    bin_id: int
    code: str
    on_hand: Decimal


class PickListLineRead(BaseModel):
    """
    One pick-list line driving the pick screen — a service-CONSTRUCTED read.

    For sales-order line `sales_order_line_id` (item `item_id`, `description`),
    reports the ordered/reserved/picked/shipped quantities and the service's
    `suggested_from_bin_id` (NULL when it has none to suggest), plus every
    candidate `available_bins` holding the item. All quantities are fixed-point
    Decimals (never float — D-11).
    """

    sales_order_line_id: str
    item_id: str
    description: str
    qty_ordered: Decimal
    qty_reserved: Decimal
    qty_picked: Decimal
    qty_shipped: Decimal
    suggested_from_bin_id: int | None = None
    available_bins: list[PickListBinRead]


class PickListRead(BaseModel):
    """
    Pick list for a sales order — a service-CONSTRUCTED read.

    `sales_order_id` is the order being picked and `lines` are its per-line pick
    suggestions (quantities and candidate source bins).
    """

    sales_order_id: str
    lines: list[PickListLineRead]
