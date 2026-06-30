"""
PLUM module ORM models.

Tables defined here (all with plum_ table-name prefix):
  plum_classification_tag — seeded tag vocabulary (D-12)
  plum_part               — stable part header record (D-01/D-02)
  plum_part_tag           — join table: part ↔ classification tag (D-12)
  plum_part_revision      — versioned revision snapshot (D-01/D-02/D-07)
  plum_bom_item           — BOM directed edge: parent_revision → child_part (D-01/D-02/D-04)
  plum_avl_link           — Approved Vendor List link: part → syerp_partner (D-11/D-13)
  plum_avl_price_break    — Quantity price-break rows per AVL link (D-11)

Phase 5: Added PLUM Parts & Revisions data layer (PLUM-01, PLUM-02, PLUM-03).
Phase 6: Added BOM, AVL, price-break tables + cost columns on plum_part_revision
         (PLUM-04..10, D-04/D-06/D-09/D-11/D-12/D-13/D-14).

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

from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
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

    # --- Cost columns (Phase 6: D-06/D-09/D-12/D-14) — added by migration 0006 ----
    material_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=6), nullable=True
    )
    sale_price: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=6), nullable=True
    )
    released_cost_snapshot: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=18, scale=6), nullable=True
    )
    # selected_vendor_link_id FKs plum_avl_link.id; SET NULL on delete (T-06-01)
    # The FK constraint is added in migration 0006 Zone 3 (after plum_avl_link exists).
    selected_vendor_link_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("plum_avl_link.id", ondelete="SET NULL"), nullable=True
    )
    selected_price_break_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # No ORM relationships declared on PlumPartRevision.
    # Use explicit `select` queries in service functions.
    # See PlumPart docstring (lines above) for MissingGreenlet pitfall details.


# ---------------------------------------------------------------------------
# PlumBomItem — BOM edge table (D-01/D-02/D-04)
# ---------------------------------------------------------------------------


class PlumBomItem(Base):
    """
    BOM directed edge: parent_revision → child_part.
    D-01: revision owns the BOM. D-02: child resolves to latest Released
    revision at view time. D-04: carries decimal qty + optional ref_des.
    No ORM relationships (MissingGreenlet pitfall — see PlumPart docstring).
    """

    __tablename__ = "plum_bom_item"

    __table_args__ = (
        # T-06-03: prevent duplicate child under same revision at DB level
        UniqueConstraint(
            "parent_revision_id", "child_part_id", name="uq_plum_bom_item_parent_child"
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    parent_revision_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plum_part_revision.id"), nullable=False, index=True
    )
    child_part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plum_part.id"), nullable=False, index=True
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
    ref_des: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # No ORM relationships (MissingGreenlet pitfall — see PlumPart docstring).


# ---------------------------------------------------------------------------
# PlumAvlLink — Approved Vendor List link (D-11/D-13) — first cross-module FK
# ---------------------------------------------------------------------------


class PlumAvlLink(Base):
    """
    Part-level (live, not revision-controlled) link to a SYERP vendor.
    Cross-module FK: vendor_id → syerp_partner.id (validates SYERP-as-hub).
    `preferred` = sourcing designation (multiple allowed per part).
    `active` = soft-delete flag (mirrors PlumPart.active convention).
    No ORM relationships (MissingGreenlet pitfall — see PlumPart docstring).
    """

    __tablename__ = "plum_avl_link"

    __table_args__ = (
        # T-06-03: prevent duplicate vendor under same part at DB level
        UniqueConstraint("part_id", "vendor_id", name="uq_plum_avl_link_part_vendor"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plum_part.id"), nullable=False, index=True
    )
    vendor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("syerp_partner.id"), nullable=False, index=True
    )
    vendor_part_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # No ORM relationships (MissingGreenlet pitfall — see PlumPart docstring).


# ---------------------------------------------------------------------------
# PlumAvlPriceBreak — quantity price-break rows per AVL link (D-11)
# ---------------------------------------------------------------------------


class PlumAvlPriceBreak(Base):
    """
    Price-break row belonging to a PlumAvlLink. Always sorted by qty_threshold
    ascending; sort_order enforced on save to keep selected_price_break_index stable.
    avl_link_id FK uses ondelete=CASCADE (T-06-02) — orphan rows auto-removed.
    No ORM relationships (MissingGreenlet pitfall — see PlumPart docstring).
    """

    __tablename__ = "plum_avl_price_break"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    avl_link_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("plum_avl_link.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    qty_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
    lead_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # No ORM relationships (MissingGreenlet pitfall — see PlumPart docstring).
