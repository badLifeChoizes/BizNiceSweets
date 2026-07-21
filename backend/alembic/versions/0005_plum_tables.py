"""add plum_part, plum_part_revision, plum_classification_tag, plum_part_tag tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-28 00:00:00.000000+00:00

Phase 5 — PLUM Parts & Revisions.

Creates the four tables for the PLUM Product Lifecycle Management module.
All downstream PLUM services depend on these tables.

Tables:
  plum_classification_tag — seeded tag vocabulary (D-12)
  plum_part               — stable part header (D-01/D-02)
  plum_part_tag           — join table: part ↔ classification tag (D-12)
  plum_part_revision      — versioned revision snapshot (D-01/D-02/D-07)

Migration hand-authored from ORM models (app/modules/plum/models.py) —
no live DB at plan time; structure matches the model definitions exactly.
After running `podman-compose up`, `alembic upgrade head` applies this
migration to the live PostgreSQL instance.

Threat mitigations baked into schema:
  T-05-01: Partial unique index `uq_plum_part_one_released` enforces at most
           one Released revision per part at the DB level (Pitfall 3).
           postgresql_where="status = 'released'" prevents race conditions
           where two concurrent releases would create two Released revisions.
  T-05-03: Migration chains to down_revision "0004" (SYERP tables) so Alembic
           single-history is maintained and FK ordering is correct.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # plum_classification_tag  (D-12)
    # Seeded lookup table for part classification tags.
    # Integer PK (autoincrement) — mirrors GLAccount convention for seeded
    # lookup tables. Vocabulary is editable via plum.tag_vocabulary_editable.
    # ------------------------------------------------------------------
    op.create_table(
        "plum_classification_tag",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("name", name="uq_plum_classification_tag_name"),
    )

    # ------------------------------------------------------------------
    # plum_part  (D-01/D-02/D-06/D-11)
    # Stable part header. part_number is unique and auto-generated (D-06).
    # active=False is soft-delete (D-11); archived parts hidden by default.
    # UUID string PK (mirrors syerp_partner convention).
    # ------------------------------------------------------------------
    op.create_table(
        "plum_part",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("part_number", sa.String(length=50), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
        sa.UniqueConstraint("part_number", name="uq_plum_part_number"),
    )

    # Indexes for plum_part hot paths
    op.create_index("ix_plum_part_part_number", "plum_part", ["part_number"], unique=True)
    op.create_index("ix_plum_part_active", "plum_part", ["active"], unique=False)

    # ------------------------------------------------------------------
    # plum_part_tag  (D-12)
    # Many-to-many join table: plum_part ↔ plum_classification_tag.
    # Composite PK (part_id, tag_id); no additional columns in v1.
    # ------------------------------------------------------------------
    op.create_table(
        "plum_part_tag",
        sa.Column("part_id", sa.String(length=36), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("part_id", "tag_id", name="pk_plum_part_tag"),
        sa.ForeignKeyConstraint(
            ["part_id"],
            ["plum_part.id"],
            name="fk_plum_part_tag_part_id",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["plum_classification_tag.id"],
            name="fk_plum_part_tag_tag_id",
        ),
    )

    # ------------------------------------------------------------------
    # plum_part_revision  (D-01/D-02/D-07/D-08)
    # Versioned revision snapshot. One or more revisions per part.
    # status FSM: draft → in_review → released → obsolete (D-07).
    # revision_number: per-part integer sequence (1,2,3...) for ordering
    # and "latest revision" resolution via MAX query (RESEARCH Pattern 4).
    # ------------------------------------------------------------------
    op.create_table(
        "plum_part_revision",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("part_id", sa.String(length=36), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("revision_label", sa.String(length=20), nullable=False),
        # status: draft | in_review | released | obsolete (D-07)
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        # Revision-controlled attribute snapshot (D-02)
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("unit_of_measure", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reason_for_revision", sa.Text(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("obsoleted_at", sa.DateTime(timezone=True), nullable=True),
        # FK to parent part
        sa.ForeignKeyConstraint(
            ["part_id"],
            ["plum_part.id"],
            name="fk_plum_part_revision_part_id",
        ),
    )

    # Indexes for plum_part_revision hot paths
    op.create_index(
        "ix_plum_part_revision_part_id",
        "plum_part_revision",
        ["part_id"],
        unique=False,
    )
    op.create_index(
        "ix_plum_part_revision_status",
        "plum_part_revision",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_plum_part_revision_part_id_status",
        "plum_part_revision",
        ["part_id", "status"],
        unique=False,
    )

    # T-05-01: Partial unique index — at most ONE Released revision per part.
    # This DB-level constraint defends the D-08 supersede invariant even against
    # concurrent release races (Pitfall 3 / RESEARCH Open Question 1).
    op.create_index(
        "uq_plum_part_one_released",
        "plum_part_revision",
        ["part_id"],
        unique=True,
        postgresql_where=sa.text("status = 'released'"),
    )


def downgrade() -> None:
    # Drop indexes and partial unique index before dropping the table
    op.drop_index("uq_plum_part_one_released", table_name="plum_part_revision")
    op.drop_index("ix_plum_part_revision_part_id_status", table_name="plum_part_revision")
    op.drop_index("ix_plum_part_revision_status", table_name="plum_part_revision")
    op.drop_index("ix_plum_part_revision_part_id", table_name="plum_part_revision")
    op.drop_table("plum_part_revision")

    op.drop_table("plum_part_tag")

    op.drop_index("ix_plum_part_active", table_name="plum_part")
    op.drop_index("ix_plum_part_part_number", table_name="plum_part")
    op.drop_table("plum_part")

    op.drop_table("plum_classification_tag")
