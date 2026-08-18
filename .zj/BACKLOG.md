# BACKLOG — BizNiceSweets
Updated: 2026-08-18 (v4.0 Phase 5 **retro** — five previously unhomed PLAN `## Noticed` items and
reviewer questions filed: p2 **module enable/disable has no server-side gate**; p3 the commented
`compose.yml` module templates that re-introduce `U0`, the unencoded `POSTGRES_PASSWORD` in the DSN,
operator-facing error copy naming entities by numeric id, and Receipts/Payments having no human
document number)
Prior: 2026-08-17 (v4.0 Phase 5 `/zj:verify 5` fix loop — gap G-5: the p2 item PLAN `## Noticed`
#13 promised for `post_transfer` / MOUSSE `issue_components`' unvalidated bins is **now filed**;
the p3 `uat.ps1` env-file item is **RESOLVED** (reviewer #4 — the `.env.db` block is ported from
`scripts/uat.sh`))
Prior: 2026-08-17 (v4.0 Phase 5 Task 38 — p1 **Rebuild `frontend/dist` + the API container image**
RESOLVED (and it exposed blocker `U2`, fixed+pinned); p2 **positive-adjust unvalidated `bin_id`**
RESOLVED by SC8 per owner decision D-P5-5. The p1 human-UAT item stays **open** and is re-pointed at
`.zj/QA.md` — the checklist is delivered, nobody has run it, and per D-P5-11 that ticks only when a
person clicks. Two p3 items filed: no `pytest` in the API image, and `uat.ps1`'s stale env-file guard.
The `verify_*` orphan-JE item re-measured at +100.00, so a second leaker exists and is unidentified)
Prior: 2026-07-25 (Phase 4 retro — two unhomed PLAN `## Noticed` items filed p3: pre-lock
`moving_avg_cost` staleness in `post_issue`/`post_putaway`, and `verify_purchasing.py` orphan
JE rows. Nothing resized; the p2 positive-adjust bin-membership item still needs an owner call)
Prior: 2026-07-25 (Phase 4 verify — two deferred review findings logged: positive-adjust
unvalidated bin_id [p2, decision needed] and `pick_for_shipment` unsorted item locks [p2];
`TransactionRead` bin_id omission + MOUSSE audit bins → p3)
Prior: 2026-07-25 (Phase 3 retro — the p1 **CI pipeline** item RESOLVED (NFR-4 verified,
tag `zj/good-03-ci-pipeline`); its residual niceties + the phase's 4 minor verify gaps folded
into a new p3 "CI hardening" item. True-up: the p1 "Port Phase-8 verify-script assertions"
item was actually resolved by Phase 2b (NFR-5) — checked off now)
Prior: 2026-07-24 (Phase 2b retro — CRUMB `crumb_lead`/`crumb_opportunity` latent
TRUNCATE-skip harness gap → p2; mitigated this phase, will bite the first ported test that
touches leads/opportunities)
Prior: 2026-07-22 (Phase 2a retro — the p1 "PLUM live-DB test harness never runs" item
RESOLVED by 2a and checked off; two residual harness checks the self-check test doesn't cover
[back-to-back rerun; committed non-vacuity] folded as a note into the p1 CI item, their natural home)
Prior: 2026-07-19 (Phase 13 retro — invoice void/credit-memo functional gap, dead
`partially_paid` FE badge, and late-invoice COGS/revenue period split → p3)
Prior: 2026-07-18 (Phase 12a verify — bin split desyncs after bin-blind movement → p2,
folds into the cross-path inventory-ledger race item; durable fix is the 12b bin-aware pick/issue)
Prior: 2026-07-16 (Phase 10 retro — MOUSSE now writes the inventory ledger so the p2
inventory-ledger race item's "revisit when MOUSSE writes this" trigger is live; zero-cost
lone-component issue → p3; 422 sweep + placeholder-dir prune now include mousse)
Prior: 2026-07-12 (Phase 9c retro — balance-sheet fiscal-close-gated defects → p2,
backdated-payment tie-out edge → p3, syerp `service.py` now ~3,700 lines in the split item)
Prior: 2026-07-12 (Phase 9b retro — 2 minor AP correctness edge-cases → p2, stale AP FE
types → p3, FOR UPDATE template cross-referenced into the inventory-ledger race item)
Prior: 2026-07-04 (seeded at adoption from the v1.0 milestone audit, codebase map, and the
kept items of `docs/tasks/chore-architecture-planning.md` — owner decision D-ADOPT-5)

## p1 — quality/infra debt that already bit once

