# Phase 6: PLUM BOM, Costing & Integration — Pattern Map

**Mapped:** 2026-06-30
**Files analyzed:** 21 new/modified files
**Analogs found:** 20 / 21

---

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|------|-----------|----------------|---------------|
| `backend/app/modules/plum/models.py` | model | CRUD (extend) | `backend/app/modules/plum/models.py` | exact — same file, additive edit |
| `backend/alembic/versions/0006_plum_bom_costing.py` | migration | batch (DDL) | `backend/alembic/versions/0005_plum_tables.py` | exact |
| `backend/app/modules/plum/schemas.py` | schema | request-response (extend) | `backend/app/modules/plum/schemas.py` | exact — same file, additive edit |
| `backend/app/modules/plum/service.py` | service | CRUD + transform (extend) | `backend/app/modules/plum/service.py` | exact — same file, additive edit |
| `backend/app/modules/plum/bom_cte.py` | utility | transform | `backend/app/modules/plum/service.py` (db.execute + text() pattern) | role-match |
| `backend/app/modules/plum/router.py` | router | request-response (extend) | `backend/app/modules/plum/router.py` | exact — same file, additive edit |
| `backend/app/core/models.py` | config | batch (extend) | `backend/app/core/models.py` | exact — no change needed (plum models already imported) |
| `backend/requirements.txt` | config | — | `backend/requirements.txt` | exact — single-line addition |
| `backend/tests/plum/test_bom.py` | test | request-response | `backend/tests/plum/test_parts.py` | exact |
| `backend/tests/plum/test_avl.py` | test | request-response | `backend/tests/plum/test_parts.py` | exact |
| `backend/tests/plum/test_costing.py` | test | request-response | `backend/tests/plum/test_revisions.py` | role-match |
| `backend/tests/plum/test_import_export.py` | test | file-I/O | `backend/tests/plum/test_parts.py` | role-match |
| `frontend/src/routes/plum/PartDetail.tsx` | component | request-response (extend) | `frontend/src/routes/plum/PartDetail.tsx` | exact — same file, additive sections |
| `frontend/src/routes/plum/ImportExport.tsx` | component | file-I/O | `frontend/src/routes/plum/PartsList.tsx` | role-match |
| `frontend/src/routes/plum/components/BomTree.tsx` | component | request-response | `frontend/src/routes/plum/components/PartSheet.tsx` (structure) + `PartDetail.tsx` (recursive render) | role-match |
| `frontend/src/routes/plum/components/BomLineSheet.tsx` | component | request-response | `frontend/src/routes/plum/components/PartSheet.tsx` | exact |
| `frontend/src/routes/plum/components/AvlLinkSheet.tsx` | component | request-response | `frontend/src/routes/plum/components/PartSheet.tsx` | exact |
| `frontend/src/routes/plum/components/PriceBreakEditor.tsx` | component | request-response | `frontend/src/routes/plum/PartDetail.tsx` (inline Card + dl list pattern) | role-match |
| `frontend/src/routes/plum/components/PlumNav.tsx` | component | request-response (extend) | `frontend/src/routes/plum/components/PlumNav.tsx` | exact — same file, additive tab |
| `frontend/src/routes/plum/components/BomTree.test.tsx` | test | request-response | `frontend/src/routes/plum/PartsList.test.tsx` | exact |

---

## Pattern Assignments

### `backend/app/modules/plum/models.py` (model, CRUD — extend existing)

**Analog:** same file — `backend/app/modules/plum/models.py`

**Module docstring pattern** (lines 1–31): update the `Tables defined here` block to list three new tables, extend the `Phase N` comment.

**UUID string PK + no-ORM-relationships pattern** (lines 85–108):
```python
# From: backend/app/modules/plum/models.py lines 85-93 + 105-108
id: Mapped[str] = mapped_column(
    String(36), primary_key=True, default=lambda: str(uuid.uuid4())
)
# No ORM relationships declared on PlumPart or PlumPartRevision.
# Use explicit `select` queries in service functions to load revisions.
# Adding ORM relationships requires lazy="selectin" to avoid MissingGreenlet
# in async context (RESEARCH.md Pitfall 1; syerp/models.py lines 99-102).
```

**`active` soft-delete bool column pattern** (lines 92–93 on PlumPart):
```python
# From: backend/app/modules/plum/models.py lines 92-93
active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
```

**FK column with `index=True` pattern** (lines 168–170 on PlumPartRevision):
```python
# From: backend/app/modules/plum/models.py lines 168-170
part_id: Mapped[str] = mapped_column(
    String(36), ForeignKey("plum_part.id"), nullable=False, index=True
)
```

**`created_at` timestamp pattern** (lines 96–98 on PlumPart):
```python
# From: backend/app/modules/plum/models.py lines 96-98
created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
)
```

**Import additions needed** at the top of models.py — add `Numeric` to the SQLAlchemy imports and add `Decimal` from stdlib:
```python
# Extend existing line 37 of backend/app/modules/plum/models.py:
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
```

