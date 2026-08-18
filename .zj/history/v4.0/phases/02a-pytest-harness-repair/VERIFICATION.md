# Verification: Phase 02a — Pytest harness repair (NFR-5)
Date: 2026-07-21 | Commits: zj/good-01-lint-gates-clean..HEAD (b66f0e7..1f065eb, 17 commits) on chore-pytest-harness-repair
Verdict: PASS (all 6 success criteria PASS empirically; the 1 major + 2 minor gaps found at first pass were ALL fixed in the verify fix loop — see "Fix loop" below; full suite re-run 219 passed / 0 skipped)

## Fix loop (2026-07-22 — gaps closed, re-verified)
All three verifier gaps + both reviewer majors were fixed; the suite was re-run in full afterward.
- **Reviewer major #1 — `"python"` subprocess → `sys.executable`** (`conftest.py:207`): the provisioning fixture shelled out to a bare `python` (absent on standard Debian/Ubuntu/CI hosts where pytest launches via `.venv/bin/python`), which would `FileNotFoundError` the whole session and defeat SC6. Fixed to `sys.executable`.
- **Reviewer major #2 + verifier gap #1 design fork — no-DB behavior (owner: DB is a HARD REQUIREMENT):** `_provision_test_database` now calls `db_available()` and `pytest.exit(...)` with a clear message if no Postgres is reachable — **fails loud, never silent-skips**. The `skip_if_no_db` fixture was retired to a documented no-op (kept as a legacy alias so ~28 call sites don't need a mechanical parameter-strip); the module docstring + `client` docstring were corrected to drop the stale graceful-skip promise.
- **Verifier gap #1 — zero-silent-skip invariant now has a standing test:** new `backend/tests/test_harness_selfcheck.py` (`test_db_probe_connects` + `test_db_available_flag_true`) asserts `db_available() is True` — a re-introduced DSN/probe break now **fails loud** here instead of silently disappearing the DB tests while CI stays green. This closes the "central deliverable unprotected" gap; non-vacuity is no longer only a manual mutation.
- **Verifier gap #2 (minor) — SRD NFR-5 status:** updated from `planned` to `partial (2a done / 2b pending)` with a Verified stamp (`.zj/SRD.md:707`).
- **Verifier gap #3 (minor) — MAP.md test row:** updated to document the `biznice_test` DB, `TEST_POSTGRES_DB`, and both run modes (`.zj/codebase/MAP.md:70`).
- **Re-verification after the fix:** full suite `219 passed, 0 skipped` (217 + 2 self-check) in 175s; `ruff check` on the changed files exit 0; cold boot `boot-ok`; `git diff -- backend/app/` still empty (fixes are test-only). SC6's CI-localhost path is now portable (`sys.executable`).

## Summary of empirical runs
- Full suite in-container, run #1: `217 passed, 224 warnings in 165.34s` — **0 skipped**.
- Full suite in-container, run #2 (back-to-back): `217 passed, 224 warnings in 165.70s` — identical, **0 skipped, 0 IntegrityError**.
- Per-package: auth 65, core 7, plum 40, syerp 99, health+migrations 6 = **217 passed, 0 skipped** each.
- `git diff --stat zj/good-01-lint-gates-clean..HEAD -- backend/app/` is **empty** — zero product-code changes confirmed (build claim true). Only `backend/tests/**` + `.zj/` + `docs/tasks/` changed.
- 23/23 `verify_*` scripts exit 0. Cold boot `import app.main` → `boot-ok`.

## Criteria

### SC1 (DSN probe connects; no silent skip) — PASS
| Truth | Exists | Wired | Works | Evidence |
|-------|--------|-------|-------|----------|
| Probe uses libpq keyword args, not the `+psycopg2` URL | yes | yes | yes | `conftest.py:109-116` `psycopg2.connect(host=…, port=…, dbname=…, user=…, password=…)`. `python -c "from tests.conftest import _check_db_available; print(...)"` → `True`. |
| With DB present, `skip_if_no_db` does not skip | — | yes | yes | Full run shows 0 skipped; the ~100 DB-backed tests all execute. |

