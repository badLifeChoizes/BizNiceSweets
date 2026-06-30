# Phase 6: PLUM BOM, Costing & Integration — Research

**Researched:** 2026-06-29
**Domain:** PostgreSQL recursive CTEs, multi-level BOM data models, async SQLAlchemy 2.0, openpyxl, React recursive tree UI
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01: Parent revision owns the BOM.** BOM lines belong to a specific parent part revision. Edit on Draft; Release freezes structure (immutable). New revision copies BOM forward.
- **D-02: BOM line references a child PART, resolved at view time to latest Released revision.**
- **D-03: Unreleased children resolve provisionally.** Falls back to latest revision, flagged "unreleased", provisional cost used in roll-up.
- **D-04: BOM line payload** = child part + decimal quantity (NUMERIC) + optional reference designators (free text) + child UoM for context.
- **D-05: Cycles are hard-blocked.** Detect before insert, reject with clear message. Acyclic guarantee at read time.
- **D-06: Single material cost per revision.** One unit material cost on the revision snapshot. No labor/dev-range in v1.
- **D-07: Effective-cost resolution chain:** (1) selected-vendor price-break cost; (2) manually-entered material cost; (3) BOM roll-up of children; (4) uncosted. Manual cost wins over roll-up even on assemblies (purchased sub-assembly case).
- **D-08: Roll-up = Σ(child effective cost × line quantity)** up the tree, per resolution chain at each node.
- **D-09: Margin ungated, on Part Detail.** Any part revision may carry optional sale price; margin and margin % computed when both are set.
- **D-10: Single system currency.** Read from Phase-3 `locale.currency` setting (key confirmed in `settings_seed.py`). No per-line currency.
- **D-11: Full AVL link shape.** FK to `syerp_partner` + vendor part number + preferred flag + notes + qty/cost/lead-days price-break table.
- **D-12: Vendor-driven costing in v1.** Selected vendor + price-break row drives effective cost (D-07 step 1).
- **D-13: `preferred` ≠ `selected-for-costing`.** Two distinct concepts: preferred is a sourcing designation, selected drives cost.
- **D-14: Freeze cost on Release; always show live cost too.** AVL list + price-breaks are part-level/live; selected-vendor+break choice is revision-controlled; effective cost snapshotted as frozen column on release. UI shows both frozen and live cost.
- **D-15: Server-side endpoints for import/export.** FastAPI endpoints; backend owns data; RBAC-gated and audited.
- **D-16: JSON lossless, Excel multi-sheet.** JSON = full lossless round-trip; Excel = human-friendly multi-sheet (Parts, BOMs, AVL) built server-side with openpyxl.
- **D-17: Upsert, never delete.** Import matches on stable keys (part number; BOM by parent-rev + child; AVL by part + vendor), updates or inserts, never hard-deletes.
- **D-18: Preview-then-transactional commit.** Upload → server validates → preview (N new, M updated, K errors) → confirm → all-or-nothing transaction.
- **D-19 (Claude's Discretion):** Exact RBAC split — export `plum:read`, import `plum:write`; audit events `plum.imported`, `plum.exported`.

### Claude's Discretion

- Exact table/column design for `PlumBomItem`, AVL tables, material cost + sale price columns on revision.
- As-released cost snapshot storage (frozen numeric column on revision set at release time).
- Where-used implementation (recursive CTE vs. iterative) and depth/perf guards.
- JSON schema/versioning for lossless export; Excel sheet/column layout.
- Whether system-currency setting is PLUM-scoped or global (align with Phase-3 infra).

### Deferred Ideas (OUT OF SCOPE)

- Labor costing, dev-estimate cost ranges, distributor/multi-tier discounting.
- ECO / engineering-change-order workflow + effectivity dates.
- Revision→revision BOM lines (freeze exact child rev per line).
- Multi-currency + FX conversion.
- BOM tree / where-used / margin screen layouts (owned by UI-spec phase — already delivered in 06-UI-SPEC.md).
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PLUM-04 | User can build a multi-level BOM and view it as an expandable tree | BOM data model (§Standard Stack), recursive CTE patterns (§Architecture Patterns), BomTree component design (§UI patterns) |
| PLUM-05 | User can view a flat BOM with quantity roll-up across levels | Flat-BOM endpoint returning rolled-up totals; server-side recursive accumulation with shared-node qty summing |
| PLUM-06 | User can run where-used analysis to see which assemblies consume a part | Reverse recursive CTE traversal (§Architecture Patterns — Pattern 3) |
| PLUM-07 | User can link a part to one or more vendors from the SYERP vendor list (AVL), and those links are persisted | AVL table design with FK to `syerp_partner`; price-break child table |
| PLUM-08 | User can set part pricing/cost and see cost roll-up across a BOM | Cost columns on `plum_part_revision`; effective-cost resolution chain; roll-up endpoint |
| PLUM-09 | User can view margin analysis for a product | Sale price column on revision; margin computed from effective cost + sale price |
| PLUM-10 | User can import and export PLUM data as JSON and Excel | openpyxl server-side; JSON lossless export; upsert import with preview |
</phase_requirements>

---

## Summary

Phase 6 is a data-model expansion and traversal-algorithm phase sitting on top of the solid Phase-5 PLUM foundation. The primary technical challenges are: (1) designing the BOM + AVL tables correctly so that revision-controlled BOM ownership and part-level AVL data are clearly separated; (2) implementing recursive CTE-based traversal efficiently under async SQLAlchemy 2.0; and (3) building the import/export pipeline (openpyxl + JSON) with preview-then-commit semantics.

The existing codebase provides strong scaffolding. The `plum_part_revision` table (confirmed in `backend/app/modules/plum/models.py`) is the correct attachment point for BOM lines, cost columns, and the selected-vendor/costing-snapshot choice (D-01/D-06/D-14). The `syerp_partner` table (confirmed in `backend/app/modules/syerp/models.py`) is the FK target for AVL links — the first real cross-module foreign key. The system currency already lives in the Phase-3 `locale.currency` setting (confirmed in `settings_seed.py`) — no PLUM-scoped duplicate needed.

The core algorithm insight is that cost roll-up and cycle detection are best implemented in Python application code rather than raw recursive CTEs, because: (a) async SQLAlchemy 2.0's `await conn.execute(text(...))` is required to execute raw CTEs (the ORM `.cte()` helper works but adds ceremony), (b) the dataset is small (manufacturing BOMs rarely exceed a few hundred nodes), and (c) Python recursion with an explicit visited-set is simpler, testable, and matches the prototype's proven `generateFlatBom`/`getRolledUpCost` logic. The planner should use Python-side recursion for BOM traversal.

**Primary recommendation:** Add three new tables (`plum_bom_item`, `plum_avl_link`, `plum_avl_price_break`) plus four new columns on `plum_part_revision` (material_cost, sale_price, selected_vendor_link_id, released_cost_snapshot) in migration 0006; implement traversal in Python service functions; use openpyxl 3.1.5 for Excel export/import.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| BOM tree structure storage | Database / Storage | — | Relational table `plum_bom_item` with FK to revision and part |
| BOM tree traversal (expandable tree, flat BOM, where-used) | API / Backend | — | Recursive Python traversal over DB-loaded edges; returns structured JSON |
| Cycle detection on BOM add | API / Backend | — | Application-level ancestor check before insert; acyclic invariant enforced before commit |
| Effective cost resolution (vendor → manual → roll-up → uncosted) | API / Backend | — | Server computes resolution chain; result returned as part of part-detail response |
| Cost roll-up computation | API / Backend | — | Python recursive accumulation; not stored (computed on demand from live graph) |
| Released cost snapshot | Database / Storage | API triggers | Column `released_cost_snapshot` on `plum_part_revision` set at release time by existing FSM path |
| Live cost recompute (for D-14 dual-cost display) | API / Backend | — | Computed fresh on request; not persisted |
| AVL data persistence | Database / Storage | — | `plum_avl_link` + `plum_avl_price_break` tables (part-level, not revision-controlled) |
| Selected-vendor+break choice | Database / Storage | — | `selected_vendor_link_id` + `selected_price_break_index` on revision (revision-controlled) |
| Import file parsing (JSON + Excel) | API / Backend | — | FastAPI endpoint receives upload; openpyxl/json parses server-side |
| Import preview response | API / Backend | — | Server validates, returns structured diff before commit |
| Import transactional commit | Database / Storage | API controls | Single SQLAlchemy transaction for all upserts |
| Excel export generation | API / Backend | — | openpyxl builds workbook server-side; streamed as response |
| JSON export | API / Backend | — | Python dict serialization of all PLUM tables; streamed as `application/json` |
| BOM tree UI rendering | Browser / Client | — | BomTree.tsx recursive component; expand/collapse local state |
| Flat BOM UI display | Browser / Client | — | Same component, flat mode; reads pre-computed totals from API |
| AVL editor UI | Browser / Client | — | PriceBreakEditor.tsx within Sheet component |
| Cost/margin display | Browser / Client | — | Inline in PartDetail.tsx; cost grid + margin box |
| Import/export UI flow | Browser / Client | — | ImportExport.tsx 3-step flow; file input + preview table + commit |
| Currency symbol display | Browser / Client | — | Read from system settings query; displayed per UI-SPEC D-10 |

---

## Standard Stack

### Core (already installed — no new installs for most of these)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.138.0 | API endpoints for BOM, AVL, cost, import/export | Already in use; locked |
| SQLAlchemy (async) | 2.0.51 | ORM models + async queries | Already in use; confirmed via `.venv/bin/pip show` |
| PostgreSQL | (server) | Relational storage; recursive CTE support | Locked stack |
| asyncpg | 0.31.0 | Async PostgreSQL driver | Already in use; confirmed |
| Alembic | 1.18.4 | Schema migration for new tables | Already in use; single-history convention |
| openpyxl | 3.1.5 | Server-side Excel read/write for PLUM-10 | Confirmed on PyPI; slopcheck [OK]; no Python alternative that handles `.xlsx` read+write without heavier deps (pandas would add ~50 MB) |
| React 18 + TypeScript | 19.2.7 / 6.0.3 | Frontend BOM tree, AVL editor, import/export UI | Already in use; confirmed via package.json |
| TanStack Query | 5.101.1 | Client-side data fetching + cache invalidation | Already in use |
| shadcn/ui (Radix) | (per package.json) | All UI components | Already in use; locked |
| lucide-react | 1.21.0 | Icons (ChevronRight, CheckCircle, etc.) | Already in use |
| sonner | 2.0.7 | Toast notifications | Already in use |

### New packages required

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| openpyxl | 3.1.5 | Excel .xlsx read/write (server-side, PLUM-10) | Only package confirmed [OK] by slopcheck for .xlsx without pandas; permissive MIT-like license (openpyxl license) |
| `@radix-ui/react-tooltip` | (shadcn installs) | BOM tree ref-des tooltip | UI-SPEC: `npx shadcn add tooltip` installs Radix tooltip + shadcn wrapper |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| openpyxl | pandas+xlsxwriter | pandas adds 50 MB+ to the container image; openpyxl is lighter and purpose-built for .xlsx; pandas is overkill for structured-sheet output |
| openpyxl | xlsxwriter (write-only) | xlsxwriter cannot read back imports; openpyxl handles both read and write |
| Python-side BOM recursion | PostgreSQL recursive CTE in raw SQL | CTE is faster for very deep trees but adds significant complexity for async SQLAlchemy; manufacturing BOMs are shallow (3-8 levels typical); Python recursion is simpler, testable, and matches the prototype pattern |
| Python-side BOM recursion | SQLAlchemy `.cte()` ORM helper | `.cte()` with `recursive=True` works but requires careful async execution (`connection.execute(select(...).cte(...))`) — same complexity cost as raw SQL without clarity benefit for this dataset size |
| In-memory cycle check on insert | DB trigger | Application-level check is transparent, testable, and sufficient; no stored procedure complexity |

**Installation (backend):**
```bash
pip install openpyxl==3.1.5
# Add to requirements.txt: openpyxl==3.1.5
```

**Installation (frontend — shadcn tooltip):**
```bash
npx shadcn add tooltip
```

---

## Package Legitimacy Audit

| Package | Registry | Age | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|
| openpyxl | PyPI | ~15 yrs (first release 2010) | [OK] | Approved |
| @radix-ui/react-tooltip | npm | ~4 yrs | Not checked (installed via shadcn official) | Approved — shadcn official registry |

**Packages removed due to [SLOP]:** none
**Packages flagged [SUS]:** none

*slopcheck was available and ran successfully. openpyxl confirmed [OK] on PyPI.*

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (React/TanStack Query)
  |
  |── GET /api/v1/plum/parts/:id      ──► PartDetail.tsx
  |   (returns part + revisions + BOM tree + costs + AVL summary)
  |
  |── GET /api/v1/plum/parts/:id/bom          ──► BOM tree data
  |── GET /api/v1/plum/parts/:id/bom/flat     ──► Flat BOM with rolled-up qty
  |── GET /api/v1/plum/parts/:id/where-used   ──► Direct + indirect parents
  |── GET /api/v1/plum/parts/:id/avl          ──► AVL link list
  |── POST /api/v1/plum/parts/:id/bom         ──► Add BOM line (Draft only)
  |── PATCH /api/v1/plum/parts/:id/bom/:line  ──► Edit BOM line (Draft only)
  |── DELETE /api/v1/plum/parts/:id/bom/:line ──► Remove BOM line (Draft only)
  |── POST /api/v1/plum/parts/:id/avl         ──► Add vendor link
  |── PATCH /api/v1/plum/parts/:id/avl/:link  ──► Edit vendor link
  |── DELETE /api/v1/plum/parts/:id/avl/:link ──► Remove vendor link
  |── PATCH /api/v1/plum/parts/:rev_id/cost   ──► Save material_cost + sale_price
  |
  |── GET /api/v1/plum/export/json     ──► StreamingResponse (application/json)
  |── GET /api/v1/plum/export/excel    ──► StreamingResponse (xlsx)
  |── POST /api/v1/plum/import/preview ──► Validation result (N new, M updated, K errors)
  |── POST /api/v1/plum/import/commit  ──► All-or-nothing upsert transaction
  |
FastAPI / SQLAlchemy 2.0 (async)
  |
  |── plum/service.py: BOM traversal, cycle detection, cost roll-up
  |── plum/service.py: AVL CRUD, import/export logic
  |── plum/router.py: endpoints, RBAC gates, audit events
  |
PostgreSQL
  ├── plum_part              (Phase 5 — unchanged)
  ├── plum_part_revision     (Phase 5 + 4 new columns in 0006)
  │     + material_cost      NUMERIC(12,4) nullable
  │     + sale_price         NUMERIC(12,4) nullable
  │     + released_cost_snapshot  NUMERIC(12,4) nullable (frozen at release)
  │     + selected_vendor_link_id  String FK → plum_avl_link (nullable)
  │     + selected_price_break_index  Integer nullable
  ├── plum_bom_item          (new in 0006)
  ├── plum_avl_link          (new in 0006)
  └── plum_avl_price_break   (new in 0006)
```

### Recommended Project Structure

New and modified files in Phase 6:

```
backend/
├── alembic/versions/
│   └── 0006_plum_bom_costing.py        # new — adds BOM/AVL/cost tables+columns
├── app/modules/plum/
│   ├── models.py                        # extend: PlumBomItem, PlumAvlLink, PlumAvlPriceBreak
│   │                                    # extend PlumPartRevision: 5 new columns
│   ├── schemas.py                       # extend: BomItemRead/Create/Update,
│   │                                    #   AvlLinkRead/Create, PriceBreakRead/Create,
│   │                                    #   CostUpdate, ImportPreviewResponse,
│   │                                    #   BomTreeNode, FlatBomRow, WhereUsedRow
│   ├── service.py                       # extend: BOM CRUD + traversal, AVL CRUD,
│   │                                    #   cost roll-up, cycle detection,
│   │                                    #   import/export logic
│   └── router.py                        # extend: BOM endpoints, AVL endpoints,
│                                        #   cost endpoint, import/export endpoints

frontend/src/routes/plum/
├── PartDetail.tsx                       # extend: 4 new Card sections
├── ImportExport.tsx                     # new — 3-step import/export page
├── components/
│   ├── PlumNav.tsx                      # extend: add Import/Export tab
│   ├── BomTree.tsx                      # new — recursive tree + flat view
│   ├── BomLineSheet.tsx                 # new — add/edit BOM line Sheet
│   ├── PriceBreakEditor.tsx             # new — inline editable price-break rows
│   └── AvlLinkSheet.tsx                 # new — add/edit AVL vendor link Sheet
```

---

### Pattern 1: BOM Data Model — Three New Tables + Revision Columns

**What:** The full Phase-6 schema extension in one migration (0006).

**Table design:**

```python
# plum_bom_item — one row per BOM line (parent revision → child part)
class PlumBomItem(Base):
    __tablename__ = "plum_bom_item"

    id: Mapped[str]                    # UUID PK
    parent_revision_id: Mapped[str]    # FK → plum_part_revision.id
    child_part_id: Mapped[str]         # FK → plum_part.id (resolved at view time)
    quantity: Mapped[Decimal]          # NUMERIC(12,4) — supports 0.001 to 99999999
    reference_designators: Mapped[str | None]  # String(500) — free text e.g. "R1,C4"
    sort_order: Mapped[int]            # Integer — display order; default 0
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    # Unique: a parent revision cannot have the same child twice
    # __table_args__ = (UniqueConstraint("parent_revision_id", "child_part_id"),)

# plum_avl_link — one row per part↔vendor link (part-level, NOT revision)
class PlumAvlLink(Base):
    __tablename__ = "plum_avl_link"

    id: Mapped[str]                    # UUID PK
    part_id: Mapped[str]               # FK → plum_part.id
    vendor_id: Mapped[str]             # FK → syerp_partner.id (is_vendor=True)
    vendor_part_number: Mapped[str | None]  # String(100) — supplier catalog ref
    preferred: Mapped[bool]            # sourcing preference flag (D-13)
    notes: Mapped[str | None]          # Text
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]

    # Unique: one link per part+vendor
    # __table_args__ = (UniqueConstraint("part_id", "vendor_id"),)

