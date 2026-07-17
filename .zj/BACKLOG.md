# BACKLOG — BizNiceSweets
Updated: 2026-07-16 (Phase 10 retro — MOUSSE now writes the inventory ledger so the p2
inventory-ledger race item's "revisit when MOUSSE writes this" trigger is live; zero-cost
lone-component issue → p3; 422 sweep + placeholder-dir prune now include mousse)
Prior: 2026-07-12 (Phase 9c retro — balance-sheet fiscal-close-gated defects → p2,
backdated-payment tie-out edge → p3, syerp `service.py` now ~3,700 lines in the split item)
Prior: 2026-07-12 (Phase 9b retro — 2 minor AP correctness edge-cases → p2, stale AP FE
types → p3, FOR UPDATE template cross-referenced into the inventory-ledger race item)
Prior: 2026-07-04 (seeded at adoption from the v1.0 milestone audit, codebase map, and the
kept items of `docs/tasks/chore-architecture-planning.md` — owner decision D-ADOPT-5)

## p1 — quality/infra debt that already bit once

- [ ] **CI pipeline** — no CI exists anywhere (no `.github/`, no pipeline config). Lint/test
  are manual; the `SyerpPartner` bug shipped through 4 plans because live-DB tests never ran.
  Minimum: ruff + pytest + eslint + vitest on push; stretch: a live-Postgres test job so
  `skip_if_no_db` tests actually run.
- [ ] **PLUM live-DB test harness never runs (4 root causes confirmed 2026-07-04, Phase 7)** —
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
- [ ] **Port Phase-8 verify-script assertions into runnable integration tests** (Phase 8 verify,
  2026-07-08, owner-accepted deferral). SYERP-10/11's crux behaviors have **no automated regression
  protection** — their only proof is standalone `backend/scripts/verify_{inventory,purchasing,e2e_p8}.py`
  that no suite runs: (1) the receive→on-hand→moving-average integration (SYERP-11.4), (2) audit rows
  written at the router (SYERP-10.7/11.7 — the verify scripts call service fns directly, bypassing
  where `write_audit` lives), (3) a syerp-endpoint 401/403 test (SYERP-10.8/11.8 — only the generic
  `tests/auth/test_rbac.py` covers the mechanism). Blocked on the async live-DB harness repair above;
  once that lands, port the script assertions into pytest integration tests and drop the "UI flow UAT
  pending / script-only" caveats from the SRD. A silent break in the crux currently passes every gate.
- [ ] **Neither lint gate runs (Phases 6/7/8 — recurring)** — `npm run lint` errors out because
  ESLint 10 requires a flat `eslint.config.js` the project lacks, so frontend lint has effectively
  never run; `ruff` is absent from both `backend/.venv` and the API image, so backend lint can't run
  either. `tsc -b` is the only enforced static check. Fix: add `frontend/eslint.config.js` (flat
  config) and install ruff as a dev dep / add it to the image. Treat as a hard pre-merge chore, not
  a per-phase surprise. Folds into the CI item above once both commands work.
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
- [ ] **Concurrency races on the inventory ledger** (Phase 8 review, accepted-risk for
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
