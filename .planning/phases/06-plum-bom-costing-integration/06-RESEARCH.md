# Phase 6: PLUM BOM, Costing & Integration — Research

**Researched:** 2026-06-30
**Domain:** PostgreSQL recursive CTEs, multi-level BOM data models, async SQLAlchemy 2.0, openpyxl, React recursive tree UI
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**BOM Model & Structure**
- D-01: Parent revision owns the BOM. BOM lines belong to a specific parent part revision. Edit on Draft; Release freezes it. A new revision copies the prior BOM forward.
- D-02: BOM line references a child PART (not a fixed child revision); resolves to the child's latest Released revision at view/roll-up time.
- D-03: Unreleased children (no Released revision) fall back to the child's latest revision, flagged "unreleased" — provisional cost used in roll-up.
- D-04: BOM line payload = child part + decimal quantity (NUMERIC) + optional reference designators (free text) + child's UoM (shown for context).
- D-05: Cycles are hard-blocked on add/save. BOM graph is guaranteed acyclic at read time.

**Costing, Roll-up & Margin**
- D-06: Single material cost per revision (revision-controlled). No labor/dev-range in v1.
- D-07: Effective-cost resolution chain per part: (1) selected-vendor price-break cost, (2) manually-entered material cost, (3) BOM roll-up of children, (4) uncosted. Manual cost wins over roll-up even on assemblies (purchased sub-assembly support).
- D-08: Roll-up = Σ(child effective cost × line quantity) up the tree.
- D-09: Margin (price − effective cost) and margin % shown on Part Detail for any part revision that has an optional sale price. No "finished good" gating.
- D-10: Single system currency. Read from the Phase-3 `locale.currency` setting (already seeded as "USD"). No per-line currency, no FX.

**Vendor / AVL Linking**
- D-11: Full AVL link shape: FK to `syerp_partner` + vendor's part number + `preferred` flag + optional notes + quantity price-break table (rows of qty_threshold / unit_cost / lead_days).
- D-12: Vendor-driven costing is in v1. A part designates a selected vendor + selected price-break row; that row's unit cost feeds D-07 step 1.
- D-13: `preferred` (sourcing designation, multiple allowed) ≠ `selected-for-costing` (single driver, one per revision).
- D-14: AVL list + price-breaks are part-level/live. The selected-vendor+break choice is revision-controlled. On Release, the resolved effective cost is snapshotted as a frozen `as_released_cost` column on the revision. UI must surface both frozen and live recomputed cost.

**Import / Export**
- D-15: Server-side FastAPI endpoints. Export streams a file; import accepts upload, validates, writes in a transaction.
- D-16: JSON = full lossless round-trip of entire PLUM dataset. Excel = human-friendly multi-sheet (Parts, BOMs, AVL).
- D-17: Import uses upsert (match on stable keys), never hard-deletes absent rows.
- D-18: Preview-then-transactional commit. Upload → server validates → returns preview (N new, M updated, K errors) → user confirms → one all-or-nothing transaction. Any unresolved error blocks commit.

