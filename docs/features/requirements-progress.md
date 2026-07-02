# Requirements Progress

Tracks completed requirements by phase, with implementing plans and evidence.

---

## PLUM Module

| Requirement | Description | Phase | Plans | Evidence | Status |
|-------------|-------------|-------|-------|----------|--------|
| PLUM-01 | User can create, view, edit, and delete parts | Phase 5 | 05-01, 05-02 | test_parts.py | Complete |
| PLUM-02 | User can search and filter parts | Phase 5 | 05-01, 05-02 | test_parts.py | Complete |
| PLUM-03 | User can create part revisions and advance a part through its status workflow | Phase 5 | 05-01, 05-02 | test_revisions.py | Complete |
| PLUM-04 | User can build a multi-level BOM and view it as an expandable tree | Phase 6 | 06-01, 06-02, 06-04, 06-05 | test_bom.py, BomTree.test.tsx | Complete |
| PLUM-05 | User can view a flat BOM with quantity roll-up across levels | Phase 6 | 06-01, 06-02, 06-04, 06-05 | test_bom.py, BomTree.test.tsx | Complete |
| PLUM-06 | User can run where-used analysis to see which assemblies consume a part | Phase 6 | 06-01, 06-02, 06-05 | test_bom.py, PartDetail.tsx Where Used card | Complete |
| PLUM-07 | User can link a part to one or more vendors (FK to SYERP vendors / AVL) | Phase 6 | 06-01, 06-02, 06-04, 06-05 | test_avl.py, AvlLinkSheet.tsx | Complete |
| PLUM-08 | User can set part pricing/cost and see cost roll-up across a BOM | Phase 6 | 06-01, 06-02, 06-05 | test_costing.py, PartDetail.tsx Cost & Margin card | Complete |
| PLUM-09 | User can view margin analysis for a product | Phase 6 | 06-01, 06-02, 06-05 | test_costing.py, PartDetail.tsx Cost & Margin card | Complete |
| PLUM-10 | User can import and export PLUM data as JSON and Excel | Phase 6 | 06-01, 06-03, 06-05 | test_import_export.py, ImportExport.test.tsx | Complete |

---

*Last updated: 2026-07-01 — Phase 6 (PLUM-04 through PLUM-10) completed*
