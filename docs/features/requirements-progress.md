# Requirements Progress

Tracks completed requirements by phase, with implementing plans and evidence.

> **Evidence caveat (Phase 7, D-P7-4):** the PLUM pytest files below (`test_bom.py`,
> `test_avl.py`, `test_costing.py`, `test_import_export.py`, `test_parts.py`) have **never
> actually run** — a broken `skip_if_no_db` probe silently skipped them, which is how the
> `SyerpPartner` 500 shipped through Phase 6 marked "Complete". Harness repair is BACKLOG p1.
> Phase-7 status below reflects *verified* reality: code fixes proven by live-DB standalone
> proofs, and flow-level UI confirmation deferred to the v1.0 milestone UAT
> (`.zj/UAT-v1.0.md`, D-P7-5) — **not** claimed Complete on an unrun test.

---

## PLUM Module

| Requirement | Description | Phase | Plans | Evidence | Status |
|-------------|-------------|-------|-------|----------|--------|
| PLUM-01 | User can create, view, edit, and delete parts | Phase 5, 7 | 05-01, 05-02, 07 | Phase-7 numeric part# fix `1b8bfa1` — **proven live** (DB had `P100000` → generator returned `P100001`); `test_generate_part_number_digit_boundary` ships (runs once harness fixed) | Complete |
| PLUM-02 | User can search and filter parts | Phase 5 | 05-01, 05-02 | test_parts.py (Phase-5 UAT 10/10) | Complete |
| PLUM-03 | User can create part revisions and advance a part through its status workflow | Phase 5 | 05-01, 05-02 | test_revisions.py (Phase-5 UAT); Released-immutability spot-checked Phase-7 (UAT check 8) | Complete |
| PLUM-04 | User can build a multi-level BOM and view it as an expandable tree | Phase 6, 7 | 06-01, 06-02, 06-04, 06-05 | BomTree.tsx; UAT check 1 (Add Part on Draft) **passed** Phase-7; test_bom.py pending harness | Code done; UI UAT pending (check 2 for flat view) |
| PLUM-05 | User can view a flat BOM with quantity roll-up across levels | Phase 6 | 06-01, 06-02, 06-04, 06-05 | BomTree.tsx flat mode; test_bom.py pending harness | Code done; UI UAT pending (check 2) |
| PLUM-06 | User can run where-used analysis to see which assemblies consume a part | Phase 6 | 06-01, 06-02, 06-05 | PartDetail.tsx Where-Used card; test_bom.py pending harness | Code done; UI UAT pending (check 3) |
| PLUM-07 | User can link a part to one or more vendors (FK to SYERP vendors / AVL) | Phase 6, 7 | 06-01, 06-02, 06-04, 06-05, 07 | Runtime 500 fixed `5c33ed8` (Partner alias) — import resolves live, commit path passed a manual per-test run; AvlLinkSheet.tsx | Runtime fix landed & code-verified; UI UAT pending (checks 4, 9) |
| PLUM-08 | User can set part pricing/cost and see cost roll-up across a BOM | Phase 6 | 06-01, 06-02, 06-05 | Cost & Margin card; manual+roll-up live-verified (audit); vendor-price source now reachable (PLUM-07 fixed) | Code done; UI UAT pending (check 5) |
| PLUM-09 | User can view margin analysis for a product | Phase 6 | 06-01, 06-02, 06-05 | Cost & Margin card; margin calc live-verified (audit) | Code done; UI UAT pending (check 6) |
| PLUM-10 | User can import and export PLUM data as JSON and Excel | Phase 6, 7 | 06-01, 06-03, 06-05, 07 | Vendor-path 500 fixed `5c33ed8`; cache invalidation on commit `37b5f97` (tsc-clean, ImportExport tests pass) | Fixes landed & code-verified; UI UAT pending (checks 7, 10, 11) |

---

*Last updated: 2026-07-04 — Phase 7 (close v1.0 gaps): PLUM-01 defect resolved & proven live;
PLUM-04..10 code fixes landed & code-verified, flow-level UI confirmation deferred to v1.0
milestone UAT (D-P7-5). Prior "Complete" marks rested on tests that never ran (D-P7-4).*