# plum_avl_price_break — child rows of plum_avl_link
class PlumAvlPriceBreak(Base):
    __tablename__ = "plum_avl_price_break"

    id: Mapped[str]                    # UUID PK
    avl_link_id: Mapped[str]           # FK → plum_avl_link.id (ON DELETE CASCADE)
    qty_threshold: Mapped[int]         # minimum quantity for this price tier
    unit_cost: Mapped[Decimal]         # NUMERIC(12,4)
    lead_days: Mapped[int | None]      # Integer lead time in days
    sort_order: Mapped[int]            # row index; sorted by qty ascending on save

# PlumPartRevision — 5 new columns added in 0006 (ALTER TABLE)
# material_cost NUMERIC(12,4) nullable
# sale_price NUMERIC(12,4) nullable
# released_cost_snapshot NUMERIC(12,4) nullable  ← set at release time
# selected_vendor_link_id String(36) FK → plum_avl_link.id nullable
# selected_price_break_index Integer nullable (index into the vendor's price_break list)
```

**Critical design notes:**
- `plum_avl_link` is PART-level (no `revision_id`) — the AVL list is live data that applies to the part across all revisions (D-11).
- `selected_vendor_link_id` + `selected_price_break_index` are on `plum_part_revision` — revision-controlled (D-14).
- `released_cost_snapshot` is set by the existing `advance_revision_status` service function at the moment `target_status == "released"` (hooks into the existing release path in service.py line ~765).
- `quantity` uses `NUMERIC(12,4)` (not `FLOAT`) to avoid floating-point representation errors in cost multiplication.
- `plum_avl_price_break` uses `ON DELETE CASCADE` from its parent `plum_avl_link` row so link removal also removes price breaks in one operation.
- Migration 0006 `down_revision = "0005"` — chains correctly onto the single Alembic history.

### Pattern 2: BOM Traversal — Python-Side Recursion (Recommended over raw CTE)

**What:** Three traversal functions in `service.py` — BOM tree, flat BOM with rolled-up qty, and where-used.

**When to use:** All BOM/flat/where-used traversal in Phase 6. Python-side is recommended over raw CTE for this project because:
1. The dataset is small (manufacturing BOMs: typically 3-8 levels, rarely >200 nodes).
2. Async SQLAlchemy 2.0 requires `await conn.execute(text("WITH RECURSIVE ..."))` or `.execute(select(...).cte(recursive=True))` for raw CTEs — significant ceremony for uncertain gain.
3. Python recursion with a visited set is directly testable without a live DB.
4. The prototype's `generateFlatBom` and `getRolledUpCost` (plm_v54.html lines ~3894, ~3724) use exactly this pattern successfully.

**BOM tree traversal:**

```python
# Source: derived from prototype getWhereUsed/generateFlatBom pattern
async def load_bom_tree(
    db: AsyncSession,
    revision_id: str,
    visited: set[str] | None = None,
) -> list[dict]:
    """
    Recursively load BOM lines for a revision, resolved to latest child revisions.
    Returns a nested list of dicts suitable for tree serialization.
    visited: set of revision_ids already visited — prevents cycles at read time
             (cycles are blocked at insert, but visited guard is defensive).
    """
    if visited is None:
        visited = set()
    if revision_id in visited:
        return []
    visited.add(revision_id)

    # Load direct children for this revision
    items_result = await db.execute(
        select(PlumBomItem)
        .where(PlumBomItem.parent_revision_id == revision_id)
        .order_by(PlumBomItem.sort_order, PlumBomItem.created_at)
    )
    items = list(items_result.scalars().all())

    tree = []
    for item in items:
        child_rev = await _resolve_child_revision(db, item.child_part_id)
        child_bom = await load_bom_tree(db, child_rev.id, visited.copy()) if child_rev else []
        tree.append({
            "bom_item_id": item.id,
            "child_part_id": item.child_part_id,
            "child_part_number": ...,
            "child_revision_label": child_rev.revision_label if child_rev else None,
            "child_revision_status": child_rev.status if child_rev else None,
            "quantity": float(item.quantity),
            "reference_designators": item.reference_designators,
            "effective_cost": await _compute_effective_cost(db, child_rev) if child_rev else None,
            "children": child_bom,
        })
    return tree
