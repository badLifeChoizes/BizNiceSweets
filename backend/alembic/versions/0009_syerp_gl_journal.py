# ABOUTME: Alembic migration 0009 — creates the SYERP GL journal schema.
# ABOUTME: Adds syerp_journal_entry (header) and syerp_journal_line (legs) —
# ABOUTME: Phase 9a append-only posting engine; hand-authored from the ORM models.
"""add syerp journal entry/line tables

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-11 00:00:00.000000+00:00

Phase 9a — SYERP GL posting engine (D-P9a-1).

Creates the append-only general-journal ledger the posting engine builds on. A
JournalEntry is one immutable double-entry posting; each JournalLine records a
single debit-or-credit leg against a GL account. Corrections are made by
posting a reversing entry (never by edit/delete); the reversing entry points
back at the original via reversal_of_id.

Tables:
  syerp_journal_entry  — journal header. String(36) uuid PK (mirrors the other
                         non-enumerable ledger rows). entry_date is a date-only
                         posting date; memo is optional. source_type/source_id
                         are a soft polymorphic link to the originating document
                         (no FK — mirrors syerp_inventory_txn.source_*).
                         reversal_of_id is a self-FK set on a reversing entry;
                         NULL on ordinary entries. actor_id records who posted;
                         created_at defaults to now(). There is deliberately no
                         mutable status column — append-only.
  syerp_journal_line   — journal leg. String(36) uuid PK. entry_id FKs the
                         header; account_id FKs syerp_gl_account.id. debit/credit
                         are fixed-point Numeric(18,6) (D-11, never float) and
                         nullable — exactly one side is non-null per line; the
                         single-side + non-negative + balanced-entry invariants
                         live in the service layer (D-P9a-1).

Migration hand-authored from ORM models (app/modules/syerp/models.py) —
structure matches the model definitions exactly. Chains to down_revision
"0008" (SYERP purchasing) so Alembic single-history is maintained and the
syerp_gl_account FK target already exists.

Indexes mirror the model's index=True declarations only: entry_id and
account_id on the line. entry_date carries no index (the committed model does
not declare one) so the schema stays drift-free against autogenerate.

Threat mitigations baked into schema:
  FK entry_id prevents orphan lines against a non-existent entry; FK account_id
  prevents lines against a non-existent GL account; self-FK reversal_of_id
  prevents a reversal pointing at a non-existent original entry.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # syerp_journal_entry  (D-P9a-1)
    # Append-only journal header; uuid PK (mirrors the other ledger rows).
    # ------------------------------------------------------------------
    op.create_table(
        "syerp_journal_entry",
        # Primary key — UUID string (non-enumerable ledger row)
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Posting details
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("memo", sa.String(length=500), nullable=True),

        # source_type / source_id: soft polymorphic link (no FK — mirrors txn)
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("source_id", sa.String(length=36), nullable=True),

        # reversal_of_id: self-FK set on a reversing entry; NULL on ordinary ones
        sa.Column("reversal_of_id", sa.String(length=36), nullable=True),

        # Provenance / audit
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),

        # reversal_of_id — self-FK into syerp_journal_entry.id
        sa.ForeignKeyConstraint(
            ["reversal_of_id"],
            ["syerp_journal_entry.id"],
            name="fk_syerp_journal_entry_reversal_of_id",
        ),
    )

    # ------------------------------------------------------------------
    # syerp_journal_line  (D-P9a-1)
    # Append-only journal leg; uuid PK. Exactly one of debit/credit non-null.
    # ------------------------------------------------------------------
    op.create_table(
        "syerp_journal_line",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Links
        sa.Column("entry_id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),

        # Amounts (D-11) — fixed-point, never float; exactly one side non-null
        sa.Column("debit", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("credit", sa.Numeric(precision=18, scale=6), nullable=True),

        # entry_id — FK into the header
        sa.ForeignKeyConstraint(
            ["entry_id"],
            ["syerp_journal_entry.id"],
            name="fk_syerp_journal_line_entry_id",
        ),
        # account_id — FK into syerp_gl_account.id
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["syerp_gl_account.id"],
            name="fk_syerp_journal_line_account_id",
        ),
    )

    # Indexes for syerp_journal_line hot paths (mirror model index=True)
    op.create_index(
        "ix_syerp_journal_line_entry_id",
        "syerp_journal_line",
        ["entry_id"],
        unique=False,
    )
    op.create_index(
        "ix_syerp_journal_line_account_id",
        "syerp_journal_line",
        ["account_id"],
        unique=False,
    )


def downgrade() -> None:
    # Drop the line first (it FKs into the header and the GL account)
    op.drop_index(
        "ix_syerp_journal_line_account_id", table_name="syerp_journal_line"
    )
    op.drop_index(
        "ix_syerp_journal_line_entry_id", table_name="syerp_journal_line"
    )
    op.drop_table("syerp_journal_line")

    # Drop the header last (the line referenced it; self-FK dropped with it)
    op.drop_table("syerp_journal_entry")
