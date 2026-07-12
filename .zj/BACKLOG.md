# BACKLOG — BizNiceSweets
Updated: 2026-07-04 (seeded at adoption from the v1.0 milestone audit, codebase map, and the
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

## p2 — architecture & docs

- [ ] **Split `backend/app/modules/plum/service.py` (~3,000 lines)** before MOUSSE/CRISP copy
  the pattern — the monolith-file smell the prototypes suffered from. Target: before/at
  Phase 10 (MOUSSE). **Note (Phase 8):** `syerp/service.py` has now grown to ~1,800 lines
  (inventory + purchasing landed here) — the same smell is starting in the hub module; fold it
  into this split when done.
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
  `SELECT … FOR UPDATE` / serialized posting then.
- [ ] **Alembic autogenerate never exits clean** (Phase 9a verify, 2026-07-11) — `alembic check`
  reports spurious drift on **7 pre-existing unnamed `unique=True` constraints** (plum_part.part_number,
  uq_plum_part_one_released, syerp_gl_account/inventory_item/partner.code, purchase_order.po_number,
  stock_location.name) that reflect from Postgres with names the model metadata lacks; migration `0009`
  also sets `server_default=sa.text("now()")` on `created_at` while the model uses a Python-side
  `default=` only, adding one more drift line. None are correctness bugs, but they mean autogenerate
  is unusable for drift-detection. Fix: add a naming convention on `Base.metadata` (`naming_convention=`)
  so constraints reflect with stable names, and align the model/migration `created_at` default. Do
  before autogenerated migrations are ever trusted.
- [ ] **Reverse-from-UI has no Vitest** (Phase 9a verify, G3/m6) — the "Reverse" action in
  `frontend/src/routes/syerp/JournalEntries.tsx` (`c2bde3d`) is exercised only by hand; backend
  reversal incl. the 409 double-reversal guard is covered by `verify_gl.py`. Add a Vitest case
  mirroring the post-flow test: confirm dialog → `POST {id}/reverse` → toast + query invalidate.
  Fold into the 9b/9c frontend wave.
- [ ] **Integration specs** (kept from chore-architecture-planning): PLUM↔MOUSSE,
  PLUM↔SYERP, FLAN↔SYERP, shared vendor/document infrastructure.
- [ ] **Suite documentation sets** (kept): SYERP, CRUMB, MOUSSE, CRISP, GELATO under
  `docs/features/{suite}/` per `_templates/`.
- [ ] **Remove dead `frontend/src/components/ProtectedRoute.tsx`** — replaced by AppShell;
  only its own test references it.
- [ ] **Dependency license audit** (NFR-2) — required before public open-source release.

## p3 — hygiene

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
- [ ] **Receipt auto-post `entry_date` is server-local, not UTC** (Phase 9a verify) —
  `receive_line` dates the auto-posted JE with `date.today()` while `created_at` is UTC, so near
  midnight a receipt and its JE can land on different calendar days and split across register
  periods. Acceptable for single-timezone self-host; switch to
  `datetime.now(timezone.utc).date()` if UTC-consistent periods are ever required (e.g. multi-region
  deploy or fiscal-period locking in 9c).
- [ ] **`.zj/codebase/MAP.md` fuller refresh owed** (Phase 9a verify) — the migration list was
  corrected through 0009 in the verify loop, but the GL endpoints, journal tables, and the grown
  syerp `service.py` surface are still unmapped. Refresh via `/zj:docs` before the next mapper-driven
  planning pass.
- [ ] **Starlette 422 deprecation sweep** (Phase 8) — `HTTP_422_UNPROCESSABLE_ENTITY` is
  deprecated for `HTTP_422_UNPROCESSABLE_CONTENT`; fires from `post_receipt` / `post_adjustment` /
  `post_transfer` / `receive_line` in `backend/app/modules/syerp/service.py` and likely older
  modules. Cosmetic; one mechanical sweep before it becomes log noise.
