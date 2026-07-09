# LEARNINGS — BizNiceSweets

Kept lessons that change how we plan/build/verify future phases. Skip trivia; an empty
section beats a padded one. Newest phase at the bottom.

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
