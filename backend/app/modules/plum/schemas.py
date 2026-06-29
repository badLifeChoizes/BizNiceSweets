"""
PLUM Pydantic schemas (request/response models).

Phase 5: Added PartCreate, PartUpdate, PartRead, RevisionCreate,
RevisionRead, PartDetailRead.

Separation:
  - Input schemas (Create/Update): no from_attributes — validate incoming JSON.
  - Response schemas (Read): from_attributes=True — serialize from ORM instances.

All string fields carry max_length matching their plum/models.py column length
(V5 input validation, prevents silent truncation on the DB side).

Design decisions:
  - D-06: part_number is Optional in PartCreate — server auto-generates P##### if omitted.
  - D-07: Revision status transitions are enforced in the service layer, not the schema.
  - D-12: Required-to-create fields are part_number (optional) + description (required).
  - PATCH semantics: PartUpdate uses all-Optional fields; service applies
    model_dump(exclude_unset=True) so only explicitly-provided fields are updated.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Classification Tag schemas
# ---------------------------------------------------------------------------


class TagRead(BaseModel):
    """Classification tag returned to API callers."""

    id: int
    name: str
    sort_order: Optional[int] = None
    active: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Revision schemas
# ---------------------------------------------------------------------------


class RevisionCreate(BaseModel):
    """
    Payload for creating a new revision (POST /plum/parts/{id}/revisions).

    `source_revision_id`: if provided, attributes are cloned from that revision
    (D-03 copy-forward). If None, attributes are copied from the latest revision.
    `reason_for_revision` is strongly recommended (D-09 forward-only model).
    """

    source_revision_id: Optional[str] = None
    description: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, max_length=100)
    unit_of_measure: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    reason_for_revision: Optional[str] = None


class RevisionRead(BaseModel):
    """Revision data returned to API callers. Serialized from PlumPartRevision ORM."""

    id: str
    part_id: str
    revision_number: int
    revision_label: str
    status: str
    description: str
    category: Optional[str] = None
    unit_of_measure: Optional[str] = None
    notes: Optional[str] = None
    reason_for_revision: Optional[str] = None
    created_at: datetime
    released_at: Optional[datetime] = None
    obsoleted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Part schemas
# ---------------------------------------------------------------------------


class PartCreate(BaseModel):
    """
    Part creation payload (POST /plum/parts).

    `part_number` is Optional — the server auto-generates a P##### series
    number if not supplied (D-06). Only `description` is required (D-12).
    tag_ids maps to PlumClassificationTag integer PKs (join table, D-12).
    The first revision in Draft status is auto-created from these attributes (D-03).
    """

    # Identity (D-06)
    part_number: Optional[str] = Field(None, max_length=50)  # server auto-gens if None

    # Required for first revision (D-12 — only description is truly required)
    description: str = Field(..., max_length=500)

    # Optional revision-controlled fields seeded into first revision (D-03)
    category: Optional[str] = Field(None, max_length=100)
    unit_of_measure: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    reason_for_revision: Optional[str] = None  # free-text ECO substitute

    # Classification tags (D-12) — list of PlumClassificationTag.id values
    tag_ids: list[int] = Field(default_factory=list)


class PartUpdate(BaseModel):
    """
    Part update payload (PATCH /plum/parts/{id}).

    All fields Optional — PATCH semantics. Only provided (non-None, non-unset)
    fields are applied by the service layer via model_dump(exclude_unset=True).

    `active=False` triggers archive (D-11 soft-delete).
    Revision-controlled fields (description, category, UoM, notes) in a PATCH
    are only applied to the current Draft revision; updating a Released revision
    returns 422 (D-07 immutability, enforced in service layer).
    """

    part_number: Optional[str] = Field(None, max_length=50)
    active: Optional[bool] = None
    tag_ids: Optional[list[int]] = None

    # Revision-controlled fields (only editable on Draft revisions — D-07)
    description: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, max_length=100)
    unit_of_measure: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class PartRead(BaseModel):
    """
    Part data returned to API callers (list endpoint).

    Includes a summary of the current revision for list display (current_revision_label,
    current_revision_status). These fields are populated by the service layer from the
    latest revision query; they are not ORM columns on PlumPart.

    tags: list of tag names for display (populated by service from join query).
    """

    id: str
    part_number: str
    active: bool
    created_at: datetime
    updated_at: datetime

    # Current revision summary (populated by service from latest revision query)
    current_revision_label: Optional[str] = None
    current_revision_status: Optional[str] = None

    # Classification tag names (populated by service from join query)
    tags: list[str] = []

    model_config = {"from_attributes": True}


class PartDetailRead(BaseModel):
    """
    Full part detail returned for the Part Detail route (GET /plum/parts/{id}).

    Includes the complete revision history ordered newest-first (D-14).
    `revisions` is embedded in the response to avoid a second frontend query
    (RESEARCH Open Question 3 recommendation).
    """

    id: str
    part_number: str
    active: bool
    created_at: datetime
    updated_at: datetime
    tags: list[str] = []

    # Complete revision history, newest-first (D-14)
    revisions: list[RevisionRead] = []

    model_config = {"from_attributes": True}
