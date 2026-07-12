# STATE — BizNiceSweets
Updated: 2026-07-11 (Phase 9a verified + tagged `zj/good-09a-gl-posting-engine`; fix-loop artifacts committed through `593cf58`)

## Position

- **Project:** BizNiceSweets
- **Step:** Phase 9a **VERIFIED (PASS)** → next is `/zj:retro 09a` (lessons worth keeping), then `/zj:plan 09b`
- **Last update:** 2026-07-11
- **Next action:** `/zj:retro 09a` — Phase 9a passed `/zj:verify` after a fix loop worth capturing,
  then `/zj:plan 09b`. **Phase 9a is verified and tagged `zj/good-09a-gl-posting-engine`.** It
  delivered SYERP-12 **AC1/AC2/AC3 + AC8/AC9**: double-entry JournalEntry/JournalLine (append-only,
  reversal via self-FK), derived balances + account register, the manual general-journal UI, and the
  crux — PO `receive_line` atomically posts a balanced **Dr 1130 / Cr 2150** JE at receipt cost
  (seeded GR/IR 2150). Branch `feature-syerp-gl-posting-engine` off `master` (D-P9a-2).
  - **Verify fix-loop (2026-07-11):** two majors fixed — **M1** a zero-cost PO receipt (`unit_cost=0`)
    self-rejected the all-zero JE and rolled back the whole receipt (Phase-8 regression) → now skips
    the GL post; **M2** no double-reversal guard let the derived control account diverge from
    inventory → now 409. Plus **m5** entry-targeted receipt audit and **m7** docs. The two mandated
    criteria-become-tests landed: `verify_gl.py` grew the atomicity-rollback / zero-cost / double-
    reversal scenarios (**28/28**) and a **new `verify_gl_api.py`** pins the audit rows + 403/401
    RBAC over live HTTP (**9/9**). Phase-8 regression unchanged, `test_gl_journal.py` 13, FE 64/64.
    Minors deferred → PLAN.md `## Noticed` (FE reverse-action Vitest, server_default drift,
    entry_date UTC, MAP full refresh, no DESIGN.md).
  - **Phase 9 split (D-P9a-1..5):** 9a done → `/zj:plan 09b` (AP bills/match/payments, AC4/AC5) →
    `/zj:plan 09c` (AP aging + statements, AC6/AC7). AR stays out (SYERP-13 → CRUMB, D-P9-4).
- **Phase-9 spec (2026-07-11):** owner chose full subledger→GL auto-posting (D-P9-1) over
  document-only aging; AP = vendor bill matched to PO receipts + payments (D-P9-2); GR/IR clearing
  posting model (D-P9-3, CoA account codes to confirm at plan time); AR deferred to CRUMB (D-P9-4,
  new SYERP-13); v2.0 DoD unchanged, MOUSSE stays required (D-P9-5).
- **Ship record (2026-07-11):** **PR #1 MERGED** via local fast-forward
  (`feature-syerp-inventory-purchasing` → `master`, `f4e2bd3..a5ad44b`). Master now carries the
  full re-platform (Phases 1–8); `v1.0` tag (`4b6fee4`) pushed and confirmed an ancestor of
  `master`. FF chosen over GitHub's rebase-button so commit SHAs — and thus the tag — were
  preserved. The 4-year-old `master`-behind problem (standing debt #4) is **resolved**.
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