**Delegated to Research/Planner (Claude's Discretion)**
- D-19: Exact RBAC split (export `plum:read`, import `plum:write`), audit events (`plum.imported`, `plum.exported`) via existing `write_audit`.
- Exact table/column design: `PlumBomItem`, `PlumAvlLink`, `PlumAvlPriceBreak`, cost/sale-price columns on `PlumPartRevision`, as-released cost snapshot storage.
- Where-used implementation (recursive CTE vs. iterative).
- JSON schema/versioning; openpyxl Excel sheet/column layout.
- Whether `system_currency` is read from the Phase-3 `locale.currency` setting.

### Deferred Ideas (OUT OF SCOPE)

- Labor costing (hours × rate), dev-estimate cost ranges (costLow/High/Avg), distributor discount — promoted to PLUM-14..16.
- ECO / engineering-change-order workflow + effectivity dates.
- Revision→revision BOM lines (freeze exact child rev per line).
- Multi-currency + FX conversion.
- BOM tree / where-used / margin screen layouts — owned by the UI-spec phase (now COMPLETE: see 06-UI-SPEC.md).
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PLUM-04 | User can build a multi-level BOM and view it as an expandable tree | BOM edge-table model (§Standard Stack), PostgreSQL recursive CTE (§Architecture Patterns), cycle detection algorithm (§Code Examples) |
| PLUM-05 | User can view a flat BOM with quantity roll-up across levels | `generateFlatBom` recursion pattern (§Prototype Insights), server-side flat-BOM endpoint returning rolled quantities |
| PLUM-06 | User can run where-used analysis to see which assemblies consume a part | Reverse-BOM recursive CTE (§Architecture Patterns Pattern 3) |
| PLUM-07 | User can link a part to one or more vendors (FK to SYERP vendors / AVL) | `PlumAvlLink` + `PlumAvlPriceBreak` model (§Standard Stack), cross-module FK pattern |
| PLUM-08 | User can set part pricing/cost and see cost roll-up across a BOM | D-07 effective-cost chain (§Architecture Patterns Pattern 4), `material_cost` + `as_released_cost` columns on `PlumPartRevision` |
| PLUM-09 | User can view margin analysis for a product | D-09: sale_price column on `PlumPartRevision`, margin computed in service layer |
| PLUM-10 | User can import and export PLUM data as JSON and Excel | openpyxl 3.1.5 (§Standard Stack), D-16 JSON lossless / Excel multi-sheet, D-18 preview-then-commit (§Architecture Patterns Pattern 5) |
</phase_requirements>

---

## Summary

Phase 6 extends the Phase-5 PLUM parts/revisions foundation into a full product-structure and costing module. The core technical challenges are:

1. **Recursive BOM graph** — an edge table (`PlumBomItem`) with parent-revision-id → child-part-id edges. PostgreSQL `WITH RECURSIVE` CTEs handle tree traversal, flat-BOM roll-up, and reverse where-used in a single query per operation. Application-layer recursion is an acceptable alternative for v1 given the medical-device context (small BOM trees, < 50 parts per assembly in practice) but PostgreSQL CTE is recommended for correctness and performance at any depth.

2. **Effective-cost resolution chain (D-07)** — implemented in the service layer as a deterministic priority chain rather than in the DB, because it requires joining across the revision resolution logic (D-02/D-03). The as-released cost snapshot (D-14) is a frozen `NUMERIC` column written once on `advance_revision_status` when target is `released`.

3. **Cross-module FK (PLUM → SYERP)** — `PlumAvlLink` holds a FK to `syerp_partner.id` with `is_vendor = TRUE`. This is the first real cross-module FK in the system and validates the "SYERP as hub" architecture. Import validation must check that referenced vendors exist in SYERP before commit.

4. **Import/export** — `openpyxl` 3.1.5 is the correct, well-established Python library for server-side `.xlsx` generation. The preview-then-commit flow (D-18) requires a stateful server-side preview session (or a client-side JSON preview payload returned from the validate endpoint that is re-submitted on confirm).

**Primary recommendation:** Implement BOM traversal using PostgreSQL `WITH RECURSIVE` CTEs surfaced through synchronous SQLAlchemy `text()` queries (wrapped in `asyncio` via `run_in_executor` or via `db.execute(text(...))` which SQLAlchemy 2.0 async supports directly). Use openpyxl for Excel I/O, never pandas (adds 30 MB of dependency weight for functionality openpyxl covers). All patterns mirror the established Phase-4/5 service/router/schema shape exactly.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| BOM tree storage & traversal | Database (PostgreSQL) | API / Service | Recursive CTEs are native to PostgreSQL; tree traversal belongs in the DB tier for query efficiency |
| Effective-cost resolution chain | API / Service (Python) | — | D-07 chain requires cross-entity logic (revision resolution D-02/D-03, vendor selection, manual cost) that cannot cleanly be expressed as a single SQL join |
| As-released cost snapshot | Database column on `plum_part_revision` | Service (writes on release) | Frozen datum that must be immutable after release — stored in DB, written once by the release FSM path |
| Cycle detection | API / Service (Python) | — | Must run before the BOM line is committed; application-layer DFS on the adjacency graph is sufficient (cycles can't exist in DB yet if we check on add) |
| AVL / vendor links | Database (`plum_avl_link`) | Service | Cross-module FK to `syerp_partner`; live data (not revision-controlled beyond the selected-vendor+break choice) |
| Selected-vendor+break choice | Database column on `plum_part_revision` | — | Revision-controlled per D-14; stored as FK + integer index on the revision row |
| Cost roll-up (flat BOM, tree) | Database (recursive CTE) | Service (post-process) | Quantity multiplication can be done in a recursive CTE; cost resolution is done in service post-processing of CTE output |
| Where-used analysis | Database (recursive CTE, reverse direction) | — | Reverse BOM traversal via `WITH RECURSIVE` on the BOM edge table |
| Margin calculation | API / Service | Frontend (display) | Margin = sale_price − effective_cost; simple arithmetic done in service, returned in API response |
| JSON export | API / Service (streaming response) | — | Server owns the data; streams a JSON file from a FastAPI `StreamingResponse` |
| Excel export | API / Service (openpyxl) | — | Server-side file generation; no client-side library needed |
| Import preview + commit | API / Service | Frontend (display) | Two-step endpoint pattern (validate → preview JSON returned → confirm → commit); server owns validation and commit atomicity |
| BOM tree / flat BOM display | Frontend (React) | — | Recursive React component (`BomTree.tsx`) renders the tree structure returned by the API; view-mode toggle (tree/flat) is pure UI state |
| Currency display | Frontend (reads `locale.currency`) | — | System currency code read from settings and appended to cost displays; no computation on frontend |

---

## Standard Stack

### Core (Backend)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `openpyxl` | 3.1.5 [VERIFIED: PyPI] | Excel `.xlsx` read/write for import/export | Official Python library for OpenXML format; no C extensions; reads and writes multi-sheet workbooks; actively maintained; used by Django, FastAPI ecosystem broadly |
| `sqlalchemy` | 2.0.51 [VERIFIED: requirements.txt] | ORM + raw SQL for recursive CTEs | Already in stack; `db.execute(text("WITH RECURSIVE ..."))` works natively in SQLAlchemy 2.0 async |
| `fastapi` | 0.138.0 [VERIFIED: requirements.txt] | `StreamingResponse` for file downloads; `UploadFile` for imports | Already in stack; `StreamingResponse` streams file bytes; `UploadFile` provides async streaming reads |
| `python-multipart` | 0.0.32 [VERIFIED: requirements.txt] | Required for FastAPI `UploadFile` parsing | Already in stack |

### Supporting (Backend)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `io.BytesIO` | stdlib | In-memory buffer for openpyxl workbook before streaming | Use to avoid writing temp files to disk; write openpyxl workbook to BytesIO, stream from it |
| `decimal.Decimal` | stdlib | Exact decimal arithmetic for cost/qty values | Use for all cost and quantity fields that will be stored as PostgreSQL `NUMERIC` — avoids IEEE 754 float rounding errors |

### Core (Frontend)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@tanstack/react-query` | 5.101.1 [VERIFIED: package.json] | Server state management for BOM, AVL, cost data | Already in stack; invalidate queries on mutation to keep BOM tree and cost panel in sync |
| `lucide-react` | 1.21.0 [VERIFIED: package.json] | Tree toggle icons (`ChevronRight`, `ChevronDown`), action icons | Already installed; `CheckCircle`, `Circle`, `Trash2`, `Plus`, `Upload`, `Download`, `FileSpreadsheet`, `Loader2` all needed |
| `sonner` | ^2.0.7 [VERIFIED: package.json] | Toast notifications for BOM line added, vendor linked, cost saved, import complete | Already installed |
| `shadcn/ui` (Tooltip) | via `npx shadcn add tooltip` | BOM tree ref-des hover, child part description hover | Only new shadcn component needed; Radix UI `@radix-ui/react-tooltip` via shadcn |
| `axios` | ^1.18.1 [VERIFIED: package.json] | `apiClient` for BOM CRUD, AVL CRUD, cost save, export download, import upload | Already in stack |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `openpyxl` | `pandas` | pandas is 30 MB+ of dependency weight and pulls in numpy; openpyxl covers all needed Excel features without the cost. Pandas excels at data-frame operations but is overkill for structured multi-sheet export |
| `openpyxl` | `xlsxwriter` | xlsxwriter is write-only; cannot read existing .xlsx files, which is needed for Excel import (D-16). openpyxl handles both read and write |
| PostgreSQL recursive CTE | Application-layer recursion | App-layer is simpler to write in Python and works fine for small BOM trees (< 100 nodes). Recursive CTE is more efficient at depth and avoids N+1 queries. Recommend CTE for traversal, app-layer for cost resolution post-processing |
| `StreamingResponse` (FastAPI) | Temp file + `FileResponse` | Temp files require cleanup logic and disk I/O; `StreamingResponse` from `BytesIO` is clean, in-memory, and naturally suited to FastAPI |

**Installation (openpyxl — the only new dependency):**
```bash
# Add to backend/requirements.txt
echo "openpyxl==3.1.5" >> backend/requirements.txt
```

**Version verification:**
```
openpyxl: 3.1.5 (current on PyPI as of 2026-06-30)
```

---

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `openpyxl` | PyPI | ~14 years | ~35M/wk | github.com/theorchard/openpyxl (mirror) / openpyxl.readthedocs.io | [OK] (verified via slopcheck install) | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none

**Packages flagged as suspicious [SUS]:** none

All other packages (`fastapi`, `sqlalchemy`, `python-multipart`, `@tanstack/react-query`, `lucide-react`, `sonner`, `axios`) are already in the project's locked requirements/package.json — legitimacy already established in prior phases.

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (React)
    │
    ├── BOM tree view (BomTree.tsx)
    │       │  GET /api/v1/plum/parts/{id}/bom/tree
    │       │  POST /api/v1/plum/parts/{id}/bom (add line)
    │       │  PATCH /api/v1/plum/parts/{id}/bom/{line_id}
    │       │  DELETE /api/v1/plum/parts/{id}/bom/{line_id}
    │
    ├── Flat BOM view (BomTree.tsx, mode=flat)
    │       │  GET /api/v1/plum/parts/{id}/bom/flat
    │
    ├── Where-Used list (PartDetail.tsx)
    │       │  GET /api/v1/plum/parts/{id}/where-used
    │
    ├── AVL / Vendor links (AvlLinkSheet, PriceBreakEditor)
    │       │  GET /api/v1/plum/parts/{id}/avl
    │       │  POST /api/v1/plum/parts/{id}/avl
    │       │  PATCH /api/v1/plum/parts/{id}/avl/{link_id}
    │       │  DELETE /api/v1/plum/parts/{id}/avl/{link_id}
    │       │  [vendor search → GET /api/v1/syerp/partners?is_vendor=true&q=...]
    │
    ├── Cost & Margin panel (PartDetail.tsx inline)
    │       │  PATCH /api/v1/plum/parts/{id}/revisions/{rev_id}/cost
    │       │  GET /api/v1/plum/parts/{id}/revisions/{rev_id}/cost  (live recompute)
    │
    └── Import / Export page (ImportExport.tsx)
            │  GET  /api/v1/plum/export/json       → StreamingResponse (application/json)
            │  GET  /api/v1/plum/export/excel      → StreamingResponse (application/vnd.openxmlformats...)
            │  POST /api/v1/plum/import/validate   → UploadFile → preview JSON
            │  POST /api/v1/plum/import/commit     → preview token / confirm → atomic upsert
            
FastAPI (plum router)
    │
    ├── BOM service: tree query (recursive CTE), flat-BOM query, cycle check
    ├── AVL service: link CRUD, price-break CRUD, vendor search delegation
    ├── Cost service: effective-cost chain (D-07), roll-up, margin
    ├── Release hook: snapshot as_released_cost on advance_revision_status (D-14)
    └── Import/export service: openpyxl read/write, JSON serialize/deserialize,
                               upsert logic, preview generation
            │
PostgreSQL
    ├── plum_bom_item          (parent_revision_id → plum_part_revision.id,
    │                           child_part_id → plum_part.id, qty NUMERIC, ref_des)
    ├── plum_avl_link          (part_id → plum_part.id,
    │                           partner_id → syerp_partner.id [CROSS-MODULE FK],
    │                           vendor_part_number, preferred, notes)
    ├── plum_avl_price_break   (avl_link_id → plum_avl_link.id,
    │                           qty_threshold INT, unit_cost NUMERIC, lead_days INT)
    └── plum_part_revision     (+ material_cost NUMERIC, sale_price NUMERIC,
                                  as_released_cost NUMERIC,
                                  selected_avl_link_id → plum_avl_link.id,
                                  selected_price_break_index INT)
```

### Recommended Project Structure

```
backend/app/modules/plum/
├── models.py          # Add PlumBomItem, PlumAvlLink, PlumAvlPriceBreak;
│                      # add cost columns to PlumPartRevision
├── schemas.py         # Add BomItemCreate/Read, AvlLinkCreate/Read,
│                      # PriceBreakCreate/Read, CostUpdate/Read, BomTreeRead,
│                      # FlatBomRead, WhereUsedRead, ImportPreview, ExportSchemas
├── service.py         # Add BOM CRUD + cycle check, AVL CRUD, cost resolution,
│                      # roll-up, release snapshot hook, import/export functions
├── router.py          # Add BOM, AVL, cost, import/export endpoints
├── bom_cte.py         # (optional) Isolate recursive CTE SQL text for clarity
└── seed.py            # No changes needed

backend/alembic/versions/
└── 0006_plum_bom_avl_cost.py  # Single migration: all new tables + columns

backend/tests/plum/
├── test_bom.py              # Wave 0 stubs (BOM CRUD + cycle + tree + flat)
├── test_avl.py              # Wave 0 stubs (AVL CRUD, price-breaks)
├── test_costing.py          # Wave 0 stubs (effective-cost chain, roll-up, margin)
└── test_import_export.py    # Wave 0 stubs (JSON round-trip, Excel round-trip)

frontend/src/routes/plum/
├── PartDetail.tsx            # Extended with 4 new section cards
├── ImportExport.tsx          # New route (3-step import, export buttons)
└── components/
    ├── BomTree.tsx           # New: recursive tree + flat mode
    ├── BomLineSheet.tsx      # New: right-side Sheet for add/edit BOM line
    ├── PriceBreakEditor.tsx  # New: inline editable price-break row array
    ├── AvlLinkSheet.tsx      # New: right-side Sheet for add/edit AVL vendor link
    └── PlumNav.tsx           # Extended: add "Import / Export" tab
```

### Pattern 1: BOM Data Model (Edge Table)

**What:** A `plum_bom_item` table represents directed edges in the BOM DAG. Each row is one parent-revision → child-part edge with a quantity.

**Why edge table over adjacency list on `plum_part`:** Parts appear in multiple assemblies. The edge table natively supports this many-to-many structure, carries per-edge payload (qty, ref_des), and can be queried efficiently with recursive CTEs. Aligns with D-01 (parent revision owns the BOM) and D-04 (edge payload).

**Model:**
```python
# Source: derived from 06-CONTEXT.md D-01/D-04 + established Phase-5 model patterns
class PlumBomItem(Base):
    __tablename__ = "plum_bom_item"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # FK to parent revision (D-01: revision owns the BOM)
    parent_revision_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plum_part_revision.id"), nullable=False, index=True
    )
    # FK to child part (D-02: resolves to child's latest Released revision at view time)
    child_part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plum_part.id"), nullable=False
    )
    # D-04: decimal quantity (supports 0.5 kg, 2.3 m raw-material quantities)
    qty: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
    # D-04: optional reference designators (free text, comma-separated)
    ref_des: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Sort order for UI display stability
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

