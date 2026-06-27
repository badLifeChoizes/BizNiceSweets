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
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
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
