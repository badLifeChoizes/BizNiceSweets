# ABOUTME: Alembic migration 0013 — creates the CRUMB (CRM) pipeline schema.
# ABOUTME: Adds crumb_lead / crumb_opportunity / crumb_quote / crumb_quote_line
# ABOUTME: and crumb_interaction — Phase 11a CRUMB core; hand-authored.
"""crumb crm pipeline (0013)

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-16 00:00:00.000000+00:00

Phase 11a — CRUMB (CRM) leads, opportunities, quotes (with lines) and
append-only customer interactions (CRUMB-01).

Creates the five tables the CRUMB service builds on. A Lead is a prospective
customer entering the pipeline; it may convert into an Opportunity, a qualified
sale against a SYERP partner. A Quote is a header issued to a partner (optionally
against an opportunity) carrying priced QuoteLines (a PLUM part or free-text
item). An Interaction is an APPEND-ONLY record of a customer touch soft-linking
any pipeline record it relates to.

Cross-module integration is via foreign keys into the hub, exactly per the
"SYERP as the hub" constraint: partner_id → syerp_partner.id (customer) and
plum_part_id → plum_part.id (the part a quote line prices). Every hub and
intra-CRUMB FK is String(36) uuid (mirrors syerp_partner.id / plum_part.id) —
never Integer. All money/qty columns are fixed-point Numeric(18,6) (D-11, never
float), mirroring SYERP.

Tables:
  crumb_lead          — pipeline lead. String(36) uuid PK. partner_id soft-links
                        a SYERP partner (NULL until linked); opportunity_id
                        soft-links the opportunity it converted into (NULL until
                        converted). status walks new → qualified → converted;
                        active is the archive flag.
  crumb_opportunity   — qualified opportunity. String(36) uuid PK. partner_id FKs
                        syerp_partner.id (required); lead_id soft-links the
                        originating lead. estimated_value is Numeric(18,6). stage
                        walks qualify → proposal → won | lost.
  crumb_quote         — quote header. String(36) uuid PK. quote_number is unique.
                        partner_id FKs syerp_partner.id (required);
                        opportunity_id soft-links the opportunity it quotes.
                        status walks draft → sent → accepted | rejected | expired.
  crumb_quote_line    — priced line. String(36) uuid PK. quote_id FKs the header
                        (indexed); plum_part_id FKs plum_part.id (NULL for a
                        free-text line). quantity / unit_price / markup_pct are
                        Numeric(18,6).
  crumb_interaction   — append-only customer touch. String(36) uuid PK.
                        partner_id FKs syerp_partner.id (required, indexed);
                        lead_id / opportunity_id / quote_id soft-link the pipeline
                        record it relates to (any may be NULL).

crumb_lead and crumb_opportunity are mutually dependent (lead.opportunity_id ↔
opportunity.lead_id), so crumb_lead is created WITHOUT its opportunity_id FK
inline; the FK is added by op.create_foreign_key after crumb_opportunity exists,
and dropped first on downgrade to break the cycle.

Migration hand-authored from ORM models (app/modules/crumb/models.py) —
structure matches the model definitions exactly. Chains to down_revision "0012"
(mousse_work_orders) so Alembic single-history is maintained and the
syerp_partner / plum_part FK targets already exist.

Timestamps carry NO server_default: the models populate created_at / occurred_at
in Python (default=lambda: datetime.now(timezone.utc)), so the schema stays
drift-free against autogenerate for these five tables.

Indexes mirror the models' index=True declarations only: quote_number (unique)
on crumb_quote; quote_id on crumb_quote_line; partner_id on crumb_interaction.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # crumb_lead  (CRUMB-01)
    # Pipeline lead; uuid PK. Created WITHOUT its opportunity_id FK inline
    # (crumb_opportunity does not exist yet); the FK is added by
    # op.create_foreign_key below, once crumb_opportunity is created.
    # ------------------------------------------------------------------
    op.create_table(
        "crumb_lead",
        # Primary key — UUID string (mirrors syerp_partner.id)
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Identity
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("company", sa.String(), nullable=True),
        sa.Column("contact", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),

        # status: pipeline lifecycle — new | qualified | converted
        sa.Column("status", sa.String(length=30), nullable=False),
        # active: archive flag (False = archived)
        sa.Column("active", sa.Boolean(), nullable=False),

        # Links
        # partner_id — SYERP partner this lead maps to; NULL until linked
        sa.Column("partner_id", sa.String(length=36), nullable=True),
        # opportunity_id — opportunity this lead converted into; NULL until converted
        sa.Column("opportunity_id", sa.String(length=36), nullable=True),

        # Provenance / audit — created_at populated Python-side (no server_default)
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),

        # partner_id — FK into syerp_partner.id (the hub customer)
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["syerp_partner.id"],
            name="fk_crumb_lead_partner_id",
        ),
    )

    # ------------------------------------------------------------------
    # crumb_opportunity  (CRUMB-01)
    # Qualified opportunity; uuid PK. FKs the hub partner + originating lead.
    # ------------------------------------------------------------------
    op.create_table(
        "crumb_opportunity",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Identity
        sa.Column("name", sa.String(), nullable=False),

        # Links
        sa.Column("partner_id", sa.String(length=36), nullable=False),
        # lead_id — originating lead; NULL if created directly
        sa.Column("lead_id", sa.String(length=36), nullable=True),

        # Value / timing (D-11) — fixed-point, never float
        sa.Column("estimated_value", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("expected_close_date", sa.Date(), nullable=True),

        # stage: pipeline lifecycle — qualify | proposal | won | lost
        sa.Column("stage", sa.String(length=30), nullable=False),

        # Provenance / audit — created_at populated Python-side (no server_default)
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),

        # partner_id — FK into syerp_partner.id (the hub customer)
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["syerp_partner.id"],
            name="fk_crumb_opportunity_partner_id",
        ),
        # lead_id — FK into crumb_lead.id (the originating lead)
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["crumb_lead.id"],
            name="fk_crumb_opportunity_lead_id",
        ),
    )

    # crumb_lead.opportunity_id — FK into crumb_opportunity.id, added now that the
    # target exists (breaks the crumb_lead ↔ crumb_opportunity cycle at create).
    op.create_foreign_key(
        "fk_crumb_lead_opportunity_id",
        "crumb_lead",
        "crumb_opportunity",
        ["opportunity_id"],
        ["id"],
    )

    # ------------------------------------------------------------------
    # crumb_quote  (CRUMB-01)
    # Quote header; uuid PK. quote_number is unique. FKs the hub partner and
    # (optionally) the opportunity it quotes.
    # ------------------------------------------------------------------
    op.create_table(
        "crumb_quote",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Identity
        sa.Column("quote_number", sa.String(length=30), nullable=False),

        # Links
        sa.Column("partner_id", sa.String(length=36), nullable=False),
        # opportunity_id — opportunity this quote is against; NULL if standalone
        sa.Column("opportunity_id", sa.String(length=36), nullable=True),

        # status: quote lifecycle — draft | sent | accepted | rejected | expired
        sa.Column("status", sa.String(length=30), nullable=False),

        # Provenance / audit — created_at populated Python-side (no server_default)
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),

        # partner_id — FK into syerp_partner.id (the hub customer)
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["syerp_partner.id"],
            name="fk_crumb_quote_partner_id",
        ),
        # opportunity_id — FK into crumb_opportunity.id (the opportunity quoted)
        sa.ForeignKeyConstraint(
            ["opportunity_id"],
            ["crumb_opportunity.id"],
            name="fk_crumb_quote_opportunity_id",
        ),
    )

    # Unique index on quote_number (mirrors model unique=True, index=True)
    op.create_index(
        "ix_crumb_quote_quote_number",
        "crumb_quote",
        ["quote_number"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # crumb_quote_line  (CRUMB-01)
    # Priced line; uuid PK. FKs the quote header (indexed) and (optionally) a
    # PLUM part; free-text lines carry description instead.
    # ------------------------------------------------------------------
    op.create_table(
        "crumb_quote_line",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Links
        sa.Column("quote_id", sa.String(length=36), nullable=False),
        # plum_part_id — catalog part priced by this line; NULL for a free-text line
        sa.Column("plum_part_id", sa.String(length=36), nullable=True),

        # description: free-text item; required-when-no-part enforced in service
        sa.Column("description", sa.String(), nullable=True),

        # Amounts (D-11) — fixed-point, never float
        sa.Column("quantity", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("markup_pct", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),

        # quote_id — FK into crumb_quote.id (the header)
        sa.ForeignKeyConstraint(
            ["quote_id"],
            ["crumb_quote.id"],
            name="fk_crumb_quote_line_quote_id",
        ),
        # plum_part_id — FK into plum_part.id (the catalog part priced)
        sa.ForeignKeyConstraint(
            ["plum_part_id"],
            ["plum_part.id"],
            name="fk_crumb_quote_line_plum_part_id",
        ),
    )

    # Index for crumb_quote_line hot path (lines per quote)
    op.create_index(
        "ix_crumb_quote_line_quote_id",
        "crumb_quote_line",
        ["quote_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # crumb_interaction  (CRUMB-01)
    # Append-only customer touch; uuid PK. FKs the hub partner (indexed) and
    # soft-links any pipeline record (lead / opportunity / quote) it relates to.
    # ------------------------------------------------------------------
    op.create_table(
        "crumb_interaction",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Links
        sa.Column("partner_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=True),
        sa.Column("opportunity_id", sa.String(length=36), nullable=True),
        sa.Column("quote_id", sa.String(length=36), nullable=True),

        # Content
        # interaction_type: call | email | note | meeting
        sa.Column("interaction_type", sa.String(length=20), nullable=False),
        # occurred_at: when the touch happened (vs created_at when logged)
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("body", sa.String(), nullable=False),

        # Provenance / audit — created_at populated Python-side (no server_default)
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),

        # partner_id — FK into syerp_partner.id (the hub customer)
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["syerp_partner.id"],
            name="fk_crumb_interaction_partner_id",
        ),
        # lead_id — FK into crumb_lead.id (soft link)
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["crumb_lead.id"],
            name="fk_crumb_interaction_lead_id",
        ),
        # opportunity_id — FK into crumb_opportunity.id (soft link)
        sa.ForeignKeyConstraint(
            ["opportunity_id"],
            ["crumb_opportunity.id"],
            name="fk_crumb_interaction_opportunity_id",
        ),
        # quote_id — FK into crumb_quote.id (soft link)
        sa.ForeignKeyConstraint(
            ["quote_id"],
            ["crumb_quote.id"],
            name="fk_crumb_interaction_quote_id",
        ),
    )

    # Index for crumb_interaction hot path (touches per partner)
    op.create_index(
        "ix_crumb_interaction_partner_id",
        "crumb_interaction",
        ["partner_id"],
        unique=False,
    )


def downgrade() -> None:
    # Reverse dependency order. Drop the interaction first (it FKs partner, lead,
    # opportunity and quote).
    op.drop_index(
        "ix_crumb_interaction_partner_id", table_name="crumb_interaction"
    )
    op.drop_table("crumb_interaction")

    # Drop the quote line (FKs the quote and plum_part).
    op.drop_index(
        "ix_crumb_quote_line_quote_id", table_name="crumb_quote_line"
    )
    op.drop_table("crumb_quote_line")

    # Drop the quote (FKs partner and opportunity).
    op.drop_index(
        "ix_crumb_quote_quote_number", table_name="crumb_quote"
    )
    op.drop_table("crumb_quote")

    # Break the crumb_lead ↔ crumb_opportunity cycle before dropping either:
    # remove the alter-added crumb_lead.opportunity_id FK first.
    op.drop_constraint(
        "fk_crumb_lead_opportunity_id", "crumb_lead", type_="foreignkey"
    )

    # Drop the opportunity (FKs partner and lead), then the lead last.
    op.drop_table("crumb_opportunity")
    op.drop_table("crumb_lead")
