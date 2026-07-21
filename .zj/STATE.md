# STATE — BizNiceSweets
Updated: 2026-07-21 (**v4.0 Phase 1 BUILD COMPLETE** — `/zj:build 1` on branch `chore-lint-gates-clean`
(cut off the plan-carrying tip `a6ee1fb`, code-identical to `origin/master`; Task-0 branch-point
deviation logged). **All 13 tasks (0–12) done, atomic commits, tree clean.** NFR-6 delivered: **both
lint gates fixed-to-clean + proven enforcing.** Wave A (frontend ESLint 10 flat gate): flat
`eslint.config.js`, `.eslintrc.cjs` deleted, `lint` de-`--ext`'d, `npm run lint` **exit 0**. Wave B
(backend `ruff` gate): ~1159 violations fixed-to-clean (1139 safe-autofix + F821×4 via `TYPE_CHECKING` +
F811 `seeded_db`→`tests/auth/conftest.py` + E741/F841 hand-fixed + 51 load-bearing `syerp/service`
re-exports `# noqa: F401`), `ruff check .` **exit 0**. Wave C: **23/23 `verify_*` exit 0** in-container +
**cold boot** (`/health/ready` 200, `import app.main` BOOT_OK) + Vitest **44/131** + `tsc -b && vite
build` exit 0; **red→green enforce proof** on both gates (planted violation → non-zero, revert → 0).
**One MATERIAL deviation → owner decision D-P1-1:** installed `eslint-plugin-react-hooks@7.1.1`
redefined `recommended` to bundle the React-Compiler ruleset (54 errors/41 files) — out of NFR-6 scope;
owner chose **pin to `^5`** (classic 2-rule recommended = plan intent). Added `frontend/.npmrc`
`legacy-peer-deps=true` (v5 peer-declares eslint≤^9) + re-declared `@testing-library/dom` — **both flagged
for NFR-4/Phase-3 CI** (`npm ci` must keep them). SRD NFR-6 → `implemented` (CI-wiring clause deferred to
NFR-4/Phase 3); `requirements-progress.md` NFR row added; checklist archived to
`docs/tasks/_completed/2026-07-21-chore-lint-gates-clean.md`. Unrelated `.vscode/settings.json` cosmetic
edit **stashed** at owner request (restore with `git stash pop`). **Noticed (non-blocking):** the
transient-red intermediate commit `e7c6e18` (testing-lib restored next commit; tip green); root
`tests/conftest.py` + `tests/core/conftest.py` predate the ABOUTME-header standard (future sweep).
**Next action:** `/zj:verify 1`.)

Prior: 2026-07-20 (**v4.0 Phase 1 PLAN COMPLETE** — `/zj:plan 1`. Phase 1 = **lint gates
fixed-to-clean (NFR-6)**; artifacts in `.zj/phases/01-lint-gates-clean/PLAN.md`. **13 tasks** (Task 0
branch + 12 work) in 3 waves — **A: frontend gate** (add `@eslint/js`/`eslint-plugin-react-hooks`/
`eslint-plugin-react-refresh`; write flat `eslint.config.js`; fix the `--ext`-broken `lint` script;
delete `.eslintrc.cjs`; fix to zero) · **B: backend gate** (ruff availability + convention; safe
`--fix`; audit/`# noqa`-guard side-effect imports FIRST; resolve the ~71 survivors — F821×4, F811/E741/
F841, UP035×~23, 2 unsafe) · **C: regression + enforce-proof** (23/23 verify_* in-container + Vitest +
build + **cold boot**; red→green gate proof; flip NFR-6 status). **Recon done at plan** (grounds the
scope): FE is near-clean already (`tsc -b` `noUnusedLocals`/`strict` keeps unused out; only 6
pre-existing `react-hooks/exhaustive-deps` disables, which prove react-hooks was the intended
ruleset) — deps `eslint@10.5.0`+`typescript-eslint@8.62.0` already installed, just no flat config;
BE has **1159 ruff violations, 1088 SAFE-auto-fixable**, config already committed in `pyproject.toml`
(E/F/I/UP), ruff pinned in `requirements-dev.txt` but absent from `.venv`/image. **Top risk (handled):**
blind F401 `--fix` could strip a load-bearing side-effect import (module self-registration /
`app/main.py` `import app.core.models`) and re-introduce the Phase-13 cold-boot 500 — sequenced as
audit-and-`# noqa`-first (Task 6) → review every deleted-import line (Task 7) → empirical cold-boot +
23/23 gate (Task 10). **3 owner decisions bound at plan:** D-M4-3 fix-to-clean (not ratchet);
**rule strictness = recommended sets only** (no tseslint recommendedTypeChecked, no ruff B/SIM/RUF);
**formatter scope = lint-check only** (no `ruff format`/`prettier --check`; E501 stays ignored).
No `## Decisions needed` open (one conditional escalation: if an F821 is a real runtime bug, stop +
surface). **Branch:** cut fresh `chore-lint-gates-clean` off `origin/master` (current
`feature-syerp-ar-invoicing` is fully merged, 0 ahead; it may be deleted). **Next action:**
`/zj:build 1`.)

