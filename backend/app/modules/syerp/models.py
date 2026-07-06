"""
SYERP module ORM models.

Tables defined here:
  syerp_partner    — Unified vendor/customer master data record (D-01).
                     Downstream modules (PLUM, FLAN, MOUSSE, etc.) foreign-key
                     into this table. Uses boolean role flags (is_vendor,
                     is_customer) rather than separate tables — res.partner style.
  syerp_gl_account — Chart-of-accounts skeleton. Seeded at startup by
                     app.modules.syerp.coa_seed; read-only via the API in Phase 4.

Phase 4: Added Partner and GLAccount models (SYERP Core Hub).
Phase 8: Added InventoryItem, StockLocation and InventoryTxn models
         (SYERP inventory & purchasing — migration 0007).
         Added PurchaseOrder and PurchaseOrderLine models
         (SYERP purchasing — migration 0008).

All models inherit from Base so that Base.metadata is populated when
app.core.models (the central aggregator) is imported by Alembic's env.py.

CRITICAL naming decisions:
  - syerp_partner uses `active` (NOT `is_active`) to distinguish from
    auth User.is_active.
  - syerp_gl_account uses `account_type` (NOT `type`) — `type` is a Python
    built-in and a SQLAlchemy reserved word.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


# ---------------------------------------------------------------------------
# Partner — unified vendor/customer master record
# ---------------------------------------------------------------------------


class Partner(Base):
    """
    Unified vendor/customer master data record.

    A single Partner row can represent a vendor, a customer, or both
    (dual-role entity). Role membership is controlled by the `is_vendor` and
    `is_customer` boolean flags. Both flags False is an invalid state and is
    rejected by the API schema validator (RESEARCH.md Pitfall 8).

    Downstream modules (PLUM AVL, MOUSSE POs, etc.) will FK into this table
    using `partner.id`.
    """

    __tablename__ = "syerp_partner"

    # --- Primary key -------------------------------------------------------
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Identity (D-03) ---------------------------------------------------
    # code: auto-generated P-#### series; user-editable before save; unique (D-04)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    is_vendor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_customer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # active: soft-delete flag (D-05). False = archived; hidden from default lists.
    # Named `active` (not `is_active`) to distinguish from auth User.is_active.
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # --- Address block (single embedded, D-03) -----------------------------
    addr_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    addr_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    addr_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    addr_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    addr_postal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    addr_country: Mapped[str | None] = mapped_column(String(2), nullable=True)  # ISO 3166-1 alpha-2

    # --- Contact block (single embedded primary contact, D-03) ------------
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # --- Commerce (D-03, aligned with PLUM Vendors object fields) ----------
    payment_terms: Mapped[str | None] = mapped_column(String(50), nullable=True)   # e.g. "Net 30"
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)          # EIN/VAT
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)         # ISO 4217 e.g. "USD"
    country_of_origin: Mapped[str | None] = mapped_column(String(2), nullable=True)  # ISO 3166-1 alpha-2
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Timestamps --------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # No ORM relationships declared in Phase 4 — the GL endpoint returns a flat
    # list; partner list queries only need scalar columns. Adding relationships
    # later requires lazy="selectin" to avoid MissingGreenlet in async context
    # (RESEARCH.md Pitfall 2).


# ---------------------------------------------------------------------------
# GLAccount — chart-of-accounts skeleton (D-06)
# ---------------------------------------------------------------------------


class GLAccount(Base):
    """
    Chart-of-accounts record. Seeded idempotently at startup by
    app.modules.syerp.coa_seed.seed_gl_accounts(); read-only via the API.

    account_type: one of ASSET / LIABILITY / EQUITY / REVENUE / EXPENSE.
    Named `account_type` (NOT `type`) — `type` shadows Python's built-in
    and is a SQLAlchemy reserved word (RESEARCH.md Pitfall 4).

    parent_id: self-referential FK for tree structure. The GL endpoint returns
    a flat list; tree rendering is done frontend-side. No ORM relationship is
    declared here to avoid MissingGreenlet issues (Pitfall 2).
    """

    __tablename__ = "syerp_gl_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # account_type: ASSET | LIABILITY | EQUITY | REVENUE | EXPENSE
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # parent_id: self-referential; None for top-level accounts
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("syerp_gl_account.id"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ---------------------------------------------------------------------------
# InventoryItem — stock-keeping master record (Phase 8, D-P8-2)
# ---------------------------------------------------------------------------


class InventoryItem(Base):
    """
    Inventory item master record — the stock-keeping unit SYERP tracks.

    Uses a String(36) uuid PK (mirrors Partner) because it is referenced by
    FKs from inventory transactions and PO lines and is non-enumerable.

    plum_part_id is a NULLABLE FK into plum_part.id with NO cascade: SYERP
    inventory must keep working when the PLUM module is disabled (D-P8-2), so
    an item is never hard-linked to a PLUM part. The link is advisory only.

    moving_avg_cost holds the running moving-average unit cost (Decision 4),
    a fixed-point Numeric(18,6) value (never float — D-11). It defaults to 0
    and is recomputed by the inventory service on each costed receipt.
    """

    __tablename__ = "syerp_inventory_item"

    # --- Primary key — UUID string (mirrors syerp_partner.id) --------------
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Identity ----------------------------------------------------------
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    unit_of_measure: Mapped[str] = mapped_column(String(50), nullable=False)

    # --- PLUM link (D-P8-2) — advisory, nullable, no cascade ---------------
    plum_part_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("plum_part.id"), nullable=True
    )

    # --- Costing (Decision 4) — moving-average unit cost, fixed-point ------
    moving_avg_cost: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), default=Decimal("0"), nullable=False
    )

    # active: soft-delete flag; False = archived, hidden from default lists.
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # --- Timestamps --------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# StockLocation — controlled set of physical/logical stock locations (Phase 8)
# ---------------------------------------------------------------------------


class StockLocation(Base):
    """
    Stock location record — a physical or logical place inventory lives.

    Uses an Integer autoincrement PK (mirrors syerp_gl_account) because it is
    a small, controlled, enumerable set of locations managed by admins.
    """

    __tablename__ = "syerp_stock_location"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- Timestamps --------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# InventoryTxn — append-only stock movement ledger (Phase 8, AC10-4)
# ---------------------------------------------------------------------------


class InventoryTxn(Base):
    """
    Inventory transaction — one immutable leg of a stock movement.

    This is an APPEND-ONLY ledger (AC10-4): rows are never updated or deleted;
    on-hand quantities are derived by summing signed `quantity` per item and
    location. Corrections are made by posting a compensating `adjustment` row.

    quantity is SIGNED — positive for stock in (receipt), negative for stock
    out (issue). A `transfer` is recorded as two rows (out + in) sharing a
    `transfer_group_id` so the pair can be reconciled.

    txn_type: receipt | issue | adjustment | transfer.
    source_type / source_id are a soft polymorphic link back to the document
    that caused the movement (e.g. a PO receipt); no FK, so the ledger stays
    valid even if the source module is disabled.
    """

    __tablename__ = "syerp_inventory_txn"

    # --- Primary key — UUID string (non-enumerable ledger row) -------------
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- What moved and where ----------------------------------------------
    item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("syerp_inventory_item.id"), nullable=False, index=True
    )
    location_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("syerp_stock_location.id"), nullable=False, index=True
    )

    # txn_type: receipt | issue | adjustment | transfer
    txn_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # quantity: SIGNED — positive = stock in, negative = stock out
    quantity: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
    # unit_cost: fixed-point; nullable (issues/adjustments may be quantity-only)
    unit_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=6), nullable=True
    )

    # --- Provenance / audit ------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    # source_type / source_id: soft polymorphic link to originating document
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # transfer_group_id: pairs the two legs (out + in) of a transfer
    transfer_group_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


# ---------------------------------------------------------------------------
# PurchaseOrder — purchase-order header (Phase 8)
# ---------------------------------------------------------------------------


class PurchaseOrder(Base):
    """
    Purchase-order header — a request to buy goods from a vendor.

    Uses a String(36) uuid PK (mirrors Partner / InventoryItem) because it is
    referenced by FKs from PO lines and is non-enumerable.

    vendor_id is an FK into syerp_partner.id (the vendor being purchased from).

    status walks a controlled lifecycle: draft | approved | partially_received
    | received | closed. Receiving accumulates against each line's qty_received
    (Decision 5) and rolls the header status forward.

    approved_at / approved_by record the approver identity and timestamp
    (D-P8-10); both are NULL until the PO is approved.
    """

    __tablename__ = "syerp_purchase_order"

    # --- Primary key — UUID string (mirrors syerp_partner.id) --------------
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Identity ----------------------------------------------------------
    po_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    # vendor_id: FK into syerp_partner.id (the vendor being purchased from)
    vendor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("syerp_partner.id"), nullable=False, index=True
    )

    # status: draft | approved | partially_received | received | closed
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Approval (D-P8-10) — approver identity + timestamp, NULL until approved
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # --- Timestamps --------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# PurchaseOrderLine — purchase-order line item (Phase 8)
# ---------------------------------------------------------------------------


class PurchaseOrderLine(Base):
    """
    Purchase-order line — one item ordered on a PurchaseOrder.

    Uses a String(36) uuid PK (mirrors the other purchasing rows).

    po_id FKs into the header; item_id FKs into syerp_inventory_item.id (the
    item being purchased).

    qty_ordered / unit_cost are fixed-point Numeric(18,6) (never float — D-11).
    qty_received is a running accumulator (Decision 5) that receiving increments;
    it defaults to 0 and never exceeds qty_ordered.

    need_by_date is an optional requested delivery date (date-only).
    """

    __tablename__ = "syerp_purchase_order_line"

    # --- Primary key — UUID string -----------------------------------------
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Links -------------------------------------------------------------
    po_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("syerp_purchase_order.id"), nullable=False, index=True
    )
    item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("syerp_inventory_item.id"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)

    # --- Quantities & cost (Decision 5, D-11) — fixed-point, never float ----
    qty_ordered: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
    # qty_received: running accumulator incremented by receiving (Decision 5)
    qty_received: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), default=Decimal("0"), nullable=False
    )

    # need_by_date: optional requested delivery date (date-only)
    need_by_date: Mapped[date | None] = mapped_column(Date, nullable=True)
