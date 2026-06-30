---
phase: "06-plum-bom-costing-integration"
plan: "01"
subsystem: "plum-backend"
tags: ["models", "migration", "schemas", "tests", "wave-0", "bom", "avl", "costing"]
dependency_graph:
  requires: ["05-04"]
  provides: ["plum_bom_item table", "plum_avl_link table", "plum_avl_price_break table", "migration 0006", "Phase-6 schemas", "Wave-0 test stubs"]
  affects: ["06-02", "06-03", "06-04", "06-05"]
tech_stack:
  added:
    - "openpyxl==3.1.5 (Excel export/import for PLUM-10)"
    - "Decimal + Numeric(18,6) columns for all cost/qty fields (first use in project)"
    - "UniqueConstraint (first use in PLUM models)"
  patterns:
    - "Three-zone Alembic migration (ADD cols → CREATE tables → cross-table FK)"
    - "Self-referential BomTreeNode schema with model_rebuild()"
    - "Wave-0 test stub pattern: collect + skip_if_no_db"
key_files:
  created:
    - "backend/alembic/versions/0006_plum_bom_costing.py"
    - "backend/tests/plum/test_bom.py"
    - "backend/tests/plum/test_avl.py"
    - "backend/tests/plum/test_costing.py"
    - "backend/tests/plum/test_import_export.py"
  modified:
    - "backend/app/modules/plum/models.py"
    - "backend/app/modules/plum/schemas.py"
    - "backend/requirements.txt"
decisions:
  - "Three-zone migration order: ADD columns first (Zone 1), CREATE tables (Zone 2), add cross-table FK (Zone 3) — ensures atomic DDL with correct FK dependency ordering"
  - "selected_vendor_link_id FK declared directly in PlumPartRevision ORM model (not deferred) — references plum_avl_link which SQLAlchemy resolves from the same metadata; migration uses three-zone to satisfy DB ordering"
  - "Wave-0 test stubs contain real assertion bodies (not bare pass) — encodes the requirement contract for Plan 06-02/03 to drive against"
metrics:
  duration: "466s (~8 minutes)"
  completed: "2026-06-30"
  tasks_completed: 3
  tasks_total: 3
  files_created: 5
  files_modified: 3
---

# Phase 06 Plan 01: PLUM BOM & Costing Data Foundation Summary

Three-table BOM/AVL schema + Alembic migration 0006 + Phase-6 Pydantic schemas + 17 Wave-0 backend test stubs covering PLUM-04 through PLUM-10.

## What Was Built

### Task 1 — Extend models.py + openpyxl dep (commit `3f1da80`)

Extended `backend/app/modules/plum/models.py` with:

- **PlumBomItem** (`plum_bom_item`): BOM directed edge table — `parent_revision_id` FK to `plum_part_revision`, `child_part_id` FK to `plum_part`, `qty Numeric(18,6)`, `ref_des String(500)`, `sort_order`, timestamps. `UniqueConstraint(parent_revision_id, child_part_id)` named `uq_plum_bom_item_parent_child` (T-06-03).
- **PlumAvlLink** (`plum_avl_link`): Part-to-vendor link — `part_id` FK to `plum_part`, `vendor_id` FK to `syerp_partner` (first cross-module FK), `vendor_part_number`, `preferred`, `notes`, `active` soft-delete. `UniqueConstraint(part_id, vendor_id)` named `uq_plum_avl_link_part_vendor` (T-06-03).
- **PlumAvlPriceBreak** (`plum_avl_price_break`): Price-break rows — `avl_link_id` FK to `plum_avl_link` with `ondelete=CASCADE` (T-06-02), `qty_threshold`, `unit_cost Numeric(18,6)`, `lead_days`, `sort_order`.
- **5 cost columns on PlumPartRevision** (after `obsoleted_at`): `material_cost`, `sale_price`, `released_cost_snapshot` (all `Numeric(18,6)` nullable), `selected_vendor_link_id String(36)` FK to `plum_avl_link` with `ondelete=SET NULL` (T-06-01), `selected_price_break_index Integer` nullable.
- Imports: added `Decimal` from stdlib, `Numeric` + `UniqueConstraint` from SQLAlchemy.
- No `relationship()` calls added (MissingGreenlet pitfall — maintained).
- Added `openpyxl==3.1.5` to `requirements.txt` (T-06-SC pre-approved in RESEARCH audit).

