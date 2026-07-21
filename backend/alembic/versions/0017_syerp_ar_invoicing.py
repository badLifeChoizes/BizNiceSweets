# ABOUTME: Alembic migration 0017 — creates the SYERP accounts-receivable schema.
# ABOUTME: Adds syerp_invoice / syerp_invoice_line (customer invoices + SO draw)
# ABOUTME: and syerp_receipt / syerp_receipt_allocation — Phase 13; hand-authored.
"""add syerp invoice/line and receipt/allocation tables + qty_invoiced

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-19 00:00:00.000000+00:00

Phase 13 — SYERP accounts receivable: customer invoices, sales-order draw,
receipts (cash collection) apportioned across invoices (SYERP-13). The sell-side
mirror of the AP schema built in 0010.

Creates the four tables the AR service builds on. An Invoice is an FSM *document*
(mutable status, mirrors Bill) whose InvoiceLines each draw an invoiced_qty off a
CRUMB sales order line (the sell-side analogue of AP's three-way match). A Receipt
is an append-only cash collection whose amount is apportioned across invoices by
ReceiptAllocation rows.

Tables:
  syerp_invoice            — invoice header. String(36) uuid PK (mirrors
                             syerp_bill). invoice_number is unique. customer_id
                             FKs syerp_partner.id. sales_order_id FKs
                             crumb_sales_order.id (NULL for a standalone invoice).
                             status is a MUTABLE FSM column (draft|posted|
                             partially_paid|paid ...); posted_at is set on GL
                             posting (NULL until posted). actor_id records who
                             created it.
  syerp_invoice_line       — invoice line. String(36) uuid PK. invoice_id FKs the
                             header. sales_order_line_id FKs
                             crumb_sales_order_line.id (the line being invoiced).
                             invoiced_qty/unit_price/amount are fixed-point
                             Numeric(18,6) (D-11, never float).
  syerp_receipt            — receipt. String(36) uuid PK. cash_account_id FKs
                             syerp_gl_account.id (the cash account the funds land
                             in). amount is fixed-point Numeric(18,6). Append-only.
  syerp_receipt_allocation — receipt-to-invoice apportionment. String(36) uuid PK.
                             receipt_id FKs syerp_receipt.id; invoice_id FKs
                             syerp_invoice.id. amount is fixed-point Numeric(18,6).

Column added:
  crumb_sales_order_line.qty_invoiced — invoiced accumulator (AR seam).
  Numeric(18,6), NOT NULL, server_default="0" so existing rows backfill to zero.

Migration hand-authored from ORM models (app/modules/syerp/models.py plus the
qty_invoiced column on app/modules/crumb/models.py) — structure matches the model
definitions exactly. Chains to down_revision "0016" (gelato_shipments) so Alembic
single-history is maintained and the syerp_partner / syerp_gl_account /
crumb_sales_order / crumb_sales_order_line FK targets already exist.

Timestamps carry NO server_default: the models populate created_at/updated_at/
posted_at in Python (default=lambda: datetime.now(timezone.utc)), so the schema
stays drift-free against autogenerate for these four tables.

Indexes mirror the models' index=True declarations only: invoice_number (unique)
and customer_id on the invoice; invoice_id on the line; receipt_id and invoice_id
on the allocation. syerp_receipt declares no indexes.

Threat mitigations baked into schema:
  FK customer_id prevents invoices against a non-existent partner; FK
  sales_order_id / sales_order_line_id prevent a draw against a non-existent CRUMB
  order or line; FK invoice_id on the line and on the allocation prevents orphan
  rows; FK cash_account_id prevents postings against a non-existent GL account;
  FK receipt_id prevents an allocation against a non-existent receipt.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # syerp_invoice  (SYERP-13)
    # AR invoice header; uuid PK (mirrors syerp_bill). MUTABLE status.
    # Created before syerp_invoice_line whose invoice_id FK targets it.
    # ------------------------------------------------------------------
    op.create_table(
        "syerp_invoice",
        # Primary key — UUID string (mirrors syerp_bill.id)
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Identity
        sa.Column("invoice_number", sa.String(length=30), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        # sales_order_id — CRUMB sales order this invoice was raised from (NULL on standalone)
        sa.Column("sales_order_id", sa.String(length=36), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=False),

        # status: MUTABLE FSM column (draft | posted | partially_paid | paid ...)
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("memo", sa.String(length=500), nullable=True),

        # posted_at: set when posted to the GL; NULL until posted
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),

        # Provenance / audit — timestamps populated Python-side (no server_default)
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),

        # customer_id — FK into syerp_partner.id (the customer being billed)
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["syerp_partner.id"],
            name="fk_syerp_invoice_customer_id",
        ),
        # sales_order_id — FK into crumb_sales_order.id (the order it was raised from)
        sa.ForeignKeyConstraint(
            ["sales_order_id"],
            ["crumb_sales_order.id"],
            name="fk_syerp_invoice_sales_order_id",
        ),
    )

    # Indexes for syerp_invoice hot paths (mirror model index=True)
    op.create_index(
        "ix_syerp_invoice_invoice_number",
        "syerp_invoice",
        ["invoice_number"],
        unique=True,
    )
    op.create_index(
        "ix_syerp_invoice_customer_id",
        "syerp_invoice",
        ["customer_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # syerp_invoice_line  (SYERP-13)
    # Invoice line; uuid PK. sales_order_line_id draws off a CRUMB SO line.
    # ------------------------------------------------------------------
    op.create_table(
        "syerp_invoice_line",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Links
        sa.Column("invoice_id", sa.String(length=36), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("sales_order_line_id", sa.String(length=36), nullable=False),

        # Quantities / amount (D-11) — fixed-point, never float
        sa.Column("invoiced_qty", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=6), nullable=False),

        # invoice_id — FK into the header
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["syerp_invoice.id"],
            name="fk_syerp_invoice_line_invoice_id",
        ),
        # sales_order_line_id — FK into crumb_sales_order_line.id (line being invoiced)
        sa.ForeignKeyConstraint(
            ["sales_order_line_id"],
            ["crumb_sales_order_line.id"],
            name="fk_syerp_invoice_line_sales_order_line_id",
        ),
    )

    # Index for syerp_invoice_line hot path (line roll-up per invoice)
    op.create_index(
        "ix_syerp_invoice_line_invoice_id",
        "syerp_invoice_line",
        ["invoice_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # syerp_receipt  (SYERP-13)
    # Append-only cash collection; uuid PK. No indexes declared on the model.
    # ------------------------------------------------------------------
    op.create_table(
        "syerp_receipt",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Receipt details
        sa.Column("receipt_date", sa.Date(), nullable=False),
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
            name="fk_syerp_receipt_cash_account_id",
        ),
    )

    # ------------------------------------------------------------------
    # syerp_receipt_allocation  (SYERP-13)
    # Append-only receipt-to-invoice apportionment; uuid PK.
    # ------------------------------------------------------------------
    op.create_table(
        "syerp_receipt_allocation",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Links
        sa.Column("receipt_id", sa.String(length=36), nullable=False),
        sa.Column("invoice_id", sa.String(length=36), nullable=False),

        # Amount (D-11) — fixed-point, never float
        sa.Column("amount", sa.Numeric(precision=18, scale=6), nullable=False),

        # receipt_id — FK into syerp_receipt.id
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["syerp_receipt.id"],
            name="fk_syerp_receipt_allocation_receipt_id",
        ),
        # invoice_id — FK into syerp_invoice.id
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["syerp_invoice.id"],
            name="fk_syerp_receipt_allocation_invoice_id",
        ),
    )

    # Indexes for syerp_receipt_allocation hot paths (mirror model index=True)
    op.create_index(
        "ix_syerp_receipt_allocation_receipt_id",
        "syerp_receipt_allocation",
        ["receipt_id"],
        unique=False,
    )
    op.create_index(
        "ix_syerp_receipt_allocation_invoice_id",
        "syerp_receipt_allocation",
        ["invoice_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # crumb_sales_order_line — invoiced accumulator (AR seam)
    # NOT NULL with server_default="0" so existing rows backfill to zero.
    # ------------------------------------------------------------------
    op.add_column(
        "crumb_sales_order_line",
        sa.Column(
            "qty_invoiced",
            sa.Numeric(precision=18, scale=6),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    # Reverse order. Drop the crumb_sales_order_line accumulator first, then the
    # tables in reverse-FK order (allocation/line children before receipt/invoice
    # parents).
    op.drop_column("crumb_sales_order_line", "qty_invoiced")

    # Drop the allocation first (it FKs into the receipt and the invoice)
    op.drop_index(
        "ix_syerp_receipt_allocation_invoice_id", table_name="syerp_receipt_allocation"
    )
    op.drop_index(
        "ix_syerp_receipt_allocation_receipt_id", table_name="syerp_receipt_allocation"
    )
    op.drop_table("syerp_receipt_allocation")

    # Drop the receipt (the allocation referenced it; no indexes on the model)
    op.drop_table("syerp_receipt")

    # Drop the line before the header (it FKs into the invoice)
    op.drop_index("ix_syerp_invoice_line_invoice_id", table_name="syerp_invoice_line")
    op.drop_table("syerp_invoice_line")

    # Drop the header last (the line and allocation referenced it)
    op.drop_index("ix_syerp_invoice_customer_id", table_name="syerp_invoice")
    op.drop_index("ix_syerp_invoice_invoice_number", table_name="syerp_invoice")
    op.drop_table("syerp_invoice")
