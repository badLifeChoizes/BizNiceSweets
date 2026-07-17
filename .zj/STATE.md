# STATE — BizNiceSweets
Updated: 2026-07-16 (**Phase 11a RETRO'd** — learnings captured, roadmap stamped `[done]`, deferred items homed. Next action: `/zj:plan 11b`.)

## Position

- **Step:** **RETRO'd** — **Phase 11a (CRUMB CRM & pipeline) verified + retro'd 2026-07-16.** Branch
  `feature-crumb-crm-pipeline` (cut off master `039c409`, D-V3-13), tip `efcf2e6`, tagged
  `zj/good-11a-crumb-crm-pipeline`. Retro (`/zj:retro 11a`) appended LEARNINGS Phase 11a
  (new-module-as-a-package from day one; mirror the newest exemplar; the two-tier verify pair earns
  SC6; **and the keeper — 20 green verify assertions missed a major defect that the code review
  caught**, so the adversarial review is not redundant with verify). Deferred items homed: the Task-2
  alembic unique-constraint drift and the 422 deprecation sweep were re-hit by crumb and noted on the
  existing p1/p3 BACKLOG entries (not duplicated); AC4 (sales orders + soft-reservation) +
  accepted-quote→SO conversion remain Phase 11b (D-V3-10). All 19 build tasks + the fix loop
  (`a697c69`, `efcf2e6`, 4 gaps) committed; VERIFICATION.md + REVIEW.md written. **Proof (post-fix):**
  `verify_crumb.py` **22/22** + `verify_crumb_api.py` **54/54** (SC6 HTTP RBAC+audit gate) + 13/13
  regression verify_* exit 0 + FE crumb Vitest 4/4 + `npm run build` exit 0. **Next action:**
  `/zj:plan 11b`. Phase 11
  (CRUMB-01, the largest single FR) was **split into 11a + 11b** at plan (D-V3-10): **11a** = the
  inventory-free CRM chain (leads → opportunities → quotes + communication log), **11b** = sales
  orders + accepted-quote→SO conversion + the soft-reservation crux. PLAN.md for 11a holds **19 tasks**
  in 5 waves (models → migration 0013 → perms → schemas → 4-entity `crumb/service/` package →
  router+register → `verify_crumb.py` + `verify_crumb_api.py` + regression → frontend nav/4 pages/tests).
  Every in-scope CRUMB-01 AC (1/2/3−/5/6/7) maps to a task; **AC4 (sales orders + reservation) is
  deferred to 11b**. Six decisions recorded (**D-V3-10..15**). Plan reviewed goal-backward; one
  architect error caught and fixed at manager check — the hub FK columns are `String(36)` (Partner/
  plum_part PKs are UUIDs, not int).

- **Project:** BizNiceSweets
- **Milestone:** v3.0 Customer & logistics — **IN PROGRESS** (Phase 11a verified; 11b–13 pending). v2.0
  CLOSED + tagged `v2.0`; v1.0 closed + tagged 2026-07-11.
- **Branch (planning artifacts):** `chore-spec-v3-customer-logistics` — carries the v3.0 spec + this
  plan's doc edits. `master` at `35f9b66` carries all of Phases 8–10. **Phase 11a builds on a new
  `feature-crumb-crm-pipeline` branch off master (D-V3-13)** — fast-forward this spec/plan branch to
  master first.
- **Last update:** 2026-07-16
- **Next action:** `/zj:plan 11b` — Phase 11a is verified, tagged, and retro'd; the good-tag gate is
  closed until the next phase. Optionally `/zj:log phase 11a` for the formal work log.

## Next action (detail)

**`/zj:plan 11b`** — Phase 11a (CRUMB CRM & pipeline) is verified + retro'd (Verdict PASS, tag
`zj/good-11a-crumb-crm-pipeline`; LEARNINGS Phase 11a captured, roadmap `[done]`). Plan 11b: sales
orders + accepted-quote→SO conversion (the AC3 tail) + the **soft-reservation crux** (`qty_reserved`
accumulator on the SO line, D-V3-11; `available = on-hand − Σ reserved ≥ 0`, D-V3-8). Carry the
11a keeper into 11b's plan — budget a full adversarial review of the reservation logic; the verify
scripts alone will not cover its negative space (concurrent-writer over-reservation especially).
Optional: `/zj:log phase 11a` for the record.

### (historical) Phase 11a build — CRUMB-01 inventory-free portion
**`/zj:build 11a`** built a new `crumb` module (mirrors the
MOUSSE new-module pattern, D-P10-6) with a `crumb/service/` package split by entity, leads →
opportunities (stage FSM) → quotes (PLUM-derived 30% markup default, `QUOTE-####` numeric-safe, Draft
→Sent→Accepted/Rejected/Expired FSM), and an append-only customer communication log. Server-enforced
FSMs, audit at the router layer, `crumb:read`/`crumb:write` RBAC. Proven by `verify_crumb.py` (service)
+ `verify_crumb_api.py` (HTTP RBAC + audit) + FE Vitest/build; the 13 existing `verify_*` stay green.

**Before building:** fast-forward `chore-spec-v3-customer-logistics` → `master`, then cut
`feature-crumb-crm-pipeline` off master (D-V3-13).

**After 11a verifies:** `/zj:plan 11b` — sales orders + the soft-reservation crux (`qty_reserved`
accumulator on the SO line, D-V3-11; `available = on-hand − Σ reserved ≥ 0`, D-V3-8) + accepted-quote
→SO conversion. Then Phase 12 (GELATO ship, posts COGS JE) → Phase 13 (SYERP-13 AR). The DoD, not the
phase count, is the contract.

**Alternative — pay down infra debt first:** the BACKLOG **p1** items (CI pipeline, live-DB pytest
harness repair, both lint gates) are now two milestones old. A debt-paydown phase is reasonable if the
owner wants it (raise at `/zj:ideate`).

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
