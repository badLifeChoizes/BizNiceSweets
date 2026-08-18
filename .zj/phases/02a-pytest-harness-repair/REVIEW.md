# Review: v4.0 Phase 2a — Pytest harness repair (NFR-5)
Date: 2026-07-21
Scope: `zj/good-01-lint-gates-clean..HEAD` on `chore-pytest-harness-repair` (tip 1f065eb), `backend/` only.

## Summary
`git diff zj/good-01-lint-gates-clean..HEAD -- backend/app/` is **empty** — the "zero product-code changes"
claim holds; every hunk is under `backend/tests/`. The RBAC test rewrites (test_rbac.py, test_parts.py,
test_gl.py, test_partners.py) are genuine *strengthenings*, not force-green weakenings: they replace
wildcard-admin tokens with tokens minted for real roleless/limited DB users, which is the only way the
shipped "authorize from DB roles, ignore the JWT `perms` claim" gate can return a real 403. No assertion
was made vacuous, no bare deletes, no unexplained skip/xfail. Isolation, engine wiring, and the
`biznice_test` targeting are sound (see Verified). Two harness robustness defects below.

## Findings

### 1. [major] Test-DB provisioning shells out to `"python"` instead of `sys.executable`
- **Where:** `backend/tests/conftest.py:184-188` (`_provision_test_database`), no `import sys` present.
- **Failure:** The session-scoped autouse fixture runs `subprocess.run(["python", "-m", "alembic",
  "upgrade", "head"], cwd=backend_root, check=True)`. The conftest's own SC6/CI run mode is documented as
  `cd backend && … .venv/bin/python -m pytest` (lines 29-32). Invoking pytest via an explicit interpreter
  path does **not** put a `python` on `PATH`. On a standard Debian/Ubuntu CI image (only `python3` exists,
  no `python` symlink — reproduced on this very host: `which python` → not found) the subprocess raises
  `FileNotFoundError: python`, which aborts the session-scoped autouse fixture and **errors the entire
  suite before a single test runs**. Even where a `python` exists, it may be a different interpreter than
  the one running pytest and thus lack alembic/asyncpg (`ModuleNotFoundError` under `check=True`), again
  failing the whole run. This defeats the phase's stated goal (SC6: "runs unchanged against a CI localhost
  Postgres").
- **Fix:** `import sys` and use `[sys.executable, "-m", "alembic", "upgrade", "head"]`.

### 2. [major] Autouse provisioning/isolation unconditionally require a DB — no-DB runs error the whole suite
- **Where:** `backend/tests/conftest.py:139-188` (`_provision_test_database`, session autouse) and
  `237-340` (`_isolate`, function autouse). Neither gates on `db_available()`.
- **Failure:** The module docstring (lines 13-14) and the still-present `skip_if_no_db` fixture promise
  that when the DB is unreachable, "tests that require a live DB are skipped with a clear message" while
  pure-unit tests still run. That promise is now dead: with no Postgres reachable,
  `_provision_test_database`'s `psycopg2.connect(...)` raises, and because it is session-scoped **autouse**,
  every test in the tree errors at setup — including DB-free unit tests such as
  `tests/auth/test_hashing.py` and `tests/auth/test_service_unit.py`, which previously passed without a DB.
  Net effect: `pytest` on a dev box with no Postgres goes from "unit tests pass, DB tests skip" to "0
  collected tests run, all error." `skip_if_no_db` is now unreachable code for the no-DB case.
- **Fix:** Either drop the skip-when-no-DB promise from the docstring and remove/retire `skip_if_no_db`
  (make "DB required" explicit), or have the autouse provisioning fixture call `db_available()` and
  `pytest.skip`/short-circuit so DB-free tests still run. Pick one; today the design contradicts itself.

## Questions
- Is running the suite without a live Postgres a supported scenario post-Phase-2a? If DB is now a hard
  prerequisite in every environment (container + CI), finding #2 is a doc-consistency cleanup rather than a
  regression — but the surviving `skip_if_no_db` fixture and docstring say otherwise, so the intent should
  be stated explicitly in `.zj/` and the contradictory machinery removed.

## Verified (probed, no defect)
- **No product-code change:** `git diff … -- backend/app/` empty. `admin-user`/roster/`admin@test.local`
  seeds live only in `_isolate` against `TestSessionLocal` → `biznice_test`; no backdoor identity reaches
  the real `biznice` DB (SC3/SC5 hold).
- **TRUNCATE targets biznice_test, never biznice:** line 70 *unconditionally* overrides `POSTGRES_DB`
  before `Settings()` instantiation, so `settings.database_url` (and thus `test_engine`, `TestSessionLocal`,
  the `_override_get_db` session, and the alembic subprocess env) all resolve to `biznice_test`. TRUNCATE
  runs only on `test_engine` (SC6/#6 safe). The only path to hitting `biznice` is operator-set
  `TEST_POSTGRES_DB=biznice`, which is documented misuse.
- **No engine split-brain (SC2):** `_wire_test_engine` (session autouse, runs first) monkeypatches
  `app.core.db.engine`/`AsyncSessionLocal` and sets `dependency_overrides[get_db]`. Every direct-session
  fixture (`async_db_session`, `seeded_db`, `seeded_gl_accounts`) imports `AsyncSessionLocal` *inside the
  fixture body* at call time, so it binds to the patched `TestSessionLocal` — same NullPool engine, same
  `biznice_test`, as the client override. No fixture captures the pre-patch object.
- **Isolation ordering (SC4):** `_isolate` is autouse and therefore instantiated before the explicitly
  requested `seeded_gl_accounts`/`seeded_core_db` at the same (function) scope, so per-test COA/core seeds
  land *after* the truncate, not before. `TRUNCATE … RESTART IDENTITY CASCADE` over
  `Base.metadata.sorted_tables` (all models registered via the top-level `from app.main import app`) plus
  CASCADE covers FK children, so no cross-test bleed. All models present because the app import registers
  every module.
- **Negative RBAC tests are non-vacuous:** every 403-expecting test uses a genuinely limited identity
  (API-created roleless user, or roster `syerp-reader`/`regular-user-id`). No 403 test mints an
  `admin-user` (wildcard) token; `admin-user` read tokens appear only in positive 200 read tests, which
  pass correctly because `admin-user` holds the admin role regardless of claim.
- **Migration DB target:** the alembic subprocess inherits the parent's mutated `os.environ`
  (forced `POSTGRES_DB=biznice_test`), so env/env.py targets the test DB.
