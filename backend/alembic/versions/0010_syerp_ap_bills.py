# ABOUTME: Alembic migration 0010 — creates the SYERP accounts-payable schema.
# ABOUTME: Adds syerp_bill / syerp_bill_line (vendor bills + PO match) and
# ABOUTME: syerp_payment / syerp_payment_allocation — Phase 9b; hand-authored.
"""add syerp bill/line and payment/allocation tables

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-11 00:00:00.000000+00:00

Phase 9b — SYERP accounts payable: vendor bills, three-way PO match, payments
(D-P9b-1/4/5/6).

Creates the four tables the AP service builds on. A Bill is an FSM *document*
(mutable status, mirrors PurchaseOrder) whose BillLines are either `matched`
(linked to a PurchaseOrderLine — three-way PO match, D-P9b-4) or `expense`
(coded directly to a GL account). A Payment is an append-only cash disbursement
whose amount is apportioned across bills by PaymentAllocation rows (D-P9b-6).

Tables:
  syerp_bill              — bill header. String(36) uuid PK (mirrors
                            syerp_purchase_order). bill_number is unique. vendor_id
                            FKs syerp_partner.id. status is a MUTABLE FSM column
                            (draft|posted|paid ...); posted_at is set on GL posting
                            (NULL until posted). actor_id records who created it.
  syerp_bill_line         — bill line. String(36) uuid PK. bill_id FKs the header.
                            line_type is matched|expense. po_line_id FKs
                            syerp_purchase_order_line.id (matched lines; NULL on
                            expense). account_id FKs syerp_gl_account.id (expense
                            lines; NULL on matched). matched_qty/unit_cost/amount
                            are fixed-point Numeric(18,6) (D-11, never float).
  syerp_payment           — payment. String(36) uuid PK. cash_account_id FKs
                            syerp_gl_account.id (the cash account the funds leave).
                            amount is fixed-point Numeric(18,6). Append-only.
  syerp_payment_allocation — payment-to-bill apportionment. String(36) uuid PK.
                            payment_id FKs syerp_payment.id; bill_id FKs
                            syerp_bill.id. amount is fixed-point Numeric(18,6).

Migration hand-authored from ORM models (app/modules/syerp/models.py) —
structure matches the model definitions exactly. Chains to down_revision
"0009" (SYERP GL journal) so Alembic single-history is maintained and the
syerp_partner / syerp_purchase_order_line / syerp_gl_account FK targets already
exist.

Timestamps carry NO server_default: the models populate created_at/updated_at/
posted_at in Python (default=lambda: datetime.now(timezone.utc)), so the schema
stays drift-free against autogenerate for these four tables.

Indexes mirror the models' index=True declarations only: bill_number (unique)
and vendor_id on the bill; bill_id on the line; payment_id and bill_id on the
allocation. syerp_payment declares no indexes.

Threat mitigations baked into schema:
  FK vendor_id prevents bills against a non-existent partner; FK bill_id on the
  line and on the allocation prevents orphan rows; FK po_line_id prevents a
  match against a non-existent PO line; FK account_id/cash_account_id prevent
  postings against a non-existent GL account; FK payment_id prevents an
  allocation against a non-existent payment.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # syerp_bill  (D-P9b-1)
    # AP bill header; uuid PK (mirrors syerp_purchase_order). MUTABLE status.
    # ------------------------------------------------------------------
    op.create_table(
        "syerp_bill",
        # Primary key — UUID string (mirrors syerp_purchase_order.id)
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Identity
        sa.Column("bill_number", sa.String(length=30), nullable=False),
        sa.Column("vendor_id", sa.String(length=36), nullable=False),
        sa.Column("vendor_invoice_ref", sa.String(length=200), nullable=True),

        # status: MUTABLE FSM column (draft | posted | paid ...)
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("memo", sa.String(length=500), nullable=True),

        # posted_at: set when posted to the GL; NULL until posted
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),

        # Provenance / audit — timestamps populated Python-side (no server_default)
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),

        # vendor_id — FK into syerp_partner.id (the vendor being paid)
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["syerp_partner.id"],
            name="fk_syerp_bill_vendor_id",
        ),
    )

    # Indexes for syerp_bill hot paths (mirror model index=True)
    op.create_index(
        "ix_syerp_bill_bill_number",
        "syerp_bill",
        ["bill_number"],
        unique=True,
    )
    op.create_index(
        "ix_syerp_bill_vendor_id",
        "syerp_bill",
        ["vendor_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # syerp_bill_line  (D-P9b-4)
    # Bill line; uuid PK. line_type matched (po_line_id) | expense (account_id).
    # ------------------------------------------------------------------
    op.create_table(
        "syerp_bill_line",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Links
        sa.Column("bill_id", sa.String(length=36), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        # line_type: matched | expense
        sa.Column("line_type", sa.String(length=10), nullable=False),

        # Matched-line fields (line_type == 'matched') — NULL on expense lines
        sa.Column("po_line_id", sa.String(length=36), nullable=True),
        sa.Column("matched_qty", sa.Numeric(precision=18, scale=6), nullable=True),

        # Expense-line fields (line_type == 'expense') — NULL on matched lines
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("unit_cost", sa.Numeric(precision=18, scale=6), nullable=True),

        # Amount (D-11) — fixed-point, never float
        sa.Column("amount", sa.Numeric(precision=18, scale=6), nullable=False),

        # bill_id — FK into the header
        sa.ForeignKeyConstraint(
            ["bill_id"],
            ["syerp_bill.id"],
            name="fk_syerp_bill_line_bill_id",
        ),
        # po_line_id — FK into syerp_purchase_order_line.id (matched lines)
        sa.ForeignKeyConstraint(
            ["po_line_id"],
            ["syerp_purchase_order_line.id"],
            name="fk_syerp_bill_line_po_line_id",
        ),
        # account_id — FK into syerp_gl_account.id (expense lines)
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["syerp_gl_account.id"],
            name="fk_syerp_bill_line_account_id",
        ),
    )

    # Index for syerp_bill_line hot path (line roll-up per bill)
    op.create_index(
        "ix_syerp_bill_line_bill_id",
        "syerp_bill_line",
        ["bill_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # syerp_payment  (D-P9b-5)
    # Append-only cash disbursement; uuid PK. No indexes declared on the model.
    # ------------------------------------------------------------------
    op.create_table(
        "syerp_payment",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Payment details
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("cash_account_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("reference", sa.String(length=200), nullable=True),

        # Provenance / audit — created_at populated Python-side (no server_default)
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),

        # cash_account_id — FK into syerp_gl_account.id (the cash account)
        sa.ForeignKeyConstraint(
            ["cash_account_id"],
            ["syerp_gl_account.id"],
            name="fk_syerp_payment_cash_account_id",
        ),
    )

    # ------------------------------------------------------------------
    # syerp_payment_allocation  (D-P9b-6)
    # Append-only payment-to-bill apportionment; uuid PK.
    # ------------------------------------------------------------------
    op.create_table(
        "syerp_payment_allocation",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Links
        sa.Column("payment_id", sa.String(length=36), nullable=False),
        sa.Column("bill_id", sa.String(length=36), nullable=False),

        # Amount (D-11) — fixed-point, never float
        sa.Column("amount", sa.Numeric(precision=18, scale=6), nullable=False),

        # payment_id — FK into syerp_payment.id
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["syerp_payment.id"],
            name="fk_syerp_payment_allocation_payment_id",
        ),
        # bill_id — FK into syerp_bill.id
        sa.ForeignKeyConstraint(
            ["bill_id"],
            ["syerp_bill.id"],
            name="fk_syerp_payment_allocation_bill_id",
        ),
    )

    # Indexes for syerp_payment_allocation hot paths (mirror model index=True)
    op.create_index(
        "ix_syerp_payment_allocation_payment_id",
        "syerp_payment_allocation",
        ["payment_id"],
        unique=False,
    )
    op.create_index(
        "ix_syerp_payment_allocation_bill_id",
        "syerp_payment_allocation",
        ["bill_id"],
        unique=False,
    )


def downgrade() -> None:
    # Drop the allocation first (it FKs into the payment and the bill)
    op.drop_index(
        "ix_syerp_payment_allocation_bill_id", table_name="syerp_payment_allocation"
    )
    op.drop_index(
        "ix_syerp_payment_allocation_payment_id", table_name="syerp_payment_allocation"
    )
    op.drop_table("syerp_payment_allocation")

    # Drop the payment (the allocation referenced it; no indexes on the model)
    op.drop_table("syerp_payment")

    # Drop the line before the header (it FKs into the bill)
    op.drop_index("ix_syerp_bill_line_bill_id", table_name="syerp_bill_line")
    op.drop_table("syerp_bill_line")

    # Drop the header last (the line and allocation referenced it)
    op.drop_index("ix_syerp_bill_vendor_id", table_name="syerp_bill")
    op.drop_index("ix_syerp_bill_bill_number", table_name="syerp_bill")
    op.drop_table("syerp_bill")