**Note:** No ORM relationships declared per the established project-wide pattern (MissingGreenlet pitfall — documented in syerp/models.py and plum/models.py).

### Pattern 2: AVL Link + Price-Break Model

```python
# Source: 06-CONTEXT.md D-11/D-13, syerp/models.py (Partner FK target)
class PlumAvlLink(Base):
    __tablename__ = "plum_avl_link"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # Part-level (not revision-controlled — AVL list is live)
    part_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plum_part.id"), nullable=False, index=True
    )
    # Cross-module FK (first in the system — validates SYERP-as-hub)
    partner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("syerp_partner.id"), nullable=False
    )
    vendor_part_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class PlumAvlPriceBreak(Base):
    __tablename__ = "plum_avl_price_break"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    avl_link_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plum_avl_link.id"), nullable=False, index=True
    )
    qty_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
    lead_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

### Pattern 3: Cost Columns on PlumPartRevision

**Additional columns to add via migration 0006:**
```sql
-- In the migration's upgrade() function:
ALTER TABLE plum_part_revision
    ADD COLUMN material_cost NUMERIC(18,6) NULL,          -- D-06: manual material cost
    ADD COLUMN sale_price NUMERIC(18,6) NULL,             -- D-09: optional sale price
    ADD COLUMN as_released_cost NUMERIC(18,6) NULL,       -- D-14: frozen cost snapshot on Release
    ADD COLUMN selected_avl_link_id VARCHAR(36) NULL      -- D-12/D-14: FK to PlumAvlLink
                REFERENCES plum_avl_link(id),
    ADD COLUMN selected_price_break_index INTEGER NULL;   -- D-12/D-14: index into price-break array
```

**Why `selected_avl_link_id` + index (not a FK to the price-break row):** The price-break table rows may be reordered or re-created; storing the FK to the price-break row (not the link) risks the selected row being deleted. Storing the AVL link FK + an index into the sorted price-breaks matches the prototype's `selectedVendorCostIndex` pattern, is simpler, and is recoverable. The price-break sort order must be stable (sorted by `qty_threshold` ascending, enforced on save).

### Pattern 4: Recursive BOM Traversal (PostgreSQL CTE)

**BOM tree (forward, all descendants):**
```python
# Source: PostgreSQL documentation WITH RECURSIVE, verified applicable to
# SQLAlchemy 2.0 async via db.execute(text(...))
# [ASSUMED] — PostgreSQL CTE is well-known but code verified against project patterns

BOM_TREE_CTE = """
WITH RECURSIVE bom_tree AS (
    -- Base case: direct children of the parent revision
    SELECT
        bi.id AS bom_item_id,
        bi.child_part_id,
        bi.qty,
        bi.ref_des,
        bi.sort_order,
        1 AS depth,
        ARRAY[bi.child_part_id] AS path
    FROM plum_bom_item bi
    WHERE bi.parent_revision_id = :parent_revision_id

    UNION ALL

    -- Recursive case: children of children
    -- Resolve child to its latest revision, then find its BOM lines
    SELECT
        bi.id AS bom_item_id,
        bi.child_part_id,
        bi.qty,
        bi.ref_des,
        bi.sort_order,
        bt.depth + 1,
        bt.path || bi.child_part_id
    FROM plum_bom_item bi
    INNER JOIN bom_tree bt ON bi.parent_revision_id = (
        -- Resolve child part → latest revision ID
        SELECT id FROM plum_part_revision
        WHERE part_id = bt.child_part_id
          AND status = 'released'
        UNION ALL
        -- Fallback: latest draft (D-03)
        SELECT id FROM plum_part_revision
        WHERE part_id = bt.child_part_id
        ORDER BY revision_number DESC
        LIMIT 1
    )
    -- Cycle guard: D-05 prevents cycles, but guard at DB level for safety
    WHERE NOT (bi.child_part_id = ANY(bt.path))
    AND bt.depth < 50  -- practical depth guard
)
SELECT
    bt.*,
    pp.part_number,
    pr.revision_label,
    pr.status AS revision_status,
    pr.unit_of_measure,
    pr.description
FROM bom_tree bt
JOIN plum_part pp ON pp.id = bt.child_part_id
LEFT JOIN plum_part_revision pr ON pr.part_id = bt.child_part_id
    AND pr.status = 'released'
ORDER BY bt.path;
"""
```

**Note on CTE complexity:** The "resolve child to its latest revision" step inside the recursive case is complex as a correlated subquery. A simpler alternative: run the CTE over part IDs only (yielding the flat set of part_id + total quantities), then join to latest-revision info in a second pass in the service layer. This is the recommended approach for v1.

**Simpler two-pass approach (recommended for v1):**
```python
# Pass 1: Flat quantity roll-up via recursive CTE (part IDs + quantities only)
# Pass 2: Join to latest revision data in Python after fetching from DB
# This avoids the correlated subquery complexity inside the CTE recursive term.
```

### Pattern 5: Flat BOM (Quantity Roll-Up)

The flat BOM rolls up total quantity across all paths to a leaf part. This requires multiplying quantities down the tree:

```python
# Source: plum/app/plm_v54.html generateFlatBom (~line 3894)
# Prototype algorithm: DFS with visitedIds cycle guard, parentQty * item.qty at each level
# Re-platform: implement in service layer using the recursive CTE output

