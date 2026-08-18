# ABOUTME: GELATO (Warehouse Management) ORM models — storage bins that
# ABOUTME: subdivide a SYERP stock location for directed putaway (GELATO-01).
# ABOUTME: Tables are prefixed `gelato_` and FK into the SYERP hub
# ABOUTME: (syerp_stock_location); syerp_inventory_txn.bin_id soft-links back.
"""
GELATO module ORM models.

Tables defined here (all prefixed `gelato_`, GELATO-01):
  gelato_bin  — A storage bin: a named sub-location inside a SYERP stock
                location that inventory can be directed into (putaway).

Bin subdivides a syerp_stock_location so on-hand can be resolved to a precise
bin. The movement ledger (syerp_inventory_txn) carries an optional bin_id FK
back to this table (added in syerp/models.py via a string table-name FK so the
hub needs no import of GELATO — D-P12a-3).

All models inherit from the shared declarative Base so that Base.metadata is
populated when app.core.models (the central aggregator) is imported by
Alembic's env.py.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base

# ---------------------------------------------------------------------------
# Bin — storage bin inside a SYERP stock location (GELATO-01)
# ---------------------------------------------------------------------------


class Bin(Base):
    """
    Storage bin — a named sub-location inside a SYERP stock location.

    Uses an Integer autoincrement PK (mirrors syerp_stock_location) because it
    is a small, controlled, enumerable set of bins managed by warehouse admins.

    location_id FKs into syerp_stock_location.id (the location this bin lives
    in, required). code is the bin's short label, unique within its location
    (uq_gelato_bin_location_code). active toggles a bin out of putaway rotation
    without deleting it.
    """

    __tablename__ = "gelato_bin"
    __table_args__ = (
        UniqueConstraint("location_id", "code", name="uq_gelato_bin_location_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # location_id: SYERP stock location this bin subdivides (required)
    location_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("syerp_stock_location.id"), nullable=False, index=True
    )
    # code: bin label, unique within its location
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- Timestamps --------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


# ---------------------------------------------------------------------------
# Shipment — outbound fulfillment of a CRUMB sales order (GELATO, Phase 12b)
# ---------------------------------------------------------------------------


class Shipment(Base):
    """
    Shipment — the pick/pack/ship record fulfilling a CRUMB sales order.

    Uses an Integer autoincrement PK (mirrors gelato_bin) — shipments are a
    controlled, enumerable set managed by warehouse staff. FKs into the SYERP
    hub and CRUMB use string table-name references so GELATO imports neither
    module (D-P12a-3 idiom).

    sales_order_id is the CRUMB order being fulfilled; location_id is the SYERP
    stock location fulfilling it; staging_bin_id is the bin picked into (set at
    pick). status walks the pick/pack/ship lifecycle (default "picking").
    journal_entry_id is set at ship (the GL posting), nullable until then.
    """

    __tablename__ = "gelato_shipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # sales_order_id: CRUMB sales order being fulfilled (required)
    sales_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("crumb_sales_order.id"), nullable=False, index=True
    )
    # location_id: SYERP stock location fulfilling this shipment (required)
    location_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("syerp_stock_location.id"), nullable=False
    )
    # staging_bin_id: bin picked into (set at pick)
    staging_bin_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gelato_bin.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="picking", nullable=False)
    # journal_entry_id: GL posting made at ship (nullable until shipped)
    journal_entry_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("syerp_journal_entry.id"), nullable=True
    )
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # --- Timestamps --------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ShipmentLine(Base):
    """
    Shipment line — a single item/qty picked for a shipment.

    Integer autoincrement PK (mirrors gelato_shipment). shipment_id FKs its
    parent shipment; sales_order_line_id ties back to the CRUMB order line being
    fulfilled; item_id is the SYERP inventory item; from_bin_id is the bin the
    stock was picked from. inventory_txn_id is the syerp_inventory_txn movement
    written at ship (nullable until then).
    """

    __tablename__ = "gelato_shipment_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # shipment_id: parent shipment (required)
    shipment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gelato_shipment.id"), nullable=False, index=True
    )
    # sales_order_line_id: CRUMB order line being fulfilled (required)
    sales_order_line_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("crumb_sales_order_line.id"), nullable=False
    )
    # item_id: SYERP inventory item picked (required)
    item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("syerp_inventory_item.id"), nullable=False
    )
    # from_bin_id: bin the stock was picked from (required)
    from_bin_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gelato_bin.id"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
    # inventory_txn_id: movement written at ship (nullable until shipped)
    inventory_txn_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("syerp_inventory_txn.id"), nullable=True
    )

    # --- Timestamps --------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
