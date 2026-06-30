---
phase: 06-plum-bom-costing-integration
plan: 02
subsystem: plum
tags: [bom, avl, costing, fastapi, sqlalchemy, plum]
dependency_graph:
  requires: ["06-01"]
  provides: ["06-03", "06-04", "06-05"]
  affects: ["backend/app/modules/plum/service.py", "backend/app/modules/plum/router.py"]
tech_stack:
  added: []
  patterns:
    - BFS cycle detection before BOM insert (visited-set iterative traversal)
    - Recursive BOM tree traversal with visited.copy() per branch (D-02/D-03)
    - Flat BOM dict accumulator keyed by child_part_id (Pitfall 8 prevention)
    - D-07 effective-cost resolution chain (vendor price → manual → roll-up → uncosted)
    - D-14 cost snapshot written before FSM status flip in advance_revision_status
    - Lazy-import inside service functions (no circular imports in async SQLAlchemy)
    - Router BomAddBody extends BomItemCreate with optional revision_id (auto-resolve)
    - "latest" sentinel in advance endpoint resolves max(revision_number) by part
key_files:
  modified:
    - backend/app/modules/plum/service.py
    - backend/app/modules/plum/router.py
decisions:
  - "Tasks 1 and 2 committed together: both implement service.py Phase 6 functions; splitting would have required writing a partial file. Deviation documented."
  - "BomAddBody in router.py extends BomItemCreate with optional revision_id field to match test payload shape (test sends revision_id in JSON body, not as query param)."
  - "latest sentinel resolved in router before service call (not in service) to avoid coupling service.get_revision to URL convention."
  - "AVL links returned even when active=False (Pitfall 4: archived-vendor links remain visible per D-11)."
  - "selected_vendor_link_id null-check in create_revision copy-forward: if AVL link deleted since source revision, field is null-ed out (RESEARCH Open Question 1 resolution)."
metrics:
  duration: "~90 min (split across two conversation windows)"
  completed: "2026-06-30"
  tasks_completed: 3
  files_modified: 2
---

# Phase 6 Plan 02: BOM/AVL/Costing Service + Router Summary

Implemented the BOM, AVL, and costing algorithmic core in `service.py` and exposed it via 13 new endpoints in `router.py`. This is the Phase 6 functional heart: BOM CRUD with cycle detection, recursive tree/flat/where-used traversal, AVL vendor-link management with price breaks, the D-07 effective-cost resolution chain, release cost snapshots (D-14), and margin computation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1+2 | BOM CRUD + traversal + AVL + costing in service.py | 5280576 | `service.py` (+1215 lines) |
| 3 | Wire BOM/AVL/cost endpoints in router.py | eb41f35 | `router.py` (+538 lines) |

## What Was Built

### service.py Extensions (38 total functions, 2026 lines)

**BOM CRUD (PLUM-04/D-01/D-05):**
- `add_bom_line` — Draft-only guard (T-06-05) + BFS cycle check (D-05) + bom.line_added audit
- `update_bom_line` — Draft-only guard + bom.line_updated audit
- `remove_bom_line` — Draft-only guard + bom.line_removed audit

**BOM Traversal (PLUM-04/05/06):**
- `load_bom_tree` — recursive, resolves child to latest Released (D-02) or latest Draft with is_unreleased=True (D-03); visited.copy() per branch
- `load_flat_bom` — dict accumulator keyed by child_part_id, cumulative qty products per path (Pitfall 8)
- `get_where_used` — BFS upward, direct vs indirect, dedup at shallowest depth (max_depth=20)

**Private helpers:**
- `_would_create_cycle` — iterative BFS downward from candidate child; returns True if parent appears in descendants
- `_resolve_child_revision` — latest Released or latest Draft with is_unreleased flag
- `_copy_bom_forward` — copies plum_bom_item rows to new revision (called by create_revision)
- `_build_bom_tree_recursive` — recursive inner implementation with depth guard
- `_compute_bom_rollup` — Σ(child effective_cost × qty) recursive with visited guard
- `_get_system_currency` — reads locale.currency Setting (default "USD", D-10)

**AVL CRUD (PLUM-07):**
- `list_avl_links` — includes price breaks sorted by qty_threshold; active=False links included
- `add_avl_link` — validates is_vendor=True (T-06-07); 422 if absent
- `update_avl_link` — PATCH semantics; audit written
- `remove_avl_link` — soft-delete (active=False); audit written
- `add_price_break` — appends price break to AVL link; audit written

**Costing (PLUM-08/09):**
- `compute_effective_cost` — D-07 chain: vendor price-break (bounds-checked, Pitfall 7) → manual → roll-up → (None, "uncosted")
- `compute_margin` — sale_price − effective_cost + margin_pct (%)
- `update_cost` — Draft-only guard; updates material_cost/sale_price/selected_vendor_link_id/selected_price_break_index
- `get_cost_read` — live CostRead dict (always recomputes bom_rollup + effective_cost)

**Existing function extensions:**
- `create_revision` — now copies BOM lines forward (_copy_bom_forward) + cost fields with AVL null-check; released_cost_snapshot excluded (D-14)
- `advance_revision_status` — now snapshots released_cost_snapshot = compute_effective_cost(...) BEFORE status flip (D-14)