def compute_flat_bom(tree_rows: list[dict]) -> list[dict]:
    """
    Post-process recursive CTE output into flat BOM with quantity roll-up.
    
    tree_rows: list of {child_part_id, qty, depth, path, ...} from the CTE.
    
    Algorithm: group by child_part_id, sum total quantities.
    Note: a part appearing in multiple sub-assemblies needs quantities multiplied
    up each path and then summed. The CTE path provides the ancestry needed.
    """
    # The CTE already carries per-edge qty; flat roll-up requires tracking
    # the cumulative qty product down each path.
    # Simplest correct approach: accumulate in Python after getting tree rows.
    flat: dict[str, dict] = {}
    for row in tree_rows:
        part_id = row["child_part_id"]
        # qty is the edge qty; cumulative qty = product of all qtys on the path
        # Path-aware quantity: the CTE should carry cumulative_qty (product down path)
        cumulative_qty = row["cumulative_qty"]  # computed in CTE or Python
        if part_id in flat:
            flat[part_id]["total_qty"] += cumulative_qty
        else:
            flat[part_id] = {
                "part_id": part_id,
                "total_qty": cumulative_qty,
                # resolved revision info populated in second pass
            }
    return list(flat.values())
```

### Pattern 6: Where-Used (Reverse BOM Traversal)

**Direct + indirect parents via reverse recursive CTE:**
```sql
-- [ASSUMED] — standard PostgreSQL recursive CTE pattern for reverse traversal
WITH RECURSIVE where_used AS (
    -- Base: direct parents (assemblies whose BOM contains this part)
    SELECT
        pr.part_id AS parent_part_id,
        pr.id AS parent_revision_id,
        bi.parent_revision_id AS via_revision_id,
        1 AS depth,
        NULL::varchar AS immediate_via_part_id
    FROM plum_bom_item bi
    JOIN plum_part_revision pr ON pr.id = bi.parent_revision_id
    WHERE bi.child_part_id = :target_part_id
    
    UNION ALL
    
    -- Recursive: parents of parents
    SELECT
        pr.part_id,
        pr.id,
        bi.parent_revision_id,
        wu.depth + 1,
        wu.parent_part_id::varchar
    FROM plum_bom_item bi
    JOIN plum_part_revision pr ON pr.id = bi.parent_revision_id
    INNER JOIN where_used wu ON bi.child_part_id = wu.parent_part_id
    WHERE wu.depth < 50
)
SELECT DISTINCT parent_part_id, depth, immediate_via_part_id
FROM where_used
ORDER BY depth, parent_part_id;
```

The UI-SPEC asks for "Direct parent" (depth=1) and "Indirect via {immediate_parent}" (depth>1). The `immediate_via_part_id` column provides this.

### Pattern 7: Effective-Cost Resolution Chain (D-07)

```python
# Source: 06-CONTEXT.md D-07/D-08, plum/app/plm_v54.html getEffectiveCost (~line 3669)
async def get_effective_cost(
    db: AsyncSession,
    revision: PlumPartRevision,
    bom_roll_up: Decimal | None = None,
) -> tuple[Decimal | None, str]:
    """
    Resolve effective cost per D-07 priority chain.
    
    Returns (cost_value, source_label) where source_label is one of:
        "vendor price", "manual", "roll-up", "uncosted"
    
    Priority:
      1. Selected vendor + price-break unit_cost (if selected_avl_link_id set)
      2. Manual material_cost (if set on revision)
      3. BOM roll-up of children (if has BOM children, passed as bom_roll_up arg)
      4. None / "uncosted"
    """
    from app.modules.plum.models import PlumAvlLink, PlumAvlPriceBreak

    # Step 1: Selected vendor price-break
    if revision.selected_avl_link_id and revision.selected_price_break_index is not None:
        pb_result = await db.execute(
            select(PlumAvlPriceBreak)
            .where(PlumAvlPriceBreak.avl_link_id == revision.selected_avl_link_id)
            .order_by(PlumAvlPriceBreak.qty_threshold)
        )
        price_breaks = list(pb_result.scalars().all())
        idx = revision.selected_price_break_index
        if 0 <= idx < len(price_breaks):
            return (price_breaks[idx].unit_cost, "vendor price")

    # Step 2: Manual material cost
    if revision.material_cost is not None:
        return (revision.material_cost, "manual")

    # Step 3: BOM roll-up (caller pre-computes and passes in)
    if bom_roll_up is not None:
        return (bom_roll_up, "roll-up")

    # Step 4: Uncosted
    return (None, "uncosted")
```

### Pattern 8: As-Released Cost Snapshot (D-14)

Hook into the existing `advance_revision_status` function in `service.py`. When `target_status == "released"`, after setting `released_at`, compute and write `as_released_cost`:

```python
# Source: 06-CONTEXT.md D-14, backend/app/modules/plum/service.py advance_revision_status
# (existing function at ~line 707 — add snapshot logic inside the if target_status == "released" block)

if target_status == "released":
    # ... existing supersede logic ...
    
    # D-14: Snapshot the as-released cost
    roll_up = await compute_bom_rollup(db, part_id, revision.id)
    effective_cost, _ = await get_effective_cost(db, revision, roll_up)
    revision.as_released_cost = effective_cost
    revision.released_at = datetime.now(timezone.utc)
```

### Pattern 9: Cycle Detection (D-05)

The prototype uses DFS to check if adding `candidate_child_id` under `parent_part_id` would create a cycle. In the re-platform, the check runs against the DB (not in-memory), but the algorithm is the same:

```python
# Source: plum/app/plm_v54.html checkCircularBom (~line 3077)
# Re-platform: query DB for BOM descendants of candidate_child, check if parent appears

async def would_create_cycle(
    db: AsyncSession,
    parent_part_id: str,
    candidate_child_id: str,
) -> bool:
    """
    Return True if adding candidate_child_id as a child of parent_part_id
    would create a cycle in the BOM graph.
    
    A cycle would occur if parent_part_id is already a descendant of
    candidate_child_id (transitively).
    
    Uses iterative BFS over the BOM edge table.
    """
    # Get all descendants of candidate_child via BFS
    # If parent_part_id appears in those descendants, adding it would cycle
    
    # Trivial case: part cannot be its own child
    if parent_part_id == candidate_child_id:
        return True
    
    # BFS from candidate_child downward through the BOM graph
    visited: set[str] = set()
    queue: list[str] = [candidate_child_id]
    
    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        
        # Find descendants of current: parts used IN current's latest revision BOM
        # Query the BOM edge table for all BOM lines whose parent_revision
        # belongs to `current`'s latest revision
        rows = await db.execute(
            select(PlumBomItem.child_part_id)
            .join(PlumPartRevision, PlumPartRevision.id == PlumBomItem.parent_revision_id)
            .where(
                PlumPartRevision.part_id == current,
                PlumPartRevision.revision_number == select(
                    func.max(PlumPartRevision.revision_number)
                ).where(PlumPartRevision.part_id == current).scalar_subquery()
            )
        )
        for (child_id,) in rows.all():
            if child_id == parent_part_id:
                return True  # cycle detected
            if child_id not in visited:
                queue.append(child_id)
    
    return False
```

**Performance note:** Cycle detection runs once per add operation. For typical BOM trees (< 200 parts), BFS with O(N×M) queries is acceptable. For large trees, consider a single recursive CTE to get all descendants at once (more efficient, fewer round-trips).

### Pattern 10: Import/Export (openpyxl + FastAPI)

**Export (Excel multi-sheet):**
```python
# Source: openpyxl documentation (https://openpyxl.readthedocs.io/)
# [ASSUMED] — openpyxl API is well-established but not verified via Context7 for this exact version

import io
from openpyxl import Workbook
from fastapi.responses import StreamingResponse