**New models to append** (after `PlumPartRevision`, following section-banner style):
```python
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

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    parent_revision_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plum_part_revision.id"), nullable=False, index=True
    )
    child_part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plum_part.id"), nullable=False
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
    ref_des: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# PlumAvlLink — Approved Vendor List link (D-11/D-13) — first cross-module FK
# ---------------------------------------------------------------------------
class PlumAvlLink(Base):
    """
    Part-level (live, not revision-controlled) link to a SYERP vendor.
    Cross-module FK: vendor_id → syerp_partner.id (validates SYERP-as-hub).
    `preferred` = sourcing designation (multiple allowed per part).
    `active` = soft-delete flag (mirrors PlumPart.active convention).
    No ORM relationships (MissingGreenlet pitfall).
    """
    __tablename__ = "plum_avl_link"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plum_part.id"), nullable=False, index=True
    )
    vendor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("syerp_partner.id"), nullable=False
    )
    vendor_part_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# PlumAvlPriceBreak — quantity price-break rows per AVL link (D-11)
# ---------------------------------------------------------------------------
class PlumAvlPriceBreak(Base):
    """
    Price-break row belonging to a PlumAvlLink. Always sorted by qty_threshold
    ascending; sort_order enforced on save to keep selected_price_break_index stable.
    No ORM relationships (MissingGreenlet pitfall).
    """
    __tablename__ = "plum_avl_price_break"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    avl_link_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plum_avl_link.id"), nullable=False, index=True
    )
    qty_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
    lead_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

**New columns to add to `PlumPartRevision`** (after `obsoleted_at` at line 198):
```python
# Cost columns (Phase 6: D-06/D-09/D-12/D-14) — added by migration 0006
material_cost: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=6), nullable=True)
sale_price: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=6), nullable=True)
released_cost_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(precision=18, scale=6), nullable=True)
selected_vendor_link_id: Mapped[str | None] = mapped_column(
    String(36), ForeignKey("plum_avl_link.id"), nullable=True
)
selected_price_break_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

---

### `backend/alembic/versions/0006_plum_bom_costing.py` (migration, batch DDL)

**Analog:** `backend/alembic/versions/0005_plum_tables.py`

