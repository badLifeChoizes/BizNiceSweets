# STATE — BizNiceSweets
Updated: 2026-07-19 (**Phase 12b RETRO'D** — `/zj:retro 12b` on branch
`feature-gelato-pick-pack-ship`, tag `zj/good-12b-gelato-pick-pack-ship` over `553bcfb`. Roadmap
marked `[done — verified + retro'd]`; **CRUMB→GELATO outbound loop complete** (v3.0 DoD clause 2 closed).
**LEARNINGS Phase 12b banked (4 keepers):** (1) **the headline — a forced-interleave concurrency test can
pass for the WRONG reason and mask the exact bug it targets**: scenario g's staging bin was seeded to
*exactly* the ship qty, so `post_issue`'s floor guard (a *bystander* guard) rejected the duplicate while
the real defect — an UNLOCKED shipment-status FSM gate letting two ships of one packed shipment double-post
COGS — sailed through untested; keeper = build concurrency fixtures so ONLY the guard under test can reject
(scenario h: order 10 ship 5, ample staging, only the shipment-row lock can 409 the duplicate; mutation-proven);
(2) **mirroring an exemplar's lock is safe only if your transition shares its safety property** — MOUSSE
`issue_components`' status-before-lock shape is safe because issuing is *repeatable*; ship is a *one-shot
terminal* transition, so the copied item locks are necessary-but-not-sufficient — the fix locks the Shipment
row (`SELECT … FOR UPDATE`) before the FSM gate; (3) **the dead-through-UI trap was caught IN-BUILD this time**
(qty_shipped serialization on `SalesOrderLineRead`) — the counter-measure works; (4) **parallel
verifier+reviewer, reviewer-blocker-overrides-PASS, is load-bearing 4 phases running** (11a/11b/12a/12b).
Deferred items all homed at verify, trued up at retro: pick-path races Q1/Q2 → BACKLOG p2; bin-blind-desync
p2 **outbound half now closed** (inbound `post_transfer`/`post_adjustment`/MOUSSE-issue still open); downgrade
test → p3. Artifacts: VERIFICATION.md + REVIEW.md + LEARNINGS.md Phase 12b. **Next action:** `/zj:plan 13`
(SYERP-13 AR + invoice-from-shipment + customer receipts + AR aging tie-out — closes v3.0 DoD clause 3).
Optional: `/zj:log phase 12b` (formal work log); `/zj:ship` to merge the 11a+11b+12a+12b stack.)