Prior: 2026-07-20 (**v3.0 SHIPPED to master** — `/zj:ship`. The 11a→13 stack (135 commits) merged to
`master` via **PR #3**, fast-forward `3b762ba..87fb79d` preserving SHAs (same known-good pattern as v2.0's
PR #2) — `origin/master == 87fb79d`, PR #3 MERGED, all `zj/good-*` tags + annotated `v3.0` (→`e92b91d`)
pushed and reachable from master. **The standing `/zj:ship` master-merge debt is now CLEARED** (it had
carried since v2.0). Preflight was a fresh green on the branch tip: **23/23** live `verify_*` exit 0 +
**131/131** Vitest / 44 files + `npm run build` exit 0 (lint gates still non-functional, BACKLOG p1 — the
v4.0 headline). Changelog already carried v3.0 (generated at milestone close); `.zj/` + `docs/tasks/`
artifacts shipped in the merge per repo convention.

**v4.0 "Infra-debt + quality paydown" SPEC'D** (`/zj:spec`, 2026-07-20) — DoD confirmed into 5 clauses,
**NFR-4..8** written under new **PRD-12** (trustworthy engineering baseline; no new end-user capability).
Scope (D-M4-1, owner): NFR-4 CI (GitHub Actions, D-M4-2) + NFR-5 pytest-harness repair & `verify_*`
ported into the suite + NFR-6 both lint gates fixed-to-clean (D-M4-3) + NFR-7 shared inventory
FOR-UPDATE lock & inbound bin-blind fix + NFR-8 human UAT; **CRISP/offline deferred.** Proposed 5-phase
mapping in ROADMAP (lint → harness → CI → race-safety → UAT; dependency-first). Owner note: asked what
"CI" was → confirmed the milestone hardens the foundation, adds nothing users click. **Next action:**
`/zj:plan 1` (Phase 1 = lint gates fixed-to-clean, NFR-6). Post-merge housekeeping: delete the merged
`feature-syerp-ar-invoicing` branch when Phase 1 branches off master.

Prior: 2026-07-19 (**Milestone v3.0 "Customer & logistics" CLOSED + tagged `v3.0`** — `/zj:milestone`
done. DoD audited goal-backward (`.zj/MILESTONE-v3.0-AUDIT.md`): the WHOLE money loop driven on ONE
sales order end-to-end (order→reserve→pick→pack→partial-ship→invoice-from-shipment→post→partial+full
receipt→auto-Paid), all 3 clauses MET, 19/19 + 23/23 live `verify_*` + build + 131 Vitest. **Two gaps
found, BOTH FIXED at close (owner, D-M3-1/2, `97b977b`):** GAP-1 (AR aging falsely tripped a negative
1120 tie-out when a receipt predated its invoice_date — prepayment reclassified in `ar_aging_report`,
pinned by `verify_ar` scenario G, load-bearing) + GAP-2 (invoice picker bare UUID → resolved
`item_label`). **Records:** CHANGELOG v3.0 + milestone-close fixes, `.zj/logs/milestone-v3.0.md`
(130 commits, ~14.6h/10 sessions), LEARNINGS `## Milestone v3.0` (headline: review-not-verify caught
the defect on all 5 phases), DECISIONS D-M3-1..4 + index regenerated 73→134. Phases 11a/11b/12a/12b/13
archived to `.zj/history/v3.0/`. **Next milestone = v4.0 Infra-debt + quality paydown (D-M3-3).**
**Next action:** `/zj:spec` (sharpen the v4.0 DoD into clauses) then `/zj:plan 1`. Optional: `/zj:ship`
to merge the 11a+11b+12a+12b+13 stack to master.

Prior: 2026-07-19 (**Phase 13 RETRO'D** — `/zj:retro 13`. Roadmap already marked
`[done — verified 2026-07-19]`; no future phase resized. **LEARNINGS Phase 13 banked (1 surprise +
3 patterns):** (1) **the headline — mirroring a broad `except IntegrityError → retry` is only sound
if the mirrored fn can't raise a *different* IntegrityError, and adding a nullable FK the exemplar
lacks silently breaks that** (`create_invoice` copied `create_bill`'s number-collision retry but also
took an unvalidated `sales_order_id` FK → a bad id raised an FK error the retry misread as a collision
→ unbounded recursion/500; keeper = narrow the except to the specific constraint + bound it, AND
up-front-validate every FK the mirror doesn't have); (2) **a mandated adjacent-untouched-surface
regression assertion caught a real production-boot 500** the phase that introduced it (12a) had
mislabeled a "dev-only `--reload` race" — the `syerp_inventory_txn.bin_id→gelato_bin` metadata gap,
fixed by importing `app.core.models` at boot; keeper = the "assert the neighbour still works" task is
the only gate that exercises a cold process like production; (3) **dead-through-UI trap caught in-build
a 2nd straight phase** (`qty_invoiced`) — counter-measure now reliable; (4) **5th consecutive phase
where the review, not the verify suite, caught the defect that mattered** — budget both every phase.
Deferred items homed → BACKLOG p3: invoice void/credit-memo functional gap, dead `partially_paid` FE
badge, late-invoice COGS/revenue period split. **Phase 13 was the FINAL v3.0 phase (DoD clause 3
closed) — v3.0 milestone is now complete pending close-out.** Artifacts:
`.zj/phases/13-syerp-ar-invoicing/{PLAN,VERIFICATION,REVIEW}.md`, `.zj/LEARNINGS.md` Phase 13.
**Next action:** `/zj:milestone` (audit the v3.0 DoD, tag the release, archive phases 11–13, roll the
roadmap to the next milestone). Optional: `/zj:log phase 13` (formal work log); `/zj:ship` to merge the
11a+11b+12a+12b+13 stack to master.)

Prior: 2026-07-19 (**Phase 13 VERIFIED** — `/zj:verify 13`, tag `zj/good-13-syerp-ar-invoicing`.
Both checks ran in parallel; all 7 SYERP-13 success criteria PASS empirically — `verify_ar.py` 17/17
+ `verify_ar_api.py` 29/29 + **23/23 full regression**, aging ties Decimal-exact to the debit-normal
1120 (no negation), TB nets zero WITH AR posted, BS balances, RBAC 401/403/200 on all 8 routes,
attributable audit rows; verifier mutation-proved the record_receipt lock (revert `for_update` →
over-collected 120/100). **Fix loop landed 1 REVIEW MAJOR + 3 doc gaps:** `create_invoice` took a
client-supplied nullable `sales_order_id` FK **unvalidated** → a bad id failed only on the header flush,
was misread as an invoice-number collision, and **recursed forever** (RecursionError/500); fixed with
up-front 404 validation + a one-attempt-bounded retry (`7610e63`), pinned by new `verify_ar.py` scenario
**(D2)** (bogus id → clean 404, persists nothing); doc gaps closed — SYERP-13 row added to
`requirements-progress.md`, SRD:478 flipped `planned`→`verified` (stamped `7610e63`), MAP migration head
refreshed `0012`/`0014`→`0017`. Closes v3.0 DoD clause 3 (the FINAL v3.0 phase). Artifacts:
`.zj/phases/13-syerp-ar-invoicing/{VERIFICATION,REVIEW}.md`. **Next action:** `/zj:retro 13` (banks the
mirror-exemplar-shares-no-FK-surface + unvalidated-FK→unbounded-retry learnings), then v3.0 milestone.)

Prior: 2026-07-19 (**Phase 13 BUILD COMPLETE** — `/zj:build 13` on fresh branch
`feature-syerp-ar-invoicing` (cut off the code-identical 12b tip carrying the plan; a bare-tag branch
would have dropped the plan — 12a/12b precedent). **All 18 tasks shipped**, SYERP-13 AR & sell-side
books end-to-end; **v3.0 DoD clause 3 closed**. Wave A: Invoice/InvoiceLine + Receipt/ReceiptAllocation
models + `qty_invoiced` accumulator on `crumb_sales_order_line` (dead-through-UI keeper: model→schema→FE
render→Vitest) + migration **0017** (clean up/down round-trip) + AR schemas. Wave B: `service/ar.py`
(`create_invoice` FOR-UPDATE lock on SO-line rows + price locked to SO `unit_price` + stamps qty_invoiced;
`post_invoice` → **Dr 1120 / Cr 4110** JE `entry_date=invoice_date`; `record_receipt` FOR-UPDATE lock on
invoice rows + reused `bills._is_overpayment` + **Dr cash / Cr 1120** JE + auto-Paid at zero) + `ar_aging_report`
(**NO negation** — 1120 debit-normal) + thin RBAC router `/syerp/ar/*` audit-after-commit. Wave C:
`verify_ar.py` **16 asserts green** — end-to-end tie-out (asserts the 12b COGS-on-ship JE, does not rebuild),
aging **grand_total == 1120 control Decimal-exact**, over-invoice/over-receipt 422, and **BOTH concurrency
locks mutation-proven** (revert record_receipt lock → 120-vs-100 over-collect; revert create_invoice lock →
joint 12-vs-10 over-invoice + qty_invoiced lost-update; restore → one success/one 422) — the 12b "only the
guard under test can reject" discipline honored; `verify_ar_api.py` **29 asserts** (HTTP 401/403/200 triad on
all 8 routes + attributable audit + inventory-receipt regression lock); **full regression 23/23 green**, TB
nets zero, BS balances. Wave D: Invoices list/create-from-shipment/detail + Receipts + AR Aging screen + nav +
routes; FE **44 files / 131 tests green**, `npm run build` exit 0. **Two material handlings, both fixed:**
(1) the AR `ReceiptCreate` schema (Task 5) **shadowed** the inventory costed-receipt `ReceiptCreate`, silently
breaking `POST /inventory/items/{id}/receipts` → renamed to `ArReceiptCreate`, regression-locked in
verify_ar_api; (2) the Task-13 regression assertion surfaced a **pre-existing 12a production 500** —
`syerp_inventory_txn.bin_id → gelato_bin` FK unresolvable on a fresh process (lazy gelato model imports +
importlib registration) → fixed in `main.py` by importing the `app.core.models` aggregator at boot
(**D-P13-8**; D-P12a-3 preserved). Plus a phantom-`partially_paid` docstring corrected (real FSM is
draft→posted→paid). Lint gates still non-functional (BACKLOG p1); correctness rests on verify_* (23/23) +
Vitest (131). Checklist (all 18 ticked): `docs/tasks/feature-syerp-ar-invoicing.md`. **Next action:**
`/zj:verify 13`.)

Prior: 2026-07-19 (**Phase 13 PLAN COMPLETE** — `/zj:plan 13` on branch
`feature-gelato-pick-pack-ship` (planning artifacts; build branches fresh). **Phase 13 = SYERP-13 AR &
sell-side books, the FINAL v3.0 phase** — closes v3.0 DoD clause 3. **Single phase** (owner, D-P13-1 — not
sub-split; AR aging is a thin copy of AP aging, TB/P&L/BS already exist from 9c). **18 tasks in 4 waves**
(`.zj/phases/13-syerp-ar-invoicing/PLAN.md`): Wave A schema (Invoice+InvoiceLine, Receipt+ReceiptAllocation
models mirroring Bill/Payment, `qty_invoiced` accumulator on `crumb_sales_order_line`, migration **0017**,
schemas) → Wave B service (`service/ar.py`: uninvoiced-shipments query, `create_invoice`, `post_invoice`
→ Dr 1120 AR/Cr 4110 Revenue JE, `record_receipt` + allocations + FOR-UPDATE guard → Dr cash/Cr 1120 JE +
auto-Paid; `ar_aging_report` in reports.py; thin RBAC router `/syerp/ar/*` audit-after-commit) → Wave C
verify (`verify_ar.py` control-tie + invoice-from-shipment match + overpayment reject + COGS-on-ship tie +
**two load-bearing concurrency scenarios** — over-receipt AND double-invoice, both mutation-proven;
`verify_ar_api.py` HTTP RBAC/audit; full regression + TB nets zero) → Wave D frontend (Invoices
list/create-from-shipment/detail, Receipts, AR Aging screen + nav; Vitest asserts real payload shape incl.
`qty_invoiced` render). **Key facts:** COGS-on-ship JE (Dr 5100/Cr 1130) **already shipped in 12b** —
Phase 13 asserts it, doesn't rebuild (D-P13-3); invoice price **locks to SO-line `unit_price`** (owner,
D-P13-2); `qty_invoiced` claimed at draft-create mirroring AP (D-P13-5); AR aging control-tie has **NO sign
negation** (1120 debit-normal — top risk, D-P13-7). All 5 recurring keepers baked in (concurrency-from-start
with the 12b "only the guard under test can reject" fixture discipline, subledger↔control as EQUALITY not
zero, dead-through-UI field wired end-to-end in Task 3, non-optional HTTP audit/RBAC script, full regression
gate). Decisions D-P13-1..7 recorded; no `## Decisions needed` open; plan checked goal-backward at manager
review (every SC → ≥1 task, every task → an AC, real files + runnable verify). **Branch (D-P13-6):** build
on a fresh `feature-syerp-ar-invoicing` off tag `zj/good-12b-gelato-pick-pack-ship` (`553bcfb`); migration
0017. **Next action:** `/zj:build 13`.)

Prior: 2026-07-19 (**Phase 12b RETRO'D** — `/zj:retro 12b` on branch
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

- **Step:** milestone — **v3.0 "Customer & logistics" CLOSED + tagged `v3.0`** (`/zj:milestone`,
  2026-07-19). DoD audited goal-backward — whole money loop on one order end-to-end, all 3 clauses MET,
  19/19 + all 23 `verify_*` + build + 131 Vitest; 2 audit gaps BOTH fixed at close (D-M3-1/2, `97b977b`,
  pinned by `verify_ar` scenario G + FE tests). Records produced; phases 11a/11b/12a/12b/13 archived to
  `.zj/history/v3.0/`; roadmap + PROJECT rolled to **v4.0 Infra-debt + quality paydown (D-M3-3)**.
  **Next action:** `/zj:spec` (sharpen the v4.0 DoD into clauses) then `/zj:plan 1`. Optional:
  `/zj:ship` to merge the 11a+11b+12a+12b+13 stack to master.

- **(historical) Step:** **RETRO'D** — **Phase 13 (SYERP-13 AR & sell-side books — the FINAL v3.0 phase) closed
  2026-07-19** (`/zj:retro 13`), tag `zj/good-13-syerp-ar-invoicing`. Roadmap marked
  `[done — verified 2026-07-19]`; **v3.0 DoD clause 3 closed → v3.0 milestone complete pending close-out.**
  LEARNINGS Phase 13 banked (mirror-a-retry-only-safe-if-no-new-FK headline; adjacent-surface regression
  caught a real boot 500; in-build dead-through-UI catch a 2nd phase; review-caught-the-defect 5 phases
  running). Deferred → BACKLOG p3: invoice void/credit-memo, dead `partially_paid` badge, late-invoice
  COGS/revenue period split. **Next action:** `/zj:milestone` (v3.0 close). Optional: `/zj:log phase 13`;
  `/zj:ship` to merge the 11a+11b+12a+12b+13 stack.

- **(historical) Step:** **BUILD COMPLETE** — **Phase 13 (SYERP-13 AR & sell-side books — the FINAL v3.0 phase)
  built 2026-07-19** (`/zj:build 13`) on branch `feature-syerp-ar-invoicing`. All 18 tasks, **v3.0 DoD
  clause 3 closed**. Delivers the invoice (Dr 1120/Cr 4110) + receipt (Dr cash/Cr 1120) JEs + AR aging
  tying Decimal-exactly to the 1120 control (the COGS-on-ship JE was asserted, not rebuilt — D-P13-3).
  Proof: `verify_ar.py` 16 asserts (both concurrency locks mutation-proven) + `verify_ar_api.py` 29 asserts
  + **23/23** full regression (TB nets zero, BS balances) + FE **44 files / 131 tests** + `npm run build`
  exit 0. Decisions D-P13-1..8 (D-P13-8 = the app.core.models boot import). Plan + checklist all ticked.

- **(historical) Step:** **RETRO'D** — **Phase 12b (GELATO outbound: pick → pack → ship) closed 2026-07-19**
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

- **(historical) Step:** **PLAN COMPLETE** — **Phase 12b (GELATO outbound: pick → pack → ship) planned 2026-07-18.**
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

- **(historical) Step:** **RETRO'D** — **Phase 12a (GELATO bins & directed putaway) closed 2026-07-18** (`/zj:retro 12a`),
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

- **(historical) Step:** **PLAN COMPLETE** — **Phase 12a (GELATO bins & directed putaway) planned 2026-07-17.**
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

- **(historical) Step:** **RETRO'D** — **Phase 11b (CRUMB sales orders + soft-reservation) closed 2026-07-17**,
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
- **Milestone:** **v3.0 Customer & logistics — CLOSED + tagged `v3.0`** 2026-07-19 (all phases verified +
  retro'd; DoD audited goal-backward, 2 gaps fixed at close; phases archived to `.zj/history/v3.0/`).
  **Next milestone = v4.0 Infra-debt + quality paydown (D-M3-3).** v2.0 + v1.0 closed + tagged.
- **Branch:** `chore-lint-gates-clean` — v4.0 Phase 1 **BUILD COMPLETE** (all 13 tasks committed, tree
  clean, `19` commits over `origin/master`). Cut off the plan-carrying tip `a6ee1fb` (code-identical to
  `origin/master == 87fb79d`). Not yet verified/shipped. The merged `feature-syerp-ar-invoicing` branch
  may be deleted.
- **Last update:** 2026-07-21
- **Next action:** **`/zj:verify 1`** — verify v4.0 Phase 1 (NFR-6 lint gates) goal-backward against
  SC1–SC5: FE flat config + clean `npm run lint`; BE `ruff check .` clean; both gates enforce
  (red→green); no regression (23/23 `verify_*` + cold boot + Vitest + build). Build evidence + the
  D-P1-1 deviation are in `docs/tasks/_completed/2026-07-21-chore-lint-gates-clean.md`. The CI-wiring
  clause of NFR-6 is deliberately OUT of scope (deferred to NFR-4/Phase 3) — do not fault the phase for
  it. Then `/zj:retro 1`.

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
