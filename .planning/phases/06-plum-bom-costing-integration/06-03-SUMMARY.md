---
phase: 06-plum-bom-costing-integration
plan: 03
subsystem: plum
tags: [import, export, openpyxl, fastapi, sqlalchemy, plum, plum-10]
dependency_graph:
  requires: ["06-02"]
  provides: ["06-04", "06-05"]
  affects:
    - "backend/app/modules/plum/service.py"
    - "backend/app/modules/plum/router.py"
tech_stack:
  added:
    - "openpyxl==3.1.5 (already in requirements.txt from 06-01; installed in venv for 06-03)"
  patterns:
    - "build_json_export: full lossless dataset serialization (Decimal as str, no float)"
    - "generate_excel_export: three-sheet openpyxl workbook (Parts/BOM/AVL) from dict"
    - "Two-pass import validation (RESEARCH Pitfall 6): file-declared set union DB set"
    - "Upsert-never-delete import commit: select-before-insert-or-update, price breaks replace-all"
    - "Stateless re-parse on commit (RESEARCH Open Question 2 resolution)"
    - "StreamingResponse from BytesIO for both JSON and Excel exports"
    - "UploadFile + 10MB guard (T-06-11) in all three import endpoints"
    - "/import/validate alias for /import/preview (Wave-0 test stubs use /validate)"
key_files:
  modified:
    - "backend/app/modules/plum/service.py"
    - "backend/app/modules/plum/router.py"
decisions:
  - "BOM sheet named 'BOM' (not 'BOMs') — Wave-0 test stub asserts exact 'BOM' string; plan said 'BOMs' but test wins for live correctness"
  - "parse_excel_import accepts both 'BOM' and 'BOMs' sheet names for round-trip compatibility"
  - "Added /import/validate as alias for /import/preview because Wave-0 stubs call /validate not /preview"
  - "Stateless commit: client re-sends file; server re-parses and re-validates (D-18 Open Question 2 resolution per RESEARCH)"
  - "Price break rows in commit_import use delete-and-reinsert (replace-all semantics); parts/revisions/BOM/AVL rows are never deleted (D-17)"
  - "openpyxl symlinked from main project venv (.claude/worktrees/.../backend/.venv -> backend/.venv) since worktree shares package install"
metrics:
  duration: "~35 min"
  completed: "2026-07-01"
  tasks_completed: 3
  files_modified: 2
---

# Phase 6 Plan 03: Import/Export Pipeline Summary

Implemented the full PLUM-10 import/export pipeline: lossless JSON export, three-sheet Excel export (openpyxl), and two-step preview-then-commit import with upsert-never-delete semantics, cross-reference validation, 10 MB upload guard, and RBAC + audit.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1+2 | JSON/Excel export + import parse+validate+commit in service.py | cadbc70 | `service.py` (+969 lines) |
| 3 | Wire export+import endpoints in router.py | 280a31e | `router.py` (+227 lines) |

## What Was Built

### service.py Extensions (2995 total lines, +969 from 06-03)

**Export functions (PLUM-10/D-16):**
- `build_json_export(db)` — queries all PlumPart + revisions + BOM + AVL + price breaks, serializes raw stored cost columns (Decimal → str, no float), returns lossless dict with `schema_version=1` and `exported_at` ISO-8601 timestamp
- `generate_excel_export(data: dict) -> bytes` — openpyxl three-sheet workbook: Parts (header row + one row per part with latest revision description), BOM (one row per BOM line across all parts/revisions), AVL (denormalized one row per price break); values-only (T-06-12: no formula execution)

**Import parsing (PLUM-10/D-15):**
- `parse_json_import(content: bytes) -> dict` — JSON.loads with 422 on malformed input
- `parse_excel_import(content: bytes) -> dict` — openpyxl read-only+data-only (T-06-12); reconstructs parts/revisions/BOM/AVL from three sheets into the same normalized dict as JSON export

**Import validate/preview (PLUM-10/D-18 step 1 — NO DB WRITES):**
- `validate_import(db, data) -> ImportPreviewResponse` — two-pass cross-reference check (RESEARCH Pitfall 6): Pass 1 collects file-declared part_numbers; Pass 2 validates each part/BOM/AVL row against DB ∪ file set; flags unknown BOM child parts and unknown SYERP vendor_codes as `ImportRowError(field="vendor_id")`; counts new vs. updated on stable keys; performs NO writes

**Import commit (PLUM-10/D-17/D-18 step 2):**
- `commit_import(db, data, actor_id) -> ImportCommitResponse` — re-validates (Pitfall 5: stateless re-parse, no client trust); upserts PlumPart by part_number; upserts PlumPartRevision by (part_id, revision_label); upserts PlumBomItem by (parent_revision_id, child_part_id); upserts PlumAvlLink by (part_id, vendor_id); price breaks replace-all per AVL link; NEVER deletes parts/revisions/BOM/AVL absent from file (D-17); writes `plum.imported` audit event

### router.py Extensions (1062 total lines, +227 from 06-03)

6 new endpoints:

| Method | Path | Service | Permission |
|--------|------|---------|------------|
| GET | `/export/json` | `build_json_export` | plum:read |
| GET | `/export/excel` | `generate_excel_export` | plum:read |
| POST | `/import/preview` | `validate_import` | plum:write |
| POST | `/import/validate` | `validate_import` (alias) | plum:write |
| POST | `/import/commit` | `commit_import` | plum:write |

All three import endpoints include a 10 MB upload guard (T-06-11: `413 Request Entity Too Large`), `.json`/`.xlsx` dispatch (422 on unsupported type), and the write endpoints gate `plum:write`.

## Acceptance Criteria Verification

| Criterion | Result |
|-----------|--------|
| openpyxl importable | OK (3.1.5 installed) |
| build_json_export and generate_excel_export importable | OK |
| parse_json_import, parse_excel_import, validate_import, commit_import importable | OK |
| generate_excel_export sheet names | `['Parts', 'BOM', 'AVL']` |
| Routes registered (OpenAPI spec) | /plum/export/json, /plum/export/excel, /plum/import/preview, /plum/import/validate, /plum/import/commit — all present |
| require_permission count in router.py | 26 (>= 1 per endpoint) |
| 10 MB guard count in router.py | 3 (preview + validate + commit) |
| No hard-delete of parts/revisions/BOM/AVL in commit_import | Confirmed — only `await db.delete(old_pb)` for price break rows |
| Full plum test suite | 31 skipped cleanly (no errors/failures) |

## Deviations from Plan

### 1. [Rule 1 - Bug] BOM sheet named "BOM" instead of "BOMs"

- **Found during:** Task 1 verification (test file review)
- **Issue:** The plan acceptance criteria said sheet names `["Parts","BOMs","AVL"]`, but the Wave-0 test stub (`test_import_export.py` line 99) asserts `"BOM" in sheet_names` — Python list `in` checks equality, so `"BOM" in ["BOMs"]` returns `False`.
- **Fix:** Used `"BOM"` as the sheet name to match the test. `parse_excel_import` accepts both `"BOM"` and `"BOMs"` for round-trip compatibility with files exported by other tools.
- **Files modified:** `backend/app/modules/plum/service.py`
- **Commit:** cadbc70

### 2. [Rule 2 - Missing Critical Functionality] Added `/import/validate` alias endpoint

- **Found during:** Task 3 (reading Wave-0 test stubs — `test_import_export.py` line 132 uses `/import/validate`)
- **Issue:** The plan specified `/import/preview` as the endpoint name. The Wave-0 stubs from Plan 01 call `/import/validate`. Without this alias, all three import tests would fail with 404.
- **Fix:** Added a `/import/validate` endpoint with identical behavior to `/import/preview`. The plan-specified `/import/preview` endpoint also exists.
- **Files modified:** `backend/app/modules/plum/router.py`
- **Commit:** 280a31e

### 3. [Rule 3 - Blocking] Created venv symlink in worktree

- **Found during:** Task 1 verification
- **Issue:** The worktree has no `.venv` — it shares the main project's installed packages. Verification commands inside the worktree failed with `ModuleNotFoundError: No module named 'openpyxl'` (and env var errors without the symlink).
- **Fix:** Created `backend/.venv -> /home/zack/Projects/BizNiceSweets/backend/.venv` symlink. Also ran `pip install openpyxl==3.1.5` in the shared venv (it was in requirements.txt but not installed).
- **No files committed** (symlink is runtime-only, not tracked by git).

## Known Stubs

None — all functions are fully implemented. Export serializes live DB data. Import preview and commit both query the DB. The test suite skips cleanly without a DB because of the `skip_if_no_db` fixture, not because of stubs.

## Threat Flags

No new threat surface beyond the plan's threat model. All seven threat mitigations (T-06-11 through T-06-17) are implemented:

| Threat | Mitigation | Where |
|--------|-----------|-------|
| T-06-11 DoS oversized upload | 10 MB guard → 413 before parsing | router.py (3 endpoints) |
| T-06-12 Malicious Excel formula | `load_workbook(read_only=True, data_only=True)` | service.py parse_excel_import |
| T-06-13 Import overwrites/deletes | Upsert on stable keys; NEVER delete parts/revisions/BOM/AVL | service.py commit_import |
| T-06-14 Unknown AVL vendor | validate_import two-pass checks vendor_code in syerp_partner | service.py validate_import |
| T-06-15 Cost exfiltration via export | export gated require_permission("plum:read") + plum.exported audit | router.py export endpoints |
| T-06-16 Unauthorized import write | import endpoints gate require_permission("plum:write") | router.py import endpoints |
| T-06-17 SQL injection via import values | All writes via SQLAlchemy ORM parameterized inserts; no raw SQL interpolation | service.py commit_import |

## Self-Check: PASSED

Files exist:
- `backend/app/modules/plum/service.py` (2995 lines) — FOUND
- `backend/app/modules/plum/router.py` (1062 lines) — FOUND
- `.planning/phases/06-plum-bom-costing-integration/06-03-SUMMARY.md` — FOUND (this file)

Commits:
- `cadbc70` — feat(06-03): implement JSON/Excel export and import parse+validate+commit — FOUND
- `280a31e` — feat(06-03): wire export+import endpoints in router.py — FOUND
