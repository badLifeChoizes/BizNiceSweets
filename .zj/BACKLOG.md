# BACKLOG — BizNiceSweets
Updated: 2026-07-25 (Phase 4 retro — two unhomed PLAN `## Noticed` items filed p3: pre-lock
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
- [ ] **Rebuild `frontend/dist` + the API container image** — production bundle predates Phase 3;
  `:8000` serving doesn't reflect Phases 3–6 UI until rebuilt. The **API image is stale too**
  (Phase 7 verify, 2026-07-09): in-container Excel export raises `ModuleNotFoundError: openpyxl`
  though `requirements.txt` pins `openpyxl==3.1.5`, and `pytest` isn't installed — so every
  "run it in the container" verify step pays a tax. Rebuild both, or add a test stage carrying
  dev deps.
- [x] **Refresh root `CLAUDE.md` stack/architecture sections** — done in Phase 7 Task 4
  (commit `5db8278`); Technology Stack + Architecture now describe the live FastAPI/React stack
  and cite `.zj/codebase/MAP.md`. (Any remaining Windows-path references elsewhere are out of
  that task's scope.)

- [ ] **[task] [p1] Human click-through UAT for v2.0 operations** (deferred at the v2.0 milestone
  close, D-M2-2) — the 14-check `.zj/UAT-v2.0.md` (SYERP inventory + purchasing UI flows) and the
  owed v1.0 round-2 checks never ran. All backend behavior is live-proven (13/13 verify scripts) and
  the milestone audit confirmed every route is mounted, in-nav, and contract-aligned, so the tag
  rests on backend proof + wired-UI audit (D-P7-5 precedent). This is now a **pre-public-release
  gate**: run it against the Vite dev server (`localhost:5173`) with the Podman stack up before any
  public open-source release, and extend it with GL/AP/reports/MOUSSE UI flows (Phases 9–10 shipped
  no UAT checklist of their own). Record results in `.zj/UAT-v2.0.md`.

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
- [ ] **Positive adjustment accepts an unvalidated `bin_id` — can strand stock in a
  foreign-location bin pool** (Phase 4 verify review #2, 2026-07-25, minor — **decision needed**).
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
- [ ] **GELATO `pick_for_shipment` acquires item locks incrementally in request-line order**
  (Phase 4 verify review question, 2026-07-25 — pre-existing from 12b, the one remaining writer
  outside the Phase-4 lock discipline). `shipments.py:387` calls `post_putaway` per line
  UNSORTED, unlike every other multi-item path (MOUSSE issue, create_bill, confirm-SO — all
  sorted-id). Two concurrent picks whose lines order shared items oppositely (or a pick racing
  a MOUSSE issue over the same two items) can deadlock; Postgres aborts one with a 500 instead
  of a clean 409/422. Fix: sort the lines by item id before the loop. Same lock family as the
  Q1/Q2 item below; accepted-risk single-shop.
- [ ] **GELATO pick-path shipment-header races** (Phase 12b review Q1/Q2, 2026-07-19) — the
  *ship* path is now hardened (shipment row `SELECT … FOR UPDATE` before the FSM gate — no double
  COGS post; `verify_gelato_ship.py` scenario h), but the *pick* path takes no shipment/SO lock:
  (Q1) two concurrent first-picks of one SO each get-or-create a shipment → two open `picking`
  shipments for the SO (breaks the "≤1 open pick per SO" assumption `_resolve_fulfilling_location`
  relies on); (Q2) a pick can append a line to a shipment that a concurrent pack has just flipped
  to `packed`, so the line skips pack's staged-qty review. Neither corrupts the ledger (the per-item
  `post_putaway` lock holds). Fix = lock the SO row (or a unique partial index: one open shipment per
  SO) + re-assert shipment status on pick-append. Same lock family as the cross-path ledger item.
  Accepted-risk single-shop (needs two operators on the same SO in the same instant).
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

## p3 — hygiene

- [ ] **`scripts/uat.ps1` checks `POSTGRES_PASSWORD` in the wrong file (pre-D-P5-10)** (noticed
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
- [ ] **`verify_purchasing.py` leaves orphan `po_receipt`-sourced JEs behind on every run**
  (Phase 4 PLAN `## Noticed`, retro'd 2026-07-25) — its cleanup doesn't delete the journal
  entries its receipts post, so dev/CI databases accumulate orphan source rows run over run.
  Cosmetic (no assertion depends on a clean GL), but it makes hand-inspecting a dev DB noisier
  and every other script cleans up after itself — `verify_inventory_race.py` (Phase 4) is the
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
