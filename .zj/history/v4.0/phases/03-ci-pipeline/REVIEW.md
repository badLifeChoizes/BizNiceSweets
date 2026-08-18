# Review: Phase 3 — CI pipeline (`.github/workflows/ci.yml` + conftest D-P3-4), `4960d32..cf2a805`
Date: 2026-07-24

## Verdict

Clean. No blockers, no majors, no minors. The gate is genuine — every check
can fail the build, no check runs vacuously, and the branch-protection contexts
align with the reported check names.

## What I verified (and why each concern is not a finding)

**Gating semantics — all four jobs block, nothing swallows a failure.**
- No `continue-on-error`, `|| true`, or `if:` anywhere in the workflow.
- `frontend` (ci.yml:26-29): `npm run lint` is `eslint . --report-unused-disable-directives --max-warnings 0` (frontend/package.json), `tsc -b`, `vitest run`, `npm run build` — each exits non-zero on failure. `vitest run` has no `passWithNoTests`, so an empty/uncollected suite exits 1 (not a silent green).
- `backend-lint` (45): `ruff check .` exits non-zero on violations — already proven CI-red in commit ff638cc.
- `verify-scripts` loop (155-164): step shell is bash with `set -e` (plus Actions' default `-eo pipefail`); `python "$s"` is not in a pipe/subshell, so a non-zero script exit aborts the loop and fails the step. The 14 target scripts all `sys.exit(main())` with `main()` returning 1 on assertion failure (e.g. verify_inventory.py:350-360, verify_e2e_p8 exits non-zero on FAIL). An unmatched glob would pass the literal path to `python` and still error out — no vacuous-green path.

**Check-name / branch-protection alignment — the classic footgun is avoided.**
Job keys `frontend`, `backend-lint`, `backend-tests`, `verify-scripts` each set an explicit `name:` equal to the key, so GitHub reports exactly those four contexts, matching the branch-protection set `[frontend, backend-lint, backend-tests, verify-scripts]`. No matrix, no workflow-name prefix. Both `on: push` and `on: pull_request` fire on the PR head SHA, so the required contexts do report on the PR.

**Service / DB env contract — matches conftest, alembic, and the scripts.**
- config default `postgres_user="app"`, `postgres_db="biznice"` (config.py:20-23). All three DB jobs run the service as `POSTGRES_USER: app`, so alembic, seeds, conftest, and the scripts all authenticate correctly.
- `backend-tests` deliberately omits `POSTGRES_DB` so the image keeps a default DB and the maintenance `postgres` DB exists; conftest force-sets `biznice_test` and self-provisions it (create + `alembic upgrade head`). `psycopg2-binary` and `alembic` are both in requirements.txt, so the conftest probe and provisioning import cleanly.
- `verify-scripts` sets `POSTGRES_DB: biznice`, migrates it (`python -m alembic upgrade head`), then runs `run_seeds` before the loop; the scripts read `POSTGRES_*` (default user `app`, db `biznice`) and self-seed what they additionally need. `PYTHONPATH: ${{ github.workspace }}/backend` makes `app.*` importable for the bare `python scripts/verify_*.py` invocations.

**Postgres readiness — no race.** Both DB services declare `--health-cmd "pg_isready -U app"` with retries; Actions blocks job steps until the service is healthy. `pg_isready` reports the server up even when the probed DB name doesn't yet exist, so the health gate is robust across both job configs.

**Script glob — captures exactly the 14 intended non-API scripts.** `scripts/verify_*.py` = 23 files; `case *_api.py) continue` excludes the 9 `*_api.py`, leaving the 14 service-level scripts (including `verify_e2e_p8.py`, which builds its own engine and drives services directly — no uvicorn needed). A future `verify_foo.py` is auto-picked-up (good); a rename to `verify_foo_api.py` would silently drop it, but that is inherent to the intended API/non-API split, not a defect in this diff.

**Secrets — test-only throwaways, no real credential exposed.** `POSTGRES_PASSWORD`/`BNS_ADMIN_PASSWORD` = `ci_test_pw`; `JWT_SECRET` = `ci_test_jwt_secret_at_least_32_chars_long` (41 chars ≥ 32). No GitHub repo Secrets referenced; nothing resembles a live credential.

**conftest D-P3-4 change — correct, and does not weaken local runs.** Repointing the reachability probe from `settings.postgres_db` to the always-present `postgres` maintenance DB (conftest.py:119-124) only governs the loud-abort reachability gate. Provisioning still connects to `postgres` to `CREATE DATABASE` the test DB (idempotent: guarded by a `pg_database` existence check, conftest.py:200-205) and migrates it. If the test DB were genuinely unusable (e.g. missing CREATEDB privilege, or first real query fails), the `CREATE DATABASE`, the alembic subprocess (`check=True`), or the first NullPool query fails loudly — the change cannot convert a "test DB unreachable" condition into a silent skip or a run against the wrong DB. On local runs where `biznice_test` persists, behavior is unchanged.

## Questions

None outstanding.