Prior: 2026-07-19 (**Phase 12b VERIFIED** — `/zj:verify 12b` PASS on branch
`feature-gelato-pick-pack-ship`, tag `zj/good-12b-gelato-pick-pack-ship` over `553bcfb`. Verifier +
reviewer ran in parallel; the **reviewer caught a BLOCKER the verifier's concurrency test masked**:
`execute_ship` gated on an UNLOCKED shipment status and locked only the `InventoryItem` rows, so two
concurrent ships of ONE packed shipment could both pass the FSM gate → **double inventory issue +
double Dr 5100 / Cr 1130 COGS JE + double reservation relief**. Scenario g missed it (its staging bin
held exactly the ship qty, so `post_issue`'s floor guard incidentally rejected the duplicate). **Fixed**
(`553bcfb`): load the shipment `SELECT … FOR UPDATE` before the FSM gate. **New durable test**
`verify_gelato_ship.py` scenario (h) — one packed shipment partially fulfilling its SO (order 10, ship 5)
shipped twice concurrently; mutation-proven (reverting the lock → 2 JEs / qty_shipped 10 / staging drawn
twice). Full regression re-run **21/21 verify_* exit 0**, TB nets zero WITH the ship COGS JE, 1130 ties
to subledger; `verify_gelato_ship.py` **21/21**, `verify_gelato_ship_api.py` **23/23**. Two lower-severity
pick-path shipment-header races (review Q1/Q2) → BACKLOG p2; migration-downgrade automated-test gap → p3;
all recorded in PLAN `## Noticed`. Closes v3.0 DoD clause 2 (warehouse fulfillment outbound). Artifacts:
VERIFICATION.md + REVIEW.md in the phase dir. **Next action:** `/zj:retro 12b` (banks the "review catches
what the verifier's own test masks" keeper + the same-shipment-lock class) then `/zj:plan 13`.)

Prior: 2026-07-18 (**Phase 12b BUILD COMPLETE** — `/zj:build 12b` done on branch
`feature-gelato-pick-pack-ship` (cut off the 12a docs-on-top tip `bde5b77`, code-identical to tag
`zj/good-12a-gelato-bins-putaway`, D-P12b-8). **All 15 tasks shipped**, GELATO outbound pick → pack →
ship end-to-end. Wave A: migration **0016** (Shipment + ShipmentLine tables, `qty_picked`/`qty_shipped`
on `crumb_sales_order_line`) round-trips clean; shipment schemas. Wave B: NEW SYERP bin-aware
`post_issue` (single signed `issue` leg, item-master FOR-UPDATE before floor read); GELATO
`service/shipments.py` pick (net-zero pick-bin→staging via `post_putaway`, stamps qty_picked, SO
confirmed→fulfilling) / pack (FSM picking→packed, partial-pack trims staged qty) / **ship** (bin-aware
`post_issue` from staging + ONE balanced **Dr 5100 COGS / Cr 1130 Inventory** JE atomic via single
`db.commit()`, relieves qty_reserved + stamps qty_shipped, FSM→shipped); thin RBAC-gated router with
`write_audit(target_id=str(shipment.id))`. Wave C: `verify_gelato_ship.py` **22 asserts green**
(accounting crux Decimal-exact, reservation relief, partial-ship, negative space, control↔subledger tie,
**load-bearing concurrency Barrier — mutation-proven**) + `verify_gelato_ship_api.py` **23 asserts**
(HTTP 401/403/200 + attributable audit + int-PK target_id string guard); **full regression 19/19 green,
TB nets zero WITH the ship COGS JE, 1130 ties to subledger**. Wave D: shipment hooks + Fulfillment
pick→pack→ship screen + SO-detail Fulfill/Ship affordance; FE **38 files / 116 tests green**, `npm run
build` exit 0. **Three material handlings:** (1) `post_putaway` had no `commit` param → added
backwards-compatible `commit=True` so pick batches atomically (engineer correctly STOPPED, forced fix,
Deviations); (2) task-4 shipment FK schema fields mistyped `Optional[int]` → `Optional[str]` (String(36));
(3) **the recurring dead-through-UI trap CAUGHT** — SO-detail `qty_shipped` column rendered from a field
`SalesOrderLineRead` did not serialize → added `qty_picked`/`qty_shipped` to the read schema. Lint gates
remain non-functional (BACKLOG p1); correctness rests on verify_* (19/19) + Vitest (116), per project
convention. Noticed (non-blocking): belt-and-suspenders redundant ship locks; a dev-only `--reload`
FK-race on `syerp_inventory_txn.bin_id→gelato_bin` (production unaffected). **Next action:**
`/zj:verify 12b`.)

## Position

- **Step:** **RETRO'D** — **Phase 12b (GELATO outbound: pick → pack → ship) closed 2026-07-19**
  (`/zj:retro 12b`), tag `zj/good-12b-gelato-pick-pack-ship` at `553bcfb`. Roadmap marked
  `[done — verified + retro'd]`. **v3.0 DoD clause 2 (warehouse fulfillment outbound) closed** and the
  sell-side **COGS** JE (Dr 5100 / Cr 1130) posts atomically on ship. Retro banked LEARNINGS Phase 12b
  (4 keepers — the forced-interleave-test-passes-for-the-wrong-reason headline, the mirror-an-exemplar's-lock
  caveat for one-shot vs repeatable transitions, the in-build dead-through-UI catch, and review-overrides-PASS
  now load-bearing 4 phases running). Deferred items homed: pick-path races Q1/Q2 → BACKLOG p2;
  bin-blind-desync outbound half closed (inbound still open, p2); downgrade test → p3. **Next action:**
  `/zj:plan 13` (SYERP-13 AR + invoice-from-shipment). Optional: `/zj:log phase 12b`; `/zj:ship` to merge
  the 11a+11b+12a+12b stack.

- **(historical) Step:** **BUILD COMPLETE** — **Phase 12b (GELATO outbound: pick → pack → ship) built 2026-07-18.**
  All **15 tasks** on branch `feature-gelato-pick-pack-ship`. Closes the v3.0 DoD clause 2 (warehouse
  fulfillment outbound) and posts the sell-side **COGS** JE (Dr 5100 / Cr 1130). Proof: `verify_gelato_ship.py`
  22 asserts + `verify_gelato_ship_api.py` 23 asserts + **19/19** full regression (TB nets zero with the
  new JE, 1130↔subledger tie) + FE **38 files/116 tests** + `npm run build` exit 0. Checklist (all 15
  ticked): `docs/tasks/feature-gelato-pick-pack-ship.md`.

## (historical) Position

- **Step:** **PLAN COMPLETE** — **Phase 12b (GELATO outbound: pick → pack → ship) planned 2026-07-18.**
  Closes the v3.0 DoD clause 2 (warehouse fulfillment outbound) and posts the sell-side **COGS** JE
  (Dr 5100 / Cr 1130) — the first half of SYERP-13's sell-side books; invoice-from-shipment + AR stay
  Phase 13. **15 tasks:** Wave A schema (Shipment + ShipmentLine models, `qty_picked`/`qty_shipped` on
  `crumb_sales_order_line`, migration **0016**, schemas) → Wave B backend (NEW SYERP bin-aware
  `post_issue` → GELATO `shipments.py` pick/pack/ship → router+boot) → Wave C verify
  (`verify_gelato_ship.py` incl. the accounting crux + control-vs-subledger tie + reservation-relief +
  partial-ship + the load-bearing Barrier; `verify_gelato_ship_api.py` HTTP RBAC/audit; full regression
  + TB-nets-zero) → Wave D frontend (shipment hooks, a Fulfillment pick→pack→ship screen, an SO-detail
  ship affordance, colocated Vitest asserting the real payload shape). Recurring keepers baked in: real
  router/UI payload shape in verify + Vitest (11a/11b/12a trap); the non-optional HTTP audit/RBAC script
  + `write_audit(target_id=str(shipment.id))` (12a int-PK bug — Shipment is int-PK); the pre-planned
  FOR-UPDATE lock + `asyncio.Barrier` two-concurrent-ship scenario; a control-account-ties-to-subledger
  assertion (not just TB nets zero — Phase 10 keeper). **Next action:** `/zj:build 12b`.

- **Branch (D-P12b-8):** build 12b on a fresh `feature-gelato-pick-pack-ship` cut off the verified 12a
  tip (tag `zj/good-12a-gelato-bins-putaway`, `52eb481`) — 11a/11b/12a unmerged; 12b stacks. Lint gates
  remain non-functional (BACKLOG p1); correctness rests on verify_* + Vitest, per project convention.

## (historical) Position

- **Step:** **RETRO'D** — **Phase 12a (GELATO bins & directed putaway) closed 2026-07-18** (`/zj:retro 12a`),
  tag `zj/good-12a-gelato-bins-putaway` at `52eb481`. Roadmap marked `[done — verified + retro'd]`. Retro banked
  **LEARNINGS Phase 12a**, five keepers: (1) **the headline lesson — adding a new dimension (`bin_id`) to a
  shared ledger silently corrupts it for every existing writer that ignores the dimension, and it's a
  SEQUENTIAL-correctness bug, not a race** (bin-blind `post_transfer`/`post_adjustment`/MOUSSE-issue leave the
  bin overstated + unbinned pool negative even single-threaded; the SC3 roll-up identity stays exact so every
  green assertion missed it — same shape as the 09c/10 zero-sum-identity blindness, now on a physical
  dimension); (2) **a value clamp that hides the symptom can break the invariant you just proved** — clamping
  `get_bin_on_hand` would have broken SC3, so the mitigation surfaced-and-pinned the boundary (scenario E)
  instead; (3) **the paired HTTP script earned its keep a 3rd suite running — GELATO's `Bin` is the first
  int-PK audited entity and its int→`VARCHAR(36)` `target_id` coercion bug 500'd the mutation after commit;
  keeper: `write_audit(target_id=...)` must `str()` the id** (reviewer confirmed no other int-PK target exists,
  so no repo sweep owed); (4) **concurrency pre-empted by design → clean review on that axis, the 9b rule
  paying off a 3rd time**; (5) **reverse-hub string table-name FK** avoids the import cycle when a hub-core
  table must reference a satellite table. Deferred items all homed: bin-split MAJOR → BACKLOG p2 (added at
  verify); int-PK audit sweep resolved (folded to LEARNINGS, no backlog entry); 422 sweep already BACKLOG p3.
  Artifacts: `.zj/phases/12a-gelato-bins-putaway/{PLAN,VERIFICATION,REVIEW}.md`, `.zj/LEARNINGS.md` Phase 12a.
  **Next action:** `/zj:plan 12b`. Optional: `/zj:log phase 12a` (formal work log); `/zj:ship` to merge the
  11a+11b+12a stack.

- **(historical) Step:** **BUILD COMPLETE** — **Phase 12a (GELATO bins & directed putaway) built 2026-07-17.**
  All **14 tasks** shipped on a fresh `feature-gelato-bins-putaway` branch (cut off HEAD `da9474e` = the
  verified 11b code tip + plan docs; see PLAN Deviations — bare tag `fec334f` would have dropped the plan).
  Delivered: `gelato` module self-registers (mirrors mousse/crumb new-module package shape); migration
  **0015** adds `gelato_bin` + nullable `bin_id` on `syerp_inventory_txn` (hub-inversion string FK,
  D-P12a-3), round-trips clean; `gelato:read`/`gelato:write` seeded; bin CRUD (unique-within-location,
  archive-hides) + directed putaway. The **SYERP-owned bin-aware primitive** `post_putaway`/`get_bin_on_hand`
  (D-P12a-7) clones `post_transfer` intra-location + bin-dimensioned, **locks `InventoryItem` FOR UPDATE
  before the floor read** (corrected from the plan's "InventoryTxn" prose — the append-only ledger isn't the
  contention point); GELATO's thin `service/` validates bins-belong-to-location then delegates. Router thin,
  RBAC-gated, audit-after-commit. **Proof:** `verify_gelato.py` (roll-up Decimal-exact + net-zero + floor +
  the **Barrier two-concurrent-putaway scenario, proven load-bearing** — lock removed → 2 successes → FAIL,
  restored → green) + `verify_gelato_api.py` (30 asserts, HTTP 401/403/200 + attributable audit) + all 17
  existing verify_* → **19/19 green**, Trial Balance `in_balance` True (12a posts **NO GL**); FE full suite
  **37 files/108 tests**, `npm run build` exit 0; nav gating data-driven (enabled ∩ `gelato:read`).
  **Two material findings, both handled:** (1) the paired HTTP script **caught a real router-audit bug** —
  bin routes passed integer `Bin.id` to `write_audit(target_id=...)` (VARCHAR col) → asyncpg `DataError`,
  bins committed then 500'd on the audit write (audit-trail violation); fixed `str(bin_.id)`, commit
  `136e98d` (the 9a/11a keeper recurring — GELATO's `Bin` is the **first int-PK audited entity**, worth a
  repo-wide `write_audit(target_id=)` sweep, logged under PLAN `## Noticed`); (2) the 11b dead-through-UI
  trap pre-empted — verify + the Putaway Vitest both assert the **real `PutawayRequest` payload shape**.
  **Next action:** `/zj:verify 12a`.

- **Branch (D-P12a-4, amended):** `feature-gelato-bins-putaway` off HEAD `da9474e` (code-identical to tag
  `zj/good-11b-crumb-sales-orders`/`fec334f`, docs on top). 11a/11b unmerged; 12a stacks. Checklist (all 14
  ticked): `docs/tasks/feature-gelato-bins-putaway.md`. Lint gates remain non-functional (BACKLOG p1) —
  correctness rests on verify_* (19/19) + Vitest (108), per project convention.

## (historical) Position

- **Step:** **PLAN COMPLETE** — **Phase 12a (GELATO bins & directed putaway) planned 2026-07-17.**
  Phase 12 (GELATO-01, 8 ACs) **split 12a/12b at plan** (D-P12a-1, owner — mirrors 9a/b/c + 11a/b):
  **12a** = bins CRUD + directed putaway (inbound foundation; covers GELATO-01 AC1/AC2 + the putaway
  portion of AC7/AC8; **NO GL, NO sales-order/reservation, NO pick/pack/ship**); **12b** = pick → pack
  → ship + reservation relief + COGS JE (the outbound + GL crux; AC3/4/5 + ship-side AC7/AC8). Three
  owner decisions set the shape: (1) **split 12a/12b, plan 12a now**; (2) **bin_id on the existing
  `syerp_inventory_txn` ledger** — one ledger, one bin dimension, roll-up to the location total
  guaranteed by construction (D-P12a-2); (3) **full staging-bin moves in 12b** (D-P12a-4, binds 12b).
  PLAN.md = **14 tasks** in 4 waves (models → migration 0015 [`gelato_bin` + `bin_id` col] → perms →
  schemas → SYERP `post_putaway`/`get_bin_on_hand` primitive → thin GELATO `service/` package → router
  + self-register → `verify_gelato.py` + `verify_gelato_api.py` → full regression → FE nav/Bins/Putaway/
  tests). Recurring keepers baked in: verify inputs built in the **real router/UI payload shape** (the
  11a/11b dead-through-UI trap), the non-optional **HTTP-level audit/RBAC** script, and a **load-bearing
  `asyncio.Barrier` concurrency** scenario on putaway-vs-putaway (FOR UPDATE, D-V3-18). Decisions
  D-P12a-1..9 recorded; no `## Decisions needed` open. Plan checked goal-backward at manager review
  (every SC → ≥1 task, every task → an SC, real files + runnable verify). **Next action:** `/zj:build 12a`.

- **Branch (D-P12a-5):** build 12a on a fresh `feature-gelato-bins-putaway` cut off the verified 11b
  tip (tag `zj/good-11b-crumb-sales-orders`, `fec334f`) — 11a/11b unmerged; 12a stacks. Lint gates
  remain non-functional (BACKLOG p1, known); correctness rests on the verify_* suite + Vitest.

- **Step:** **RETRO'D** — **Phase 11b (CRUMB sales orders + soft-reservation) closed 2026-07-17**,
  tag `zj/good-11b-crumb-sales-orders` (`fec334f`). **CRUMB-01 complete (all ACs).** Roadmap marked
  `[done — verified + retro'd]`. Retro banked three keepers (LEARNINGS Phase 11b): (1) **verify built
  its inputs in a shape the UI never sends** — `item_id=` hand-fed while the UI sends `plum_part_id`
  only — so 17/17 green certified a dead-through-UI headline feature; the 11a "green-but-broken"
  pattern recurred with a nameable mechanism (verify inputs must match the real router/UI contract);
  (2) **run verifier + reviewer in parallel and let a reviewer BLOCKER override a verifier PASS** — it
  has now caught the one defect that mattered on two consecutive phases; (3) **a multi-entry invariant
  needs one shared resolver wired into every door** (the `_resolve_and_validate_item_id` fix).
  Deferred items each have a home: quote→SO idempotency guard → BACKLOG p3; `plum_part_id` non-unique
  → accepted for single-shop; Closed-SO stale `qty_reserved` → cosmetic, recorded. **Next action:**
  `/zj:plan 12` (GELATO warehouse core — ship posts the COGS JE; realizes the D-P8-3 bin deferral).
  Optional: `/zj:log phase 11b` to file the formal work log; `/zj:ship` to merge the 11a+11b stack.

- **(historical) Step:** **BUILD COMPLETE** — **Phase 11b (CRUMB sales orders + soft-reservation) built 2026-07-17.**
  All **17 tasks** shipped on branch `feature-crumb-sales-orders` (cut off the verified 11a code tip
  `a8191cf`; tag `zj/good-11a-crumb-crm-pipeline` is docs-behind at `7c573d3`, code identical — see PLAN
  Deviations). CRUMB-01 completed (all ACs): SO models + migration 0014; direct SO CRUD + `SO-####`
  numeric-safe numbering + FSM (Draft→Confirmed→Fulfilling→Closed, +Cancelled from Draft/Confirmed);
  accepted-quote→SO conversion (item_id resolved from `plum_part_id`, free-text→NULL, source_quote/opp
  stamped); the **soft-reservation crux** — confirm reserves `min(qty_ordered, available)` with
  `available = get_item_on_hand − Σ open (confirmed/fulfilling) reservations ≥ 0`, `InventoryItem` rows
  `FOR UPDATE` locked in sorted-id order BEFORE the read (bills.py template), cancel releases; router
  audit + `crumb:read`/`crumb:write` RBAC; SO list/create/detail (ordered/reserved/shortage) + Convert-to-SO
  affordance. 11b posts **NO GL** (TB still nets zero). **Mandated Task-8 adversarial review → VERDICT
  PASS** (`REVIEW-task8.md`): invariant holds under concurrency; Medium finding (reservation not
  serialized vs raw stock write-offs) = **D-V3-18 by-design** (narrow lock; SYERP floor-guard deferred
  to Phase 12). **Proof:** backend `verify_crumb_so.py` (25 asserts incl. concurrency scenario F,
  mutation-tested load-bearing) + `verify_crumb_so_api.py` (40 asserts HTTP RBAC+audit) + all 15 existing
  verify_* → **17/17 green**; FE full suite **35 files/100 tests**; `npm run build` exit 0. **Next
  action:** `/zj:verify 11b`.

- **Branch (D-V3-19):** `feature-crumb-sales-orders` — 11a is unmerged; 11b stacks on it. Checklist
  (all ticked): `docs/tasks/feature-crumb-sales-orders.md`. Lint gates remain non-functional (BACKLOG
  p1, known) — correctness rests on the verify_* suite + Vitest, per project convention.

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
- **Last update:** 2026-07-19
- **Next action:** `/zj:plan 13` — the final v3.0 phase: **SYERP-13 AR & sell-side books** (7 ACs).
  Invoice-from-shipment (Dr AR 1120 / Cr Revenue), customer receipts (Dr Cash / Cr AR 1120), and an
  **AR aging report tying Decimal-exactly to the 1120 control account** with the Trial Balance still
  netting zero — closing v3.0 DoD clause 3. Builds on the shipments 12b posts (invoices key off a
  shipped shipment) + the SYERP-12 GL engine ✓. Keep the recurring keepers: the subledger↔control
  same-date-basis tie-out (09c), the control-ties-to-subledger assertion not just TB-nets-zero (Phase 10),
  the row-lock + `asyncio.Barrier` concurrency scenario on any receipt/allocation guard, the non-optional
  HTTP audit/RBAC script, and the real router/UI payload shape in verify + Vitest. Likely to sub-split at
  plan (mirrors 9a/b/c, 11a/b, 12a/b) — the DoD, not the phase count, is the contract.

## Next action (detail)

**`/zj:plan 13`** — SYERP-13 AR + invoicing from the shipment/SO — the last v3.0 clause. **Alternative —
pay down infra debt first:** the BACKLOG **p1** items (CI, live-DB pytest harness repair, both lint gates)
are now two milestones old; a debt-paydown phase is reasonable if the owner wants it (raise at `/zj:ideate`).
Also standing: the pick-path shipment-header races (BACKLOG p2, Q1/Q2) and the inbound half of the
bin-blind-desync item (p2) — weigh the shared cross-path row-lock refactor when a multi-writer deploy nears.

### (historical) Phase 11b verify target
**`/zj:verify 11b`** verified goal-backward against the 6 SCs: SO model/migration/wiring (SC1); direct
CRUD + FSM (SC2); accepted-quote→SO conversion (SC3); the soft-reservation invariant incl. the
concurrency crux (SC4 — re-run `verify_crumb_so.py` scenario F, it is mutation-tested load-bearing);
router audit + RBAC at HTTP level (SC5 — `verify_crumb_so_api.py`); FE + regression 17/17 + TB nets zero
(SC6). Deviations to review: SO list omits a cosmetic "total" column (header schema has no `total_value`);
branch cut off `a8191cf` not the bare tag (code-identical). Noticed follow-ups (all deferred, non-blocking):
Closed-SO stale `qty_reserved` (cosmetic), item→InventoryItem ambiguity (single-shop OK), 422 deprecation
sweep (BACKLOG p3).

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
