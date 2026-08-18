# ABOUTME: FLAN (Project Management) ORM models — projects, phases, tasks and
# ABOUTME: their tag join tables (FLAN-01). Tables are prefixed `flan_`.
# ABOUTME: A phase stores NO dates or % complete: those are derived from its
# ABOUTME: tasks on every read (D-V5-1), so "never hand-set" is structural.
"""
FLAN module ORM models.

Tables defined here (all prefixed `flan_`, FLAN-01):
  flan_project     — A project: the top of the Project → Phase → Task tree and
                     the scope every other FLAN row belongs to (FLAN-01.1).
  flan_phase       — A stage of exactly one project, ordered and statused
                     (FLAN-01.2). Carries no dates and no percent column.
  flan_task        — A unit of work in exactly one phase (hence one project),
                     keyed `<PREFIX>-<n>` unique within its project (FLAN-01.3).
  flan_project_tag — Opaque tag applied to a project (D-V5P1-5).
  flan_task_tag    — Opaque tag applied to a task (D-V5P1-5).

All models inherit from the shared declarative Base so that Base.metadata is
populated when app.core.models (the central aggregator) is imported by
Alembic's env.py.

Two structural choices are load-bearing and deliberate:

  * **A phase has no start_date, due_date or percent_complete column**
    (D-V5-1). Storing them would make "derived from the tasks, never hand-set"
    a rule someone has to remember; omitting the columns makes it impossible to
    break. The values are computed per read in the service rollup.
  * **Tags live in join tables, not an array column** (D-V5P1-5). The later
    group-by-facet and in-plan-basis filters are plain SQL aggregations over
    these tables, and no ARRAY/JSON column exists anywhere in the codebase.

PK style mirrors the hub: String(36) uuid strings, defaulted in Python.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base

# ---------------------------------------------------------------------------
# Project — top of the Project → Phase → Task tree (FLAN-01.1)
# ---------------------------------------------------------------------------


class Project(Base):
    """
    Project — the scope that owns every phase, task and roster row in FLAN.

    Uses a String(36) uuid PK (mirrors the hub) because it is referenced by FKs
    from phases, tasks, tags and the team roster, and because the id is
    immutable and non-enumerable (FLAN-01.1).

    name is required and **deliberately not unique** — duplicate project names
    are explicitly allowed by FLAN-01.1, so no unique constraint exists here.

    key_prefix is the per-project task-key prefix (D-V5P1-2): defaulted from the
    name at create, editable until the first task exists and immutable after.
    It is stored rather than inferred from existing keys, unlike the v45
    prototype's majority-inference, which is not ported.

    category is the prototype's project classification — work | personal |
    client | none (flan/app/prj-mgmt-v24.html:2457) — and is nullable because a
    project need not be classified.

    currency is the ISO-4217 code the project's (later) money fields are read
    in; it defaults to USD so no create has to supply it.

    start_date and gate_date are the project's own planned start and gate/target
    date — hand-set at the project level, unlike a phase's derived dates.

    active is the archive flag (FLAN-01.1): archiving is a soft delete that
    retains all data, and every mutating service call refuses to write inside an
    archived project.
    """

    __tablename__ = "flan_project"

    # --- Primary key — UUID string -----------------------------------------
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Identity ----------------------------------------------------------
    # name: required; duplicates ARE allowed (FLAN-01.1) — no unique constraint
    name: Mapped[str] = mapped_column(String, nullable=False)
    # key_prefix: per-project task-key prefix, locked once a task exists (D-V5P1-2)
    key_prefix: Mapped[str] = mapped_column(String(10), nullable=False)
    # category: work | personal | client | none; NULL when unclassified
    category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    # currency: ISO-4217 code; defaults to USD
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    # --- Timing (project-level, hand-set) ----------------------------------
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # gate_date: the project's gate/target date
    gate_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # active: archive flag (False = archived, rejects writes but keeps data)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- Timestamps --------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Phase — a stage of exactly one project (FLAN-01.2)
# ---------------------------------------------------------------------------


class Phase(Base):
    """
    Phase — a named, ordered stage belonging to exactly one project.

    Uses a String(36) uuid PK because it is referenced by FKs from tasks and
    phase assignees.

    project_id is the owning project (required, indexed — every phase list is
    scoped by it). sort_order drives display order; status walks
    pending → in-progress → complete.

    **There is deliberately no start_date, due_date or percent_complete column
    here (D-V5-1).** A phase's start date, due date and % complete are derived
    from its tasks on every read — earliest task start, latest task due, and the
    share of its tasks in status Done — and are never hand-set. Omitting the
    columns makes that structural instead of a rule to remember; a phase with no
    tasks reports no dates and 0.00%.
    """

    __tablename__ = "flan_phase"

    # --- Primary key — UUID string -----------------------------------------
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Links -------------------------------------------------------------
    # project_id: owning project (required); every phase list is scoped by it
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("flan_project.id"), nullable=False, index=True
    )

    # --- Identity ----------------------------------------------------------
    name: Mapped[str] = mapped_column(String, nullable=False)
    # sort_order: display order within the project
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # status: pending | in-progress | complete
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    # --- Timestamps --------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


# ---------------------------------------------------------------------------
# Task — a unit of work in exactly one phase (FLAN-01.3)
# ---------------------------------------------------------------------------


class Task(Base):
    """
    Task — one unit of work, belonging to exactly one phase (hence one project).

    Uses a String(36) uuid PK because it is referenced by FKs from task tags and
    task assignees.

    phase_id FKs into flan_phase.id with ondelete="CASCADE": deleting a phase
    cascades to its tasks (FLAN-01.2), enforced by the database rather than by
    service-layer bookkeeping.

    project_id is carried **in addition to** phase_id — redundant by the tree,
    but required by uq_flan_task_project_key, which makes the task key unique
    within its project. The service sets it from the phase (never from the
    client) and re-checks task.project_id == phase.project_id on every write.

    key is the human handle, `<PREFIX>-<n>` unpadded (D-V5P1-7) from the
    project's key_prefix, generated with a numeric-safe cast so PRJ-9 → PRJ-10
    (D-P8-6).

    status is To Do | In Progress | Done — the Done share is what a phase's
    derived % complete counts. start_date/due_date are optional; due == start is
    a valid zero-duration milestone and due < start is refused server-side.

    risk_level is none | low | medium | high; pinned flags a task for the top of
    a board.
    """

    __tablename__ = "flan_task"
    __table_args__ = (
        UniqueConstraint("project_id", "key", name="uq_flan_task_project_key"),
    )

    # --- Primary key — UUID string -----------------------------------------
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Links -------------------------------------------------------------
    # phase_id: owning phase (required); CASCADE — deleting a phase deletes its tasks
    phase_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("flan_phase.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # project_id: owning project; denormalized from the phase so the key can be
    # unique per project (uq_flan_task_project_key)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("flan_project.id"), nullable=False, index=True
    )

    # --- Identity ----------------------------------------------------------
    # key: `<PREFIX>-<n>` unpadded (D-V5P1-7), unique within the project
    key: Mapped[str] = mapped_column(String(20), nullable=False)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    # status: To Do | In Progress | Done (the Done share drives phase % complete)
    status: Mapped[str] = mapped_column(String(20), default="To Do", nullable=False)

    # --- Timing ------------------------------------------------------------
    # due_date == start_date is a valid zero-duration milestone; due < start 4xx
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- Flags -------------------------------------------------------------
    # risk_level: none | low | medium | high
    risk_level: Mapped[str] = mapped_column(String(10), default="none", nullable=False)
    # pinned: surfaces the task at the top of a board
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- Timestamps --------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# ProjectTag / TaskTag — tag join tables (D-V5P1-5)
# ---------------------------------------------------------------------------


class ProjectTag(Base):
    """
    Project tag — one tag applied to one project.

    Composite PK (project_id, tag) makes a tag idempotent per project without a
    surrogate id; project_id FKs with ondelete="CASCADE" so a deleted project
    leaves no orphan tags.

    In Phase 1 a tag is an **opaque normalized string** (D-V5P1-5): no
    `Facet:Value` parsing, no exclusivity rules, no reserved facets — that is
    FLAN-04, next phase. tag is indexed because the facet grouping and filtering
    that phase adds aggregate by it.
    """

    __tablename__ = "flan_project_tag"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("flan_project.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # tag: opaque normalized string in Phase 1; indexed for later group-by-facet
    tag: Mapped[str] = mapped_column(String(60), primary_key=True, nullable=False, index=True)


class TaskTag(Base):
    """
    Task tag — one tag applied to one task.

    Composite PK (task_id, tag), task_id FK with ondelete="CASCADE" so deleting
    a task (or cascading a phase delete through to it) leaves no orphan tags.

    Same Phase-1 semantics as ProjectTag: the tag is an opaque normalized string
    (D-V5P1-5), indexed for the group-by-facet queries FLAN-04 adds.
    """

    __tablename__ = "flan_task_tag"

    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("flan_task.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # tag: opaque normalized string in Phase 1; indexed for later group-by-facet
    tag: Mapped[str] = mapped_column(String(60), primary_key=True, nullable=False, index=True)
