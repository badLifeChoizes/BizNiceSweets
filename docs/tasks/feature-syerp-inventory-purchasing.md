# Task — feature-syerp-inventory-purchasing

Branch carries Phase 7 (v1.0 gap closure) + Phase 8 (v2.0 inventory & purchasing),
and now the **v1.0 milestone close** (`/zj:milestone`).

## Milestone v1.0 close — gap closure

- [x] Milestone audit vs definition of done (`.zj/MILESTONE-v1.0-AUDIT.md`) — **GAPS FOUND**
- [x] **G1** where-used UI defect — parents all rendered "Direct parent" (PLUM-06)
  - [x] Backend: `WhereUsedRow.via_part_number` added (`schemas.py`)
  - [x] Backend: BFS carries the intermediate part (`service.py:get_where_used`)
  - [x] Frontend: label + sort key off `indirect`, not the absence of `via_part_number`
  - [x] Regression tests: `PartDetail.test.tsx` (5), `test_bom.py` (via-part assertions)
  - [x] Proven live: 14/14 assertions (where-used names the via part)
- [x] **G2** Excel export 500 — `openpyxl` missing from the API image
  - [x] Rebuilt `compose_api` image; `openpyxl 3.1.5` present
  - [x] Proven live: `/plum/export/excel` → 200, payload is a real `.xlsx`
- [x] Full regression: 66 live-DB assertions, backend 90 passed/98 skipped, frontend 54 passed, `tsc -b` clean
- [x] Doctor artifact-format fixes (`STATE.md` required fields)
- [x] **G3** broken pytest DB harness (98 skips) — deferred by owner, BACKLOG p1 / D-P7-4 / D-M1-2
- [x] Records: CHANGELOG (98 entries), work log, learnings roll-up, decisions index (44)
- [x] Archive Phase 7 → `.zj/history/v1.0/phases/`; roll ROADMAP + PROJECT + STATE forward
- [x] Human UAT round 1 (owner, 2026-07-11) — found 3 UI defects; checks 3/5/6/12 passed
- [x] **D1** flat-BOM cost footer double-count (280→110) — footer shows `bom_rollup_cost`; BomTree tests
- [x] **D2** AVL add-vendor 500 on duplicate — 409 on active dup, reactivate on re-add; proven live; tests
- [x] **D3** import file picker dead — drag-drop + real Choose File button; ImportExport tests
- [x] Regression: frontend 59 passed, backend 90/100-skip, tsc clean, 5 verify scripts + AVL live PASS
- [x] Human UAT round 2 — owner satisfied; authorized the tag 2026-07-11
- [x] Tag `v1.0` at HEAD (D-M1-1) — applied at `4b6fee4`