async def export_excel(db: AsyncSession) -> StreamingResponse:
    wb = Workbook()
    
    # Sheet 1: Parts
    ws_parts = wb.active
    ws_parts.title = "Parts"
    ws_parts.append(["Part Number", "Description", "Category", "UoM", "Status", 
                      "Revision", "Material Cost", "Sale Price", "As Released Cost", "Tags"])
    # ... populate rows from DB ...
    
    # Sheet 2: BOMs
    ws_boms = wb.create_sheet("BOMs")
    ws_boms.append(["Parent Part Number", "Parent Revision", "Child Part Number", 
                     "Qty", "Ref Des"])
    # ... populate rows ...
    
    # Sheet 3: AVL
    ws_avl = wb.create_sheet("AVL")
    ws_avl.append(["Part Number", "Vendor Code", "Vendor Name", "Vendor Part Number",
                    "Preferred", "Notes", "Qty Threshold", "Unit Cost", "Lead Days"])
    # ... populate rows ...
    
    # Stream from BytesIO
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plum_export.xlsx"},
    )
```

**Import preview-then-commit pattern (D-18):**
```python
# Two endpoints: POST /import/validate and POST /import/commit

@router.post("/import/validate")
async def validate_import(
    file: UploadFile,
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> ImportPreviewRead:
    """
    Step 1 of D-18: parse file, validate, return preview (no DB writes).
    Returns ImportPreviewRead with new_count, update_count, errors list.
    """
    content = await file.read()
    # Enforce 10 MB guard
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "File exceeds 10 MB limit")
    
    if file.filename.endswith(".json"):
        preview = await _validate_json_import(content, db)
    elif file.filename.endswith(".xlsx"):
        preview = await _validate_excel_import(content, db)
    else:
        raise HTTPException(400, "Unsupported file format")
    
    return preview


@router.post("/import/commit")
async def commit_import(
    # Re-upload the same file + confirm flag; or use a session token
    # Simplest v1: re-upload with the file again and commit directly
    # (preview is regenerated; any errors block commit per D-18)
    file: UploadFile,
    current_user=Depends(require_permission("plum:write")),
    db: AsyncSession = Depends(get_db),
) -> ImportResultRead:
    """
    Step 2 of D-18: re-validate, then commit in one transaction.
    Returns 400 if any errors exist in the re-validation pass.
    """
    content = await file.read()
    # ...validate again, then upsert in a single transaction...
    await write_audit(db, actor_id=str(current_user.id), action="plum.imported", ...)
```

**Note on D-18 commit strategy:** The simplest v1 implementation is to require the client to re-upload the file for commit (no server-side session storage). The frontend already holds the file in state between steps 1 and 2. This avoids server-side session management complexity.

### Anti-Patterns to Avoid

- **Float for monetary values:** Always use `NUMERIC` in PostgreSQL and `Decimal` in Python for cost/price/qty fields. IEEE 754 float rounding is inappropriate for financial data. The prototype used JavaScript `Number` (float); the re-platform must use `NUMERIC`. [VERIFIED: established PostgreSQL best practice]
- **ORM relationships on PLUM/SYERP models:** The project-wide decision (documented in `syerp/models.py` lines 99–102 and `plum/models.py` lines 105–108) forbids ORM relationships due to `MissingGreenlet` in async context. Use explicit `select()` queries throughout. [VERIFIED: project codebase]
- **Hard-deleting BOM items on import:** D-17 explicitly forbids hard-deletes during import. Use upsert only. Rows absent from the file are left in place.
- **Writing `as_released_cost` anywhere other than the release FSM path:** The snapshot must only be written once, at the moment of release, inside `advance_revision_status`. Writing it at any other time breaks D-14's immutability guarantee.
- **Cycle detection only at the UI layer:** The cycle check (D-05) must be enforced in the service layer (before the DB write), not just as frontend validation. The prototype did it in JS only; the re-platform must do it server-side.
- **Storing cost as a JSON blob:** All cost fields (material_cost, sale_price, as_released_cost) must be individual typed columns, not packed into a JSON field. This allows proper `NUMERIC` typing, indexing, and migration evolution.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Excel file read/write | Custom CSV parsing + `struct.pack` | `openpyxl` 3.1.5 | openpyxl handles cell types, number formats, multi-sheet workbooks, and formula cells correctly. Hand-rolled CSV breaks on multi-line fields and special characters |
| Recursive BOM traversal | Nested Python loops with N+1 DB queries | PostgreSQL `WITH RECURSIVE` CTE | N+1 queries at 5 levels deep on a 50-part BOM = 50+ queries. CTE does it in 1 query |
| File download streaming | Write to temp file, serve with `FileResponse` | `StreamingResponse` + `BytesIO` | Temp files require cleanup; `StreamingResponse` from `BytesIO` is clean and memory-safe for files up to a few MB |
| Import file parsing (XLSX) | Reading bytes directly | `openpyxl.load_workbook(BytesIO(content))` | openpyxl handles .xlsx zip structure, shared strings table, cell type inference, and encoding |
| Cycle detection | None / trust the user | Server-side BFS cycle check before commit | Without server-side cycle detection, a malformed import or concurrent API call can corrupt the BOM graph. The DB has no acyclicity constraint |
| Decimal arithmetic | Python `float` | `decimal.Decimal` / PostgreSQL `NUMERIC` | Floating-point rounding errors accumulate in cost roll-ups (e.g., 0.1 + 0.2 ≠ 0.3 in float). Use `NUMERIC` at rest and `Decimal` in Python computations |

**Key insight:** The two hardest problems in this phase — recursive traversal and Excel I/O — both have mature, correct solutions already in the Python ecosystem. The only real implementation work is integrating them with the domain model.

---

## Common Pitfalls

### Pitfall 1: MissingGreenlet on ORM Relationship Access

**What goes wrong:** Adding `relationship()` to `PlumBomItem`, `PlumAvlLink`, or the extended `PlumPartRevision` and then accessing those relationships in an async route handler causes `MissingGreenlet` (SQLAlchemy greenlet thread error).

**Why it happens:** SQLAlchemy's async session requires `lazy="selectin"` (or explicit eager loading) on all ORM relationships. The project-wide decision forbids ORM relationships to avoid this class of error entirely (documented in `plum/models.py` docstring).

**How to avoid:** Never add `relationship()` to any new model. Use explicit `select()` queries for every association lookup. The service layer performs explicit join queries.

**Warning signs:** `MissingGreenlet` in test output after adding a new model. The fix is always to remove the relationship and replace with an explicit query.

### Pitfall 2: Recursive CTE in SQLAlchemy 2.0 Async

**What goes wrong:** Using `db.execute(text("WITH RECURSIVE ..."))` in an async context requires passing parameters correctly. Named parameters (`:param_name`) work; positional `%s` parameters are dialect-specific and fragile.

**Why it happens:** SQLAlchemy's `text()` uses bindparam syntax (`:name`) by default; PostgreSQL also supports `$1` in raw SQL but `text()` does not map to those automatically.

**How to avoid:**
```python
# Correct: named bindparams with text()
result = await db.execute(
    text(BOM_TREE_CTE),
    {"parent_revision_id": revision_id}
)
```

**Warning signs:** `ProgrammingError: column "parent_revision_id" does not exist` — this is the symptom of unbound parameters in a raw CTE.

### Pitfall 3: Flat BOM Quantity Roll-Up Logic

**What goes wrong:** A part that appears in multiple sub-assemblies gets its quantity summed correctly only if you multiply quantities down each path first. Naively summing edge quantities (without path-product) underestimates total quantity.

**Why it happens:** The flat BOM quantity is the sum of (path quantity products) across all paths to a part. The prototype's `generateFlatBom` handles this via `parentQty * item.qty` at each recursion level. The CTE approach needs a `cumulative_qty` column (product of all edge quantities on the path from root to this node).

**How to avoid:** The recursive CTE must maintain a `cumulative_qty` column:
```sql
-- In the recursive CTE, carry cumulative quantity product
qty AS bom_item_qty,                            -- edge qty
1.0 AS cumulative_qty                           -- base case: qty product = 1 at root
-- In recursive step:
bi.qty AS bom_item_qty,
bt.cumulative_qty * bi.qty AS cumulative_qty    -- multiply down the path
```
Then flat BOM = GROUP BY child_part_id, SUM(cumulative_qty).

**Warning signs:** Flat BOM shows quantities that are too low for parts used in multiple places (e.g., a screw used in 3 sub-assemblies of qty 4 each shows 4 instead of 12).

### Pitfall 4: selected_price_break_index Stale After Price-Break Edits

**What goes wrong:** If a user edits the price-break list for a vendor (reorders, deletes, or inserts rows), the `selected_price_break_index` stored on the revision may point to a different row or an out-of-bounds index.

**Why it happens:** The index is a position-based reference into a sorted list that can change.

**How to avoid:** Always sort price-breaks by `qty_threshold` ascending before saving, and enforce this sort order consistently. When a price-break row is deleted and the selected index becomes out-of-bounds, clear the selection (`selected_avl_link_id = NULL`, `selected_price_break_index = NULL`) and surface a warning to the user. On the UI side, show "No longer valid" if the index is stale.

**Alternative:** Use a FK to the price-break row (`selected_price_break_id`) instead of an index. This is more robust but was not chosen in the decisions (D-12/D-14 reference "index" from the prototype). The planner should decide based on D-14's stability requirements.

**Warning signs:** Users report cost calculations showing wrong vendor prices after editing price breaks.

### Pitfall 5: Import Commit Without Re-Validation

**What goes wrong:** The D-18 preview is generated at upload time, but the commit endpoint trusts the preview result passed from the client without re-running validation. A malicious or corrupted client request could commit invalid data.

**Why it happens:** Stateless server design requires the server to either (a) store preview state server-side, or (b) re-validate on commit.

**How to avoid:** The commit endpoint must re-run the full validation pass before executing the upsert. The D-18 contract says "any unresolved error blocks the commit" — this requires server-side enforcement, not client-side trust.

**Warning signs:** Import succeeds even when the source file contains references to non-existent SYERP vendors.

### Pitfall 6: NUMERIC vs float in SQLAlchemy 2.0

**What goes wrong:** Declaring a column as `Float` instead of `Numeric(precision, scale)` in SQLAlchemy causes PostgreSQL to use a floating-point type (`double precision`), which accumulates rounding errors in cost roll-ups.

**How to avoid:** Use `from sqlalchemy import Numeric` and `Mapped[Decimal]` with `from decimal import Decimal`. Verify the migration generates `NUMERIC(18, 6)` columns, not `FLOAT` or `DOUBLE PRECISION`.

```python
from decimal import Decimal as PyDecimal
from sqlalchemy import Numeric

