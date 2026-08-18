# ABOUTME: Alembic migration 0018 — creates the FLAN (Project Management) schema.
# ABOUTME: Adds flan_project / flan_phase / flan_task, the two tag join tables,
# ABOUTME: flan_team_member and the two assignment join tables — Phase 1 (v5.0).
"""add flan project/phase/task, tags, team roster and assignment tables

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-18 00:00:00.000000+00:00

Phase 1 (v5.0) — FLAN project management (FLAN-01): the Project → Phase → Task
tree, the per-project team roster, the two tag join tables and the two
assignment join tables. This is FLAN's first schema; nothing existed before it.

Creates the eight tables the FLAN service builds on:
  flan_project        — project header. String(36) uuid PK (mirrors the hub).
                        name is required and deliberately NOT unique (duplicate
                        project names are allowed, FLAN-01.1). key_prefix is the
                        per-project task-key prefix (D-V5P1-2). currency is the
                        ISO-4217 code; start_date/gate_date are the project's own
                        hand-set dates. active is the archive flag — archiving is
                        a soft delete that retains all data.
  flan_phase          — a stage of exactly one project. String(36) uuid PK.
                        project_id FKs flan_project.id (required, indexed).
                        sort_order drives display order; status walks
                        pending|in-progress|complete. **Carries deliberately NO
                        start_date, due_date or percent_complete column (D-V5-1)**
                        — those three are derived from the phase's tasks on every
                        read, so "never hand-set" is structural, not a rule.
  flan_task           — a unit of work in exactly one phase. String(36) uuid PK.
                        phase_id FKs flan_phase.id ON DELETE CASCADE so deleting a
                        phase cascades to its tasks (FLAN-01.2) in the database
                        rather than in service bookkeeping. project_id FKs
                        flan_project.id and is carried in addition to phase_id
                        because uq_flan_task_project_key makes the key unique
                        within its project. key is the unpadded `<PREFIX>-<n>`
                        handle (D-V5P1-7); status is To Do|In Progress|Done (the
                        Done share drives a phase's derived %).
  flan_project_tag    — opaque tag on a project (D-V5P1-5). Composite PK
                        (project_id, tag); project_id FK ON DELETE CASCADE.
  flan_task_tag       — opaque tag on a task (D-V5P1-5). Composite PK
                        (task_id, tag); task_id FK ON DELETE CASCADE, so a
                        cascaded phase delete leaves no orphan tags.
  flan_team_member    — a project's roster row (FLAN-01.4). String(36) uuid PK.
                        project_id FKs flan_project.id (required, indexed).
                        hourly_rate is fixed-point Numeric(18,6) (D-11, never
                        float) and is stored but read by nothing in v5.0
                        (D-V5-2 / D-M5-2). user_id optionally FKs users.id
                        **ON DELETE SET NULL** — deleting a platform user must not
                        delete project history, so the roster row survives as an
                        unlinked entry. uq_flan_member_project_user stops one user
                        being rostered twice on a project (Postgres permits many
                        NULLs, so unlinked members are unconstrained). active is
                        the soft-remove flag (D-V5P1-6).
  flan_task_assignee  — assignment of a roster member to a task (FLAN-01.5).
                        Composite PK (task_id, member_id).
  flan_phase_assignee — assignment of a roster member to a phase (FLAN-01.5).
                        Composite PK (phase_id, member_id).

The cascade shapes are load-bearing and deliberate. task_id/phase_id on the
assignment tables cascade (deleting the work deletes its assignments), but
**member_id on both assignment tables has NO cascade** (D-V5P1-6): removing a
roster member is a soft-remove whose assignment rows the service deletes
explicitly so the change is audited — a DB cascade would erase them silently.

Migration hand-authored from the ORM models (app/modules/flan/models.py) after
autogenerating against the live dev database; structure matches the model
definitions exactly. Chains to down_revision "0017" (syerp_ar_invoicing) so
Alembic single-history is maintained and the users.id FK target already exists.

Timestamps carry NO server_default: the models populate created_at/updated_at in
Python (default=lambda: datetime.now(UTC)), so the schema stays drift-free
against autogenerate for these eight tables.

Indexes mirror the models' index=True declarations only: project_id on the phase
and on the team member; phase_id and project_id on the task; tag on both tag
tables (indexed even though it is part of the composite PK, because FLAN-04's
group-by-facet aggregates by it alone). The join tables declare no other indexes.

Threat mitigations baked into schema:
  FK project_id prevents phases, tasks, tags and roster rows against a
  non-existent project; FK phase_id prevents orphan tasks and phase assignments;
  FK task_id prevents orphan task tags and task assignments; FK member_id
  prevents an assignment naming a non-existent roster member; FK user_id
  prevents a roster row linking a non-existent platform user;
  uq_flan_task_project_key makes a duplicate task key inside a project a database
  error (the key generator's retry hinges on that constraint name);
  uq_flan_member_project_user prevents the same user being rostered twice.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic
revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # flan_project  (FLAN-01.1)
    # Top of the Project → Phase → Task tree; uuid PK (mirrors the hub).
    # Created first: every other flan_* table FKs into it directly or
    # through its children. name is NOT unique — duplicates are allowed.
    # ------------------------------------------------------------------
    op.create_table(
        "flan_project",
        # Primary key — UUID string (mirrors the hub)
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Identity — name deliberately not unique (FLAN-01.1)
        sa.Column("name", sa.String(), nullable=False),
        # key_prefix: per-project task-key prefix, locked once a task exists (D-V5P1-2)
        sa.Column("key_prefix", sa.String(length=10), nullable=False),
        # category: work | personal | client | none; NULL when unclassified
        sa.Column("category", sa.String(length=30), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        # currency: ISO-4217 code the project's (later) money fields are read in
        sa.Column("currency", sa.String(length=3), nullable=False),

        # Timing — project-level and hand-set (unlike a phase's derived dates)
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("gate_date", sa.Date(), nullable=True),

        # active: archive flag (False = archived, keeps data, rejects writes)
        sa.Column("active", sa.Boolean(), nullable=False),

        # Timestamps — populated Python-side (no server_default)
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ------------------------------------------------------------------
    # flan_phase  (FLAN-01.2)
    # A stage of exactly one project. NO start_date / due_date /
    # percent_complete column: those are derived per read (D-V5-1).
    # ------------------------------------------------------------------
    op.create_table(
        "flan_phase",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Links
        sa.Column("project_id", sa.String(length=36), nullable=False),

        # Identity
        sa.Column("name", sa.String(), nullable=False),
        # sort_order: display order within the project
        sa.Column("sort_order", sa.Integer(), nullable=False),
        # status: pending | in-progress | complete
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("description", sa.String(), nullable=True),

        # Timestamps — populated Python-side (no server_default)
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),

        # project_id — FK into flan_project.id (the owning project)
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["flan_project.id"],
            name="fk_flan_phase_project_id",
        ),
    )

    # Index for the flan_phase hot path (every phase list is project-scoped)
    op.create_index(
        "ix_flan_phase_project_id",
        "flan_phase",
        ["project_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # flan_task  (FLAN-01.3)
    # Unit of work in exactly one phase. phase_id CASCADEs so deleting a
    # phase deletes its tasks (FLAN-01.2). project_id is carried as well so
    # the key can be unique per project (uq_flan_task_project_key).
    # ------------------------------------------------------------------
    op.create_table(
        "flan_task",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Links
        sa.Column("phase_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),

        # Identity — key is the unpadded `<PREFIX>-<n>` handle (D-V5P1-7)
        sa.Column("key", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.String(), nullable=False),
        # status: To Do | In Progress | Done (Done share drives phase % complete)
        sa.Column("status", sa.String(length=20), nullable=False),

        # Timing — due == start is a valid zero-duration milestone; due < start 4xx
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),

        # Flags
        # risk_level: none | low | medium | high
        sa.Column("risk_level", sa.String(length=10), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),

        # Timestamps — populated Python-side (no server_default)
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),

        # phase_id — FK into flan_phase.id; CASCADE so a phase delete removes its tasks
        sa.ForeignKeyConstraint(
            ["phase_id"],
            ["flan_phase.id"],
            name="fk_flan_task_phase_id",
            ondelete="CASCADE",
        ),
        # project_id — FK into flan_project.id (denormalized from the phase)
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["flan_project.id"],
            name="fk_flan_task_project_id",
        ),
        # Task key unique within its project — the key generator's retry hinges
        # on this constraint NAME appearing in the IntegrityError
        sa.UniqueConstraint("project_id", "key", name="uq_flan_task_project_key"),
    )

    # Indexes for flan_task hot paths (mirror model index=True)
    op.create_index(
        "ix_flan_task_phase_id",
        "flan_task",
        ["phase_id"],
        unique=False,
    )
    op.create_index(
        "ix_flan_task_project_id",
        "flan_task",
        ["project_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # flan_project_tag  (D-V5P1-5)
    # Opaque tag on a project. Composite PK (project_id, tag) makes a tag
    # idempotent per project; CASCADE leaves no orphan tags.
    # ------------------------------------------------------------------
    op.create_table(
        "flan_project_tag",
        sa.Column("project_id", sa.String(length=36), primary_key=True, nullable=False),
        # tag: opaque normalized string in Phase 1 (no Facet:Value parsing yet)
        sa.Column("tag", sa.String(length=60), primary_key=True, nullable=False),

        # project_id — FK into flan_project.id; CASCADE on project delete
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["flan_project.id"],
            name="fk_flan_project_tag_project_id",
            ondelete="CASCADE",
        ),
    )

    # Index on tag alone (it leads no PK prefix) — FLAN-04 groups by facet
    op.create_index(
        "ix_flan_project_tag_tag",
        "flan_project_tag",
        ["tag"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # flan_task_tag  (D-V5P1-5)
    # Opaque tag on a task. Composite PK (task_id, tag); CASCADE so a task
    # delete — including one cascaded from a phase — leaves no orphan tags.
    # ------------------------------------------------------------------
    op.create_table(
        "flan_task_tag",
        sa.Column("task_id", sa.String(length=36), primary_key=True, nullable=False),
        # tag: opaque normalized string in Phase 1 (no Facet:Value parsing yet)
        sa.Column("tag", sa.String(length=60), primary_key=True, nullable=False),

        # task_id — FK into flan_task.id; CASCADE on task delete
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["flan_task.id"],
            name="fk_flan_task_tag_task_id",
            ondelete="CASCADE",
        ),
    )

    # Index on tag alone (it leads no PK prefix) — FLAN-04 groups by facet
    op.create_index(
        "ix_flan_task_tag_tag",
        "flan_task_tag",
        ["tag"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # flan_team_member  (FLAN-01.4)
    # A project's roster row; uuid PK. user_id is SET NULL on user delete so
    # deleting a platform user never deletes project history.
    # Created before the assignment tables whose member_id FK targets it.
    # ------------------------------------------------------------------
    op.create_table(
        "flan_team_member",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),

        # Links
        sa.Column("project_id", sa.String(length=36), nullable=False),

        # Identity — only name is required (a member needs no account or email)
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("role", sa.String(length=60), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        # color: `#rrggbb` display swatch
        sa.Column("color", sa.String(length=7), nullable=True),

        # hourly_rate (D-11) — fixed-point; stored, read by nothing in v5.0
        sa.Column("hourly_rate", sa.Numeric(precision=18, scale=6), nullable=True),

        # user_id: optional platform-user link
        sa.Column("user_id", sa.String(length=36), nullable=True),

        # active: soft-remove flag (False = removed, assignments cleared, row kept)
        sa.Column("active", sa.Boolean(), nullable=False),

        # Timestamps — populated Python-side (no server_default)
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),

        # project_id — FK into flan_project.id (the roster is per-project)
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["flan_project.id"],
            name="fk_flan_team_member_project_id",
        ),
        # user_id — FK into users.id; SET NULL so a deleted user leaves the
        # roster row (and all its history) standing as an unlinked entry
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_flan_team_member_user_id",
            ondelete="SET NULL",
        ),
        # One platform user may be rostered at most once per project; Postgres
        # permits many NULLs, so unlinked members are unconstrained
        sa.UniqueConstraint("project_id", "user_id", name="uq_flan_member_project_user"),
    )

    # Index for the flan_team_member hot path (the roster is read project-scoped)
    op.create_index(
        "ix_flan_team_member_project_id",
        "flan_team_member",
        ["project_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # flan_task_assignee  (FLAN-01.5)
    # Composite PK (task_id, member_id) makes an assignment idempotent.
    # task_id CASCADEs; member_id deliberately does NOT (D-V5P1-6) — the
    # service deletes a removed member's assignments explicitly so the
    # change is audited rather than silently cascaded away.
    # ------------------------------------------------------------------
    op.create_table(
        "flan_task_assignee",
        sa.Column("task_id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("member_id", sa.String(length=36), primary_key=True, nullable=False),

        # task_id — FK into flan_task.id; CASCADE on task delete
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["flan_task.id"],
            name="fk_flan_task_assignee_task_id",
            ondelete="CASCADE",
        ),
        # member_id — FK into flan_team_member.id; NO cascade (D-V5P1-6)
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["flan_team_member.id"],
            name="fk_flan_task_assignee_member_id",
        ),
    )

    # ------------------------------------------------------------------
    # flan_phase_assignee  (FLAN-01.5)
    # Same shape and reasoning as flan_task_assignee: phase_id CASCADEs,
    # member_id does not (D-V5P1-6).
    # ------------------------------------------------------------------
    op.create_table(
        "flan_phase_assignee",
        sa.Column("phase_id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("member_id", sa.String(length=36), primary_key=True, nullable=False),

        # phase_id — FK into flan_phase.id; CASCADE on phase delete
        sa.ForeignKeyConstraint(
            ["phase_id"],
            ["flan_phase.id"],
            name="fk_flan_phase_assignee_phase_id",
            ondelete="CASCADE",
        ),
        # member_id — FK into flan_team_member.id; NO cascade (D-V5P1-6)
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["flan_team_member.id"],
            name="fk_flan_phase_assignee_member_id",
        ),
    )


def downgrade() -> None:
    # Reverse order — children before parents so no FK is left dangling.
    # The assignment join tables reference the roster, the task and the phase.
    op.drop_table("flan_phase_assignee")
    op.drop_table("flan_task_assignee")

    # The roster is referenced only by the assignment tables, now gone
    op.drop_index("ix_flan_team_member_project_id", table_name="flan_team_member")
    op.drop_table("flan_team_member")

    # Tag tables reference the task and the project
    op.drop_index("ix_flan_task_tag_tag", table_name="flan_task_tag")
    op.drop_table("flan_task_tag")
    op.drop_index("ix_flan_project_tag_tag", table_name="flan_project_tag")
    op.drop_table("flan_project_tag")

    # Tasks reference the phase and the project
    op.drop_index("ix_flan_task_project_id", table_name="flan_task")
    op.drop_index("ix_flan_task_phase_id", table_name="flan_task")
    op.drop_table("flan_task")

    # Phases reference the project
    op.drop_index("ix_flan_phase_project_id", table_name="flan_phase")
    op.drop_table("flan_phase")

    # The project last — everything that referenced it is gone
    op.drop_table("flan_project")
