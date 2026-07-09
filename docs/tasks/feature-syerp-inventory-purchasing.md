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
- [ ] Human UAT — 10 of 12 checks (`.zj/UAT-v1.0.md`) — **owner runs**
- [ ] Tag `v1.0` at HEAD (D-M1-1) — blocked on the UAT above
