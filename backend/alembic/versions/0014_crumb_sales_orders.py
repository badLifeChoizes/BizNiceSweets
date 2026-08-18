# ABOUTME: Alembic migration 0014 — creates the CRUMB (CRM) sales-order schema.
# ABOUTME: Adds crumb_sales_order / crumb_sales_order_line — Phase 11b CRUMB
# ABOUTME: sales orders + soft-reservation accumulator; hand-authored.
"""crumb sales orders (0014)

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-17 00:00:00.000000+00:00

Phase 11b — CRUMB (CRM) sales orders (CRUMB-01). A SalesOrder is a confirmed
order header issued to a SYERP partner, optionally originating from a source
quote / opportunity, carrying ordered SalesOrderLines. A line orders a SYERP
stock item (item_id) or a non-stock free-text item (D-V3-16), optionally
referencing a PLUM catalog part for display, and holds a soft-reservation
accumulator qty_reserved (D-V3-11).

Cross-module integration is via foreign keys into the hub, exactly per the
"SYERP as the hub" constraint: partner_id → syerp_partner.id (customer),
item_id → syerp_inventory_item.id (stock item ordered) and plum_part_id →
plum_part.id (the catalog part referenced). source_quote_id → crumb_quote.id
and source_opportunity_id → crumb_opportunity.id soft-link the pipeline origin.
Every hub and intra-CRUMB FK is String(36) uuid (mirrors syerp_partner.id /
plum_part.id) — never Integer. All money/qty columns are fixed-point
Numeric(18,6) (D-11, never float), mirroring SYERP.

Tables:
  crumb_sales_order      — sales order header. String(36) uuid PK. so_number is
                           unique. partner_id FKs syerp_partner.id (required);
                           source_quote_id / source_opportunity_id soft-link the
                           quote / opportunity it originated from (either may be
                           NULL). status walks draft → confirmed → fulfilling →
                           closed | cancelled. order_date is required;
                           required_date is optional.
  crumb_sales_order_line — ordered line. String(36) uuid PK. sales_order_id FKs
                           the header (indexed); item_id FKs syerp_inventory_item.id
                           (NULL for a non-stock line); plum_part_id FKs
                           plum_part.id (display, NULL if none); free-text lines
                           carry description. qty_ordered / unit_price /
                           qty_reserved are Numeric(18,6) (qty_reserved is the
                           reservation accumulator).

Migration hand-authored from ORM models (app/modules/crumb/models.py) —
structure matches the model definitions exactly. Chains to down_revision "0013"
(crumb_crm_pipeline) so Alembic single-history is maintained and the
syerp_partner / crumb_quote / crumb_opportunity / syerp_inventory_item /
plum_part FK targets already exist.

Timestamps carry NO server_default: the model populates created_at in Python
(default=lambda: datetime.now(timezone.utc)), so the schema stays drift-free
against autogenerate for these two tables.

Indexes mirror the models' index=True declarations only: so_number (unique) on
crumb_sales_order; sales_order_id on crumb_sales_order_line.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # crumb_sales_order  (CRUMB-01, Phase 11b)
    # Sales order header; uuid PK. so_number is unique. FKs the hub partner
    # (required) and (optionally) the source quote / opportunity.
    # ------------------------------------------------------------------
    op.create_table(
        "crumb_sales_order",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Identity
        sa.Column("so_number", sa.String(length=30), nullable=False),

        # Links
        sa.Column("partner_id", sa.String(length=36), nullable=False),
        # source_quote_id — quote this order was created from; NULL if standalone
        sa.Column("source_quote_id", sa.String(length=36), nullable=True),
        # source_opportunity_id — opportunity this order is against; NULL if standalone
        sa.Column("source_opportunity_id", sa.String(length=36), nullable=True),

        # status: order lifecycle — draft | confirmed | fulfilling | closed | cancelled
        sa.Column("status", sa.String(length=30), nullable=False),

        # Timing
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("required_date", sa.Date(), nullable=True),

        # Provenance / audit — created_at populated Python-side (no server_default)
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),

        # partner_id — FK into syerp_partner.id (the hub customer)
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["syerp_partner.id"],
            name="fk_crumb_sales_order_partner_id",
        ),
        # source_quote_id — FK into crumb_quote.id (the originating quote)
        sa.ForeignKeyConstraint(
            ["source_quote_id"],
            ["crumb_quote.id"],
            name="fk_crumb_sales_order_source_quote_id",
        ),
        # source_opportunity_id — FK into crumb_opportunity.id (the originating opportunity)
        sa.ForeignKeyConstraint(
            ["source_opportunity_id"],
            ["crumb_opportunity.id"],
            name="fk_crumb_sales_order_source_opportunity_id",
        ),
    )

    # Unique index on so_number (mirrors model unique=True, index=True)
    op.create_index(
        "ix_crumb_sales_order_so_number",
        "crumb_sales_order",
        ["so_number"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # crumb_sales_order_line  (CRUMB-01, Phase 11b)
    # Ordered line; uuid PK. FKs the sales order header (indexed) and
    # (optionally) a SYERP stock item and a PLUM part; non-stock lines carry
    # description instead. qty_reserved is the soft-reservation accumulator.
    # ------------------------------------------------------------------
    op.create_table(
        "crumb_sales_order_line",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Links
        sa.Column("sales_order_id", sa.String(length=36), nullable=False),
        # item_id — SYERP stock item ordered; NULL for a non-stock line (D-V3-16)
        sa.Column("item_id", sa.String(length=36), nullable=True),
        # plum_part_id — catalog part referenced by this line (display); NULL if none
        sa.Column("plum_part_id", sa.String(length=36), nullable=True),

        # description: free-text / display item; carries the item for a non-stock line
        sa.Column("description", sa.String(), nullable=True),

        # Amounts (D-11) — fixed-point, never float
        sa.Column("qty_ordered", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=18, scale=6), nullable=False),
        # qty_reserved: reservation accumulator (D-V3-11); starts at zero
        sa.Column("qty_reserved", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),

        # sales_order_id — FK into crumb_sales_order.id (the header)
        sa.ForeignKeyConstraint(
            ["sales_order_id"],
            ["crumb_sales_order.id"],
            name="fk_crumb_sales_order_line_sales_order_id",
        ),
        # item_id — FK into syerp_inventory_item.id (the stock item ordered)
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["syerp_inventory_item.id"],
            name="fk_crumb_sales_order_line_item_id",
        ),
        # plum_part_id — FK into plum_part.id (the catalog part referenced)
        sa.ForeignKeyConstraint(
            ["plum_part_id"],
            ["plum_part.id"],
            name="fk_crumb_sales_order_line_plum_part_id",
        ),
    )

    # Index for crumb_sales_order_line hot path (lines per sales order)
    op.create_index(
        "ix_crumb_sales_order_line_sales_order_id",
        "crumb_sales_order_line",
        ["sales_order_id"],
        unique=False,
    )


def downgrade() -> None:
    # Reverse dependency order. Drop the line first (it FKs the header, the
    # stock item and plum_part), then the header.
    op.drop_index(
        "ix_crumb_sales_order_line_sales_order_id",
        table_name="crumb_sales_order_line",
    )
    op.drop_table("crumb_sales_order_line")

    op.drop_index(
        "ix_crumb_sales_order_so_number", table_name="crumb_sales_order"
    )
    op.drop_table("crumb_sales_order")
