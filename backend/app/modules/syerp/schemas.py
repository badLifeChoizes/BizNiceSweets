"""
SYERP Pydantic schemas (request/response models).

Phase 4: Added PartnerCreate, PartnerRead, PartnerUpdate, GLAccountRead.

Separation:
  - Input schemas (Create/Update): no from_attributes — validate incoming JSON.
  - Response schemas (Read): from_attributes=True — serialize from ORM instances.

All string fields carry max_length matching their syerp/models.py column length
(V5 input validation, prevents silent truncation on the DB side).

The at-least-one-role model_validator on PartnerCreate and PartnerUpdate enforces
that a partner cannot exist with neither is_vendor nor is_customer (RESEARCH.md
Pitfall 8 — an "orphan" partner has no useful meaning in the domain).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Partner schemas
# ---------------------------------------------------------------------------


class PartnerCreate(BaseModel):
    """
    Partner creation payload (POST /syerp/partners).

    `code` is optional — the server auto-generates a P-#### series code if
    not supplied (D-04). At least one of is_vendor / is_customer must be True.
    """

    # Identity
    name: str = Field(..., max_length=255)
    code: Optional[str] = Field(None, max_length=20)
    is_vendor: bool = False
    is_customer: bool = False

    # Address block (D-03) — max_length matches models.py column definitions
    addr_line1: Optional[str] = Field(None, max_length=255)
    addr_line2: Optional[str] = Field(None, max_length=255)
    addr_city: Optional[str] = Field(None, max_length=100)
    addr_state: Optional[str] = Field(None, max_length=100)
    addr_postal: Optional[str] = Field(None, max_length=20)
    addr_country: Optional[str] = Field(None, max_length=2)

    # Contact block (D-03)
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=50)

    # Commerce (D-03)
    payment_terms: Optional[str] = Field(None, max_length=50)
    tax_id: Optional[str] = Field(None, max_length=50)
    currency: Optional[str] = Field(None, max_length=3)
    country_of_origin: Optional[str] = Field(None, max_length=2)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def require_at_least_one_role(self) -> "PartnerCreate":
        """Reject partners with no role flag set (Pitfall 8)."""
        if not self.is_vendor and not self.is_customer:
            raise ValueError(
                "A partner must have at least one role: "
                "set is_vendor=True or is_customer=True."
            )
        return self


class PartnerUpdate(BaseModel):
    """
    Partner update payload (PATCH /syerp/partners/{id}).

    All fields Optional — PATCH semantics. Only provided (non-None) fields
    are applied by the service layer. `active=False` triggers archive
    (D-05 soft-delete). Role flag updates validate the at-least-one-role
    rule only when both flags are explicitly provided as False.
    """

    name: Optional[str] = Field(None, max_length=255)
    code: Optional[str] = Field(None, max_length=20)
    is_vendor: Optional[bool] = None
    is_customer: Optional[bool] = None
    active: Optional[bool] = None

    # Address block
    addr_line1: Optional[str] = Field(None, max_length=255)
    addr_line2: Optional[str] = Field(None, max_length=255)
    addr_city: Optional[str] = Field(None, max_length=100)
    addr_state: Optional[str] = Field(None, max_length=100)
    addr_postal: Optional[str] = Field(None, max_length=20)
    addr_country: Optional[str] = Field(None, max_length=2)

    # Contact block
    contact_name: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=50)

    # Commerce
    payment_terms: Optional[str] = Field(None, max_length=50)
    tax_id: Optional[str] = Field(None, max_length=50)
    currency: Optional[str] = Field(None, max_length=3)
    country_of_origin: Optional[str] = Field(None, max_length=2)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_role_flags(self) -> "PartnerUpdate":
        """
        Reject a PATCH that would leave the partner with no roles.

        Only triggered when BOTH role flags are explicitly provided as False.
        A partial update (e.g. only is_vendor=False) is allowed — the existing
        DB record may still have is_customer=True.
        """
        if self.is_vendor is False and self.is_customer is False:
            raise ValueError(
                "A partner must retain at least one role: "
                "is_vendor and is_customer cannot both be False."
            )
        return self


class PartnerRead(BaseModel):
    """
    Partner data returned to API callers.

    Serialized from a Partner ORM instance via from_attributes=True.
    Includes all D-03 field groups plus timestamps.
    """

    id: str
    code: str
    name: str
    is_vendor: bool
    is_customer: bool
    active: bool

    # Address
    addr_line1: Optional[str] = None
    addr_line2: Optional[str] = None
    addr_city: Optional[str] = None
    addr_state: Optional[str] = None
    addr_postal: Optional[str] = None
    addr_country: Optional[str] = None

    # Contact
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

    # Commerce
    payment_terms: Optional[str] = None
    tax_id: Optional[str] = None
    currency: Optional[str] = None
    country_of_origin: Optional[str] = None
    notes: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Inventory item schemas (Phase 8)
# ---------------------------------------------------------------------------


class InventoryItemCreate(BaseModel):
    """
    Inventory item creation payload (POST /syerp/inventory/items).

    `code` is optional — the server auto-generates a numeric-safe ITEM-####
    series code if not supplied (Decision 2). `plum_part_id` is optional: an
    item may be a pure SYERP stock item unlinked to any PLUM part (D-P8-2).

    `moving_avg_cost` is intentionally absent — a new item starts at the model
    default of 0 and is only ever recomputed by costed receipts (Task 5),
    never set directly through the item API (D-11).
    """

    name: str = Field(..., max_length=255)
    code: Optional[str] = Field(None, max_length=20)
    unit_of_measure: str = Field(..., max_length=50)
    plum_part_id: Optional[str] = Field(None, max_length=36)


class InventoryItemUpdate(BaseModel):
    """
    Inventory item update payload (PATCH /syerp/inventory/items/{id}).

    All fields Optional — PATCH semantics. Only provided (non-None) fields are
    applied. `active=False` archives the item (soft-delete), dropping it from
    the default list. `moving_avg_cost` is deliberately not updatable here —
    it is owned by the receipt costing path (Task 5), not the item API (D-11).
    """

    name: Optional[str] = Field(None, max_length=255)
    code: Optional[str] = Field(None, max_length=20)
    unit_of_measure: Optional[str] = Field(None, max_length=50)
    plum_part_id: Optional[str] = Field(None, max_length=36)
    active: Optional[bool] = None


class InventoryItemRead(BaseModel):
    """
    Inventory item data returned to API callers.

    Serialized from an InventoryItem ORM instance via from_attributes=True.
    `moving_avg_cost` is a fixed-point Decimal (Numeric(18,6)) — never float.
    """

    id: str
    code: str
    name: str
    unit_of_measure: str
    plum_part_id: Optional[str] = None
    moving_avg_cost: Decimal
    active: bool

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Stock location schemas (Phase 8)
# ---------------------------------------------------------------------------


class StockLocationCreate(BaseModel):
    """
    Stock location creation payload (POST /syerp/inventory/locations).

    `name` is the unique key (there is no generated code — StockLocation has an
    Integer autoincrement PK). A fresh deploy already contains a seeded "Main"
    location (D-P8-14), so this endpoint is for adding further locations.
    """

    name: str = Field(..., max_length=100)


class StockLocationUpdate(BaseModel):
    """
    Stock location update payload (PATCH /syerp/inventory/locations/{id}).

    All fields Optional — PATCH semantics. Only provided (non-None) fields are
    applied. `active=False` archives the location (soft-delete), dropping it
    from the default list.
    """

    name: Optional[str] = Field(None, max_length=100)
    active: Optional[bool] = None


class StockLocationRead(BaseModel):
    """
    Stock location data returned to API callers.

    Serialized from a StockLocation ORM instance via from_attributes=True.
    """

    id: int
    name: str
    active: bool

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# On-hand & valuation schemas (Phase 8, Task 4)
# ---------------------------------------------------------------------------


class OnHandByLocation(BaseModel):
    """
    One row of derived on-hand stock for an item at a single location.

    `quantity` is the signed SUM(InventoryTxn.quantity) for the item at this
    location (AC10-3) — a derived aggregate, never a stored column. It is a
    fixed-point Decimal (Numeric(18,6)), never float.
    """

    location_id: int
    location_name: str
    quantity: Decimal


class ItemOnHandRead(BaseModel):
    """
    Derived on-hand + valuation view for a single inventory item.

    `locations` lists only locations with a nonzero net on-hand (zero-net
    locations are omitted — see get_item_onhand docstring). `total_quantity`
    is the grand total across those locations; `onhand_value` is
    `total_quantity * moving_avg_cost` (AC10-5), all computed in Decimal.
    """

    item_id: str
    moving_avg_cost: Decimal
    locations: list[OnHandByLocation]
    total_quantity: Decimal
    onhand_value: Decimal


# ---------------------------------------------------------------------------
# Inventory transaction (ledger) schema (Phase 8, Task 11 read half)
# ---------------------------------------------------------------------------


class ReceiptCreate(BaseModel):
    """
    Costed-receipt posting payload (POST /syerp/inventory/items/{id}/receipts).

    A receipt adds stock at a known unit cost and drives the item's
    moving-average recompute (AC10-5, Task 5). Constraints mirror the service
    guard so bad input is rejected at the boundary with a 422:
      - `qty` > 0 (a receipt is stock IN; zero/negative is not a receipt).
      - `unit_cost` >= 0 (a receipt may be free, but never negative-cost).

    `source_type` / `source_id` are the optional soft polymorphic link back to
    the originating document (e.g. a PO receipt); no FK, so the ledger stays
    valid even if the source module is disabled.
    """

    location_id: int
    qty: Decimal = Field(..., gt=0)
    unit_cost: Decimal = Field(..., ge=0)
    source_type: Optional[str] = Field(None, max_length=50)
    source_id: Optional[str] = Field(None, max_length=36)


class AdjustmentCreate(BaseModel):
    """
    Stock-adjustment posting payload (POST /syerp/inventory/items/{id}/adjustments).

    An adjustment corrects the on-hand quantity of an item at one location by a
    SIGNED `qty_delta` (Task 6). A negative delta covers the manual "issue" /
    write-off case in v2.0 — the `issue` txn_type stays reserved for MOUSSE.

    `reason` is REQUIRED and non-empty (min_length=1): every adjustment must
    record why stock moved, for audit/traceability (AC10-6). Adjustments do NOT
    carry a unit_cost and never move the item's moving-average — only receipts
    do (AC10-5).

    The negative-stock guard (resulting LOCATION on-hand would be < 0) is
    enforced in the service, not here, because it depends on live DB state.
    """

    location_id: int
    qty_delta: Decimal
    reason: str = Field(..., min_length=1, max_length=255)


class TransferCreate(BaseModel):
    """
    Stock-transfer posting payload (POST /syerp/inventory/items/{id}/transfers).

    A transfer moves `qty` of an item FROM one location TO another (Task 7). It
    posts TWO paired `transfer` ledger legs sharing a transfer_group_id — a `-qty`
    leg at `from_location_id` and a `+qty` leg at `to_location_id` — so total item
    on-hand nets to zero and the moving-average is left untouched (only receipts
    move it, AC10-5).

    `qty` must be > 0 (a transfer is a positive movement between locations; the
    sign is applied per-leg by the service). The remaining guards depend on live
    DB state and are enforced in the service:
      - `from_location_id == to_location_id` is rejected (422) — a self-transfer
        is a no-op.
      - source-location on-hand < `qty` (over-draw) is rejected (422, AC10-6) so
        a transfer can never drive the source location negative.
    """

    from_location_id: int
    to_location_id: int
    qty: Decimal = Field(..., gt=0)


class TransactionRead(BaseModel):
    """
    One immutable inventory-ledger row returned to API callers (AC10-4).

    Serialized from an InventoryTxn joined to its StockLocation for the
    human-readable `location_name`. Quantities/costs are fixed-point Decimals,
    never float. This is read-only history — the ledger is append-only.
    """

    id: str
    item_id: str
    location_id: int
    location_name: str
    txn_type: str
    quantity: Decimal
    unit_cost: Optional[Decimal] = None
    reason: Optional[str] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Purchase order schemas (Phase 8, Task 15)
# ---------------------------------------------------------------------------
#
# A PO header carries its lines nested (PORead.lines) so a single GET returns the
# whole order — the frontend never has to stitch a header to a separate line list.
# Lines are created/edited/removed through the dedicated /orders/{id}/lines
# endpoints (only while the PO is in Draft), not through POCreate — a new PO is
# born empty and lines are added afterwards, mirroring the two-step UI flow.


class POLineCreate(BaseModel):
    """
    Purchase-order line creation payload (POST /syerp/purchasing/orders/{id}/lines).

    `line_no` is intentionally absent — the service auto-assigns the next
    sequential line number per PO. Quantities/costs are fixed-point Decimals
    (never float — D-11): `qty_ordered` must be > 0 and `unit_cost` >= 0.
    `qty_received` is not settable here — it starts at 0 and is only moved by the
    receiving path (Decision 5). Lines may be added only while the PO is Draft
    (enforced in the service, AC11-1).
    """

    item_id: str = Field(..., max_length=36)
    qty_ordered: Decimal = Field(..., gt=0)
    unit_cost: Decimal = Field(..., ge=0)
    need_by_date: Optional[date] = None


class POLineUpdate(BaseModel):
    """
    Purchase-order line update payload (PATCH /syerp/purchasing/orders/{id}/lines/{line_id}).

    All fields Optional — PATCH semantics; only provided (non-None) fields are
    applied. `qty_ordered` (> 0) and `unit_cost` (>= 0) stay fixed-point Decimals.
    `qty_received` and `line_no` are not editable here (receiving owns qty_received;
    line_no is server-assigned). Edits are allowed only while the PO is Draft
    (enforced in the service, AC11-1).
    """

    item_id: Optional[str] = Field(None, max_length=36)
    qty_ordered: Optional[Decimal] = Field(None, gt=0)
    unit_cost: Optional[Decimal] = Field(None, ge=0)
    need_by_date: Optional[date] = None


class POLineRead(BaseModel):
    """
    Purchase-order line returned to API callers.

    Serialized from a PurchaseOrderLine ORM instance via from_attributes=True.
    Quantities/costs are fixed-point Decimals (Numeric(18,6)), never float.
    """

    id: str
    po_id: str
    item_id: str
    line_no: int
    qty_ordered: Decimal
    unit_cost: Decimal
    qty_received: Decimal
    need_by_date: Optional[date] = None

    model_config = {"from_attributes": True}


class POCreate(BaseModel):
    """
    Purchase-order header creation payload (POST /syerp/purchasing/orders).

    `vendor_id` MUST reference an existing Partner with is_vendor=True — the
    service rejects a non-vendor (or missing) partner with 422 (AC11-3). A new PO
    is created empty and in Draft; lines are added afterwards through the
    /orders/{id}/lines endpoints. `po_number` is server-generated (numeric-safe
    PO-#### series), never client-supplied.
    """

    vendor_id: str = Field(..., max_length=36)
    notes: Optional[str] = None


class PORead(BaseModel):
    """
    Purchase-order header returned to API callers, with its lines nested.

    Lines are embedded (`lines: list[POLineRead]`) so a single GET returns the
    complete order. Assembled in the service (not via a lazy ORM relationship) to
    avoid MissingGreenlet in the async context (RESEARCH.md Pitfall 2). `status`
    walks draft | approved | partially_received | received | closed;
    approved_at/approved_by are NULL until the PO is approved.

    `total` and the *_qty roll-ups are computed in the service from the loaded
    lines (no extra query) so vendor purchase-history lists (AC11-3) and the
    status table (AC11-5) get ordered value + ordered/received/outstanding
    quantities without an N+1. Decimals are exact (never float — D-11).
    """

    id: str
    po_number: str
    vendor_id: str
    status: str
    notes: Optional[str] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # Per-PO roll-ups computed in the service from the loaded lines (no N+1):
    # `total` = SUM(qty_ordered * unit_cost) — the PO's ordered value (AC11-3);
    # the *_qty fields drive the vendor status table (AC11-5). All Decimal, exact.
    total: Decimal = Decimal("0")
    total_ordered_qty: Decimal = Decimal("0")
    total_received_qty: Decimal = Decimal("0")
    outstanding_qty: Decimal = Decimal("0")
    lines: list[POLineRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ReceiveLine(BaseModel):
    """
    PO line receiving payload (POST /syerp/purchasing/orders/{id}/lines/{line_id}/receive).

    Receives `qty` of the line into `location_id`, posting a REAL costed inventory
    receipt at the line's unit cost (Task 17, AC11-4). `qty` must be > 0 at the
    boundary; the service additionally rejects over-receipt (`qty_received + qty >
    qty_ordered`) and receiving on a PO that is not `approved` /
    `partially_received`. `qty` is a fixed-point Decimal (never float — D-11).
    """

    location_id: int
    qty: Decimal = Field(..., gt=0)


# ---------------------------------------------------------------------------
# GL Account schema
# ---------------------------------------------------------------------------


class GLAccountRead(BaseModel):
    """
    GL account data returned to API callers.

    Read-only in Phase 4 (D-11 scope guard). The flat list is
    grouped/rendered by the frontend.
    """

    id: int
    code: str
    name: str
    account_type: str  # ASSET | LIABILITY | EQUITY | REVENUE | EXPENSE
    parent_id: Optional[int] = None
    active: bool

    model_config = {"from_attributes": True}
