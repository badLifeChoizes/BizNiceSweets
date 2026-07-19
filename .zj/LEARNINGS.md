# LEARNINGS — BizNiceSweets

Kept lessons that change how we plan/build/verify future phases. Skip trivia; an empty
section beats a padded one. Newest phase at the top.

## Phase 13 — SYERP-13 AR & sell-side books (verified 2026-07-19)

The final v3.0 phase: invoice-from-shipment (Dr 1120 / Cr 4110) → receipt (Dr cash / Cr 1120)
→ AR aging tied Decimal-exact to the debit-normal 1120, TB still nets zero, BS balances.
Built by mirroring the AP side (`create_bill` / payments / `ap_aging_report`) shape-for-shape.
Verifier returned PASS (17/17 + 29/29 + 23/23 regression); the parallel reviewer found the one
MAJOR that mattered — the **fifth consecutive phase (11a/11b/12a/12b/13) where the code review,
not the verify suite, caught the defect that mattered.** The recurring signal is now a fact of
this project's process, not a coincidence: the verify suite proves the happy path and the
targeted concurrency/tie-out cruxes; the adversarial review finds the input the plan never
imagined. Budget both, every phase.

### Surprises (assumptions wrong → corrected truth)

- **Mirroring an exemplar's broad `except IntegrityError → retry` is only sound if the mirrored
  function cannot raise a *different* IntegrityError than the one being retried — and adding a
  nullable FK the exemplar lacks silently breaks that invariant.** `create_bill` retries on an
  `INV-####`/`BILL-####` unique-number collision by catching *any* `IntegrityError`, rolling
  back, and re-running — sound there because a number collision is the **only** IntegrityError
  that path can produce. `create_invoice` copied that block verbatim but also accepts an
  `Optional[str] sales_order_id` — a real FK to `crumb_sales_order` that `create_bill` has no
  analogue for — and passed it into the header **unvalidated** (unlike `customer_id` and each
  line's `sales_order_line_id`, both SELECT-gated). A bogus `sales_order_id` makes `flush()`
  raise an **FK** IntegrityError; the broad except misreads it as a number collision, rolls back,
  and recurses with the identical bad id → deterministic unbounded recursion → `RecursionError`/
  500 after ~1000 round-trips (a self-inflicted mild DoS), nothing persisting, no clean 422.
  **Keeper: when you mirror a retry-on-IntegrityError block, the retry is only safe if you (a)
  narrow the `except` to the *specific* constraint (inspect the constraint name / `orig`) and
  bound it (retry-once, like `create_bill` actually does), AND (b) validate up front every FK the
  mirrored function accepts that the exemplar didn't — a new nullable FK is exactly the surface
  the copied error-handling was never written to cover.** Fixed in `7610e63`: SELECT-gate
  `sales_order_id` → 422 when absent (mirroring the customer gate), plus a bounded retry; pinned
  by new `verify_ar` scenario (D2) — bogus id → clean 404/422, persists nothing. This is the
  AP-mirror cousin of 12b's "the exemplar's safety rested on a property your use case doesn't
  share" — there it was repeatable-vs-terminal; here it's a-FK-surface-the-exemplar-lacks. The
  mirror is a strong *default*, but every field the mirror doesn't have is un-audited by the copy.

### Patterns that worked (repeat these)

- **A mandated regression assertion against the *adjacent untouched* surface caught a real
  production-boot 500 that the phase which introduced it had mislabeled.** Task 13's plan required
  asserting the pre-existing costed inventory-receipt endpoint still accepts its body after AR
  landed. That assertion returned 500 on a **fresh** app process: GELATO imports its models lazily
  (D-P12a-3), so `importlib` module registration left `gelato_bin` out of `Base.metadata` and the
  cross-module string FK `syerp_inventory_txn.bin_id → gelato_bin` was unresolvable until some
  gelato call happened to load the models — order-dependent, which is exactly why 12a's Noticed
  mis-diagnosed it as a "dev-only `--reload` race." Fixed (`ea2f2cb`) by importing the central
  `app.core.models` aggregator at boot — the same metadata contract Alembic and every verify
  script already rely on — with D-P12a-3 preserved (SYERP still never imports gelato). **Keeper:
  the "assert the neighbouring feature you *didn't* touch still works" task is not busywork — it
  is the only gate that exercises a cold process the way production boots, and it caught a latent
  cross-module metadata defect that all of 12a/12b's own green suites sailed past because their
  fixtures had already warmed the models. Keep writing the adjacent-surface regression assertion
  into every phase that shares a table/FK with a prior one.**

- **The dead-through-UI trap was caught in-build for the SECOND straight phase — the counter-measure
  is now reliable, not lucky.** `qty_invoiced` was added to the SO line model and had to reach the
  read schema + FE type + render or go invisible (the 11a/11b/12a blank-column trap). Because the
  plan's FE task said "render the accumulator" AND the Vitest asserted the value renders, the full
  contract (backend serialization included) was driven end-to-end and the field shipped live. Same
  outcome as 12b's `qty_shipped`: writing "assert the column actually renders its value" into the
  frontend task converts the recurring trap into a non-event.

- **Latent schema-shadow bug caught at build by the same-file naming discipline.** The new AR
  `ReceiptCreate` schema shadowed the pre-existing inventory costed-receipt `ReceiptCreate` in the
  shared `schemas.py`, silently rebinding `POST /inventory/items/{id}/receipts` to the wrong body.
  Renamed to `ArReceiptCreate` (zero prior refs) at build. Cheap catch, but a reminder that a flat
  shared `schemas.py` across a growing module makes name collisions a live hazard — prefer a
  module/feature prefix on new request schemas when the file is already crowded.

### Deferred (each has a home)

- **Invoice void / credit memos** — no decrement path for `qty_invoiced`; out-of-scope for v3.0,
  filed to BACKLOG as a real functional gap so it isn't lost.
- **`partially_paid` phantom status** — never emitted by the API (real FSM is `draft|posted|paid`;
  a partial receipt stays `posted`). Backend docstrings corrected at build; a harmless dead FE
  badge variant remains as defensive rendering — drop in a future FE tidy (BACKLOG p3).
- **COGS/revenue period split on late invoices** — `execute_ship` ages COGS on ship date, the
  invoice ages AR on invoice date; correct, but the two can land in different periods. Acceptable
  for v3.0; noted for any future revenue-recognition matching work (BACKLOG p3).

## Phase 12b — GELATO outbound pick → pack → ship + COGS JE (verified 2026-07-19)

The outbound crux: pick (bin-aware net-zero to staging) → pack (FSM) → ship (bin-aware
`post_issue` from staging + atomic Dr 5100 COGS / Cr 1130 JE + reservation relief), closing
v3.0 DoD clause 2. Built by mirroring MOUSSE `issue_components` shape-for-shape. Verifier
returned PASS (21/21); the parallel reviewer found a BLOCKER — the **fourth consecutive phase
(11a/11b/12a/12b) where the code review, not the verify suite, caught the one defect that
mattered.** But this one is the sharpest of the four, because the verify suite *had* a
concurrency test aimed straight at the bug and it went green anyway.

### Surprises (assumptions wrong → corrected truth)

- **A concurrency test can pass for the WRONG reason and thereby mask the exact bug it
  targets — a green forced-interleave scenario is not proof unless its fixture lets ONLY the
  guard under test reject.** `execute_ship` gated on `shipment.status == "packed"` read from an
  UNLOCKED `db.get` and locked only the `InventoryItem` rows, so two concurrent ships of one
  *packed* shipment both passed the FSM gate → double inventory issue + double COGS JE + double
  reservation relief. Scenario (g) — the phase's own `asyncio.Barrier(2)` two-ship test — went
  green, so SC4's concurrency claim read as proven. It masked the blocker because its staging
  bin was seeded to *exactly* the ship qty, so `post_issue`'s **floor guard** incidentally
  rejected the second draw — a *different* guard catching the duplicate for an unrelated reason,
  while the FSM/row-lock defect sailed through untested. With an ample or residual-staged bin
  (normal WMS practice) the double-post goes through. **Corrected truth / keeper: when you write
  a forced-interleave test, construct the fixture so the guard under test is the ONLY thing that
  can reject the second actor — give every *other* guard (floor, over-ship, quantity) enough
  slack to pass. The new scenario (h) does exactly this: order 10, ship 5, ample staging, so the
  over-ship guard and floor guard both have headroom and only the shipment-row lock can 409 the
  duplicate. Mutation-proven: revert the lock → successes=2 / je_count=2 / qty_shipped=10.** A
  green concurrency assertion whose fixture lets a bystander guard do the rejecting is the
  concurrency-axis cousin of 11b's "verify built its input in a shape the UI never sends" — the
  test exercises a path, just not the one it claims to.

- **Mirroring an exemplar's concurrency pattern faithfully still ships a race when the
  exemplar's safety rests on a property your use case doesn't share.** The build copied MOUSSE
  `issue_components`' "read status → lock item rows → mutate" shape verbatim, and the build-time
  note reasoned the item locks were "belt-and-suspenders" redundant. Both were wrong for ship:
  MOUSSE's status-before-lock shape is safe *only because issuing is an intentionally repeatable
  operation* — re-issuing is a legitimate no-harm replay. Ship is a **one-shot terminal
  transition** (packed → shipped, posting an irreversible GL fact), so the same shape is a
  double-post, and the item locks (which serialize DB *access* to the stock rows) do NOT protect
  the one-shot *status gate* — only a lock on the row whose status gates the transition does.
  Fix: `select(Shipment).where(id==...).with_for_update()` before the FSM gate, so the loser
  blocks, re-reads `shipped`, and 409s. **Keeper: the exemplar's lock is on the resource; a
  one-shot FSM transition must also lock (or re-assert after locking) the row whose status is the
  gate. Before copying a concurrency pattern, ask whether the exemplar is safe because the
  operation is repeatable — if yours is terminal, the copied lock is necessary but not
  sufficient.** (This corrects, on the record, the build-time "either item lock alone suffices"
  reasoning — it held only for scenario (g)'s scarce-bin, two-*different*-shipments case.)

### Patterns that worked (repeat these)

- **The recurring dead-through-UI trap was CAUGHT DURING BUILD this time, not at verify.** SO
  detail rendered a "Shipped" column from `qty_shipped`, but `SalesOrderLineRead` didn't
  serialize `qty_picked`/`qty_shipped` — the 11a/11b/12a blank-column trap set up to strike a
  fourth time. The engineer caught it in-build (fix commit "serialize qty_picked/qty_shipped on
  SalesOrderLineRead") because the plan's Task 15 explicitly said to render from the accumulator
  AND the FE test asserted the value renders. Confirmation: the counter-measure (drive/assert the
  real contract end-to-end, backend-serialization included) works — writing "assert the column
  actually renders its value" into the frontend task is what turns the recurring trap into an
  in-build catch instead of a verify-loop finding.

- **Parallel verifier + reviewer, reviewer-blocker-overrides-PASS, is now load-bearing four
  phases running — budget it as non-optional, most of all when verify is green.** 11a (part-less
  line), 11b (dead-through-UI), 12a (bin-split desync), 12b (concurrent double-ship): each time
  the verifier returned PASS and the reviewer found the defect that mattered. 12b is the strongest
  case yet *for* the review because verify didn't merely lack the test — it *had* the test and it
  was falsely green. The independent adversarial read reasons about the input/interleaving domain
  the harness's own fixtures can't reach. This is settled practice; a green verify is never a
  reason to skip it.

### Deferred items (each has a home — logged at verify, trued up here)

- **Two pick-path shipment-header races (reviewer Q1/Q2)** — concurrent first-pick creates two
  open shipments per SO (Q1); pick can append a line to a shipment a concurrent pack just flipped
  (Q2). No ledger corruption (per-item `post_putaway` lock holds), but both break the "≤1 open
  pick per SO / no post-pack append" assumptions. → **BACKLOG p2**, same lock family as the
  cross-path ledger race; fix = lock the SO row (or a unique partial index: one open shipment per
  SO) + re-assert shipment status on append.
- **Bin-blind-desync p2 item half-closed.** 12b makes the OUTBOUND path (pick `post_putaway` +
  ship `post_issue`) bin-aware, so pick→ship keeps the `bin_id` dimension consistent. Still open:
  `post_transfer`/`post_adjustment`/MOUSSE `issue_components` remain bin-blind. **BACKLOG p2
  updated** to record the outbound half is done, inbound/adjust half remains.
- **Migration 0016 downgrade path has no automated test** — exercised only by the manual
  `downgrade -1 && upgrade head` round-trip. → **BACKLOG p3** (a durable downgrade-round-trip
  assertion would close it for all migrations at once).

## Phase 12a — GELATO bins & directed putaway (verified 2026-07-18)

First GELATO phase: a new `gelato` module (bins + directed inbound putaway) that added a
`bin_id` *dimension* to the shared SYERP inventory ledger. The cleanest new-suite build to
date on the concurrency axis — the pre-planned lock + Barrier came back CLEAN from review.
The one MAJOR was a genuinely new class, and the most instructive lesson of the phase:
adding a dimension to a ledger that other writers ignore.

### Surprises (assumptions wrong → corrected truth)

- **Adding a new dimension to a shared ledger silently corrupts that dimension for every
  existing writer that ignores it — and it is a SEQUENTIAL-correctness bug, not a race.**
  12a added `bin_id` to `syerp_inventory_txn` and made ONLY putaway bin-aware; the
  pre-existing draw primitives (`post_transfer`, `post_adjustment`, MOUSSE `issue_components`)
  keep writing `bin_id=NULL` and floor-guard per-*location*. So the moment a bin-blind draw
  leaves a location that holds binned stock, the bin it "left" overstates and the unbinned
  pool goes negative — receive 10 → putaway to bin A → adjust −10 ⇒ bin A still 10, unbinned
  −10, location total 0 (correct). The plan under-framed this as a *partial concurrency race*
  (cross-path lock deferred); the reviewer sharpened it to single-threaded rot in normal
  operation. **The location roll-up and the SC3 `Σ(bins)+unbinned==location` identity stay
  Decimal-exact — only the split lies**, which is exactly why every green assertion missed it
  (the same shape as the 09c/10 "a zero-sum identity can't see a subledger break" lessons,
  now on a physical dimension rather than a GL control account). Corrected truth / keeper:
  **when you add a dimension to a shared ledger, either make every writer of that ledger
  dimension-aware in the same phase, or explicitly scope the new dimension as trustworthy
  only until the first dimension-blind write — and pin that boundary with a test so the
  durable fix visibly changes it.** 12b (bin-aware pick/issue) is the durable fix and was
  told in writing not to assume 12a closed it.

- **A value clamp that hides the symptom can break the invariant you just proved.** The
  obvious mitigation for the negative unbinned pool was to clamp `get_bin_on_hand` at zero.
  Rejected — clamping would break the very SC3 `Σ(bins)+unbinned==location` identity that was
  this phase's crux (a clamped bin figure no longer sums to the location total). The chosen
  mitigation *preserved* the identity: a TRUST BOUNDARY docstring + `verify_gelato.py`
  scenario (E) that **pins** the stale-bin/negative-pool behavior AND re-proves the roll-up
  survives a bin-blind draw Decimal-exact. Keeper: **before clamping/suppressing a
  wrong-looking derived value, check whether the "wrong" value is load-bearing for a proven
  invariant — surface-and-pin the boundary rather than clamp it away.**

### Patterns that worked (repeat these)

- **The paired HTTP verify script earned its keep a THIRD consecutive suite — this time on a
  type-coercion defect only an int-PK entity could expose.** GELATO's `Bin` is the first
  int-PK entity ever written to `audit_log` (every previously-audited entity in mousse/crumb/
  syerp carries a uuid-string PK). The bin routes passed the integer `Bin.id` to
  `write_audit(target_id=...)`, but `audit_log.target_id` is `VARCHAR(36)`; asyncpg raised
  `DataError`, so each bin route **committed the bin then 500'd on the audit write — a bin
  created with no attributable audit row** (a traceability violation). `verify_gelato.py`
  (service-level) structurally could not see it; `verify_gelato_api.py` (real HTTP) caught it
  immediately (`str(bin_.id)` fix, `136e98d`). The reviewer then confirmed **no other int-PK
  audit target exists today**, so no repo sweep is owed — but the keeper for any future int-PK
  audited entity is concrete: **`write_audit(target_id=...)` must `str()` the id; the column
  is `VARCHAR(36)` and a raw int PK 500s the mutation *after* it commits.** The 9a/11a rule
  holds a third time — the HTTP script is non-optional because a service script cannot reach
  the router's audit/RBAC layer.

- **Concurrency pre-empted by design → clean review on that axis (the 9b rule paying off a
  third time, after Phase 10).** The FOR-UPDATE lock (on the `InventoryItem` master row —
  deviation-corrected from the plan's `InventoryTxn` prose, since the append-only ledger isn't
  the contention point) + a genuine `asyncio.Barrier(2)` two-putaway scenario, proven
  load-bearing, were planned in the *same task breath* as the mutation. The reviewer found the
  putaway↔putaway crux CLEAN. Continued confirmation: plan the row lock + a forced-interleave
  verify scenario with any invariant-guarding mutation and the recurring post-hoc concurrency
  major becomes a non-event. (The reviewer's only concurrency note was the *cross-path*
  putaway↔transfer/issue edge — the standing BACKLOG p2 ledger-race item, not a 12a regression.)

### Process notes

- **Reverse-hub FK works cleanly via a string table-name FK.** 12a needed a SYERP-*core* table
  (`syerp_inventory_txn`) to reference a GELATO-owned table (`gelato_bin`) — the reverse of the
  normal hub direction (satellites reference the hub, not vice-versa). `ForeignKey("gelato_bin.id")`
  as a **string** (SQLAlchemy resolves lazily by table name, so no Python import of gelato models
  into syerp) avoided the import cycle; migration 0015 creates `gelato_bin` before the FK. No boot
  or Alembic-resolution issues. Reusable whenever a future satellite module must be referenced by a
  hub-owned table.
- **9th consecutive DB-touching phase paying the same two taxes:** in-container verify needs
  `PYTHONPATH=/app`; neither lint gate runs (both BACKLOG p1). Continued evidence only, not
  re-litigated. (One transient `verify_mousse_api` failure this phase was a uvicorn `--reload`
  worker-restart race from `podman cp` of a source file mid-loop — not a code defect; clean on the
  settled re-run. Note for future in-container fix-loops: let `--reload` settle before re-running the
  full suite.)

## Phase 11b — CRUMB sales orders + soft-reservation (verified 2026-07-17)

CRUMB-01 completed: SO FSM, accepted-quote→SO conversion, and the soft-reservation crux
(lock-before-read, Σ-reserved over open SOs, concurrency-proven). Clean build — and then the
**same class of blind spot as 11a struck again**, in a sharper, more instructive form. The
parallel code review caught a BLOCKER while 17/17 verify assertions stayed green.

### Surprises (assumptions wrong → corrected truth)

- **The 11a "green-but-broken" keeper recurred — with a nameable mechanism: verify built its
  inputs in a shape no UI path sends.** `verify_crumb_so.py` passed `item_id=` directly to the
  line-create schema. But the frontend line editor sends a part line as `plum_part_id` ONLY, and
  the *direct* create/add/update service path never bridged `plum_part_id→item_id` (only the
  conversion path did). Result: every UI-created SO line persisted `item_id=NULL`, reserved 0 on
  confirm, and showed a false "Non-stock" badge + full shortage even with stock on hand — the
  **headline feature was dead through the UI** while every verify assertion passed, because the
  test constructed the one input shape the UI never produces. **Corrected truth / keeper:
  service-layer verify scripts must construct inputs in the SAME shape the router/UI actually
  sends — resolve-from-`plum_part_id`, not hand-fed `item_id`. Green over a synthetic shape
  proves a path no user travels.** This is the 11a lesson made concrete: it's not just "verify
  misses negative space," it's "verify can mismatch the real input contract and certify a dead
  feature." Both times the fix included a NEW load-bearing assertion driving the *real* shape
  (11b's `(D2)` asserts a `plum_part_id`-only line resolves to the linked stock item).

### Patterns that worked (repeat these)

- **Run verifier and reviewer in parallel, and let a reviewer BLOCKER override a verifier PASS.**
  The verifier returned PASS (17/17, source-read); the reviewer, working the same diff
  independently, found the dead-through-UI blocker the harness structurally hid. The manager
  treated the reviewer's blocker as authoritative over the premature PASS, ran a fix loop, and
  re-verified. **The independent adversarial review is not redundant with verify — on this
  project it has now caught the one defect that mattered on two consecutive phases. Budget it as
  non-optional, especially on "low-risk, just-mirror-the-exemplar" builds where verify feels
  sufficient.**
- **A multi-entry invariant needs ONE shared resolver, wired into every entry point from the
  start.** Root cause was asymmetry: conversion resolved `plum_part_id→item_id`
  (`_resolve_item_id_for_part`); direct create/add/update copied `item_id` verbatim. The fix
  factored a single `_resolve_and_validate_item_id` used by all three direct paths, reusing
  conversion's resolver. Keeper: **when two+ entry points must establish the same invariant
  (here: a line needs a resolved `item_id` to reserve), the resolution belongs in one helper on
  the shared path, never re-implemented (or forgotten) per entry point.** Same shape as the 11a
  "structural guard before value early-return" lesson — invariant enforcement must not depend on
  which door you came through.
- **The concurrency crux got a real load-bearing test, not a mock.** Scenario F
  (`asyncio.gather` + `Barrier`, two independent sessions, on-hand 10 / each orders 7, ×5) asserts
  combined `qty_reserved == 10` exactly — and is proven load-bearing (removing the FOR-UPDATE lock
  fails it). Plus the mandated Task-8 adversarial review of the invariant ran *before* verify.
  Repeat for any concurrency/invariant crux: assert the invariant under genuine contention and
  prove the guard is what holds it.

### Deferred items (each has a home)

- **Quote→SO conversion has no idempotency guard** — an Accepted quote converts to unlimited
  duplicate SOs (no status change, button always visible). Owner chose fix-blocker-only at verify.
  → **BACKLOG p3** (`.zj/BACKLOG.md:176`); fix when post-conversion quote lifecycle is specified
  (candidate: 422 re-convert if an SO already stamps this quote, or a `converted` quote status).
- **`InventoryItem.plum_part_id` has no uniqueness constraint** — conversion/resolution picks the
  lowest `id` deterministically. **Accepted for the single-shop model, no action**; if a shop ever
  links two sellable items to one PLUM part the chosen item is arbitrary. Follow-up only if it
  bites: a primary/sellable flag or uniqueness constraint. Documented in PLAN `## Noticed`.
- **Closed SOs retain stale `qty_reserved`** (cosmetic; Closed ∉ the OPEN availability sum, so no
  invariant impact). Optional zero-on-close. Recorded in VERIFICATION Gaps #2 / REVIEW-task8 #3.

## Phase 11a — CRUMB CRM & pipeline (verified 2026-07-16)

First v3.0 phase: a whole new `crumb` suite (leads → opportunities → quotes + comm log) built
by mirroring MOUSSE. The smoothest large build to date — and yet the code review, not the
verify scripts, caught the one defect that mattered.

### Patterns that worked (repeat these)

- **Start a new module's service as a package from day one.** CRUMB shipped as `crumb/service/`
  (`_common`, `leads`, `opportunities`, `quotes`, `interactions` + `__init__` re-export) instead of
  a single `service.py` — applying the D-V3-9 lesson (SYERP's 3,800-line monolith that had to be
  split under duress) *preemptively*, at the architect's call. Zero refactor debt; each entity's
  logic stayed small. Every new suite should start as a package, never as one file that later
  metastasizes.
- **Mirror the newest exemplar module wholesale.** A 19-task new suite landed with only a 4-gap
  fix loop because MOUSSE (Phase 10) was copied shape-for-shape: self-register, audit-after-commit
  at the router, RBAC gating, FSM transition tables (`STAGE_TRANSITIONS`/`QUOTE_TRANSITIONS`), the
  numeric-safe `QUOTE-####` generator (the D-P8-6 shape), and the paired verify scripts. The module
  pattern is now a worn groove; copying the freshest exemplar is the cheapest way to add a suite.
- **The two-tier verify pair again earned SC6.** `verify_crumb.py` (service, live Postgres) +
  `verify_crumb_api.py` (HTTP RBAC + attributable audit) — the plan made the HTTP script
  *non-optional* because a service-level script structurally cannot prove router-layer audit/RBAC
  (the 9a lesson). It caught the audit rows and the 403/401 gating that service tests can't see.

### Surprises (assumptions wrong → corrected truth)

- **20 green verify assertions missed a major defect; the code review caught it.** `verify_crumb.py`
  passed 20/20, yet a part-less quote line carrying a price but no description was silently accepted
  — an unlabeled, customer-facing $100 line. The **reviewer** (REVIEW.md #1), not the verifier,
  found it, plus two minor correctness gaps and one audit-asymmetry question. Corrected truth:
  **verify proves the paths you thought to write; it does not cover the negative space. The
  adversarial branch review is not redundant with verify — budget for it on every phase, most of
  all on a "just mirror the exemplar" one where the build feels low-risk.**
- **A value shortcut ran before the structural guard.** The root cause of the major defect:
  `_resolve_line_amounts` returned on the explicit-price branch *before* the part-or-description
  identity check ran. Keeper: **structural / identity invariants must be enforced before any
  value-based early return** — an early `return` past a guard is the same bug class as an early
  `continue` past a validation.

### Cost sinks (time planning didn't predict)

- **A mirror-the-exemplar build still needs a fix-loop budget.** The plan treated regression as
  "should hold trivially" and implicitly the whole build as low-defect because it copied MOUSSE.
  It still produced 1 major + 2 minor correctness gaps needing a build+re-verify cycle
  (`a697c69`, `efcf2e6`). Copying an exemplar retires *architectural* risk, not *correctness* risk
  in the novel business logic (pricing rules, FK validation, audit symmetry) — that logic is new
  every time and deserves the full review pass regardless of how familiar the scaffolding looks.

### Process notes

- **Autogenerate can't persist inside the container.** Task 2 `alembic revision --autogenerate` ran
  in-container but hit `PermissionError` writing the host bind-mounted `alembic/versions/`; the
  migration was hand-authored on the host to match the 0012 convention (circular
  `crumb_lead`↔`crumb_opportunity` FK broken via a post-create `op.create_foreign_key`). Autogenerate
  stays a *drift-detection aid only* — and it still can't exit clean (the p1 naming-convention item,
  re-hit here at Task 2). Migrations are authored by hand.

## Milestone v2.0 — Operations (closed 2026-07-16)

Roll-up of Phases 8, 9a, 9b, 9c, 10 (SYERP inventory/purchasing + GL/AP/reporting + MOUSSE
work orders). Distilled from the phase retros plus the milestone audit
(`.zj/MILESTONE-v2.0-AUDIT.md`), which traced all four DoD clauses end-to-end and found one
minor gap (G1). The milestone's spine was double-entry accounting, and its lessons cluster there.

### Repeat these

- **Assert a GL control account directly against its subledger — never against zero.** This was
  the milestone's hardest-won lesson (Phase 10, the 1130 drift), but it generalizes across the
  whole GL surface: every crux invariant this milestone shipped was a *zero-sum identity* — WIP
  clears to zero, GR/IR clears to zero, trial balance nets zero, balance sheet balances — and **not
  one of them can detect a control-account/subledger divergence**, because a mismatch preserves
  Σdr==Σcr by construction. The reviewer caught a real 1130-vs-perpetual-inventory drift that 34
  green assertions were blind to. Durable rule: to protect 1130/2110/2150…, assert
  `control_balance == Σ(subledger)` Decimal-exact; "the clearing account cleared" and "the books
  balance" are both true while the control account silently lies. (09c saw the seed of this — an
  `in_balance` identity is tautological; Phase 10 was the same bug one level out.)
- **Plan the row lock AND a forced-interleave verify in the same task breath as any invariant-
  guarding mutation.** The read-check-write concurrency major was caught post-hoc by the reviewer in
  Phases 7, 9a, and 9b — four times the sequential verify script was structurally blind to it. 9b
  codified the counter-pattern (`SELECT … FOR UPDATE` in sorted-id order + an `asyncio.gather`/
  `Barrier` two-request scenario). **Phase 10 was the first phase to add a live invariant-guarding
  mutation and have the reviewer find *nothing* on that axis** — because the lock and the
  forced-interleave scenario were planned in from the start and spot-checked red-without / green-with.
  The counter-pattern works; apply it pre-emptively, not after the fourth catch.
- **HTTP-level `verify_*_api.py` from the start.** 9a learned the hard way that a service-level verify
  script cannot prove router behavior (audit rows, 401/403 RBAC); 9b/9c/10 each shipped an API-level
  verify script from the plan. Now settled practice — router concerns get their own live-HTTP gate.
- **Standalone live-DB `verify_*.py` are the real integration gate** while the pytest harness stays
  down (D-P7-4). 13 scripts / ~200 assertions proved the entire v2.0 DoD backend; the milestone audit
  re-ran them clean. They carried regression protection across five phases with no automated suite.

### Never do these again

- **Never let a mechanical refactor's self-check reuse the transform's own node filter.** The
  D-P10-4 AST split of `syerp/service.py` filtered on `ast.Assign` and silently dropped two
  `ast.AnnAssign` maps (`PO_TRANSITIONS`/`BILL_TRANSITIONS`); its parity check shared the same filter
  and was blind to its own omission. Only pytest *collection* (an actual import) surfaced it — the
  `verify_*` scripts never import those names. Prove import-surface completeness by importing every
  public name, not by behavioral scripts that touch a subset.
- **Never port a PLAN's "verified" reference facts as fact.** Phase 10's plan Context asserted `Base`
  lived in `app.core.db` (it's `app.core.base`) and `syerp_inventory_txn.id` was an int PK (it's
  `String(36)`). Both wrong; the engineer caught them against source. Same family as v1.0's "never
  trust a doc's file path" — re-confirm import paths and column types at implementation.

### Process notes

- **A recurring reviewer-caught major is a planning gap, not bad luck — codify the counter-pattern
  the second time you see it, not the fourth.** The concurrency race cost a fix-loop in 7, 9a, and 9b
  before 9b's rule pre-empted it in 10. Three of those four were avoidable had the pattern been
  written down after the second occurrence.
- **The master-merge debt is now two milestones deep.** v1.0 and v2.0 were both tagged on the working
  tip of an *unmerged* feature branch (D-M1-1, D-M2-3); each phase cut off the previous unclosed tip
  (D-P8-11 and successors). Master is 98 commits behind and carries none of Phases 9–10. `/zj:ship`
  owes the reconciliation; deferring it per-phase compounds it per-milestone.
- **The p1 infra debt rode the whole milestone unpaid** — no CI, the live-DB pytest harness still
  broken, both lint gates still non-functional. Correctness rested entirely on `verify_*` + Vitest for
  five phases. It held, but the debt is now two milestones old and was deferred again at close in
  favor of Customer & logistics (D-M2-4).
- **The milestone audit earned its cost again** (as in v1.0): goal-backward from the DoD found G1 — a
  first-render report error the phase verify never exercised — that all five phase verifications
  missed. Cheap insurance; run it every milestone.

## Phase 10 — MOUSSE work-order core, materials-only (verified 2026-07-16)

### Surprises (assumptions that were wrong → corrected truth)
- **"WIP clears to zero" + "trial balance nets zero" are BOTH Σdr==Σcr identities — neither can
  detect a GL-control-vs-subledger divergence, and the phase's whole verify suite rested on exactly
  those two.** `verify_mousse.py` proved the 1140 WIP account returned to its pre-WO balance
  Decimal-exact and the TB still netted zero (34/34 green). The reviewer still found a MAJOR: on
  completion the clearing JE debited 1130 by `accumulated_wip` while `post_receipt` capitalised only
  `planned_qty × fg_unit_cost` into the inventory subledger, so on non-divisible WIP (100/3) the
  1130 **control account** permanently drifted from the perpetual-inventory valuation (Σ on_hand ×
  moving_avg) by a sub-quantum every WO. Both green assertions are blind to it *by construction*: a
  clearing-account-returns-to-X check is a property of one account's own postings, and TB-nets-zero
  is the universal Σdr==Σcr identity — **a control-account/subledger mismatch changes neither**.
  This is the exact cousin of the 09c "`in_balance` is tautological" lesson, one level out: there,
  the balance-sheet identity couldn't catch a composition bug; here, two *different* zero-sum
  identities couldn't catch a subledger tie-out break. **Durable rule: to protect a GL control
  account (1130/2110/2150…) you must assert it directly against its subledger — `control_balance ==
  Σ(subledger)` — never against zero, never against the trial balance. "The clearing account
  cleared" and "the books balance" are both true while the control account silently lies.** The fix
  (`5cffeeb`, D-P10-2 amended) routes the residual to a seeded 5190 Inventory Rounding account so
  1140 clears AND 1130 ties; `verify_mousse.py` scenario D now asserts `1130 debit == FG receipt
  value` and `5190 == residual`.
- **A single completion JE moved TWO ledger accounts and only ONE was invariant-checked.** The plan's
  crux ("1140 returns to pre-WO exactly") framed completion as a one-account event; the same JE also
  debits 1130, whose correctness is a *separate* invariant (tie to subledger, above) that no
  assertion covered. **Rule: when one mutation posts to N accounts, enumerate an invariant per
  account before writing the verify — the account the plan is focused on clearing is rarely the only
  one that can be wrong.**

### Patterns that worked (repeat these)
- **The recurring concurrency-major class was pre-empted by design, not just absent — this is the
  9b rule paying off, and the first proof it does.** Phases 7/9a/9b each had the reviewer catch a
  read-check-write major the sequential verify couldn't express; 09c dodged it only because a
  read-only phase has no such write. Phase 10 *did* add an invariant-guarding mutation (issue
  decrements on-hand under a floor guard) — the class was live — yet the reviewer found nothing on
  that axis, because the FOR-UPDATE row lock (Task 8, `create_bill` template) **and** the
  `asyncio.Barrier`-forced two-concurrent-issue verify scenario (Task 13) were planned in from the
  start and spot-checked red-without-lock / green-with-lock. **Confirmation: for any new mutation
  guarding a hard invariant, plan the row lock + a forced-interleave verify scenario in the same
  task breath — it converts the recurring post-hoc major into a pre-empted non-event.** (Caveat the
  reviewer still raised: the issue lock serializes issue-vs-issue only, not issue-vs-SYERP-adjustment
  against the same item — the broader inventory-ledger lock gap, now concrete since MOUSSE writes
  this ledger; homed to BACKLOG p2.)

### Cost sinks / recurrences (no new lesson, continued evidence)
- **Mechanical AST refactor had a silent blind spot that only `import` caught.** The D-P10-4
  syerp `service.py` split filtered module-level constants on `ast.Assign` and so dropped two
  `ast.AnnAssign` (type-annotated) maps, `PO_TRANSITIONS`/`BILL_TRANSITIONS`; the split's own parity
  check shared the same filter and so was blind to its own omission. Nothing surfaced it until
  pytest *collection* failed importing `test_purchasing.py` — the `verify_*` scripts never import
  those names, so they stayed green (`3d59068` re-exported them). **Rule: a mechanical transform's
  self-check must not reuse the transform's own node filter — verify import-surface completeness by
  actually importing every public name (collection/`__all__` parity), not by the behavioral scripts,
  which only touch a subset of the API.**
- **Two "verified" reference facts in the PLAN Context were wrong** — `Base` is `app.core.base` (not
  `app.core.db`), and `syerp_inventory_txn.id` is `String(36)` (not an int PK). The engineer caught
  both against real source at Task 2. Same family as the v1.0 "never trust a doc's file path" lesson:
  even a plan's own "verified" Context drifts; re-confirm types/import paths against source at
  implementation, don't port the prose.
- **7th consecutive phase paying the same two taxes:** in-container verify needs `PYTHONPATH=/app`;
  neither lint gate runs (both BACKLOG p1). Noted as continued evidence, not re-litigated.

## Phase 09c — AP aging + financial statements (verified 2026-07-12)

### Patterns that worked (repeat these)
- **First phase since Phase 6 with zero reviewer majors — and the reason is structural, not luck.**
  Phases 7 / 9a / 9b each had the reviewer catch a major the green live-verify missed (a poison
  input, a zero-cost regression, a concurrency race). 09c had none, because a **read-only
  derivation phase has no read-check-write and no new invariant-guarding mutation** — the only
  write was the additive `bill_date` column, which guards no invariant. The entire "reviewer finds
  the concurrency/domain major the sequential verify can't express" class (the recurring 7/9a/9b
  finding) simply had **no home** here. **Triage signal for planning: a report/statement phase that
  only derives from already-posted data is structurally low-risk on the concurrency axis — spend the
  review budget on sign-convention and derivation correctness (the two Risks that mattered here),
  not on lock analysis.** Conversely, the moment a phase adds a mutation that guards an invariant,
  the 9b concurrency rule reactivates.
- **The subledger↔control tie-out (SC2, the crux) was made provable by a plan-time date-basis
  decision, not by the verify assertion.** The aging subledger ages bills on `bill_date`; the 2110
  control account ages journal lines on `entry_date`. These are *different columns* — the tie-out
  can only hold exact-Decimal if they carry the same value, so D-P9c-1 set the bill JE
  `entry_date = bill.bill_date` at post time (`729ec00`). Same shape as 09b's GR/IR
  (make-it-hold-by-construction, then assert equality) and 09a's coalesce. **Durable rule: a
  subledger↔control tie-out holds only if both sides age on the same date basis — unify the date
  basis at write time, then assert `Decimal == Decimal` exact. If you find yourself needing a
  tolerance on a tie-out, the date bases have diverged; fix the posting, don't loosen the assert.**

### Surprises (assumptions that were wrong → corrected truth)
- **`in_balance == True` on the balance sheet is a *tautological* assertion — it can never fail, so
  it proves nothing about the line it was meant to check.** `assets == liabilities + equity` is a
  mathematical consequence of every JE balancing *plus* the computed `net_income = Σrevenue −
  Σexpense`; there is no ledger state that makes it false (the reviewer confirmed: `in_balance`
  cannot be driven false). So the SC5 `in_balance` check, run alone, is green by construction and
  would stay green even if the computed 3130 net-income line were doubled or mislabelled. The real
  risks — the unconditional 3130 line **double-counting** if 3130 ever carries a posting (REVIEW #1),
  and the "Current Year Net Income" label being **all-time R−E** rather than fiscal-year-bounded
  (REVIEW #2) — are *presentation/composition* bugs the identity structurally cannot catch. What
  saved SC5 was that `verify_reports.py` *also* asserted the **composition**: exactly one appended
  3130 row, its amount `== profit_loss(BOT, as_of).net_income`, and zero posted 3130 lines. **Rule:
  when an invariant holds by construction, asserting the invariant is worthless — assert the
  composition that could actually be wrong (the row count, the line's provenance, the sign), not the
  identity that must be true.** This is the balance-sheet cousin of the 09b "snapshot a control and
  assert it *returns*, not that it's zero" lesson: assert the thing that can break, not the thing
  that can't.

### Cost sinks (time planning didn't predict)
- **Same two recurring taxes, no new ones (6th consecutive phase):** in-container verify still needs
  `PYTHONPATH=/app` and neither lint gate ran (both BACKLOG p1, unwritten wrapper / flat-config).
  Noted only as continued evidence; not re-litigated.

## Phase 09b — AP bills, PO match & payments (verified 2026-07-12)

### Patterns that worked (repeat these)
- **The clearing-account invariant is best proven as a pre/post derived-balance *equality*, not an
  absolute.** The GR/IR-clears-to-zero crux held Decimal-exact because `verify_ap.py` (e) captured
  the 2150 balance *before* the receipt and asserted it returned to that exact value after
  receive→post_bill (−450.000000 → −450.000000), instead of asserting "== 0" (2150 carries balance
  from other unbilled receipts, so an absolute-zero assert would be both wrong and untestable on a
  shared account). What makes the equality hold: `post_bill` **ignores the user's `unit_cost` and
  books at the PO line's `unit_cost`**, and forces `matched_qty == full live unbilled_qty` — so a
  single bill's Dr GR/IR is arithmetically identical to the receipt's Cr GR/IR. Reuse the "snapshot
  a control balance, mutate, assert it returns" shape for any clearing/suspense account.
- **HTTP-level verify planned from the start (the 09a rule) paid off immediately.** `verify_ap_api.py`
  existed in the plan (Task 12) as a first-class gate, not a fix-loop afterthought, and proved the
  three audit rows + full 403/401/200 RBAC that `verify_ap.py` structurally cannot reach. Second
  consecutive phase where planning the router-level script up front removed the 09a-style gap before
  it opened. This is now settled practice — keep it for 9c.

### Surprises (assumptions that were wrong → corrected truth)
- **A sequential verify script is structurally blind to read-then-write races — the reviewer caught
  the major again (4th time: 7, 9a, and now the concurrency class).** Both guards this phase exist
  is to prevent — double-billing a receipt (GR/IR never clears) and overpaying a bill (AP negative)
  — were implemented as read-check-write with **no row lock**, and a fully green `verify_ap.py`
  (24 sequential scenarios) could never surface it because two concurrent transactions is not a
  scenario a sequential driver *can* express. Fix: `SELECT … FOR UPDATE` on the contended PO-line /
  bill rows, acquired up-front in sorted-id order (deadlock-safe), so the second txn blocks and
  re-reads the true billed/paid sum. **The durable rule: any read-check-write guarding a hard
  invariant needs (1) a row lock or DB constraint, AND (2) a `asyncio.gather` two-concurrent-request
  verify scenario that asserts exactly one succeeds and the other 422s.** A sequential PASS proves
  the guard's arithmetic, never its concurrency. Scenarios (j)/(k) are now that template.
- **This concurrency class was *not* deferrable, unlike the identical inventory-ledger races (BACKLOG
  p2, accepted-risk for single-shop).** The distinction that matters: the inventory moving-average
  drift *self-heals on the next receipt*, but a double-billed receipt leaves GR/IR permanently
  non-zero and an overpaid bill leaves AP permanently negative — the phase's own crux, breached
  irreversibly. **Rule for triage: a read-check-write race is deferrable only if its breach
  self-corrects; if it corrupts a ledger invariant permanently, it's a major even single-shop.**
  The `create_bill`/`record_payment` FOR UPDATE code is now the in-repo template for when the
  inventory-ledger locking finally lands (MOUSSE / first multi-writer deploy).

### Cost sinks (time planning didn't predict)
- **Same two recurring taxes, no new ones:** in-container verify still needs `PYTHONPATH=/app`
  (5th DB-touching phase paying it — the "bake it into a wrapper" fix still unwritten), and neither
  lint gate ran (5th consecutive phase, BACKLOG p1). Noted only as continued evidence both p1 items
  are real; not re-litigated.

### Process notes
- **Two service-scope gaps surfaced only at the router/verify layer, both fixed same-phase without
  a deviation from plan intent:** `record_payment` (T7) shipped without the `list_payments` read its
  `GET /ap/payments` route (T10) needed, and `create_bill` (T5) validated each matched line's
  exact-match independently so two matched lines against the *same* `po_line_id` in one payload could
  jointly over-bill (a same-payload cousin of the concurrency race) — fixed by rejecting duplicate
  `po_line_id` within a bill. **Takeaway:** when planning a service function, enumerate its *reads*
  the router will need (not just the mutation) and the *within-payload* duplicate-key cases, not only
  the cross-request ones.

## Phase 09a — GL posting engine + receipt auto-post (verified 2026-07-11)

### Patterns that worked (repeat these)
- **Service-level verify scripts structurally cannot prove router-level behavior.** `verify_gl.py`
  drove the service functions directly, so `write_audit` and `require_permission` — both of which
  live in the **router**, not the service — were never exercised. SC5 (audit rows + 403 RBAC) read
  green while having *zero* automated proof; it was provable only by hand in the verify session
  (gap G2). Fix was a second script, `verify_gl_api.py`, that POSTs/reverses/receives over live
  HTTP and asserts the `audit_log` rows + 401/403 on every endpoint. **Rule for 9b/9c and every
  future phase: any criterion whose behavior lives in the router — audit writes, RBAC gating,
  HTTP status mapping — needs an HTTP-level verify script, planned from the start, not a
  service-level one.** A service-driven script proves domain logic and silently skips the whole
  router surface.
- **The fix-loop "every mandated criterion becomes an executable test" rule held again.** The two
  verifier-mandated gaps became durable guards: G1 (atomicity rollback) → `verify_gl.py` scenario
  (f) forces the JE to fail mid-`receive_line` and asserts *both* the stock txn and the JE roll
  back; G2 → the new `verify_gl_api.py`. This is the third phase (7, 8, 9a) where turning the gap
  into a red/green script is what closed it.

### Surprises (assumptions that were wrong → corrected truth)
- **Adding a mandatory atomic side-effect to an existing flow narrowed the inputs it accepts — a
  regression even though the atomicity was correct.** Wiring the balanced-JE post into Phase-8's
  `receive_line` meant an all-zero JE (from a schema-legal `unit_cost=0` — samples, consignment,
  warranty replacements) hit the balance validator, failed the XOR/≥2-line check → 422, and rolled
  back the *entire valid receipt*. The unit-of-work was sound; the new coupling shrank the accepted
  input domain vs. Phase 8, where that same receipt succeeded. Fix: skip the GL post when
  `amount == 0`. **Rule:** when you thread a new required side-effect through an existing
  transaction, enumerate the original flow's legal inputs the side-effect might now reject (here:
  zero-value) — the atomicity being correct does not mean the flow still accepts what it used to.
- **SQL `SUM` NULL-propagates on single-sided derived balances.** `func.sum(debit) - func.sum(credit)`
  returns `NULL` (→ 0) whenever *either* side has no rows — i.e. any single-sided or control account
  (all-debit, or a credit-only account like GR/IR 2150). A $60 debit account reported $0; the
  receipt's GR/IR movement read as 0. Fix: `coalesce(sum(debit),0) - coalesce(sum(credit),0)` per
  side (empty account still 0−0=0). This is exactly the defect class the broken DB-pytest (D-P7-4)
  would mask, and it's the live proof that caught it. **9b/9c derive AP-control and cash balances
  the same way — coalesce each side independently from the first draft.**
- **The reviewer again found the majors the green live-verify missed — via domain reasoning, not
  the exercised path** (Phase 7 lesson, confirmed a second time). Both majors were invisible to a
  passing `verify_gl.py`: the zero-cost regression above, and a missing double-reversal guard —
  nothing stopped reversing an already-reversed entry, so a second accountant's reverse re-applied
  the original and the derived control account silently diverged from on-hand inventory (now a 409).
  **Keep running review *and* live-verify; a green empirical drive is never a substitute for domain
  reasoning over the input domain.**

### Cost sinks (time planning didn't predict)
- **The in-container verify scripts need `PYTHONPATH=/app`** — the plan's bare
  `python scripts/verify_gl.py` fails `ModuleNotFoundError: app` inside `compose_api_1`. Same class
  as Phase 8's `.env`-substitution / throwaway-container gotchas. The "bake the verify HOW-TO into a
  wrapper" fix from Phase 8 still doesn't exist; every DB-touching phase keeps paying the tax.
- **Neither lint gate ran — a fourth consecutive phase** (already homed to BACKLOG p1). Noted only
  as further evidence the p1 item is real; not re-litigated here.

### Process notes
- **No DESIGN.md for a frontend-bearing phase (G5) — accepted** because tasks 11–13 carried explicit
  per-task acceptance criteria in PLAN.md. Fine for a phase reusing an established design system
  (`GLAccounts.tsx` layout, `ReceiveLineDialog` form pattern); flag if a future frontend phase
  introduces genuinely new UX rather than restyling existing patterns.

## Phase 08 — SYERP inventory & purchasing (verified 2026-07-08)

### Patterns that worked (repeat these)
- **Standalone live-DB `verify_*.py` scripts are our real integration gate while the pytest
  harness is broken.** With the async live-DB pytest suite still down (D-P7-4), the phase crux
  (receive → on-hand → moving-average) was proven by three scripts run against live Postgres —
  `verify_inventory` 15/15, `verify_purchasing` 18/18, `verify_e2e_p8` 18/18. This is the same
  "prove it with a script, not the suite" move Phase 7 used. Keep doing it for any DB-touching
  phase **until the harness is repaired** — but see the durability cost below.
- **`verify_e2e_p8.py` ran against a freshly-migrated empty DB (alembic 0001→0008 + seed + full
  flow), not the dev DB.** That is a stronger definition-of-done than asserting against an
  already-populated database — it proves migrations, the idempotent `Main` seed, and the flow
  from nothing. Make the fresh-DB e2e script the default shape for future phases.
- **Pure Decimal boundary tests pre-empted the whole numeric-vs-lexicographic bug class.**
  `_next_item_code`/`_next_po_number` were tested at the 9→10 digit boundary and asserted
  non-lexicographic — the exact defect that shipped in Phase 7 (`generate_part_number`). Writing
  the boundary test *with* the generator, not after a bug, is what changed. Same for the
  moving-average and negative-floor predicates: fast, repeatable, exact.
- **Wave order backend→UI per domain, with the backend proven live before its UI exists**, kept
  each layer honest (inventory backend + verify_inventory → inventory UI → purchasing backend +
  verify_purchasing → purchasing UI). The UI never got built on an unproven backend.

### Surprises (assumptions that were wrong → corrected truth)
- **`except IntegrityError → regenerate code → retry` assumed the only flush IntegrityError is a
  unique-code collision. False.** A bad advisory FK (`plum_part_id` not in `plum_part`) raises the
  *same* `IntegrityError`; the retry branch rolled back, minted a fresh code, re-inserted the
  **same bad FK**, and the second flush re-raised unhandled → HTTP 500 (`update_item` had no
  try/except at all → 500 on commit). Corrected: pre-validate the advisory FK and reject 422
  (`_validate_plum_part`, `554c3fe`) — this is exactly the D-P8-2 "PLUM link is advisory, must
  degrade" case. **Rule going forward:** a broad `except IntegrityError` that "fixes and retries"
  must first distinguish *which* constraint fired (inspect `err.orig`/constraint name), or it will
  silently mishandle every other integrity error. The one input never existence-checked (the
  item's own FK) was the one that broke; `add_line` was safe only because it pre-validated.
- **Per-file test runs hid a real regression; only the full suite caught it.**
  `InventoryItemDetail.test.tsx` (written against Task-11 *stub* dialogs) passed in isolation but
  broke once the real Adjust/Transfer dialogs landed — their location `useQuery` hit the mock's
  catch-all, got a non-array, and `locations.filter` threw. **Run the full frontend suite before
  declaring a UI wave done**, not just the files you touched; a seam mock written against a stub
  goes stale the moment the stub becomes real.
- **A plan's `pytest -k "po_number or fsm"` acceptance command selected 0 tests** — the `-k`
  expression assumed node-name substrings that didn't exist (real names were `test_generator_*` /
  `test_po_transitions_*`). A green "0 selected, 0 failed" is a false pass. **Verify any `-k`
  selector actually selects the intended tests before writing it into a plan's acceptance step**
  (here the engineer added `po_number`/`fsm` pytest markers so the command means what it says).

### Cost sinks (time planning didn't predict)
- **podman-compose does not substitute the repo-root `.env` into container env** in this
  environment — a bare `up -d db` brings up Postgres with an empty `POSTGRES_PASSWORD` and refuses
  to initialize, which burned verify time. Workaround: `set -a; . ./.env; set +a` before
  `podman-compose up`. The `db` service is also intentionally not host-published, so live scripts
  must run inside a throwaway `compose_api` container. **Bake both into the verify HOW-TO / a
  wrapper** so every future DB-touching phase doesn't rediscover them.
- **Neither lint gate ran, again.** `ruff` is absent from `.venv` and the image; `npm run lint` is
  broken repo-wide (ESLint 10 needs a flat `eslint.config.js` that doesn't exist). Correctness
  rested entirely on tests + verify scripts; `tsc -b` was the only enforced static check. This is
  now a *recurring* per-phase cost/risk — folded into the CI/lint p1 backlog items; treat as a
  hard pre-merge chore, not a per-phase surprise.

### Durability caveat (why the "worked" pattern is also a liability)
The verify-script approach *proves* behavior but does not *pin* it: no suite or CI runs those
scripts, so a silent break in the phase crux (SYERP-11.4), audit-row writes (10.7/11.7), or RBAC
(10.8/11.8) would pass every automated gate. That's the owner-accepted deferral, already BACKLOG
p1 — but the lesson is explicit: **standalone verify scripts are a verification tool, never a
regression tool.** Every phase we close on scripts adds to a growing pile of unpinned behavior.

## Phase 07 — Close v1.0 gaps (verified 2026-07-09; built 2026-07-04, retro'd after Phase 8)

### Patterns that worked (repeat these)
- **The review caught what the live verification could not.** `/zj:verify` drove
  `generate_part_number()` against a live DB — seeded `P99999`, `P100000`, `P-DUPE-01`, got the
  right answer, marked SC2 PASS. The reviewer instead read `schemas.py:122`, saw `part_number` is
  `String(50)` with **no pattern constraint**, and reasoned about the *input domain* rather than the
  exercised path: a legal `P9999999999` matches `^P[0-9]+$` and overflows the new
  `cast(..., Integer)`. That is the blocker. **Empirical drive proves the happy path; only domain
  reasoning finds the poison input.** Keep running both — a live-green verify is not a substitute
  for a review, and this is the phase that proves it.
- **The fix loop's "every criterion becomes an executable, red/green-proven test" rule.** Each guard
  was validated by *reverting the fix and watching it fail*: revert one of four aliases → only that
  assertion breaks; revert `Numeric`→`Integer` → `NumericValueOutOfRangeError`; delete the
  `invalidateQueries` line → the positive test fails and the negative stays green. A test never seen
  red is an assumption. Make this the default close-out for a GAPS verdict.
- **Splitting a generator's tests into a pure half and a live-DB half** (`tests/plum/test_part_number.py`
  runs in the ordinary suite; `scripts/verify_part_numbering.py` covers the SQL). The pure half
  survives the broken harness. Same shape Phase 8 used for `_next_item_code` — now confirmed twice.

### Surprises (assumptions that were wrong → corrected truth)
- **A fix can be strictly worse than the bug it fixes.** The old lexicographic `MAX()` produced
  *duplicate* part numbers — annoying, recoverable, per-request. The Phase-7 "fix" traded it for a
  **permanent, user-triggerable denial of service**: any `plum:write` user could plant one legal row
  and every subsequent auto-numbered `create_part` returned 500 forever, recoverable only by hand-
  deleting the row. **Rule:** when a fix introduces a cast or coercion over a column, check the
  column's *declared* domain (`String(50)`, no pattern), not the values you imagine it holds. Widen
  to a type that cannot fail over that whole domain (`Numeric`, not `BigInteger` — the latter just
  moves the cliff to 19 digits).
- **"Verified live" ≠ "protected."** SC1 and SC2 both passed live and both had **zero** executable
  regression protection: the committed `tests/plum/{test_avl,test_import_export,test_parts}.py` cases
  that nominally cover them have *never once executed* (harness broken). A phase can be honestly PASS
  and still leave its own fixes free to silently re-break. Verification must report *pinned-by*
  separately from *works* — the VERIFICATION.md "Regression protection" table is what surfaced this.
- **The silent skip is the root cause behind this entire phase.** `_check_db_available()` feeds a
  `postgresql+psycopg2://` SQLAlchemy URL to raw `psycopg2.connect()`, which rejects it; a bare
  `except` turns that into "no DB → skip." 34 skipped reads as green. That one line is why the
  `SyerpPartner` ImportError shipped through four plans. **A large skip count is a FAIL, not a pass**
  — every DB-touching phase must assert the skip count, not just the exit code.

### Cost sinks (time planning didn't predict)
- **Verifying a phase *after* the next one shipped on top of it.** Phase 8 was built on the Phase-7
  branch before Phase 7 was verified, so verification had to (a) confirm the three fixes were still
  intact at a downstream HEAD and (b) re-run all three Phase-8 verify scripts after the `Numeric`
  fix touched shared PLUM service code — 66 live assertions re-run instead of 15. **Verify before
  you stack.** The ZJ phase order exists for this.
- **Neither lint gate ran — again** (`npm run lint` errors out: ESLint 10 wants a flat
  `eslint.config.js` that doesn't exist; `ruff` is absent from both `.venv` and the API image). Third
  phase in a row. Now homed as its own BACKLOG p1 item rather than being rediscovered per-phase.
- **The dev container image is stale**: in-container Excel export raises `ModuleNotFoundError: openpyxl`
  despite `requirements.txt` pinning it, and `pytest` isn't installed either. Any "run it in the
  container" verify step pays this tax until the image is rebuilt.

---

## Milestone v1.0 — Foundation + PLUM (closed 2026-07-09)

Roll-up of Phases 1–7. Distilled from the phase retros plus the milestone audit
(`.zj/MILESTONE-v1.0-AUDIT.md`), which found one major defect the phases had all missed.

### Repeat these

- **Audit goal-backward from the definition of done, not from the phase list.** Every phase in
  v1.0 was `[verified]`/PASS, and the milestone still surfaced a major defect (G1). Phase
  verification asks "did the plan get built?"; the milestone asks "does the product do what it
  promised?" They are not the same question, and the second one is the one that matters.
- **Standalone live-DB `verify_*.py` scripts are the real integration gate** while the pytest
  harness is down. 66 assertions across five scripts, all green, caught nothing false and proved
  the entire DoD backend. They earned their keep.
- **Making each success criterion an executable test** (Phase 7) — proven red *and* green — is
  what turned "we believe this works" into "this is pinned." The red proof is the load-bearing
  half; a test that has never failed is a test that has never been checked.
- **Statuses that stay pessimistic until proven are cheap insurance.** PLUM-06 sat at
  `partial (unverified)` for two phases. That caution was *correct* — it was hiding G1. A status
  is a claim about current code; do not upgrade it to make a table look finished.

### Never do these again

- **Never let "verified live" mean "verified at the API."** G1's backend traversal was correct
  and provable; the UI threw its answer away by keying off a field the API never sent. API-level
  proof does not transfer to the component that consumes it. When a capability spans a
  contract, verify *through* the contract, from the surface the user touches.
- **Never let a frontend read a field the backend does not emit.** The whole G1 class of bug is
  a silent contract drift: `entry.via_part_number` was always `undefined`, optional-chained into a
  plausible-looking fallback, so it degraded into a *wrong answer* instead of an error. Optional
  fields with sensible-looking fallbacks hide contract breaks. Prefer a required field, or assert
  the contract in a test.
- **Never trust a doc's file path.** `SRD SYERP-05` cited `syerp/seed.py` for months; the file is
  `coa_seed.py`. The root instructions repeated the same wrong name. Doc rot is silent and it
  compounds — `zj doctor` had 18 errors nobody had run.
- **Never describe a broken quality gate as a working one.** The root instructions advertised a
  "zero-warning policy" while *both* lint gates were non-functional (ESLint 10 with a legacy
  `.eslintrc.cjs` and no parser deps; `ruff` pinned but never installed). A gate you believe in but
  do not run is worse than no gate — it buys false confidence.
- **Never under-report the blast radius of a broken harness.** The SRD called the skips a PLUM
  problem. They were 98 skips across auth (38), plum (34), syerp (17), and core (7) — roughly 3×
  wider than documented, i.e. *every* module's DB-backed tests.

### Process notes

- **The commit-ordering trap:** Phase 7 (v1.0) fixes landed *after* all 30 of Phase 8's (v2.0)
  commits, because Phase 8 was planned before v1.0 formally closed (D-P8-11). Consequence: no
  commit in history is a clean v1.0 tree. If milestones are meant to be taggable, do not start
  the next milestone's build on the previous one's unclosed branch.
- **A milestone-close audit is worth its cost.** It found G1 (major, unprotected), G2 (a stale
  container image masking a working feature), 18 doctor errors, a stale PRD status, and a
  3×-understated harness gap — none of which seven phase verifications had caught.
