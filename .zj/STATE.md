# STATE — BizNiceSweets
Updated: 2026-07-05

## Position

- **Milestone:** v1.0 — Foundation + PLUM (Phase 7 built; verify + close still **open**) ·
  v2.0 spec started (SYERP-10/11 expanded).
- **Phase:** 7 build complete; **8 (SYERP inventory & purchasing) now spec-ready** — owner
  elected to plan Phase 8 ahead of formally closing v1.0 (2026-07-05).
- **Branch:** `bugfix-plum-v1-gaps` (off `chore-architecture-planning` per D-P7-3)

## Next action

`/zj:plan 8` — SYERP-10/11 are spec-complete with acceptance criteria (SRD, expanded 2026-07-05;
scope decisions D-P8-1..7). Plan the inventory + purchasing phase against them.

**Still owed on v1.0 (do not lose):** `/zj:verify 07` then `/zj:milestone` (runs the human-UAT,
`.zj/UAT-v1.0.md`: checks 1 & 8 passed; 2–7 & 9–12 outstanding). Planning Phase 8 first is an
owner choice; v1.0 is not closed and Phase 7 is not yet verified.

## Build result (Phase 7)

- **T1** `5c33ed8` — Partner-alias fix (AVL/import 500s gone; import resolves live).
- **T2** `1b8bfa1` — numeric part# (proven live: DB had `P100000` → returns `P100001`).
- **T3** `37b5f97` — import-commit cache invalidation (tsc-clean, tests pass).
- **T4** `5db8278` — CLAUDE.md stack/architecture refreshed to live FastAPI/React.
- **T5** — stack up, `compose_api_1`, `alembic 0006`; :5173 serves; :8000 serves no SPA.
- **T6** — human-UAT deferred to milestone (D-P7-5); checks 1 & 8 passed.
- **T7** — SRD + requirements-progress reconciled honestly (PLUM-01 defect resolved; PLUM-04..10
  code-verified, UI UAT milestone-pending).

## Two deferrals now owned elsewhere (BACKLOG p1)

1. **PLUM live-DB test harness never runs** (broken probe + async-engine loop + no seed/isolation)
   — D-P7-4, BACKLOG p1. Fixes currently proven via standalone async scripts, not pytest.
2. **v1.0 human-UAT** — `.zj/UAT-v1.0.md`, run at `/zj:milestone` (D-P7-5).

## Known blockers (fixed by Phase 7 — all re-confirmed in live code 2026-07-04)

1. `backend/app/modules/plum/service.py` imports nonexistent `SyerpPartner` (lines
   1634/2139/2607/2740; real class `Partner`) → AVL + vendor import/export HTTP 500. → Plan Task 1.
2. `generate_part_number()` (service.py:108) lexicographic MAX → duplicate part numbers past a
   digit-width boundary. → Plan Task 2.
3. ImportExport commit (`ImportExport.tsx`) doesn't invalidate `['plum','parts']` → stale
   Parts List ≤30 s. → Plan Task 3.

## Phase 7 plan shape

- **Wave 1 (code):** T1 backend SyerpPartner alias + live vendor-path coverage · T2 numeric
  part-number + boundary test (same file — after T1) · T3 frontend cache invalidation ·
  T4 CLAUDE.md stack/architecture refresh (independent, owner decision D-P7-2).
- **Wave 2 (verify):** T5 stack up + discover API container + `alembic 0006` + full live-DB PLUM
  suite (0 unexpected skips) · T6 blocking consolidated human-verify at :5173 (D-P7-1).
- **Wave 3 (docs):** T7 reconcile `.zj/SRD.md` + `docs/features/requirements-progress.md`,
  gated on the T6 outcome.

Planning decisions recorded: DECISIONS.md D-P7-1 (verify at :5173 only), D-P7-2 (scope = 4 GSD
plans + CLAUDE.md refresh; CI stays backlog).

## Adoption note

Adopted from GSD on 2026-07-04. Prior planning system archived at `archive/planning-gsd/`
(phases 01–07, REQUIREMENTS, ROADMAP, STATE, v1.0-MILESTONE-AUDIT, codebase snapshots) and
`archive/planning-docs/` (program ROADMAP.md, decisions.md). `.zj/` is self-contained — the
archive is history, not a dependency.