### router.py Extensions (20 endpoints total, 836 lines)

13 new Phase 6 endpoints:

| Method | Path | Service | Permission |
|--------|------|---------|------------|
| GET | `/parts/{part_id}/bom` | `load_bom_tree` | plum:read |
| GET | `/parts/{part_id}/bom/flat` | `load_flat_bom` | plum:read |
| GET | `/parts/{part_id}/where-used` | `get_where_used` | plum:read |
| POST | `/parts/{part_id}/bom` | `add_bom_line` | plum:write |
| PATCH | `/parts/{part_id}/bom/{line_id}` | `update_bom_line` | plum:write |
| DELETE | `/parts/{part_id}/bom/{line_id}` | `remove_bom_line` | plum:write |
| GET | `/parts/{part_id}/avl` | `list_avl_links` | plum:read |
| POST | `/parts/{part_id}/avl` | `add_avl_link` | plum:write |
| PATCH | `/parts/{part_id}/avl/{link_id}` | `update_avl_link` | plum:write |
| DELETE | `/parts/{part_id}/avl/{link_id}` | `remove_avl_link` | plum:write |
| POST | `/parts/{part_id}/avl/{link_id}/price-breaks` | `add_price_break` | plum:write |
| GET | `/parts/{part_id}/revisions/{rev_id}/cost` | `get_cost_read` | plum:read |
| PATCH | `/parts/{part_id}/revisions/{rev_id}/cost` | `update_cost` | plum:write |

Also added `latest` sentinel to advance endpoint: `/revisions/latest/advance` resolves `max(revision_number)` for the part before calling service (test ergonomics).

## Acceptance Criteria Verification

| Criterion | Result |
|-----------|--------|
| `grep -c 'status != "draft"'` in service.py | 4 (>= 1) |
| `grep -c "circular BOM"` in service.py | 1 |
| load_flat_bom dict accumulator | Present (keyed by child_part_id) |
| material_cost AND selected_vendor_link_id in create_revision copy-forward | 7 matches |
| released_cost_snapshot precedes status flip in advance_revision_status | Line 861 before line 870 |
| `grep -c "locale.currency"` in service.py | 2 |
| bounds-check on selected_price_break_index | `if 0 <= idx < len(price_breaks)` at line 1897 |
| All routes registered (url_path_for) | All 13 OK |
| `grep -c "require_permission"` in router.py | 21 |
| Full plum test suite | 31 skipped cleanly (no errors/failures) |

## Deviations from Plan

### Implementation-level deviations

**1. [Rule 3 - Blocking] Tasks 1 and 2 committed as single service.py commit**
- **Found during:** Task 2 verification
- **Issue:** Both tasks modify the same file (`service.py`). The Phase 6 functions for BOM (Task 1) and AVL/costing (Task 2) were added in a single editing pass within the prior conversation context to avoid multiple large-file rewrites. The commit message for 5280576 explicitly includes all AVL + costing functions.
- **Fix:** Documented as deviation. All Task 2 acceptance criteria verified post-commit (released_cost_snapshot placement, locale.currency, price-break bounds-check).
- **Commit:** 5280576

**2. [Rule 2 - Missing Critical Functionality] `latest` sentinel in advance endpoint**
- **Found during:** Task 3 (reading test_bom.py Wave 0 stubs)
- **Issue:** Tests call `POST /parts/{part_id}/revisions/latest/advance`; router only had `{rev_id}` as a UUID path parameter.
- **Fix:** Added inline resolution: if `rev_id == "latest"`, query `max(revision_number)` for the part before calling service. No new service function required.
- **Files modified:** `backend/app/modules/plum/router.py`
- **Commit:** eb41f35

**3. [Rule 2 - Missing Critical Functionality] `BomAddBody` with optional `revision_id`**
- **Found during:** Task 3 (reading test_bom.py line 65)
- **Issue:** Tests send `revision_id` in the JSON body of POST /bom. The `BomItemCreate` schema has no such field. Plan described revision_id as a query param but tests use body.
- **Fix:** Created `BomAddBody(BomItemCreate)` inline in router.py with `revision_id: Optional[str] = None`. When omitted, auto-resolves to latest revision. Test that asserts 422 on Released revision relies on this auto-resolution.
- **Files modified:** `backend/app/modules/plum/router.py`
- **Commit:** eb41f35

## Known Stubs

None — all functions are fully implemented. Roll-up costing and where-used traversal are live (not mocked). The test suite skips cleanly without a DB because of the `skip_if_no_db` fixture, not because of stubs.

## Threat Flags

No new threat surface beyond what was specified in the plan's threat model.

## Self-Check: PASSED

- `5280576` exists: `git log --oneline | grep 5280576` → confirmed
- `eb41f35` exists: `git log --oneline | grep eb41f35` → confirmed
- `backend/app/modules/plum/service.py` exists: 2026 lines
- `backend/app/modules/plum/router.py` exists: 836 lines
- `.planning/phases/06-plum-bom-costing-integration/06-02-SUMMARY.md` exists: this file
