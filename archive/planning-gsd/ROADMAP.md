### Phase 6: PLUM BOM, Costing & Integration

**Goal**: Users can build multi-level product structures, run cost analysis, link parts to vendors, and move data in and out of PLUM
**Depends on**: Phase 5
**Requirements**: PLUM-04, PLUM-05, PLUM-06, PLUM-07, PLUM-08, PLUM-09, PLUM-10
**Success Criteria** (what must be TRUE):

  1. User can add child parts to a parent part to build a multi-level BOM and view it as an expandable tree
  2. User can view a flat BOM with total quantity rolled up across all levels for each child part
  3. User can run where-used analysis on a part and see every assembly that directly or indirectly uses it
  4. User can link a part to one or more vendors from the SYERP vendor list (AVL), and those links are persisted
  5. User can set a cost on a part and see the cost roll up through the BOM tree to the top-level assembly
  6. User can view a margin analysis showing cost vs. price for a finished product
  7. User can export PLUM data as JSON or Excel and re-import it, restoring the same data set

**Plans**: 5 plans
Plans:
**Wave 1**

- [x] 06-01-PLAN.md — Backend data foundation: PlumBomItem/PlumAvlLink/PlumAvlPriceBreak models + 5 revision cost columns, migration 0006, openpyxl dep, Wave 0 backend test stubs (PLUM-04..10)

**Wave 2** *(blocked on Wave 1)*

- [x] 06-02-PLAN.md — Backend service + router: BOM CRUD/tree/flat/where-used + cycle detection, AVL CRUD, effective-cost chain + margin + release snapshot, copy-forward; greens test_bom/test_avl/test_costing

**Wave 3** *(blocked on Wave 2 — same service.py/router.py files)*

- [x] 06-03-PLAN.md — Backend import/export: lossless JSON + multi-sheet Excel export, two-step preview/commit upsert import (never-delete, 10MB guard, cross-ref validation); greens test_import_export

**Wave 4** *(blocked on Wave 2)*

- [x] 06-04-PLAN.md — Frontend components: Tooltip install, BomTree (tree + flat) + smoke test, BomLineSheet (part search + cycle error), PriceBreakEditor, AvlLinkSheet (vendor search)

**Wave 5** *(blocked on Waves 3 + 4)*

- [ ] 06-05-PLAN.md — Frontend integration: PartDetail four cards (BOM/AVL/Cost&Margin/Where-Used), Import/Export page + 3-step flow, PlumNav tab, App route, requirements-progress update, human-verify checkpoint

**UI hint**: yes

### Phase 7: Close v1.0 gaps: fix PLUM/SYERP Partner import (PLUM-07/10), part-number ordering (PLUM-01), import cache invalidation; verify Phase 6

**Goal:** PLUM part-to-vendor links (AVL) and JSON/Excel import-export work end-to-end without runtime errors, auto part-number generation is numerically correct past a digit-width boundary, the Parts List refreshes immediately after an import commit, and Phase 6's PLUM-04..10 flows are human-verified with traceability reconciled.
**Requirements**: PLUM-01, PLUM-04, PLUM-05, PLUM-06, PLUM-07, PLUM-08, PLUM-09, PLUM-10 (+ CORE-01, CORE-09 traceability reconciliation)
**Depends on:** Phase 6
**Plans:** 4 plans

Plans:
**Wave 1** *(parallel — disjoint files)*

- [ ] 07-01-PLAN.md — Backend service.py fixes: alias Partner as SyerpPartner at 4 sites (PLUM-07/10/08), numeric-safe generate_part_number (PLUM-01), + live-DB regression coverage
- [ ] 07-02-PLAN.md — Frontend: invalidate ['plum','parts'] on import-commit success so the Parts List refreshes without manual reload (PLUM-10)

**Wave 2** *(blocked on Wave 1)*

- [ ] 07-03-PLAN.md — Consolidated human-verify: 7 PLUM flows (PLUM-04..10) + 4 Phase-7 regression checks; supersedes the unrun 06-05 Task 4 checkpoint

**Wave 3** *(blocked on Wave 2)*

- [ ] 07-04-PLAN.md — Reconcile REQUIREMENTS.md + docs/features/requirements-progress.md against the verified outcome (PLUM-04..10, CORE-01, CORE-09)
