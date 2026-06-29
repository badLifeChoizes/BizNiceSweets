# Phase 5: PLUM Parts & Revisions - Pattern Map

**Mapped:** 2026-06-28
**Files analyzed:** 15 new/modified files
**Analogs found:** 12 / 15 (3 net-new or partial)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/modules/plum/__init__.py` | module-init | request-response | `backend/app/modules/syerp/__init__.py` | exact |
| `backend/app/modules/plum/models.py` | model | CRUD | `backend/app/modules/syerp/models.py` | role-match (different entity shape) |
| `backend/app/modules/plum/schemas.py` | schema | request-response | `backend/app/modules/syerp/schemas.py` | role-match |
| `backend/app/modules/plum/service.py` | service | CRUD | `backend/app/modules/syerp/service.py` | role-match (FSM logic is net-new) |
| `backend/app/modules/plum/router.py` | route | request-response | `backend/app/modules/syerp/router.py` | exact |
| `backend/app/modules/plum/seed.py` | config/seed | CRUD | `backend/app/modules/syerp/coa_seed.py` | role-match |
| `backend/app/core/models.py` | config | — | self (uncomment stub) | modification |
| `backend/app/core/seed.py` | config/seed | — | self (extend run_seeds) | modification |
| `backend/alembic/versions/0005_plum_tables.py` | migration | CRUD | `backend/alembic/versions/0004_syerp_tables.py` | role-match |
| `backend/tests/plum/test_parts.py` | test | request-response | `backend/tests/syerp/test_partners.py` | exact |
| `backend/tests/plum/test_revisions.py` | test | CRUD | `backend/tests/syerp/test_partners.py` | role-match |
| `frontend/src/routes/plum/PartsList.tsx` | component | request-response | `frontend/src/routes/syerp/Vendors.tsx` | exact |
| `frontend/src/routes/plum/components/PlumNav.tsx` | component | — | `frontend/src/routes/syerp/components/SyerpNav.tsx` | exact |
| `frontend/src/routes/plum/components/PartSheet.tsx` | component | CRUD | `frontend/src/routes/syerp/components/PartnerSheet.tsx` | role-match |
| `frontend/src/routes/plum/components/ArchivePartDialog.tsx` | component | CRUD | `frontend/src/routes/syerp/components/PartnerArchiveDialog.tsx` | exact |
| `frontend/src/routes/plum/PartDetail.tsx` | component | request-response | none — net-new | no analog |
| `frontend/src/routes/plum/components/NewRevisionDialog.tsx` | component | CRUD | `frontend/src/routes/syerp/components/PartnerSheet.tsx` | partial (dialog shell only) |
| `frontend/src/routes/plum/components/AdvanceStatusDialog.tsx` | component | event-driven | `frontend/src/routes/syerp/components/PartnerArchiveDialog.tsx` | partial (dialog shell only) |
| `frontend/src/App.tsx` | route | — | self (extend SYERP block) | modification |

---

## Pattern Assignments

### `backend/app/modules/plum/__init__.py` (module-init)

**Analog:** `backend/app/modules/syerp/__init__.py` (lines 1–22)

**Full file pattern** (copy verbatim, replace "syerp" with "plum"):
```python
"""
PLUM — Product Lifecycle Management module.

This __init__.py:
  1. Defines MODULE_NAME and imports router (satisfies Module Protocol).
  2. Calls registry.register(sys.modules[__name__]) so PLUM self-registers
     when app/main.py does `import app.modules.plum`.
"""
import sys

from app.core import registry
from app.modules.plum.router import router  # noqa: F401

MODULE_NAME = "plum"

registry.register(sys.modules[__name__])
```

---

### `backend/app/modules/plum/models.py` (model, CRUD)

**Analog:** `backend/app/modules/syerp/models.py`

**Imports pattern** (lines 23–31):
```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base
```

**Model class shape** (lines 39–97 adapted — `Partner` class structure):
```python
class PlumPart(Base):
    __tablename__ = "plum_part"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    part_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    # No ORM relationships — see comment in syerp/models.py lines 99–102
```

**Critical comment to copy** (syerp/models.py lines 99–102):
```python
    # No ORM relationships declared — the GL endpoint returns a flat
    # list; partner list queries only need scalar columns. Adding relationships
    # later requires lazy="selectin" to avoid MissingGreenlet in async context
    # (RESEARCH.md Pitfall 2).
```
Adapt: "No ORM relationships declared on PlumPart or PlumPartRevision. Use explicit `select` queries in service functions to load revisions. Adding `relationship()` requires `lazy='selectin'` to avoid MissingGreenlet in async context."

**`plum_` table-name prefix** (syerp/models.py line 52): every table name must use `plum_` prefix (e.g. `plum_part`, `plum_part_revision`, `plum_classification_tag`, `plum_part_tag`).

**Integer PK pattern** for lookup tables (syerp/models.py lines 126–127 — GLAccount):
```python
id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
```
Use this for `PlumClassificationTag` (seeded lookup table, integer PK is sufficient).

---

### `backend/app/modules/plum/schemas.py` (schema, request-response)

**Analog:** `backend/app/modules/syerp/schemas.py`

**Imports pattern** (lines 1–21):
```python
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator
```

**Input schema pattern** — Optional code with server auto-gen (lines 30–43):
```python
class PartCreate(BaseModel):
    # Required fields only: part_number + description (D-12 divergence)
    part_number: Optional[str] = Field(None, max_length=50)  # server auto-gens if None
    description: str = Field(..., max_length=500)
    # Optional revision-controlled fields (first revision seed):
    category: Optional[str] = Field(None, max_length=100)
    unit_of_measure: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    reason_for_revision: Optional[str] = None  # free-text ECO substitute
    tag_ids: list[int] = Field(default_factory=list)  # classification tag IDs
