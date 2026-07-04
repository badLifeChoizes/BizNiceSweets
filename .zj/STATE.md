# STATE — BizNiceSweets
Updated: 2026-07-04

## Position

- **Milestone:** v1.0 — Foundation + PLUM (one phase from closing)
- **Phase:** 7 — Close v1.0 gaps (**planned** — `PLAN.md` ready at `.zj/phases/07-close-v1-0-gaps/`)
- **Branch:** `chore-architecture-planning` (planning done here; Phase 7 executes on `bugfix-plum-v1-gaps` off `master`)

## Next action

`/zj:build 07` — execute the 7-task plan (3 waves + a standalone CLAUDE.md refresh).
Wave 2 Task 6 is a **blocking human-verify** — the build pauses for you to click through 12
flows at http://localhost:5173. Bring the Podman stack up first (it is currently down); the
plan's Task 5 formalizes the up + container-name-discovery + `alembic current == 0006` steps.

After Phase 7 verifies: `/zj:milestone` to close v1.0, then `/zj:spec` to expand the
SYERP-10..12 / MOUSSE-01 placeholders before planning Phase 8.

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
