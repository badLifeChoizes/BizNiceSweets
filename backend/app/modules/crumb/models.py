# ABOUTME: CRUMB (CRM) ORM models — leads, opportunities, quotes with lines,
# ABOUTME: and append-only customer interactions. Tables are prefixed `crumb_`
# ABOUTME: and FK into the SYERP hub (partners) and PLUM (parts).
"""
CRUMB module ORM models.

Tables defined here (all prefixed `crumb_`, CRUMB-01):
  crumb_lead          — Pipeline lead: a prospective customer/contact that can
                        be qualified and converted into an opportunity.
  crumb_opportunity   — A qualified sales opportunity against a SYERP partner,
                        walking a stage lifecycle toward won/lost.
  crumb_quote         — Quote header issued to a partner, optionally tied to an
                        opportunity, with a controlled status lifecycle.
  crumb_quote_line    — A priced line on a quote: a PLUM part or free-text item
                        with quantity, unit price and optional markup.
  crumb_sales_order   — Sales order header issued to a partner, optionally tied
                        to a source quote/opportunity, with a status lifecycle.
  crumb_sales_order_line — An ordered line on a sales order: a SYERP stock item
                        or non-stock free-text item with quantity, unit price
                        and a reservation accumulator.
  crumb_interaction   — Append-only log of a customer touch (call/email/note/
                        meeting) against a partner and optional pipeline record.

All models inherit from the shared declarative Base so that Base.metadata is
populated when app.core.models (the central aggregator) is imported by
Alembic's env.py.

Cross-module integration is via foreign keys into the hub, exactly per the
"SYERP as the hub" constraint: SYERP supplies the partner (customer); PLUM
supplies the part a quote line prices. All hub FKs are String(36) uuids,
mirroring syerp_partner.id and plum_part.id.

All money/qty columns are fixed-point Numeric(18,6) (never float — D-11),
mirroring SYERP.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base

# ---------------------------------------------------------------------------
# Lead — pipeline lead (CRUMB-01)
# ---------------------------------------------------------------------------


class Lead(Base):
    """
    Lead — a prospective customer/contact entering the pipeline.

    Uses a String(36) uuid PK (mirrors the SYERP/PLUM hub PKs) because it is
    referenced by FKs from opportunities and interactions and is non-enumerable.

    partner_id softly links an existing SYERP partner if the lead maps to one;
    opportunity_id links the opportunity this lead was converted into (a forward
    reference to crumb_opportunity — resolved by table-name string FK, so
    definition order does not matter).

    status walks new → qualified → converted. active is an archive flag: a lead
    is soft-archived by clearing it rather than being deleted.
    """

    __tablename__ = "crumb_lead"

    # --- Primary key — UUID string -----------------------------------------
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Identity ----------------------------------------------------------
    name: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    contact: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)

    # status: pipeline lifecycle — new | qualified | converted
    status: Mapped[str] = mapped_column(String(30), default="new", nullable=False)
    # active: archive flag (False = archived)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- Links -------------------------------------------------------------
    # partner_id: existing SYERP partner this lead maps to; NULL until linked
    partner_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("syerp_partner.id"), nullable=True
    )
    # opportunity_id: opportunity this lead converted into (forward ref); NULL until converted
    opportunity_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("crumb_opportunity.id"), nullable=True
    )

    # --- Provenance / audit ------------------------------------------------
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


# ---------------------------------------------------------------------------
# Opportunity — qualified sales opportunity (CRUMB-01)
# ---------------------------------------------------------------------------


class Opportunity(Base):
    """
    Opportunity — a qualified sales opportunity against a SYERP partner.

    Uses a String(36) uuid PK (mirrors the hub) because it is referenced by FKs
    from leads, quotes and interactions and is non-enumerable.

    partner_id is the SYERP customer the opportunity is for (required). lead_id
    softly links the originating lead. estimated_value is fixed-point
    Numeric(18,6) (never float — D-11).

    stage walks qualify → proposal → won | lost.
    """

    __tablename__ = "crumb_opportunity"

    # --- Primary key — UUID string -----------------------------------------
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Identity ----------------------------------------------------------
    name: Mapped[str] = mapped_column(String, nullable=False)

    # --- Links -------------------------------------------------------------
    # partner_id: SYERP customer the opportunity is for (required)
    partner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("syerp_partner.id"), nullable=False
    )
    # lead_id: originating lead; NULL if created directly
    lead_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("crumb_lead.id"), nullable=True
    )

    # --- Value / timing (D-11) — fixed-point, never float ------------------
    estimated_value: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=6), nullable=True
    )
    expected_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # stage: pipeline lifecycle — qualify | proposal | won | lost
    stage: Mapped[str] = mapped_column(String(30), default="qualify", nullable=False)

    # --- Provenance / audit ------------------------------------------------
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


# ---------------------------------------------------------------------------
# Quote — quote header (CRUMB-01)
# ---------------------------------------------------------------------------


class Quote(Base):
    """
    Quote — a quote header issued to a SYERP partner.

    Uses a String(36) uuid PK (mirrors the hub) because it is referenced by FKs
    from quote lines and interactions and is non-enumerable.

    quote_number is the human-facing unique identifier. partner_id is the SYERP
    customer (required); opportunity_id softly links the opportunity it quotes.

    status walks draft → sent → accepted | rejected | expired.
    """

    __tablename__ = "crumb_quote"

    # --- Primary key — UUID string -----------------------------------------
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Identity ----------------------------------------------------------
    quote_number: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False, index=True
    )

    # --- Links -------------------------------------------------------------
    # partner_id: SYERP customer the quote is for (required)
    partner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("syerp_partner.id"), nullable=False
    )
    # opportunity_id: opportunity this quote is against; NULL if standalone
    opportunity_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("crumb_opportunity.id"), nullable=True
    )

    # status: quote lifecycle — draft | sent | accepted | rejected | expired
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)

    # --- Provenance / audit ------------------------------------------------
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


# ---------------------------------------------------------------------------
# QuoteLine — priced line on a quote (CRUMB-01)
# ---------------------------------------------------------------------------


class QuoteLine(Base):
    """
    Quote line — one priced line on a quote.

    Uses a String(36) uuid PK.

    plum_part_id FKs into plum_part.id when the line prices a catalog part; it
    is NULL for a free-text line, in which case description carries the item.
    (The required-when-no-part rule is enforced in the service layer, not the
    DB, so description is nullable here.)

    quantity, unit_price and markup_pct are fixed-point Numeric(18,6) (never
    float — D-11). sort_order controls display order.
    """

    __tablename__ = "crumb_quote_line"

    # --- Primary key — UUID string -----------------------------------------
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Links -------------------------------------------------------------
    quote_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("crumb_quote.id"), nullable=False, index=True
    )
    # plum_part_id: catalog part priced by this line; NULL for a free-text line
    plum_part_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("plum_part.id"), nullable=True
    )

    # description: free-text item; required-when-no-part enforced in service
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    # --- Amounts (D-11) — fixed-point, never float -------------------------
    quantity: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6))
    markup_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=6), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer)


# ---------------------------------------------------------------------------
# Interaction — append-only customer touch log (CRUMB-01)
# ---------------------------------------------------------------------------


class Interaction(Base):
    """
    Interaction — one immutable record of a customer touch.

    APPEND-ONLY: rows are never updated or deleted; the history of contact is a
    permanent audit trail.

    partner_id is the SYERP customer the touch was with (required). lead_id /
    opportunity_id / quote_id softly link the pipeline record it relates to, any
    of which may be NULL.

    interaction_type is call | email | note | meeting. occurred_at is when the
    touch actually happened (distinct from created_at, when it was logged).
    """

    __tablename__ = "crumb_interaction"

    # --- Primary key — UUID string -----------------------------------------
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Links -------------------------------------------------------------
    # partner_id: SYERP customer the touch was with (required)
    partner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("syerp_partner.id"), nullable=False, index=True
    )
    lead_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("crumb_lead.id"), nullable=True
    )
    opportunity_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("crumb_opportunity.id"), nullable=True
    )
    quote_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("crumb_quote.id"), nullable=True
    )

    # --- Content -----------------------------------------------------------
    # interaction_type: call | email | note | meeting
    interaction_type: Mapped[str] = mapped_column(String(20))
    # occurred_at: when the touch actually happened (vs created_at when logged)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    body: Mapped[str] = mapped_column(String)

    # --- Provenance / audit ------------------------------------------------
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


# ---------------------------------------------------------------------------
# SalesOrder — sales order header (CRUMB-01, Phase 11b)
# ---------------------------------------------------------------------------


class SalesOrder(Base):
    """
    Sales order — a confirmed order header issued to a SYERP partner.

    Uses a String(36) uuid PK (mirrors the hub) because it is referenced by FKs
    from sales order lines and is non-enumerable.

    so_number is the human-facing unique identifier. partner_id is the SYERP
    customer (required). source_quote_id / source_opportunity_id softly link the
    quote / opportunity the order originated from (either may be NULL for a
    directly-created order).

    status walks draft → confirmed → fulfilling → closed | cancelled.
    """

    __tablename__ = "crumb_sales_order"

    # --- Primary key — UUID string -----------------------------------------
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Identity ----------------------------------------------------------
    so_number: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False, index=True
    )

    # --- Links -------------------------------------------------------------
    # partner_id: SYERP customer the order is for (required)
    partner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("syerp_partner.id"), nullable=False
    )
    # source_quote_id: quote this order was created from; NULL if standalone
    source_quote_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("crumb_quote.id"), nullable=True
    )
    # source_opportunity_id: opportunity this order is against; NULL if standalone
    source_opportunity_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("crumb_opportunity.id"), nullable=True
    )

    # status: order lifecycle — draft | confirmed | fulfilling | closed | cancelled
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)

    # --- Timing ------------------------------------------------------------
    order_date: Mapped[date] = mapped_column(Date)
    required_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- Provenance / audit ------------------------------------------------
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


# ---------------------------------------------------------------------------
# SalesOrderLine — ordered line on a sales order (CRUMB-01, Phase 11b)
# ---------------------------------------------------------------------------


class SalesOrderLine(Base):
    """
    Sales order line — one ordered line on a sales order.

    Uses a String(36) uuid PK.

    item_id FKs into syerp_inventory_item.id when the line orders a stock item;
    it is NULL for a non-stock line (D-V3-16), in which case description carries
    the free-text item. plum_part_id is a display FK into plum_part.id when the
    line references a catalog part.

    qty_ordered, unit_price and qty_reserved are fixed-point Numeric(18,6)
    (never float — D-11). qty_reserved is the reservation accumulator
    (D-V3-11), defaulting to zero. qty_picked and qty_shipped are the
    picked/shipped accumulators (D-P12b-5), likewise Numeric(18,6) and
    defaulting to zero. sort_order controls display order.
    """

    __tablename__ = "crumb_sales_order_line"

    # --- Primary key — UUID string -----------------------------------------
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Links -------------------------------------------------------------
    sales_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("crumb_sales_order.id"), nullable=False, index=True
    )
    # item_id: SYERP stock item ordered; NULL for a non-stock line (D-V3-16)
    item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("syerp_inventory_item.id"), nullable=True
    )
    # plum_part_id: catalog part referenced by this line (display); NULL if none
    plum_part_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("plum_part.id"), nullable=True
    )

    # description: free-text / display item; carries the item for a non-stock line
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    # --- Amounts (D-11) — fixed-point, never float -------------------------
    qty_ordered: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), nullable=False
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), nullable=False
    )
    # qty_reserved: reservation accumulator (D-V3-11); starts at zero
    qty_reserved: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), nullable=False, default=Decimal("0")
    )
    # qty_picked: picked accumulator (D-P12b-5); starts at zero
    qty_picked: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), nullable=False, default=Decimal("0")
    )
    # qty_shipped: shipped accumulator (D-P12b-5); starts at zero
    qty_shipped: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), nullable=False, default=Decimal("0")
    )
    # qty_invoiced: invoiced accumulator (AR seam); starts at zero
    qty_invoiced: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), nullable=False, default=Decimal("0")
    )
    sort_order: Mapped[int] = mapped_column(Integer)
