# ABOUTME: Alembic migration 0016 — creates the GELATO (WMS) outbound shipment
# ABOUTME: schema (gelato_shipment + gelato_shipment_line) and adds the picked/
# ABOUTME: shipped accumulators to crumb_sales_order_line — Phase 12b pick/pack/ship.
"""gelato shipments (0016)

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-18 00:00:00.000000+00:00

Phase 12b — GELATO (Warehouse Management) outbound fulfillment. A Shipment is the
pick/pack/ship record fulfilling a CRUMB sales order out of a SYERP stock
location. It carries lines (one item/qty each) picked from bins into a staging
bin, and at ship posts a GL entry and writes inventory movements.

Cross-module integration is via foreign keys into the hub and CRUMB, exactly per
the "SYERP as the hub" constraint: gelato_shipment.sales_order_id →
crumb_sales_order.id, location_id → syerp_stock_location.id, staging_bin_id →
gelato_bin.id, journal_entry_id → syerp_journal_entry.id (nullable, set at ship);
gelato_shipment_line.shipment_id → gelato_shipment.id, sales_order_line_id →
crumb_sales_order_line.id, item_id → syerp_inventory_item.id, from_bin_id →
gelato_bin.id, inventory_txn_id → syerp_inventory_txn.id (nullable, set at ship).
Like gelato_bin, both tables use an Integer autoincrement PK — shipments are a
controlled, enumerable set managed by warehouse staff.

Tables:
  gelato_shipment       — pick/pack/ship record. Integer PK. sales_order_id FKs
                          crumb_sales_order.id (required, indexed). status walks
                          the pick/pack/ship lifecycle (default "picking"). Created
                          before gelato_shipment_line so the child FK resolves.
  gelato_shipment_line  — a single item/qty picked for a shipment. Integer PK.
                          shipment_id FKs gelato_shipment.id (required, indexed).

Columns added:
  crumb_sales_order_line.qty_picked  — picked accumulator (D-P12b-5).
  crumb_sales_order_line.qty_shipped — shipped accumulator (D-P12b-5).
Both are Numeric(18,6), NOT NULL, server_default="0" so existing rows backfill.

Migration hand-authored from ORM models (app/modules/gelato/models.py plus the
qty_picked / qty_shipped columns on app/modules/crumb/models.py) — structure
matches the model definitions exactly. Chains to down_revision "0015"
(gelato_bins) so the gelato_bin / syerp FK targets already exist and Alembic
single-history is maintained. Table-create order matters: gelato_shipment (parent)
is created before gelato_shipment_line (child) whose FK targets it.

Timestamps carry NO server_default: the model populates created_at in Python
(default=lambda: datetime.now(timezone.utc)), matching the drift-free convention
used by 0014 / 0015.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # gelato_shipment  (GELATO, Phase 12b)
    # Pick/pack/ship record fulfilling a CRUMB sales order; Integer PK.
    # Created before gelato_shipment_line whose shipment_id FK targets it.
    # ------------------------------------------------------------------
    op.create_table(
        "gelato_shipment",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),

        # sales_order_id — CRUMB sales order being fulfilled (required, indexed)
        sa.Column("sales_order_id", sa.String(length=36), nullable=False),
        # location_id — SYERP stock location fulfilling this shipment (required)
        sa.Column("location_id", sa.Integer(), nullable=False),
        # staging_bin_id — gelato_bin picked into (set at pick, required)
        sa.Column("staging_bin_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        # journal_entry_id — GL posting made at ship (nullable until shipped)
        sa.Column("journal_entry_id", sa.String(length=36), nullable=True),
        sa.Column("actor_id", sa.String(length=36), nullable=False),

        # created_at populated Python-side (no server_default)
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),

        sa.ForeignKeyConstraint(
            ["sales_order_id"],
            ["crumb_sales_order.id"],
            name="fk_gelato_shipment_sales_order_id",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["syerp_stock_location.id"],
            name="fk_gelato_shipment_location_id",
        ),
        sa.ForeignKeyConstraint(
            ["staging_bin_id"],
            ["gelato_bin.id"],
            name="fk_gelato_shipment_staging_bin_id",
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"],
            ["syerp_journal_entry.id"],
            name="fk_gelato_shipment_journal_entry_id",
        ),
    )

    # Index on sales_order_id (mirrors model index=True) — shipments-per-order
    op.create_index(
        "ix_gelato_shipment_sales_order_id",
        "gelato_shipment",
        ["sales_order_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # gelato_shipment_line  (GELATO, Phase 12b)
    # One item/qty picked for a shipment; Integer PK. Created after the parent
    # gelato_shipment so its shipment_id FK resolves.
    # ------------------------------------------------------------------
    op.create_table(
        "gelato_shipment_line",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),

        # shipment_id — parent shipment (required, indexed)
        sa.Column("shipment_id", sa.Integer(), nullable=False),
        # sales_order_line_id — CRUMB order line being fulfilled (required)
        sa.Column("sales_order_line_id", sa.String(length=36), nullable=False),
        # item_id — SYERP inventory item picked (required)
        sa.Column("item_id", sa.String(length=36), nullable=False),
        # from_bin_id — gelato_bin the stock was picked from (required)
        sa.Column("from_bin_id", sa.Integer(), nullable=False),
        sa.Column("qty", sa.Numeric(precision=18, scale=6), nullable=False),
        # inventory_txn_id — movement written at ship (nullable until shipped)
        sa.Column("inventory_txn_id", sa.String(length=36), nullable=True),

        # created_at populated Python-side (no server_default)
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),

        sa.ForeignKeyConstraint(
            ["shipment_id"],
            ["gelato_shipment.id"],
            name="fk_gelato_shipment_line_shipment_id",
        ),
        sa.ForeignKeyConstraint(
            ["sales_order_line_id"],
            ["crumb_sales_order_line.id"],
            name="fk_gelato_shipment_line_sales_order_line_id",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["syerp_inventory_item.id"],
            name="fk_gelato_shipment_line_item_id",
        ),
        sa.ForeignKeyConstraint(
            ["from_bin_id"],
            ["gelato_bin.id"],
            name="fk_gelato_shipment_line_from_bin_id",
        ),
        sa.ForeignKeyConstraint(
            ["inventory_txn_id"],
            ["syerp_inventory_txn.id"],
            name="fk_gelato_shipment_line_inventory_txn_id",
        ),
    )

    # Index on shipment_id (mirrors model index=True) — lines-per-shipment roll-up
    op.create_index(
        "ix_gelato_shipment_line_shipment_id",
        "gelato_shipment_line",
        ["shipment_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # crumb_sales_order_line — picked / shipped accumulators (D-P12b-5)
    # NOT NULL with server_default="0" so existing rows backfill to zero.
    # ------------------------------------------------------------------
    op.add_column(
        "crumb_sales_order_line",
        sa.Column(
            "qty_picked",
            sa.Numeric(precision=18, scale=6),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "crumb_sales_order_line",
        sa.Column(
            "qty_shipped",
            sa.Numeric(precision=18, scale=6),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    # Reverse order. Drop the crumb_sales_order_line accumulators, then the
    # child table, then the parent table (child FK references parent).
    op.drop_column("crumb_sales_order_line", "qty_shipped")
    op.drop_column("crumb_sales_order_line", "qty_picked")

    op.drop_index("ix_gelato_shipment_line_shipment_id", table_name="gelato_shipment_line")
    op.drop_table("gelato_shipment_line")

    op.drop_index("ix_gelato_shipment_sales_order_id", table_name="gelato_shipment")
    op.drop_table("gelato_shipment")
