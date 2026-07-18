# ABOUTME: GELATO (Warehouse Management) Pydantic request/response schemas —
# ABOUTME: bin create/update/read, per-bin on-hand, the putaway request/result
# ABOUTME: (its two inventory-ledger legs, resulting bin on-hand, location total),
# ABOUTME: and the unbinned-stock read that drives the putaway suggestion screen.
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
from typing import Optional

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
    description: Optional[str] = None


class BinUpdate(BaseModel):
    """
    Bin PATCH payload (PATCH /gelato/bins/{id}).

    All fields optional — only the supplied fields are changed. `active=False`
    toggles a bin out of putaway rotation without deleting it. `location_id` and
    `code` are immutable identity and so are not settable here.
    """

    description: Optional[str] = None
    active: Optional[bool] = None


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
    description: Optional[str] = None
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
    from_bin_id: Optional[int] = None


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
    suggested_bin_id: Optional[int] = None
