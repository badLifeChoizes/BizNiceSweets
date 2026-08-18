# ABOUTME: Alembic migration 0015 — creates the GELATO (WMS) storage-bin schema.
# ABOUTME: Adds gelato_bin and the syerp_inventory_txn.bin_id soft-link — Phase
# ABOUTME: 12a GELATO directed putaway; hand-authored from the ORM models.
"""gelato bins (0015)

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-17 00:00:00.000000+00:00

Phase 12a — GELATO (Warehouse Management) storage bins (GELATO-01). A Bin is a
named sub-location inside a SYERP stock location that inventory can be directed
into (putaway). It subdivides a syerp_stock_location so on-hand can be resolved
to a precise bin. The append-only movement ledger (syerp_inventory_txn) gains an
optional bin_id FK back to this table so a movement can record which bin it was
directed into.

Cross-module integration is via foreign keys into the hub, exactly per the
"SYERP as the hub" constraint: gelato_bin.location_id → syerp_stock_location.id
(the location this bin subdivides, required) and syerp_inventory_txn.bin_id →
gelato_bin.id (optional; the hub declares the FK by string table-name so it needs
no import of GELATO — D-P12a-3). Unlike the uuid-keyed CRUMB tables, gelato_bin
uses an Integer autoincrement PK, mirroring syerp_stock_location, because bins are
a small, controlled, enumerable set managed by warehouse admins.

Tables:
  gelato_bin  — storage bin. Integer PK. location_id FKs syerp_stock_location.id
                (required, indexed). code is the bin's short label, unique within
                its location (uq_gelato_bin_location_code). description is optional.
                active toggles a bin out of putaway rotation without deleting it.

Column added:
  syerp_inventory_txn.bin_id — optional Integer FK (fk_inventory_txn_bin) into
                gelato_bin.id, indexed. NULL for movements not directed to a bin.

Migration hand-authored from ORM models (app/modules/gelato/models.py plus the
bin_id column on app/modules/syerp/models.py) — structure matches the model
definitions exactly. Chains to down_revision "0014" (crumb_sales_orders) so the
syerp_stock_location / syerp_inventory_txn FK targets already exist and Alembic
single-history is maintained. Table-create order matters: gelato_bin is created
before the bin_id FK that targets it.

Timestamps carry NO server_default: the model populates created_at in Python
(default=lambda: datetime.now(timezone.utc)), matching the drift-free convention
used by 0014.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # gelato_bin  (GELATO-01, Phase 12a)
    # Storage bin subdividing a SYERP stock location; Integer autoincrement PK.
    # code is unique within its location (uq_gelato_bin_location_code). Created
    # before the syerp_inventory_txn.bin_id FK that targets it.
    # ------------------------------------------------------------------
    op.create_table(
        "gelato_bin",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),

        # location_id — SYERP stock location this bin subdivides (required)
        sa.Column("location_id", sa.Integer(), nullable=False),

        # code: bin label, unique within its location
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),

        # created_at populated Python-side (no server_default)
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),

        # location_id — FK into syerp_stock_location.id (the hub location)
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["syerp_stock_location.id"],
            name="fk_gelato_bin_location_id",
        ),
        # code unique within its location (mirrors model UniqueConstraint)
        sa.UniqueConstraint("location_id", "code", name="uq_gelato_bin_location_code"),
    )

    # Index on location_id (mirrors model index=True) — bins-per-location roll-up
    op.create_index(
        "ix_gelato_bin_location_id",
        "gelato_bin",
        ["location_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # syerp_inventory_txn.bin_id  (GELATO-01, Phase 12a)
    # Optional soft-link recording which gelato_bin a movement was directed into.
    # NULL for movements not directed to a bin. Added after gelato_bin exists.
    # ------------------------------------------------------------------
    op.add_column(
        "syerp_inventory_txn",
        sa.Column("bin_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_syerp_inventory_txn_bin_id",
        "syerp_inventory_txn",
        ["bin_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_inventory_txn_bin",
        "syerp_inventory_txn",
        "gelato_bin",
        ["bin_id"],
        ["id"],
    )


def downgrade() -> None:
    # Reverse dependency order. Drop the FK / index / column on
    # syerp_inventory_txn first (it references gelato_bin), then drop the table.
    op.drop_constraint(
        "fk_inventory_txn_bin", "syerp_inventory_txn", type_="foreignkey"
    )
    op.drop_index("ix_syerp_inventory_txn_bin_id", table_name="syerp_inventory_txn")
    op.drop_column("syerp_inventory_txn", "bin_id")

    op.drop_index("ix_gelato_bin_location_id", table_name="gelato_bin")
    op.drop_table("gelato_bin")
