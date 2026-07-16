# STATE — BizNiceSweets
Updated: 2026-07-16 (**Phase 11a VERIFIED** on `feature-crumb-crm-pipeline` — Verdict PASS, 4 verify/review gaps fixed at close, tagged `zj/good-11a-crumb-crm-pipeline`. Next action: `/zj:retro 11a` then `/zj:plan 11b`.)

## Position

- **Step:** **VERIFIED** — **Phase 11a (CRUMB CRM & pipeline) verified 2026-07-16, Verdict PASS.** Branch
  `feature-crumb-crm-pipeline` (cut off master `039c409`, D-V3-13), tip `efcf2e6`, tagged
  `zj/good-11a-crumb-crm-pipeline`. All 19 build tasks + the verify fix loop committed. VERIFICATION.md
  (all 7 SCs PASS, each pinned by a durable test) + REVIEW.md written. **Fix loop (`a697c69`, `efcf2e6`)
  closed 4 gaps:** (1major) part-less quote line with a price but no description was accepted → now 422
  (free-text identity guard runs before the explicit-price branch, verify_crumb E2/E3); (minor)
  `convert_to_opportunity` now re-resolves the customer (AC6); (minor) bad `opportunity_id` on quote
  create → 404 not 500; (owner Q) a Won-spawned quote now writes its own `quote.created` audit row
  (verify_crumb_api C2). Docs refreshed: CLAUDE.md Suite Status + MAP.md now record the shipped crumb
  module. **Proof (post-fix):** `verify_crumb.py` **22/22** + `verify_crumb_api.py` **54/54** (SC6 HTTP
  RBAC+audit gate) + 13/13 regression verify_* exit 0 + FE crumb Vitest 4/4 + `npm run build` exit 0. AC4
  (sales orders + soft-reservation) + accepted-quote→SO conversion deferred to 11b (D-V3-10). **Next
  action:** `/zj:retro 11a` (the fix loop produced lessons — missing negative-path test coverage; plus
  the Task-2 pre-existing alembic unique-constraint drift Noticed item worth surfacing), then `/zj:plan 11b`.
  (Planned 2026-07-16 — Phase 11a is the inventory-free portion of CRUMB-01; AC4 sales orders + reservation deferred to 11b.) Phase 11
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
- **Next action:** `/zj:retro 11a` — capture the fix-loop lessons (missing negative-path test coverage;
  the Task-2 pre-existing alembic unique-constraint drift), then `/zj:plan 11b`. Phase 11a is verified
  and tagged; the good-tag gate is closed until the next phase.

## Next action (detail)

**`/zj:retro 11a`** then **`/zj:plan 11b`** — Phase 11a (CRUMB CRM & pipeline) is verified (Verdict
PASS, tag `zj/good-11a-crumb-crm-pipeline`). Retro is worth running: the verify fix loop surfaced a
real major defect (a part-less priced quote line skipped the free-text description guard) that the
build's own verify scripts did not cover — a durable lesson about negative-path test coverage — plus
the standing Task-2 alembic unique-constraint drift (see PLAN Noticed) to surface to the owner. Then
plan 11b (sales orders + accepted-quote→SO conversion + the soft-reservation crux).

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