qty: Mapped[PyDecimal] = mapped_column(Numeric(precision=18, scale=6), nullable=False)
```

### Pitfall 7: Cross-Module FK Ordering in Migration

**What goes wrong:** Migration `0006_plum_bom_avl_cost.py` adds `plum_avl_link.partner_id → syerp_partner.id`. If the migration is accidentally placed before `0004_syerp_tables.py` in Alembic's chain, the FK constraint fails (referenced table doesn't exist yet).

**How to avoid:** Set `down_revision = "0005"` in migration 0006. The chain `0005 → 0004 → ... → 0001` guarantees SYERP tables exist before PLUM AVL tables are created.

**Warning signs:** `alembic upgrade head` fails with "relation syerp_partner does not exist" on a fresh DB.

---

## Code Examples

### BOM Line Create + Cycle Check (Service Layer)
```python
# Source: 06-CONTEXT.md D-04/D-05, project service.py pattern (Phase-5)
async def add_bom_item(
    db: AsyncSession,
    parent_revision_id: str,
    child_part_id: str,
    qty: Decimal,
    ref_des: str | None,
    actor_id: str,
) -> PlumBomItem:
    from app.modules.plum.models import PlumBomItem, PlumPartRevision
    
    # Verify revision exists and is Draft (immutable on Released)
    rev = await get_revision(db, parent_revision_id)
    if rev.status != "draft":
        raise HTTPException(422, "Cannot edit BOM on a non-Draft revision")
    
    # D-05: Hard-block cycles
    if await would_create_cycle(db, rev.part_id, child_part_id):
        raise HTTPException(
            422,
            f"Adding this part would create a circular BOM reference. "
            f"Choose a different part."
        )
    
    # Get current max sort_order
    max_sort = await db.execute(
        select(func.max(PlumBomItem.sort_order))
        .where(PlumBomItem.parent_revision_id == parent_revision_id)
    )
    next_sort = (max_sort.scalar() or 0) + 1
    
    item = PlumBomItem(
        id=str(uuid.uuid4()),
        parent_revision_id=parent_revision_id,
        child_part_id=child_part_id,
        qty=qty,
        ref_des=ref_des,
        sort_order=next_sort,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    
    await write_audit(db, actor_id=actor_id, action="bom.line_added",
                      target_type="bom_item", target_id=item.id,
                      detail=f"BOM line added to revision {parent_revision_id}")
    return item
```

### BOM Copy-Forward on New Revision
```python
# Source: 06-CONTEXT.md D-01 "A new revision copies the prior BOM forward"
# Hooks into existing create_revision() in service.py
async def copy_bom_forward(
    db: AsyncSession,
    source_revision_id: str,
    new_revision_id: str,
) -> int:
    """Copy all BOM lines from source_revision to new_revision. Returns count of lines copied."""
    from app.modules.plum.models import PlumBomItem
    
    existing = await db.execute(
        select(PlumBomItem).where(PlumBomItem.parent_revision_id == source_revision_id)
        .order_by(PlumBomItem.sort_order)
    )
    lines = list(existing.scalars().all())
    
    for line in lines:
        db.add(PlumBomItem(
            id=str(uuid.uuid4()),
            parent_revision_id=new_revision_id,
            child_part_id=line.child_part_id,
            qty=line.qty,
            ref_des=line.ref_des,
            sort_order=line.sort_order,
        ))
    
    await db.flush()  # Not commit — called inside create_revision's transaction
    return len(lines)
```

### Resolve Child to Latest Revision
```python
# Source: 06-CONTEXT.md D-02/D-03
async def resolve_child_revision(
    db: AsyncSession,
    child_part_id: str,
) -> tuple["PlumPartRevision | None", bool]:
    """
    Resolve a child part to its effective revision per D-02/D-03.
    
    Returns (revision, is_provisional) where:
      - is_provisional=False: child has a Released revision (authoritative)
      - is_provisional=True: child has no Released revision, using latest Draft (D-03)
    """
    from app.modules.plum.models import PlumPartRevision
    
    # Try latest Released revision first (D-02)
    released = await get_released_revision(db, child_part_id)
    if released:
        return (released, False)
    
    # Fallback: latest overall revision (D-03)
    latest_result = await db.execute(
        select(PlumPartRevision)
        .where(PlumPartRevision.part_id == child_part_id)
        .order_by(PlumPartRevision.revision_number.desc())
    )
    latest = latest_result.scalars().first()
    return (latest, True)  # provisional if any
```

### openpyxl JSON Export (Lossless)
```python
# Source: openpyxl docs, 06-CONTEXT.md D-16
import json
import io
from datetime import datetime

async def export_json(db: AsyncSession) -> StreamingResponse:
    """
    D-16: Full lossless JSON export of the entire PLUM dataset.
    Includes: parts, all revisions (with cost data), BOM lines, AVL links, price-breaks.
    """
    # Fetch all data
    parts_data = await _export_parts_full(db)
    
    payload = {
        "schema_version": "1.0",
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "parts": parts_data,  # includes nested revisions, bom_items, avl_links, price_breaks
    }
    
    json_bytes = json.dumps(payload, default=str, indent=2).encode("utf-8")
    
    return StreamingResponse(
        io.BytesIO(json_bytes),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=plum_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        },
    )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Client-side SheetJS (JavaScript) for Excel I/O | Server-side openpyxl (Python) via FastAPI endpoint | Phase 6 (architecture shift from prototype) | Import now validates against the DB (vendor existence, part references); export is auth-gated and audited |
| In-memory JSON array (prototype `DB.parts`) for BOM storage | Relational edge table (`plum_bom_item`) with PostgreSQL CTE traversal | Phase 6 re-platform | Multi-user safe, FK-integrity-checked, traversal scales with tree depth |
| `float` (JavaScript Number) for cost/quantity | `NUMERIC(18,6)` (PostgreSQL) + `Decimal` (Python) | Phase 6 re-platform | Eliminates floating-point rounding errors in cost roll-ups |
| Linear scan of all parts for where-used (O(N) in prototype) | Reverse recursive CTE with index on `plum_bom_item.child_part_id` | Phase 6 | Scales to thousands of parts without full-table scan |
| No cycle enforcement in prototype `addToBom` | Hard server-side cycle detection (DFS/BFS) before DB write (D-05) | Phase 6 | Guarantees BOM graph acyclicity; makes roll-up and where-used safe without cycle guards at read time |