```

**PATCH semantics pattern** — all Optional, model_dump(exclude_unset=True) (lines 75–126):
```python
class PartUpdate(BaseModel):
    part_number: Optional[str] = Field(None, max_length=50)
    active: Optional[bool] = None
    tag_ids: Optional[list[int]] = None
    # Revision-controlled fields (only editable on Draft revisions)
    description: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, max_length=100)
    unit_of_measure: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
```

**Read schema pattern** — from_attributes=True (lines 128–167):
```python
class PartRead(BaseModel):
    id: str
    part_number: str
    active: bool
    created_at: datetime
    updated_at: datetime
    tags: list[str] = []       # list of tag names
    # Current revision summary fields (for list display)
    current_revision_label: Optional[str] = None
    current_revision_status: Optional[str] = None

    model_config = {"from_attributes": True}
```

**model_validator pattern** (syerp/schemas.py lines 64–72) — adapt for revision immutability checks if needed at schema level. In Phase 5, the 422 for editing a Released revision is enforced in the service layer, not the schema.

---

### `backend/app/modules/plum/service.py` (service, CRUD + event-driven FSM)

**Analog:** `backend/app/modules/syerp/service.py`

**Imports pattern** (lines 1–35):
```python
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.modules.plum.models import PlumPart, PlumPartRevision
    from app.modules.plum.schemas import PartCreate, PartUpdate, RevisionCreate
```

**Auto-generate code pattern** — `generate_partner_code` (syerp/service.py lines 43–73):
```python
async def generate_part_number(db: AsyncSession) -> str:
    """
    Generate the next part number in the P##### series.
    Uses DB MAX query on existing part_numbers. Returns "P00001" when none exist.
    The DB unique constraint on plum_part.part_number is the authoritative guard.
    """
    from sqlalchemy import func
    from app.modules.plum.models import PlumPart

    result = await db.execute(
        select(func.max(PlumPart.part_number)).where(PlumPart.part_number.like("P%"))
    )
    max_pn: str | None = result.scalar()
    if max_pn is None:
        return "P00001"
    try:
        suffix = int(max_pn[1:])
    except ValueError:
        suffix = 0
    return f"P{suffix + 1:05d}"
```

**Create with IntegrityError retry** (syerp/service.py lines 105–147):
```python
async def create_part(db: AsyncSession, data: "PartCreate") -> "PlumPart":
    import sqlalchemy.exc
    from app.modules.plum.models import PlumPart

    user_supplied_pn = bool(data.part_number)
    part_number = data.part_number or await generate_part_number(db)

    part = PlumPart(part_number=part_number, active=True)
    db.add(part)

    try:
        await db.flush()
    except sqlalchemy.exc.IntegrityError:
        await db.rollback()
        if user_supplied_pn:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Part number '{part_number}' already exists.",
            )
        part_number = await generate_part_number(db)
        part = PlumPart(part_number=part_number, active=True)
        db.add(part)
        await db.flush()

    # Auto-create first revision in Draft (D-03)
    # ... (then INSERT PlumPartRevision)
    await db.commit()
    await db.refresh(part)
    return part
```

**List with active filter + ilike search** (syerp/service.py lines 150–193):
```python
async def list_parts(
    db: AsyncSession,
    q: str | None = None,
    status_filter: str | None = None,
    include_archived: bool = False,
) -> list:
    """
    Return parts matching filters.
    status_filter: filters on the part's current revision status (correlated subquery).
    include_archived: when False (default), excludes active=False rows.
    """
    from app.modules.plum.models import PlumPart

    stmt = select(PlumPart)

    if not include_archived:
        stmt = stmt.where(PlumPart.active == True)  # noqa: E712

    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                PlumPart.part_number.ilike(like),
                # description is on PlumPartRevision — join required for description search
            )
        )
    # status_filter requires correlated subquery (see Pattern 4 in RESEARCH.md)
    stmt = stmt.order_by(PlumPart.part_number)
    result = await db.execute(stmt)
    return list(result.scalars().all())
```

**Get by ID with 404** (syerp/service.py lines 196–213):
```python
async def get_part(db: AsyncSession, part_id: str) -> "PlumPart":
    from app.modules.plum.models import PlumPart

    result = await db.execute(select(PlumPart).where(PlumPart.id == part_id))
    part = result.scalars().first()
    if part is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part {part_id} not found",
        )
    return part
```

**PATCH with model_dump(exclude_unset=True)** (syerp/service.py lines 216–241):
```python
async def update_part(db: AsyncSession, part_id: str, data: "PartUpdate") -> "PlumPart":
    part = await get_part(db, part_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(part, field, value)
    await db.commit()
    await db.refresh(part)
    return part
```

**FSM transition logic** (net-new — no analog, based on domain decisions D-07/D-08):
```python
VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft":     ["in_review"],
    "in_review": ["released", "draft"],
    "released":  ["obsolete"],   # internal only — triggered by supersede
    "obsolete":  [],             # terminal
}

async def advance_revision_status(
    db: AsyncSession, part_id: str, revision_id: str,
    target_status: str, actor_id: str
) -> "PlumPartRevision":
    # 1. Load revision, verify part_id matches (404 if not)
    # 2. Validate transition via VALID_TRANSITIONS dict (422 if invalid)
    # 3. If target == "released": find prior Released rev, set it to obsolete,
    #    write audit("revision.obsoleted"), flush within same transaction
    # 4. Set revision.status = target_status, set released_at if releasing
    # 5. await db.commit()
    # 6. write_audit(target-specific action)
    # NOTE: wrap steps 3-5 in a single transaction; call db.flush() between
    # the two updates (obsolete + release) before commit to prevent race