**File header + revision identifiers pattern** (lines 1–40 of 0005):
```python
# From: backend/alembic/versions/0005_plum_tables.py lines 31-40
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

**`op.create_table` with named FK constraints pattern** (lines 94–110 of 0005):
```python
# From: backend/alembic/versions/0005_plum_tables.py lines 94-110
op.create_table(
    "plum_part_tag",
    sa.Column("part_id", sa.String(length=36), nullable=False),
    sa.Column("tag_id", sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint("part_id", "tag_id", name="pk_plum_part_tag"),
    sa.ForeignKeyConstraint(["part_id"], ["plum_part.id"], name="fk_plum_part_tag_part_id"),
    sa.ForeignKeyConstraint(["tag_id"], ["plum_classification_tag.id"], name="fk_plum_part_tag_tag_id"),
)
```

**`op.create_index` pattern** (lines 155–160 of 0005):
```python
# From: backend/alembic/versions/0005_plum_tables.py lines 155-160
op.create_index("ix_plum_part_revision_part_id", "plum_part_revision", ["part_id"], unique=False)
```

**`op.create_index` with `postgresql_where` partial index** (lines 177–183 of 0005):
```python
# From: backend/alembic/versions/0005_plum_tables.py lines 177-183
op.create_index(
    "uq_plum_part_one_released",
    "plum_part_revision",
    ["part_id"],
    unique=True,
    postgresql_where=sa.text("status = 'released'"),
)
```

**`op.add_column` pattern for extending existing table** (new for Phase 6 — no analog in 0005; use standard Alembic):
```python
def upgrade() -> None:
    # ── Create new tables (plum_bom_item, plum_avl_link, plum_avl_price_break) ──
    op.create_table("plum_avl_link", ...)
    op.create_table("plum_avl_price_break", ...)
    op.create_table("plum_bom_item", ...)

    # ── Extend plum_part_revision with cost columns (D-06/D-09/D-12/D-14) ──
    op.add_column("plum_part_revision", sa.Column("material_cost", sa.Numeric(18, 6), nullable=True))
    op.add_column("plum_part_revision", sa.Column("sale_price", sa.Numeric(18, 6), nullable=True))
    op.add_column("plum_part_revision", sa.Column("released_cost_snapshot", sa.Numeric(18, 6), nullable=True))
    op.add_column("plum_part_revision", sa.Column("selected_vendor_link_id", sa.String(36), nullable=True))
    op.add_column("plum_part_revision", sa.Column("selected_price_break_index", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_plum_revision_selected_avl_link",
        "plum_part_revision", "plum_avl_link",
        ["selected_vendor_link_id"], ["id"],
    )
    # Indexes for new columns / tables
    op.create_index("ix_plum_bom_item_parent_revision_id", "plum_bom_item", ["parent_revision_id"])
    op.create_index("ix_plum_bom_item_child_part_id", "plum_bom_item", ["child_part_id"])
    op.create_index("ix_plum_avl_link_part_id", "plum_avl_link", ["part_id"])
    op.create_index("ix_plum_avl_price_break_avl_link_id", "plum_avl_price_break", ["avl_link_id"])
```

**`downgrade()` reverse order** (lines 186–200 of 0005): drop indexes, then FK constraints, then columns, then tables — in reverse FK dependency order.

---

### `backend/app/modules/plum/schemas.py` (schema, request-response — extend existing)

**Analog:** same file — `backend/app/modules/plum/schemas.py`

**Create schema (input, no `from_attributes`) pattern** (lines 50–65):
```python
# From: backend/app/modules/plum/schemas.py lines 50-65
class RevisionCreate(BaseModel):
    source_revision_id: Optional[str] = None
    description: Optional[str] = Field(None, max_length=500)
    # All fields Optional — PATCH semantics or optional creation fields
```

**Read schema (`from_attributes=True`) pattern** (lines 67–84):
```python
# From: backend/app/modules/plum/schemas.py lines 67-84
class RevisionRead(BaseModel):
    id: str
    part_id: str
    revision_number: int
    # ... all scalar columns matching the ORM model
    model_config = {"from_attributes": True}
```

**New schemas to add** — following established naming + field-length conventions:
```python
# BOM
class BomItemCreate(BaseModel):
    child_part_id: str
    qty: Decimal = Field(..., gt=0)
    ref_des: Optional[str] = Field(None, max_length=500)

class BomItemUpdate(BaseModel):
    qty: Optional[Decimal] = Field(None, gt=0)
    ref_des: Optional[str] = Field(None, max_length=500)

class BomItemRead(BaseModel):
    id: str
    parent_revision_id: str
    child_part_id: str
    qty: Decimal
    ref_des: Optional[str] = None
    sort_order: int
    created_at: datetime
    model_config = {"from_attributes": True}

# AVL
class AvlLinkCreate(BaseModel):
    vendor_id: str
    vendor_part_number: Optional[str] = Field(None, max_length=100)
    preferred: bool = False
    notes: Optional[str] = None

class AvlLinkUpdate(BaseModel):
    vendor_part_number: Optional[str] = Field(None, max_length=100)
    preferred: Optional[bool] = None
    notes: Optional[str] = None

class PriceBreakCreate(BaseModel):
    qty_threshold: int = Field(..., ge=1)
    unit_cost: Decimal = Field(..., ge=0)
    lead_days: Optional[int] = Field(None, ge=0)

class PriceBreakRead(BaseModel):
    id: str
    avl_link_id: str
    qty_threshold: int
    unit_cost: Decimal
    lead_days: Optional[int] = None
    sort_order: int
    model_config = {"from_attributes": True}

class AvlLinkRead(BaseModel):
    id: str
    part_id: str
    vendor_id: str
    vendor_part_number: Optional[str] = None
    preferred: bool
    notes: Optional[str] = None
    active: bool
    price_breaks: list[PriceBreakRead] = []
    model_config = {"from_attributes": True}

# Cost / margin
class CostUpdate(BaseModel):
    material_cost: Optional[Decimal] = Field(None, ge=0)
    sale_price: Optional[Decimal] = Field(None, ge=0)
    selected_vendor_link_id: Optional[str] = None
    selected_price_break_index: Optional[int] = Field(None, ge=0)

class CostRead(BaseModel):
    material_cost: Optional[Decimal] = None
    sale_price: Optional[Decimal] = None
    released_cost_snapshot: Optional[Decimal] = None
    selected_vendor_link_id: Optional[str] = None
    selected_price_break_index: Optional[int] = None
    effective_cost: Optional[Decimal] = None   # computed by service
    effective_cost_source: Optional[str] = None  # "vendor price" | "manual" | "roll-up" | "uncosted"
    bom_rollup_cost: Optional[Decimal] = None  # live roll-up (always shown even for Released)
    margin: Optional[Decimal] = None            # sale_price − effective_cost
    margin_pct: Optional[Decimal] = None        # margin / effective_cost × 100
    model_config = {"from_attributes": True}

# Import / Export
class ImportPreviewRead(BaseModel):
    new_count: int
    update_count: int
    errors: list[str]

class ImportResultRead(BaseModel):
    inserted: int
    updated: int
```

---

### `backend/app/modules/plum/service.py` (service, CRUD + transform — extend existing)

**Analog:** same file — `backend/app/modules/plum/service.py`

**Setting lookup pattern** (lines 114–127) — copy for `_get_system_currency`:
```python
# From: backend/app/modules/plum/service.py lines 114-127
async def _get_revision_scheme(db: AsyncSession) -> str:
    from app.core.settings_model import Setting
    result = await db.execute(
        select(Setting.value).where(Setting.key == "plum.revision_scheme")
    )
    value: str | None = result.scalar()
    return value or "asme"

# Phase-6 analog:
async def _get_system_currency(db: AsyncSession) -> str:
    from app.core.settings_model import Setting
    result = await db.execute(
        select(Setting.value).where(Setting.key == "locale.currency")
    )
    value: str | None = result.scalar()
    return value or "USD"
```

**`write_audit` call pattern** (lines 695–702):
```python
# From: backend/app/modules/plum/service.py lines 695-702
await write_audit(
    db,
    actor_id=actor_id,
    action="revision.created",
    target_type="revision",
    target_id=str(new_revision.id),
    detail=f"Revision {new_revision.revision_label} created for part {part_id}",
)
```

**`db.add` + `db.commit` + `db.refresh` pattern** (lines 691–693):
```python
# From: backend/app/modules/plum/service.py lines 691-693
db.add(new_revision)
await db.commit()
await db.refresh(new_revision)
```

**`db.flush()` between two dependent writes in one transaction** (lines 772–780):
```python
# From: backend/app/modules/plum/service.py lines 772-780
prior_released.status = "obsolete"
prior_released.obsoleted_at = datetime.now(timezone.utc)
await db.flush()  # Must flush before next write that violates the partial unique index
await write_audit(db, actor_id=actor_id, action="revision.obsoleted", ...)
```

**`HTTPException` with status codes pattern** (lines 748–762):
```python
# From: backend/app/modules/plum/service.py lines 748-762
raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision ... not found")
raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cannot edit BOM on a non-Draft revision")
```

**`db.execute(select(...))` explicit query pattern** (lines 604–612 in `get_released_revision`):
```python
# From: backend/app/modules/plum/service.py lines 604-612
result = await db.execute(
    select(PlumPartRevision)
    .where(PlumPartRevision.part_id == part_id, PlumPartRevision.status == "released")
)
return result.scalars().first()
```

**Hook point for as-released cost snapshot (D-14)** — insert inside `advance_revision_status` (lines 765–789), after the supersede flush and before updating `revision.released_at`:
```python
# From: backend/app/modules/plum/service.py lines 765-786 (context for insertion point)
if target_status == "released":
    prior_released = await get_released_revision(db, part_id)
    if prior_released and prior_released.id != revision_id:
        prior_released.status = "obsolete"
        prior_released.obsoleted_at = datetime.now(timezone.utc)
        await db.flush()
        await write_audit(...)
    # ← INSERT Phase-6 cost snapshot here:
    # roll_up = await compute_bom_rollup(db, revision.id)
    # effective_cost, _ = await get_effective_cost(db, revision, roll_up)
    # revision.released_cost_snapshot = effective_cost
    scheme = await _get_revision_scheme(db)
    new_label = _release_label(scheme, revision.revision_label)
    revision.revision_label = new_label
    revision.released_at = datetime.now(timezone.utc)
```

**Hook point for BOM copy-forward (D-01)** — insert in `create_revision` (lines 691–693), after `db.add(new_revision)` and `await db.commit()`, call `await copy_bom_forward(db, source.id, new_revision.id)` using `db.flush()` inside `copy_bom_forward` so it stays in the same transaction. `copy_bom_forward` must use `db.flush()` not `db.commit()`.

---

### `backend/app/modules/plum/bom_cte.py` (utility, transform — new file)

**Analog:** `backend/app/modules/plum/service.py` (pattern only — `db.execute` + SQLAlchemy `select`)

**Raw SQL `text()` + named bindparams pattern** — no existing analog in the codebase; use RESEARCH.md Pattern 4 directly:
```python
# Pattern to follow (verified against SQLAlchemy 2.0 + asyncio project stack):
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Named bindparams (:name) — never string interpolation, never positional %s
result = await db.execute(
    text(BOM_TREE_CTE_SQL),
    {"parent_revision_id": revision_id}   # dict of named params
)
rows = result.mappings().all()  # list of RowMapping (dict-like access)
```

**Module structure**: define CTE SQL as module-level string constants (uppercase), then `async def` functions that call `db.execute(text(CONSTANT), params)`. Source each constant with an inline comment: `# Source: RESEARCH.md Pattern 4` or `# [ASSUMED]: standard PostgreSQL WITH RECURSIVE`.

---

### `backend/app/modules/plum/router.py` (router, request-response — extend existing)

**Analog:** same file — `backend/app/modules/plum/router.py`

**Router header + imports pattern** (lines 38–65):
```python
# From: backend/app/modules/plum/router.py lines 38-65
from __future__ import annotations
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.auth.service import write_audit
from app.modules.plum.schemas import (PartCreate, PartDetailRead, ...)
from app.modules.plum.service import (advance_revision_status, create_part, ...)

router = APIRouter(prefix="/plum", tags=["plum"])
```

**GET endpoint with `plum:read` guard** (lines 73–96):
```python
# From: backend/app/modules/plum/router.py lines 73-96
@router.get("/parts", response_model=list[PartRead])
async def list_parts_endpoint(
    q: str | None = None,
    current_user=Depends(require_permission("plum:read")),
    db: AsyncSession = Depends(get_db),
) -> list[PartRead]:
    ...
```

**POST endpoint with `plum:write` guard + audit** (lines 127–167):
```python
# From: backend/app/modules/plum/router.py lines 127-167
@router.post("/parts", response_model=PartRead, status_code=status.HTTP_201_CREATED)
async def create_part_endpoint(
    data: PartCreate,
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> PartRead:
    result = await create_part(db, data)
    await write_audit(db, actor_id=str(current_user.id), action="part.created", ...)
    return result
```

**`StreamingResponse` for export endpoints** — new for this project:
```python
# New pattern (no existing codebase analog):
from fastapi.responses import StreamingResponse
@router.get("/export/json")
async def export_json_endpoint(
    current_user=Depends(require_permission("plum:read")),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    await write_audit(db, actor_id=str(current_user.id), action="plum.exported", detail="json")
    return await export_json(db)
# Return type annotation is StreamingResponse, NOT a Pydantic schema
```

**`UploadFile` for import endpoints** — new for this project:
```python
# New pattern (no existing codebase analog):
from fastapi import UploadFile, File
@router.post("/import/validate", response_model=ImportPreviewRead)
async def validate_import_endpoint(
    file: UploadFile = File(...),
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> ImportPreviewRead:
    content = await file.read()
    ...
```

**New endpoint URL structure** (per RESEARCH.md architecture diagram):
```
GET  /plum/parts/{id}/bom/tree          plum:read
GET  /plum/parts/{id}/bom/flat          plum:read
POST /plum/parts/{id}/bom               plum:write  (add line; revision_id in body)
PATCH /plum/parts/{id}/bom/{line_id}    plum:write
DELETE /plum/parts/{id}/bom/{line_id}   plum:write
GET  /plum/parts/{id}/where-used        plum:read
GET  /plum/parts/{id}/avl               plum:read
POST /plum/parts/{id}/avl               plum:write
PATCH /plum/parts/{id}/avl/{link_id}    plum:write
DELETE /plum/parts/{id}/avl/{link_id}   plum:write
GET  /plum/parts/{id}/revisions/{rev_id}/cost   plum:read
PATCH /plum/parts/{id}/revisions/{rev_id}/cost  plum:write
GET  /plum/export/json                  plum:read
GET  /plum/export/excel                 plum:read
POST /plum/import/validate              plum:write
POST /plum/import/commit                plum:write
```

---

### `backend/tests/plum/test_bom.py` / `test_avl.py` / `test_costing.py` / `test_import_export.py` (test)

**Analog:** `backend/tests/plum/test_parts.py`

**Full test file header + fixture pattern** (lines 1–55 of test_parts.py):
```python
# From: backend/tests/plum/test_parts.py lines 1-55
"""
PLUM [BOM/AVL/costing/import-export] tests — Phase 6.

Behaviors tested (PLUM-0X):
  - ...

Tests require a live PostgreSQL database (skip_if_no_db).
These are Wave 0 tests: will FAIL/ERROR until the implementation wave greens them.
Pattern mirrors backend/tests/plum/test_parts.py exactly.
"""
import pytest
import httpx
```

**`create_access_token` permission token pattern** (lines 40–42 of test_parts.py):
```python
# From: backend/tests/plum/test_parts.py lines 40-42
from app.modules.auth.service import create_access_token
token = create_access_token(subject="admin-user", permissions=["plum:write"])
# Read-only tests:
read_token = create_access_token(subject="reader-user", permissions=["plum:read"])
```

**HTTP call + assertion pattern** (lines 44–54 of test_parts.py):
```python
# From: backend/tests/plum/test_parts.py lines 44-54
response = await client.post(
    "/api/v1/plum/parts",
    json={"description": "Widget housing"},
    headers={"Authorization": f"Bearer {token}"},
)
assert response.status_code == 201
body = response.json()
assert "part_number" in body
```

**File upload pattern for `test_import_export.py`** (new pattern — no existing analog):
```python
# httpx multipart for UploadFile endpoints:
import io
json_payload = b'{"schema_version": "1.0", "parts": []}'
files = {"file": ("plum_export.json", io.BytesIO(json_payload), "application/json")}
response = await client.post(
    "/api/v1/plum/import/validate",
    files=files,
    headers={"Authorization": f"Bearer {token}"},
)
```

---

### `frontend/src/routes/plum/PartDetail.tsx` (component, request-response — extend existing)

**Analog:** same file — `frontend/src/routes/plum/PartDetail.tsx`

**Imports pattern** (lines 26–44):
```typescript
// From: frontend/src/routes/plum/PartDetail.tsx lines 26-44
import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { apiClient } from '@/api/client'
```

**Card section pattern for the four new sections** (lines 232–234, per UI-SPEC contract):
```tsx
// From: frontend/src/routes/plum/PartDetail.tsx lines 232-234 + UI-SPEC §Extended Part Detail
<Card>
  <CardHeader className="pb-2">
    <div className="flex items-center justify-between">
      <h2 className="text-base font-semibold text-foreground">{Section Title}</h2>
      {isDraft && <Button variant="outline" size="sm" onClick={...}>Add Part</Button>}
    </div>
  </CardHeader>
  <CardContent>
    {/* section body — see BomTree, AvlPanel, CostPanel, WhereUsedList sub-components */}
  </CardContent>
</Card>
```

**`useQuery` for child resource** (lines 148–153):
```typescript
// From: frontend/src/routes/plum/PartDetail.tsx lines 148-153
const { data: part, isLoading, isError } = useQuery<PartDetailRead, Error>({
  queryKey: ['plum', 'parts', partId],
  queryFn: () => apiClient.get<PartDetailRead>(`/api/v1/plum/parts/${partId}`).then(r => r.data),
  enabled: !!partId,
})
// Phase-6 pattern per new query key hierarchy:
const { data: bomTree } = useQuery({
  queryKey: ['plum', 'parts', partId, 'bom', 'tree'],
  queryFn: () => apiClient.get(`/api/v1/plum/parts/${partId}/bom/tree`).then(r => r.data),
  enabled: !!partId && !!currentRevision,
})
```

**`useMutation` + `invalidateQueries` + `toast` pattern** (lines 156–175):
```typescript
// From: frontend/src/routes/plum/PartDetail.tsx lines 156-175
const mutation = useMutation<..., Error, ...>({
  mutationFn: (vars) => apiClient.post(...).then(r => r.data),
  onSuccess: () => {
    void queryClient.invalidateQueries({ queryKey: ['plum', 'parts', partId, 'bom'] })
    toast('BOM line added.')
    setSheetOpen(false)
  },
  onError: () => { toast.error('Action failed. Please try again.') },
})
```

**Loading / error guard pattern** (lines 198–215) — apply to each new section's data fetch:
```tsx
// From: frontend/src/routes/plum/PartDetail.tsx lines 198-215
if (isLoading) {
  return <div className="p-8 flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
}
if (isError || !data) {
  return <div className="p-8"><p className="text-sm text-muted-foreground">Could not load ... try again.</p></div>
}
```

---

### `frontend/src/routes/plum/ImportExport.tsx` (component, file-I/O — new file)

**Analog:** `frontend/src/routes/plum/PartsList.tsx`

**Page layout + PlumNav + `h1` heading pattern** (inferred from PartsList.tsx lines 100+ and PartDetail.tsx lines 219–230):
```tsx
// Page wrapper pattern from PartDetail.tsx line 219:
return (
  <div className="p-8 space-y-6">
    <PlumNav />
    <h1 className="text-xl font-semibold text-foreground">Import / Export</h1>
    {/* Export card, Import card */}
  </div>
)
```

**`useMutation` for file download** (new pattern for this project):
```typescript
// No existing codebase analog — new pattern for Phase 6:
const exportMutation = useMutation({
  mutationFn: async (format: 'json' | 'excel') => {
    const ext = format === 'json' ? 'json' : 'xlsx'
    const response = await apiClient.get(`/api/v1/plum/export/${format}`, { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `plum_export.${ext}`
    a.click()
    window.URL.revokeObjectURL(url)
  },
  onSuccess: () => { toast('Export downloaded.') },
  onError: () => { toast.error('Export failed.') },
})
```

**D-18 three-step import state**:
```typescript
// Local state for the import flow (no existing analog):
const [importFile, setImportFile] = useState<File | null>(null)
const [preview, setPreview] = useState<ImportPreviewRead | null>(null)
const [step, setStep] = useState<'select' | 'preview' | 'done'>('select')
```

---

### `frontend/src/routes/plum/components/BomTree.tsx` (component, request-response — new file)

**Analog:** `frontend/src/routes/plum/components/PartSheet.tsx` (component structure) + `frontend/src/routes/plum/PartDetail.tsx` (Card + query pattern)

**Component JSDoc header** (pattern from PartDetail.tsx lines 1–24):
```typescript
/**
 * BomTree — recursive expandable BOM tree and flat BOM table for Part Detail.
 *
 * Props:
 *   partId: string
 *   revisionId: string — current revision; BOM is fetched for this revision
 *   isDraft: boolean — shows edit actions only when true (D-01 immutability)
 *
 * Views (PLUM-04 / PLUM-05):
 *   tree: recursive <ul> with expand/collapse (default; all expanded on load)
 *   flat: <Table> with total qty roll-up (GET /bom/flat endpoint)
 *
 * Query keys:
 *   ['plum', 'parts', partId, 'bom', 'tree'] — tree view
 *   ['plum', 'parts', partId, 'bom', 'flat'] — flat view
 */
```

**View-mode + expand state** (mirrors PartDetail's `useState` for open/close):
```typescript
// From: frontend/src/routes/plum/PartDetail.tsx lines 142-146 (pattern)
const [viewMode, setViewMode] = useState<'tree' | 'flat'>('tree')
const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())
// Initialize expandedIds to all item IDs after data loads (all expanded by default per UI-SPEC)
```

**Flat BOM toggle tabs** (UI-SPEC contract §Section 1 BOM Tree):
```tsx
// From: 06-UI-SPEC.md §Flat BOM toggle
<div className="flex gap-1 border-b border-border mb-4">
  <button
    className={viewMode === 'tree'
      ? 'pb-2 border-b-2 border-primary text-foreground text-sm font-medium'
      : 'pb-2 border-b-2 border-transparent text-muted-foreground text-sm'}
    onClick={() => setViewMode('tree')}
  >Tree</button>
  <button
    className={viewMode === 'flat'
      ? 'pb-2 border-b-2 border-primary text-foreground text-sm font-medium'
      : 'pb-2 border-b-2 border-transparent text-muted-foreground text-sm'}
    onClick={() => setViewMode('flat')}
  >Flat</button>
</div>
```

**Recursive BOM row** (new pattern; no existing analog in codebase):
```tsx
// BomRow renders one line; calls itself for children (expanded state)
function BomRow({ item, depth, isDraft }: { item: BomTreeItem; depth: number; isDraft: boolean }) {
  const hasChildren = item.children && item.children.length > 0
  const isExpanded = expandedIds.has(item.bom_item_id)
  return (
    <li style={{ paddingLeft: `${depth * 24}px` }}>  {/* pl-6 per level = 24px */}
      <div className="flex items-center gap-2">
        {hasChildren
          ? <button aria-expanded={isExpanded} aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${item.part_number}`} onClick={...}>
              {isExpanded ? <ChevronDown className="h-4 w-4" aria-hidden="true" /> : <ChevronRight className="h-4 w-4" aria-hidden="true" />}
            </button>
          : <span className="w-4" />}
        <span className="font-medium text-sm text-foreground">{item.part_number}</span>
        {item.is_provisional && (
          <span className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold bg-amber-50 text-amber-700">Unreleased</span>
        )}
        <span className="font-mono text-sm text-foreground">{item.qty} <span className="text-muted-foreground">{item.unit_of_measure}</span></span>
        {item.ref_des && <span className="text-xs text-muted-foreground" title={item.ref_des}>{item.ref_des.substring(0, 48)}{item.ref_des.length > 48 ? '…' : ''}</span>}
        {/* effective cost, actions (Draft only) */}
      </div>
      {isExpanded && hasChildren && (
        <ul>{item.children!.map(child => <BomRow key={child.bom_item_id} item={child} depth={depth + 1} isDraft={isDraft} />)}</ul>
      )}
    </li>
  )
}
```

**Empty state pattern** (from UI-SPEC §BOM Empty state):
```tsx
// UI-SPEC contract:
<p className="text-sm text-muted-foreground text-center py-6">No parts added yet.</p>
<p className="text-xs text-muted-foreground text-center">Add child parts to build a bill of materials for this revision.</p>
```

---

### `frontend/src/routes/plum/components/BomLineSheet.tsx` (component, request-response — new file)

**Analog:** `frontend/src/routes/plum/components/PartSheet.tsx` — copy structure exactly.

**Sheet component structure** (lines 109–389 of PartSheet.tsx — full skeleton):
```typescript
// From: frontend/src/routes/plum/components/PartSheet.tsx lines 265-389
export function BomLineSheet({ open, mode, partId, revisionId, line, onClose }: BomLineSheetProps) {
  const queryClient = useQueryClient()
  const [formChildPartId, setFormChildPartId] = useState('')
  const [formQty, setFormQty] = useState<number>(1)
  const [formRefDes, setFormRefDes] = useState('')

  const mutation = useMutation({
    mutationFn: (payload) =>
      mode === 'create'
        ? apiClient.post(`/api/v1/plum/parts/${partId}/bom`, { ...payload, revision_id: revisionId }).then(r => r.data)
        : apiClient.patch(`/api/v1/plum/parts/${partId}/bom/${line!.id}`, payload).then(r => r.data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['plum', 'parts', partId, 'bom'] })
      toast(mode === 'create' ? 'Part added to BOM.' : 'BOM line updated.')
      onClose()
    },
    onError: (err) => { toast.error(getApiErrorMessage(err, 'Failed to save BOM line.')) },
  })

  return (
    <Sheet open={open} onOpenChange={(isOpen) => { if (!isOpen) onClose() }}>
      <SheetContent side="right" aria-labelledby="bom-line-sheet-title" aria-describedby="bom-line-sheet-desc" className="overflow-y-auto">
        <SheetHeader>
          <SheetTitle id="bom-line-sheet-title">{mode === 'create' ? 'Add Part to BOM' : 'Edit BOM Line'}</SheetTitle>
          <SheetDescription id="bom-line-sheet-desc">...</SheetDescription>
        </SheetHeader>
        {/* form fields */}
        <SheetFooter>
          <Button variant="outline" onClick={onClose} disabled={mutation.isPending}>Cancel</Button>
          <Button variant="default" onClick={handleSave} disabled={mutation.isPending}>
            {mutation.isPending ? <><Loader2 className="animate-spin" aria-hidden="true" />Saving…</> : (mode === 'create' ? 'Add Part' : 'Save')}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
```

**`getApiErrorMessage` helper** (lines 88–105 of PartSheet.tsx) — copy verbatim:
```typescript
// From: frontend/src/routes/plum/components/PartSheet.tsx lines 88-105
function getApiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail)) {
      const msgs = detail.map((d) => {
        const loc = Array.isArray(d?.loc) ? d.loc[d.loc.length - 1] : undefined
        const field = typeof loc === 'string' ? loc : undefined
        const msg = typeof d?.msg === 'string' ? d.msg : 'invalid value'
        return field ? `${field}: ${msg}` : msg
      }).filter(Boolean)
      if (msgs.length) return msgs.join('; ')
    }
  }
  return fallback
}
```

---

### `frontend/src/routes/plum/components/AvlLinkSheet.tsx` (component, request-response — new file)

**Analog:** `frontend/src/routes/plum/components/PartSheet.tsx` — identical Sheet structure.

**Vendor search** uses `GET /api/v1/syerp/partners?is_vendor=true&q={query}` (D-11). Debounced 300ms, same pattern as child-part search in BomLineSheet.

**PriceBreakEditor sub-component** is embedded inside this Sheet for managing price-break rows inline (see PriceBreakEditor section below).

**Selected-for-costing checkbox** — marks the AVL link as the selected vendor for D-07 step 1. Only one can be selected per revision. Selection updates `selected_vendor_link_id` + `selected_price_break_index` on the revision via `PATCH /revisions/{rev_id}/cost`. Visual indicator: `CheckCircle` in `text-green-600` with `aria-label="Selected for costing"`.

---

### `frontend/src/routes/plum/components/PriceBreakEditor.tsx` (component, request-response — new file)

**Analog:** `frontend/src/routes/plum/PartDetail.tsx` lines 430–453 (inline `<dl>` display list adapted to editable table rows)

**Inline editable table row pattern** (from Table + TableBody + TableCell in PartsList.tsx and PartDetail.tsx):
```tsx
// From: frontend/src/routes/plum/PartsList.tsx (TableRow/TableCell structure)
// Adapted for price-break editing:
<Table>
  <TableHeader>
    <TableRow>
      <TableHead>Min Qty</TableHead>
      <TableHead>Unit Cost</TableHead>
      <TableHead>Lead Days</TableHead>
      <TableHead></TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    {priceBreaks.map((pb, idx) => (
      <TableRow key={idx} className="h-10">  {/* h-10 = UI-SPEC spacing exception for dense editor */}
        <TableCell>
          <Input type="number" min="1" value={pb.qty_threshold} onChange={...} className="font-mono text-sm h-8" />
        </TableCell>
        <TableCell>
          <Input type="number" step="0.000001" min="0" value={pb.unit_cost} onChange={...} className="font-mono text-sm h-8" />
        </TableCell>
        <TableCell>
          <Input type="number" min="0" value={pb.lead_days ?? ''} onChange={...} className="h-8" />
        </TableCell>
        <TableCell>
          <Button variant="ghost" size="sm" onClick={() => removePriceBreak(idx)} aria-label="Remove price break">
            <Trash2 className="h-4 w-4 text-destructive" aria-hidden="true" />
          </Button>
        </TableCell>
      </TableRow>
    ))}
  </TableBody>
