# STATE — BizNiceSweets
Updated: 2026-07-16 (**Phase 11b PLANNED** — PLAN.md written (17 tasks), 4 decisions recorded (D-V3-16..19). Next action: `/zj:build 11b`.)

## Position

- **Step:** **PLAN COMPLETE** — **Phase 11b (CRUMB sales orders + soft-reservation) planned 2026-07-16.**
  `.zj/phases/11b-crumb-sales-orders/PLAN.md` holds **17 tasks** (backend 1–12, frontend 13–17)
  completing CRUMB-01 (all ACs): sales orders (Draft→Confirmed→Fulfilling→Closed FSM, +Cancelled from
  Draft/Confirmed), accepted-quote→SO conversion (AC3 tail), and the **soft-reservation crux** (AC4,
  D-V3-8/11) — `available(item) = on-hand − Σ open SO-line reservations ≥ 0`, `qty_reserved`
  accumulator on the SO line, confirm reserves `min(qty_ordered, available)`, shortage indicator not
  hard-blocked, cancel releases. **Task 8 is the isolated crux** (confirm/reserve/lock + cancel/release):
  contended `InventoryItem` rows `SELECT … FOR UPDATE` in sorted-id order (bills.py template) BEFORE
  the read-check-write; `verify_crumb_so.py` scenario F asserts two `asyncio.gather` concurrent confirms
  cannot over-reserve — **and the 11a keeper is carried in: a full adversarial review of Task 8 is
  mandated before verify** (20 green assertions missed a major in 11a). 11b posts **NO GL** (soft
  quantity, no InventoryTxn/JE; TB still nets zero). Four decisions recorded **D-V3-16..19**: non-stock
  lines confirm with reserve 0 (D-V3-16); both direct-create + conversion (D-V3-17); narrow lock scope,
  broader ledger-floor unification stays BACKLOG p2 → Phase 12 (D-V3-18); branch
  `feature-crumb-sales-orders` off the 11a tip tag (D-V3-19). Plan reviewed goal-backward — all 6 SCs
  covered, `## Decisions needed` empty. **Next action:** `/zj:build 11b`.

- **Branch to cut (D-V3-19):** `feature-crumb-sales-orders` off tag `zj/good-11a-crumb-crm-pipeline`
  (commit `efcf2e6`) — 11a is unmerged; 11b stacks on it. Checklist: `docs/tasks/feature-crumb-sales-orders.md`.

- **(historical) Step:** **RETRO'd** — **Phase 11a (CRUMB CRM & pipeline) verified + retro'd 2026-07-16.** Branch
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
- **Next action:** `/zj:build 11b` — Phase 11b is planned (17 tasks, PLAN.md written, D-V3-16..19
  recorded). First cut the branch `feature-crumb-sales-orders` off tag `zj/good-11a-crumb-crm-pipeline`
  (D-V3-19), then build task-by-task.

## Next action (detail)

**`/zj:build 11b`** — `.zj/phases/11b-crumb-sales-orders/PLAN.md` holds 17 tasks completing CRUMB-01:
sales orders (Draft→Confirmed→Fulfilling→Closed FSM), accepted-quote→SO conversion (AC3 tail), and the
**soft-reservation crux** (`qty_reserved` accumulator D-V3-11; `available = on-hand − Σ reserved ≥ 0`
D-V3-8). **Task 8 is the isolated crux** — carry the 11a keeper: a full adversarial review of the
reserve/lock logic is mandated before verify; `verify_crumb_so.py` scenario F pins the concurrent
over-reservation negative space. 11b posts no GL. Cut `feature-crumb-sales-orders` off tag
`zj/good-11a-crumb-crm-pipeline` (`efcf2e6`, D-V3-19) first.

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
