# LEARNINGS — BizNiceSweets

Kept lessons that change how we plan/build/verify future phases. Skip trivia; an empty
section beats a padded one. Newest phase at the top.

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