```

---

### `backend/app/modules/plum/router.py` (route, request-response)

**Analog:** `backend/app/modules/syerp/router.py`

**Imports pattern** (lines 31–48):
```python
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.auth.service import write_audit
from app.modules.plum.schemas import (PartCreate, PartRead, PartUpdate,
                                        RevisionCreate, RevisionRead, PartDetailRead)
from app.modules.plum.service import (
    create_part, list_parts, get_part, update_part,
    create_revision, advance_revision_status,
)

router = APIRouter(prefix="/plum", tags=["plum"])
# Note: mount_all() in registry.py adds /api/v1 — do NOT include it here.
# Full paths: /api/v1/plum/parts, /api/v1/plum/parts/{id}/revisions, etc.
```

**Read endpoint with permission gate** (syerp/router.py lines 58–77):
```python
@router.get("/parts", response_model=list[PartRead])
async def list_parts_endpoint(
    q: str | None = None,
    status: str | None = None,
    include_archived: bool = False,
    current_user=Depends(require_permission("plum:read")),
    db: AsyncSession = Depends(get_db),
) -> list[PartRead]:
    return await list_parts(db, q=q, status_filter=status, include_archived=include_archived)
```

**Write endpoint with audit** (syerp/router.py lines 80–102):
```python
@router.post("/parts", response_model=PartRead, status_code=status.HTTP_201_CREATED)
async def create_part_endpoint(
    data: PartCreate,
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> PartRead:
    part = await create_part(db, data)
    await write_audit(
        db,
        actor_id=str(current_user.id),
        action="part.created",
        target_type="part",
        target_id=str(part.id),
        detail=f"Part created: {part.part_number}",
    )
    return part
```

**Archive-aware PATCH** (syerp/router.py lines 118–153 — the was_active pattern):
```python
@router.patch("/parts/{part_id}", response_model=PartRead)
async def update_part_endpoint(
    part_id: str,
    data: PartUpdate,
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> PartRead:
    existing = await get_part(db, part_id)
    was_active = existing.active

    part = await update_part(db, part_id, data)

    is_archiving = data.active is False and was_active is True
    audit_action = "part.archived" if is_archiving else "part.updated"

    await write_audit(
        db,
        actor_id=str(current_user.id),
        action=audit_action,
        target_type="part",
        target_id=str(part.id),
        detail=f"Part {audit_action.split('.')[1]}: {part.part_number}",
    )
    return part
```

---

### `backend/app/modules/plum/seed.py` (config/seed, CRUD)

**Analog:** `backend/app/modules/syerp/coa_seed.py`

**Idempotent select-before-insert pattern** (auth/seed.py lines 45–60 adapted):
```python
"""
PLUM module seed.

Seeds:
  1. Classification tag starter vocabulary (D-12):
     Purchased, Manufactured, Assembly, Finished Good, Tool, Raw Material
  2. Default settings (D-04, D-12):
     plum.revision_scheme = "asme"
     plum.tag_vocabulary_editable = "true"

All operations are idempotent — safe on every podman-compose up.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_CLASSIFICATION_TAGS = [
    ("Purchased", 1),
    ("Manufactured", 2),
    ("Assembly", 3),
    ("Finished Good", 4),
    ("Tool", 5),
    ("Raw Material", 6),
]

async def seed_plum_data(db: "AsyncSession") -> None:
    from sqlalchemy import select
    from app.modules.plum.models import PlumClassificationTag
    from app.core.settings_model import Setting

    # Idempotent tag insert
    for name, sort_order in _CLASSIFICATION_TAGS:
        result = await db.execute(
            select(PlumClassificationTag).where(PlumClassificationTag.name == name)
        )
        if result.scalars().first() is None:
            db.add(PlumClassificationTag(name=name, sort_order=sort_order, active=True))

    # Idempotent settings insert
    for key, value in [("plum.revision_scheme", "asme"),
                       ("plum.tag_vocabulary_editable", "true")]:
        result = await db.execute(select(Setting).where(Setting.key == key))
        if result.scalars().first() is None:
            db.add(Setting(key=key, value=value))

    await db.commit()
```

---

### `backend/app/core/models.py` (modification)

**File to modify:** `/home/zack/Projects/BizNiceSweets/backend/app/core/models.py`

**Change:** Uncomment line 27 (already present as a stub):
```python
# Before (line 27):
# from app.modules.plum import models as plum_models    # noqa: F401

# After:
from app.modules.plum import models as plum_models  # noqa: F401
```

This must happen BEFORE running `alembic revision --autogenerate`.

---

### `backend/app/core/seed.py` (modification)

**File to modify:** `/home/zack/Projects/BizNiceSweets/backend/app/core/seed.py`

**Extend `run_seeds()`** (add after line 43, following the established import + call pattern at lines 38–43):
```python
    from app.modules.plum.seed import seed_plum_data
    await seed_plum_data(db)
```

---

### `backend/alembic/versions/0005_plum_tables.py` (migration)

**Analog:** `backend/alembic/versions/0004_syerp_tables.py`

**Header pattern** (lines 1–41):
```python
"""add plum_part, plum_part_revision, plum_classification_tag, plum_part_tag tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-XX-XX 00:00:00.000000+00:00

Phase 5 — PLUM Parts & Revisions.

Tables:
  plum_classification_tag — seeded tag vocabulary (D-12)
  plum_part               — stable part header (D-01/D-02)
  plum_part_tag           — join table: part ↔ classification tag (D-12)
  plum_part_revision      — versioned revision snapshot (D-01/D-02/D-07)
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
aliases: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Create in dependency order: tags → parts → part_tag → revisions
    op.create_table('plum_classification_tag', ...)
    op.create_table('plum_part', ...)
    op.create_table('plum_part_tag', ...)
    op.create_table('plum_part_revision', ...)
    # Add partial unique index for "one Released per part" invariant (Pitfall 3)
    op.create_index(
        'uq_plum_part_one_released',
        'plum_part_revision',
        ['part_id'],
        unique=True,
        postgresql_where=sa.text("status = 'released'"),
    )

def downgrade() -> None:
    op.drop_index('uq_plum_part_one_released', table_name='plum_part_revision')
    op.drop_table('plum_part_revision')
    op.drop_table('plum_part_tag')
    op.drop_table('plum_part')
    op.drop_table('plum_classification_tag')
```

---

### `backend/tests/plum/test_parts.py` (test, request-response)

**Analog:** `backend/tests/syerp/test_partners.py`

**Test file header + fixture pattern** (lines 1–34):
```python
"""
PLUM part tests — Phase 5.

Behaviors tested (PLUM-01, PLUM-02):
  - Part create → 201, first revision auto-created in Draft (PLUM-01)
  - Part create with duplicate part_number → 409 (PLUM-01)
  - Part update → 200, audit log written (PLUM-01)
  - Part archive sets active=false (PLUM-01)
  - Archived part absent from default list (PLUM-01)
  - plum:write required for create → 403 without it (PLUM-01)
  - Search ?q= filters by part_number (PLUM-02)
  - Search ?q= filters by description (PLUM-02)
  - Status filter returns only matching parts (PLUM-02)

Tests require a live PostgreSQL database (skip_if_no_db).
"""
import pytest
import httpx

# Token creation pattern (identical to syerp tests lines 41–43):
async def test_create_part(client: httpx.AsyncClient, skip_if_no_db: None) -> None:
    from app.modules.auth.service import create_access_token
    token = create_access_token(subject="admin-user", permissions=["plum:write"])

    response = await client.post(
        "/api/v1/plum/parts",
        json={"description": "Widget housing"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert "part_number" in body
    assert body["active"] is True
```

**Audit log verification pattern** (test_partners.py lines 85–125 — exact copy, change table/action names):
```python
    # Verify AuditLog row was written (same pattern as test_update_partner_writes_audit)
    from sqlalchemy import select
    from app.core.db import AsyncSessionLocal
    from app.modules.auth.models import AuditLog

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "part.updated",
                AuditLog.target_id == part_id,
            )
        )
        row = result.scalars().first()
    assert row is not None, "Expected AuditLog row for part.updated"
```

---

### `backend/tests/plum/test_revisions.py` (test, CRUD + event-driven)

**Analog:** `backend/tests/syerp/test_partners.py` (structure only — revision FSM tests are net-new behavior)

**Test structure pattern** — same fixture signature, same token pattern:
```python
async def test_create_revision(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    from app.modules.auth.service import create_access_token
    token = create_access_token(subject="admin-user", permissions=["plum:write", "plum:read"])
    # 1. Create a part (POST /plum/parts → 201)
    # 2. Create a revision (POST /plum/parts/{id}/revisions → 201)
    # 3. Assert status="draft", attributes copied from first revision
```

**Status transition test pattern** (net-new — no analog exists; derived from D-07/D-08):
```python
async def test_release_supersedes_prior(
    client: httpx.AsyncClient,
    skip_if_no_db: None,
) -> None:
    # 1. Create part (auto Draft Rev A)
    # 2. Advance Rev A: draft → in_review → released
    # 3. Create Rev B (auto Draft)
    # 4. Advance Rev B: draft → in_review → released
    # 5. Assert Rev A is now status="obsolete"
    # 6. Assert Rev B is status="released"
    # 7. Assert at most one "released" row per part (DB invariant)
```

---

### `frontend/src/routes/plum/PartsList.tsx` (component, request-response)

**Analog:** `frontend/src/routes/syerp/Vendors.tsx`

**Imports pattern** (lines 24–51 — copy verbatim, replace syerp refs with plum):
```typescript
import { useState, useCallback, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { MoreHorizontal, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Badge } from '@/components/ui/badge'
import { apiClient } from '@/api/client'
import { useNavigate } from 'react-router-dom'
import { PlumNav } from './components/PlumNav'
import { PartSheet } from './components/PartSheet'
import { ArchivePartDialog } from './components/ArchivePartDialog'
```

**API fetch function pattern** (Vendors.tsx lines 54–61):
```typescript
function fetchParts(q: string, status: string, includeArchived: boolean): Promise<PartRead[]> {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  if (status) params.set('status', status)
  if (includeArchived) params.set('include_archived', 'true')
  return apiClient
    .get<PartRead[]>(`/api/v1/plum/parts?${params.toString()}`)
    .then((r) => r.data)
}
```

**Debounced search state pattern** (Vendors.tsx lines 87–96 — copy exactly):
```typescript
const [searchValue, setSearchValue] = useState('')
const [searchFilter, setSearchFilter] = useState('')
const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
  const v = e.target.value
  setSearchValue(v)
  if (debounceTimer.current) clearTimeout(debounceTimer.current)
  debounceTimer.current = setTimeout(() => setSearchFilter(v), 300)
}, [])
```

**TanStack Query pattern** (Vendors.tsx lines 111–114):
```typescript
const { data: parts = [], isLoading, isError } = useQuery<PartRead[], Error>({
  queryKey: ['plum', 'parts', { q: searchFilter, status: statusFilter, includeArchived }],
  queryFn: () => fetchParts(searchFilter, statusFilter, includeArchived),
})
```

**Restore mutation pattern** (Vendors.tsx lines 117–129):
```typescript
const restoreMutation = useMutation<PartRead, Error, string>({
  mutationFn: (partId) =>
    apiClient
      .patch<PartRead>(`/api/v1/plum/parts/${partId}`, { active: true })
      .then((r) => r.data),
  onSuccess: () => {
    void queryClient.invalidateQueries({ queryKey: ['plum', 'parts'] })
    toast('Part restored.')
  },
  onError: () => {
    toast.error('Failed to restore part. Please try again.')
  },
})
```

**Page wrapper + nav pattern** (Vendors.tsx lines 154–163):
```typescript
return (
  <div className="p-8 space-y-6">
    <PlumNav />
    <div className="space-y-1">
      <h1 className="text-xl font-semibold text-foreground">Parts</h1>
      <p className="text-base font-normal text-muted-foreground">
        Manage parts and their revision history.
      </p>
    </div>
    {/* toolbar, table/empty states below — same structure as Vendors.tsx */}
  </div>
)
```

**Toolbar pattern** (Vendors.tsx lines 165–186) — add status Select and navigate-on-row-click vs Vendors' edit-sheet-on-row-click:
```typescript
{/* Row click → navigate to Part Detail (not edit sheet) */}
<TableRow
  key={part.id}
  className="h-12 cursor-pointer"
  onClick={() => navigate(`/plum/parts/${part.id}`)}
>
```

**Empty state pattern** (Vendors.tsx lines 199–215 — copy structure, adapt copy per UI-SPEC):
```typescript
{searchFilter || statusFilter ? (
  <>
    <p className="text-base font-semibold text-foreground">No parts found</p>
    <p className="text-sm text-muted-foreground">
      No parts match your search. Clear the filter or create a new part.
    </p>
  </>
) : (
  <>
    <p className="text-base font-semibold text-foreground">No parts yet</p>
    <p className="text-sm text-muted-foreground">
      Create your first part to get started.
    </p>
  </>
)}
```

**DropdownMenu action pattern** (Vendors.tsx lines 240–269 — copy exactly, adapt labels):
```typescript
<DropdownMenu>
  <DropdownMenuTrigger asChild>
    <Button
      variant="ghost"
      size="icon"
      className="h-11 w-11"
      aria-label={`Part actions for ${part.part_number}`}
      onClick={(e) => e.stopPropagation()}  // prevent row navigation
    >
      <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
      <span className="sr-only">Open actions menu</span>
    </Button>
  </DropdownMenuTrigger>
  <DropdownMenuContent align="end">
    <DropdownMenuItem onClick={(e) => { e.stopPropagation(); openEditSheet(part) }}>
      Edit
    </DropdownMenuItem>
    {part.active ? (
      <DropdownMenuItem
        onClick={(e) => { e.stopPropagation(); openArchiveDialog(part) }}
        className="text-destructive focus:text-destructive"
      >
        Archive
      </DropdownMenuItem>
    ) : (
      <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleRestore(part) }}>
        Restore
      </DropdownMenuItem>
    )}
  </DropdownMenuContent>
