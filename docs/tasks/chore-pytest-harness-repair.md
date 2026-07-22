# Task: chore-pytest-harness-repair (v4.0 Phase 2a — NFR-5)

Repair the backend pytest harness so every DB-backed test runs against a live PostgreSQL
database with **zero silent skips**, fixing the four D-P7-4 root causes, and green the ~100
currently-skipped auth/plum/syerp/core tests — per-test-isolated, back-to-back-rerunnable,
pointable at both the in-container `db` host and a CI localhost Postgres.

Plan: `.zj/phases/02a-pytest-harness-repair/PLAN.md`
Branch: `chore-pytest-harness-repair` off `93de57d` (code-identical to `dd401d1` /
`zj/good-01-lint-gates-clean`; cut off the plan-carrying tip so PLAN.md travels — Task-0 deviation).

## Checklist

- [x] 0. Cut branch and open checklist
- [x] 1. Fix the DSN probe (SC1)
- [x] 2. Point the harness at a dedicated, migrated test database (SC6 + isolation foundation)
- [x] 3. NullPool test engine + resolve the app's session to it (SC2)
- [x] 4. Per-test truncate+reseed isolation, incl. the `admin-user` identity (SC3 + SC4)
- [x] 5. Green the auth package
- [x] 6. Green the core package
- [x] 7. Green the plum package
- [x] 8. Green the syerp DB-backed tests
- [x] 9. Green the root tests
- [x] 10. Prove non-vacuity (SC5)
- [x] 11. Document + prove env-pointability (SC6)
- [x] 12. Regression keepers: boot + verify_* + full-suite zero-skip green (SC5 + keepers)

## Regression gate (Task 12)

- **Cold boot:** `import app.main` → `BOOT_OK` (guards the Phase 12a/13 boot-500 class); the ASGI
  `tests/test_health.py` passes within the suite (app serves).
- **23/23 `verify_*` exit 0** in-container (ap/ap_api, ar/ar_api, crumb/crumb_api, crumb_so/so_api,
  e2e_p8, gelato/api, gelato_ship/api, gl/api, inventory, mousse/api, part_numbering,
  plum_vendor_paths, purchasing, reports/reports_api) — no FAILs. App-DB (`biznice`) unaffected by the
  test harness (tests run on `biznice_test`).
- **Full suite on one shared DB: 217 passed, 0 failed, 0 skipped** (167s). Back-to-back reruns stable
  (SC4). Non-vacuity proven (Task 10).
- **Lint gate held:** the syerp test edit introduced one ruff I001 (import order) in
  `tests/syerp/test_gl.py`; auto-fixed → `ruff check .` exit 0 (Phase-1 zero-violation baseline intact).

## Non-vacuity proof (Task 10, SC5)

Planted a transient product-behavior mutation in `app/modules/syerp/service/partners.py`
(`create_partner`: `partner.is_vendor = False` after building the row) → the DB-backed HTTP test
`tests/syerp/test_partners.py::test_create_vendor` turned **RED** (`assert False is True`, 1 failed).
Reverted the mutation → the same test returns **GREEN** (1 passed); working tree clean (no diff on
`partners.py`). This proves the formerly-skipped tests exercise the real DB round-trip and do not
vacuously pass.

## Run modes (Task 11, SC6 — env-pointable, no hard-coded host)

Documented in `backend/tests/conftest.py`'s module docstring. Host/port/password come from the
environment; conftest forces `POSTGRES_DB=$TEST_POSTGRES_DB` (default `biznice_test`) so the running
app DB is never touched. `grep -nE '"db"|"localhost"|host="' backend/tests/conftest.py` → none.

- **In-container (local default):**
  `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest -q'`
- **Localhost Postgres (CI / Phase 3; compose_db is never host-port-mapped, so CI runs its own):**
  `cd backend && POSTGRES_HOST=localhost POSTGRES_PORT=5432 POSTGRES_PASSWORD=<pw> JWT_SECRET=<≥32ch> BNS_ADMIN_PASSWORD=<pw> TEST_POSTGRES_DB=biznice_test .venv/bin/python -m pytest -q`
- Parallel-isolated runs: pass a distinct `TEST_POSTGRES_DB` (auto-created + migrated by the session fixture) — used during Wave B to green plum/syerp on separate DBs.

## Deviations

- **Task 0 branch point:** plan says cut off `dd401d1`; cut off `93de57d` instead (the plan
  commit, `.zj/`-docs-only, code-identical to `dd401d1`) so PLAN.md travels onto the branch.
  Same "bare tag drops the plan" precedent logged on phases 12a/12b/13.

- **Env prerequisite:** container `compose_api_1` python (3.13) lacked pytest/httpx/pytest-asyncio
  (pytest never ran here — the whole point of NFR-5). Installed `requirements-dev.txt` into the
  container's system site-packages as root (`podman exec --user root … pip install`). Ephemeral —
  lost on image rebuild. **Durable fix (bake dev deps into a test image) → Phase 3 / NFR-4.**

## Noticed

(populated during Wave B — every xfail/skip listed with reason + follow-up owner)
- Container dev-deps install is not durable across rebuild — Phase 3 must bake a test image
  (see Deviations). Documented for SC6 / Task 11.
- **No xfail/skip was needed** — every one of the 32 first-run failures was TEST drift (fixed) with
  zero product-code changes. So this section lists no suppressed tests.
- **Pre-existing, product-side, out of 2a scope (candidates for backlog / 2b):**
  (1) `SAWarning: unresolvable cycles between crumb_lead, crumb_opportunity` fires on every truncate —
  mutually-dependent FKs; harmless today but the warning says it "may raise an error in a future
  release." (2) `StarletteDeprecationWarning: HTTP_422_UNPROCESSABLE_ENTITY is deprecated` at
  `plum/router.py:277/563/680`. Neither is introduced by this phase.
- **`_isolate` reseeds auth + roster only, NOT the full app seed set** (modules/settings/COA/location/
  plum-tags) — deliberate, to keep the per-test baseline minimal so `test_inventory` (29) and other
  bare-DB-assuming tests stay green. GL tests that need the COA seed it themselves via a syerp-local
  `seeded_gl_accounts` fixture (mirrors core's `seeded_core_db`). Noted so 2b knows the baseline shape.