- [x] **CI pipeline** — **RESOLVED by v4.0 Phase 3 (verified 2026-07-25, tag
  `zj/good-03-ci-pipeline`, NFR-4).** `.github/workflows/ci.yml`: four independent blocking jobs
  (`frontend` npm ci→lint→tsc→vitest→build; `backend-lint` ruff; `backend-tests` pytest vs a live
  `postgres:17` service, 232 passed / 0 skipped, self-provisioned `biznice_test` per D-P3-4;
  `verify-scripts` migrate+seed `biznice` then the 14 non-API `verify_*`) on every push/PR,
  red-proven on real runs (broken test + ruff/eslint violations), and required-status branch
  protection on `master` (PR #4). The runner honors `frontend/.npmrc` (SC7). The stretch goal
  ("live-Postgres job so DB tests actually run") landed too. Residual niceties folded in here by
  Phases 1/2a (standing enforce-smoke; pytest double-run; committed non-vacuity note) moved to the
  p3 **CI hardening** item below — including the standing caveat that `legacy-peer-deps=true` is a
  *global* peer-mask silencing conflicts on every future dep bump.
- [x] **PLUM live-DB test harness never runs (4 root causes confirmed 2026-07-04, Phase 7)** —
  **RESOLVED by v4.0 Phase 2a (verified 2026-07-22, tag `zj/good-02a-pytest-harness-repair`).**
  All four root causes fixed at the harness layer (`backend/tests/conftest.py`): libpq-keyword DSN
  probe, NullPool test engine + app-session monkeypatch, per-test `admin-user` identity seed, and
  per-test truncate-reseed isolation against a dedicated `biznice_test` DB. The ~100 formerly
  silent-skip tests now run 0-skip green twice back-to-back; DB is now a *hard* requirement (no-DB
  fails loud), and `tests/test_harness_selfcheck.py` pins the zero-silent-skip invariant so this
  exact regression fails loud, never silently. Original diagnosis below, kept for the record.
  deferred by owner (D-P7-4) until blocking/asked. The `skip_if_no_db` suite has *always*
  silently skipped, even inside the API container. Confirmed causes: (1) `tests/conftest.py`
  `_check_db_available()` passes the `postgresql+psycopg2://` SQLAlchemy URL to raw
  `psycopg2.connect()`, which errors `invalid dsn` → probe always False → all 33 PLUM tests
  skip (1-line fix: `.replace("+psycopg2","")`); (2) with the probe fixed, every test fails
  `sqlalchemy.exc.InterfaceError` — the module-level async engine (`app/core/db.py`) is bound
  to a different event loop than each pytest-asyncio test (needs NullPool or a per-test
  engine/session fixture); (3) no `admin-user` User is seeded though tests auth as
  `subject="admin-user"`; (4) no per-test isolation → `uq_plum_part_number` IntegrityError
  collisions on rerun against the persistent dev DB. This is the exact silent-skip that let
  the `SyerpPartner` 500 ship. Until fixed, PLUM fixes are proven by human-verify (D-P7-1) +
  standalone async scripts, not the pytest suite.
- [x] **Port Phase-8 verify-script assertions into runnable integration tests** (Phase 8 verify,
  2026-07-08, owner-accepted deferral) — **RESOLVED by v4.0 Phase 2b (verified 2026-07-24, tag
  `zj/good-02b-port-verify-cruxes`, NFR-5); checked off at the Phase 3 retro true-up.** All three
  named gaps closed: (1) the receive→on-hand→moving-average crux ported as a service-path pytest test
  (`test_moving_average_service_crux`, mutation-proven RED); (2)+(3) HTTP-level audit + 401/403 tests
  per module surface including the inventory receipt endpoint (Wave B, `13a27cf`). The SRD
  "script-only" caveats were dropped at 2b; the cruxes now also run on every push via the Phase-3
  `backend-tests` CI job. Original text kept in git history.
- [x] **Neither lint gate runs (Phases 6/7/8 — recurring)** — RESOLVED in v4.0 Phase 1
  (`chore-lint-gates-clean`, NFR-6, verified). Frontend now runs on a flat `frontend/eslint.config.js`
  (`npm run lint` exit 0); `ruff` installed at `backend/.venv/bin/ruff` (`ruff check .` exit 0); both
  fixed to a zero-violation baseline and proven enforcing (red→green). CI auto-run of the two gates
  still folds into the CI-pipeline item above (Phase 3 / NFR-4) — that item stays open.
- [ ] **Seed/startup integration test** — admin-seed path has no DB-backed regression test
  (a `MissingGreenlet` slipped past unit tests in Phase 2).
- [x] **Rebuild `frontend/dist` + the API container image** — **RESOLVED by v4.0 Phase 5 Tasks
  34–35 (2026-08-17).** Both rebuilt; the image now carries `openpyxl 3.1.5` (verified in-image),
  and the bundle served at `:8000` on a fresh prod volume is `index-BQmUVhcG.js`, byte-identical to
  `frontend/dist/assets/` — image and host are one build. **The rebuild exposed defect `U2`, a
  blocker: the image could not be built at all.** `COPY frontend/package*.json ./` never matched the
  dotfile `frontend/.npmrc`, so `npm ci` ran without `legacy-peer-deps=true` and died on the
  `eslint-plugin-react-hooks@5` peer range — a break introduced by Phase 1's lint devDeps and masked
  for five phases by the very staleness this item describes. Fixed `8d61cca`, pinned `f82ec38`
  (`backend/tests/test_containerfile_config.py`, RED on revert).
  **Residual, deliberately not fixed here:** `pytest` is still absent from the image, so the backend
  suite cannot run in-container (the bind-mounted venv carries host-path shebangs). Phase-5 Task 33
  ran it against a disposable `postgres:17-alpine` instead. The "add a test stage carrying dev deps"
  half of this item is therefore **not** delivered — refiled as a p3 item below.
- [x] **Refresh root `CLAUDE.md` stack/architecture sections** — done in Phase 7 Task 4
  (commit `5db8278`); Technology Stack + Architecture now describe the live FastAPI/React stack
  and cite `.zj/codebase/MAP.md`. (Any remaining Windows-path references elsewhere are out of
  that task's scope.)

- [ ] **[task] [p1] Run the human click-through checklist** (deferred at the v2.0 milestone close,
  D-M2-2; **re-pointed 2026-08-17, D-P5-11**) — **still open, and deliberately so.** The *checklist*
  is now delivered and complete: `.zj/QA.md`, 61 checks, requirement-keyed, 31/47 requirements
  covered with zero real gaps, against reproducible fresh-volume fixtures. **Nobody has run it** —
  `.zj/QA.md` §6 holds zero readings. Under `QA docs: non-blocking` that blocks no phase and no
  milestone, so this item will not be ticked by any engineering work; it is ticked only by a person
  clicking. Run order and its dependency rationale (read-only before mutating, GELATO back on before
  the GELATO sitting, money loop last) are the twelve-sitting table in
  `.zj/phases/05-human-uat/PLAN.md`. Record readings in `.zj/QA.md` §6; it is the resumable state, so
  a partial run is normal and useful.
  *(Supersedes the original wording, which pointed at `.zj/UAT-v2.0.md` and the owed v1.0 round-2 —
  both now history, carried into `.zj/QA.md` verbatim.)*

## p2 — architecture & docs

- [ ] **CRUMB `crumb_lead`/`crumb_opportunity` silently skipped by the test-harness TRUNCATE**
  (Phase 2b, 2026-07-24) — `tests/conftest.py` `_isolate` builds its truncate order from
  `Base.metadata.sorted_tables`, which drops those two tables from the sort because of an
  unresolvable FK cycle between them (SAWarning). They may therefore **not** be reset between
  tests. Latent, not yet bitten: the Phase-2b CRUMB ports build sales orders from partner+item and
  create **no** lead/opportunity rows, so no cross-test pollution today (0-skip suite green ×2
  confirms it). But the first ported test that touches leads/opportunities will inherit rows from a
  prior test. Fix: break the FK cycle for sort purposes (e.g. deferrable constraint or an explicit
  truncate list that includes both tables), or add them to a manual TRUNCATE tail in `_isolate`.
- [ ] **Split `backend/app/modules/plum/service.py` (~3,000 lines)** before MOUSSE/CRISP copy
  the pattern — the monolith-file smell the prototypes suffered from. Target: before/at
  Phase 10 (MOUSSE). **Note (Phase 8):** `syerp/service.py` has now grown to ~1,800 lines
  (inventory + purchasing landed here) — the same smell is starting in the hub module; fold it
  into this split when done. **Update (Phase 9c):** `syerp/service.py` is now **~3,700 lines /
  ~133 KB** (GL posting in 9a, AP bills/payments in 9b, the four report functions in 9c all landed
  here) — it has passed `plum/service.py` and is the more urgent split. Phase 10 (MOUSSE) is the
  trigger; do it before MOUSSE adds work-order posting to the same file.
- [ ] **Auto-number double-collision race in `create_part`** (Phase 7 verify, 2026-07-09) —
  `backend/app/modules/plum/service.py` retries a collided auto-generated `part_number` exactly
  once, and the retry's `db.flush()` is unguarded. Two concurrent no-`part_number` creates are
  handled; **three** can surface an unhandled `IntegrityError` → 500. Pre-existing (not introduced
  by the Phase-7 numeric fix), same read-check-write class as the ledger races below, and equally
  benign single-shop. Fix by looping the retry (bounded) or taking the number from a Postgres
  sequence instead of `MAX()+1`.
- [ ] **Audit-write atomicity vs. the mutation** (Phase 8 review, 2026-07-08) — every service
  mutation commits, then the router calls `write_audit`, which does its own `db.commit()`
  (inherited Phase-4 pattern, consistent module-wide). A process death or `write_audit` failure
  between the two commits persists the mutation with **no audit row**. Not a new defect, but
  traceability is a first-class medical-device-origin concern: if strict audit-with-mutation
  atomicity is wanted, thread `commit=False` through the audit insert so it shares the mutation's
  transaction (one commit). Revisit before CRISP (QMS) or any compliance sign-off.
- [x] **Concurrency races on the inventory ledger** — **RESOLVED by v4.0 Phase 4 (NFR-7,
  verified 2026-07-25, tag `zj/good-04-inventory-race-safety`).** All floor-guarded writers now
  serialize on the shared sorted-id FOR-UPDATE discipline (`post_receipt`/`post_adjustment`/
  `post_transfer` item-master lock before any floor/aggregate read; `receive_line` PO-header lock,
  PO→item order documented; putaway/issue/MOUSSE already locked). Mutation-proven by
  `verify_inventory_race.py` (4 barrier races incl. the MOUSSE-issue × SYERP-adjust mixed pair —
  M1–M4 all executed RED→GREEN), auto-runs in CI `verify-scripts`. Moving-average lost-update
  also closed (re-read under lock). Residuals live in their own entries: pick-path shipment-header
  races + unsorted pick locks (below), positive-adjust bin membership (above). Original analysis
  in git history.
  (Phase 8 review, accepted-risk for
  single-shop, Plan Risk #4) — moving-average recompute, the over-receipt guard, and the
  negative-stock guards each read-check-write **without a row lock**. Single-threaded every path
  is correct (verified); under concurrent writers the moving average *drifts* (self-heals on the
  next receipt) but the two hard invariants this phase guarantees — `qty_received ≤ qty_ordered`
  and per-location on-hand `≥ 0` — **can be breached**. Accepted for single-shop v2.0. Revisit
  when MOUSSE (Phase 10) also writes this ledger, or the first multi-writer deployment — add
  `SELECT … FOR UPDATE` / serialized posting then. **Template now exists (Phase 9b):**
  `create_bill` / `record_payment` in `syerp/service.py` lock the contended rows up-front in
  sorted-id order (deadlock-safe) before the guard read — copy that shape when locking this ledger.
  **Trigger now live (Phase 10 review):** MOUSSE `issue_components` writes this ledger and locks
  only issue-vs-issue (its own `InventoryItem` rows FOR UPDATE) — a concurrent MOUSSE issue and a
  SYERP `post_adjustment`/`post_receipt` on the same item/location can both pass their floor guards
  and drive derived on-hand negative, because the SYERP adjust/receive paths still take no row lock.
  The narrow phase invariant ("two concurrent issues can't overdraw") holds; the ledger-wide floor
  guarantee does not. Fix is the shared lock across every floor-guarded path (issue/adjust/receive/
  transfer), not a MOUSSE-only lock. Still accepted-risk single-shop.
- [x] **Bin split desyncs after any bin-blind movement** — **RESOLVED by v4.0 Phase 4 (NFR-7,
  verified 2026-07-25, tag `zj/good-04-inventory-race-safety`).** No draw primitive writes
  bin-blind anymore (D-P4-1 explicit-or-unbinned across adjust/transfer/MOUSSE issue; outbound
  half closed in 12b); the split can no longer newly rot. Pinned by `verify_gelato.py` scenario E
  (flip) + F and `verify_mousse.py` scenario G — including the restored per-location floor that
  defends the pre-Phase-4 legacy desync rows (G2 legacy-desync fixture, mutation-proven).
  `list_unbinned_stock` keeps its `>0` filter, now documented as masking legacy data only.
  Historical record below. (Phase 12a review MAJOR, 2026-07-18) —
  12a made ONLY putaway bin-aware. The pre-existing draw primitives — `post_transfer`,
  `post_adjustment` (`syerp/service/inventory.py`), and MOUSSE `issue_components` — all write
  `bin_id=NULL` and floor-guard **per-location**, not per-bin. So once stock is put into a bin,
  a bin-blind draw out of that location leaves the bin figure **overstated** and the unbinned
  pool **negative**, even single-threaded (not a race — a sequential-correctness gap): receive
  10 → putaway into bin A → adjust/transfer/issue −10 ⇒ bin A still reports 10, unbinned = −10,
  location total = 0 (correct). Every bin figure 12a surfaces (`get_bin_on_hand`,
  `PutawayResult.bin_on_hand`, the putaway screen) silently rots in normal operation; the
  `list_unbinned_stock` `>0` filter hides the negative rather than flagging it. **Location/total
  on-hand and the Σ(bins)+unbinned==location roll-up (SC3) stay exact** — only the split lies.
  Documented (get_bin_on_hand docstring trust-boundary note) and **pinned by `verify_gelato.py`
  scenario (E)** so the durable fix visibly changes it. Durable fix = make pick/issue/transfer/
  adjust bin-aware (draw from a chosen bin) so the ledger's bin dimension stays consistent —
  this is exactly the **Phase 12b** bin-aware pick→pack→ship work (GELATO-01 AC3/AC5); 12b MUST
  NOT assume 12a already closed it. Folds into the cross-path row-lock item above (same
  primitives, same ledger). Accepted boundary for the 12a inbound-only slice.
  **Update (Phase 12b, 2026-07-19):** the OUTBOUND half is now closed — ship uses the new bin-aware
  `post_issue` (draws from the chosen staging bin), and pick uses bin-aware `post_putaway`, so the
  pick→ship path keeps the bin dimension consistent. Still open on the INBOUND/adjust side:
  `post_transfer`, `post_adjustment`, and MOUSSE `issue_components` remain bin-blind.
  **Update (v4.0 Phase 4 build, 2026-07-25): INBOUND/adjust half closed in code** —
  `post_adjustment` (bin_id), `post_transfer` (from_bin_id), and MOUSSE `issue_components`
  (per-line bin_id) are now bin-aware (D-P4-1 explicit-or-unbinned: None draws ONLY the
  unbinned pool, per-POOL floor guard), so no primitive writes bin-blind draws anymore and
  the split no longer rots; pre-Phase-4 desync'd rows remain as historical artifacts (the
  `list_unbinned_stock` `>0` filter now only masks that legacy data, never a live negative).
  `get_bin_on_hand`'s trust-boundary note rewritten to the new invariant. Final check-off of
  this item happens at Phase 4 verify (scenario (E) flip, `verify_gelato.py`).
- [x] **Positive adjustment accepts an unvalidated `bin_id` — can strand stock in a
  foreign-location bin pool** — **RESOLVED by v4.0 Phase 5 SC8 (`e57c1ff`, pinned `0a7a89f`).**
  Owner chose option (a) (**D-P5-5**): `post_adjustment` now runs one raw-SQL existence +
  location-membership probe against `gelato_bin(id, location_id)` for any non-null `bin_id` and
  rejects a mismatch with 422, writing nothing. **No gelato model import**, so D-P12a-3's
  no-imports rule still holds. Pinned as `verify_gelato.py` scenario **(G)**, four assertions:
  G1 the mismatched pair is rejected and writes no ledger rows; G2 a wholly non-existent bin is
  rejected 422 rather than surfacing a raw FK IntegrityError as a 500; G3 the matching pair still
  succeeds and raises that bin's on-hand by exactly 5; G4 `bin_id=None` is untouched by the probe
  (D-P4-1). RED was unambiguous before the fix — `status=None rows 1->2`, i.e. no exception at all
  and stock booked into a bin at the wrong location. Original text follows.
  *(Phase 4 verify review #2, 2026-07-25, minor — decision needed.)*
  D-P12a-3 (SYERP never validates bin existence/membership; FK backstop) was safe pre-Phase-4
  because every public bin WRITE went through GELATO, which does validate location-membership.
  Phase 4's draw paths self-guard (a mismatched `(location, bin)` pool reads 0 → 422), but a
  POSITIVE `post_adjustment {location_id: B, bin_id: <bin of location A>}` passes the FK, writes
  a ledger row at `(B, bin-of-A)`, and the stock then counts in B's location total while
  belonging to no pool GELATO will ever display — stranded until a manual negative adjustment
  names the same mismatched pair. FE dialogs can't produce it (bin resets on location change);
  only raw API callers hit it. Options: (a) one cheap raw-SQL existence+membership check against
  `gelato_bin(id, location_id)` on non-null bin_id (no gelato model import, so D-P12a-3's
  no-imports rule holds), 422 on mismatch; or (b) an explicit decision entry accepting it.
  Owner call.
- [ ] **`post_transfer` and MOUSSE `issue_components` still trust their bins — SC8's guard is
  asymmetric** (promised as a p2 item by Phase-5 PLAN `## Noticed` #13, filed at `/zj:verify 5`
  fix-loop 2026-08-17). SC8 (D-P5-5) scoped the probe to the positive-adjust path only, and the
  fix loop then widened it to **three** tests — the bin must exist, belong to the named location,
  **and be active** (`inventory.py:444-477`, `fd7ca87`), matching `execute_putaway`
  (`gelato/service/putaway.py:165-179`). The two sibling draw paths validate **zero**:
  `post_transfer`'s `from_bin_id` (docstring `inventory.py:618-621`: *"The BIN is NOT validated
  here: bin existence + location-membership is GELATO's domain and the caller's job (D-P12a-3);
  the DB FK on bin_id is the backstop"*) and MOUSSE `issue_components`' per-line `bin_id`
  (docstring `mousse/service.py:607-610`, same claim — MOUSSE writes its own `InventoryTxn` at
  `mousse/service.py:764` rather than going through a shared primitive). Both are reachable from
  the API with a mismatched or archived `(location, bin)` pair.
  Impact is smaller than SC8's — a draw from a foreign or archived pool reads on-hand `0` and is
  rejected by the pool floor — but the *docstrings assert a guarantee nobody provides*, and the
  next primitive written against that contract inherits the hole. Fix: extend SC8's raw-SQL probe
  (**no gelato model import** — D-P12a-3 keeps the hub free of satellite imports) to both paths,
  and correct both docstrings; pin as further `verify_gelato.py` scenarios in the shape of
  (G1)–(G5). Do it in one pass so all three bin-taking primitives state and enforce the same
  contract. While there, check `post_issue`'s identical "checked by the caller" docstring
  (`inventory.py:1019-1022`) against its sole caller, `gelato/service/shipments.py:630` — the
  claim may hold there, but nobody has verified it.
- [x] **GELATO `pick_for_shipment` acquires item locks incrementally in request-line order** —
  **RESOLVED at the v4.0 milestone close (2026-08-18, `4dc3154`, audit GAP-2).** No longer
  accepted-risk-theoretical: the milestone audit **reproduced the deadlock 6/6 iterations** under
  an `asyncio.Barrier`. `execute_pick` now validates every line in a pure-read pass and then moves
  them in **sorted item-id order**, giving one global lock order (the sort had to follow a
  validation pass because `PickLineRequest` carries only `sales_order_line_id`, so `item_id` is not
  knowable without a DB read). Pinned by `verify_gelato_ship.py` scenario **(j)** — two picks of
  *different* SOs over the same two items in opposite order, so the SO lock cannot mask the sort —
  and proven load-bearing in isolation (remove only the sort → (j) RED with
  `asyncpg.exceptions.DeadlockDetectedError`). Original text below for the record.
  *(Was: `shipments.py:387` calls `post_putaway` per line UNSORTED, unlike every other multi-item
  path — MOUSSE issue, create_bill, confirm-SO, all sorted-id. Fix: sort the lines by item id
  before the loop.)*
- [ ] **[bug] [p2] GELATO pick-path shipment-header races — Q1 RESOLVED, Q2 STILL OPEN**
  (Phase 12b review Q1/Q2, 2026-07-19; half-closed at the v4.0 close 2026-08-18).
  **(Q1) — FIXED (`4dc3154`, audit GAP-2).** Two concurrent first-picks of one SO each
  get-or-created a shipment → **two open `picking` shipments**, which the milestone audit
  reproduced (`ids=[42, 43]`) along with an unnamed bonus symptom: a **lost `qty_picked` update**
  (both sessions read 0, both wrote 5). `execute_pick` now takes the sales-order row
  `SELECT … FOR UPDATE` *before* the get-or-create, so the loser blocks and then appends to the
  winner's shipment. Pinned by `verify_gelato_ship.py` scenario **(i)**, load-bearing in isolation
  (remove only the lock → RED `shipments_for_so=[101, 102]`). This mattered more than "accepted
  risk" implied: GELATO exposes **no list-shipments-for-an-SO route**, so the second shipment's
  picked stock was unreachable without DB surgery.
  **(Q2) — STILL OPEN.** A pick can still append a line to a shipment a concurrent pack has just
  flipped to `packed`, so the line skips pack's staged-qty review. The SO lock does **not** close
  this: the fix is to re-assert shipment status on pick-append (a shipment-row lock, the
  `execute_ship` shape). Does not corrupt the ledger — the per-item `post_putaway` lock holds.
- [ ] **[bug] [p3] GELATO has no "list shipments for a sales order" route** (surfaced at the v4.0
  close, audit GAP-2). `gelato/router.py` exposes only `GET /gelato/shipments/{id}`. `4dc3154`
  removes the way stock *becomes* stranded, but any shipment stranded by a pre-fix deploy is still
  unreachable through the API — recovery needs DB access. A list-by-SO route makes it recoverable
  and is a reasonable operator feature regardless.
- [ ] **Alembic autogenerate never exits clean** (Phase 9a verify, 2026-07-11) — `alembic check`
  reports spurious drift on **7 pre-existing unnamed `unique=True` constraints** (plum_part.part_number,
  uq_plum_part_one_released, syerp_gl_account/inventory_item/partner.code, purchase_order.po_number,
  stock_location.name) that reflect from Postgres with names the model metadata lacks; migration `0009`
  also sets `server_default=sa.text("now()")` on `created_at` while the model uses a Python-side
  `default=` only, adding one more drift line. None are correctness bugs, but they mean autogenerate
  is unusable for drift-detection. Fix: add a naming convention on `Base.metadata` (`naming_convention=`)
  so constraints reflect with stable names, and align the model/migration `created_at` default. Do
  before autogenerated migrations are ever trusted. **Re-hit Phase 11a Task 2 (2026-07-16):**
  autogenerating migration 0013 again surfaced the same 7 spurious constraint drops (correctly
  excluded from the crumb-only migration) — the friction now recurs once per new module.
- [ ] **Reverse-from-UI has no Vitest** (Phase 9a verify, G3/m6) — the "Reverse" action in
  `frontend/src/routes/syerp/JournalEntries.tsx` (`c2bde3d`) is exercised only by hand; backend
  reversal incl. the 409 double-reversal guard is covered by `verify_gl.py`. Add a Vitest case
  mirroring the post-flow test: confirm dialog → `POST {id}/reverse` → toast + query invalidate.
  Fold into the 9b/9c frontend wave.
- [ ] **AP GR/IR sub-micro residue on multi-lot fractional receipts** (Phase 9b review #2, minor
  correctness) — `create_bill` books the matched leg as ONE combined `matched_qty × unit_cost`
  (`syerp/service.py:3163`), while `receive_line` booked each receipt's `Cr GR/IR` as a
  separately-`quantize`d product (quantum `0.000001`, `:1951`). With a fractional qty received
  across multiple lots the two need not agree at the 6th decimal, so GR/IR is left holding
  ~`n_lots × 0.5e-6` rather than exactly zero — financially trivial but a real divergence from the
  "nets to zero exactly" invariant. `verify_ap.py` (e) uses a single fully-received line and cannot
  surface it. Fix: derive the matched amount from the Σ of the *booked* receipt amounts for that
  `po_line_id` (or quantize identically per receipt). Fold into 9c if the crux is revisited.
- [ ] **Balance-sheet "Current Year Net Income" line — two fiscal-close-gated defects** (Phase 9c
  review #1/#2, both minor/latent, both resolved by the same future feature). `balance_sheet`
  (`syerp/service.py:3735-3812`) appends a **computed** 3130 "Current Year Net Income" row
  (`amount = Σrevenue − Σexpense`, all-time, `entry_date <= as_of`) and adds it into `total_equity`,
  because no closing entries are posted so ledger 3130 is empty. Two problems surface the moment the
  ledger grows: (1) **double-count** — the main query inner-joins `JournalLine` filtered to
  ASSET/LIABILITY/EQUITY, so it includes 3130 as a *second* row the instant anything posts to 3130
  (nothing forbids a manual JE to that leaf via `post_journal_entry`); the identity still holds
  (`in_balance` is tautological — see LEARNINGS 09c), so this is silent presentation duplication.
  (2) **wrong label** — the line sums R−E from beginning-of-time with no fiscal-year lower bound, so
  once the ledger spans >1 fiscal year "Current Year Net Income" overstates the current year by all
  prior years' cumulative P&L (balance still ties; label lies). **Both land with fiscal-year close /
  closing entries / retained-earnings roll-forward** (explicitly out of scope for v2.0 — the DoD has
  no closing-entry clause). Fix when that phase arrives: exclude 3130 from the main query (or skip
  the computed line when ledger 3130 is non-empty) so exactly one 3130 row is ever emitted, and bound
  net-income to the current fiscal year moving prior-year P&L to retained earnings. Until then,
  documented as cumulative. `verify_reports.py` pins the *composition* (exactly one appended row ==
  P&L net income) so a regression that breaks the current model would be caught.

- [ ] **AP zero-quantity matched line → permanently unpostable draft** (Phase 9b review #3, minor)
  — for a fully-billed/never-received PO line (`unbilled_qty == 0`) a hand-crafted
  `{line_type:'matched', matched_qty:0}` passes `_is_exact_match(0 == 0)` and persists an `amount=0`
  line; `post_bill` then emits an all-zero JE line that `_je_is_balanced` rejects, so the bill 422s
  forever and is stuck in `draft`. No money bug (nothing posts) and the UI never generates it (the
  picker filters `unbilled_qty > 0`), but the API accepts it. Fix: reject `matched_qty <= 0` in
  `BillLineCreate` / `create_bill`.
- [ ] **Integration specs** (kept from chore-architecture-planning): PLUM↔MOUSSE,
  PLUM↔SYERP, FLAN↔SYERP, shared vendor/document infrastructure.
- [ ] **Suite documentation sets** (kept): SYERP, CRUMB, MOUSSE, CRISP, GELATO under
  `docs/features/{suite}/` per `_templates/`.
- [ ] **Remove dead `frontend/src/components/ProtectedRoute.tsx`** — replaced by AppShell;
  only its own test references it.
- [ ] **Stale AP frontend types/comments** (Phase 9b Noticed) — `Bills.tsx` `BillLineRead` declares
  a non-existent `quantity` field and omits `line_no`/`matched_qty` (harmless today: the list
  renders no line rows; `BillDetail.tsx` defines a correct local type — latent trap if the list type
  is reused). Separately, an AP schema comment mentions a `partially_paid` status that the FSM never
  uses (draft→posted→paid only; a partial payment leaves the bill `posted`). Both cosmetic; fix when
  next touching the AP screens/schemas.
- [ ] **Dependency license audit** (NFR-2) — required before public open-source release.

- [ ] **Module enable/disable is UI-only — there is no server-side gate** (v4.0 Phase 5 PLAN
  `## Noticed` #1, homed at retro 2026-08-18) — `backend/app/core/modules_router.py` stores the
  `enabled` flag and nothing reads it: `grep -rn 'require_module\|module_enabled' backend/app/`
  returns nothing, and `frontend/src/App.tsx` has no per-module route guard. Disabling GELATO only
  filters the sidebar (`AppShell.tsx:37-46` `getVisibleModules`); `/api/v1/gelato/*` still serves any
  authorized user and `/gelato/bins` stays directly reachable by URL. **CORE-07 as written is
  satisfied** ("Admin can enable or disable individual modules", verified by "toggle updates nav
  live"), so this is an unbuilt capability rather than a defect against a shipped requirement — but
  the SRD statement reads stronger than the implementation, and a self-hoster who disables a module
  for policy reasons will assume it is off. Consequence today: the three Phase-4 dialogs' docstrings
  ("Hidden … when the bins query errors (GELATO off)" — `StockAdjustDialog.tsx:20-21`,
  `StockTransferDialog.tsx:20`, `IssueComponentsDialog.tsx:149-151`) are **wrong about the cause**;
  the real `isError` trigger is an RBAC 403 or a network failure. Fix in two parts, separable: (a)
  correct the three docstrings now — cheap, and they currently mislead; (b) add a
  `require_module(<key>)` router dependency plus a route guard, and true up CORE-07's statement.
  Natural home is the **Quality & release** candidate milestone.

## p3 — hygiene

- [ ] **The two new QA-doc guard scripts cannot run the documented in-container way**
  (v4.0 Phase 5 verify, N-1, 2026-08-17) — `backend/scripts/verify_qa_doc.py` and
  `verify_qa_citations.py` (`ba4c074`, `8352858`) read `.zj/QA.md` and `.zj/SRD.md`, which the
  `Containerfile` does not copy (it copies `backend/` only). So the house recipe
  `podman exec … python scripts/verify_*.py` now yields **15/17** rather than 17/17, and the two
  that fail do so for an environment reason rather than a real one — exactly the kind of noise
  that trains people to ignore a red. CI runs them from the checkout and is unaffected. Fix:
  document them as checkout-only beside the sweep recipe, or have them exit 0 with a skip notice
  when `.zj/` is absent. Same family as the `pytest`-not-in-the-image item below.
- [ ] **`verify_qa_citations.py` erodes silently if a citation loses its shape**
  (v4.0 Phase 5 verify, N-2, 2026-08-17) — the extractor matches four documented citation forms;
  a citation reformatted out of all four is simply not extracted, so the count drops (223 instead
  of 224) and the script still reports "All assertions PASSED". The anti-vacuum assertion catches a
  *missing block*, not a *malformed citation inside a present block*. Fix: assert a floor on the
  extracted count, or fail when a `✅ Machine already proved` block yields zero citations.
- [ ] **Three `verify_gl.py` citations are only weakly pinned**
  (v4.0 Phase 5 verify, N-3, 2026-08-17; PLAN `## Noticed` #9(a), still open) — `.zj/QA.md` cites
  `verify_gl.py (A)`, `(B)`, `(M1)` but that script letters its scenarios `(a)`–`(h)` lower-case,
  so those three resolve only incidentally. `verify_qa_citations.py` now prints them as `WEAK` on
  every run, so the rot is visible rather than invisible. Fix properly by re-lettering the
  letterless `verify_*` scripts to the `(G1)`-style scheme the newer ones use, then tightening the
  citations.
- [ ] **The API image carries no `pytest`, so the backend suite cannot run in-container**
  (split out of the now-resolved p1 rebuild item, v4.0 Phase 5 Task 33, 2026-08-17) — the runtime
  stage installs `requirements.txt` only, and the bind-mounted `backend/.venv/bin/pytest` carries
  host-path shebangs, so neither route works. Every "run the suite in the container" instruction in
  the docs is therefore wrong, and Task 33 had to run it against a **disposable**
  `postgres:17-alpine` on a host port instead (compose's `db` is deliberately unpublished, T-01-12).
  That workaround is fine and arguably safer — it cannot touch the seeded dev database — but it is
  undocumented tribal knowledge. Fix: either add a builder/test stage carrying
  `requirements-dev.txt`, or document the disposable-Postgres recipe in
  `docs/deployment/local-dev.md` beside the other verified commands. The `openpyxl` half of the
  original item is done; only this half remains.
- [x] **`scripts/uat.ps1` checks `POSTGRES_PASSWORD` in the wrong file (pre-D-P5-10)** —
  **RESOLVED at the `/zj:verify 5` fix loop (2026-08-17, review finding #4).** The
  `scripts/uat.sh` block is ported: the `.ps1` now ensures **both** `.env` and `.env.db` exist
  (creating each from its template), greps `^POSTGRES_PASSWORD=\S+` in **`.env.db`**, and adds
  the new upgrade warning when `.env` still defines `POSTGRES_PASSWORD`. §1.6 of
  `docs/deployment/local-dev.md` — which already claimed both launchers create both files — is
  now true. **⚠ Landed unexecuted:** no PowerShell interpreter exists on the dev host (`pwsh`
  absent), so the port was reviewed line-by-line against the bash original but never run. The
  first Windows user to touch it should confirm `-Fresh` on a bare checkout.
  *Original text follows.* (noticed
  2026-08-08 while porting the launcher to bash during Phase 5) — the `.ps1` warns when
  `^POSTGRES_PASSWORD=\S+` is absent from `.env`, but D-P5-10 moved that credential to `.env.db`
  and gave it exactly one home there. So on a stock checkout the `.ps1` warns on a *correct*
  setup (`.env` legitimately has no `POSTGRES_PASSWORD`), and — worse — it never checks `.env.db`
  exists at all, so `./scripts/uat.ps1 -Fresh` on a first-ever deploy sails past its own guard
  straight into defect **U0** (`Database is uninitialized and superuser password is not
  specified`). Windows-only exposure, which is why it was not fixed inline. `scripts/uat.sh`
  already has the corrected guard (checks both files exist, greps `.env.db`) — port that block
  back. Compose-side config is separately pinned by `backend/tests/test_compose_config.py`;
  neither launcher is covered by a test.
- [ ] **Pre-lock `moving_avg_cost` staleness remains in `post_issue` / `post_putaway`** (Phase 4
  PLAN `## Noticed` T1 + review finding 3 follow-through, retro'd 2026-07-25) — both load `item`
  before taking the FOR UPDATE lock (which selects the id column only and does not repopulate the
  mapped object), then value their ledger legs from `item.moving_avg_cost`. A receipt committing
  between the load and the lock leaves the leg stamped at the pre-receipt cost for a movement the
  lock demonstrably serialized *after* it. Quantities and GL are unaffected (legs net to zero;
  valuation reports read the live average) — this is **audit provenance only**, which still
  matters given the first-class traceability constraint. Phase 4 fixed the same shape in
  `post_receipt` (`73e45c2`) and `post_transfer` (`5a45a7b`); fix = `await db.refresh(item)`
  after the lock. Fold in whenever either function is next touched.
- [ ] **`verify_*` scripts leave orphan journal entries behind — at least two leakers, one
  unidentified** (Phase 4 PLAN `## Noticed`, retro'd 2026-07-25; **re-measured Phase-5 Task 33,
  2026-08-17**) — `verify_purchasing.py`'s cleanup doesn't delete the journal entries its
  receipts post, so dev/CI databases accumulate orphan source rows run over run.
  **New measurement:** the full 24-script sweep against a freshly-seeded volume drifts
  **`+100.00`** on total debit, total credit and total liabilities (`total_assets`
  7991.75 → 8091.75, trial-balance 8447.25 → 8547.25). That is **double** the `+50.00`
  previously attributed to `verify_purchasing.py` alone, so **at least one other script leaks
  too and has not been identified** — isolating it is the first step of this item. Per-document
  literals and aging buckets were unaffected in both measurements.
  Cosmetic (no assertion depends on a clean GL), but it makes hand-inspecting a dev DB noisier,
  it forces a fresh-volume re-seed before `.zj/QA.md`'s aggregate checks can be trusted, and
  every other script cleans up after itself — `verify_inventory_race.py` (Phase 4) is the
  current template.
- [ ] **`TransactionRead` omits `bin_id`; MOUSSE issue audit records no per-line bins** (Phase 4
  verify review question, 2026-07-25) — the transactions API/FE cannot show which pool a
  post-Phase-4 ledger row hit (Phase 4's own `verify_gelato.py` scenario F had to read leg
  bin_ids from raw ledger rows), and the `work_order.issued` audit row records only line count +
  value, so per-line bins are reconstructable only from the ledger. Pre-existing schema, but
  bin_id became load-bearing in Phase 4. Fix: add `bin_id` to `TransactionRead` (+ FE column
  where useful) and per-line bins to the MOUSSE issue audit detail. Related FE tidy: `useBins`
  has no `retry: false`, so a GELATO-off deploy retries the bins GET 3× per location before the
  pickers degrade (harmless, noisy).
- [ ] **CI hardening niceties** (Phase 3 retro, 2026-07-25 — owner chose close-as-is; these are
  the phase's homed minors plus the residuals folded into the old p1 CI item by Phases 1/2a).
  All low-priority; the standing protection today is that the four jobs run on every push:
  (a) **standing enforce-smoke** — SC3/SC4 red demos were one-time manual pushes; a
  self-restoring inject→expect-red→revert smoke would continuously prove the gates still fail on
  a violation; (b) **"0 skipped" guard on the pytest job** — a future silently-`skip`ped test
  leaves `backend-tests` green (2a's `test_harness_selfcheck.py` pins the DSN-class regression,
  not arbitrary new skips); e.g. assert on the pytest summary or a collected-count check;
  (c) **back-to-back pytest rerun step** — the isolation guarantee is proven only by manual
  double-runs; (d) **meta-test on `ci.yml` shape** — deleting a job/check silently stops checking
  it; branch protection would go stale-but-satisfied only if the context vanished (GitHub then
  blocks, so partial inherent cover); (e) **Node-20 action deprecation** — bump
  `checkout`/`setup-node`/`setup-python` majors to clear the cosmetic warning; (f) **duplicate
  push+PR runs** — both triggers fire for same-repo PR branches; scope `push` to `master` (or
  add concurrency groups) to halve runner minutes. Standing caveat carried from Phase 1:
  `frontend/.npmrc` `legacy-peer-deps=true` is a *global* peer-mask — a green `npm ci` is not
  proof of peer sanity on future dep bumps.
- [ ] **Invoice void / credit memos** (Phase 13 retro, 2026-07-19) — AR has no reversal path:
  `qty_invoiced` only ever increments (matches Phase 13 out-of-scope), so a mistaken invoice
  cannot be voided and an over-bill cannot be credited back. A real functional gap for any
  operator, deferred from v3.0. Fix needs a decrement path for `qty_invoiced` + a void/credit
  FSM state + the reversing JE (Dr 4110 / Cr 1120). Sequence with the sell-side lifecycle work.
- [ ] **`partially_paid` phantom badge in AR FE** (Phase 13 retro, 2026-07-19) — the real invoice
  FSM is `draft|posted|paid` (a partial receipt stays `posted`); the API never emits
  `partially_paid`. Backend docstrings were corrected at build, but the AR FE carries a dead
  `partially_paid` badge variant as defensive rendering. Cosmetic — drop it in a future FE tidy.
- [ ] **COGS/revenue period split on late invoices** (Phase 13 retro, 2026-07-19) — `execute_ship`
  ages COGS on ship date while the invoice ages AR/revenue on invoice date, so a late invoice
  lands revenue in a different period than its COGS. Correct and accepted for v3.0; note for any
  future revenue-recognition matching work (there is no matching layer today).
- [ ] **Migration 0016 downgrade path has no automated test** (Phase 12b verify, 2026-07-19) — the
  `0016→0015` drop of `gelato_shipment`/`gelato_shipment_line` + the SO-line accumulator columns is
  exercised only by the manual `alembic downgrade -1 && upgrade head` round-trip command, not asserted
  by any script. Low value (round-trip is reproducible; every `verify_*` runs on the upgraded schema),
  but a durable downgrade-round-trip assertion would close the gap for all migrations at once.
- [ ] **CRUMB quote→SO conversion has no idempotency guard** (Phase 11b verify Question, 2026-07-17)
  — an Accepted quote can be converted to **unlimited duplicate sales orders**: `convert_quote_to_sales_order`
  changes no quote state and takes no guard, yet `QuoteDetail.tsx` copy implies the quote "moves to
  converted." Owner chose fix-blocker-only at verify, so this was left open. Fix when the quote
  lifecycle post-conversion is specified — candidate: 422 on re-convert if an SO already stamps this
  quote as `source_quote_id`, or add a `converted` quote status. Low risk single-shop (duplicate SOs
  are visible + cancellable), but a data-hygiene trap. Revisit at Phase 13 (SYERP-13 invoicing) when
  the quote→SO→invoice chain is firmed up.
- [ ] **MOUSSE zero-cost lone-component issue is unpostable** (Phase 10 review Q2 / PLAN `## Noticed`,
  minor UX edge) — issuing ONLY a component whose `moving_avg_cost` is 0 makes `total_value == 0`, and
  the balanced-JE guard rejects an all-zero JE 422, so the component's stock is never consumed and it
  stays under-issued — forcing an audited `override_incomplete` at completion for a genuinely
  free/nominal part. Documented intentional (a zero JE has no GL meaning). Workaround: issue it
  alongside a non-zero component. Fix only if a real workflow hits it — e.g. skip the GL leg (still
  post the InventoryTxn) when a line values to zero, or allow a zero-value issue to consume stock
  without a JE. Revisit if it confuses a real operator.
- [ ] **Linux-native stack launcher** — only launcher is PowerShell (`scripts/uat.ps1`);
  add a bash equivalent or document the manual compose commands prominently.
- [ ] **Root placeholder suite dirs** (`syerp/`, `crumb/`, `mousse/`, `crisp/`, `gelato/`
  contain only CLAUDE.md) — confusing next to real code at `backend/app/modules/`; prune or
  clearly mark.
- [ ] **Repo weight** — `plum/` 33 MB + `flan/` 8.7 MB of frozen prototypes/archives (22
  archived FLAN versions, 2.6 MB JSON DB). Consider pruning archives or git-lfs once ports
  supersede them (prototypes are frozen per D-ADOPT-4).
- [ ] **Milestone bookkeeping** — GSD Wave-0 `wave_0_complete` flags were never set for any
  phase (historical; relevant only if auditing the archive).
- [ ] **Backdated-payment AP-aging tie-out edge** (Phase 9c review Question + PLAN `## Noticed` T5,
  low severity — reviewer and build both concur it is *correct* behavior, not a bug). Neither
  `create_bill` nor `record_payment` validates `payment_date >= bill_date`. For a bill dated
  2026-07-10 paid on 2026-07-01, `ap_aging_report(as_of=2026-07-05)` excludes the bill
  (`bill_date > as_of`) while the payment's 2110 debit (`entry_date=2026-07-01`) is inside the control
  window → `control_balance` negative, `grand_total` 0, `in_balance` False. This is a faithful
  reflection of a genuinely anomalous ledger (AP carries a debit because cash left before the invoice
  was booked), not a report defect. **Decision needed only if product wants to reject the data-entry
  order at write time** (validate `payment_date >= bill_date`) rather than surface it as
  out-of-balance. Left as-is for now; revisit if it ever confuses a real operator.

- [ ] **Receipt auto-post `entry_date` is server-local, not UTC** (Phase 9a verify) —
  `receive_line` dates the auto-posted JE with `date.today()` while `created_at` is UTC, so near
  midnight a receipt and its JE can land on different calendar days and split across register
  periods. Acceptable for single-timezone self-host; switch to
  `datetime.now(timezone.utc).date()` if UTC-consistent periods are ever required (e.g. multi-region
  deploy or fiscal-period locking in 9c).
- [ ] **`.zj/codebase/MAP.md` fuller refresh owed** (Phase 9a verify; still owed through 9c) — the
  migration list stops at 0009 (head is now **0011**), and the entire Phase 9 surface is unmapped:
  GL posting endpoints + journal tables (9a), AP bills/payments (9b), the four report endpoints +
  AP-aging/financial-statement screens (9c), and the grown syerp `service.py` (~273 lines claimed at
  `:124`; actually **~3,700 lines / ~133 KB**). Refresh via `/zj:docs` before the Phase-10
  mapper-driven planning pass.
- [ ] **Starlette 422 deprecation sweep** (Phase 8) — `HTTP_422_UNPROCESSABLE_ENTITY` is
  deprecated for `HTTP_422_UNPROCESSABLE_CONTENT`; fires from `post_receipt` / `post_adjustment` /
  `post_transfer` / `receive_line` in `backend/app/modules/syerp/service.py`, now also
  `backend/app/modules/mousse/service.py` (which matched the SYERP convention, Phase 10), now also
  `backend/app/modules/crumb/service/*` (Phase 11a, same convention), and likely older modules.
  Cosmetic; one mechanical sweep before it becomes log noise.
- [ ] `[task] [p3]` **Proper customer prepayment / deposit accounting** (v3.0 milestone audit,
  GAP-1 / D-M3-1) — v3.0 fixed the AR aging *report* so a receipt dated before its invoice_date no
  longer trips a false negative-1120 tie-out (prepayments reclassified out of the control in
  `ar_aging_report`), but there is still no first-class model for a customer deposit: the cash sits
  as a credit against a not-yet-recognized invoice rather than in an unearned-revenue / customer-
  deposit liability account. Revisit alongside invoice void / credit memos (the other Phase-13 p3
  deferrals) when sell-side revenue-recognition work is scoped. Until then the report tie-out is
  correct for every date ordering and the GL always balances.

- [ ] **The commented module-service templates in `compose.yml` re-introduce `U0`** (v4.0 Phase 5
  PLAN `## Noticed` #7(a) + reviewer question, homed at retro 2026-08-18) — the commented-out stubs
  at `compose/compose.yml:111-157` (`plum-worker`, `gelato-worker`, …) all carry `env_file: ../.env`
  **alone**. D-P5-10 moved the database credentials to `.env.db` and pinned the two-file form for
  `db` and `api` only, so whoever uncomments a module service gets the app secrets and **no**
  database credentials — the exact drift D-P5-10 exists to prevent, pre-seeded into the file. Fix:
  update the templates to the two-file form, and extend `backend/tests/test_compose_config.py` to
  assert it for every service that declares an `env_file` (commented blocks included, or at minimum
  a comment warning).
- [ ] **`POSTGRES_PASSWORD` is interpolated into the DSN without URL-encoding** (v4.0 Phase 5
  reviewer question, homed at retro 2026-08-18) — `backend/app/core/config.py:52-56` and
  `backend/scripts/seed_uat_fixtures.py:269`. Pre-existing, but `.env.db.example` now tells a
  first-time self-hoster to "set a strong, unique password" in a brand-new file, so a password
  containing `@`, `/`, `:` or `#` yields an opaque asyncpg parse failure on **first boot** — the
  worst possible moment, and the same first-deploy blast radius as `U0`. Fix: `quote_plus()` the
  password when building the DSN (both sites), or at minimum a one-line warning in
  `.env.db.example`.
- [ ] **Operator-facing error copy names entities by numeric id, and one message reports the wrong
  noun** (v4.0 Phase 5 PLAN `## Noticed` #4(a), #4(g), #13, homed at retro 2026-08-18) — the
  unbinned-pool rejection reads *"exceeds the unbinned pool at location 374"* and SC8's reads
  *"Bin 5 does not exist at location 6"*; if either reaches a toast the operator sees a database id
  where the screen shows `UAT-LOC-A`. Consistent with existing house style, so fix them together
  rather than one-off. Separately, `update_cost` rejects a Released revision with *"BOM lines can
  only be edited on Draft revisions."* (`plum/service.py:2029`) — copy-pasted from `add_bom_line`;
  correct behaviour, wrong noun, and the user is editing a cost.
- [ ] **Receipts and Payments have no human document number** (v4.0 Phase 5 PLAN `## Noticed` #4(k),
  homed at retro 2026-08-18) — `ReceiptRead` / `PaymentRead` expose only `id`, date, amount and a
  free-text `reference`, unlike `BILL-####` / `INV-####` / `PO-####` / `SO-####`. The Receipts and
  Payments lists therefore identify a row by UUID, and nothing enforces `reference` uniqueness. A
  cash-application dispute has no document to point at. Fix: a sequenced `RCT-####` / `PMT-####`
  alongside the existing generators when the AR/AP screens are next touched.