</DropdownMenu>
```

---

### `frontend/src/routes/plum/components/PlumNav.tsx` (component)

**Analog:** `frontend/src/routes/syerp/components/SyerpNav.tsx` (lines 1–42 — copy verbatim, adapt names)

**Full file pattern** (copy lines 1–42, replace syerp with plum):
```typescript
import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'

const TABS = [
  { to: '/plum/parts', label: 'Parts' },
  // Phase 6 will add: { to: '/plum/boms', label: 'BOMs' }
]

export function PlumNav() {
  return (
    <nav className="flex gap-1 border-b border-border" aria-label="PLUM sections">
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          className={({ isActive }) =>
            cn(
              '-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  )
}
```

---

### `frontend/src/routes/plum/components/PartSheet.tsx` (component, CRUD)

**Analog:** `frontend/src/routes/syerp/components/PartnerSheet.tsx`

**Imports + type interface pattern** (lines 27–89 — copy structure, adapt fields):
```typescript
import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Separator } from '@/components/ui/separator'
import { apiClient } from '@/api/client'
import { cn } from '@/lib/utils'

export interface PartRead {
  id: string
  part_number: string
  active: boolean
  tags: string[]
  current_revision_label?: string | null
  current_revision_status?: string | null
  created_at: string
  updated_at: string
}
```

**API error helper** (PartnerSheet.tsx lines 114–131 — copy verbatim, no changes needed):
```typescript
function getApiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail)) {
      const msgs = detail
        .map((d) => {
          const loc = Array.isArray(d?.loc) ? d.loc[d.loc.length - 1] : undefined
          const field = typeof loc === 'string' ? loc : undefined
          const msg = typeof d?.msg === 'string' ? d.msg : 'invalid value'
          return field ? `${field}: ${msg}` : msg
        })
        .filter(Boolean)
      if (msgs.length) return msgs.join('; ')
    }
  }
  return fallback
}
```

**useEffect form population pattern** (PartnerSheet.tsx lines 175–218 — copy structure):
```typescript
useEffect(() => {
  if (!open) return
  if (mode === 'create') {
    // fetch auto-generated part number: GET /api/v1/plum/parts/next-number
    // set form fields to empty / defaults
  } else if (mode === 'edit' && part) {
    setFormPartNumber(part.part_number)
    setFormDescription(/* from current revision */)
    setFormTagIds(/* from part.tag_ids */)
  }
}, [open, mode, part])
```

**Settings-read pattern for revision scheme** (PartnerSheet.tsx lines 139–148 — adapt to read `plum.revision_scheme` setting):
```typescript
const { data: settings = [] } = useQuery<SettingRecord[], Error>({
  queryKey: ['core', 'settings'],
  queryFn: () =>
    apiClient.get<SettingRecord[]>('/api/v1/core/settings').then((r) => r.data),
  staleTime: 5 * 60 * 1000,
})
```

**Sheet structure + Separator sections** (PartnerSheet.tsx lines 340–598):
```typescript
<Sheet open={open} onOpenChange={handleOpenChange}>
  <SheetContent
    side="right"
    aria-labelledby="part-sheet-title"
    aria-describedby="part-sheet-description"
    className="overflow-y-auto"
  >
    <SheetHeader>
      <SheetTitle id="part-sheet-title">{mode === 'create' ? 'Create Part' : 'Edit Part'}</SheetTitle>
      <SheetDescription id="part-sheet-description">...</SheetDescription>
    </SheetHeader>

    <div className="py-6 space-y-6">
      {/* Section 1: Identity */}
      <div className="space-y-4">
        <Label htmlFor="part-number">Part Number</Label>
        <Input id="part-number" ... />
        <p className="text-xs text-muted-foreground">
          System-generated. You may change it before saving.
        </p>
        {/* Description — required */}
        <Label htmlFor="part-description">Description</Label>
        <Input id="part-description" ... />
      </div>

      <Separator />

      {/* Section 2: Classification — checkbox group for tags */}
      <div className="space-y-4">...</div>

      {/* Create mode only: Section 3: Revision seed note */}
      {mode === 'create' && (
        <>
          <Separator />
          <div className="space-y-4">...</div>
        </>
      )}
    </div>

    <SheetFooter className={cn('flex gap-2 pt-4')}>
      <Button variant="outline" onClick={onClose} disabled={isSaving}>Cancel</Button>
      <Button variant="default" onClick={handleSave} disabled={isSaving}>
        {isSaving ? <><Loader2 className="animate-spin" aria-hidden="true" />Saving…</> : 'Save Part'}
      </Button>
    </SheetFooter>
  </SheetContent>
