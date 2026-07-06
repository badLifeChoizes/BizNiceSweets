# ABOUTME: Alembic migration 0008 — creates the SYERP purchasing schema.
# ABOUTME: Adds syerp_purchase_order (header) and syerp_purchase_order_line
# ABOUTME: (line items) — Phase 8; hand-authored from the ORM models.
"""add syerp purchase order/line tables

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-06 00:00:00.000000+00:00

Phase 8 — SYERP Inventory & Purchasing.

Creates the two tables the purchasing service builds on. A PurchaseOrder is a
request to buy goods from a vendor; each PurchaseOrderLine records an ordered
item, its cost, and a running qty_received accumulator (Decision 5) that
receiving increments as goods arrive.

Tables:
  syerp_purchase_order       — PO header. String(36) uuid PK (mirrors
                               syerp_partner). vendor_id FKs syerp_partner.id.
                               status walks draft|approved|partially_received|
                               received|closed (default draft). approved_at/
                               approved_by capture the approver identity
                               (D-P8-10); NULL until approved.
  syerp_purchase_order_line  — PO line. String(36) uuid PK. po_id FKs the
                               header; item_id FKs syerp_inventory_item.id.
                               qty_ordered/unit_cost/qty_received are fixed-point
                               Numeric(18,6) (Decision 5 / D-11, never float);
                               qty_received defaults to 0. need_by_date is a
                               nullable date-only requested delivery date.

Migration hand-authored from ORM models (app/modules/syerp/models.py) —
structure matches the model definitions exactly. Chains to down_revision
"0007" (SYERP inventory) so Alembic single-history is maintained and the
syerp_partner / syerp_inventory_item FK targets already exist.

Threat mitigations baked into schema:
  UniqueConstraint on syerp_purchase_order.po_number (race-safe at DB level).
  FK vendor_id prevents POs against a non-existent partner; FK po_id/item_id on
  the line prevent orphan lines and lines against non-existent items.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # syerp_purchase_order  (D-P8-10)
    # PO header; uuid PK (mirrors syerp_partner).
    # ------------------------------------------------------------------
    op.create_table(
        "syerp_purchase_order",
        # Primary key — UUID string (mirrors syerp_partner.id)
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Identity
        sa.Column("po_number", sa.String(length=20), nullable=False),
        sa.Column("vendor_id", sa.String(length=36), nullable=False),

        # status: draft | approved | partially_received | received | closed
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),

        # Approval (D-P8-10) — NULL until approved
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(length=36), nullable=True),

        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),

        # Unique constraint on po_number is the race-safe DB-level guard
        sa.UniqueConstraint("po_number", name="uq_syerp_purchase_order_po_number"),
        # vendor_id — FK into syerp_partner.id (the vendor purchased from)
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["syerp_partner.id"],
            name="fk_syerp_purchase_order_vendor_id",
        ),
    )

    # Indexes for syerp_purchase_order hot paths
    op.create_index(
        "ix_syerp_purchase_order_po_number",
        "syerp_purchase_order",
        ["po_number"],
        unique=True,
    )
    op.create_index(
        "ix_syerp_purchase_order_vendor_id",
        "syerp_purchase_order",
        ["vendor_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # syerp_purchase_order_line  (Decision 5)
    # PO line; uuid PK. qty_received is a running accumulator.
    # ------------------------------------------------------------------
    op.create_table(
        "syerp_purchase_order_line",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Links
        sa.Column("po_id", sa.String(length=36), nullable=False),
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),

        # Quantities & cost (Decision 5, D-11) — fixed-point, never float
        sa.Column("qty_ordered", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column(
            "qty_received",
            sa.Numeric(precision=18, scale=6),
            nullable=False,
            server_default=sa.text("0"),
        ),

        # need_by_date: optional requested delivery date (date-only)
        sa.Column("need_by_date", sa.Date(), nullable=True),

        # po_id — FK into the header
        sa.ForeignKeyConstraint(
            ["po_id"],
            ["syerp_purchase_order.id"],
            name="fk_syerp_purchase_order_line_po_id",
        ),
        # item_id — FK into syerp_inventory_item.id
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["syerp_inventory_item.id"],
            name="fk_syerp_purchase_order_line_item_id",
        ),
    )

    # Index for syerp_purchase_order_line hot path (line roll-up per PO)
    op.create_index(
        "ix_syerp_purchase_order_line_po_id",
        "syerp_purchase_order_line",
        ["po_id"],
        unique=False,
    )


def downgrade() -> None:
    # Drop the line first (it FKs into the header and inventory item)
    op.drop_index(
        "ix_syerp_purchase_order_line_po_id", table_name="syerp_purchase_order_line"
    )
    op.drop_table("syerp_purchase_order_line")

    # Drop the header last (the line referenced it)
    op.drop_index("ix_syerp_purchase_order_vendor_id", table_name="syerp_purchase_order")
    op.drop_index("ix_syerp_purchase_order_po_number", table_name="syerp_purchase_order")
    op.drop_table("syerp_purchase_order")
