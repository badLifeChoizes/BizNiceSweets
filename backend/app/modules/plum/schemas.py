"""
PLUM Pydantic schemas (request/response models).

Phase 5: Added PartCreate, PartUpdate, PartRead, RevisionCreate,
RevisionRead, PartDetailRead.

Phase 6: Added BOM, AVL, cost, and import/export schemas:
  BomItemCreate, BomItemUpdate, BomItemRead
  BomTreeNode (recursive — children: list[BomTreeNode])
  FlatBomRow, WhereUsedRow
  AvlLinkCreate, AvlLinkUpdate, AvlLinkRead
  PriceBreakCreate, PriceBreakRead
  CostUpdate, CostRead
  ImportRowError, ImportPreviewResponse, ImportCommitResponse
  RevisionRead extended with 5 optional cost fields.

Separation:
  - Input schemas (Create/Update): no from_attributes — validate incoming JSON.
  - Response schemas (Read): from_attributes=True — serialize from ORM instances.
  - BomTreeNode: from_attributes=False — built from dicts (recursive CTE rows).

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
from decimal import Decimal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Classification Tag schemas
# ---------------------------------------------------------------------------


class TagRead(BaseModel):
    """Classification tag returned to API callers."""

    id: int
    name: str
    sort_order: int | None = None
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

    source_revision_id: str | None = None
    description: str | None = Field(None, max_length=500)
    category: str | None = Field(None, max_length=100)
    unit_of_measure: str | None = Field(None, max_length=50)
    notes: str | None = None
    reason_for_revision: str | None = None


class RevisionRead(BaseModel):
    """Revision data returned to API callers. Serialized from PlumPartRevision ORM."""

    id: str
    part_id: str
    revision_number: int
    revision_label: str
    status: str
    description: str
    category: str | None = None
    unit_of_measure: str | None = None
    notes: str | None = None
    reason_for_revision: str | None = None
    created_at: datetime
    released_at: datetime | None = None
    obsoleted_at: datetime | None = None

    # Phase 6 cost fields (D-06/D-09/D-12/D-14) — all optional; null until set
    material_cost: Decimal | None = None
    sale_price: Decimal | None = None
    released_cost_snapshot: Decimal | None = None
    selected_vendor_link_id: str | None = None
    selected_price_break_index: int | None = None

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
    part_number: str | None = Field(None, max_length=50)  # server auto-gens if None

    # Required for first revision (D-12 — only description is truly required)
    description: str = Field(..., max_length=500)

    # Optional revision-controlled fields seeded into first revision (D-03)
    category: str | None = Field(None, max_length=100)
    unit_of_measure: str | None = Field(None, max_length=50)
    notes: str | None = None
    reason_for_revision: str | None = None  # free-text ECO substitute

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

    part_number: str | None = Field(None, max_length=50)
    active: bool | None = None
    tag_ids: list[int] | None = None

    # Revision-controlled fields (only editable on Draft revisions — D-07)
    description: str | None = Field(None, max_length=500)
    category: str | None = Field(None, max_length=100)
    unit_of_measure: str | None = Field(None, max_length=50)
    notes: str | None = None


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
    current_revision_label: str | None = None
    current_revision_status: str | None = None

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


# ---------------------------------------------------------------------------
# Phase 6 schemas — BOM (PLUM-04/05/06)
# ---------------------------------------------------------------------------


class BomItemCreate(BaseModel):
    """
    Payload for adding a child part to a revision's BOM
    (POST /plum/parts/{id}/bom).

    `qty` must be positive (D-04 — zero-quantity BOM lines are invalid).
    `ref_des` is optional reference designator string (e.g., "R1, R2, C4").
    """

    child_part_id: str
    qty: Decimal = Field(..., gt=0)
    ref_des: str | None = Field(None, max_length=500)
    sort_order: int | None = None


class BomItemUpdate(BaseModel):
    """
    Payload for updating a BOM line (PATCH /plum/parts/{id}/bom/{line_id}).

    All fields Optional — PATCH semantics.
    Only editable on Draft revisions (D-07 immutability enforced in service).
    """

    qty: Decimal | None = Field(None, gt=0)
    ref_des: str | None = Field(None, max_length=500)
    sort_order: int | None = None


class BomItemRead(BaseModel):
    """BOM line returned to API callers. Serialized from PlumBomItem ORM."""

    id: str
    parent_revision_id: str
    child_part_id: str
    qty: Decimal
    ref_des: str | None = None
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class BomTreeNode(BaseModel):
    """
    Recursive node in the BOM tree response (GET /plum/parts/{id}/bom/tree).

    `children` is self-referential — call BomTreeNode.model_rebuild() after
    class definition so Pydantic resolves the forward reference correctly.

    Built from dicts (recursive CTE rows), NOT from ORM instances, so
    from_attributes is False (default).
    `is_unreleased`: True when the resolved child revision is not in
    'released' status (D-02 provisional warning for BOM tree display).
    """

    bom_item_id: str
    part_id: str
    part_number: str
    unit_of_measure: str | None = None
    qty: Decimal
    ref_des: str | None = None
    sort_order: int
    depth: int = 0
    is_unreleased: bool = False
    effective_cost: Decimal | None = None
    effective_cost_source: str | None = None  # "vendor price" | "manual" | "roll-up" | "uncosted"
    children: list[BomTreeNode] = []


# Resolve self-referential forward reference for `children`
BomTreeNode.model_rebuild()


class FlatBomRow(BaseModel):
    """
    A row in the flat (rolled-up) BOM response (GET /plum/parts/{id}/bom/flat).

    `total_qty` is the rolled-up quantity across all paths to this child part
    (D-04 shared-part quantity aggregation).
    """

    part_id: str
    part_number: str
    unit_of_measure: str | None = None
    total_qty: Decimal
    effective_cost: Decimal | None = None
    extended_cost: Decimal | None = None  # total_qty × effective_cost
    is_unreleased: bool = False


class WhereUsedRow(BaseModel):
    """
    A row in the where-used response (GET /plum/parts/{id}/where-used).

    `direct`: True if this parent directly references the query part.
    `indirect`: True if the reference is via a nested BOM path (transitive).
    `via_part_number`: for an indirect parent, the intermediate part through
    which the query part is reached on the shallowest path. None when direct.
    """

    parent_part_id: str
    parent_part_number: str
    parent_revision_id: str
    parent_revision_label: str
    parent_revision_status: str
    direct: bool = True
    indirect: bool = False
    via_part_number: str | None = None


# ---------------------------------------------------------------------------
# Phase 6 schemas — AVL (PLUM-07)
# ---------------------------------------------------------------------------


class PriceBreakCreate(BaseModel):
    """
    Payload for adding a price break to an AVL link
    (POST /plum/parts/{id}/avl/{link_id}/price-breaks).
    """

    qty_threshold: int = Field(..., ge=1)
    unit_cost: Decimal = Field(..., ge=0)
    lead_days: int | None = Field(None, ge=0)
    sort_order: int | None = None


class PriceBreakRead(BaseModel):
    """Price break returned to API callers. Serialized from PlumAvlPriceBreak ORM."""

    id: str
    avl_link_id: str
    qty_threshold: int
    unit_cost: Decimal
    lead_days: int | None = None
    sort_order: int

    model_config = {"from_attributes": True}


class AvlLinkCreate(BaseModel):
    """
    Payload for linking a vendor to a part (POST /plum/parts/{id}/avl).

    `vendor_id` must reference a syerp_partner with is_vendor=True (D-13,
    enforced in service layer).
    """

    vendor_id: str
    vendor_part_number: str | None = Field(None, max_length=100)
    preferred: bool = False
    notes: str | None = None


class AvlLinkUpdate(BaseModel):
    """
    Payload for updating an AVL link (PATCH /plum/parts/{id}/avl/{link_id}).

    All fields Optional — PATCH semantics.
    """

    vendor_part_number: str | None = Field(None, max_length=100)
    preferred: bool | None = None
    notes: str | None = None
    active: bool | None = None


class AvlLinkRead(BaseModel):
    """AVL link returned to API callers. Includes embedded price breaks."""

    id: str
    part_id: str
    vendor_id: str
    vendor_part_number: str | None = None
    preferred: bool
    notes: str | None = None
    active: bool
    price_breaks: list[PriceBreakRead] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Phase 6 schemas — Costing (PLUM-08/09)
# ---------------------------------------------------------------------------


class CostUpdate(BaseModel):
    """
    Payload for updating cost data on a revision
    (PATCH /plum/parts/{id}/revisions/{rev_id}/cost).

    Selecting a vendor link + price break index sets the vendor-sourced
    effective cost (D-07 step 1). material_cost is the manual override (D-06).
    """

    material_cost: Decimal | None = Field(None, ge=0)
    sale_price: Decimal | None = Field(None, ge=0)
    selected_vendor_link_id: str | None = None
    selected_price_break_index: int | None = Field(None, ge=0)


class CostRead(BaseModel):
    """
    Computed cost summary for a revision
    (GET /plum/parts/{id}/revisions/{rev_id}/cost).

    `effective_cost`: the cost used for roll-up — vendor price if selected,
    else manual material_cost, else BOM roll-up total, else None ("uncosted").
    `effective_cost_source`: one of "vendor price" | "manual" | "roll-up" | "uncosted".
    `bom_rollup_cost`: live recursive BOM roll-up (always computed, even for Released).
    `margin` and `margin_pct`: sale_price minus effective_cost calculations.
    Released revisions additionally expose `released_cost_snapshot` (frozen at release).
    """

    material_cost: Decimal | None = None
    sale_price: Decimal | None = None
    released_cost_snapshot: Decimal | None = None
    selected_vendor_link_id: str | None = None
    selected_price_break_index: int | None = None
    effective_cost: Decimal | None = None
    effective_cost_source: str | None = None
    bom_rollup_cost: Decimal | None = None
    margin: Decimal | None = None
    margin_pct: Decimal | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Phase 6 schemas — Import / Export (PLUM-10)
# ---------------------------------------------------------------------------


class ImportRowError(BaseModel):
    """
    A single row-level validation error from an import preview operation.

    `row`: 1-based row number in the source file (1 = first data row after header).
    `field`: the field name that failed validation (may be empty for row-level errors).
    `message`: human-readable description of the problem.
    """

    row: int
    field: str
    message: str


class ImportPreviewResponse(BaseModel):
    """
    Preview response for a dry-run import validation
    (POST /plum/import/validate).

    Reports how many rows would be inserted vs. updated, and any validation
    errors encountered. No data is written. Caller reviews then calls
    POST /plum/import/commit to apply (D-18 three-step import flow).
    """

    new_count: int
    updated_count: int
    errors: list[ImportRowError] = []


class ImportCommitResponse(BaseModel):
    """
    Result of a committed import (POST /plum/import/commit).

    D-18 no-delete contract: import never removes parts or revisions.
    Only insertions and updates are performed.
    """

    inserted: int
    updated: int
