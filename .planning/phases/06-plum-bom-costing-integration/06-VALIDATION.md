---
phase: 6
slug: plum-bom-costing-integration
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-29
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

### Backend (pytest)

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| **Config file** | `backend/pyproject.toml` (`asyncio_mode = "auto"`, `testpaths = ["tests"]`) |
| **Runner** | `backend/.venv/bin/pytest` (project virtualenv) |
| **Quick run command** | `cd backend && .venv/bin/pytest tests/plum/ -x -q` |
| **Full suite command** | `cd backend && .venv/bin/pytest tests/ -q` |
| **DB-dependent tests** | take the `skip_if_no_db` fixture; skip cleanly (not error) when no PostgreSQL is reachable |
| **Estimated runtime** | ~30 seconds (plum subset), ~60 seconds (full) |

### Frontend (Vitest)

| Property | Value |
|----------|-------|
| **Framework** | Vitest ^4.1.9 + @testing-library/react ^16.3.2 |
| **Config file** | `frontend/vite.config.ts` |
| **Quick run command** | `cd frontend && npm test -- --run src/routes/plum/` |
| **Full suite command** | `cd frontend && npm test -- --run` |
| **Type gate** | `cd frontend && npx tsc --noEmit -p tsconfig.json` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** backend → `cd backend && .venv/bin/pytest tests/plum/ -x -q`; frontend → `cd frontend && npx tsc --noEmit && npm test -- --run src/routes/plum/`
- **After every plan wave:** `cd backend && .venv/bin/pytest tests/ -q && cd ../frontend && npm test -- --run`
- **Before `/gsd:verify-work`:** full backend + frontend suites must be green (or clean-skip where no DB)
- **Max feedback latency:** ~60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | PLUM-04..10 | T-06-01 / T-06-02 / T-06-03 | import smoke | `cd backend && .venv/bin/python -c "from app.modules.plum.models import PlumBomItem, PlumAvlLink, PlumAvlPriceBreak, PlumPartRevision; assert hasattr(PlumPartRevision,'material_cost') and hasattr(PlumPartRevision,'selected_vendor_link_id'); print('models OK')"` | ✅ | ⬜ pending |
| 06-01-02 | 01 | 1 | PLUM-04..10 | T-06-01 / T-06-02 | migration parse | `cd backend && .venv/bin/python -c "import ast; src=open('alembic/versions/0006_plum_bom_costing.py').read(); ast.parse(src); assert 'down_revision' in src and '\"0005\"' in src and 'plum_bom_item' in src and 'plum_avl_link' in src and 'plum_avl_price_break' in src and 'SET NULL' in src and 'CASCADE' in src; print('migration OK')"` | ✅ | ⬜ pending |
| 06-01-03 | 01 | 1 | PLUM-04..10 | T-06-SC | unit (collect-only) | `cd backend && .venv/bin/pytest tests/plum/test_bom.py tests/plum/test_avl.py tests/plum/test_costing.py tests/plum/test_import_export.py --collect-only -q` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 2 | PLUM-04, PLUM-05, PLUM-06 | T-06-05 / T-06-06 | integration | `cd backend && .venv/bin/pytest tests/plum/test_bom.py -q` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 2 | PLUM-07, PLUM-08, PLUM-09 | T-06-07 / T-06-09 / T-06-10 | integration + unit | `cd backend && .venv/bin/pytest tests/plum/test_avl.py tests/plum/test_costing.py -q` | ❌ W0 | ⬜ pending |
| 06-02-03 | 02 | 2 | PLUM-04..09 | T-06-08 | integration (routes) | `cd backend && .venv/bin/python -c "from app.main import app; ..." && .venv/bin/pytest tests/plum/ -q` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 3 | PLUM-10 | T-06-15 | integration | `cd backend && .venv/bin/pytest tests/plum/test_import_export.py -q -k "export"` | ❌ W0 | ⬜ pending |
| 06-03-02 | 03 | 3 | PLUM-10 | T-06-13 / T-06-14 / T-06-17 | integration | `cd backend && .venv/bin/pytest tests/plum/test_import_export.py -q` | ❌ W0 | ⬜ pending |
| 06-03-03 | 03 | 3 | PLUM-10 | T-06-11 / T-06-12 / T-06-16 | integration (routes) | `cd backend && .venv/bin/python -c "from app.main import app; ..." && .venv/bin/pytest tests/plum/ -q` | ❌ W0 | ⬜ pending |
| 06-04-01 | 04 | 4 | PLUM-04, PLUM-05 | T-06-18 / T-06-19 | unit (React) | `cd frontend && test -f src/components/ui/tooltip.tsx && npx tsc --noEmit -p tsconfig.json && npm test -- --run src/routes/plum/components/BomTree.test.tsx` | ❌ W0 | ⬜ pending |
| 06-04-02 | 04 | 4 | PLUM-04 | T-06-19 / T-06-20 | type + grep gate | `cd frontend && npx tsc --noEmit -p tsconfig.json && grep -c "Save Line" src/routes/plum/components/BomLineSheet.tsx && grep -c "circular BOM" src/routes/plum/components/BomLineSheet.tsx` | N/A | ⬜ pending |
| 06-04-03 | 04 | 4 | PLUM-07 | T-06-19 | type + grep gate | `cd frontend && npx tsc --noEmit -p tsconfig.json && grep -c "Add Price Break" src/routes/plum/components/PriceBreakEditor.tsx && grep -c "Save Vendor Link" src/routes/plum/components/AvlLinkSheet.tsx && grep -c "is_vendor" src/routes/plum/components/AvlLinkSheet.tsx` | N/A | ⬜ pending |
| 06-05-01 | 05 | 5 | PLUM-04..09 | T-06-21 | type + grep gate | `cd frontend && npx tsc --noEmit -p tsconfig.json && grep -c "Bill of Materials" src/routes/plum/PartDetail.tsx && grep -c "Approved Vendor List" ... && grep -c "Cost & Margin" ... && grep -c "Where Used" ...` | N/A | ⬜ pending |
| 06-05-02 | 05 | 5 | PLUM-10 | T-06-22 / T-06-23 / T-06-24 | unit (React) | `cd frontend && npx tsc --noEmit -p tsconfig.json && grep -c "import-export" src/routes/plum/components/PlumNav.tsx && grep -c "import-export" src/App.tsx && npm test -- --run src/routes/plum/ImportExport.test.tsx` | ❌ W0 | ⬜ pending |
| 06-05-03 | 05 | 5 | PLUM-04..10 | — | full suite gate | `cd backend && .venv/bin/pytest tests/ -q; cd ../frontend && npm test -- --run; grep -c "PLUM-10" docs/features/requirements-progress.md` | N/A | ⬜ pending |
| 06-05-04 | 05 | 5 | PLUM-04..10 | T-06-21 | manual (human-verify) | see Manual-Only Verifications | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Test Exists column: ✅ = verifier already exists; ❌ W0 = Wave 0 must create the test file/stub first; N/A = grep/type/import gate, no pytest/vitest file required.*