</Sheet>
```

**Mutation + invalidation pattern** (PartnerSheet.tsx lines 268–308 — copy, adapt queryKey):
```typescript
const createMutation = useMutation<PartRead, Error, PartPayload>({
  mutationFn: (payload) =>
    apiClient.post<PartRead>('/api/v1/plum/parts', payload).then((r) => r.data),
  onSuccess: () => {
    void queryClient.invalidateQueries({ queryKey: ['plum', 'parts'] })
    toast('Part created.')
    onClose()
  },
  onError: (err) => {
    toast.error(getApiErrorMessage(err, 'Failed to save part. Please try again.'))
  },
})
```

---

### `frontend/src/routes/plum/components/ArchivePartDialog.tsx` (component, CRUD)

**Analog:** `frontend/src/routes/syerp/components/PartnerArchiveDialog.tsx` (lines 1–127 — near-verbatim copy)

**Full pattern** (copy PartnerArchiveDialog.tsx, replace partner → part, syerp → plum, role logic removed):
```typescript
// Props interface:
interface ArchivePartDialogProps {
  open: boolean
  part: PartRead | null
  onClose: () => void
}

// Mutation (PartnerArchiveDialog.tsx lines 50–67 pattern):
const archiveMutation = useMutation<PartRead, Error, string>({
  mutationFn: (partId) =>
    apiClient
      .patch<PartRead>(`/api/v1/plum/parts/${partId}`, { active: false })
      .then((r) => r.data),
  onSuccess: () => {
    void queryClient.invalidateQueries({ queryKey: ['plum', 'parts'] })
    toast('Part archived.')
    onClose()
  },
  onError: () => {
    toast.error('Failed to archive part. Please try again.')
  },
})