```

**Flat BOM (rolled-up quantities):**

```python
# Accumulate all leaf/assembly parts with multiplied quantities across all paths
async def load_flat_bom(
    db: AsyncSession,
    revision_id: str,
    multiplier: Decimal = Decimal("1"),
    acc: dict[str, dict] | None = None,
    visited: set[str] | None = None,
) -> list[dict]:
    """
    Returns list of {child_part_id, part_number, total_qty, unit_cost, extended_cost}.
    total_qty = sum of (multiplier × line_qty) across all paths to this part.
    Matches prototype generateFlatBom pattern (plm_v54.html ~3894).
    """
```

**Where-used (reverse traversal):**

```python
async def get_where_used(
    db: AsyncSession,
    part_id: str,
    depth: int = 0,
    max_depth: int = 20,
    visited_part_ids: set[str] | None = None,
) -> list[dict]:
    """
    Find all revisions whose BOM contains part_id (direct or indirect).
    Returns [{parent_part_id, parent_part_number, parent_rev_label,
              parent_rev_status, relationship: 'direct'|'indirect',
              via_part_number: str|None}]
    Sorted: direct first, then indirect breadth-first per UI-SPEC.
    max_depth: guard against pathologically deep graphs.
    """
```

**PostgreSQL recursive CTE option (if needed for performance later):**

```python
# If Python recursion proves too slow for large datasets (unlikely for v1),
# the raw CTE pattern for async SQLAlchemy 2.0 is:
from sqlalchemy import text
async with db.connection() as conn:
    result = await conn.execute(text("""
        WITH RECURSIVE bom_tree AS (
            SELECT bi.id, bi.parent_revision_id, bi.child_part_id,
                   bi.quantity, 1 as depth
            FROM plum_bom_item bi
            WHERE bi.parent_revision_id = :revision_id
            UNION ALL
            SELECT bi.id, bi.parent_revision_id, bi.child_part_id,
                   bt.quantity * bi.quantity, bt.depth + 1
            FROM plum_bom_item bi
            JOIN bom_tree bt ON bi.parent_revision_id = (
                SELECT r.id FROM plum_part_revision r
                WHERE r.part_id = bi.child_part_id
                ORDER BY r.revision_number DESC LIMIT 1
            )
            WHERE bt.depth < 20
        )
        SELECT * FROM bom_tree
    """), {"revision_id": revision_id})