### Task 2 — Migration 0006 (commit `c7afcdd`)

Created `backend/alembic/versions/0006_plum_bom_costing.py`:

- `revision = "0006"`, `down_revision = "0005"` — chains to PLUM base tables.
- **Zone 1**: `op.add_column` five cost columns on `plum_part_revision`.
- **Zone 2**: `op.create_table` for `plum_avl_link` (with named FKs, UniqueConstraint, server_defaults), `plum_avl_price_break` (ondelete=CASCADE), `plum_bom_item` (UniqueConstraint). Indexes created after each table.
- **Zone 3**: `op.create_foreign_key("fk_plum_revision_selected_avl_link", ...)` from `plum_part_revision.selected_vendor_link_id` to `plum_avl_link.id` with `ondelete="SET NULL"` — Zone 3 because target table must exist first.
- **downgrade()**: drops FK constraint first, then tables in reverse dependency order (price_break → avl_link → bom_item), then drops the five added columns in reverse order.
- Parses as valid Python (`ast.parse` verified).

### Task 3 — Phase-6 schemas + Wave-0 test stubs (commit `931ae25`)

Extended `backend/app/modules/plum/schemas.py` with:
- `BomItemCreate`, `BomItemUpdate`, `BomItemRead`
- `BomTreeNode` (self-referential `children: list[BomTreeNode]`; `model_rebuild()` called; `from_attributes=False`)
- `FlatBomRow`, `WhereUsedRow`
- `PriceBreakCreate`, `PriceBreakRead`, `AvlLinkCreate`, `AvlLinkUpdate`, `AvlLinkRead`
- `CostUpdate`, `CostRead` (effective_cost, effective_cost_source, bom_rollup_cost, margin, margin_pct)
- `ImportRowError`, `ImportPreviewResponse`, `ImportCommitResponse`
- `RevisionRead` extended with 5 optional cost fields.

Created four Wave-0 backend test files:
- `test_bom.py`: 5 functions (PLUM-04/05/06)
- `test_avl.py`: 2 functions (PLUM-07)
- `test_costing.py`: 5 functions (PLUM-08/09)
- `test_import_export.py`: 5 functions (PLUM-10)

All 17 tests collect and skip cleanly without a live DB (verified via pytest output).

## Verification Results

```
models OK
migration OK
All acceptance criteria passed
17 tests collected, 17 skipped (No live database)
31 plum tests total (existing + new) — no collection errors
```

## Deviations from Plan

None — plan executed exactly as written. All three tasks completed within spec.

The FK declaration on `selected_vendor_link_id` in the ORM model references `plum_avl_link.id` directly (the plan specified this pattern). SQLAlchemy resolves the FK string reference at metadata finalization time, not at import time, so the forward reference works correctly across model files.

## Threat Mitigations Applied

| Threat | Mitigation | Where |
|--------|-----------|-------|
| T-06-01 Dangling revision→AVL FK | `ondelete=SET NULL` on `selected_vendor_link_id` | models.py + migration Zone 3 |
| T-06-02 Orphan price-break rows | `ondelete=CASCADE` on `avl_link_id` | models.py + migration Zone 2 |
| T-06-03 Duplicate BOM/AVL rows | `UniqueConstraint` on both tables | models.py + migration Zone 2 |
| T-06-04 Float precision | `Numeric(18,6)` for all cost/qty columns | models.py + migration |
| T-06-SC openpyxl legitimacy | Pre-approved in RESEARCH Package Legitimacy Audit | requirements.txt |

## Known Stubs

None — schemas are fully specified (not data-wired). Test stubs contain real assertion bodies encoding the requirement contracts; they fail gracefully with skip (not error) until Plans 06-02/03 implement the service/router.

## Self-Check: PASSED

Files exist:
- `backend/alembic/versions/0006_plum_bom_costing.py` — FOUND
- `backend/tests/plum/test_bom.py` — FOUND
- `backend/tests/plum/test_avl.py` — FOUND
- `backend/tests/plum/test_costing.py` — FOUND
- `backend/tests/plum/test_import_export.py` — FOUND

Commits:
- `3f1da80` — feat(06-01): extend PLUM models — FOUND
- `c7afcdd` — feat(06-01): author migration 0006 — FOUND
- `931ae25` — feat(06-01): add Phase-6 schemas and Wave 0 stubs — FOUND
