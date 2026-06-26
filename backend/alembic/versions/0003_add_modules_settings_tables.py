"""add_modules_settings_tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-26 00:00:00.000000+00:00

Phase 3 — App Shell & Settings.

Creates two new platform tables in a single revision within the existing
Alembic history (Phase 1 D-03 single history maintained).

Tables:
  modules   — DB-backed runtime enable/disable state for each suite (CORE-07)
              Natural string PK (`key` = MODULE_NAME), enabled/always_on flags.
              SYERP seeds with always_on=true; backend rejects disable of
              always-on modules (D-08).
  settings  — Key-value settings store for company identity + locale defaults
              (CORE-06). Surrogate int PK for D-13 per-user groundwork.
              Partial unique index `uq_settings_global` enforces uniqueness for
              global rows (owner_id IS NULL) without breaking PostgreSQL NULL
              semantics (NULL != NULL in standard UNIQUE constraints — Pitfall 5).

Migration hand-authored from ORM models — no live DB at plan time (0002 convention).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # modules  (CORE-07 — runtime enable/disable state per suite)
    # Natural string PK: key matches MODULE_NAME in each module's __init__.py
    # ------------------------------------------------------------------
    op.create_table(
        "modules",
        sa.Column("key", sa.String(length=50), primary_key=True, nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        # enabled: admin-togglable; server_default=true (new rows are on by default)
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        # always_on: platform-bundled flag; SYERP=true; never set via API (D-08)
        sa.Column(
            "always_on",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        # sort_order: sidebar display order; lower = higher in list
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("100"),
        ),
    )

    # ------------------------------------------------------------------
    # settings  (CORE-06 — key-value store for company info + locale defaults)
    # Surrogate int PK avoids a breaking migration when per-user rows arrive (D-13)
    # ------------------------------------------------------------------
    op.create_table(
        "settings",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        # Dotted key convention: "company.name", "locale.currency", etc.
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        # Type hint for deserialization: "str", "bool", "int", "json"
        sa.Column(
            "value_type",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'str'"),
        ),
        # Logical grouping for the admin UI: "company", "locale", "feature"
        sa.Column(
            "category",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'general'"),
        ),
        # D-13 groundwork: "global" in v1; "user" scope added later without rewrite
        sa.Column(
            "scope",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'global'"),
        ),
        # D-13 groundwork: None for global rows; user.id for per-user overrides later
        # Mirrors AuditLog.actor_id nullable-string pattern
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
    )

    # Non-unique index on key for fast lookups (SELECT WHERE key=... is the hot path)
    op.create_index("ix_settings_key", "settings", ["key"], unique=False)

    # Partial unique index for global settings: UNIQUE(key) WHERE owner_id IS NULL.
    # Standard UNIQUE(key, owner_id) does NOT work because PostgreSQL treats
    # NULL != NULL — two rows with key='company.name' and owner_id=NULL would
    # both pass the constraint. The partial index closes this gap (Pitfall 5).
    op.create_index(
        "uq_settings_global",
        "settings",
        ["key"],
        unique=True,
        postgresql_where=sa.text("owner_id IS NULL"),
    )


def downgrade() -> None:
    # Drop settings indexes before dropping the table
    op.drop_index("uq_settings_global", table_name="settings")
    op.drop_index("ix_settings_key", table_name="settings")
    op.drop_table("settings")
    # modules has no indexes beyond the primary key
    op.drop_table("modules")
