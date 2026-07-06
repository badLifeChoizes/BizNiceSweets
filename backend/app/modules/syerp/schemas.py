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

from datetime import datetime
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
