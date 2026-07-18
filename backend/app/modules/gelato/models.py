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

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
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
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
