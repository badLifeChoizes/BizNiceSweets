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


# ---------------------------------------------------------------------------
# Journal entry / line schemas (Phase 9a — GL posting engine)
# ---------------------------------------------------------------------------
#
# A journal entry carries its lines nested (JournalEntryCreate.lines /
# JournalEntryRead.lines) so a single POST posts a whole balanced entry and a
# single GET returns it complete. Balancing (SUM debits == SUM credits) and the
# minimum-two-lines rule are enforced in the service against live account state;
# the per-line "exactly one of debit/credit, both >= 0" rule is enforced here as
# defense-in-depth beside the pure posting helper (D-P9-1). Money is Decimal
# (never float — D-11).


class JournalLineCreate(BaseModel):
    """
    One line of a journal-entry posting payload.

    Exactly ONE of `debit` / `credit` must be set (non-None); the other side is
    left None. Any supplied amount must be >= 0 — a negative debit/credit is a
    sign error, not a valid posting (flip it to the other column instead). This
    mirrors the pure posting helper's guard as defense-in-depth (D-P9-1).
    """

    account_id: int
    debit: Optional[Decimal] = None
    credit: Optional[Decimal] = None

    @model_validator(mode="after")
    def exactly_one_side_non_negative(self) -> "JournalLineCreate":
        """Reject lines that set both sides, neither side, or a negative amount."""
        if (self.debit is None) == (self.credit is None):
            raise ValueError(
                "A journal line must set exactly one of debit or credit "
                "(not both, not neither)."
            )
        if self.debit is not None and self.debit < 0:
            raise ValueError("debit must be >= 0.")
        if self.credit is not None and self.credit < 0:
            raise ValueError("credit must be >= 0.")
        return self


class JournalEntryCreate(BaseModel):
    """
    Journal-entry posting payload (POST /syerp/gl/journal-entries).

    A manual entry: `entry_date` is the effective date, `memo` an optional
    description, and `lines` the balanced set of debit/credit legs. The service
    enforces balancing and the minimum-two-lines rule against live account
    state; each line is validated here (JournalLineCreate). Money is Decimal.
    """

    entry_date: date
    memo: Optional[str] = None
    lines: list[JournalLineCreate]


