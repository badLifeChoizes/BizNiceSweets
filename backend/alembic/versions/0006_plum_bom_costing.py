"""add plum_bom_item, plum_avl_link, plum_avl_price_break tables + cost columns on plum_part_revision

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-30 00:00:00.000000+00:00

Phase 6 — PLUM BOM, Costing & Integration.

Creates three new tables and extends plum_part_revision with five cost columns.
All downstream BOM, AVL, and costing services depend on these tables/columns.

Tables added:
  plum_bom_item        — BOM directed edge: parent_revision → child_part (D-01/D-02/D-04)
  plum_avl_link        — Approved Vendor List link: part → syerp_partner (D-11/D-13)
  plum_avl_price_break — Quantity price-break rows per AVL link (D-11)

Columns added to plum_part_revision:
  material_cost             — Numeric(18,6), nullable (D-06)
  sale_price                — Numeric(18,6), nullable (D-09)
  released_cost_snapshot    — Numeric(18,6), nullable (D-14)
  selected_vendor_link_id   — String(36) FK plum_avl_link.id SET NULL (D-12)
  selected_price_break_index — Integer, nullable (D-12)

Migration hand-authored from ORM models (app/modules/plum/models.py) —
no live DB at plan time; structure matches the model definitions exactly.
Chains to down_revision "0005" (PLUM base tables) so Alembic single-history
is maintained and FK ordering is correct.

Upgrade zones:
  Zone 1: op.add_column five cost columns on plum_part_revision
  Zone 2: op.create_table for plum_avl_link, plum_avl_price_break, plum_bom_item
  Zone 3: op.create_foreign_key selected_vendor_link_id → plum_avl_link.id (SET NULL)
          (Zone 3 because plum_avl_link must exist before the FK can be created)

Threat mitigations baked into schema:
  T-06-01: FK plum_part_revision.selected_vendor_link_id → plum_avl_link.id
           with ondelete=SET NULL prevents dangling references on AVL delete.
  T-06-02: FK plum_avl_price_break.avl_link_id → plum_avl_link.id
           with ondelete=CASCADE auto-removes orphan price-break rows.
  T-06-03: UniqueConstraint(parent_revision_id, child_part_id) on plum_bom_item
           and UniqueConstraint(part_id, vendor_id) on plum_avl_link prevent
           duplicate BOM/AVL rows at the DB level.
  T-06-04: Numeric(18,6) for all cost/qty columns (not float) — exact fixed-point.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Zone 1: Extend plum_part_revision with cost columns (D-06/D-09/D-12/D-14) ──
    # These columns are added before creating plum_avl_link so that if a partial
    # upgrade fails, the rollback Zone does not need to worry about FK ordering
    # for the SET NULL FK (which is only added in Zone 3).
    op.add_column(
        "plum_part_revision",
        sa.Column("material_cost", sa.Numeric(18, 6), nullable=True),
    )
    op.add_column(
        "plum_part_revision",
        sa.Column("sale_price", sa.Numeric(18, 6), nullable=True),
    )
    op.add_column(
        "plum_part_revision",
        sa.Column("released_cost_snapshot", sa.Numeric(18, 6), nullable=True),
    )
    op.add_column(
        "plum_part_revision",
        sa.Column("selected_vendor_link_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "plum_part_revision",
        sa.Column("selected_price_break_index", sa.Integer(), nullable=True),
    )

    # ── Zone 2: Create new tables ──────────────────────────────────────────
    # Order: plum_avl_link first (plum_avl_price_break FKs to it;
    #        plum_bom_item has no dependency on either AVL table).

    # plum_avl_link — Approved Vendor List link (D-11/D-13)
    # Cross-module FK: vendor_id → syerp_partner.id (SYERP-as-hub).
    op.create_table(
        "plum_avl_link",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("part_id", sa.String(length=36), nullable=False),
        sa.Column("vendor_id", sa.String(length=36), nullable=False),
        sa.Column("vendor_part_number", sa.String(length=100), nullable=True),
        sa.Column(
            "preferred",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
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
        sa.ForeignKeyConstraint(
            ["part_id"],
            ["plum_part.id"],
            name="fk_plum_avl_link_part_id",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["syerp_partner.id"],
            name="fk_plum_avl_link_vendor_id",
        ),
        # T-06-03: prevent duplicate vendor per part at DB level
        sa.UniqueConstraint("part_id", "vendor_id", name="uq_plum_avl_link_part_vendor"),
    )

    # Indexes for plum_avl_link hot paths
    op.create_index("ix_plum_avl_link_part_id", "plum_avl_link", ["part_id"], unique=False)
    op.create_index("ix_plum_avl_link_vendor_id", "plum_avl_link", ["vendor_id"], unique=False)

    # plum_avl_price_break — quantity price-break rows per AVL link (D-11)
    # avl_link_id FK uses ondelete=CASCADE (T-06-02) — orphan rows auto-removed.
    op.create_table(
        "plum_avl_price_break",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("avl_link_id", sa.String(length=36), nullable=False),
        sa.Column(
            "qty_threshold",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("unit_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("lead_days", sa.Integer(), nullable=True),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.ForeignKeyConstraint(
            ["avl_link_id"],
            ["plum_avl_link.id"],
            name="fk_plum_avl_price_break_avl_link_id",
            ondelete="CASCADE",
        ),
    )

    # Index for plum_avl_price_break hot paths
    op.create_index(
        "ix_plum_avl_price_break_avl_link_id",
        "plum_avl_price_break",
        ["avl_link_id"],
        unique=False,
    )

    # plum_bom_item — BOM directed edge: parent_revision → child_part (D-01/D-02/D-04)
    op.create_table(
        "plum_bom_item",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("parent_revision_id", sa.String(length=36), nullable=False),
        sa.Column("child_part_id", sa.String(length=36), nullable=False),
        sa.Column("qty", sa.Numeric(18, 6), nullable=False),
        sa.Column("ref_des", sa.String(length=500), nullable=True),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
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
        sa.ForeignKeyConstraint(
            ["parent_revision_id"],
            ["plum_part_revision.id"],
            name="fk_plum_bom_item_parent_revision_id",
        ),
        sa.ForeignKeyConstraint(
            ["child_part_id"],
            ["plum_part.id"],
            name="fk_plum_bom_item_child_part_id",
        ),
        # T-06-03: prevent duplicate child under same revision at DB level
        sa.UniqueConstraint(
            "parent_revision_id",
            "child_part_id",
            name="uq_plum_bom_item_parent_child",
        ),
    )

    # Indexes for plum_bom_item hot paths
    op.create_index(
        "ix_plum_bom_item_parent_revision_id",
        "plum_bom_item",
        ["parent_revision_id"],
        unique=False,
    )
    op.create_index(
        "ix_plum_bom_item_child_part_id",
        "plum_bom_item",
        ["child_part_id"],
        unique=False,
    )

    # ── Zone 3: Add FK from plum_part_revision.selected_vendor_link_id ──────
    # Must be in Zone 3 because plum_avl_link (the FK target) is created in Zone 2.
    # ondelete=SET NULL (T-06-01): deleting an AVL link nulls the revision's cost pointer
    # rather than cascading a delete or leaving a dangling reference.
    op.create_foreign_key(
        "fk_plum_revision_selected_avl_link",
        "plum_part_revision",
        "plum_avl_link",
        ["selected_vendor_link_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Reverse of upgrade — drop in reverse dependency order.

    # Zone 3 first: drop the cross-table FK from plum_part_revision → plum_avl_link
    op.drop_constraint(
        "fk_plum_revision_selected_avl_link",
        "plum_part_revision",
        type_="foreignkey",
    )

    # Zone 2: drop tables in reverse FK order
    # plum_bom_item has no dependency on AVL tables — drop it first for clarity
    op.drop_index("ix_plum_bom_item_child_part_id", table_name="plum_bom_item")
    op.drop_index("ix_plum_bom_item_parent_revision_id", table_name="plum_bom_item")
    op.drop_table("plum_bom_item")

    # plum_avl_price_break FKs to plum_avl_link — drop price_break before avl_link
    op.drop_index("ix_plum_avl_price_break_avl_link_id", table_name="plum_avl_price_break")
    op.drop_table("plum_avl_price_break")

    op.drop_index("ix_plum_avl_link_vendor_id", table_name="plum_avl_link")
    op.drop_index("ix_plum_avl_link_part_id", table_name="plum_avl_link")
    op.drop_table("plum_avl_link")

    # Zone 1: drop added columns in reverse order
    op.drop_column("plum_part_revision", "selected_price_break_index")
    op.drop_column("plum_part_revision", "selected_vendor_link_id")
    op.drop_column("plum_part_revision", "released_cost_snapshot")
    op.drop_column("plum_part_revision", "sale_price")
    op.drop_column("plum_part_revision", "material_cost")
