# Phase 5: PLUM Parts & Revisions - Research

**Researched:** 2026-06-28
**Domain:** PLM data model (parts + revisions), FastAPI/SQLAlchemy module patterns, React/TanStack Query list + detail-page patterns
**Confidence:** HIGH

---

## Summary

Phase 5 creates the PLUM module from scratch, mirroring the SYERP module structure that Phase 4 fully established and verified. The codebase already contains the exact patterns this phase needs: `backend/app/modules/syerp/` is a complete working reference for module-as-package layout (models, schemas, service, router), RBAC gating, soft-delete, auto-generated codes, audit logging, and server-side search. The frontend has a complete reference in `Vendors.tsx` + `PartnerSheet.tsx` for the list + sheet pattern, and `SyerpNav.tsx` for the module sub-nav tab strip. The Part Detail route with a revision timeline is the only net-new UI construct with no existing analog.

The domain model diverges from the prototype (`plm_v54.html`) in a deliberate, well-documented way: the prototype stores revision-related fields on the part record itself (a flat structure with `revision` and `status` as scalar fields on each part). Phase 5 uses a **two-table model** — a stable `plum_part` header (part number, classification tags) and a `plum_part_revision` child table that snapshots revision-controlled attributes and carries the status state machine. This is the locked D-01/D-02 decision. The prototype is a field-set and UX reference only, not the target schema.

All PLUM permissions (`plum:read`, `plum:write`) are already seeded by `backend/app/modules/auth/seed.py`. The PLUM module is already registered in `modules_seed.py`. The `core/models.py` aggregator has a commented-out stub (`# from app.modules.plum import models as plum_models`) that just needs to be uncommented once the package exists.

**Primary recommendation:** Treat `backend/app/modules/syerp/` as the canonical copy-template for the new `backend/app/modules/plum/` package, and `Vendors.tsx` + `SyerpNav.tsx` as the copy-template for the Parts list frontend. Build the Part Detail route and revision timeline as net-new components following the established shadcn/TanStack Query pattern.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01: Attribute-snapshot revision model.** Part = stable header; each revision freezes a snapshot of revision-controlled attributes. Released revision is immutable. Revision history shows what changed A→B.
- **D-02: Stable identity vs revision-controlled split.**
  - Part-level (stable, shared across all revs): part number, classification tags.
  - Revision-controlled (snapshotted per revision): description, category, unit of measure, notes.
- **D-03: First revision auto-created; copy-forward seed.** Creating a part auto-creates its first revision in Draft. New revision copies prior revision's attributes forward. Default source = latest Released revision; user may clone from any prior revision.
- **D-04: Revision scheme = system-wide setting.** Two modes: SemVer (auto-start `0.1.0`) and ASME (auto-start `A`, skipping I, O, Q, S, X, Z per ASME Y14.35).
- **D-05: SemVer digit mapping.** MAJOR bumps on release (zeroes rest); MINOR bumps for new Draft; PATCH for trivial corrections. Released revisions land on clean whole numbers.
- **D-06: Part number = auto-prefill + editable + unique.** System prefills next sequential number; user may override; DB-enforced unique. No format/pattern enforcement in v1.
- **D-07: Lifecycle states live on the revision.** States: Draft → In Review → Released → Obsolete; reject: In Review → Draft. Draft = editable; In Review = locked; Released = frozen/immutable; Obsolete = terminal.
- **D-08: Supersede on release.** Releasing a new revision auto-obsoletes the prior released revision. Exactly one revision is in Released status per part at any time.
- **D-09: Forward-only — no revert flag.** No `is_current`/revert mechanism. "Go back" = create new forward revision cloning an older rev's attributes.
- **D-10: Transitions are `plum:write`-gated and audited.** Uses `require_permission("plum:write")` and `write_audit` helper. Audit events: `part.created`, `revision.released`, `revision.obsoleted` (minimum).
- **D-11: Soft-delete / archive — no hard delete.** Sets `active=false`; lists default to active-only with show-archived toggle. Rows retained for Phase-6 FK references.
- **D-12: Classification = optional multi-select tags, NOT a required enum.** Seeded starter vocabulary: Purchased, Manufactured, Assembly, Finished Good, Tool, Raw Material. Vocabulary editable via a setting. Required-to-create fields: part number + description only.
- **D-13: Phase 6 derives make/buy/assembly from BOM, not the tag.** Tags are purely organizational in v1.
- **D-14: List → dedicated Part Detail route.** Parts list screen → clicking a row opens `/plum/parts/:id` Part Detail route with revision-history timeline and revision actions.
- **D-15: Search & filter reuse Phase-4 mechanism.** Server-side debounced live search across part number + description; status filter (Draft/In Review/Released/Obsolete) on current revision status; active/archived toggle.

### Claude's Discretion

- Exact `plum_part` / `plum_part_revision` column sets, types, lengths, nullability, indexes.
- `active=false` vs `archived_at` timestamp for soft-delete marker (D-11).
- Unit-of-measure handling (free text vs seeded UoM list) and whether `category` is free text or controlled field.
- Storage of classification tags (join table vs array/JSON) and seed-management surface.
- Whether In Review → Released needs a dedicated approver permission beyond `plum:write` (D-10).
- Exact frontend composition of Part Detail route and revision timeline (D-14).
- Precise debounce timing and filter mechanics (D-15).
- Whether revision-scheme + tag-vocabulary settings are PLUM-scoped or global settings table (D-04, D-12).

### Deferred Ideas (OUT OF SCOPE)

- BOM / multi-level structure, where-used, cost roll-up, margin, AVL linking, import/export (Phase 6).
- ECO / engineering-change-order workflow + effectivity dates.
- Working iterations / check-in–check-out (informal A.1, A.2 versions).
- Revertible `is_current` current-release pointer.
- Part-number format/pattern enforcement (v1 enforces uniqueness only).
- Part-type / tag filter facet on the parts list.
- Distinct approver permission for In Review → Released (left as `plum:write` in v1).

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PLUM-01 | User can create, view, edit, and delete parts | Two-table model (plum_part + plum_part_revision); CRUD endpoints; PartSheet component; soft-delete archive pattern from SYERP |
| PLUM-02 | User can search and filter parts | Server-side search with `.ilike()` on part number + description; status filter on current revision; active/archived toggle; debounced 300ms in frontend |
| PLUM-03 | User can create part revisions and advance a part through its status workflow | plum_part_revision table with status FSM; transition endpoints; auto-obsolete on release; D-08 supersede logic; revision history on Part Detail page |

