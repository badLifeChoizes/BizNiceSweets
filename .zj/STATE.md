# STATE — BizNiceSweets
Updated: 2026-07-16 (**v2.0 SHIPPED to master** — PR #2 merged via fast-forward, `v2.0` tag pushed, master-merge debt D-M2-3 resolved. Next action: `/zj:spec` for v3.0 Customer & logistics.)

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
- **Branch:** `feature-mousse-work-orders` — carried Phases 9a→10 + the v2.0 close; now **merged to
  `master` (fast-forward, `aa497b1..35f9b66`)**. Safe to delete locally + on origin. The `v2.0` tag
  (`d6c91cb`) is preserved and reachable from master; a `chore:` gitignore commit (`35f9b66`) sits
  one above it.
- **Last update:** 2026-07-16
- **Next action:** `/zj:spec` to sharpen the v3.0 "Customer & logistics" DoD into clauses and expand
  the coarse FRs (CRUMB-01, GELATO-01, SYERP-13/AR) before planning Phase 1 of v3.0.

## Next action (detail)

**`/zj:spec`** — sharpen the v3.0 "Customer & logistics" definition of done into clauses and expand
the coarse FRs (CRUMB-01, GELATO-01, SYERP-13/AR) before planning Phase 1 of v3.0. The v2.0
milestone is fully closed and shipped; `master` now carries all of Phases 8–10.

**Ship record (2026-07-16):** PR **#2** (`feature-mousse-work-orders` → `master`) opened and merged
via **fast-forward** — 104 milestone commits + the gitignore hygiene commit. Mirrors the v1.0 ship
(PR #1). `v2.0` tag pushed to origin. **D-M2-3 (master-merge debt) resolved.** Local + origin master
at `35f9b66`.

Alternative if the owner wants to pay down infra debt first: the BACKLOG **p1** items (CI pipeline,
live-DB pytest harness repair, both lint gates) are now two milestones old — a `/zj:ideate` on
whether v3.0 leads with a debt-paydown phase is reasonable.

## Deferred at the v2.0 close (owner-approved — do not lose)

- **Human click-through UAT** (`.zj/UAT-v2.0.md` 14 checks + owed v1.0 round-2) → BACKLOG **p1**
  pre-public-release gate (D-M2-2). Tag rests on backend live-proof + the wired-UI audit; extend the
  checklist with GL/AP/reports/MOUSSE UI flows before running it.
- **BACKLOG p1 infra debt** — no CI, live-DB pytest harness broken (100 skips, D-P7-4), both lint
  gates non-functional. Correctness rests on `verify_*` + Vitest. Carried into v3.0.
- **`/zj:ship` master-merge** (D-M2-3) — **RESOLVED 2026-07-16** (PR #2, fast-forward to `35f9b66`).

## Standing context

- **Stack for verification:** `podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d`;
  run verify scripts in-container: `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/<name>.py`.
  Vite dev server for UI/UAT at `http://localhost:5173`.
- **v2.0 tag placement (D-M2-3, mirrors D-M1-1):** the `v2.0` tag (`d6c91cb`) was applied on the
  then-unmerged branch tip; the fast-forward ship (PR #2) preserved the SHA and it is now reachable
  from `master`. Debt cleared.
- **Adoption note:** adopted from GSD 2026-07-04; prior systems archived under `archive/`. `.zj/` is
  self-contained.