```

Note: The `AsyncSession.execute(text(...))` path requires obtaining a connection via `async with db.connection() as conn` in SQLAlchemy 2.0 for raw SQL CTEs. [VERIFIED: SQLAlchemy 2.0 docs — async sessions]

### Pattern 3: Cycle Detection on BOM Add

**What:** Application-level ancestor check before inserting a BOM line.

**Algorithm:**

```python
async def _would_create_cycle(
    db: AsyncSession,
    parent_revision_id: str,
    proposed_child_part_id: str,
) -> bool:
    """
    Return True if adding proposed_child_part_id as a child of parent_revision_id
    would create a cycle.

    A cycle exists if proposed_child_part_id is an ANCESTOR of the part that
    owns parent_revision_id. Walk up the BOM graph from the parent part's id.

    Algorithm: BFS/DFS upward from parent part through all revisions where
    the parent's own part is used as a child. If we reach proposed_child_part_id,
    it would be a cycle.
    """
    # Load the part that owns parent_revision_id
    rev = await get_revision(db, parent_revision_id)
    parent_part_id = rev.part_id

    # Check: is proposed_child_part_id the same as the parent part? (direct self-loop)
    if proposed_child_part_id == parent_part_id:
        return True

    # BFS: find all ancestor parts of parent_part_id
    visited = {parent_part_id}
    queue = [parent_part_id]

    while queue:
        current_part_id = queue.pop(0)
        # Find all revisions of current_part_id that appear as children in any BOM
        # (i.e., find which parts have current_part_id in their BOM)
        result = await db.execute(
            select(PlumBomItem.parent_revision_id)
            .where(PlumBomItem.child_part_id == current_part_id)
        )
        ancestor_rev_ids = [r[0] for r in result.all()]
        for rev_id in ancestor_rev_ids:
            rev_result = await db.execute(
                select(PlumPartRevision.part_id).where(PlumPartRevision.id == rev_id)
            )
            ancestor_part_id = rev_result.scalar()
            if ancestor_part_id == proposed_child_part_id:
                return True
            if ancestor_part_id and ancestor_part_id not in visited:
                visited.add(ancestor_part_id)
                queue.append(ancestor_part_id)

    return False
```

**HTTP response on cycle detected:**

```python
raise HTTPException(
    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    detail=f"Adding {child_part_number} here would create a circular BOM. Choose a different part."
)
```

### Pattern 4: Effective Cost Resolution Chain (D-07)

**What:** The priority-ordered cost computation for a given revision.

```python
async def compute_effective_cost(
    db: AsyncSession,
    revision: PlumPartRevision,
) -> tuple[Decimal | None, str]:
    """
    Returns (cost_value, source_label) per D-07 resolution chain:
    1. selected-vendor price-break cost  → source = "vendor price"
    2. manually-entered material_cost    → source = "manual"
    3. BOM roll-up of children           → source = "roll-up"
    4. uncosted                          → source = "uncosted", value = None
    """
    # Step 1: selected vendor price-break
    if revision.selected_vendor_link_id and revision.selected_price_break_index is not None:
        pb_result = await db.execute(
            select(PlumAvlPriceBreak)
            .where(PlumAvlPriceBreak.avl_link_id == revision.selected_vendor_link_id)
            .order_by(PlumAvlPriceBreak.sort_order)
        )
        breaks = list(pb_result.scalars().all())
        if 0 <= revision.selected_price_break_index < len(breaks):
            return (breaks[revision.selected_price_break_index].unit_cost, "vendor price")

    # Step 2: manual material_cost
    if revision.material_cost is not None:
        return (revision.material_cost, "manual")

    # Step 3: BOM roll-up (if this revision has children)
    bom_items = await _load_direct_bom_items(db, revision.id)
    if bom_items:
        total = Decimal("0")
        for item in bom_items:
            child_rev = await _resolve_child_revision(db, item.child_part_id)
            if child_rev:
                child_cost, _ = await compute_effective_cost(db, child_rev)
                if child_cost is not None:
                    total += child_cost * item.quantity
        return (total, "roll-up")

    # Step 4: uncosted
    return (None, "uncosted")
```

**Live vs. frozen cost (D-14):**

```python
# On release, snapshot the current effective cost:
# (inside advance_revision_status, after target_status == "released")
frozen_cost, _ = await compute_effective_cost(db, revision)
revision.released_cost_snapshot = frozen_cost

# For display: compute live cost fresh, compare to frozen
live_cost, live_source = await compute_effective_cost(db, revision)
frozen_cost = revision.released_cost_snapshot
# Return both in the API response so the UI can show the D-14 notice
```

### Pattern 5: Import Preview + Transactional Commit (D-18)

**What:** Two-endpoint import flow — preview then commit.

```python
# POST /plum/import/preview
# Accepts multipart file upload (UploadFile)
# Parses JSON or Excel into memory
# Validates all rows WITHOUT writing to DB
# Returns ImportPreviewResponse

class ImportPreviewResponse(BaseModel):
    session_token: str         # opaque token identifying the parsed data (store in server memory or temp)
    new_count: int
    updated_count: int
    errors: list[ImportError]  # row, field, message

class ImportError(BaseModel):
    row: int
    field: str
    message: str

# POST /plum/import/commit
# Body: {"session_token": "..."}
# Re-reads the validated data and applies in ONE transaction
# Returns ImportCommitResponse: {new_count, updated_count}
```

**Implementation note:** For simplicity in v1, re-parse the file on commit rather than caching parsed data server-side. The user experience is: upload file → preview (validation results) → confirm → upload file is re-parsed and committed. This avoids server-side session storage. Alternative: include the parsed data payload directly in the commit request body (JSON import can simply re-send the JSON; Excel import can re-upload or pass a server-side temp path). Recommendation: re-upload on commit — keeps the server stateless. Planner should choose based on simplicity preference.

**Upsert logic (D-17):**

```python
# Stable keys:
# Parts: part_number
# BOM lines: (parent_revision_id, child_part_id) — resolved by part_number + revision_label
# AVL links: (part_id, vendor_id) — resolved by part_number + vendor code
# Price breaks: replace all price breaks for a link on AVL upsert

# Pattern: select-then-insert-or-update (matches existing Phase 4/5 seed pattern)
existing = await db.execute(select(PlumPart).where(PlumPart.part_number == row["part_number"]))
part = existing.scalars().first()
if part is None:
    db.add(PlumPart(...))
    new_count += 1
else:
    # update fields
    updated_count += 1
# Never delete
```

**Excel sheet layout (D-16):**

```
Workbook sheets:
  "Parts" — part_number, description, category, unit_of_measure, tags, notes
  "BOMs"  — parent_part_number, parent_revision_label, child_part_number, quantity, reference_designators
  "AVL"   — part_number, vendor_code, vendor_part_number, preferred, notes,
             pb_qty_threshold, pb_unit_cost, pb_lead_days
             (AVL + price-breaks denormalized — one row per price break, repeated vendor fields)
