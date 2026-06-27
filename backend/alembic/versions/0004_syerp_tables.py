"""add syerp_partner and syerp_gl_account tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-27 00:00:00.000000+00:00

Phase 4 — SYERP Core Hub.

Creates the two tables that every downstream PLUM/MOUSSE/FLAN module will
foreign-key into. This is a single revision within the existing Alembic
history (single-history policy established in Phase 1).

Tables:
  syerp_partner     — Unified vendor/customer master data (D-01, D-03).
                      Boolean role flags (is_vendor, is_customer) following
                      the res.partner pattern; `active` boolean for soft-delete
                      (D-05); unique code constraint (D-04, T-04-01).
  syerp_gl_account  — Chart-of-accounts skeleton (D-06).
                      Integer PK; self-referential parent_id FK for tree
                      structure; account_type avoids Python/SA `type` conflict.

Migration hand-authored from ORM models (app/modules/syerp/models.py) —
no live DB at plan time; structure matches the model definitions exactly.
After running `podman-compose up`, `alembic upgrade head` applies this
migration to the live PostgreSQL instance.

Threat mitigations baked into schema:
  T-04-01: UniqueConstraint on syerp_partner.code (race-safe at DB level).
  T-04-03: self-referential FK on syerp_gl_account.parent_id (static seed
           uses parent-before-child ordering; no runtime DoS surface).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # syerp_partner  (D-01, D-03, D-04, D-05)
    # Unified vendor/customer master record with boolean role flags.
    # ------------------------------------------------------------------
    op.create_table(
        "syerp_partner",
        # Primary key — UUID string (mirrors auth users.id convention)
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Identity (D-03, D-04)
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_vendor", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_customer", sa.Boolean(), nullable=False, server_default=sa.false()),
        # active: soft-delete flag (D-05); named `active` (not `is_active`)
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),

        # Address block (single embedded, D-03) — all nullable
        sa.Column("addr_line1", sa.String(length=255), nullable=True),
        sa.Column("addr_line2", sa.String(length=255), nullable=True),
        sa.Column("addr_city", sa.String(length=100), nullable=True),
        sa.Column("addr_state", sa.String(length=100), nullable=True),
        sa.Column("addr_postal", sa.String(length=20), nullable=True),
        sa.Column("addr_country", sa.String(length=2), nullable=True),  # ISO 3166-1 alpha-2

        # Contact block (single embedded primary contact, D-03) — all nullable
        sa.Column("contact_name", sa.String(length=255), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=50), nullable=True),

        # Commerce (D-03) — all nullable
        sa.Column("payment_terms", sa.String(length=50), nullable=True),
        sa.Column("tax_id", sa.String(length=50), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),         # ISO 4217
        sa.Column("country_of_origin", sa.String(length=2), nullable=True),  # ISO 3166-1 alpha-2
        sa.Column("notes", sa.Text(), nullable=True),

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

        # T-04-01: unique constraint on code is the race-safe DB-level guard
        sa.UniqueConstraint("code", name="uq_syerp_partner_code"),
    )

    # Indexes for syerp_partner hot paths
    op.create_index("ix_syerp_partner_code", "syerp_partner", ["code"], unique=True)
    op.create_index("ix_syerp_partner_name", "syerp_partner", ["name"], unique=False)
    op.create_index("ix_syerp_partner_active", "syerp_partner", ["active"], unique=False)

    # ------------------------------------------------------------------
    # syerp_gl_account  (D-06)
    # Chart-of-accounts skeleton; seeded idempotently at startup.
    # account_type avoids Python built-in / SA reserved word `type`.
    # ------------------------------------------------------------------
    op.create_table(
        "syerp_gl_account",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        # account_type: ASSET | LIABILITY | EQUITY | REVENUE | EXPENSE
        sa.Column("account_type", sa.String(length=20), nullable=False),
        # parent_id: self-referential FK for tree structure (T-04-03)
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),

        sa.UniqueConstraint("code", name="uq_syerp_gl_account_code"),
        # T-04-03: self-referential FK (parents are inserted before children in seed)
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["syerp_gl_account.id"],
            name="fk_syerp_gl_account_parent_id",
        ),
    )

    # Index on code for fast lookups during seed and API queries
    op.create_index("ix_syerp_gl_account_code", "syerp_gl_account", ["code"], unique=True)


def downgrade() -> None:
    # Drop syerp_gl_account first (it has a self-referential FK — no circular dependency)
    op.drop_index("ix_syerp_gl_account_code", table_name="syerp_gl_account")
    op.drop_table("syerp_gl_account")

    # Drop syerp_partner indexes before table
    op.drop_index("ix_syerp_partner_active", table_name="syerp_partner")
    op.drop_index("ix_syerp_partner_name", table_name="syerp_partner")
    op.drop_index("ix_syerp_partner_code", table_name="syerp_partner")
    op.drop_table("syerp_partner")
