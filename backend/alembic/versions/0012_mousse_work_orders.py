# ABOUTME: Alembic migration 0012 — creates the MOUSSE work-order schema.
# ABOUTME: Adds mousse_work_order / mousse_work_order_component and
# ABOUTME: mousse_work_order_issue — Phase 10 MOUSSE core; hand-authored.
"""add mousse work-order, component and issue tables

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-13 00:00:00.000000+00:00

Phase 10 — MOUSSE (Manufacturing Execution) materials-only work orders
(MOUSSE-01).

Creates the three tables the MOUSSE service builds on. A WorkOrder is a request
to build a PLUM part into finished-goods inventory (mutable status FSM, begins at
"draft"). Its WorkOrderComponents are the resolved BOM lines consumed to build
it. A WorkOrderIssue is an APPEND-ONLY record of a component quantity issued
(consumed) against the WO, soft-linking back to the SYERP inventory txn and
journal entry it generated so the audit trail from consumption to GL is
traceable.

Tables:
  mousse_work_order            — WO header. String(36) uuid PK (mirrors
                                 syerp_inventory_item). wo_number is unique.
                                 plum_part_id FKs plum_part.id (the FG part to
                                 build). released_revision_id FKs
                                 plum_part_revision.id and output_item_id FKs
                                 syerp_inventory_item.id — both NULL until
                                 release. target_location_id FKs
                                 syerp_stock_location.id (int PK). status is the
                                 MUTABLE FSM column. wo_date is the single
                                 accounting date basis for the WO's journal
                                 entries. planned_qty is fixed-point
                                 Numeric(18,6) (D-11, never float).
  mousse_work_order_component  — resolved BOM line. String(36) uuid PK.
                                 work_order_id FKs the header. child_part_id FKs
                                 plum_part.id (the component part). item_id FKs
                                 syerp_inventory_item.id (NULL until release).
                                 qty_per / qty_required are fixed-point
                                 Numeric(18,6) (D-11).
  mousse_work_order_issue      — append-only component-issue row. String(36)
                                 uuid PK. work_order_id FKs the header;
                                 component_id FKs the component. item_id FKs
                                 syerp_inventory_item.id; location_id FKs
                                 syerp_stock_location.id (int PK). quantity /
                                 unit_cost are fixed-point Numeric(18,6) (D-11).
                                 inventory_txn_id FKs syerp_inventory_txn.id and
                                 journal_entry_id FKs syerp_journal_entry.id —
                                 both String(36) uuid PKs (NOT int), so the FK
                                 columns mirror that type.

Migration hand-authored from ORM models (app/modules/mousse/models.py) —
structure matches the model definitions exactly. Chains to down_revision "0011"
(syerp_bill.bill_date) so Alembic single-history is maintained and the
plum_part / plum_part_revision / syerp_inventory_item / syerp_stock_location /
syerp_inventory_txn / syerp_journal_entry FK targets already exist.

Timestamps carry NO server_default: the models populate created_at/completed_at
in Python (default=lambda: datetime.now(timezone.utc)), so the schema stays
drift-free against autogenerate for these three tables.

Indexes mirror the models' index=True declarations only: wo_number (unique) and
plum_part_id on the header; work_order_id on the component and on the issue.

Threat mitigations baked into schema:
  FK plum_part_id / released_revision_id / output_item_id prevent a WO against a
  non-existent PLUM part/revision or SYERP item; FK target_location_id prevents a
  build into a non-existent stock location; FK work_order_id on the component and
  issue prevents orphan rows; FK component_id on the issue prevents an issue
  against a non-existent component; FK item_id / location_id prevent an issue
  against a non-existent SYERP item/location; FK inventory_txn_id /
  journal_entry_id prevent an issue soft-linking a non-existent ledger row or
  journal entry.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # mousse_work_order  (MOUSSE-01)
    # WO header; uuid PK (mirrors syerp_inventory_item). MUTABLE status FSM.
    # ------------------------------------------------------------------
    op.create_table(
        "mousse_work_order",
        # Primary key — UUID string (mirrors syerp_inventory_item.id)
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Identity
        sa.Column("wo_number", sa.String(length=30), nullable=False),

        # Build target (PLUM)
        sa.Column("plum_part_id", sa.String(length=36), nullable=False),
        # released_revision_id / output_item_id — NULL until the WO is released
        sa.Column("released_revision_id", sa.String(length=36), nullable=True),
        sa.Column("output_item_id", sa.String(length=36), nullable=True),

        # Plan (D-11) — fixed-point, never float
        sa.Column("planned_qty", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("target_location_id", sa.Integer(), nullable=False),

        # status: MUTABLE FSM column (begins at "draft")
        sa.Column("status", sa.String(length=30), nullable=False),
        # wo_date: single accounting date basis for the WO's journal entries
        sa.Column("wo_date", sa.Date(), nullable=False),

        # Provenance / audit — created_at populated Python-side (no server_default)
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # completed_at: set when the WO is completed; NULL until then
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),

        # plum_part_id — FK into plum_part.id (the FG part to build)
        sa.ForeignKeyConstraint(
            ["plum_part_id"],
            ["plum_part.id"],
            name="fk_mousse_work_order_plum_part_id",
        ),
        # released_revision_id — FK into plum_part_revision.id (snapshot on release)
        sa.ForeignKeyConstraint(
            ["released_revision_id"],
            ["plum_part_revision.id"],
            name="fk_mousse_work_order_released_revision_id",
        ),
        # output_item_id — FK into syerp_inventory_item.id (resolved on release)
        sa.ForeignKeyConstraint(
            ["output_item_id"],
            ["syerp_inventory_item.id"],
            name="fk_mousse_work_order_output_item_id",
        ),
        # target_location_id — FK into syerp_stock_location.id (int PK)
        sa.ForeignKeyConstraint(
            ["target_location_id"],
            ["syerp_stock_location.id"],
            name="fk_mousse_work_order_target_location_id",
        ),
    )

    # Indexes for mousse_work_order hot paths (mirror model index=True)
    op.create_index(
        "ix_mousse_work_order_wo_number",
        "mousse_work_order",
        ["wo_number"],
        unique=True,
    )
    op.create_index(
        "ix_mousse_work_order_plum_part_id",
        "mousse_work_order",
        ["plum_part_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # mousse_work_order_component  (MOUSSE-01)
    # Resolved BOM line; uuid PK. FKs into the header + PLUM/SYERP.
    # ------------------------------------------------------------------
    op.create_table(
        "mousse_work_order_component",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Links
        sa.Column("work_order_id", sa.String(length=36), nullable=False),
        sa.Column("child_part_id", sa.String(length=36), nullable=False),
        # item_id: SYERP inventory item the component maps to; NULL until release
        sa.Column("item_id", sa.String(length=36), nullable=True),

        # Quantities (D-11) — fixed-point, never float
        sa.Column("qty_per", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("qty_required", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("unit_of_measure", sa.String(length=50), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),

        # work_order_id — FK into the header
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["mousse_work_order.id"],
            name="fk_mousse_work_order_component_work_order_id",
        ),
        # child_part_id — FK into plum_part.id (the component part)
        sa.ForeignKeyConstraint(
            ["child_part_id"],
            ["plum_part.id"],
            name="fk_mousse_work_order_component_child_part_id",
        ),
        # item_id — FK into syerp_inventory_item.id (resolved on release)
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["syerp_inventory_item.id"],
            name="fk_mousse_work_order_component_item_id",
        ),
    )

    # Index for mousse_work_order_component hot path (components per WO)
    op.create_index(
        "ix_mousse_work_order_component_work_order_id",
        "mousse_work_order_component",
        ["work_order_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # mousse_work_order_issue  (MOUSSE-01)
    # Append-only component-issue row; uuid PK. FKs into the header, the
    # component, and the SYERP hub (item, location, txn, journal entry).
    # ------------------------------------------------------------------
    op.create_table(
        "mousse_work_order_issue",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Links
        sa.Column("work_order_id", sa.String(length=36), nullable=False),
        sa.Column("component_id", sa.String(length=36), nullable=False),
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),

        # Amounts (D-11) — fixed-point, never float
        sa.Column("quantity", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=18, scale=6), nullable=False),

        # Soft links to the SYERP hub — both String(36) uuid PKs (NOT int)
        sa.Column("inventory_txn_id", sa.String(length=36), nullable=False),
        sa.Column("journal_entry_id", sa.String(length=36), nullable=False),

        # Provenance / audit — created_at populated Python-side (no server_default)
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),

        # work_order_id — FK into the header
        sa.ForeignKeyConstraint(
            ["work_order_id"],
            ["mousse_work_order.id"],
            name="fk_mousse_work_order_issue_work_order_id",
        ),
        # component_id — FK into the component being issued
        sa.ForeignKeyConstraint(
            ["component_id"],
            ["mousse_work_order_component.id"],
            name="fk_mousse_work_order_issue_component_id",
        ),
        # item_id — FK into syerp_inventory_item.id (the item consumed)
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["syerp_inventory_item.id"],
            name="fk_mousse_work_order_issue_item_id",
        ),
        # location_id — FK into syerp_stock_location.id (int PK)
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["syerp_stock_location.id"],
            name="fk_mousse_work_order_issue_location_id",
        ),
        # inventory_txn_id — FK into syerp_inventory_txn.id (movement ledger)
        sa.ForeignKeyConstraint(
            ["inventory_txn_id"],
            ["syerp_inventory_txn.id"],
            name="fk_mousse_work_order_issue_inventory_txn_id",
        ),
        # journal_entry_id — FK into syerp_journal_entry.id (general journal)
        sa.ForeignKeyConstraint(
            ["journal_entry_id"],
            ["syerp_journal_entry.id"],
            name="fk_mousse_work_order_issue_journal_entry_id",
        ),
    )

    # Index for mousse_work_order_issue hot path (issues per WO)
    op.create_index(
        "ix_mousse_work_order_issue_work_order_id",
        "mousse_work_order_issue",
        ["work_order_id"],
        unique=False,
    )


def downgrade() -> None:
    # Drop the issue first (it FKs into the header and the component)
    op.drop_index(
        "ix_mousse_work_order_issue_work_order_id",
        table_name="mousse_work_order_issue",
    )
    op.drop_table("mousse_work_order_issue")

    # Drop the component next (it FKs into the header; the issue referenced it)
    op.drop_index(
        "ix_mousse_work_order_component_work_order_id",
        table_name="mousse_work_order_component",
    )
    op.drop_table("mousse_work_order_component")

    # Drop the header last (the component and issue referenced it)
    op.drop_index(
        "ix_mousse_work_order_plum_part_id", table_name="mousse_work_order"
    )
    op.drop_index(
        "ix_mousse_work_order_wo_number", table_name="mousse_work_order"
    )
    op.drop_table("mousse_work_order")
