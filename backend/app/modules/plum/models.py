"""
PLUM module ORM models.

Tables defined here (all with plum_ table-name prefix):
  plum_classification_tag — seeded tag vocabulary (D-12)
  plum_part               — stable part header record (D-01/D-02)
  plum_part_tag           — join table: part ↔ classification tag (D-12)
  plum_part_revision      — versioned revision snapshot (D-01/D-02/D-07)

Phase 5: Added PLUM Parts & Revisions data layer (PLUM-01, PLUM-02, PLUM-03).

All models inherit from Base so that Base.metadata is populated when
app.core.models (the central aggregator) is imported by Alembic's env.py.

Design decisions (locked):
  - D-01/D-02: Two-table model. plum_part is the stable header (part number,
    classification tags). plum_part_revision snapshots revision-controlled
    attributes per revision (description, category, UoM, notes).
  - D-07: Revision lifecycle states: draft → in_review → released → obsolete.
    The revision carries the status, not the part.
  - D-08: Exactly one Released revision per part at any time, enforced by the
    partial unique index `uq_plum_part_one_released` in migration 0005.
  - D-11: Soft-delete on parts via `active=False` (matches SYERP partner pattern).
  - D-12: Classification tags are a join table (plum_part_tag) for normalization.

CRITICAL: No ORM relationships declared on PlumPart or PlumPartRevision.
Use explicit `select` queries in service functions to load revisions.
Adding ORM relationships requires lazy="selectin" to avoid MissingGreenlet
in async context (RESEARCH.md Pitfall 1 — same pitfall documented in
syerp/models.py lines 99–102).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


# ---------------------------------------------------------------------------
# PlumClassificationTag — seeded lookup table for part classification (D-12)
# ---------------------------------------------------------------------------


class PlumClassificationTag(Base):
    """
    Classification tag lookup table. Seeded at startup with six starter values:
    Purchased, Manufactured, Assembly, Finished Good, Tool, Raw Material (D-12).

    Uses integer PK (autoincrement) — mirrors GLAccount pattern for seeded
    lookup tables where natural text keys (name) carry the domain identity.
    Vocabulary is editable via the `plum.tag_vocabulary_editable` setting.
    """

    __tablename__ = "plum_classification_tag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ---------------------------------------------------------------------------
# PlumPart — stable part header (D-01/D-02)
# ---------------------------------------------------------------------------


class PlumPart(Base):
    """
    Stable part header record.

    Part identity (part number, classification tags) is shared across all
    revisions. Revision-controlled attributes (description, category, UoM,
    notes) are stored on PlumPartRevision.

    `active=False` is the soft-delete / archive flag (D-11). Archived parts
    are hidden from default list queries but retained for Phase-6 FK references.
    """

    __tablename__ = "plum_part"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # part_number: auto-generated P##### series; user-editable before save; unique (D-06)
    part_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    # active: soft-delete flag (D-11); False = archived; hidden from default lists
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # No ORM relationships declared on PlumPart or PlumPartRevision.
    # Use explicit `select` queries in service functions to load revisions.
    # Adding ORM relationships requires lazy="selectin" to avoid MissingGreenlet
    # in async context (RESEARCH.md Pitfall 1; syerp/models.py lines 99-102).


# ---------------------------------------------------------------------------
# PlumPartTag — join table: part ↔ classification tag (D-12)
# ---------------------------------------------------------------------------


class PlumPartTag(Base):
    """
    Many-to-many join table between PlumPart and PlumClassificationTag.

    Composite primary key (part_id, tag_id). No additional columns needed
    in v1. Phase 6 can add metadata (e.g. added_by, added_at) if required.
    """

    __tablename__ = "plum_part_tag"

    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plum_part.id"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("plum_classification_tag.id"), primary_key=True
    )


# ---------------------------------------------------------------------------
# PlumPartRevision — versioned revision snapshot (D-01/D-02/D-07)
# ---------------------------------------------------------------------------


class PlumPartRevision(Base):
    """
    Per-revision snapshot of revision-controlled part attributes.

    Status FSM (D-07):
      draft → in_review → released → obsolete
      in_review → draft (reject)
      released → obsolete (auto-triggered by supersede, D-08)

    `revision_number` (integer 1,2,3...) uniquely orders revisions per part
    and is used for "latest revision" resolution (MAX query — Pattern 4 in
    RESEARCH.md / Open Question 2 recommendation).

    The partial unique index `uq_plum_part_one_released` (created in migration
    0005) enforces at most one Released revision per part at the DB level
    (Pitfall 3 / T-05-01).
    """

    __tablename__ = "plum_part_revision"

    __table_args__ = (
        # Composite index for "find revisions for a part filtered by status"
        # queries (supports the supersede check in advance_revision_status).
        Index("ix_plum_part_revision_part_id_status", "part_id", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plum_part.id"), nullable=False, index=True
    )
    # revision_number: per-part integer sequence (1, 2, 3...) for ordering
    # and "latest revision" resolution via MAX query (RESEARCH Pattern 4)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # revision_label: human-readable label ("A", "B", "0.1.0", etc.)
    # Generated from the plum.revision_scheme setting (D-04/D-05)
    revision_label: Mapped[str] = mapped_column(String(20), nullable=False)
    # status: draft | in_review | released | obsolete (D-07)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", index=True
    )

    # --- Revision-controlled attribute snapshot (D-02) ---------------------
    # These fields are frozen at the revision level; changing them requires
    # creating a new revision (Released revisions are immutable — D-07).
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit_of_measure: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_for_revision: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Timestamps -------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    obsoleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