// Dialog JSX (PartnerArchiveDialog.tsx lines 87–127 pattern):
<Dialog open={open} onOpenChange={handleOpenChange}>
  <DialogContent aria-labelledby="archive-part-dialog-title" aria-describedby="archive-part-dialog-desc">
    <DialogHeader>
      <DialogTitle id="archive-part-dialog-title">Archive part?</DialogTitle>
      <DialogDescription id="archive-part-dialog-desc">
        {part ? `${part.part_number} — {description} will be hidden from the parts list. History and references are preserved and can be restored at any time.` : ''}
      </DialogDescription>
    </DialogHeader>
    <DialogFooter>
      <Button variant="outline" onClick={onClose} disabled={isArchiving}>Keep Part</Button>
      <Button
        variant="destructive"
        onClick={handleConfirm}
        disabled={isArchiving}
        aria-label={part ? `Archive ${part.part_number}` : 'Archive part'}
      >
        {isArchiving ? <><Loader2 className="animate-spin" aria-hidden="true" />Archiving…</> : 'Archive Part'}
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

---

### `frontend/src/App.tsx` (modification)

**File to modify:** `/home/zack/Projects/BizNiceSweets/frontend/src/App.tsx`

**Add imports** (after line 16, following the SYERP block pattern at lines 13–16):
```typescript
// PLUM routes (Phase 5)
import { PartsList } from '@/routes/plum/PartsList'
import { PartDetail } from '@/routes/plum/PartDetail'
```