</Table>
```

---

### `frontend/src/routes/plum/components/PlumNav.tsx` (component — extend existing)

**Analog:** same file — `frontend/src/routes/plum/components/PlumNav.tsx`

**`TABS` array pattern** (lines 14–17):
```typescript
// From: frontend/src/routes/plum/components/PlumNav.tsx lines 14-17
const TABS = [
  { to: '/plum/parts', label: 'Parts' },
  // Phase 6 addition:
  { to: '/plum/import-export', label: 'Import / Export' },
]
```

No other changes to this file.

---

### `frontend/src/routes/plum/components/BomTree.test.tsx` (test — new file)

**Analog:** `frontend/src/routes/plum/PartsList.test.tsx`

**Test file structure** (lines 1–88 of PartsList.test.tsx):
```typescript
// From: frontend/src/routes/plum/PartsList.test.tsx lines 1-48
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BomTree } from '@/routes/plum/components/BomTree'

vi.mock('@/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
  },
}))

import { apiClient } from '@/api/client'
const mockGet = vi.mocked(apiClient.get)

function renderBomTree(props = { partId: 'p1', revisionId: 'r1', isDraft: true }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <BomTree {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('BomTree component', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('renders empty state when BOM has no lines', async () => {
    mockGet.mockResolvedValueOnce({ data: { items: [] } })
    renderBomTree()
    await waitFor(() => {
      expect(screen.getByText('No parts added yet.')).toBeInTheDocument()
    })
  })

  it('renders BOM tree mode with part number', async () => { ... })
  it('switches to flat mode and renders flat BOM table', async () => { ... })
})
```

---

## Shared Patterns

### Authentication / Permission Gate
**Source:** `backend/app/modules/auth/dependencies.py` (via `require_permission`)
**Apply to:** All new router endpoints
```python
# From: backend/app/modules/plum/router.py lines 78, 131, 196
current_user=Depends(require_permission("plum:read"))    # GET endpoints
current_user=Depends(require_permission("plum:write"))   # POST / PATCH / DELETE endpoints
```

### Audit Logging
**Source:** `backend/app/modules/auth/service.py` lines 313–342 (`write_audit`)
**Apply to:** All state-mutating service functions
```python
# From: backend/app/modules/plum/service.py lines 695-702
await write_audit(
    db,
    actor_id=actor_id,
    action="bom.line_added",   # Phase-6 actions: bom.line_added, bom.line_updated,
                               # bom.line_removed, avl.link_added, avl.link_updated,
                               # avl.link_removed, cost.updated, plum.exported, plum.imported
    target_type="bom_item",
    target_id=str(item.id),
    detail=f"BOM line added to revision {parent_revision_id}",
)
```

### Error Response Format
**Source:** `backend/app/modules/plum/service.py` lines 748–762
**Apply to:** All service functions that validate preconditions
```python
# From: backend/app/modules/plum/service.py lines 748-762
raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="...")
raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="...")
raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="...")
```

### `getApiErrorMessage` (Frontend Toast Error)
**Source:** `frontend/src/routes/plum/components/PartSheet.tsx` lines 88–105
**Apply to:** BomLineSheet, AvlLinkSheet, ImportExport — copy verbatim.

### No ORM Relationships Rule
**Source:** `backend/app/modules/plum/models.py` lines 105–108
**Apply to:** All new models (`PlumBomItem`, `PlumAvlLink`, `PlumAvlPriceBreak`)
Never add `relationship()`. Always use explicit `select(...)` in service layer.

### `NUMERIC` for Monetary / Decimal Fields
**Source:** RESEARCH.md Pitfall 6 (first use in Phase 6 — no prior codebase analog)
**Apply to:** All `material_cost`, `sale_price`, `released_cost_snapshot`, `unit_cost`, `qty` columns
```python
from decimal import Decimal
from sqlalchemy import Numeric
qty: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
```

### `plum_` Table-Name Prefix
**Source:** `backend/app/modules/plum/models.py` lines 58, 83, 124, 157
**Apply to:** All new tables: `plum_bom_item`, `plum_avl_link`, `plum_avl_price_break`

### Query Key Naming Hierarchy (Frontend)
**Source:** `frontend/src/routes/plum/PartDetail.tsx` line 149 (`['plum', 'parts', partId]`)
**Apply to:** All new TanStack Query calls
```typescript
['plum', 'parts', partId, 'bom', 'tree']       // tree view
['plum', 'parts', partId, 'bom', 'flat']       // flat view
['plum', 'parts', partId, 'where-used']        // where-used list
['plum', 'parts', partId, 'avl']               // AVL links list
['plum', 'parts', partId, 'revisions', revId, 'cost']  // cost read
['plum', 'import-export']                      // not used for queries; invalidate after import
```

### Status Badge Color Map
**Source:** `frontend/src/routes/plum/PartDetail.tsx` lines 60–65
**Apply to:** BomTree (unreleased child badge uses `bg-amber-50 text-amber-700` per UI-SPEC — new Phase-6 color)
```typescript
// From: frontend/src/routes/plum/PartDetail.tsx lines 60-65
const STATUS_BADGE_CLASSES: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-600',
  in_review: 'bg-yellow-50 text-yellow-700',
  released: 'bg-green-50 text-green-600',
  obsolete: 'bg-gray-100 text-gray-400',
}
// Phase-6 additions (UI-SPEC):
// Unreleased child:   bg-amber-50 text-amber-700
// Preferred vendor:   bg-blue-50 text-blue-700
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/app/modules/plum/bom_cte.py` | utility | transform | No recursive CTE SQL exists anywhere in the project. Use RESEARCH.md Patterns 4–6 directly. |

All other Phase-6 files have close codebase analogs in Phase 4/5 code.

---

## Metadata

**Analog search scope:** `backend/app/modules/plum/`, `backend/app/modules/syerp/`, `backend/alembic/versions/`, `backend/app/core/`, `backend/tests/plum/`, `frontend/src/routes/plum/`
**Files scanned:** 18 source files read in full
**Pattern extraction date:** 2026-06-30