### SC2 (event loop; no InterfaceError; shared NullPool engine) — PASS
| Truth | Exists | Wired | Works | Evidence |
|-------|--------|-------|-------|----------|
| One NullPool async test engine | yes | yes | yes | `conftest.py:89-90` `create_async_engine(..., poolclass=NullPool)` + `TestSessionLocal`. |
| Direct-session fixtures resolve to it | yes | yes | yes | `_wire_test_engine` monkeypatches `app.core.db.engine`/`.AsyncSessionLocal` (`conftest.py:212-215`). |
| httpx-ASGI `client` resolves to it | yes | yes | yes | `app.dependency_overrides[get_db]` override (`conftest.py:217-221`); tests mixing `client`+direct session pass with no `InterfaceError` across the full 217-test run. |

### SC3 (admin-user seed; RBAC resolves from DB user) — PASS
| Truth | Exists | Wired | Works | Evidence |
|-------|--------|-------|-------|----------|
| Real seeded admin present per test | yes | yes | yes | `_isolate` calls `seed_admin_user` (`conftest.py:274`); auth login/refresh tests (65 passed) authenticate as `admin@test.local`. |
| `User(id="admin-user")` bound to admin role | yes | yes | yes | `conftest.py:280-287`; plum/syerp tests minting `subject="admin-user"` get 201/200 (not 401/403). |
| Limited roster identities (`syerp-reader`, `regular-user-id`) | yes | yes | yes | `conftest.py:308-336`; negative RBAC tests get genuine 403 — proven by non-vacuity below and 99 syerp / 65 auth passing. |

### SC4 (isolation; back-to-back, no unique-constraint collisions) — PASS
| Truth | Exists | Wired | Works | Evidence |
|-------|--------|-------|-------|----------|
| Per-test TRUNCATE … RESTART IDENTITY CASCADE + reseed | yes | yes | yes | `_isolate` autouse fixture (`conftest.py:237-340`). |
| Back-to-back reruns identical, 0 IntegrityError | — | yes | yes | Two full runs: `217 passed` both, no `uq_plum_part_number`/IntegrityError in either. |

### SC5 (green, non-vacuous, 0 skipped) — PASS
| Truth | Exists | Wired | Works | Evidence |
|-------|--------|-------|-------|----------|
| Full suite green, 0 skipped | — | — | yes | `217 passed, 224 warnings` — no `skipped` token in summary. |
| ~100 formerly-skipped tests now execute+pass | — | yes | yes | Per-package counts (auth/core/plum/syerp/root) all 0 skipped. |
| Non-vacuity: mutation flips a DB-backed test RED | — | — | yes | **Re-driven independently**: set `partners.py:63` `"is_vendor": False` → `tests/syerp/test_partners.py::test_create_vendor` → `FAILED … assert False is True (1 failed)`. Reverted via `git checkout` → `1 passed`; tree clean (`git status` empty for the file). |
| No bare deletions / blanket skips | yes | — | yes | `## Noticed` records ABOUTME headers only; no committed xfail/skip; all 32 first-run failures were test drift (product diff empty). |

### SC6 (env-pointable; no hard-coded host) — PASS (localhost mode documented, not yet exercised — no CI until Phase 3)
| Truth | Exists | Wired | Works | Evidence |
|-------|--------|-------|-------|----------|
| Host/port come from env, not literals | yes | yes | yes | `grep -nE '"db"\|"localhost"\|host="' tests/conftest.py` → no matches. Host read from `settings.postgres_host`. (Only repo grep hit `test_health.py:26 body["db"]` is a JSON response key, not a host.) |
| Dedicated `biznice_test` DB, forced before import | yes | yes | yes | `conftest.py:70` `os.environ["POSTGRES_DB"]=…TEST_POSTGRES_DB, "biznice_test"`; `biznice_test` exists, 47 tables, `alembic_version=0017`. |
| Live `biznice` untouched | — | yes | yes | Live DB independently intact: 47 tables incl. `plum_part`, `syerp_partner`. |
| Both run modes documented | yes | — | n/a (localhost) | `conftest.py:16-33` module docstring documents in-container + localhost commands and env knobs. Localhost mode is documented but not exercised here (compose_db is never host-port-mapped; CI localhost Postgres is Phase 3). |