```

**JSON schema (D-16):**

```json
{
  "schema_version": 1,
  "exported_at": "ISO8601",
  "parts": [
    {
      "part_number": "P00001",
      "active": true,
      "tags": ["Purchased"],
      "revisions": [
        {
          "revision_label": "A",
          "revision_number": 1,
          "status": "released",
          "description": "...",
          "material_cost": "12.5000",
          "sale_price": null,
          "released_cost_snapshot": "12.5000",
          "selected_vendor_link_id": null,
          "selected_price_break_index": null,
          "bom": [
            {"child_part_number": "P00002", "quantity": "2.0000", "reference_designators": "R1,R2"}
          ]
        }
      ],
      "avl": [
        {
          "vendor_code": "V-0001",
          "vendor_part_number": "CAP-100",
          "preferred": true,
          "notes": null,
          "price_breaks": [
            {"qty_threshold": 1, "unit_cost": "12.5000", "lead_days": 14}
          ]
        }
      ]
    }
  ]
}
```

**schema_version** field allows the importer to validate compatibility. Start at 1; increment on breaking schema changes.

### Pattern 6: openpyxl Usage (Server-Side Excel)

```python
# Source: openpyxl 3.1.5 official docs — confirmed via pip index versions
import openpyxl
from io import BytesIO
from fastapi.responses import StreamingResponse

# Export
def generate_excel_export(data: dict) -> bytes:
    wb = openpyxl.Workbook()
    ws_parts = wb.active
    ws_parts.title = "Parts"
    ws_parts.append(["Part Number", "Description", "Category", "UoM", "Tags", "Notes"])
    for part in data["parts"]:
        ws_parts.append([part["part_number"], ...])

    ws_boms = wb.create_sheet("BOMs")
    ws_boms.append(["Parent Part", "Parent Rev", "Child Part", "Quantity", "Ref Des"])
    # ... populate

    ws_avl = wb.create_sheet("AVL")
    ws_avl.append(["Part Number", "Vendor Code", "Vendor Part #", "Preferred", ...])
    # ... populate

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()

# Stream as download
return StreamingResponse(
    iter([excel_bytes]),
    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    headers={"Content-Disposition": "attachment; filename=plum-export.xlsx"}
)

# Import parsing
def parse_excel_import(file_bytes: bytes) -> dict:
    wb = openpyxl.load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
    parts_sheet = wb["Parts"]
    bom_sheet = wb["BOMs"]
    avl_sheet = wb["AVL"]
    # iterate rows[1:] (skip header)
    rows = list(parts_sheet.iter_rows(min_row=2, values_only=True))
    ...
```

### Pattern 7: Copy-Forward of BOM on New Revision

**What:** When `create_revision` is called (Phase 5 service.py ~line 613), the BOM of the source revision must be copied forward to the new Draft revision.

**Location:** Extend `create_revision()` in `service.py` — after the new `PlumPartRevision` row is created, query `plum_bom_item` rows for the source revision and insert them with `parent_revision_id = new_revision.id`.

```python
# After creating new_revision and await db.flush() (to get new_revision.id):
bom_items_result = await db.execute(
    select(PlumBomItem).where(PlumBomItem.parent_revision_id == source.id)
)
for item in bom_items_result.scalars().all():
    db.add(PlumBomItem(
        id=str(uuid.uuid4()),
        parent_revision_id=new_revision.id,
        child_part_id=item.child_part_id,
        quantity=item.quantity,
        reference_designators=item.reference_designators,
        sort_order=item.sort_order,
    ))
# cost fields (material_cost, sale_price, selected_vendor_link_id, etc.) are
# also copied forward from source revision — same pattern as description/category
```

**Note:** `selected_vendor_link_id` should be copied forward ONLY if the referenced AVL link still exists and is active. Defensive null-check on copy is safer than assuming the link persists.

### Pattern 8: RBAC + Audit Pattern (Mirrors Existing)

All new endpoints follow the established pattern from `router.py`:

```python
@router.post("/parts/{part_id}/bom", ...)
async def add_bom_line(
    part_id: str,
    data: BomItemCreate,
    current_user = Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
):
    # business logic
    await write_audit(db, actor_id=str(current_user.id), action="bom.line_added",
                      target_type="bom_item", target_id=str(new_item.id),
                      detail=f"Added {child_part_number} to BOM of rev {rev_label}")