</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Part CRUD (create/edit/archive) | API / Backend | Frontend (form) | Business rules (unique code, auto-gen, audit) are backend; form is presentation only |
| Revision state machine (Draft→In Review→Released→Obsolete) | API / Backend | — | Immutability rules, supersede-on-release, transition validation must be enforced server-side |
| Status filter on "current revision" | API / Backend | — | Requires a subquery/join to find the most-recent non-obsoleted revision per part; cannot be done client-side cheaply |
| Classification tag storage and lookup | API / Backend | Frontend (multi-select UI) | FK integrity and seed management are server concerns; UI renders the tag list from API |
| Revision-scheme setting (ASME vs SemVer) | API / Backend | Frontend (read setting) | Label generation is backend business logic; frontend reads the current scheme to display labels |
| Revision history timeline | Frontend | — | Read-only display; data already fetched in Part Detail query; pure rendering concern |
| Part number auto-generation | API / Backend | Frontend (prefill display) | Uses DB MAX query to generate next code; frontend shows prefilled value, user edits before save |
| Search debounce | Frontend | — | 300ms debounce is a UX concern; backend receives the already-debounced `?q=` param |
| Navigation (Parts list → Part Detail) | Frontend (React Router) | — | Client-side routing; no server involvement in navigation |
| Audit logging | API / Backend | — | `write_audit()` called inside router handlers; not a frontend concern |

---

## Standard Stack

### Core (already installed — no new installs required)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | current (pyproject.toml) | API framework | Locked stack decision; existing module pattern |
| SQLAlchemy 2.0 async | current | ORM + async DB | Locked stack decision; all existing models use it |
| PostgreSQL | current (Podman Compose) | Persistence | Locked stack decision; single shared DB |
| Alembic | current | Schema migration | Established single-history pattern (0005 next) |
| Pydantic v2 | current | Request/response schemas | All existing schemas use `model_dump`, `from_attributes` |
| React 18 + TypeScript | current | Frontend | Locked stack |
| TanStack Query v5 | current | Data fetching + cache invalidation | All existing screens use it |
| shadcn/ui | current | Component library | All components needed are already installed |
| sonner | current | Toast notifications | Already installed (Phase 3) |
| lucide-react 1.21.0 | current | Icons | Already installed; `ChevronLeft`, `MoreHorizontal`, `Loader2` are in use |

### No new packages required

All library needs are satisfied by what is already installed. Verified: the UI-SPEC explicitly lists all required shadcn components as "Already Installed" and states "No new shadcn installs required for this phase." [VERIFIED: codebase scan of `frontend/src/components/ui/`]

---

## Package Legitimacy Audit

> No new packages are installed in this phase. All dependencies were already verified and installed in prior phases (Phases 1-4). This section is intentionally minimal.

| Package | Registry | Disposition |
|---------|----------|-------------|
| (none new) | — | Not applicable |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

---

## Architecture Patterns

### System Architecture Diagram

```
Browser
  │
  ├─ GET /plum/parts (PartsList)
  │     └─ useQuery(['plum','parts',{q,status,includeArchived}])
  │           └─ GET /api/v1/plum/parts?q=&status=&include_archived=
  │                 ├─ require_permission("plum:read")
  │                 └─ list_parts() — ilike search + status subquery + active filter
  │
  ├─ POST /api/v1/plum/parts (create part + first revision)
  │     ├─ require_permission("plum:write")
  │     ├─ generate_part_number() → auto-gen or user-supplied
  │     ├─ INSERT plum_part
  │     ├─ INSERT plum_part_revision (Draft, label=scheme_start, copy attrs from payload)
  │     └─ write_audit("part.created")
  │
  ├─ GET /plum/parts/:id (PartDetail)
  │     └─ useQuery(['plum','parts',id])
  │           └─ GET /api/v1/plum/parts/{id}
  │                 ├─ require_permission("plum:read")
  │                 └─ get_part_with_revisions() — part + all revisions ordered newest-first
  │
  ├─ PATCH /api/v1/plum/parts/{id} (edit/archive part)
  │     ├─ require_permission("plum:write")
  │     ├─ UPDATE plum_part (part-level fields only: tags if not join-table, active)
  │     └─ write_audit("part.updated" | "part.archived")
  │
  ├─ POST /api/v1/plum/parts/{id}/revisions (new revision)
  │     ├─ require_permission("plum:write")
  │     ├─ copy-forward attributes from source revision (D-03)
  │     ├─ compute next revision label (ASME or SemVer minor bump)
  │     ├─ INSERT plum_part_revision (status=Draft)
  │     └─ write_audit("revision.created")
  │
  └─ POST /api/v1/plum/parts/{id}/revisions/{rev_id}/advance (status transition)
        ├─ require_permission("plum:write")
        ├─ validate transition (FSM rules: D-07)
        ├─ if transition → Released:
        │     UPDATE prior Released revision → Obsolete
        │     write_audit("revision.obsoleted", prior_rev)
        ├─ UPDATE plum_part_revision status
        └─ write_audit("revision.released" | "revision.submitted" | "revision.rejected")
```

### Recommended Project Structure