class JournalLineRead(BaseModel):
    """
    One journal-entry line returned to API callers.

    Serialized from a JournalLine ORM instance via from_attributes=True. Amounts
    are fixed-point Decimals (never float — D-11); the unused side is None.
    """

    id: str  # String(36) uuid PK (models.py) — D-P9a-1
    line_no: int
    account_id: int
    debit: Optional[Decimal] = None
    credit: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class JournalEntryRead(BaseModel):
    """
    Journal entry returned to API callers, with its lines nested.

    Serialized from a JournalEntry ORM instance via from_attributes=True.
    `source_type` / `source_id` are the soft polymorphic link back to the
    originating document (e.g. an inventory receipt auto-post); `reversal_of_id`
    is set on the reversing entry produced by a reversal (D-P9-1). `actor_id`
    records who posted it (audit/traceability).
    """

    id: str  # String(36) uuid PK (models.py) — D-P9a-1
    entry_date: date
    memo: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    reversal_of_id: Optional[str] = None  # self-FK String(36) — D-P9a-1
    actor_id: str
    created_at: datetime
    lines: list[JournalLineRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ReverseRequest(BaseModel):
    """
    Journal-entry reversal payload (POST /syerp/gl/journal-entries/{id}/reverse).

    Posts a new entry that swaps every debit/credit of the target, linked back
    via `reversal_of_id`. `memo` optionally overrides the reversing entry's memo
    (the service supplies a default derived from the original when omitted).
    """

    memo: Optional[str] = None


class AccountRegisterRow(BaseModel):
    """
    One row of an account register — a single posting to the account in date
    order, with the running balance after it (Decimal, never float — D-11).
    """

    entry_date: date
    entry_id: str  # JournalEntry.id String(36) uuid — D-P9a-1
    memo: Optional[str] = None
    debit: Optional[Decimal] = None
    credit: Optional[Decimal] = None
    running_balance: Decimal


class AccountRegisterRead(BaseModel):
    """
    Account register for a single GL account over a period.

    Carries the account meta (id/code/name), the `opening_balance` carried into
    the period, the ordered `rows` of postings each with their running balance,
    and the `closing_balance` after the last row. All balances are Decimal.
    """

    account_id: int
    account_code: str
    account_name: str
    opening_balance: Decimal
    closing_balance: Decimal
    rows: list[AccountRegisterRow] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Accounts-payable schemas (Phase 9b — AP bills, PO match, payments; SYERP-12)
# ---------------------------------------------------------------------------
#
# A bill carries its lines nested (BillCreate.lines / BillRead.lines) so a single
# POST records a whole vendor invoice and a single GET returns it complete. A bill
# line is one of exactly two shapes — a `matched` line (drawing a costed quantity
# off an unbilled PO receipt) or a free-text `expense` line (a GL account + amount)
# — the one-shape rule is enforced on BillLineCreate as defense-in-depth beside the
# service. `total` / `open_balance` on BillRead and `amount` on PaymentRead are
# DERIVED roll-ups the service computes (open_balance = total - allocations; a
# payment's amount = SUM of its allocations); they are plain fields here, filled by
# the service rather than validated from the client. Money is Decimal (never float
# — D-11).


class UnbilledReceiptRead(BaseModel):
    """
    One unbilled PO receipt available to match on a bill (matched-line picker).

    A PO line that has been received but not yet fully billed: `unbilled_qty` is
    the still-billable quantity at the line's `unit_cost`. Quantities/costs are
    fixed-point Decimals (never float — D-11).
    """

    po_line_id: str
    po_number: str
    item_id: str
    unbilled_qty: Decimal
    unit_cost: Decimal


class BillLineCreate(BaseModel):
    """
    One line of a bill-creation payload — exactly one of two shapes.

    A `matched` line draws `matched_qty` off an unbilled PO receipt (`po_line_id`);
    its amount is derived by the service from the receipt's unit cost, so no
    `account_id`/`amount` is supplied. An `expense` line is free-text against a GL
    `account_id` for an explicit `amount` (> 0), with no `po_line_id`. Setting both
    `po_line_id` and `account_id`, or an unknown `line_type`, is rejected here as
    defense-in-depth beside the service. Money is Decimal (never float — D-11).
    """

    line_type: str  # 'matched' | 'expense'
    po_line_id: Optional[str] = None
    matched_qty: Optional[Decimal] = None
    account_id: Optional[int] = None
    amount: Optional[Decimal] = None

    @model_validator(mode="after")
    def exactly_one_line_shape(self) -> "BillLineCreate":
        """Reject any line that is not a clean 'matched' or 'expense' shape."""
        if self.po_line_id is not None and self.account_id is not None:
            raise ValueError(
                "A bill line cannot set both po_line_id and account_id — a line is "
                "either a matched PO receipt or a free-text expense, not both."
            )
        if self.line_type == "matched":
            if self.po_line_id is None or self.matched_qty is None:
                raise ValueError(
                    "A matched bill line must set po_line_id and matched_qty."
                )
            if self.account_id is not None:
                raise ValueError("A matched bill line must not set account_id.")
        elif self.line_type == "expense":
            if self.account_id is None:
                raise ValueError("An expense bill line must set account_id.")
            if self.amount is None or self.amount <= 0:
                raise ValueError("An expense bill line must set amount > 0.")
            if self.po_line_id is not None:
                raise ValueError("An expense bill line must not set po_line_id.")
        else:
            raise ValueError("line_type must be 'matched' or 'expense'.")
        return self


class BillCreate(BaseModel):
    """
    Bill (vendor invoice) creation payload (POST /syerp/ap/bills).

    `vendor_id` MUST reference an existing Partner with is_vendor=True (enforced in
    the service). `vendor_invoice_ref` is the supplier's own invoice number (free
    text, optional). `lines` is the non-empty set of matched/expense legs; the
    service derives matched-line amounts from PO receipts and rolls up the total.
    `bill_number` is server-generated, never client-supplied.
    """

    vendor_id: str = Field(..., max_length=36)
    vendor_invoice_ref: Optional[str] = None
    # bill_date: the vendor's invoice date AP aging buckets from; defaults to
    # today server-side when omitted (D-P9c-1).
    bill_date: Optional[date] = None
    lines: list[BillLineCreate] = Field(..., min_length=1)


class BillLineRead(BaseModel):
    """
    One bill line returned to API callers.

    Serialized from a BillLine ORM instance via from_attributes=True. A `matched`
    line carries po_line_id/matched_qty/unit_cost; an `expense` line carries
    account_id. `amount` is the line's booked value either way — a matched line's
    matched_qty * unit_cost, an expense line's explicit amount. Money is Decimal.
    """

    id: str
    line_no: int
    line_type: str
    po_line_id: Optional[str] = None
    matched_qty: Optional[Decimal] = None
    account_id: Optional[int] = None
    unit_cost: Optional[Decimal] = None
    amount: Decimal

    model_config = {"from_attributes": True}


class BillRead(BaseModel):
    """
    Bill returned to API callers, with its lines nested.

    `total` and `open_balance` are DERIVED roll-ups the service computes from the
    lines and allocations (open_balance = total - SUM allocations), not stored
    fields — the service constructs this model rather than serializing an ORM
    instance for those two, so they are plain Decimals here. `status` walks
    draft | posted | partially_paid | paid; `posted_at` is NULL until posted.
    Money is Decimal (never float — D-11).
    """

    id: str
    bill_number: str
    vendor_id: str
    vendor_invoice_ref: Optional[str] = None
    bill_date: date
    status: str
    memo: Optional[str] = None
    posted_at: Optional[datetime] = None
    total: Decimal = Decimal("0")
    open_balance: Decimal = Decimal("0")
    lines: list[BillLineRead] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentAllocationCreate(BaseModel):
    """
    One allocation of a payment to a specific bill (payment-creation payload).

    Applies `amount` (> 0) against the open balance of `bill_id`; the service
    rejects over-application. Money is Decimal (never float — D-11).
    """

    bill_id: str
    amount: Decimal = Field(..., gt=0)


class PaymentCreate(BaseModel):
    """
    Payment creation payload (POST /syerp/ap/payments).

    Records a cash disbursement from `cash_account_id` on `payment_date`, split
    across one or more bills via `allocations`. The payment's amount is NOT
    client-supplied — the service sums the allocations — so it is absent here.
    `reference` is the check/transfer reference (free text, optional). Money is
    Decimal (never float — D-11).
    """

    payment_date: date
    cash_account_id: int
    reference: Optional[str] = None
    allocations: list[PaymentAllocationCreate] = Field(..., min_length=1)


class PaymentAllocationRead(BaseModel):
    """
    One payment allocation returned to API callers.

    Serialized from a PaymentAllocation ORM instance via from_attributes=True.
    `amount` is the value applied to `bill_id` (Decimal, never float — D-11).
    """

    bill_id: str
    amount: Decimal

    model_config = {"from_attributes": True}


class PaymentRead(BaseModel):
    """
    Payment returned to API callers, with its allocations nested.

    `amount` is the DERIVED total the service sums from the allocations (the client
    never supplies it), so this model is service-constructed rather than a plain ORM
    serialization for that field. Money is Decimal (never float — D-11).
    """

    id: str
    payment_date: date
    cash_account_id: int
    amount: Decimal
    reference: Optional[str] = None
    allocations: list[PaymentAllocationRead] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Accounts-receivable schemas (Phase 13 — AR invoices, receipts; SYERP-13)
# ---------------------------------------------------------------------------
#
# The sell-side mirror of the AP schemas. An invoice carries its lines nested
# (InvoiceCreate.lines / InvoiceRead.lines) so a single POST records a whole
# customer invoice and a single GET returns it complete. Each line draws an
# uninvoiced shipped quantity off a CRUMB sales order line (the sell-side analogue
# of a matched PO receipt). `total` / `open_balance` on InvoiceRead and `amount` on
# ReceiptRead are DERIVED roll-ups the service computes (open_balance = total −
# allocations; a receipt's amount = SUM of its allocations); they are plain fields
# here, filled by the service rather than validated from the client. Money is
# Decimal (never float — D-11).


class UninvoicedShipmentRead(BaseModel):
    """
    One uninvoiced shipped quantity available to invoice (invoice-line picker).

    A sales order line that has been shipped but not yet fully invoiced:
    `uninvoiced_qty` is the still-billable quantity at the line's `unit_price`.
    `item_id` FKs a SYERP stock item on a stock line; `description` carries the
    free-text item on a non-stock line. Quantities/prices are fixed-point Decimals
    (never float — D-11).
    """

    sales_order_line_id: str
    so_number: str
    item_id: Optional[str] = None
    description: Optional[str] = None
    uninvoiced_qty: Decimal
    unit_price: Decimal


class InvoiceLineCreate(BaseModel):
    """
    One line of an invoice-creation payload.

    Draws `invoiced_qty` (> 0) off an uninvoiced shipped quantity on the sales order
    line `sales_order_line_id`; its amount is derived by the service from the line's
    unit price, so no `unit_price`/`amount` is supplied. Money is Decimal.
    """

    sales_order_line_id: str
    invoiced_qty: Decimal = Field(..., gt=0)


class InvoiceCreate(BaseModel):
    """
    Invoice (customer invoice) creation payload (POST /syerp/ar/invoices).

    `customer_id` MUST reference an existing Partner with is_customer=True (enforced
    in the service). `sales_order_id` optionally ties the invoice to the CRUMB sales
    order it is raised from (NULL for a standalone invoice). `lines` is the non-empty
    set of invoiced quantities; the service derives line amounts from the sales order
    line prices and rolls up the total. `invoice_number` is server-generated, never
    client-supplied; `invoice_date` defaults to today server-side when omitted.
    """

    customer_id: str = Field(..., max_length=36)
    sales_order_id: Optional[str] = None
    invoice_date: Optional[date] = None
    lines: list[InvoiceLineCreate] = Field(..., min_length=1)


class InvoiceLineRead(BaseModel):
    """
    One invoice line returned to API callers.

    Serialized from an InvoiceLine ORM instance via from_attributes=True. `amount`
    is the line's booked value — invoiced_qty * unit_price. Money is Decimal.
    """

    id: str
    line_no: int
    sales_order_line_id: str
    invoiced_qty: Decimal
    unit_price: Decimal
    amount: Decimal

    model_config = {"from_attributes": True}


class InvoiceRead(BaseModel):
    """
    Invoice returned to API callers, with its lines nested.

    `total` and `open_balance` are DERIVED roll-ups the service computes from the
    lines and allocations (open_balance = total − SUM allocations), not stored
    fields — the service constructs this model rather than serializing an ORM
    instance for those two, so they are plain Decimals here. `status` walks
    draft | posted | partially_paid | paid; `posted_at` is NULL until posted.
    Money is Decimal (never float — D-11).
    """

    id: str
    invoice_number: str
    customer_id: str
    sales_order_id: Optional[str] = None
    invoice_date: date
    status: str
    memo: Optional[str] = None
    posted_at: Optional[datetime] = None
    total: Decimal = Decimal("0")
    open_balance: Decimal = Decimal("0")
    lines: list[InvoiceLineRead] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class ReceiptAllocationCreate(BaseModel):
    """
    One allocation of a receipt to a specific invoice (receipt-creation payload).

    Applies `amount` (> 0) against the open balance of `invoice_id`; the service
    rejects over-application. Money is Decimal (never float — D-11).
    """

    invoice_id: str
    amount: Decimal = Field(..., gt=0)


class ArReceiptCreate(BaseModel):
    """
    AR cash-receipt creation payload (POST /syerp/ar/receipts).

    Records a cash collection into `cash_account_id` on `receipt_date`, split across
    one or more invoices via `allocations`. The receipt's amount is NOT
    client-supplied — the service sums the allocations — so it is absent here.
    `reference` is the check/transfer reference (free text, optional). Money is
    Decimal (never float — D-11).

    Named ArReceiptCreate (not ReceiptCreate) to avoid colliding with the inventory
    costed-receipt schema of that name earlier in this module — a duplicate class name
    would shadow the inventory one and break its request body (Phase 13 fix).
    """

    receipt_date: date
    cash_account_id: int
    reference: Optional[str] = None
    allocations: list[ReceiptAllocationCreate] = Field(..., min_length=1)


class ReceiptAllocationRead(BaseModel):
    """
    One receipt allocation returned to API callers.

    Serialized from a ReceiptAllocation ORM instance via from_attributes=True.
    `amount` is the value applied to `invoice_id` (Decimal, never float — D-11).
    """

    invoice_id: str
    amount: Decimal

    model_config = {"from_attributes": True}


class ReceiptRead(BaseModel):
    """
    Receipt returned to API callers, with its allocations nested.

    `amount` is the DERIVED total the service sums from the allocations (the client
    never supplies it), so this model is service-constructed rather than a plain ORM
    serialization for that field. Money is Decimal (never float — D-11).
    """

    id: str
    receipt_date: date
    cash_account_id: int
    amount: Decimal
    reference: Optional[str] = None
    allocations: list[ReceiptAllocationRead] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Financial report schemas (Phase 9c — AP aging + financial statements)
# ---------------------------------------------------------------------------
#
# These are read-only, service-CONSTRUCTED report models (not ORM serializations):
# the service derives every figure from the append-only journal / AP subledger and
# assembles the model. Money is Decimal throughout (never float — D-11). Report
# balances are date-filtered on JournalEntry.entry_date (the report window), NOT the
# whole-ledger derive_account_balance; sign is normalised so every magnitude presents
# positive (debit-normal ASSET/EXPENSE as Σdr−Σcr, credit-normal LIABILITY/EQUITY/
# REVENUE as Σcr−Σdr). AP aging ties out to the 2110 Accounts-Payable control (AC6);
# TB/P&L/Balance-Sheet are the AC7 statements.


class ApAgingTotals(BaseModel):
    """
    The five AP-aging bucket sums, shared by each vendor row's roll-up and the
    report grand total. `total` == current + d31_60 + d61_90 + d90_plus. Buckets
    the still-open bill balance by age = (as_of − bill_date).days: `current` 0–30,
    `d31_60` 31–60, `d61_90` 61–90, `d90_plus` 90+. Money is Decimal (never float).
    """

    current: Decimal
    d31_60: Decimal
    d61_90: Decimal
    d90_plus: Decimal
    total: Decimal


class ApAgingBucketRow(BaseModel):
    """
    One vendor's AP-aging row — the vendor identity plus its five bucket sums
    (same shape as ApAgingTotals). `total` is the vendor's whole open payable.
    """

    vendor_id: str
    vendor_name: str
    current: Decimal
    d31_60: Decimal
    d61_90: Decimal
    d90_plus: Decimal
    total: Decimal


class ApAgingReport(BaseModel):
    """
    Accounts-payable aging as of a date, with the 2110 subledger tie-out (AC6).

    `vendors` lists each vendor with an open payable, bucketed by age; `grand_total`
    is the column roll-up across vendors. `control_balance` is the date-filtered 2110
    Accounts-Payable derived balance (negated to present the positive outstanding
    payable, since 2110 is credit-normal); `in_balance` is True when the aging grand
    total ties to that control to the cent (D-P9c-1). Money is Decimal (never float).
    """

    as_of: date
    vendors: list[ApAgingBucketRow] = Field(default_factory=list)
    grand_total: ApAgingTotals
    control_balance: Decimal
    in_balance: bool


class ArAgingTotals(BaseModel):
    """
    The five AR-aging bucket sums, shared by each customer row's roll-up and the
    report grand total. `total` == current + d31_60 + d61_90 + d90_plus. Buckets
    the still-open invoice balance by age = (as_of − invoice_date).days: `current`
    0–30, `d31_60` 31–60, `d61_90` 61–90, `d90_plus` 90+. Money is Decimal.
    """

    current: Decimal
    d31_60: Decimal
    d61_90: Decimal
    d90_plus: Decimal
    total: Decimal


class ArAgingBucketRow(BaseModel):
    """
    One customer's AR-aging row — the customer identity plus its five bucket sums
    (same shape as ArAgingTotals). `total` is the customer's whole open receivable.
    """

    customer_id: str
    customer_name: str
    current: Decimal
    d31_60: Decimal
    d61_90: Decimal
    d90_plus: Decimal
    total: Decimal


class ArAgingReport(BaseModel):
    """
    Accounts-receivable aging as of a date, with the 1200 subledger tie-out.

    `customers` lists each customer with an open receivable, bucketed by age;
    `grand_total` is the column roll-up across customers. `control_balance` is the
    date-filtered Accounts-Receivable derived balance; `in_balance` is True when the
    aging grand total ties to that control to the cent. Money is Decimal (never
    float — D-11).
    """

    as_of: date
    customers: list[ArAgingBucketRow] = Field(default_factory=list)
    grand_total: ArAgingTotals
    control_balance: Decimal
    in_balance: bool


class TrialBalanceRow(BaseModel):
    """
    One trial-balance row — a posting account's net position as of a date, split
    into a single non-zero column. If Σdebit − Σcredit >= 0 the magnitude sits in
    `debit` (credit 0), otherwise in `credit` (debit 0). Money is Decimal.
    """

    account_id: int
    code: str
    name: str
    account_type: str  # ASSET | LIABILITY | EQUITY | REVENUE | EXPENSE
    debit: Decimal
    credit: Decimal


class TrialBalanceReport(BaseModel):
    """
    Trial balance as of a date — every posting account's net debit/credit (AC7).

    `rows` are ordered by account code; `total_debit` / `total_credit` are the column
    sums and `in_balance` is True when they are equal (a balanced ledger). Money is
    Decimal (never float — D-11).
    """

    as_of: date
    rows: list[TrialBalanceRow] = Field(default_factory=list)
    total_debit: Decimal
    total_credit: Decimal
    in_balance: bool


class ProfitLossLine(BaseModel):
    """
    One P&L line — a revenue or expense account's positive period activity. Money
    is Decimal (never float — D-11).
    """

    account_id: int
    code: str
    name: str
    amount: Decimal


class ProfitLossReport(BaseModel):
    """
    Profit & loss over an inclusive [date_from, date_to] window (AC7).

    `revenue` / `expense` list each account's positive period activity (ordered by
    code); `total_revenue` / `total_expense` are the section sums and `net_income`
    is total_revenue − total_expense. Money is Decimal (never float — D-11).
    """

    date_from: date
    date_to: date
    revenue: list[ProfitLossLine] = Field(default_factory=list)
    total_revenue: Decimal
    expense: list[ProfitLossLine] = Field(default_factory=list)
    total_expense: Decimal
    net_income: Decimal


class BalanceSheetLine(BaseModel):
    """
    One balance-sheet line — an account's positive as-of balance (or the computed
    current-year net-income equity line). Money is Decimal (never float — D-11).
    """

    account_id: int
    code: str
    name: str
    amount: Decimal


class BalanceSheetReport(BaseModel):
    """
    Balance sheet as of a date — assets vs. liabilities + equity (AC7).

    Each section lists its accounts (ordered by code) as positive magnitudes.
    `equity` additionally carries a COMPUTED current-year net-income line (3130) —
    revenue less expense through `as_of` — because no closing entries are posted, so
    ledger 3130 is empty. `in_balance` is True when total_assets == total_liabilities
    + total_equity (the accounting identity). Money is Decimal (never float — D-11).
    """

    as_of: date
    assets: list[BalanceSheetLine] = Field(default_factory=list)
    total_assets: Decimal
    liabilities: list[BalanceSheetLine] = Field(default_factory=list)
    total_liabilities: Decimal
    equity: list[BalanceSheetLine] = Field(default_factory=list)
    total_equity: Decimal
    in_balance: bool