**Deprecated/outdated:**
- `visitedIds = new Set()` cycle guard in `getRolledUpCost` and `generateFlatBom` (prototype): With D-05 guaranteeing acyclicity at write time, the read-time cycle guard is no longer needed — the server-side check replaces it.

---

## Prototype Insights (plum/app/plm_v54.html)

These findings from the v54 prototype are domain logic worth carrying forward. They are reference-only — the prototype code is NOT used directly.

### AVL Vendor Shape (`partVendors` array, ~line 3418)
The prototype stores per-part: `{vendorId, vendorPartNumber, isPreferred, costs[], notes}` where `costs[]` = `[{minQty, unitCost, leadTimeDays, effectiveDate}]`. The re-platform maps this to:
- `PlumAvlLink`: `part_id`, `partner_id`, `vendor_part_number`, `preferred`, `notes`
- `PlumAvlPriceBreak`: `avl_link_id`, `qty_threshold` (= `minQty`), `unit_cost`, `lead_days`
- `selectedVendorId` + `selectedVendorCostIndex` → `selected_avl_link_id` + `selected_price_break_index` on `PlumPartRevision`

### Effective-Cost Chain (`getEffectiveCost`, ~line 3669)
The prototype priority: (1) selected vendor `costs[selectedVendorCostIndex].unitCost`, (2) released `part.cost`, (3) `part.costAvg`. The re-platform D-07 chain maps: (1) selected vendor price-break, (2) manual `material_cost`, (3) BOM roll-up. Note: the prototype did not have a BOM-roll-up fallback as step 3 — D-07 adds this as a new capability.

### Cycle Detection (`checkCircularBom`, ~line 3077)
The prototype: `checkCircularBom(assemblyId, partIdToAdd, visited)` checks if `assemblyId` appears in `partIdToAdd`'s BOM tree. The re-platform equivalent queries the DB directly (see Pattern 9 above).

### Flat BOM (`generateFlatBom`, ~line 3894)
The prototype: leaf parts accumulate by `partId` with `qty += parentQty` (running product). Non-leaf assemblies recurse into children. The re-platform equivalent uses a recursive CTE with `cumulative_qty` (path product) then `SUM(cumulative_qty)` by `child_part_id`.

### Where-Used (`getWhereUsed`, ~line 3814)
The prototype: **direct-only linear scan** (not recursive). The re-platform upgrades this to direct + indirect (full reverse traversal) per PLUM-06 and the ROADMAP success criterion #3.

### Excel Import (`handlePartsImport`, `handleBomsImport`, ~line 25773)
The prototype uses SheetJS (client-side CDN library). The re-platform replaces entirely with server-side openpyxl. The Excel column layout (Parts sheet, BOMs sheet, AVL sheet) is designed to match what a user familiar with the prototype would expect.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | PostgreSQL `WITH RECURSIVE` CTE syntax shown in Pattern 4 uses the correct join approach for resolving child parts to their latest revision inside the recursive term | Architecture Patterns Pattern 4 | CTE may not execute as expected in PostgreSQL; symptom would be incorrect tree traversal. Mitigation: use the two-pass approach (CTE for part IDs + Python join for revision data) which avoids the complex correlated subquery entirely |
| A2 | `selected_price_break_index` is stored as an integer index into the price-break list sorted by `qty_threshold`. If price breaks are reordered, this index goes stale | Architecture Patterns Pattern 3 | Wrong cost is used in effective-cost chain (D-07 step 1). Mitigation: always enforce sort order on save; validate index on read |
| A3 | openpyxl's `load_workbook(BytesIO(content))` supports reading `.xlsx` files from a bytes buffer | Code Examples (import) | If openpyxl requires a file path (not supported for BytesIO), the import endpoint would need to write a temp file. Mitigation: openpyxl docs confirm BytesIO support but not verified with Context7 for this version |
| A4 | The D-14 live cost recompute displayed on Released revisions is computed on-demand (not cached) | Architecture Patterns Pattern 7 | If BOM is large and cost re-resolution is slow, the PartDetail page could have noticeable latency. Mitigation: for v1 (small BOM trees), on-demand is acceptable |

**If this table is empty:** it is not empty — see above.

---

## Open Questions

1. **`selected_price_break_index` vs. `selected_price_break_id` (FK)**
   - What we know: the prototype stores an index (`selectedVendorCostIndex`); D-12/D-14 reference this pattern.
   - What's unclear: an FK to the price-break row would be more robust but the CONTEXT.md uses "index" terminology.
   - Recommendation: The planner should use a FK (`selected_price_break_id → plum_avl_price_break.id`) for robustness. If a price-break row is deleted, set `selected_price_break_id = NULL` (cascading or explicit) and surface a warning. This is strictly safer than an index and still matches the D-12/D-14 intent.

2. **BOM copy-forward scope**
   - What we know: D-01 says "A new revision copies the prior BOM forward to edit."
   - What's unclear: Does copy-forward include the `selected_avl_link_id` and `selected_price_break_index` (or `_id`) columns on the new revision? Logically yes (the cost selection should carry forward), but this needs a deliberate decision.
   - Recommendation: Copy all cost-related columns forward (material_cost, sale_price, selected_avl_link_id, selected_price_break_index). `as_released_cost` must NOT be copied (it is only set on release). The planner should make this explicit in the copy-forward task.

3. **System currency source**
   - What we know: D-10 says "one organization currency"; Phase-3 seeds `locale.currency = "USD"` in the settings table.
   - What's unclear: CONTEXT.md says "a Phase-3 system setting, default e.g. USD" — confirming this is the `locale.currency` setting already seeded.
   - Recommendation: Read `locale.currency` from the `Setting` table (same pattern as `_get_revision_scheme` in `service.py`). No new setting needed.

4. **Import commit: re-upload vs. server-side session**
   - What we know: D-18 requires preview → user confirms → commit. The simplest pattern is re-upload the file for commit.
   - What's unclear: Is the UX acceptable to require the client to hold the file in state and re-upload it?
   - Recommendation: Re-upload is acceptable for v1. The frontend `ImportExport.tsx` holds the file in React state between steps 1 and 2 (the file input ref is not cleared until after commit). Implement this as the default; add server-side session (store validated payload in DB or cache) in v2 if file size becomes a concern.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | openpyxl, FastAPI backend | ✓ | 3.12.3 | — |
| openpyxl | Excel export/import | ✗ (not yet in requirements.txt) | 3.1.5 on PyPI | No fallback — required for PLUM-10 Excel |
| PostgreSQL | All DB operations including CTEs | ✓ (via Podman Compose) | Configured in stack | — |
| `@radix-ui/react-tooltip` | shadcn Tooltip component | ✗ (not yet installed) | via `npx shadcn add tooltip` | No fallback — required by UI-SPEC for BOM tree hover |
| `lucide-react` icons (CheckCircle, Circle, Upload, Download, FileSpreadsheet) | BOM tree, AVL, Import/Export UI | ✓ | 1.21.0 | — |

**Missing dependencies with no fallback:**
- `openpyxl==3.1.5` — must be added to `backend/requirements.txt` before Wave 1
- `@radix-ui/react-tooltip` (via `npx shadcn add tooltip`) — must be installed before Wave 4

**Missing dependencies with fallback:**
- None

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| Config file | `backend/pyproject.toml` (`asyncio_mode = "auto"`, `testpaths = ["tests"]`) |
| Quick run command | `cd backend && pytest tests/plum/ -x -q` |
| Full suite command | `cd backend && pytest -x -q` |

Frontend:

| Property | Value |
|----------|-------|
| Framework | Vitest ^4.1.9 + @testing-library/react ^16.3.2 |
| Config file | `frontend/vite.config.ts` (inferred from package.json) |
| Quick run command | `cd frontend && npx vitest run --reporter=verbose src/routes/plum/` |
| Full suite command | `cd frontend && npx vitest run` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLUM-04 | POST BOM line → 201; tree returned with correct depth | integration (DB required) | `pytest tests/plum/test_bom.py::test_add_bom_line -x` | ❌ Wave 0 |
| PLUM-04 | Cycle detection → 422 on add that would create cycle | integration (DB required) | `pytest tests/plum/test_bom.py::test_cycle_detection -x` | ❌ Wave 0 |
| PLUM-04 | BOM tree endpoint returns correct depth/qty for 3-level BOM | integration (DB required) | `pytest tests/plum/test_bom.py::test_bom_tree_depth -x` | ❌ Wave 0 |
| PLUM-05 | Flat BOM roll-up: part used in 2 sub-assemblies shows correct total qty | integration (DB required) | `pytest tests/plum/test_bom.py::test_flat_bom_rollup -x` | ❌ Wave 0 |
| PLUM-06 | Where-used returns direct parents | integration (DB required) | `pytest tests/plum/test_bom.py::test_where_used_direct -x` | ❌ Wave 0 |
| PLUM-06 | Where-used returns indirect (grandparent) assemblies | integration (DB required) | `pytest tests/plum/test_bom.py::test_where_used_indirect -x` | ❌ Wave 0 |
| PLUM-07 | POST AVL link with price-breaks → 201; link + breaks persisted | integration (DB required) | `pytest tests/plum/test_avl.py::test_add_avl_link -x` | ❌ Wave 0 |
| PLUM-07 | AVL link rejects archived/non-vendor partner | integration (DB required) | `pytest tests/plum/test_avl.py::test_avl_vendor_validation -x` | ❌ Wave 0 |
| PLUM-08 | Effective cost = vendor price when selected (D-07 step 1) | unit (no DB) | `pytest tests/plum/test_costing.py::test_effective_cost_vendor -x` | ❌ Wave 0 |
| PLUM-08 | Effective cost = manual cost when no vendor selected (D-07 step 2) | unit (no DB) | `pytest tests/plum/test_costing.py::test_effective_cost_manual -x` | ❌ Wave 0 |
| PLUM-08 | Roll-up: parent cost = sum(child effective cost × qty) | integration (DB required) | `pytest tests/plum/test_costing.py::test_cost_rollup -x` | ❌ Wave 0 |
| PLUM-08 | as_released_cost snapshotted on revision release | integration (DB required) | `pytest tests/plum/test_costing.py::test_as_released_snapshot -x` | ❌ Wave 0 |
| PLUM-09 | Margin = sale_price − effective_cost; margin_pct computed correctly | unit (no DB) | `pytest tests/plum/test_costing.py::test_margin_calculation -x` | ❌ Wave 0 |
| PLUM-10 | JSON export → re-import restores same part + revision + BOM + AVL dataset | integration (DB required) | `pytest tests/plum/test_import_export.py::test_json_roundtrip -x` | ❌ Wave 0 |
| PLUM-10 | Excel export → re-import updates existing parts + inserts new ones (upsert, no deletes) | integration (DB required) | `pytest tests/plum/test_import_export.py::test_excel_roundtrip -x` | ❌ Wave 0 |
| PLUM-10 | Import with invalid vendor reference → preview shows error, commit blocked | integration (DB required) | `pytest tests/plum/test_import_export.py::test_import_invalid_vendor -x` | ❌ Wave 0 |
| PLUM-10 | Import file > 10 MB → 413 | unit (no DB) | `pytest tests/plum/test_import_export.py::test_import_size_limit -x` | ❌ Wave 0 |
| PLUM-04 (frontend) | BomTree renders expand/collapse; flat mode shows rolled qty | unit (React) | `npx vitest run src/routes/plum/components/BomTree.test.tsx` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && pytest tests/plum/ -x -q`
- **Per wave merge:** `cd backend && pytest -x -q && cd ../frontend && npx vitest run`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps (must exist before implementation waves)

- [ ] `backend/tests/plum/test_bom.py` — BOM CRUD + cycle detection + tree + flat + where-used stubs
- [ ] `backend/tests/plum/test_avl.py` — AVL link + price-break CRUD stubs
- [ ] `backend/tests/plum/test_costing.py` — effective cost chain, roll-up, margin, release snapshot stubs
- [ ] `backend/tests/plum/test_import_export.py` — JSON round-trip, Excel round-trip, validation stubs
- [ ] `frontend/src/routes/plum/components/BomTree.test.tsx` — tree/flat render smoke test

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | existing `require_permission()` on all new endpoints |
| V3 Session Management | no | handled by Phase-2 auth; no new session types |
| V4 Access Control | yes | `plum:read` for export/GET; `plum:write` for BOM edit/AVL/import |
| V5 Input Validation | yes | Pydantic schemas with `max_length`, `min_value` constraints; file size guard (10 MB); parameterized SQL for CTEs |
| V6 Cryptography | no | no new crypto; cost/BOM data is not encrypted at rest beyond DB-level |
| V7 Error Handling | yes | import errors returned as structured preview (no stack traces to client) |

### Known Threat Patterns for This Phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious import file (path traversal, macro injection) | Tampering | openpyxl does not execute Excel macros; reject `.xlsm` files; accept `.xlsx` only. File size guard (10 MB) prevents DoS via large uploads |
| BOM cycle injection via concurrent API calls | Tampering | Cycle check runs in the service layer per-request; PostgreSQL transaction isolation ensures atomicity of check+insert |
| Privilege escalation via import | Elevation of Privilege | Import endpoint requires `plum:write`; audit event `plum.imported` written on commit |
| SQL injection via BOM/AVL search queries | Tampering | All queries use parameterized SQLAlchemy `text(..., {"param": value})` or ORM `.where()` — never string interpolation |
| Broken object-level authorization (BOLA) | Information Disclosure | BOM/AVL endpoints are part-scoped; verify `parent_revision.part_id` belongs to a real part before any write. Existing `require_permission` gates all routes |
| Export of sensitive cost data | Information Disclosure | Export requires `plum:read` permission; audit event `plum.exported` written on every export |

---

## Sources

### Primary (HIGH confidence)
- `backend/app/modules/plum/models.py` — Phase-5 data model, established naming/pattern conventions
- `backend/app/modules/plum/service.py` — Phase-5 service layer patterns, FSM, copy-forward, audit hooks
- `backend/app/modules/plum/router.py` — Phase-5 router/RBAC patterns
- `backend/app/modules/syerp/models.py` — `syerp_partner` FK target for AVL links
- `backend/alembic/versions/0005_plum_tables.py` — migration pattern (hand-authored, no-live-DB convention)
- `backend/app/core/models.py` — aggregator import pattern (Alembic discovery)
- `backend/app/core/seed.py` — idempotent seed hook pattern
- `backend/app/core/settings_seed.py` — `locale.currency` = "USD" already seeded
- `.planning/phases/06-plum-bom-costing-integration/06-CONTEXT.md` — all decisions D-01..D-19
- `.planning/phases/06-plum-bom-costing-integration/06-UI-SPEC.md` — screen layouts, component contracts, accessibility
- `frontend/src/routes/plum/PartDetail.tsx` — existing Phase-5 page structure to extend
- `frontend/package.json` — installed frontend packages (all verified)
- `backend/requirements.txt` — installed backend packages (all verified)

### Secondary (MEDIUM confidence)
- `plum/app/plm_v54.html` (lines 3669–3941) — domain logic reference for effective cost chain, BOM traversal, flat BOM, where-used, cycle detection, AVL vendor shape — [ASSUMED] for domain correctness, not code reuse
- PyPI `openpyxl` 3.1.5 — latest version confirmed via `pip index versions openpyxl`; slopcheck `[OK]`

### Tertiary (LOW confidence)
- PostgreSQL `WITH RECURSIVE` CTE examples for reverse BOM traversal — [ASSUMED] standard pattern, not verified via live DB query

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages verified in requirements.txt/package.json or PyPI
- Architecture: HIGH — directly derived from existing Phase-4/5 codebase patterns + CONTEXT.md locked decisions
- Prototype insights: MEDIUM — prototype code read directly, but prototype is not the target schema
- Recursive CTE SQL: MEDIUM — standard PostgreSQL feature but exact CTE syntax for this schema is [ASSUMED]
- Pitfalls: HIGH — most derived from existing codebase decisions and documented pitfalls

**Research date:** 2026-06-30
**Valid until:** 2026-07-30 (stable domain; SQLAlchemy/FastAPI/openpyxl APIs are not fast-moving)
