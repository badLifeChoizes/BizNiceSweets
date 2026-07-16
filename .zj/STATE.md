# STATE — BizNiceSweets
Updated: 2026-07-16 (**Milestone v2.0 "Operations" CLOSED + tagged `v2.0`**. Next milestone = v3.0 Customer & logistics. Next action: `/zj:ship` then `/zj:spec`.)

## Position

- **Step:** milestone — **v2.0 "Operations" closed and tagged `v2.0` (2026-07-16).** The definition
  of done ("track inventory, raise purchase orders, keep real books with AP + financial statements,
  execute work orders that consume PLUM BOMs and inventory") was audited goal-backward against the
  running stack (`.zj/MILESTONE-v2.0-AUDIT.md`): all four clauses proven end-to-end backend↔frontend↔DB,
  **13/13 live `verify_*` scripts exit 0**, whole-DB trial balance nets zero, control accounts tie to
  subledgers, `npm run build` clean, 90/90 Vitest, alembic head 0012. Verdict clean but for one minor
  gap **G1** (P&L report 422'd on an empty `from` date), **fixed at close** (`2578ca5`). Records:
  CHANGELOG (v2.0 released), `.zj/logs/milestone-v2.0.md`, LEARNINGS "Milestone v2.0", DECISIONS
  D-M2-1..4 + regenerated index, the audit doc. Phases 8/9a/9b/9c/10 archived to
  `.zj/history/v2.0/phases/`; `.zj/phases/` is empty.

- **Project:** BizNiceSweets
- **Milestone:** v2.0 Operations — **CLOSED + tagged `v2.0`**. v1.0 closed + tagged 2026-07-11.
- **Branch:** `feature-mousse-work-orders` — carries Phases 9a→10 + the v2.0 close. The `v2.0` tag
  sits at its HEAD.
- **Last update:** 2026-07-16
- **Next action:** `/zj:ship` (resolve the 2-milestone-deep master-merge debt, D-M2-3), then
  `/zj:spec` to sharpen the v3.0 "Customer & logistics" DoD into clauses and expand the coarse FRs
  (CRUMB-01, GELATO-01, SYERP-13/AR) before planning Phase 1 of v3.0.

## Next action (detail)

**`/zj:ship`** — resolve the master-merge debt (D-M2-3, now two milestones deep): `master` is 98
commits behind and carries none of Phases 9–10; both `v1.0` and `v2.0` are tagged on the working tip
of an unmerged feature branch. Then **`/zj:spec`** to sharpen the v3.0 "Customer & logistics"
definition of done into clauses and expand the coarse FRs (CRUMB-01, GELATO-01, SYERP-13/AR) before
planning Phase 1 of v3.0.

Alternative if the owner wants to pay down infra debt first: the BACKLOG **p1** items (CI pipeline,
live-DB pytest harness repair, both lint gates) are now two milestones old — a `/zj:ideate` on
whether v3.0 leads with a debt-paydown phase is reasonable.

## Deferred at the v2.0 close (owner-approved — do not lose)

- **Human click-through UAT** (`.zj/UAT-v2.0.md` 14 checks + owed v1.0 round-2) → BACKLOG **p1**
  pre-public-release gate (D-M2-2). Tag rests on backend live-proof + the wired-UI audit; extend the
  checklist with GL/AP/reports/MOUSSE UI flows before running it.
- **BACKLOG p1 infra debt** — no CI, live-DB pytest harness broken (100 skips, D-P7-4), both lint
  gates non-functional. Correctness rests on `verify_*` + Vitest. Carried into v3.0.
- **`/zj:ship` master-merge** (D-M2-3) — the 98-commit-behind master.

## Standing context

- **Stack for verification:** `podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d`;
  run verify scripts in-container: `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/<name>.py`.
  Vite dev server for UI/UAT at `http://localhost:5173`.
- **v2.0 tag placement (D-M2-3, mirrors D-M1-1):** the `v2.0` tag's tree is an unmerged branch tip —
  recorded, not accidental; a later fast-forward preserves the SHA.
- **Adoption note:** adopted from GSD 2026-07-04; prior systems archived under `archive/`. `.zj/` is
  self-contained.