**Add routes** (inside `<Route element={<AppShell />}>`, after the SYERP block at lines 31–35):
```typescript
{/* PLUM module routes — Sidebar nav lands on /plum → redirect to parts list */}
<Route path="/plum" element={<Navigate to="/plum/parts" replace />} />
<Route path="/plum/parts" element={<PartsList />} />
<Route path="/plum/parts/:id" element={<PartDetail />} />
```

---

### `frontend/src/routes/plum/PartDetail.tsx` (component — NET NEW, no direct analog)

**Closest partial analog:** `frontend/src/routes/syerp/Vendors.tsx` (TanStack Query and page wrapper patterns only)

**TanStack Query for detail page** (Vendors.tsx lines 111–114 adapted):
```typescript
const { data: part, isLoading, isError } = useQuery<PartDetailRead, Error>({
  queryKey: ['plum', 'parts', partId],
  queryFn: () =>
    apiClient.get<PartDetailRead>(`/api/v1/plum/parts/${partId}`).then((r) => r.data),
})
```

**Back navigation button** (uses `useNavigate` + `ChevronLeft` icon from lucide-react — already in use in project):
```typescript
import { ChevronLeft } from 'lucide-react'
const navigate = useNavigate()

<Button variant="ghost" size="sm" onClick={() => navigate('/plum/parts')}>
  <ChevronLeft className="h-4 w-4" aria-hidden="true" />
  Back to Parts
</Button>
```

**Card component for part header** — shadcn `<Card>` / `<CardHeader>` / `<CardContent>` already installed; no existing page-level card analog in SYERP screens (they are table-only layouts). Import from `@/components/ui/card`.

**Revision timeline** — `<ol aria-label="Revision history">` with inline CSS connector line. No existing analog. Implement as described in UI-SPEC lines 162–176. Key elements:
- `<ol className="space-y-0" aria-label="Revision history">` containing `<li>` per revision
- 2px vertical connector: `<div className="absolute left-3 top-4 bottom-0 w-0.5 bg-border" />`
- 8px connector dot: `<div className="h-2 w-2 rounded-full ..." />` (color from status)
- Revision attributes as `<dl>` definition list at `text-sm`

**Status badge color mapping** (new, no analog — matches UI-SPEC lines 89–95):
```typescript
const STATUS_BADGE_CLASSES: Record<string, string> = {
  draft:     'bg-gray-100 text-gray-600',
  in_review: 'bg-yellow-50 text-yellow-700',
  released:  'bg-green-50 text-green-600',
  obsolete:  'bg-gray-100 text-gray-400',
}

function RevisionStatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_BADGE_CLASSES[status] ?? 'bg-gray-100 text-gray-500'}`}>
      {status.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())}
    </span>
  )
}
```

**Advance status strip** — inline flex row per UI-SPEC lines 153–159. New pattern with no analog. Conditionally rendered only when current revision is `draft` or `in_review`.

**Mutation pattern for advance status** (follows Vendors.tsx mutation shape):
```typescript
const advanceMutation = useMutation<RevisionRead, Error, { targetStatus: string }>({
  mutationFn: ({ targetStatus }) =>
    apiClient
      .post<RevisionRead>(
        `/api/v1/plum/parts/${partId}/revisions/${currentRevision.id}/advance`,
        { target_status: targetStatus },
      )
      .then((r) => r.data),
  onSuccess: () => {
    void queryClient.invalidateQueries({ queryKey: ['plum', 'parts', partId] })
    toast('Status updated.')
  },
  onError: () => {
    toast.error('Status transition failed. Please try again.')
  },
})
```

---

### `frontend/src/routes/plum/components/NewRevisionDialog.tsx` (component, CRUD)

**Closest partial analog:** `frontend/src/routes/syerp/components/PartnerArchiveDialog.tsx` (Dialog shell pattern only)

**Dialog shell pattern** (PartnerArchiveDialog.tsx lines 86–127):
```typescript
<Dialog open={open} onOpenChange={handleOpenChange}>
  <DialogContent aria-labelledby="new-rev-title" aria-describedby="new-rev-desc">
    <DialogHeader>
      <DialogTitle id="new-rev-title">Create New Revision</DialogTitle>
      <DialogDescription id="new-rev-desc">
        A new Draft revision will be created, copying attributes from{' '}
        {sourceRevision?.revision_label}. You may choose a different source below.
      </DialogDescription>
    </DialogHeader>
    {/* Clone-from selector: <Select> listing all prior revisions */}
    {/* Reason for revision: <textarea> — required */}
    <DialogFooter>
      <Button variant="outline" onClick={onClose}>Cancel</Button>
      <Button variant="default" onClick={handleCreate} disabled={isCreating}>
        {isCreating ? <><Loader2 className="animate-spin" aria-hidden="true" />Creating…</> : 'Create Revision'}
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

**Mutation pattern** (follows PartnerArchiveDialog.tsx mutation shape at lines 50–67):
```typescript
const createRevisionMutation = useMutation<RevisionRead, Error, RevisionCreatePayload>({
  mutationFn: (payload) =>
    apiClient
      .post<RevisionRead>(`/api/v1/plum/parts/${partId}/revisions`, payload)
      .then((r) => r.data),
  onSuccess: (rev) => {
    void queryClient.invalidateQueries({ queryKey: ['plum', 'parts', partId] })
    toast(`New revision ${rev.revision_label} created.`)
    onClose()
  },
  onError: () => {
    toast.error('Failed to create revision. Please try again.')
  },
})
```

---

### `frontend/src/routes/plum/components/AdvanceStatusDialog.tsx` (component, event-driven)

**Closest partial analog:** `frontend/src/routes/syerp/components/PartnerArchiveDialog.tsx` (Dialog shell + destructive button pattern)