```

**Audit actions for Phase 6:**

| Action | Trigger |
|--------|---------|
| `bom.line_added` | POST bom line |
| `bom.line_updated` | PATCH bom line |
| `bom.line_removed` | DELETE bom line |
| `avl.link_added` | POST avl link |
| `avl.link_updated` | PATCH avl link |
| `avl.link_removed` | DELETE avl link |
| `part.cost_updated` | PATCH revision cost |
| `plum.exported` | GET export endpoint |
| `plum.imported` | POST import commit |

### Anti-Patterns to Avoid

- **Don't store roll-up cost as a cached column on revision.** Cost roll-up is computed on demand. Caching it creates invalidation complexity (any change to a child's cost or any BOM structural change would require invalidating all ancestor revisions). The dataset is small enough that on-demand computation is fast.
- **Don't use ORM relationships on new models.** The existing codebase explicitly avoids ORM relationships (`lazy="selectin"` requirement for async — MissingGreenlet pitfall). All new models must follow the same pattern: no `relationship()` declarations; use explicit `select()` queries in service functions.
- **Don't allow BOM edits on Released revisions.** All BOM-mutating endpoints must check `revision.status == "draft"` and return 422 if not. Mirrors the Phase-5 immutability pattern.
- **Don't use Python `float` for cost arithmetic.** Use `Decimal` from the `decimal` module for all cost calculations. `float` precision errors compound in multiplication (e.g., `0.1 * 3` is not exactly `0.3` in float). NUMERIC(12,4) in Postgres maps to Python `Decimal` via asyncpg.
- **Don't hard-delete on import.** D-17 is explicit: import never hard-deletes. Enforce this with a comment in the import service function and a test.
- **Don't skip `await db.flush()` between revenue-revision cycle.** When the release path sets `released_cost_snapshot`, it hooks into an existing `db.flush()` already present in `advance_revision_status` (the supersede flush at line ~769). The snapshot assignment should happen BEFORE the flush that updates `revision.status = "released"`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Excel .xlsx read/write | Custom CSV parser / manual XML manipulation | openpyxl 3.1.5 | xlsx is a zip of XML files; openpyxl handles encoding, cell types, multiple sheets |
| Numeric precision in cost arithmetic | Python `float` math | Python `Decimal` + `NUMERIC(12,4)` in Postgres | float accumulates rounding errors; Decimal is exact for fixed-point |
| File upload handling | Manual multipart parsing | `python-multipart` (already installed) + FastAPI `UploadFile` | FastAPI natively supports `UploadFile` param when `python-multipart` is installed |
| shadcn Tooltip | Custom CSS tooltip | `npx shadcn add tooltip` | Radix Tooltip handles focus/keyboard/ARIA correctly |
| Recursive tree component | Complex imperative DOM code | Simple recursive React component (`BomTree.tsx`) | React handles tree diffing; local `useState` for expand/collapse is sufficient |
| RBAC on new endpoints | Ad-hoc permission checks | `require_permission("plum:read"|"plum:write")` dependency | Already wired via `Depends()` in existing endpoints |

**Key insight:** The hardest parts of this phase are algorithm-level (BOM traversal, cycle detection, effective-cost chain) — not infrastructure-level. All infrastructure (auth, RBAC, audit, ORM, migration) already exists and must simply be reused.

---

## Common Pitfalls

### Pitfall 1: ORM Relationships and MissingGreenlet
**What goes wrong:** Adding `relationship()` to new models without `lazy="selectin"` causes `MissingGreenlet` errors at runtime in async context.
**Why it happens:** SQLAlchemy's default lazy loading issues a blocking sync DB call, which fails in the async event loop.
**How to avoid:** Follow the explicit comment in `plum/models.py` line 105-108: do NOT declare ORM relationships. Use explicit `select()` queries in service functions.
**Warning signs:** `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called` in stack traces.

### Pitfall 2: `float` vs `Decimal` in Cost Calculations
**What goes wrong:** Cost roll-up accumulates floating-point rounding errors, producing values like `$12.300000000000001` instead of `$12.30`.
**Why it happens:** Python `float` is IEEE 754 binary floating-point, not decimal.
**How to avoid:** Use `from decimal import Decimal` everywhere cost arithmetic appears. asyncpg returns PostgreSQL `NUMERIC` columns as Python `Decimal` automatically.
**Warning signs:** Cost display shows more than 4 decimal places, or two `Decimal` values that should be equal compare as unequal.

### Pitfall 3: BOM Edit Without Draft Check
**What goes wrong:** A Released revision's BOM is mutated, violating the freeze-on-release invariant (D-01).
**Why it happens:** Forgetting to check `revision.status == "draft"` in BOM-mutating endpoints.
**How to avoid:** Every BOM-mutating endpoint loads the parent revision and raises 422 if not Draft. Mirrors Phase-5 `update_part` pattern (service.py line ~506).
**Warning signs:** BOM changes appear on Released revisions without creating a new revision.

### Pitfall 4: Cross-Module FK Without Active Guard
**What goes wrong:** An AVL link points to an archived (`active=False`) vendor, and the vendor's data is silently excluded from list queries.
**Why it happens:** The `syerp_partner` table uses soft-delete (`active=False`). BOM/AVL queries that join `syerp_partner` may filter on `active=True` and drop the vendor.
**How to avoid:** AVL link creation should warn if vendor is archived but still allow the link (the link persists even if the vendor is later archived). AVL-read queries should return the vendor even if archived (include archived vendors in the join — do NOT filter `active=True` when loading existing links).
**Warning signs:** Existing AVL entries disappear from the list after a vendor is archived.

### Pitfall 5: Cycle Detection Race Condition
**What goes wrong:** Two concurrent requests both pass the cycle check and insert conflicting BOM lines that together create a cycle.
**Why it happens:** The cycle check is application-level, not DB-enforced.
**How to avoid:** For v1, accept this theoretical race (small dataset, low concurrency, single-user typical). The DB-level protection is the `UniqueConstraint("parent_revision_id", "child_part_id")` which prevents duplicate lines; a cycle would require two separately-valid non-duplicate lines that together form a cycle, requiring exact simultaneous requests. Flag this as a known limitation. If needed in v2, a DB trigger or serializable transaction level can enforce acyclicity.
**Warning signs:** Cycle at read time causes infinite recursion — the `visited` set guard in traversal functions prevents infinite loops even if a cycle exists.

### Pitfall 6: Import Preview Without Validation of Cross-References
**What goes wrong:** Import preview passes validation, but commit fails because a BOM row references a part_number that doesn't exist in PLUM yet (and the import file includes that part in the same upload).
**Why it happens:** Import validation checks references against the CURRENT database state, not against the OTHER rows being imported.
**How to avoid:** Two-pass validation in the preview step: (1) collect all part_numbers declared in the file; (2) when validating BOM rows, check against DB UNION file-declared parts. Similarly for AVL vendor_code: check DB `syerp_partner` — vendors referenced in AVL MUST already exist in SYERP (per D-18: "referenced vendors not in SYERP" is an import error).
**Warning signs:** Import preview shows 0 errors but commit fails with FK constraint violations.

### Pitfall 7: `selected_price_break_index` Out of Bounds After Price-Break Edit
**What goes wrong:** A revision has `selected_price_break_index = 2` but someone edits the AVL price breaks and now only 2 rows exist (indices 0, 1). The index 2 is now out of bounds.
**Why it happens:** The selected index is a positional index into a mutable list of price breaks.
**How to avoid:** When loading effective cost: always bounds-check `selected_price_break_index` against the actual length of the price-break list; if out of bounds, fall through to the next resolution step (manual cost). Show a warning in the UI when the selected break is missing.
**Warning signs:** Effective cost computation silently skips to "manual" or "uncosted" after price breaks are edited.

### Pitfall 8: Flat BOM Shared Sub-Assembly Quantity Accumulation
**What goes wrong:** If part P00010 appears in two different branches of the BOM (e.g., used in both sub-assembly A and sub-assembly B), the flat BOM should show the TOTAL quantity (qty_in_A + qty_in_B), not two separate rows.
**Why it happens:** A naive recursive flat-BOM function appends a new row for each path.
**How to avoid:** Use a dict keyed by `child_part_id` as the accumulator; add quantities rather than appending rows. This matches the prototype `generateFlatBom` pattern (plm_v54.html ~3900-3924): `if (existing) { existing.qty += parentQty } else { results.push(...) }`.
**Warning signs:** Flat BOM shows duplicate part rows with separate quantities instead of one row with summed quantity.

---

## Code Examples

### Add New Models to core/models.py Aggregator

```python
# backend/app/core/models.py — add after existing plum_models import:
from app.modules.plum import models as plum_models  # noqa: F401
# plum_models now includes PlumBomItem, PlumAvlLink, PlumAvlPriceBreak
# No additional import line needed IF they are in the same plum/models.py file
```

### Migration 0006 Pattern (ALTER TABLE + new tables)

```python
# backend/alembic/versions/0006_plum_bom_costing.py
revision: str = "0006"
down_revision: str = "0005"

def upgrade() -> None:
    # 1. Add columns to plum_part_revision (ALTER TABLE)
    op.add_column("plum_part_revision",
        sa.Column("material_cost", sa.Numeric(12, 4), nullable=True))
    op.add_column("plum_part_revision",
        sa.Column("sale_price", sa.Numeric(12, 4), nullable=True))
    op.add_column("plum_part_revision",
        sa.Column("released_cost_snapshot", sa.Numeric(12, 4), nullable=True))
    op.add_column("plum_part_revision",
        sa.Column("selected_vendor_link_id", sa.String(36), nullable=True))
    op.add_column("plum_part_revision",
        sa.Column("selected_price_break_index", sa.Integer(), nullable=True))

    # 2. Create plum_bom_item
    op.create_table("plum_bom_item", ...)

    # 3. Create plum_avl_link
    op.create_table("plum_avl_link", ...)

    # 4. Create plum_avl_price_break
    op.create_table("plum_avl_price_break", ...)

    # 5. Add FK constraint from plum_part_revision.selected_vendor_link_id
    #    → plum_avl_link.id (deferrable — avl_link may not exist yet at migration time)
    op.create_foreign_key(
        "fk_plum_revision_selected_avl_link",
        "plum_part_revision", "plum_avl_link",
        ["selected_vendor_link_id"], ["id"],
        ondelete="SET NULL"
    )
```

**Critical:** The FK from `plum_part_revision.selected_vendor_link_id → plum_avl_link.id` should use `ondelete="SET NULL"` so that deleting an AVL link automatically clears the selection on Draft revisions, rather than blocking the delete or orphaning the reference.

### System Currency Access Pattern

```python
# Read locale.currency from the global settings table (D-10)
# Same pattern as _get_revision_scheme() in service.py
async def _get_system_currency(db: AsyncSession) -> str:
    from app.core.settings_model import Setting
    result = await db.execute(
        select(Setting.value).where(
            Setting.key == "locale.currency",
            Setting.owner_id.is_(None),
        )
    )
    return result.scalar() or "USD"
```

**Confirmed:** `locale.currency` key exists in `settings_seed.py` with default `"USD"`. No new setting needed.

### FastAPI File Upload for Import

```python
# [ASSUMED] Standard FastAPI UploadFile pattern
from fastapi import UploadFile, File