```
backend/app/modules/plum/
├── __init__.py          # MODULE_NAME + self-register with registry
├── models.py            # PlumPart, PlumPartRevision, PlumPartTag (if join-table)
├── schemas.py           # PartCreate, PartUpdate, PartRead, RevisionCreate, RevisionRead, etc.
├── service.py           # list_parts, create_part, get_part, update_part, create_revision, advance_status
├── router.py            # /plum/parts + /plum/parts/{id}/revisions + advance endpoint
└── seed.py              # seed_plum_settings(), seed_plum_tag_vocabulary()

frontend/src/routes/plum/
├── PartsList.tsx                    # Parts list screen (/plum/parts)
├── PartDetail.tsx                   # Part detail + revision history (/plum/parts/:id)
└── components/
    ├── PlumNav.tsx                  # Tab strip (mirrors SyerpNav.tsx)
    ├── PartSheet.tsx                # Create/edit part sheet
    ├── NewRevisionDialog.tsx        # Create new revision dialog
    ├── ArchivePartDialog.tsx        # Archive confirmation dialog
    └── AdvanceStatusDialog.tsx      # Release confirmation dialog (In Review → Released)
```

### Pattern 1: Module-as-Package Registration

Every module is a Python package that self-registers with the router registry on import. Mirrors `syerp/__init__.py` exactly.

```python
# backend/app/modules/plum/__init__.py
# Source: codebase — backend/app/modules/syerp/__init__.py [VERIFIED: codebase]
import sys
from app.core import registry
from app.modules.plum.router import router  # noqa: F401

MODULE_NAME = "plum"
registry.register(sys.modules[__name__])
```

And `core/models.py` must be updated:
```python
# Uncomment the existing stub:
from app.modules.plum import models as plum_models  # noqa: F401
```

### Pattern 2: Two-Table Model (plum_part + plum_part_revision)

The part is a stable header; revisions carry the evolving design data:

```python
# backend/app/modules/plum/models.py [ASSUMED — SQLAlchemy 2.0 pattern; column set is planner's discretion]
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, String, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column
from app.core.base import Base

class PlumPart(Base):
    __tablename__ = "plum_part"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    part_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    # Classification tags: store as join table (see Pattern 5) or JSONB array

class PlumPartRevision(Base):
    __tablename__ = "plum_part_revision"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    part_id: Mapped[str] = mapped_column(String(36), ForeignKey("plum_part.id"), nullable=False, index=True)
    revision_label: Mapped[str] = mapped_column(String(20), nullable=False)  # "A", "0.1.0", etc.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")  # draft|in_review|released|obsolete
    # Revision-controlled attribute snapshot (D-02)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit_of_measure: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_for_revision: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    obsoleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

**Note:** No ORM relationships declared on these models to avoid `MissingGreenlet` in async context — the SYERP models document this pitfall explicitly. Use explicit `select` queries with `where(PlumPartRevision.part_id == part_id)`.

### Pattern 3: Revision Status FSM

Valid transitions only (D-07):

```
draft → in_review      (submit)
in_review → released   (release — also obsoletes prior released)
in_review → draft      (reject)
released → obsolete    (auto-triggered only by next release — no direct user action)
```

```python
# backend/app/modules/plum/service.py [ASSUMED — pattern derived from domain rules D-07/D-08]
VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft":      ["in_review"],
    "in_review":  ["released", "draft"],
    "released":   ["obsolete"],   # only triggered internally by supersede
    "obsolete":   [],             # terminal
}

async def advance_revision_status(db, part_id, revision_id, target_status, actor_id):
    revision = await get_revision(db, revision_id)
    if revision.part_id != part_id:
        raise HTTPException(404)
    if target_status not in VALID_TRANSITIONS.get(revision.status, []):
        raise HTTPException(422, detail=f"Cannot transition from {revision.status} to {target_status}")

    if target_status == "released":
        # D-08: supersede prior released revision
        prior = await get_released_revision(db, part_id)
        if prior and prior.id != revision_id:
            prior.status = "obsolete"
            prior.obsoleted_at = datetime.now(timezone.utc)
            await write_audit(db, actor_id, "revision.obsoleted", "revision", prior.id,
                              f"Superseded by {revision.revision_label}")

    revision.status = target_status
    if target_status == "released":
        revision.released_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(revision)

    audit_action = {
        "in_review": "revision.submitted",
        "released":  "revision.released",
        "draft":     "revision.rejected",
    }[target_status]
    await write_audit(db, actor_id, audit_action, "revision", revision_id, ...)
    return revision
```

### Pattern 4: Current Revision for Status Filter (PLUM-02)

Filtering the parts list by "current revision status" requires identifying the current revision per part. The current revision is the latest non-obsolete revision (most recently created revision that is not Obsolete), or the single Released revision if one exists.

Recommended approach: a correlated subquery or a `DISTINCT ON` PostgreSQL query. The simpler approach for this list scale:

```python
# backend/app/modules/plum/service.py [ASSUMED — SQLAlchemy pattern]
from sqlalchemy import select, func

# Subquery: most recent revision per part
latest_rev_subq = (
    select(
        PlumPartRevision.part_id,
        func.max(PlumPartRevision.created_at).label("latest_created_at")
    )
    .group_by(PlumPartRevision.part_id)
    .subquery()
)

stmt = (
    select(PlumPart, PlumPartRevision)
    .join(PlumPartRevision, PlumPartRevision.part_id == PlumPart.id)
    .join(latest_rev_subq, (
        (latest_rev_subq.c.part_id == PlumPartRevision.part_id) &
        (latest_rev_subq.c.latest_created_at == PlumPartRevision.created_at)
    ))
)
if status_filter:
    stmt = stmt.where(PlumPartRevision.status == status_filter)
```

**Note:** This works reliably only if `created_at` values are unique per part. A safer alternative is a `revision_order` integer column (1, 2, 3...) on `plum_part_revision` to avoid timestamp collision. The planner should choose one of these approaches.

### Pattern 5: Classification Tags Storage

Three options (planner's discretion per Claude's Discretion list):

**Option A — Join table (recommended for Phase 6 extensibility):**
```
plum_classification_tag (id, name, sort_order)  ← seeded
plum_part_tag (part_id FK, tag_id FK)           ← join table
```
- Clean relational model; Phase 6 can filter by tag efficiently; supports tag management via settings.

**Option B — Array/JSONB column on plum_part:**
```
plum_part.tags: JSONB (e.g. ["Purchased", "Tool"])
```
- Simpler migration; PostgreSQL JSONB supports array containment queries; less setup.
- Downside: tag rename requires a data migration over all part rows.

**Recommendation:** Join table (Option A). Tags are already identified as editable via a setting (D-12), and Phase 6 will want to filter/report by tag. The join table approach keeps the data normalized and supports future tag management cleanly. [ASSUMED — based on relational design best practices and Phase-6 extensibility requirement from CONTEXT.md]

### Pattern 6: Revision Label Generation

```python
# ASME mode: A, B, C, D, E, F, G, H, J, K, L, M, N, P, R, T, U, V, W, Y
# Skip: I, O, Q, S, X, Z (per ASME Y14.35)
ASME_SKIP = {"I", "O", "Q", "S", "X", "Z"}
ASME_LETTERS = [c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c not in ASME_SKIP]
# ASME_LETTERS = ['A','B','C','D','E','F','G','H','J','K','L','M','N','P','R','T','U','V','W','Y']
# 20 valid letters; after Y double up: AA, AB, ...

