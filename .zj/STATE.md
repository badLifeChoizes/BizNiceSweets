# STATE — BizNiceSweets
Updated: 2026-07-09

## Position

- **Project:** BizNiceSweets
- **Step:** ship (PR open, awaiting merge)
- **Last update:** 2026-07-11
- **Next action:** Merge **PR #1** (https://github.com/badLifeChoizes/BizNiceSweets/pull/1) —
  `feature-syerp-inventory-purchasing` → `master`, a clean fast-forward (269 ahead, 0 behind).
  **Merge with a merge-commit or "Rebase and merge" — NOT squash**, or the `v1.0` tag (at
  `4b6fee4`, mid-history) would dangle off `master`. Branch + `v1.0` tag are pushed to origin.
  After merge: `/zj:retro 08` if not yet run, delete the merged branch, then `/zj:spec` +
  `/zj:plan 09` for v2.0 Phase 9.
- **Milestone:** v1.0 — Foundation + PLUM — **CLOSED + tagged `v1.0` 2026-07-11**.
  v2.0 Operations in progress (Phase 8 done + verified + retro'd).
- **Phase:** none active for v1.0 (Phase 7 archived to `.zj/history/v1.0/phases/`).
  Phase 8 (`.zj/phases/08-syerp-inventory-purchasing/`) belongs to v2.0 and stays active.
- **Branch:** `feature-syerp-inventory-purchasing` — carries Phases 7 + 8 + the milestone close.

## v1.0 milestone close — status

**Audit:** `.zj/MILESTONE-v1.0-AUDIT.md`, verdict **GAPS FOUND**, driven live against the running
stack. All four definition-of-done clauses (deploy / log in / vendors+customers / multi-level BOM
+ cost roll-up) proven at the API layer.

**Gaps triaged with the owner:**
| Gap | Severity | Disposition |
|---|---|---|
| **G1** Where-Used labelled *every* parent "Direct parent" (PLUM-06) | major, unprotected | **Fixed** `63ea954` — backend now emits `via_part_number`; UI keys off `indirect`. Guards: `PartDetail.test.tsx` (5), `test_bom.py`. Proven live 14/14. |
| **G2** Excel export 500 — `openpyxl` absent from the API image | blocker for UAT check 7 | **Fixed** by rebuilding `compose_api`. `/plum/export/excel` → 200, valid `.xlsx`. No code change. |
| **G3** live-DB pytest harness skips 98 tests | systemic | **Deferred** (owner-approved) — BACKLOG p1, D-P7-4, D-M1-2. Not PLUM-only: auth 38, plum 34, syerp 17, core 7. |

**Records produced:**
- `CHANGELOG.md` — generated from commits, 98 `feat:`/`fix:` entries grouped by phase (new file;
  never hand-edit).
- `.zj/logs/milestone-v1.0.md` — work log: ≈47 h over 30 inferred sessions, 224 v1.0-era commits.
- `.zj/LEARNINGS.md` — "Milestone v1.0" roll-up.
- `.zj/DECISIONS.md` — regenerated `## Index` (44 entries) + **D-M1-1** (tag placement),
  **D-M1-2** (G1/G2 fixed, G3 deferred).
- `zj doctor`: **18 errors → 0** (19 warnings remain, all BACKLOG tag-format).

## What is left before the tag

**Human UAT round 1 ran 2026-07-11** (owner). Passed checks 3, 5, 6, 12. Surfaced three UI
defects — **D1** flat-BOM cost footer (280 vs 110), **D2** AVL "Add Vendor" 500 on a duplicate,
**D3** dead import file picker — all now **fixed** (`a88431c`, D-M1-3), tested, and D2 proven live.
**Round 2 owed:** re-run checks **2, 4/9, 7, 10, 11**. These plus the already-passed 1, 3, 5, 6, 8,
12 close all twelve. Residue is genuine visual confirmation: red styling (6 ✓), toast absence
(9, 10), badges/footer (2, 4), visible no-refresh (11).

Stack must be up: `podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d`
(rebuild `api` if the stack is recreated, or G2 returns). `alembic current` == `0008 (head)`.

Once the UAT passes: `git tag -a v1.0 -m "Foundation + PLUM"` at HEAD (per **D-M1-1**, that tree
also contains Phase 8 / v2.0 work — this is recorded, not accidental).

## Standing debt (carried into v2.0)

1. **Live-DB pytest harness never runs** — 98 skips across every module (BACKLOG p1, D-P7-4).
   Regression protection currently rests on `backend/scripts/verify_*.py` (66 assertions) and the
   Vitest suite, both of which do run.
2. **Both lint gates non-functional** (BACKLOG p1) — ESLint 10 is flat-config-only but the repo
   ships `.eslintrc.cjs` with a removed `--ext` flag and no `@typescript-eslint` parser deps;
   `ruff` is pinned in `requirements-dev.txt` but not installed in `backend/.venv`.
3. **No CI** (BACKLOG p1) — the `SyerpPartner` bug shipped through four plans because live-DB
   tests never ran.
4. **`master` is 263 commits behind** at `f4e2bd3` (2025-12-20) and contains no `backend/`,
   `frontend/`, or `.zj/`. The entire re-platform is unmerged; the merge story is unresolved
   (`/zj:ship`, D-P7-3 / D-P8-11).

## After the tag

1. `/zj:ship` — resolve the `master` merge story for the branch carrying Phases 7 + 8.
2. `/zj:spec` — refine the v2.0 definition of done before planning Phase 9.
3. `/zj:plan 09` — SYERP AP/AR & reporting (SYERP-12).

## Adoption note

Adopted from GSD on 2026-07-04. Prior planning system archived at `archive/planning-gsd/`
(phases 01–07, REQUIREMENTS, ROADMAP, STATE, v1.0-MILESTONE-AUDIT, codebase snapshots) and
`archive/planning-docs/` (program ROADMAP.md, decisions.md). `.zj/` is self-contained — the
archive is history, not a dependency.
