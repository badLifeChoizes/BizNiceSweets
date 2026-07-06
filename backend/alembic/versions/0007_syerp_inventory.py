# ABOUTME: Alembic migration 0007 — creates the SYERP inventory schema.
# ABOUTME: Adds syerp_inventory_item, syerp_stock_location and the append-only
# ABOUTME: syerp_inventory_txn ledger (Phase 8; hand-authored from the ORM models).
"""add syerp inventory item/location/txn tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-06 00:00:00.000000+00:00

Phase 8 — SYERP Inventory & Purchasing.

Creates the three tables the inventory and purchasing services build on. Every
stock movement is recorded in the append-only syerp_inventory_txn ledger
(AC10-4); on-hand quantities are derived by summing signed quantities.

Tables:
  syerp_inventory_item   — Stock-keeping master record (D-P8-2).
                           String(36) uuid PK (mirrors syerp_partner) — referenced
                           by FKs from txns and PO lines, non-enumerable. Advisory,
                           nullable FK to plum_part.id with NO cascade so inventory
                           keeps working when PLUM is disabled. moving_avg_cost is a
                           fixed-point Numeric(18,6) (Decision 4 / D-11, never float).
  syerp_stock_location   — Physical/logical stock locations.
                           Integer PK (mirrors syerp_gl_account) — small controlled,
                           enumerable set; unique name.
  syerp_inventory_txn    — Append-only stock-movement ledger (AC10-4).
                           String(36) uuid PK; signed quantity; soft polymorphic
                           source link (source_type/source_id, no FK); transfer_group_id
                           pairs the two legs of a transfer.

Migration hand-authored from ORM models (app/modules/syerp/models.py) —
structure matches the model definitions exactly. Chains to down_revision
"0006" (PLUM BOM/costing) so Alembic single-history is maintained and the
plum_part FK target already exists.

Threat mitigations baked into schema:
  UniqueConstraint on syerp_inventory_item.code and syerp_stock_location.name
  (race-safe at DB level). FK item_id/location_id on the ledger prevent txns
  against non-existent items/locations. plum_part_id FK is nullable with no
  ondelete cascade — the link is advisory (D-P8-2).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # syerp_inventory_item  (D-P8-2, Decision 4)
    # Stock-keeping master record; uuid PK (mirrors syerp_partner).
    # ------------------------------------------------------------------
    op.create_table(
        "syerp_inventory_item",
        # Primary key — UUID string (mirrors syerp_partner.id)
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Identity
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("unit_of_measure", sa.String(length=50), nullable=False),

        # PLUM link (D-P8-2) — advisory, nullable, no cascade
        sa.Column("plum_part_id", sa.String(length=36), nullable=True),

        # Costing (Decision 4) — moving-average unit cost, fixed-point
        sa.Column(
            "moving_avg_cost",
            sa.Numeric(precision=18, scale=6),
            nullable=False,
            server_default=sa.text("0"),
        ),

        # active: soft-delete flag
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),

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

        # Unique constraint on code is the race-safe DB-level guard
        sa.UniqueConstraint("code", name="uq_syerp_inventory_item_code"),
        # Advisory PLUM link — nullable FK, no ondelete cascade (D-P8-2)
        sa.ForeignKeyConstraint(
            ["plum_part_id"],
            ["plum_part.id"],
            name="fk_syerp_inventory_item_plum_part_id",
        ),
    )

    # Indexes for syerp_inventory_item hot paths
    op.create_index(
        "ix_syerp_inventory_item_code", "syerp_inventory_item", ["code"], unique=True
    )
    op.create_index(
        "ix_syerp_inventory_item_name", "syerp_inventory_item", ["name"], unique=False
    )
    op.create_index(
        "ix_syerp_inventory_item_active", "syerp_inventory_item", ["active"], unique=False
    )

    # ------------------------------------------------------------------
    # syerp_stock_location
    # Small controlled set of stock locations; Integer PK (mirrors gl_account).
    # ------------------------------------------------------------------
    op.create_table(
        "syerp_stock_location",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),

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

        sa.UniqueConstraint("name", name="uq_syerp_stock_location_name"),
    )

    # Index on name for fast lookups
    op.create_index(
        "ix_syerp_stock_location_name", "syerp_stock_location", ["name"], unique=True
    )

    # ------------------------------------------------------------------
    # syerp_inventory_txn  (AC10-4)
    # Append-only stock-movement ledger; uuid PK. Signed quantity.
    # ------------------------------------------------------------------
    op.create_table(
        "syerp_inventory_txn",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # What moved and where
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),

        # txn_type: receipt | issue | adjustment | transfer
        sa.Column("txn_type", sa.String(length=20), nullable=False),
        # quantity: SIGNED — positive = stock in, negative = stock out
        sa.Column("quantity", sa.Numeric(precision=18, scale=6), nullable=False),
        # unit_cost: fixed-point; nullable
        sa.Column("unit_cost", sa.Numeric(precision=18, scale=6), nullable=True),

        # Provenance / audit
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        # source_type / source_id: soft polymorphic link (no FK — D-P8-2)
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        # transfer_group_id: pairs the two legs (out + in) of a transfer
        sa.Column("transfer_group_id", sa.String(length=36), nullable=True),

        sa.ForeignKeyConstraint(
            ["item_id"],
            ["syerp_inventory_item.id"],
            name="fk_syerp_inventory_txn_item_id",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["syerp_stock_location.id"],
            name="fk_syerp_inventory_txn_location_id",
        ),
    )

    # Indexes for syerp_inventory_txn hot paths (item/location roll-ups, time-ordering)
    op.create_index(
        "ix_syerp_inventory_txn_item_id", "syerp_inventory_txn", ["item_id"], unique=False
    )
    op.create_index(
        "ix_syerp_inventory_txn_location_id",
        "syerp_inventory_txn",
        ["location_id"],
        unique=False,
    )
    op.create_index(
        "ix_syerp_inventory_txn_created_at",
        "syerp_inventory_txn",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    # Drop the ledger first (it FKs into item and location)
    op.drop_index("ix_syerp_inventory_txn_created_at", table_name="syerp_inventory_txn")
    op.drop_index("ix_syerp_inventory_txn_location_id", table_name="syerp_inventory_txn")
    op.drop_index("ix_syerp_inventory_txn_item_id", table_name="syerp_inventory_txn")
    op.drop_table("syerp_inventory_txn")

    # Drop stock location
    op.drop_index("ix_syerp_stock_location_name", table_name="syerp_stock_location")
    op.drop_table("syerp_stock_location")

    # Drop inventory item last (the ledger referenced it)
    op.drop_index("ix_syerp_inventory_item_active", table_name="syerp_inventory_item")
    op.drop_index("ix_syerp_inventory_item_name", table_name="syerp_inventory_item")
    op.drop_index("ix_syerp_inventory_item_code", table_name="syerp_inventory_item")
    op.drop_table("syerp_inventory_item")