# SemVer mode: first revision = "0.1.0"
# New Draft (minor bump from released): 1.0.0 → 1.1.0
# Release (major bump): 0.1.0 → 1.0.0, 1.1.0 → 2.0.0
# Patch correction: 1.0.0 → 1.0.1
```

[ASSUMED — derived from D-04/D-05 in CONTEXT.md; implementation detail is planner's discretion]

### Pattern 7: Part Number Auto-Generation

Mirrors the SYERP partner code pattern (`generate_partner_code`). Use a DB MAX query on existing part numbers to determine the next value.

```python
# Mirrors syerp/service.py generate_partner_code() exactly
async def generate_part_number(db: AsyncSession) -> str:
    from sqlalchemy import func
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

On `IntegrityError` (duplicate), retry once with a fresh number (same as SYERP pattern — user-supplied duplicate → 409 Conflict; auto-generated collision → retry). [ASSUMED — format choice (P##### vs P-####) is planner's discretion]

### Pattern 8: Frontend TanStack Query Keys

Consistent query key hierarchy — mirrors SYERP pattern:

```typescript
// List query
['plum', 'parts', { q, status, includeArchived }]

// Detail query
['plum', 'parts', partId]

// Revisions for a part (loaded as part of detail or separately)
['plum', 'parts', partId, 'revisions']
```

On successful mutations, invalidate the appropriate scope:
- Create/archive/edit part → invalidate `['plum', 'parts']`
- Create/advance revision → invalidate `['plum', 'parts', partId]`

### Anti-Patterns to Avoid

- **ORM relationships without `lazy="selectin"` in async context.** The SYERP models explicitly document this pitfall (MissingGreenlet). Do not declare SQLAlchemy `relationship()` on async models unless `lazy="selectin"` is set. Use explicit queries instead.
- **Status filter client-side on a large list.** The status filter must be server-side (the list could grow to hundreds of parts). All filtering goes through query params.
- **Hardcoding revision labels.** The revision scheme (ASME vs SemVer) is a setting. Label generation must read the setting, not hardcode "A".
- **Blocking Released revisions on the frontend only.** The immutability of Released revisions (D-07) must be enforced at the API layer (return 422 on any edit attempt for a revision with status=released). Frontend disabling of the "Edit" action is UX only.
- **Hard-deleting parts or revisions.** Only soft-delete (active=false) on parts. Revisions are never deleted — Obsolete is terminal, not deleted.
- **Missing audit log on release.** The `revision.released` and `revision.obsoleted` audit entries (D-10) must both be written when a revision is released (one for the new Released rev, one for the prior Obsoleted rev).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| RBAC permission gating | Custom auth check | `require_permission("plum:read|write")` from `auth/dependencies.py` | Already exists and tested |
| Audit log entries | Custom log table or print | `write_audit()` from `auth/service.py` | Existing helper; append-only pattern already established |
| UUID generation | Custom ID scheme | `lambda: str(uuid.uuid4())` in `mapped_column(default=...)` | SYERP pattern; consistent with all existing PKs |
| Pydantic request validation | Manual field checks | `Field(..., max_length=N)` + `model_validator` | Pydantic v2 handles it; SYERP schemas are the reference |
| TanStack Query cache invalidation | Manual state management | `queryClient.invalidateQueries({ queryKey: [...] })` | Existing pattern in Vendors.tsx |
| Debounce logic for search | Custom throttle | `useRef` + `setTimeout(300ms)` pattern from Vendors.tsx | Copy exact pattern; don't add a debounce library |
| Toast notifications | Custom alert/notification | `toast()` from `sonner` (already installed Phase 3) | sonner is the project's toast library |
| Dialog/Sheet components | Custom modal | shadcn `<Dialog>`, `<Sheet>` (already installed) | All components needed are in `frontend/src/components/ui/` |

**Key insight:** This phase's backend is a near-copy of the SYERP module with a different domain model. The frontend list screen is a near-copy of Vendors.tsx with different columns. Maximize reuse of established patterns; the only genuinely new work is the Part Detail route with revision timeline and the status FSM service logic.

---

## Common Pitfalls

### Pitfall 1: MissingGreenlet on ORM Relationships (async SQLAlchemy)

**What goes wrong:** Declaring a `relationship()` on a model and accessing it outside an `async with` session context raises `MissingGreenlet`. The SYERP models have an explicit comment about this pitfall.

**Why it happens:** SQLAlchemy's async session does not allow implicit lazy loading. Any relationship access triggers a synchronous DB call that fails in async context.

**How to avoid:** Do not declare `relationship()` on `PlumPart` or `PlumPartRevision` unless `lazy="selectin"` is set. Instead, write explicit `select` queries in service functions. Example: to get all revisions for a part, run `select(PlumPartRevision).where(PlumPartRevision.part_id == part_id)` explicitly.

**Warning signs:** `sqlalchemy.exc.MissingGreenlet` exception at runtime when a route is called.

### Pitfall 2: Revision Immutability Not Enforced Server-Side

**What goes wrong:** The frontend disables the edit form for Released revisions, but the PATCH endpoint accepts the update anyway, corrupting the audit trail.

**Why it happens:** Frontend-only guards are bypassed by direct API calls.

**How to avoid:** In `update_revision()` service function, check `if revision.status == "released": raise HTTPException(422, "Released revisions are immutable")`. This is the authoritative guard; the frontend disable is only UX convenience.

**Warning signs:** PATCH to a Released revision returns 200 instead of 422.

### Pitfall 3: Two Released Revisions Simultaneously

**What goes wrong:** A race condition where two concurrent requests both advance a revision to Released without one triggering the supersede of the other. Result: two revisions with `status="released"` on the same part.

**Why it happens:** The "check-then-act" pattern (read prior released, then update, then update current) is not atomic without a transaction or SELECT FOR UPDATE.

**How to avoid:** Wrap the entire advance-to-released logic in a single database transaction. SQLAlchemy's async session uses a transaction per request by default; ensure `flush()` is called between the two updates (obsolete prior + release current) within the same transaction before `commit()`. Alternatively, add a partial unique index: `CREATE UNIQUE INDEX uq_plum_part_one_released ON plum_part_revision(part_id) WHERE status = 'released'` — the DB enforces the invariant at the schema level.

**Warning signs:** Two rows in `plum_part_revision` with the same `part_id` and `status='released'`.

### Pitfall 4: Status Filter on "Current Revision" — Wrong JOIN

**What goes wrong:** Joining `plum_part` to `plum_part_revision` without limiting to the "current" revision returns multiple rows per part (one per revision). Applying the status filter then excludes parts that have any non-matching revision, not parts whose *current* revision doesn't match.

**Why it happens:** Simple JOIN without "latest revision" subquery.

**How to avoid:** Always filter via a correlated subquery or `DISTINCT ON (part_id) ORDER BY created_at DESC` to identify the current revision before applying the status filter. See Pattern 4 above.

**Warning signs:** A part with RevA=Released and RevB=Draft disappears from the "Released" filter even though its *current* revision is Draft (which is correct), or conversely appears in "Draft" even though an older rev was Released.

### Pitfall 5: Alembic Autogenerate Misses New Models

**What goes wrong:** `alembic revision --autogenerate` produces an empty migration because the new models are not imported into `core/models.py`.

**Why it happens:** Alembic's `env.py` imports `core/models.py` to populate `Base.metadata`; models not imported there are invisible.

**How to avoid:** Uncomment the existing commented stub in `backend/app/core/models.py`:
```python
from app.modules.plum import models as plum_models  # noqa: F401
```
Do this before running `alembic revision --autogenerate`. The stub is already in the file waiting for Phase 5. [VERIFIED: codebase]

**Warning signs:** `alembic revision --autogenerate` generates a migration with only `# No changes detected` or empty `upgrade()`/`downgrade()` bodies.

### Pitfall 6: `active=false` Leaks Into Phase-6 FK Pickers

**What goes wrong:** Phase 6 adds BOM child selection — if the parts list endpoint returns archived parts by default, an archived part could be added to a BOM.

**Why it happens:** `include_archived` parameter defaults to `False`; but if a new endpoint (e.g. a BOM picker) fails to pass this default, it might surface archived parts.

**How to avoid:** All list endpoints default to `include_archived=False`. Document this explicitly in the service function docstring. Phase 6 BOM pickers should use the same default. [Mirrors the same pitfall documented in SYERP service.py]

### Pitfall 7: Revision Label Generation Reads Setting on Every Call

**What goes wrong:** If the revision scheme setting is fetched from the DB inside every call to `generate_revision_label()`, this adds a DB round-trip on every part create and revision create.

**Why it happens:** Settings are stored in the `settings` table, not in app config.

**How to avoid:** Read the revision scheme setting once per request in the router handler (it's one row) and pass it to the service function. Or cache it with a short TTL. Do not embed a DB query inside a tight loop.

---

## Code Examples

Verified patterns from the existing codebase:

### Module Self-Registration (`__init__.py`)
```python
# Source: backend/app/modules/syerp/__init__.py [VERIFIED: codebase]
import sys
from app.core import registry
from app.modules.plum.router import router  # noqa: F401

MODULE_NAME = "plum"
registry.register(sys.modules[__name__])
```

### Idempotent Seed (select-before-insert)
```python
# Source: backend/app/modules/auth/seed.py [VERIFIED: codebase]
result = await db.execute(select(PlumClassificationTag).where(PlumClassificationTag.name == name))
if result.scalars().first() is None:
    db.add(PlumClassificationTag(name=name, sort_order=sort_order))
await db.commit()
```

### Server-Side Search with `.ilike()`
```python
# Source: backend/app/modules/syerp/service.py [VERIFIED: codebase]
if q:
    like = f"%{q}%"
    stmt = stmt.where(
        or_(
            PlumPart.part_number.ilike(like),
            PlumPartRevision.description.ilike(like),
        )
    )
```

### Soft-Delete Archive Pattern
```python
# Source: backend/app/modules/syerp/router.py (archive via PATCH) [VERIFIED: codebase]
existing = await get_part(db, part_id)
was_active = existing.active
part = await update_part(db, part_id, data)
is_archiving = data.active is False and was_active is True
audit_action = "part.archived" if is_archiving else "part.updated"
await write_audit(db, actor_id=str(current_user.id), action=audit_action, ...)
```

### Frontend Debounced Search
```typescript
// Source: frontend/src/routes/syerp/Vendors.tsx [VERIFIED: codebase]
const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
  const v = e.target.value
  setSearchValue(v)
  if (debounceTimer.current) clearTimeout(debounceTimer.current)
  debounceTimer.current = setTimeout(() => setSearchFilter(v), 300)
}, [])
```

### Frontend Module Sub-Nav Tab Strip
```typescript
// Source: frontend/src/routes/syerp/components/SyerpNav.tsx [VERIFIED: codebase]
const TABS = [
  { to: '/plum/parts', label: 'Parts' },
  // Phase 6 will add: { to: '/plum/boms', label: 'BOMs' }
]
export function PlumNav() {
  return (
    <nav className="flex gap-1 border-b border-border" aria-label="PLUM sections">
      {TABS.map((tab) => (
        <NavLink key={tab.to} to={tab.to} className={({ isActive }) =>
          cn('-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors',
             isActive ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground')
        }>{tab.label}</NavLink>
      ))}
    </nav>
  )
}
```

### React Router Navigate Redirect Pattern
```tsx
// Source: frontend/src/App.tsx [VERIFIED: codebase] — SYERP pattern to mirror for PLUM
<Route path="/plum" element={<Navigate to="/plum/parts" replace />} />
<Route path="/plum/parts" element={<PartsList />} />
<Route path="/plum/parts/:id" element={<PartDetail />} />
```

---

## Detailed Design Recommendations (Claude's Discretion Items)

The following are the researcher's recommendations for the discretion items delegated in CONTEXT.md:

### Soft-Delete Marker

**Recommend `active=false` boolean.** Matches the SYERP partner pattern exactly (D-05 Phase 4 used `active`). An `archived_at` timestamp is more informative but adds complexity (nullable timestamp vs boolean) without benefit in v1 — archived-at can be derived from the audit log if needed. Consistency with SYERP is the stronger argument. [ASSUMED]

### Classification Tags Storage

**Recommend join table.** See Pattern 5. Tags are explicitly described as "editable via a setting" (D-12). A join table supports tag rename without a data migration over all part rows, and supports Phase-6 BOM filtering by tag. [ASSUMED]

Tables:
- `plum_classification_tag (id INT PK, name VARCHAR(100) UNIQUE, sort_order INT, active BOOL)` — seeded
- `plum_part_tag (part_id VARCHAR(36) FK → plum_part.id, tag_id INT FK → plum_classification_tag.id, PRIMARY KEY (part_id, tag_id))`

### Unit-of-Measure Handling

**Recommend free text on `PlumPartRevision.unit_of_measure` (VARCHAR 50).** A seeded UoM list adds infrastructure complexity (another table, another seed, another settings entry) for a Phase 5 that already has significant scope. Free text is correct for v1. Phase 6 can add a controlled UoM vocabulary if needed. [ASSUMED]

### Category Handling

**Recommend free text on `PlumPartRevision.category` (VARCHAR 100).** Same reasoning as UoM. The prototype uses it as a text category field; there is no decision to make it controlled in v1. [ASSUMED]

### Revision-Scheme and Tag-Vocabulary Settings

**Recommend storing in the global `settings` table** (the Phase-3 settings infrastructure). Two new setting rows:
- `plum.revision_scheme` = `"asme"` | `"semver"`, default `"asme"`
- `plum.tag_vocabulary_editable` = `"true"` | `"false"`, default `"true"` (controls whether the tag list shows an "Add custom tag" option)

This reuses the existing `core/settings_seed.py` pattern with no new infrastructure. The settings API already exists. [ASSUMED]

### Part Number Format

**Recommend `P#####` (P + 5 zero-padded digits, e.g. P00001).** Matches the prototype's actual part numbers in `plm_database.json` (`"P00001"`, `"P00002"`, etc.) — familiar to the user. The SYERP code uses `P-####` (with dash); using `P#####` (no dash) for parts distinguishes them visually. [ASSUMED — planner may choose either format]

### Revision Order Column

**Recommend adding `revision_number INT` (1, 2, 3...) to `plum_part_revision`.** Auto-increment per part. This solves the "latest revision" query cleanly via `MAX(revision_number)` and avoids the timestamp collision issue described in Pitfall 3/Pattern 4. Use a sequence-per-part: on insert, `SELECT MAX(revision_number) FROM plum_part_revision WHERE part_id = ? FOR UPDATE` then `MAX + 1` within a transaction. [ASSUMED]

### `PlumPartRevision` Indexes

- `ix_plum_part_revision_part_id` — for all "revisions for a part" queries
- `ix_plum_part_revision_status` — for status filter queries
- `ix_plum_part_revision_part_id_status` — composite, for "find Released revision for part X" queries (the supersede check in D-08)

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| PLUM prototype: flat part record with `revision` + `status` scalars on the part | Phase 5: two-table model (`plum_part` header + `plum_part_revision` child, D-01/D-02) | Enables revision history, immutable Released snapshots, Phase-6 BOM attachment per revision |
| Prototype: monolithic status (draft/released/obsolete on part) | Phase 5: status FSM on revision (Draft→In Review→Released→Obsolete per revision, D-07) | Supports concurrent revisions at different statuses (e.g. Rev B in Draft while Rev A is Released) |
| Prototype: ECO workflow for change governance | Phase 5: free-text "reason for revision" note (deferred ECO to Phase 6+) | Lighter model; ECO can be added as PLUM-13 without changing the core revision structure |

---

## Runtime State Inventory

> This is a **greenfield phase** (creating a new module from scratch). There is no runtime state to migrate. This section confirms the absence of state to migrate.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — `plum_part` and `plum_part_revision` tables do not exist yet | Create via Alembic migration 0005 |
| Live service config | None — PLUM module exists in the `modules` table (seeded Phase 3) but has no router mounted yet | Register router in `__init__.py`, mount via `core/registry.py` |
| OS-registered state | None | — |
| Secrets/env vars | None specific to PLUM | `plum:read`/`plum:write` permissions already seeded (Phase 2) |
| Build artifacts | None | — |

---

## Environment Availability

> Step 2.6: External dependencies are the same as Phases 1-4 (PostgreSQL, Python/FastAPI, Node/React). No new external tools required.

| Dependency | Required By | Available | Fallback |
|------------|------------|-----------|----------|
| PostgreSQL | plum_part + plum_part_revision tables | ✓ (running from Phase 4) | — |
| Python / FastAPI runtime | Backend API | ✓ | — |
| Node.js / Vite dev server | Frontend development | ✓ | — |
| Alembic | Migration 0005 | ✓ | — |

**Missing dependencies with no fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework (backend) | pytest + pytest-asyncio (`asyncio_mode = "auto"`) |
| Framework (frontend) | vitest + @testing-library/react |
| Backend config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Frontend config file | `frontend/vite.config.ts` (`test.environment = "jsdom"`) |
| Backend quick run | `cd backend && python -m pytest tests/plum/ -x` |
| Frontend quick run | `cd frontend && npx vitest run src/routes/plum/` |
| Backend full suite | `cd backend && python -m pytest` |
| Frontend full suite | `cd frontend && npx vitest run` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLUM-01 | Create part → 201, fields correct, first revision auto-created in Draft | integration (DB) | `pytest tests/plum/test_parts.py::test_create_part -x` | ❌ Wave 0 |
| PLUM-01 | Create part with duplicate part_number → 409 | integration (DB) | `pytest tests/plum/test_parts.py::test_create_duplicate_part_number -x` | ❌ Wave 0 |
| PLUM-01 | Edit part → 200, audit log written | integration (DB) | `pytest tests/plum/test_parts.py::test_update_part -x` | ❌ Wave 0 |
| PLUM-01 | Archive part → active=false, hidden from default list | integration (DB) | `pytest tests/plum/test_parts.py::test_archive_part -x` | ❌ Wave 0 |
| PLUM-01 | `plum:write` required for create → 403 without it | integration (DB) | `pytest tests/plum/test_parts.py::test_create_requires_write_permission -x` | ❌ Wave 0 |
| PLUM-02 | Search ?q= filters by part_number | integration (DB) | `pytest tests/plum/test_parts.py::test_search_by_part_number -x` | ❌ Wave 0 |
| PLUM-02 | Search ?q= filters by description | integration (DB) | `pytest tests/plum/test_parts.py::test_search_by_description -x` | ❌ Wave 0 |
| PLUM-02 | Status filter returns only matching parts | integration (DB) | `pytest tests/plum/test_parts.py::test_filter_by_status -x` | ❌ Wave 0 |
| PLUM-03 | Create revision → 201, status=Draft, attributes copied forward | integration (DB) | `pytest tests/plum/test_revisions.py::test_create_revision -x` | ❌ Wave 0 |
| PLUM-03 | Advance Draft → In Review → 200, status updated | integration (DB) | `pytest tests/plum/test_revisions.py::test_advance_to_in_review -x` | ❌ Wave 0 |
| PLUM-03 | Advance In Review → Released → prior Released becomes Obsolete | integration (DB) | `pytest tests/plum/test_revisions.py::test_release_supersedes_prior -x` | ❌ Wave 0 |
| PLUM-03 | Edit Released revision → 422 (immutable) | integration (DB) | `pytest tests/plum/test_revisions.py::test_released_revision_immutable -x` | ❌ Wave 0 |
| PLUM-03 | Revision history visible (ordered newest-first) | integration (DB) | `pytest tests/plum/test_revisions.py::test_revision_history_order -x` | ❌ Wave 0 |
| PLUM-01 | PartsList screen renders heading + Create Part button | unit (frontend) | `cd frontend && npx vitest run src/routes/plum/PartsList.test.tsx` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend && python -m pytest tests/plum/ -x` (backend) + `cd frontend && npx vitest run src/routes/plum/` (frontend)
- **Per wave merge:** Full suite — `cd backend && python -m pytest` + `cd frontend && npx vitest run`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/plum/__init__.py` — test package init
- [ ] `backend/tests/plum/test_parts.py` — PLUM-01/02 backend tests (mirrors `tests/syerp/test_partners.py`)
- [ ] `backend/tests/plum/test_revisions.py` — PLUM-03 backend tests
- [ ] `frontend/src/routes/plum/PartsList.test.tsx` — smoke test (mirrors `Vendors.test.tsx`)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (inherited) | `get_current_user` dependency in `auth/dependencies.py` |
| V3 Session Management | yes (inherited) | JWT access token + httpOnly refresh cookie (Phase 2) |
| V4 Access Control | yes | `require_permission("plum:read")` / `require_permission("plum:write")` |
| V5 Input Validation | yes | Pydantic `Field(max_length=N)` + model validators on all create/update schemas |
| V6 Cryptography | no | No new cryptographic operations in this phase |

### Known Threat Patterns for This Phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via search `?q=` param | Tampering | Parameterized `.ilike()` (never raw-SQL string interpolation) — mirrors SYERP service.py |
| Unauthorized write (create/edit/archive/advance status) | Elevation of Privilege | `require_permission("plum:write")` on all mutation endpoints |
| Unauthorized read | Info Disclosure | `require_permission("plum:read")` on all GET endpoints |
| Bypassing Released revision immutability | Tampering | Server-side 422 check before any PATCH on a Released revision |
| Race condition: two revisions simultaneously Released | Tampering | Atomic transaction + optional partial unique index on `(part_id) WHERE status='released'` |
| XSS via revision `description` or `notes` stored in DB and rendered | Tampering | React auto-escapes JSX interpolation; no `dangerouslySetInnerHTML` — safe by default |
| Audit log repudiation | Repudiation | `write_audit()` is append-only (no update/delete endpoint); audits both release and obsolete events |

---

## Project Constraints (from CLAUDE.md)

- **Commit messages:** Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`). No "co-authored", "powered by", or "generated with Claude" in any commit message.
- **Branch naming:** This work is on `chore-architecture-planning`; feature work branches use `feature-*`.
- **Feature alignment:** Reference requirement IDs (PLUM-01, PLUM-02, PLUM-03) in task/plan work. Update `docs/features/requirements-progress.md` when completing a requirement.
- **No CHANGELOG.md edits:** Generated from commits; never edit directly.
- **GSD workflow:** All implementation proceeds through GSD phases/plans (`.planning/` artifacts), not ad-hoc edits.
- **Tech stack constraints:**
  - Backend: FastAPI + SQLAlchemy 2.0 + PostgreSQL. No ORMs other than SQLAlchemy.
  - Frontend: React 18 + TypeScript + Tailwind CSS + shadcn/ui. No new CSS frameworks. No inline JS.
  - No new third-party packages unless absolutely required (none are required for Phase 5).
- **Plum module namespace:** Table names use `plum_` prefix; route prefix is `/plum/...` (no `/api/v1` in router — `mount_all()` adds it).
- **Alembic single history:** New migration = `0005_plum_tables.py`, `down_revision = "0004"`.

---

## Open Questions

1. **Partial unique index for "one Released per part" invariant**
   - What we know: The D-08 supersede logic ensures only one revision is Released at a time via application code.
   - What's unclear: Whether to also add a DB-level `UNIQUE WHERE status='released'` partial index as a belt-and-suspenders guard against race conditions.
   - Recommendation: Add it. The migration is one line and protects a critical data invariant. If the partial index is too restrictive (PostgreSQL partial index syntax varies), fall back to validating in service + explicit `SELECT FOR UPDATE` in the release transaction. [ASSUMED]

2. **Revision number auto-increment strategy**
   - What we know: The "latest revision" subquery (Pattern 4) is cleaner with an integer `revision_number` column vs timestamp comparison.
   - What's unclear: Whether `SELECT MAX(revision_number) WHERE part_id = ? FOR UPDATE` inside a transaction is sufficient, or whether a PostgreSQL sequence per part is needed.
   - Recommendation: `SELECT MAX(revision_number) FOR UPDATE` within a transaction is sufficient for a self-hosted single-server deployment with low concurrency. No per-part sequence needed. [ASSUMED]

3. **`GET /plum/parts/:id` response shape — embed revisions or separate endpoint?**
   - What we know: The Part Detail screen shows the part header plus all revisions. The NewRevisionDialog needs a list of existing revisions for the clone-from selector.
   - What's unclear: Whether to embed revisions in the `GET /plum/parts/{id}` response or provide a separate `GET /plum/parts/{id}/revisions` endpoint.
   - Recommendation: Embed revisions in the part detail response (`PartDetailRead` schema includes `revisions: list[RevisionRead]`). Keeps the frontend to one query for the Part Detail route. [ASSUMED]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Join table is the better choice for classification tags | Design Recommendations — Tags | If inline JSONB is chosen instead, the migration and schema differ; minor rework |
| A2 | `active=false` boolean is preferable to `archived_at` timestamp | Design Recommendations — Soft-delete | If timestamp chosen, column name changes in migration and queries |
| A3 | `revision_number INT` column added to resolve "latest revision" query cleanly | Design Recommendations — Revision Order | Without this, timestamp-based "latest" query has edge cases; design decision affects Pattern 4 |
| A4 | Partial unique index `ON plum_part_revision(part_id) WHERE status='released'` | Open Questions | Without the index, double-release is possible in a race; with it, the DB enforces the invariant |
| A5 | `GET /plum/parts/{id}` embeds revisions in response (not separate endpoint) | Open Questions | If separate endpoint preferred, frontend needs two queries for Part Detail |
| A6 | Part number format is `P#####` (e.g. `P00001`) | Pattern 7 | If user prefers `P-####` (SYERP style) or another format, update the generator |
| A7 | Revision scheme and tag vocabulary stored as global settings (not PLUM-scoped) | Design Recommendations — Settings | If PLUM-scoped settings are preferred, a new `settings.owner_type` filter is needed |
| A8 | Free text for `unit_of_measure` and `category` | Design Recommendations | If controlled vocabulary is preferred later, requires adding lookup tables in Phase 6 |

---

## Sources

### Primary (HIGH confidence — verified from codebase)

- `backend/app/modules/syerp/` — complete backend module pattern reference (models, schemas, service, router, __init__.py)
- `backend/app/modules/auth/service.py` — `write_audit()` function signature and usage
- `backend/app/modules/auth/dependencies.py` — `require_permission()` and `get_current_user` dependencies
- `backend/app/modules/auth/seed.py` — confirms `plum:read` and `plum:write` permissions already seeded
- `backend/app/core/models.py` — confirms commented-out PLUM stub awaiting uncomment
- `backend/app/core/modules_seed.py` — confirms PLUM already registered in the 7-suite catalog
- `backend/app/core/seed.py` — confirms `run_seeds()` pattern for adding PLUM seed
- `backend/tests/syerp/test_partners.py` — Wave 0 test structure pattern
- `backend/tests/conftest.py` — `skip_if_no_db` fixture and `client` fixture pattern
- `frontend/src/routes/syerp/Vendors.tsx` — list screen pattern (search, table, empty states, mutations)
- `frontend/src/routes/syerp/components/PartnerSheet.tsx` — sheet create/edit pattern
- `frontend/src/routes/syerp/components/SyerpNav.tsx` — sub-nav tab strip pattern
- `frontend/src/routes/syerp/components/PartnerArchiveDialog.tsx` — destructive dialog pattern
- `frontend/src/App.tsx` — route wiring pattern (Navigate + nested Route)
- `frontend/src/routes/syerp/Vendors.test.tsx` — Wave 0 frontend test pattern
- `frontend/vite.config.ts` — vitest configuration
- `backend/pyproject.toml` — pytest configuration
- `.planning/phases/05-plum-parts-revisions/05-CONTEXT.md` — all locked decisions (D-01 through D-15)
- `.planning/phases/05-plum-parts-revisions/05-UI-SPEC.md` — complete UI design contract

### Secondary (MEDIUM confidence — derived from official project documentation)

- `plum/data/plm_database.json` — confirms actual part field set from the prototype (part_number format P#####, revision "A", status "draft"/"Released")
- `.planning/phases/04-syerp-core-hub/04-04-SUMMARY.md` — confirms Phase 4 complete and all patterns established

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all dependencies are already installed; verified in codebase
- Architecture (backend module structure): HIGH — direct copy of verified SYERP pattern
- Architecture (revision FSM): HIGH — locked decisions D-07/D-08 are authoritative
- Architecture (frontend list screen): HIGH — direct copy of verified Vendors.tsx pattern
- Architecture (Part Detail route / revision timeline): MEDIUM — net-new UI with no existing analog; UI-SPEC is detailed and prescriptive but implementation has not been executed
- Discretion recommendations (tags, soft-delete, revision number): ASSUMED — labeled as such
- Pitfalls: HIGH — drawn directly from existing codebase comments (SYERP models document MissingGreenlet pitfall; syerp/service.py documents the archived-rows-in-pickers pitfall)

**Research date:** 2026-06-28
**Valid until:** 2026-07-28 (stable stack — 30 days; no fast-moving dependencies)