### Canonical Wave 0 test functions (must match Plan 06-01 Task 3 stubs and RESEARCH.md test map exactly)

| File | Functions | Count |
|------|-----------|-------|
| `backend/tests/plum/test_bom.py` | test_add_bom_line, test_bom_line_released_immutable, test_bom_cycle_detection, test_flat_bom_shared_part, test_where_used_indirect | 5 |
| `backend/tests/plum/test_avl.py` | test_add_avl_link, test_avl_link_non_vendor | 2 |
| `backend/tests/plum/test_costing.py` | test_effective_cost_vendor, test_effective_cost_manual, test_effective_cost_rollup, test_release_snapshots_cost, test_margin_computation | 5 |
| `backend/tests/plum/test_import_export.py` | test_export_json, test_export_excel_sheets, test_import_preview_valid, test_import_preview_unknown_vendor, test_import_commit_no_delete | 5 |
| `frontend/src/routes/plum/components/BomTree.test.tsx` | empty-state render, one-row render | 2 |

---

## Wave 0 Requirements

- [ ] `backend/tests/plum/test_bom.py` — stubs for PLUM-04/05/06 (5 functions, see canonical table)
- [ ] `backend/tests/plum/test_avl.py` — stubs for PLUM-07 (2 functions)
- [ ] `backend/tests/plum/test_costing.py` — stubs for PLUM-08/09 (5 functions)
- [ ] `backend/tests/plum/test_import_export.py` — stubs for PLUM-10 (5 functions)
- [ ] `frontend/src/routes/plum/components/BomTree.test.tsx` — tree/flat render smoke test (created in Plan 06-04)

All five test stub files are created in **Wave 0 (Plan 06-01 Task 3 for the four backend files; Plan 06-04 Task 1 for BomTree.test.tsx)**. Backend stubs MUST collect under pytest and skip cleanly without a live DB; they go green as Plans 02/03 implement the behavior.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Seven ROADMAP success criteria + Released-revision immutability (BOM tree add/expand, flat roll-up footer, where-used direct/indirect labels, AVL vendor link + preferred, effective-cost source transitions, margin/negative-margin color, JSON+Excel export/round-trip import with no deletes + >10 MB rejection, frozen "Released at" cost) | PLUM-04..10 | Visual/interactive UI behavior across the running stack — tree expand/collapse, currency suffix, download files, drag-drop import preview, and red negative-margin styling cannot be asserted by automated unit tests | Run the stack (Vite dev overlay at http://localhost:5173 against the running API). Follow the 7-step + immutability script in Plan 06-05 Task 4 `<how-to-verify>`. Blocking human-verify checkpoint (`gate="blocking"`); user types "approved". |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (the one human-verify task, 06-05-04, is a deliberate `checkpoint:human-verify` for UI criteria)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every code task has an automated command; the only manual task is the terminal checkpoint)
- [x] Wave 0 covers all MISSING references (4 backend stub files + BomTree.test.tsx)
- [x] No watch-mode flags (all commands use `--run` / `-q`, none use `--watch`)
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-30