Only needed for the In Review → Released transition (confirmation required per UI-SPEC lines 213–219). Dialog shell follows PartnerArchiveDialog.tsx exactly. Key copy (UI-SPEC lines 213–219):
```typescript
<DialogTitle id="release-dialog-title">Release revision {revision.revision_label}?</DialogTitle>
<DialogDescription id="release-dialog-desc">
  This will release {revision.revision_label} and automatically obsolete the current
  released revision ({priorReleasedLabel}). Released revisions cannot be edited.
</DialogDescription>
// Footer: Cancel + Release (variant="default", NOT destructive)
```

---

## Shared Patterns

### Authentication / RBAC Gate
**Source:** `backend/app/modules/auth/dependencies.py` (lines 97–127)
**Apply to:** All PLUM router endpoints
```python
from app.modules.auth.dependencies import require_permission

# Read endpoints:
current_user=Depends(require_permission("plum:read"))

# Write endpoints (create, update/archive, create revision, advance status):
current_user=Depends(require_permission("plum:write"))
```
Note: `plum:read` and `plum:write` are already seeded in `backend/app/modules/auth/seed.py` lines 37–38. No new permission rows needed.

### Audit Logging
**Source:** `backend/app/modules/auth/service.py` lines 313–342
**Apply to:** All PLUM router write handlers (create part, update/archive, create revision, advance status)
```python
from app.modules.auth.service import write_audit

await write_audit(
    db,
    actor_id=str(current_user.id),
    action="part.created",          # or: part.updated, part.archived,
                                     #     revision.created, revision.submitted,
                                     #     revision.released, revision.rejected,
                                     #     revision.obsoleted
    target_type="part",             # or "revision"
    target_id=str(entity.id),
    detail="...",
)
```
Minimum required audit events (D-10): `part.created`, `revision.released`, `revision.obsoleted`. All other mutation events are best-practice additions.

### Error Handling (Backend)
**Source:** `backend/app/modules/syerp/service.py` lines 127–147 (IntegrityError catch)
**Apply to:** `create_part` service function
```python
import sqlalchemy.exc

try:
    await db.flush()
except sqlalchemy.exc.IntegrityError:
    await db.rollback()
    if user_supplied_code:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Part number '{code}' already exists.")
    code = await generate_part_number(db)
    # ... retry once
```

### Error Handling (Frontend)
**Source:** `frontend/src/routes/syerp/components/PartnerSheet.tsx` lines 114–131
**Apply to:** `PartSheet.tsx`, `NewRevisionDialog.tsx`, `AdvanceStatusDialog.tsx`
```typescript
function getApiErrorMessage(err: unknown, fallback: string): string {
  // ... (copy verbatim from PartnerSheet.tsx lines 114–131)
}
// Usage in onError handlers:
toast.error(getApiErrorMessage(err, 'Failed to save part. Please try again.'))
```

### TanStack Query Cache Invalidation
**Source:** `frontend/src/routes/syerp/Vendors.tsx` lines 122–124
**Apply to:** All PLUM mutation `onSuccess` handlers

| Mutation | Invalidate |
|----------|-----------|
| Create / archive / restore / edit part | `{ queryKey: ['plum', 'parts'] }` |
| Create revision | `{ queryKey: ['plum', 'parts', partId] }` |
| Advance revision status | `{ queryKey: ['plum', 'parts', partId] }` |

### Accessibility Requirements
**Source:** `frontend/src/routes/syerp/Vendors.tsx` lines 246–250 + `PartnerArchiveDialog.tsx` lines 88–90
**Apply to:** All PLUM components

- Icon-only buttons: `aria-label` on button + `aria-hidden="true"` on icon + `<span className="sr-only">` fallback
- Dialogs: `aria-labelledby` → DialogTitle `id` + `aria-describedby` → DialogDescription `id`
- Badges: color AND text label (never color alone)
- PlumNav: `aria-label="PLUM sections"` on `<nav>`
- Revision timeline: `aria-label="Revision history"` on `<ol>`

### Database Session Pattern (async)
**Source:** `backend/app/modules/syerp/router.py` line 63 + service.py throughout
**Apply to:** All PLUM router endpoints
```python
db: AsyncSession = Depends(get_db)
```
All DB operations use `await db.execute(select(...))`, `db.add(...)`, `await db.flush()`, `await db.commit()`, `await db.refresh(obj)`. No synchronous DB calls.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `frontend/src/routes/plum/PartDetail.tsx` | component | request-response | No existing "detail page" route with header card + timeline in the codebase. All SYERP screens are table-only list screens. The TanStack Query and page wrapper patterns transfer; the Card, timeline, and status-strip are net-new UI constructs. |
| Revision FSM logic in `plum/service.py` (`advance_revision_status`, `VALID_TRANSITIONS`) | service | event-driven | No state-machine / status-transition logic exists in any current service. Entirely new domain logic derived from D-07/D-08 decisions. |
| `plum_part_revision` "latest revision" correlated subquery (Pattern 4 in RESEARCH.md) | service | CRUD | No multi-row child query of this kind exists in syerp/service.py (Partner has no child table). Derived from RESEARCH.md Pattern 4. |

---

## Metadata

**Analog search scope:** `backend/app/modules/syerp/`, `backend/app/modules/auth/`, `backend/app/core/`, `backend/alembic/versions/`, `backend/tests/syerp/`, `backend/tests/conftest.py`, `frontend/src/routes/syerp/`, `frontend/src/App.tsx`
**Files scanned:** 19 source files read in full
**Pattern extraction date:** 2026-06-28