@router.post("/import/preview", response_model=ImportPreviewResponse)
async def import_preview(
    file: UploadFile = File(...),
    current_user = Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    if file.filename.endswith(".json"):
        data = parse_json_import(content)
    elif file.filename.endswith(".xlsx"):
        data = parse_excel_import(content)
    else:
        raise HTTPException(422, "Unsupported file type. Use .json or .xlsx")
    preview = await validate_import(db, data)
    return preview
```

`python-multipart==0.0.32` is already in `requirements.txt` — UploadFile works immediately.

---

## Runtime State Inventory

Phase 6 adds new tables and columns but does not rename anything. There is no runtime state migration needed. Specific inventory:

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | No existing BOM, AVL, or cost data (these tables don't exist yet) | None — new tables |
| Live service config | No external service carries BOM/cost configuration | None |
| OS-registered state | None | None |
| Secrets/env vars | No new secrets needed | None |
| Build artifacts | `frontend/dist` may be stale (built in Phase 1, updated through Phases 3-5) | Rebuild `frontend/dist` + container image after frontend work |

**Nothing found in category (verified):** Stored data for BOM/cost does not exist — Phase 5 migration (`0005_plum_tables.py`) confirms no cost/BOM columns were added. Runtime state inventory is clean.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | Data layer | ✓ (via Podman) | (server) | — |
| asyncpg | SQLAlchemy async driver | ✓ | 0.31.0 | — |
| openpyxl | Excel import/export | ✗ (not yet installed) | 3.1.5 on PyPI | No fallback — must install |
| python-multipart | FastAPI UploadFile | ✓ | 0.0.32 | — |
| shadcn Tooltip | BOM tree ref-des hover | ✗ (not yet installed) | (via npx shadcn) | Could use `title` attr only, but UI-SPEC requires Tooltip |
| Node.js / npm | Frontend build | ✓ | (present) | — |

**Missing dependencies with no fallback:**
- `openpyxl` must be added to `requirements.txt` and installed (`pip install openpyxl==3.1.5`) before Excel import/export endpoints can be tested.
- `shadcn Tooltip` must be installed (`npx shadcn add tooltip`) before BomTree ref-des hover is implementable.

**Missing dependencies with fallback:**
- None.

---

## Validation Architecture

**Nyquist validation:** Enabled (`workflow.nyquist_validation: true` in `.planning/config.json`).

### Test Framework

| Property | Value |
|----------|-------|
| Backend framework | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| Backend config | `backend/pyproject.toml` (inferred from existing test collection) |
| Backend quick run | `cd backend && .venv/bin/pytest tests/plum/ -x -q` |
| Backend full suite | `cd backend && .venv/bin/pytest tests/ -x -q` |
| Frontend framework | vitest 4.1.9 + @testing-library/react |
| Frontend config | `frontend/vite.config.ts` (`test.environment: 'jsdom'`) |
| Frontend quick run | `cd frontend && npm test -- --run src/routes/plum/` |
| Frontend full suite | `cd frontend && npm test -- --run` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File |
|--------|----------|-----------|-------------------|------|
| PLUM-04 | POST BOM line → 201, child appears in GET bom response | integration | `pytest tests/plum/test_bom.py::test_add_bom_line -x` | Wave 0 gap |
| PLUM-04 | BOM line on Released revision → 422 | integration | `pytest tests/plum/test_bom.py::test_bom_line_released_immutable -x` | Wave 0 gap |
| PLUM-04 | Adding a cycle → 422 with cycle message | integration | `pytest tests/plum/test_bom.py::test_bom_cycle_detection -x` | Wave 0 gap |
| PLUM-05 | GET /bom/flat returns qty-summed rows for shared sub-assembly | integration | `pytest tests/plum/test_bom.py::test_flat_bom_shared_part -x` | Wave 0 gap |
| PLUM-06 | GET /where-used returns direct + indirect parents | integration | `pytest tests/plum/test_bom.py::test_where_used_indirect -x` | Wave 0 gap |
| PLUM-07 | POST AVL link → 201; GET avl returns link | integration | `pytest tests/plum/test_avl.py::test_add_avl_link -x` | Wave 0 gap |
| PLUM-07 | POST AVL link to non-vendor partner → 422 | integration | `pytest tests/plum/test_avl.py::test_avl_link_non_vendor -x` | Wave 0 gap |
| PLUM-08 | PATCH cost → effective cost = vendor price (step 1) | integration | `pytest tests/plum/test_costing.py::test_effective_cost_vendor -x` | Wave 0 gap |
| PLUM-08 | Effective cost falls through to manual (step 2) | unit | `pytest tests/plum/test_costing.py::test_effective_cost_manual -x` | Wave 0 gap |
| PLUM-08 | Effective cost roll-up from children (step 3) | unit | `pytest tests/plum/test_costing.py::test_effective_cost_rollup -x` | Wave 0 gap |
| PLUM-08 | Release snapshots cost into released_cost_snapshot | integration | `pytest tests/plum/test_costing.py::test_release_snapshots_cost -x` | Wave 0 gap |
| PLUM-09 | Margin = sale_price - effective_cost when both set | unit | `pytest tests/plum/test_costing.py::test_margin_computation -x` | Wave 0 gap |
| PLUM-10 | GET export/json returns valid JSON with parts + bom + avl | integration | `pytest tests/plum/test_import_export.py::test_export_json -x` | Wave 0 gap |
| PLUM-10 | GET export/excel returns xlsx with 3 sheets | integration | `pytest tests/plum/test_import_export.py::test_export_excel_sheets -x` | Wave 0 gap |
| PLUM-10 | POST import/preview returns new_count=N, 0 errors for valid JSON | integration | `pytest tests/plum/test_import_export.py::test_import_preview_valid -x` | Wave 0 gap |
| PLUM-10 | Import preview catches unknown vendor in AVL row | integration | `pytest tests/plum/test_import_export.py::test_import_preview_unknown_vendor -x` | Wave 0 gap |
| PLUM-10 | Import commit upserts without deleting existing data | integration | `pytest tests/plum/test_import_export.py::test_import_commit_no_delete -x` | Wave 0 gap |

**Frontend tests:**

| Req ID | Behavior | Test Type | File |
|--------|----------|-----------|------|
| PLUM-04 | BomTree renders child rows; expand/collapse toggles | smoke | `frontend/src/routes/plum/components/BomTree.test.tsx` — Wave 0 gap |
| PLUM-10 | ImportExport renders Step 1 upload zone and both export buttons | smoke | `frontend/src/routes/plum/ImportExport.test.tsx` — Wave 0 gap |

### Sampling Rate

- **Per task commit:** `cd backend && .venv/bin/pytest tests/plum/ -x -q`
- **Per wave merge:** `cd backend && .venv/bin/pytest tests/ -x -q && cd frontend && npm test -- --run`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

Backend (create before implementation):

- [ ] `backend/tests/plum/test_bom.py` — covers PLUM-04, PLUM-05, PLUM-06
- [ ] `backend/tests/plum/test_avl.py` — covers PLUM-07
- [ ] `backend/tests/plum/test_costing.py` — covers PLUM-08, PLUM-09
- [ ] `backend/tests/plum/test_import_export.py` — covers PLUM-10

Frontend (create before implementation):

- [ ] `frontend/src/routes/plum/components/BomTree.test.tsx` — smoke test
- [ ] `frontend/src/routes/plum/ImportExport.test.tsx` — smoke test

All backend test files follow the existing `tests/plum/test_parts.py` pattern: `skip_if_no_db` fixture for DB-dependent tests; `create_access_token` for auth tokens.

---

## Security Domain

**security_enforcement:** Enabled (default — not set to false in config.json).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (carried from Phase 2) | PyJWT + `require_permission()` dependency |
| V3 Session Management | yes (carried from Phase 2) | httpOnly cookie refresh token; access token in memory |
| V4 Access Control | yes | `require_permission("plum:read")` / `require_permission("plum:write")` on all new endpoints |
| V5 Input Validation | yes | Pydantic schemas with `max_length` on all string inputs; NUMERIC type for costs prevents injection |
| V6 Cryptography | no | No new cryptographic operations in Phase 6 |
| V7 Error Handling | yes (ongoing) | FastAPI exception handlers return structured errors without stack traces to client |
| V8 Data Protection | yes | Audit log on all mutations (D-19); no cost/price data in logs beyond action identifiers |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| BOM cycle via crafted insert | Tampering | Application-level cycle detection before insert; `visited` set guard at read time |
| Mass data exfiltration via export | Information Disclosure | `plum:read` RBAC gate on export; audit event `plum.exported` written on every export |
| Malicious Excel upload (macro/formula injection) | Tampering | openpyxl reads values only (`data_only=True`); no formula execution; `read_only=True` mode disables external links |
| Oversized file upload DoS | Denial of Service | FastAPI `UploadFile` reads into memory — add a file size limit (e.g., 10 MB) in the import endpoint using `file.size` check or content-length header inspection |
| SQL injection via import data | Tampering | All DB writes use SQLAlchemy ORM parameterized inserts — no raw string interpolation |
| Cross-module FK pollution (AVL → wrong partner) | Tampering | AVL link creation validates `syerp_partner.is_vendor=True` and `active=True` at insert time; returns 422 if vendor not found or not active |

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| SheetJS (client-side, the prototype) | openpyxl (server-side, FastAPI) | Import/export are RBAC-gated and audited; no client-side memory limits; aligns with D-15 (server-side architecture) |
| In-memory JSON file (prototype) | PostgreSQL with FK relationships | Multi-user safe; revision-controlled; cross-module FK to SYERP vendors |
| Single-part cost field (prototype `cost`) | Effective-cost resolution chain (D-07) | Supports purchased sub-assemblies; vendor price-break driven costing; historical snapshot |

**Deprecated/outdated in this project context:**
- Client-side SheetJS for import/export: prototype pattern, not applicable to the server-side architecture.
- `cost`/`costAvg`/`laborCost` as flat fields on part: the prototype pattern; replaced by revision-controlled `material_cost` + `released_cost_snapshot` + vendor-driven resolution chain.

---

## Open Questions

1. **BOM copy-forward scope: should `selected_vendor_link_id` copy forward to a new Draft revision?**
   - What we know: D-14 says the selected-vendor+break choice is revision-controlled and should be snapshotted at release. When creating a new revision, it's useful to carry forward the prior choice (user can then change it on the new Draft).
   - What's unclear: if the AVL link referenced by `selected_vendor_link_id` has been deleted by the time the new revision is created, the copied FK would be invalid.
   - Recommendation: Copy `selected_vendor_link_id` and `selected_price_break_index` forward, but with a defensive check: if the link no longer exists, set both to `null` on the new revision. Include a service comment explaining this.

2. **Import session token vs. re-upload for commit step (D-18):**
   - What we know: D-18 requires upload → preview → confirm. Two implementation options: (a) server stores parsed data in memory keyed by a session token for 10 minutes; (b) client re-uploads the same file on commit.
   - What's unclear: Option (a) has memory implications for large files; option (b) requires the frontend to retain the File object between steps.
   - Recommendation: Option (b) (re-upload on commit) is simpler and stateless. The frontend File API retains the File object after selection; the user never sees the second upload. This is standard practice for multi-step upload flows.

3. **File size limit for imports:**
   - What we know: An unbounded file upload is a DoS vector. The PLUM dataset is small (typical: <500 parts, <2000 BOM lines, <1000 AVL links).
   - Recommendation: Enforce a 10 MB limit on import uploads (generous for the dataset size). Implement via `if len(content) > 10 * 1024 * 1024: raise HTTPException(413, ...)`.

4. **`plum_avl_price_break` cascade delete behavior:**
   - What we know: When an AVL link is removed, its price breaks should also be removed.
   - Recommendation: `ON DELETE CASCADE` on the FK from `plum_avl_price_break.avl_link_id → plum_avl_link.id`. This is the correct relational pattern — no application-level cascade needed.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | FastAPI UploadFile pattern works with `python-multipart==0.0.32` for the import endpoint | Code Examples | LOW — python-multipart is already in requirements.txt and confirmed by FastAPI docs; UploadFile is well-established |
| A2 | Re-uploading the file on import commit is the recommended approach for the D-18 two-step flow | Open Questions | LOW — alternative (session token) works but adds complexity; re-upload is simpler and frontend-side File API retains the object |
| A3 | `openpyxl` `data_only=True` + `read_only=True` is sufficient to prevent formula injection from malicious imports | Security Domain | MEDIUM — openpyxl does not execute formulas; however, a crafted file could still exploit an openpyxl parsing vulnerability; for v1 this is acceptable |
| A4 | Manufacturing BOMs in this application will not exceed ~200 nodes, making Python-side recursion fast enough | Architecture Patterns | LOW — if a customer builds a 2000-node BOM, Python recursion may be slow; the `visited` dict and early-exit guards mitigate this; a CTE path can be added in v2 if needed |

**All other claims in this research were verified against actual codebase files or confirmed PyPI/npm registry.**

---

## Sources

### Primary (HIGH confidence)

- Codebase: `backend/app/modules/plum/models.py` — confirmed `PlumPart`, `PlumPartRevision` schema; no cost/BOM columns exist yet
- Codebase: `backend/app/modules/syerp/models.py` — confirmed `syerp_partner` table name, `is_vendor`, `active` columns; UUID PK
- Codebase: `backend/app/modules/plum/service.py` — confirmed `advance_revision_status` hook point (~line 765) for cost snapshot; `create_revision` copy-forward (~line 613)
- Codebase: `backend/app/modules/plum/router.py` — confirmed RBAC pattern, endpoint mount convention, audit pattern
- Codebase: `backend/app/modules/plum/schemas.py` — confirmed Pydantic schema patterns
- Codebase: `backend/alembic/versions/0005_plum_tables.py` — confirmed migration convention; `down_revision = "0004"`
- Codebase: `backend/app/core/settings_seed.py` — confirmed `locale.currency` key (not a new setting needed)
- Codebase: `backend/requirements.txt` — confirmed installed packages; openpyxl NOT yet installed
- Codebase: `frontend/package.json` — confirmed frontend deps; no Tooltip component installed
- Codebase: `frontend/src/routes/plum/PartDetail.tsx` — confirmed extension point for 4 new Card sections
- Codebase: `plum/app/plm_v54.html` (~lines 3380-3941) — confirmed prototype domain logic: `getEffectiveCost`, `generateFlatBom`, `getRolledUpCost`, `getWhereUsed`, AVL shape `partVendors`
- PyPI: `pip index versions openpyxl` — confirmed version 3.1.5, available
- slopcheck: `slopcheck install openpyxl` — confirmed [OK]
- SQLAlchemy: confirmed 2.0.51 installed; asyncpg dialect OK; NUMERIC maps to Decimal

### Secondary (MEDIUM confidence)

- `.planning/phases/06-plum-bom-costing-integration/06-CONTEXT.md` — locked decisions D-01 through D-19; canonical reference for all design choices
- `.planning/phases/06-plum-bom-costing-integration/06-UI-SPEC.md` — approved UI contract; all component names, interaction patterns, and copy confirmed from this source
- `.planning/STATE.md` — phase history and key decisions confirmed

### Tertiary (LOW confidence)

- [ASSUMED] FastAPI `UploadFile` behavior with `python-multipart` — training knowledge, not verified against FastAPI 0.138.0 changelog; however `python-multipart` is in requirements.txt which is the documented prerequisite

---

## Project Constraints (from CLAUDE.md)

| Directive | Enforcement |
|-----------|-------------|
| Conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:` | All commit messages in planned tasks |
| NEVER include "co-authored", "powered by", or "generated with Claude" in commit messages | Enforced in task commit steps |
| Tech stack: FastAPI + SQLAlchemy 2.0 + PostgreSQL; React 18 + TypeScript + Tailwind + shadcn/ui | All new code must use this stack |
| No pandas/heavy deps: permissive license only | openpyxl chosen (not pandas); openpyxl has MIT-style license |
| Audit trail first-class | All new endpoints write audit events (D-19) |
| Soft-delete / no hard-delete | Import D-17 never hard-deletes; AVL link removal is a hard-delete only of the link itself (not the part or vendor) — acceptable; BOM line removal is also a hard-delete of the line row (acceptable) |
| SYERP as hub | AVL FK to `syerp_partner` is the first real cross-module FK |
| Modular monolith / single Alembic history | Migration 0006 chains `down_revision = "0005"` |
| `plum_` table name prefix | All new tables: `plum_bom_item`, `plum_avl_link`, `plum_avl_price_break` |
| No ORM relationships (MissingGreenlet pitfall) | All new models follow same pattern as Phase 5 |

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified against installed venv or PyPI; codebase code confirmed against actual files
- Architecture: HIGH — BOM table design derived from locked CONTEXT.md decisions and confirmed existing schema
- Traversal patterns: HIGH — Python recursion recommended over CTE based on confirmed SQLAlchemy 2.0 async constraints and dataset size
- Pitfalls: HIGH — most pitfalls derived directly from existing codebase patterns (MissingGreenlet, partial unique index flush) and confirmed prototype behavior
- Import/export: MEDIUM-HIGH — openpyxl usage patterns from training knowledge; package existence confirmed via PyPI; specific async streaming pattern [ASSUMED]

**Research date:** 2026-06-29
**Valid until:** 2026-08-01 (packages are stable; codebase may evolve)
