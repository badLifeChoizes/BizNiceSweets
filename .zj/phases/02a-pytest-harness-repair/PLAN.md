# Plan: 02a — Pytest harness repair
Goal: Repair the backend pytest harness so every DB-backed test executes against a live PostgreSQL database with **zero silent skips**, fixing the four confirmed D-P7-4 root causes, and bring the ~100 currently-skipped auth/plum/syerp/core tests to a green, per-test-isolated, back-to-back-rerunnable run — pointable at both the in-container `db` host and a CI localhost Postgres so NFR-4/Phase 3 can wire it.
Status: draft

## Success criteria
Implements **NFR-5** (`.zj/SRD.md`; roadmap Phase 2, split 2a/2b per D-P2a-2). Fixes the four D-P7-4 root causes.

- **SC1 (root cause #1 — DSN):** the DB-availability probe connects; with a DB present, `skip_if_no_db` no longer skips.
- **SC2 (root cause #2 — event loop):** DB-backed tests run without `sqlalchemy.exc.InterfaceError` — direct-session fixtures (`async_db_session`/`seeded_db`/`seeded_core_db`) AND the httpx-ASGI `client` fixture (driving the app's own `get_db`) share one coherent, loop-safe engine.
- **SC3 (root cause #3 — admin-user seed):** auth/plum/syerp token+RBAC tests authenticate — the identities their minted tokens name are resolvable in the DB.
- **SC4 (root cause #4 — isolation):** the full suite reruns back-to-back with NO `uq_plum_part_number` (or other unique-constraint) IntegrityError collisions.
- **SC5 (green, non-vacuous):** `pytest -q` reports **0 skipped** among DB-backed tests and the suite is **GREEN**; the ~100 formerly-skipped tests execute and pass; non-vacuity proven (breaking an asserted behavior turns ≥1 DB-backed test RED). Any genuinely-broken test is fixed or `xfail`/`skip`-with-logged-reason in `## Noticed` — no bare deletions or blanket skips.
- **SC6 (env-pointable):** harness runs in-container (`postgres_host=db`) and against a localhost Postgres via env override, no hard-coded host; exact commands documented.

## Context
- **Branch (D-P2a-3):** `chore-pytest-harness-repair` cut off `zj/good-01-lint-gates-clean` @ `dd401d1`. v4.0 phases stack unmerged, ship at milestone close (v3.0's 11a→13 precedent). Conventional commits (`test:`/`chore:`/`fix:`), **no** co-authored/generated-with-Claude lines. Checklist at `docs/tasks/chore-pytest-harness-repair.md`.
- **No Alembic schema change** is expected — the test DB uses existing migrations (`backend/alembic/versions/`, head 0017-era). If a task finds it needs a migration, **STOP and flag** the owner.
- **The DSN bug (SC1):** `backend/tests/conftest.py:57` passes `settings.database_url_sync` (`postgresql+psycopg2://…`) to `psycopg2.connect()`. Verified today: this raises `ProgrammingError: invalid dsn: missing "=" …` → probe always False → everything skips. Fix: connect with libpq keyword args from `settings.postgres_host/port/db/user/password`.
- **The engine bug (SC2):** `backend/app/core/db.py:17-19` — module-level `engine = create_async_engine(settings.database_url)` + `AsyncSessionLocal`; `get_db()` (line 22) yields from it. Under pytest-asyncio (`asyncio_mode="auto"`, function-scoped loops) an asyncpg connection pooled on one loop is reused on another → `InterfaceError`. Fix: a `poolclass=NullPool` test engine (no cross-loop connection reuse) that the app's `AsyncSessionLocal`/`get_db` resolve to during tests.
- **The auth bug (SC3) — verified deeper than "seed missing":** `backend/app/modules/auth/dependencies.py:85` `get_current_user` resolves the token `sub` to a DB user via `get_user_by_id`, and `require_permission` (line 115-125) reads roles/permissions **from that DB user, not from the token's `permissions` claim**. Plum/syerp tests mint `create_access_token(subject="admin-user", permissions=[…])` (e.g. `tests/plum/test_bom.py:38`, `tests/syerp/test_partners.py:38`); auth tests log in as the real seeded admin (`admin_login_token`, `tests/auth/conftest_helpers.py:74`). So the DB must contain BOTH the real seeded admin AND a `User(id="admin-user")` with the admin (wildcard) role. `User.id` is `Mapped[str]` (String(36)) — `"admin-user"` is a legal PK value.
- **Fixtures today:** `tests/auth/conftest_helpers.py` (`async_db_session`, `seeded_db`, `admin_login_token`, `create_regular_user`), `tests/auth/conftest.py` (re-exports `seeded_db`), `tests/core/conftest.py` (`seeded_core_db`). All open `AsyncSessionLocal()` directly and gate on `skip_if_no_db`. Seeds: `app.modules.auth.seed.seed_admin_user`, `app.core.modules_seed.seed_modules_table`, `app.core.settings_seed.seed_default_settings`.
- **Test inventory & which already run:** pure-helper files with **no DB fixtures** already execute and pass — `tests/syerp/test_ap.py`, `test_purchasing.py`, `test_gl_journal.py`, `tests/plum/test_part_number.py`, `tests/auth/test_hashing.py`, `test_service_unit.py` (confirmed by header/imports). DB-backed (currently silently skipped): auth `test_login/test_rbac/test_refresh/test_refresh_rotation/test_seed_admin/test_user_admin`; core `test_modules/test_settings`; plum `test_avl/test_bom/test_costing/test_import_export/test_parts/test_revisions`; syerp `test_gl/test_inventory/test_partners`; root `test_health/test_migrations`.
- **mousse/crumb/gelato have no `tests/` dirs** — their crux lives only in `verify_*` (that is 2b, out of scope).
- **Live infra verified:** `compose_api_1`, `compose_db_1` (healthy) running; 23 `backend/scripts/verify_*.py` present; `pytest`/`ruff` at `backend/.venv/bin/`.

## Decisions
- **D-P2a-1 (isolation mechanism — chosen, not open):** dedicated **test database** (`biznice_test`, name overridable via `TEST_POSTGRES_DB`) built once per session via `alembic upgrade head`; a **session-scoped async engine with `poolclass=NullPool`**; **per-test isolation by `TRUNCATE … RESTART IDENTITY CASCADE` of all model tables (except `alembic_version`) + re-running the idempotent seeds** before each test. The app's `AsyncSessionLocal`/`get_db` resolve to this engine (module monkeypatch + `app.dependency_overrides[get_db]`) so both fixture families and `client` share it. *Why over savepoint/rollback:* the service layer calls `db.commit()` pervasively and HTTP-client tests commit through the app's own `get_db` session (a different connection than a test's direct session) — truncate-reset is robust regardless of how many sessions/connections committed. The owner kept concurrency mutation-proofs in the standalone `verify_*` scripts (D-P2a-2), so pytest never needs cross-session concurrent commits, which is what would have justified the more fragile shared-connection savepoint approach. NullPool is also the SC2 fix (no cross-event-loop connection reuse). *Why a separate DB, not `biznice`:* per-test TRUNCATE must never wipe the running dev/app data in `biznice`; conftest **force-sets** `POSTGRES_DB=biznice_test` (unconditional, not `setdefault` — the container already exports `POSTGRES_DB=biznice`) before `import app.main`.
- **D-P2a-2 (2a/2b split — recorded):** Phase 2 (NFR-5) is split. **2a (this phase)** repairs the harness and greens the *existing* suite. **2b (separate later phase)** ports the DoD-named `verify_*` cruxes (inventory moving-avg + audit/RBAC, GL/AP/AR ties, MOUSSE WIP-clears, CRUMB reservation, GELATO ship COGS) into pytest. The **concurrency mutation-proofs (`asyncio.gather`/`Barrier` + `FOR UPDATE`) STAY in the standalone `verify_*` scripts** (run as a separate CI step) and are NOT ported — which is what lets 2a's isolation model skip cross-session concurrency. No porting tasks appear in 2a.
- **D-P2a-3 (branch/stacking):** branch `chore-pytest-harness-repair` off `zj/good-01-lint-gates-clean` @ `dd401d1`; unmerged stack to milestone close.
- **D-P2a-5 (owner, Wave B — RBAC test-model reconciliation):** the never-run tests assume claim-based token permissions; shipped RBAC derives them from the DB user (claim ignored, D-P2a-4). Owner chose **seed a fixed test-identity roster** (min churn) in `_isolate` — extend beyond `admin-user`=wildcard to every DB-backed static subject tests mint, each bound to a role granting exactly its intended permission; rewrite only the negatives that mint the real (wildcard) admin with a stripped claim. Plus mechanical: force `BNS_ADMIN_EMAIL=admin@test.local`/`BNS_ADMIN_PASSWORD=testadminpass` for the hard-coded login tests, and fix ~7 domain/schema drifts per package. Full rationale in `.zj/DECISIONS.md` D-P2a-5.
- **D-P2a-4 (SC3 realization):** SC3 is satisfied by seeding, per test, the real admin (`seed_admin_user`) AND a `User(id="admin-user")` bound to the `admin` role — because RBAC resolves permissions from the DB user, not the token claim (verified in `dependencies.py`). This is a harness seed, not a product change.

## Tasks

### [x] 0. Cut branch and open checklist
- **Files:** `docs/tasks/chore-pytest-harness-repair.md` (new)
- **Do:** `git checkout -b chore-pytest-harness-repair zj/good-01-lint-gates-clean`. Create the checklist file mirroring this task list.
- **Done when:** branch exists at `dd401d1`; checklist committed (`chore:`).
- **Verify:** `git log --oneline -1` shows the branch tip == `dd401d1`; `git branch --show-current` == `chore-pytest-harness-repair`.
- **Parallel-ok:** no (gates everything)

---
### Wave A — repair the four root causes at the harness layer (NFR-5, SC1–SC4, SC6)

### [x] 1. Fix the DSN probe (SC1)
- **Files:** `backend/tests/conftest.py` (`_check_db_available`, lines ~44-64; add 2-line ABOUTME header while here)
- **Do:** Replace the `psycopg2.connect(settings.database_url_sync, …)` call with libpq keyword args: `psycopg2.connect(host=settings.postgres_host, port=settings.postgres_port, dbname=settings.postgres_db, user=settings.postgres_user, password=settings.postgres_password.get_secret_value(), connect_timeout=2)`. Keep the `try/except → bool` shape. Add the ABOUTME 2-line header (Phase-1 `## Noticed` cleanup).
- **Done when:** in-container, `db_available()` returns True and no DB-backed test is skipped for "no live database".
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -c "from tests.conftest import _check_db_available; print(_check_db_available())"` prints `True`. (Depends on Task 2's env forcing for the DB name, but the DSN shape is provable standalone: the old form raised `invalid dsn`, the new form connects.)
- **Parallel-ok:** no (conftest is edited by Tasks 1-4)

### [x] 2. Point the harness at a dedicated, migrated test database (SC6 + isolation foundation)
- **Files:** `backend/tests/conftest.py` (env block ~24-33; new session-scoped setup fixture)
- **Do:** BEFORE `import app.main`, **force** `os.environ["POSTGRES_DB"] = os.environ.get("TEST_POSTGRES_DB", "biznice_test")` (unconditional — container already exports `POSTGRES_DB=biznice`). Leave `POSTGRES_HOST`/`POSTGRES_PORT` to the environment (no hard-coding — SC6). Add a **sync, session-scoped, autouse** fixture that: (a) connects to the maintenance DB (`dbname="postgres"`) via psycopg2 keyword args and `CREATE DATABASE biznice_test` if absent; (b) runs `alembic upgrade head` against it as a subprocess (`.venv/bin/alembic upgrade head`, cwd `backend/`, inheriting the forced env so `alembic/env.py` targets `biznice_test`). Sync + session-scoped avoids any event-loop-scope conflict.
- **Done when:** a fresh `biznice_test` exists with the full schema at head; the running app's `biznice` DB is untouched.
- **Verify:** `podman exec compose_db_1 psql -U app -d biznice_test -c "\dt"` lists `users`, `plum_parts`, `alembic_version` (and confirms head via `select version_num from alembic_version`).
- **Parallel-ok:** no

### [x] 3. NullPool test engine + resolve the app's session to it (SC2)
- **Files:** `backend/tests/conftest.py` (new engine + session-scoped autouse wiring fixture); reads `backend/app/core/db.py`
- **Do:** Create one `create_async_engine(settings.database_url, poolclass=NullPool)` and an `async_sessionmaker(test_engine, expire_on_commit=False)`. In a session-scoped autouse fixture, monkeypatch `app.core.db.engine` and `app.core.db.AsyncSessionLocal` to the test objects (so the direct-session fixtures that do `from app.core.db import AsyncSessionLocal` bind to it) AND set `app.main.app.dependency_overrides[get_db]` to yield from the test sessionmaker (so the `client` fixture's routes/`get_current_user` use it). Expose the test sessionmaker for fixtures.
- **Done when:** a DB-backed test using both `client` and `async_db_session` runs to completion with no `InterfaceError`/"attached to a different loop".
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -m pytest tests/syerp/test_partners.py -q` runs without any `InterfaceError` (assertion failures still allowed at this stage; loop errors are not).
- **Parallel-ok:** no

### [x] 4. Per-test truncate+reseed isolation, incl. the `admin-user` identity (SC3 + SC4)
- **Files:** `backend/tests/conftest.py` (new function-scoped autouse `_isolate` fixture); reads `app.modules.auth.seed`, `app.modules.auth.models`
- **Do:** Add a **function-scoped autouse async** fixture that, before each test, on the test engine: (1) `TRUNCATE <all Base.metadata tables except alembic_version> RESTART IDENTITY CASCADE` in one statement; (2) `await seed_admin_user(session)` (roles/permissions + real admin); (3) insert `User(id="admin-user", email="admin-user@test.local", hashed_password=<any hash>, is_active=True)` and append the `admin` role, commit — so tokens minted with `subject="admin-user"` resolve and pass the wildcard RBAC check (D-P2a-4). Enumerate truncatable tables from `Base.metadata.sorted_tables`.
- **Done when:** running the full suite twice back-to-back yields identical results with zero `uq_plum_part_number`/unique-constraint `IntegrityError`; a plum test that only mints an `admin-user` token (no `seeded_db`) authenticates (no 401).
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest tests/plum/test_parts.py -q && python -m pytest tests/plum/test_parts.py -q'` — both runs report the same pass count, no IntegrityError.
- **Parallel-ok:** no

---
### Wave B — execute the newly-running suite and make each package green (NFR-5, SC5)
> These tests have LITERALLY never run; expect latent breakage (drifted assertions, stale API shapes, wrong status codes, changed schemas). For each package: run it, triage failures into (a) test drift → fix the test, (b) real product bug → fix minimally or, if it exceeds harness scope, record as `xfail(reason=…)` in `## Noticed`, (c) genuinely obsolete → `skip(reason=…)` with justification. **No bare deletes, no blanket skips.** Each package is one task; split further only if a package's fix set exceeds ~1h. Wave B tasks are independent of each other once Wave A lands.

### [x] 5. Green the auth package
- **Files:** `backend/tests/auth/test_login.py`, `test_rbac.py`, `test_refresh.py`, `test_refresh_rotation.py`, `test_seed_admin.py`, `test_user_admin.py` (pure `test_hashing.py`/`test_service_unit.py` already pass — re-confirm)
- **Do:** Run the package; fix/triage per the Wave-B policy. Watch for `admin_login_token` depending on the real seeded admin (present via Task 4) and refresh-token family/rotation rows surviving truncate correctly.
- **Done when:** `pytest tests/auth -q` is green, 0 skipped.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -m pytest tests/auth -q`
- **Parallel-ok:** yes

### [x] 6. Green the core package
- **Files:** `backend/tests/core/test_modules.py`, `test_settings.py`, `backend/tests/core/conftest.py` (add 2-line ABOUTME header — Phase-1 `## Noticed` cleanup)
- **Do:** Run/triage; `seeded_core_db` runs three seeds — confirm order and idempotency under truncate-reset.
- **Done when:** `pytest tests/core -q` green, 0 skipped; `core/conftest.py` carries the ABOUTME header.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -m pytest tests/core -q`
- **Parallel-ok:** yes

### [x] 7. Green the plum package
- **Files:** `backend/tests/plum/test_avl.py`, `test_bom.py`, `test_costing.py`, `test_import_export.py`, `test_parts.py`, `test_revisions.py` (pure `test_part_number.py` already passes)
- **Do:** Run/triage per policy. `test_bom` (341L) and `test_costing` (310L) are heavy DB and the original D-P7-4 evidence set — expect the most drift here. AVL rows FK to SYERP partners; ensure their setup seeds a partner.
- **Done when:** `pytest tests/plum -q` green, 0 skipped.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -m pytest tests/plum -q`
- **Parallel-ok:** yes

### [x] 8. Green the syerp DB-backed tests
- **Files:** `backend/tests/syerp/test_gl.py`, `test_inventory.py`, `test_partners.py` (pure `test_ap.py`/`test_gl_journal.py`/`test_purchasing.py` already pass — re-confirm they still do)
- **Do:** Run/triage per policy. `test_inventory` (459L, 29 tests) is the largest DB set. Confirm the three pure files are unaffected by the harness changes.
- **Done when:** `pytest tests/syerp -q` green, 0 skipped.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -m pytest tests/syerp -q`
- **Parallel-ok:** yes

### [x] 9. Green the root tests
- **Files:** `backend/tests/test_health.py`, `backend/tests/test_migrations.py`
- **Do:** Run/triage. `test_migrations` likely asserts head/round-trip against the DB — confirm it targets `biznice_test`.
- **Done when:** `pytest tests/test_health.py tests/test_migrations.py -q` green, 0 skipped.
- **Verify:** `podman exec -e PYTHONPATH=/app compose_api_1 python -m pytest tests/test_health.py tests/test_migrations.py -q`
- **Parallel-ok:** yes

---
### Wave C — non-vacuity, env-pointability, and the regression keepers (NFR-5, SC5/SC6 + keepers)

### [x] 10. Prove non-vacuity (SC5)
- **Files:** none committed (transient edit)
- **Do:** Temporarily break one asserted product behavior a DB-backed test exercises (e.g. return a wrong `on_hand` in inventory service, or a wrong status code in `syerp/router.py`); confirm ≥1 DB-backed pytest test turns RED; revert. Record which test + which mutation in the checklist.
- **Done when:** a documented mutation flips a named DB-backed test RED, and reverting restores green — proving the tests hit the DB, not vacuously pass.
- **Verify:** the checklist records the RED test name and the revert; suite green after revert.
- **Parallel-ok:** no (run after Wave B green)

### [x] 11. Document + prove env-pointability (SC6)
- **Files:** `backend/tests/conftest.py` (module docstring), `docs/tasks/chore-pytest-harness-repair.md`
- **Do:** Document the two run modes and the env knobs (`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_PASSWORD`, `JWT_SECRET`, `BNS_ADMIN_PASSWORD`, `TEST_POSTGRES_DB`). No hard-coded host anywhere. Prove the default in-container run (`host=db`) green; describe the CI localhost invocation for Phase 3 (a localhost Postgres service, since `compose_db` is never port-mapped to the host).
- **Done when:** both commands (bottom of this plan) are documented; `grep -rn '"db"' backend/tests` shows no hard-coded host in test code.
- **Verify:** in-container run green; `rg -n "localhost\"|\"db\"" backend/tests/conftest.py` shows host comes from settings/env only.
- **Parallel-ok:** yes

### [x] 12. Regression keepers: boot + verify_* + full-suite zero-skip green (SC5 + keepers)
- **Files:** none (verification task); may touch nothing beyond re-running gates
- **Do:** Because this phase rewires shared harness/engine surfaces, prove no regression: (1) **cold boot** — `import app.main` succeeds and the app serves (guards the Phase 12a/13 boot-500 class); (2) all **23 `verify_*` scripts** exit 0 in-container; (3) full `pytest -q` reports **0 skipped among DB-backed tests** and is GREEN. Confirm no change was made to `app/core/db.py`'s production behavior beyond test-time monkeypatch (the app engine still builds at import).
- **Done when:** app boots + serves; 23/23 verify_* exit 0; full suite green with 0 DB-backed skips.
- **Verify:**
  - Boot: `podman exec -e PYTHONPATH=/app compose_api_1 python -c "import app.main; print('boot-ok')"` and `curl -sf http://<api>/api/v1/health` (or the ASGI health test) returns 200.
  - verify_*: `for s in backend/scripts/verify_*.py; do podman exec -e PYTHONPATH=/app compose_api_1 python scripts/$(basename $s) || echo "FAIL $s"; done` — no FAIL lines.
  - Suite: the full-run command below reports `0 skipped` for DB tests.
- **Parallel-ok:** no (final gate)

## Risks
- **Latent breakage larger than expected** — these ~100 tests have never run; assertions/API shapes may have drifted across 13 phases. *Early warning:* Wave B failure counts on first run. *Mitigation:* one owning task per package + honest xfail/skip-with-reason policy (never blanket-skip to force green).
- **pytest-asyncio loop-scope vs a session-scoped engine** — a session-scoped *async* fixture conflicts with function-scoped loops. *Early warning:* `InterfaceError`/"attached to a different loop" persists after Task 3. *Mitigation:* keep DB-create/migrate SYNC and session-scoped; keep the engine a plain (non-async) object; run TRUNCATE in the function loop; NullPool guarantees fresh per-loop connections.
- **`CREATE DATABASE` / TRUNCATE privileges** for the `app` role on `biznice_test`. *Early warning:* Task 2 session fixture errors on create, or Task 4 truncate raises `permission denied`. *Mitigation:* create via the maintenance connection; document any required `GRANT`; the DB is owned by `app` in compose so this is expected to work.
- **A latent fix reveals a needed schema change** — forbidden in 2a. *Early warning:* a test wants a column/constraint not at head. *Mitigation:* STOP and flag the owner (do not add an Alembic revision here).

## Deviations
- **Task 0 branch point:** plan says cut off `dd401d1`; cut off `93de57d` instead (the plan commit, `.zj/`-docs-only, code-identical to `dd401d1` / tag `zj/good-01-lint-gates-clean`) so PLAN.md travels onto the build branch. Same "bare tag drops the plan" precedent logged on phases 12a/12b/13.

## Noticed
- Populate during Wave B: every test that ends up `xfail`/`skip` must be listed here with its reason and the follow-up owner (product-bug backlog item, or 2b). Bare deletion is not permitted.
- Candidate 2b hand-off: any `verify_*` crux assertion found missing from the pytest suite while greening a package (do not port it here — record it for 2b).
- ABOUTME headers added to `tests/conftest.py` (Task 1) and `tests/core/conftest.py` (Task 6) close the Phase-1 `## Noticed` cleanup item for those two pre-standard files.

## Out of scope (deferred so build doesn't drift)
- **Porting `verify_*` crux assertions into pytest** — that is Phase 2b (D-P2a-2).
- **Concurrency mutation-proofs** (`asyncio.gather`/`Barrier` + `FOR UPDATE`) — stay in the standalone `verify_*` scripts as a separate CI step (owner decision, D-P2a-2); not ported to pytest.
- **CI auto-run wiring** of the gates — Phase 3 / NFR-4.
- **New `tests/` dirs for mousse/crumb/gelato** — no pytest coverage exists; their crux stays in `verify_*` until 2b.
- **Any Alembic schema change** — the test DB uses existing migrations.

---
## Run the repaired suite

**In-container (local default; `postgres_host=db` from container env, `POSTGRES_DB` forced to `biznice_test` by conftest):**
```
podman exec -e PYTHONPATH=/app compose_api_1 python -m pytest -q
```

**Against a localhost Postgres (CI / Phase 3; a localhost Postgres service, since compose_db is never host-port-mapped):**
```
cd backend && POSTGRES_HOST=localhost POSTGRES_PORT=5432 \
  POSTGRES_PASSWORD=<pw> JWT_SECRET=<≥32-char secret> BNS_ADMIN_PASSWORD=<pw> \
  TEST_POSTGRES_DB=biznice_test \
  .venv/bin/python -m pytest -q
```
