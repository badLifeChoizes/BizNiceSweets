# STATE — BizNiceSweets
Updated: 2026-07-16 (**v3.0 "Customer & logistics" spec'd** — DoD sharpened into 3 clauses; CRUMB-01/GELATO-01/SYERP-13 expanded to full ACs; Phase 11→12→13 mapping proposed; D-V3-1..9 recorded. Next action: `/zj:plan 11`.)

## Position

- **Step:** spec — **v3.0 "Customer & logistics" requirements complete (2026-07-16).** The milestone
  DoD is sharpened into **three verifiable clauses** (CRM & sales pipeline / warehouse fulfillment /
  AR & sell-side books) and the three coarse FRs are expanded to full acceptance criteria: **CRUMB-01**
  (7 ACs, Phase 11), **GELATO-01** (8 ACs, Phase 12), **SYERP-13** (7 ACs, Phase 13). Nine scope
  decisions recorded (**D-V3-1..9**). Sell side is a two-event real-books mirror of v2.0 procure-to-pay
  and needs **no new CoA accounts** (1120 AR / 4110 Revenue / 5100 COGS already seeded). Deferred within
  v3.0: lot/serial, email/analytics, price lists. Updated: PRD-8, SRD (3 FRs + traceability), ROADMAP
  (phase→FR map), DECISIONS. `.zj/phases/` is empty — no phase planned yet.

- **Project:** BizNiceSweets
- **Milestone:** v3.0 Customer & logistics — **SPEC'D, planning next**. v2.0 CLOSED + tagged `v2.0`;
  v1.0 closed + tagged 2026-07-11.
- **Branch:** `chore-spec-v3-customer-logistics` (cut from `master`/`feature-mousse-work-orders` tip,
  which are even) — carries only this spec's doc edits. `master` at `35f9b66` carries all of Phases
  8–10.
- **Last update:** 2026-07-16
- **Next action:** `/zj:plan 11` — plan **Phase 11 (CRUMB CRM & sales orders, CRUMB-01)**, the first
  of the three v3.0 phases (order → ship → invoice build order). Likely to sub-split at plan the way
  Phase 9 became 9a/9b/9c.

## Next action (detail)

**`/zj:plan 11`** — plan Phase 11 delivering **CRUMB-01** (new `crumb` module): leads → opportunities
→ quotes → sales orders + communication log, PLUM-derived editable line pricing, and the
**soft-reservation** invariant (`available = on-hand − reserved ≥ 0`, D-V3-8) which is the phase's
crux. No GL in Phase 11. Depends only on shipped surfaces (SYERP customers, PLUM parts, SYERP
inventory for reservation). See ROADMAP v3.0 phase→FR table and the SRD CRUMB-01 ACs.

**Sequencing:** build order follows the money — Phase 11 order → Phase 12 GELATO ship (posts the COGS
JE) → Phase 13 SYERP-13 invoice/collect. The DoD, not the phase count, is the contract; sub-split at
plan as needed.

**Alternative — pay down infra debt first:** the BACKLOG **p1** items (CI pipeline, live-DB pytest
harness repair, both lint gates) are now two milestones old. A debt-paydown phase before Phase 11 is
reasonable if the owner wants it (raise at `/zj:plan` or `/zj:ideate`).

**This spec branch:** `chore-spec-v3-customer-logistics` holds only doc edits — merge it to `master`
(fast-forward) whenever convenient; it is not a code phase and needs no verify.

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
