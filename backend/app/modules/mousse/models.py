# ABOUTME: MOUSSE (Manufacturing Execution) ORM models — work orders, their
# ABOUTME: resolved BOM components, and append-only component-issue rows.
# ABOUTME: Tables are prefixed `mousse_` and FK into PLUM parts/revisions and
# ABOUTME: the SYERP hub (inventory items, locations, txns, journal entries).
"""
MOUSSE module ORM models.

Tables defined here (all prefixed `mousse_`, MOUSSE-01):
  mousse_work_order            — Work-order header: a request to build a
                                 PLUM part into finished-goods inventory.
  mousse_work_order_component  — A resolved BOM line for a work order: the
                                 child parts/items consumed to build it.
  mousse_work_order_issue      — Append-only record of a component quantity
                                 issued (consumed) against a work order, with
                                 soft links back to the SYERP inventory txn and
                                 journal entry it generated.

All models inherit from the shared declarative Base so that Base.metadata is
populated when app.core.models (the central aggregator) is imported by
Alembic's env.py.

Cross-module integration is via foreign keys into the hub, exactly per the
"SYERP as the hub" constraint: PLUM parts/revisions supply the build target and
BOM; SYERP supplies the inventory item, stock location, movement ledger
(syerp_inventory_txn) and general journal (syerp_journal_entry).

All money/qty columns are fixed-point Numeric(18,6) (never float — D-11),
mirroring SYERP.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base

# ---------------------------------------------------------------------------
# WorkOrder — work-order header (MOUSSE-01)
# ---------------------------------------------------------------------------


class WorkOrder(Base):
    """
    Work-order header — a request to build a PLUM part into finished goods.

    Uses a String(36) uuid PK (mirrors syerp_inventory_item.id) because it is
    referenced by FKs from components and issues and is non-enumerable.

    plum_part_id is the FG part to build (FK into plum_part.id, required).
    released_revision_id / output_item_id are NULL until the WO is released:
    release snapshots the released PLUM revision and resolves the SYERP
    finished-goods inventory item the build will stock.

    target_location_id is the SYERP stock location the finished goods land in.

    status walks a controlled lifecycle beginning at "draft".

    wo_date is the single date basis for every journal entry this work order
    posts, so all of a WO's GL activity shares one accounting date.
    """

    __tablename__ = "mousse_work_order"

    # --- Primary key — UUID string (mirrors syerp_inventory_item.id) --------
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Identity ----------------------------------------------------------
    wo_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)

    # --- Build target (PLUM) -----------------------------------------------
    # plum_part_id: FG part to build (required)
    plum_part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plum_part.id"), nullable=False, index=True
    )
    # released_revision_id: snapshot of the released PLUM revision; NULL until release
    released_revision_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("plum_part_revision.id"), nullable=True
    )
    # output_item_id: SYERP FG inventory item resolved from the WO part; NULL until release
    output_item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("syerp_inventory_item.id"), nullable=True
    )

    # --- Plan (D-11) — fixed-point, never float ----------------------------
    # planned_qty: quantity to build; must be > 0 (enforced in the service layer)
    planned_qty: Mapped[Decimal] = mapped_column(
        Numeric(precision=18, scale=6), nullable=False
    )
    # target_location_id: SYERP stock location the finished goods land in
    target_location_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("syerp_stock_location.id"), nullable=False
    )

    # status: controlled lifecycle, begins at "draft"
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    # wo_date: single accounting date basis for all of this WO's journal entries
    wo_date: Mapped[date] = mapped_column(Date, nullable=False)

    # --- Provenance / audit ------------------------------------------------
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    # completed_at: set when the WO is completed; NULL until then
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# WorkOrderComponent — resolved BOM line for a work order (MOUSSE-01)
# ---------------------------------------------------------------------------


class WorkOrderComponent(Base):
    """
    Work-order component — one resolved BOM line consumed to build a WO.

    Uses a String(36) uuid PK (mirrors the header).

    child_part_id FKs into plum_part.id (the component part). item_id FKs into
    syerp_inventory_item.id (the SYERP item that part maps to) and is NULL until
    the WO is released and the component resolves to a stockable item.

    qty_per is the per-unit BOM quantity; qty_required is the extended quantity
    for the whole build (qty_per * planned_qty). Both are fixed-point
    Numeric(18,6) (never float — D-11). sort_order controls display order.
    """

    __tablename__ = "mousse_work_order_component"

    # --- Primary key — UUID string -----------------------------------------
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Links -------------------------------------------------------------
    work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("mousse_work_order.id"), nullable=False, index=True
    )
    # child_part_id: FK into plum_part.id (the component part)
    child_part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plum_part.id"), nullable=False
    )
    # item_id: SYERP inventory item the component maps to; NULL until release
    item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("syerp_inventory_item.id"), nullable=True
    )

    # --- Quantities (D-11) — fixed-point, never float ----------------------
    qty_per: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6))
    qty_required: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6))
    unit_of_measure: Mapped[str] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer)


# ---------------------------------------------------------------------------
# WorkOrderIssue — append-only component-issue record (MOUSSE-01)
# ---------------------------------------------------------------------------


class WorkOrderIssue(Base):
    """
    Work-order issue — one immutable record of a component quantity issued
    (consumed) against a work order.

    APPEND-ONLY (mirrors syerp_inventory_txn / syerp_journal_entry): rows are
    never updated or deleted; a mistaken issue is corrected by a compensating
    entry, never by editing the original.

    quantity is a POSITIVE magnitude of the component issued; unit_cost is the
    fixed-point cost it was consumed at. inventory_txn_id / journal_entry_id are
    soft links back to the SYERP movement ledger row and journal entry this
    issue generated, so the audit trail from consumption to GL is traceable.
    """

    __tablename__ = "mousse_work_order_issue"

    # --- Primary key — UUID string (non-enumerable ledger row) -------------
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Links -------------------------------------------------------------
    work_order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("mousse_work_order.id"), nullable=False, index=True
    )
    component_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("mousse_work_order_component.id"), nullable=False
    )
    item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("syerp_inventory_item.id"), nullable=False
    )
    location_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("syerp_stock_location.id"), nullable=False
    )

    # --- Amounts (D-11) — fixed-point, never float -------------------------
    # quantity: POSITIVE magnitude issued
    quantity: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6))

    # --- Soft links to the SYERP hub the issue generated -------------------
    # syerp_inventory_txn.id is a String(36) uuid PK (see syerp/models.py) —
    # NOT an int; the FK column type mirrors it.
    inventory_txn_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("syerp_inventory_txn.id")
    )
    journal_entry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("syerp_journal_entry.id")
    )

    # --- Provenance / audit ------------------------------------------------
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
