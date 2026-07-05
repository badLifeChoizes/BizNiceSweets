# STATE — BizNiceSweets
Updated: 2026-07-04

## Position

- **Milestone:** v1.0 — Foundation + PLUM (one phase from closing)
- **Phase:** 7 — Close v1.0 gaps (**build in flight** — PAUSED at Task 6 blocking human-verify)
- **Branch:** `bugfix-plum-v1-gaps` (off `chore-architecture-planning` per D-P7-3)

## Next action

**Task 6 — blocking human-verify (build is PAUSED here).** The Podman stack is UP
(`compose_db_1`/`compose_api_1`/`compose_frontend_1`), `alembic current == 0006`, Vite dev serves
HTTP 200 at http://localhost:5173, API `/docs` 200 at :8000. Open :5173, log in as admin, and
run the 12 checks in PLAN.md Task 6 (7 PLUM flows PLUM-04..10 + regression checks 9–12). Reply
"approved" if all pass, or list the failing flow(s) with observations. On approval the build
resumes at Task 7 (traceability reconciliation), then wrap-up → `/zj:verify 07`.

**Build progress:** T1–T5 done & committed (`5c33ed8` alias fix, `1b8bfa1` numeric part#,
`37b5f97` cache invalidation, `5db8278` CLAUDE.md refresh; T5 stack/env confirmed). Automated
live-DB suite is deferred (D-P7-4) — fixes proven via live-DB standalone proofs; Task 6 is the
end-to-end confirmation.

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
