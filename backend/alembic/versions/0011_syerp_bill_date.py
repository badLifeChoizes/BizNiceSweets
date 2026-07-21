# ABOUTME: Alembic migration 0011 — adds syerp_bill.bill_date (invoice date).
# ABOUTME: Date NOT NULL; existing rows backfilled to created_at::date so AP
# ABOUTME: aging has a real date basis — Phase 9c; hand-authored.
"""add syerp_bill.bill_date

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-12 00:00:00.000000+00:00

Phase 9c — SYERP AP aging: gives every vendor bill a real invoice date to
bucket from (0/30/60/90+), distinct from created_at (D-P9c-1).

bill_date is Date NOT NULL. Because syerp_bill may already hold rows (Phase 9b),
adding a NOT NULL column in one step would fail; instead the column lands
nullable, existing rows are backfilled server-side to created_at::date (the
D-P9c-1 default for pre-existing bills), then the NOT NULL constraint is
applied. New rows always supply bill_date from create_bill (defaulting to
today), so no Python/server default is carried on the model.

Chains to down_revision "0010" (the AP bill/line + payment/allocation tables),
so syerp_bill already exists when this runs.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # syerp_bill.bill_date  (D-P9c-1)
    # NOT NULL on a populated table needs three steps: add nullable, backfill
    # existing rows to created_at::date (the pre-existing-bill default), then
    # tighten to NOT NULL.
    # ------------------------------------------------------------------
    op.add_column("syerp_bill", sa.Column("bill_date", sa.Date(), nullable=True))
    op.execute(
        "UPDATE syerp_bill SET bill_date = created_at::date WHERE bill_date IS NULL"
    )
    op.alter_column("syerp_bill", "bill_date", nullable=False)


def downgrade() -> None:
    op.drop_column("syerp_bill", "bill_date")