## Regression protection
| Criterion | Pinned by |
|-----------|-----------|
| SC1 DSN probe | **MISSING (gap below)** — no standing test asserts `db_available()` is True; a re-introduced DSN bug would silently skip DB tests and CI would stay green. |
| SC2 event loop | The suite itself — any cross-loop reuse raises `InterfaceError` → RED across DB tests. |
| SC3 admin-user/RBAC | `tests/syerp/test_partners.py`, `tests/plum/*`, `tests/auth/test_rbac.py`, `test_user_admin.py` (401/403 on missing/limited identity). |
| SC4 isolation | The suite (a collision RED-fails within a run); **back-to-back rerun is not a standing automated check** — manual. |
| SC5 green | The full suite (exit code). **Non-vacuity is a transient, uncommitted mutation — harness correctness is otherwise unprotected.** |
| SC5 zero-skip invariant | **MISSING (gap below)** — pytest exit 0 does not distinguish "ran" from "skipped"; nothing fails when DB tests silently skip again. |
| SC6 env-pointable | manual: config/docs; localhost path unexercised until Phase 3 CI. |

## Test suite
- `podman exec -e PYTHONPATH=/app compose_api_1 sh -c 'cd /app && python -m pytest -q'` → `217 passed, 224 warnings in 165.34s` (run #1) / `165.70s` (run #2). 0 failed, 0 skipped, 0 error.
- verify_* regression: all 23 scripts exit 0.
- Cold boot: `import app.main` → `boot-ok`.

## Gaps (all RESOLVED in the fix loop — see "Fix loop" at top)
1. **[major — RESOLVED] No standing test guards the phase's own goal — the zero-silent-skip invariant.** The whole phase exists because ~100 DB tests silently skipped and CI stayed green. Nothing today re-catches that: pytest exit 0 is identical whether the DB-backed tests run or skip, and reverting the SC1 DSN fix would make `skip_if_no_db` skip again while the autouse `_isolate`/`_provision` fixtures (which connect independently) keep the run "green". Suggested fix: add `backend/tests/test_harness_selfcheck.py` with (a) `test_db_probe_connects` asserting `db_available() is True` (fails loudly, not-skips, if the probe breaks), and optionally (b) a session-end hook asserting `terminalreporter.stats.get("skipped")` is empty for DB-backed nodeids. Feasible and cheap; without it the central deliverable is unprotected. Non-vacuity itself remains a manual, uncommitted mutation.
2. **[minor — RESOLVED] SRD NFR-5 status is stale.** `.zj/SRD.md:707` still reads `**Status: planned**` with no note that 2a (harness repair, 4 root causes, 0-skip green) is complete and 2b (verify_* porting) is the remaining piece. Suggested fix: update the status line to reflect 2a done / 2b pending, citing this VERIFICATION.md.
3. **[minor — RESOLVED] `.zj/codebase/MAP.md` test/commands section is stale.** It lists only `pytest from backend/` (MAP.md:70) and does not mention the new dedicated `biznice_test` DB, the `TEST_POSTGRES_DB` knob, the required secrets, or the in-container run command that this phase established. Suggested fix: add the two run modes + env knobs (mirror `conftest.py:16-33`).

## Deferred (correctly out of scope for 2a — do NOT fail 2a)
- Porting `verify_*` crux assertions into pytest → Phase 2b (D-P2a-2). Concurrency mutation-proofs stay standalone.
- CI auto-run wiring of gates + the localhost-Postgres run mode exercised for real → Phase 3 / NFR-4.

## Pre-existing warnings (not introduced by 2a, informational)
- crumb_lead/crumb_opportunity FK cycle `SAWarning` at `conftest.py:263` (Base.metadata.sorted_tables) — cosmetic; truncate still works via CASCADE.
- Starlette `HTTP_422_UNPROCESSABLE_ENTITY` deprecation in `plum/router.py` and FastAPI routing — product-side, not harness.
