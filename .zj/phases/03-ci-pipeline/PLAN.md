# Plan: Phase 03 — CI pipeline (GitHub Actions)
Goal: Every push and PR to the BizNiceSweets repo runs a blocking GitHub Actions pipeline that executes all lint / type-check / build / frontend-test / DB-backed pytest / service-layer `verify_*` checks and reports red-blocks-merge.
Status: draft

## Success criteria
> From ROADMAP v4.0 Phase 3 (line 422) and SRD **NFR-4** (traces PRD-12). Cited inline per task.

- **SC1** — Committed `.github/workflows/ci.yml` triggers on `push` and `pull_request` and defines jobs running every named check: `ruff check .` (from `backend/`), `npm run lint`, `tsc -b`, `vitest run`, `npm run build`, `pytest` (against a `postgres:17` service), and the service-layer non-API `verify_*` scripts.
- **SC2** — On a pushed branch, every named job **executes** and a clean tree shows **all jobs green** on a real Actions run.
- **SC3** — A branch with a deliberately-broken backend test turns status **red** (pytest job fails), then reverted.
- **SC4** — A branch with a deliberately-introduced lint violation (ruff AND eslint) turns status **red**, then reverted.
- **SC5** — The pytest job runs DB-backed tests against live Postgres with **0 silent skips** (expected 232 passed / 0 skipped) and the Phase-2b ported cruxes execute.
- **SC6** — Pipeline **demonstrated on a real PR to `master`** showing status checks; checks configured as **required (blocking)** via branch protection.
- **SC7** — Reproducible installs: runner honors `frontend/.npmrc` (`legacy-peer-deps=true`) so `npm ci` resolves; `ruff` + backend dev deps installed for their jobs.

## Context
- **Repo:** `github.com/badLifeChoizes/BizNiceSweets`; `gh` authed as `badLifeChoizes`. No `.github/` exists yet. `origin/master` HEAD = v4.0 spec commit; v4.0 phase branches are local/unmerged. Phase 3 stacks on the 2b tip.
- **Branch base (D-P3):** cut `chore-ci-pipeline` from current `chore-port-verify-cruxes` HEAD (`4960d32`) so repaired harness + ported cruxes are present.
- **pytest is self-provisioning** (`backend/tests/conftest.py:145-207`): connects to maintenance `postgres` DB, `CREATE DATABASE "biznice_test"`, runs `alembic upgrade head` via a `sys.executable -m alembic` subprocess (cwd = backend). The Postgres **service just needs to exist** with the default `postgres` DB + matching creds. No pre-created test DB, no manual migration step for the pytest job.
- **conftest env contract:** reads `POSTGRES_HOST`/`POSTGRES_PORT`/`POSTGRES_PASSWORD`; force-sets `POSTGRES_DB=biznice_test`; requires `POSTGRES_PASSWORD`, `JWT_SECRET`, `BNS_ADMIN_PASSWORD` present (no no-DB skip mode — missing/unreachable DB fails loud).
- **Secrets are test-only throwaways** — set as plain `env:` in the workflow (JWT_SECRET ≥32 chars). No GitHub repo Secrets required.
- **Deps confirmed present:** `backend/requirements.txt` (fastapi, sqlalchemy 2.0.51, alembic 1.18.4, asyncpg, `psycopg2-binary` 2.9.12 — needed for the sync alembic URL `settings.database_url_sync`, `alembic/env.py:45`); `backend/requirements-dev.txt` (pytest 9.1.1, pytest-asyncio, httpx, ruff 0.15.18).
- **verify_* scripts:** 23 in `backend/scripts/`; 9 are `*_api.py` (need a booted uvicorn — **excluded**, D-P3-1). The 14 non-API scripts build their own async engine from `POSTGRES_*` (default DB `biznice`) and call service functions directly. **Confirmed by grep: none self-create the DB, run migrations, or `create_all`** — their headers say "Bring up + migrate the dev DB" as a precondition. So the verify job must create + migrate `biznice` before the loop (see Task 5 / DB-naming risk).
- **Version pins (MAP.md):** Node 22 (`setup-node@v4`), Python 3.13 (`setup-python@v5`). Frontend cmds from `frontend/`; backend lint `ruff check .` from `backend/`.
- **`frontend/.npmrc`** sets `legacy-peer-deps=true` (D-P1-1) — `npm ci` honors the project `.npmrc` automatically. **Watch item:** this is a *global* peer-mask, not a scoped override; a future dep bump can silently resolve an incompatible peer without erroring.

## Decisions
> All three owner decisions resolved at plan. IDs D-P3-1..3.

- **D-P3-1 — `verify_*` in CI = service-layer subset.** One CI job runs the 14 non-API `verify_*.py` scripts against the live Postgres service (they house the concurrency mutation-proofs per D-P2a-2). Exclude all `*_api.py` (they hit `http://localhost:8000`; their RBAC/audit behavior was ported into the pytest HTTP suite in Phase 2b, making them redundant). Exact list derived by globbing `backend/scripts/verify_*.py` and dropping `*_api.py`.
- **D-P3-2 — Backend runner = setup-python + pip + Postgres service** (not a built container image). `ubuntu-latest` + `actions/setup-python@v5` (3.13) + `pip install -r requirements.txt -r requirements-dev.txt`, with a `postgres:17` service mapped to `localhost:5432`. Matches conftest's documented localhost invocation; sidesteps in-container dep-install pain.
- **D-P3-3 — Full live demonstration + branch protection.** Push `chore-ci-pipeline` to origin, open a real PR → master, prove green + broken-test-red + broken-lint-red on real Actions runs, and configure branch protection so the CI checks are required/blocking. Owner-authorized outward push of the unmerged v4.0 stack's branch.

## Decisions needed
None — all resolved above.

## Tasks

### [ ] 0. Cut the Phase-3 branch and open the task checklist
- **Files:** git branch `chore-ci-pipeline`; `docs/tasks/chore-ci-pipeline.md`
- **Do:** From `chore-port-verify-cruxes` HEAD (`4960d32`), `git switch -c chore-ci-pipeline`. Create `docs/tasks/chore-ci-pipeline.md` with the checklist mirroring these tasks (per-branch checklist convention).
- **Done when:** `git branch --show-current` prints `chore-ci-pipeline`; the checklist file exists and lists tasks 1–8.
- **Verify:** `git branch --show-current && git log --oneline -1 && test -f docs/tasks/chore-ci-pipeline.md && echo OK`
- **Parallel-ok:** no (blocks all)

### [ ] 1. Author the `frontend` and `backend-lint` jobs of the workflow  (SC1, SC7)
- **Files:** `.github/workflows/ci.yml` (new)
- **Do:** Create the workflow with `on: [push, pull_request]`, `name: CI`, and a top-level `jobs:` map with `strategy.fail-fast: false` semantics achieved by keeping jobs independent (no `needs:`). Add:
  - **`frontend`** job: `runs-on: ubuntu-latest`; `actions/checkout@v4`; `actions/setup-node@v4` with `node-version: 22` and `cache: npm`, `cache-dependency-path: frontend/package-lock.json`; steps (all `working-directory: frontend`): `npm ci`, `npm run lint`, `npx tsc -b`, `npx vitest run`, `npm run build`. (`npm ci` reads `frontend/.npmrc` → `legacy-peer-deps=true` automatically — SC7.)
  - **`backend-lint`** job: `setup-python@v5` `python-version: 3.13`, `cache: pip`; install `backend/requirements-dev.txt` (ruff lives there); step `ruff check .` with `working-directory: backend`.
- **Done when:** `ci.yml` parses as valid YAML and both jobs are fully specified with real commands (no placeholders).
- **Verify:** `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo YAML-OK`; locally sanity-run the same commands: `cd frontend && npm ci && npm run lint && npx tsc -b && npx vitest run && npm run build`, `cd backend && ruff check .`
- **Parallel-ok:** no (creates the file tasks 2–3 edit)

### [ ] 2. Add the `backend-tests` job (pytest against live postgres:17)  (SC1, SC2, SC5)
- **Files:** `.github/workflows/ci.yml`
- **Do:** Add a `backend-tests` job: `setup-python@v5` 3.13 + `pip install -r backend/requirements.txt -r backend/requirements-dev.txt`. Declare a `services.postgres` = `postgres:17` with `env: POSTGRES_PASSWORD: <testpw>` (leave `POSTGRES_DB` unset so the default `postgres` maintenance DB exists — conftest needs it to CREATE `biznice_test`), `ports: 5432:5432`, and a health-check `options` (`pg_isready` interval/retries). Run step (`working-directory: backend`) `pytest -q` with job/step `env:` `POSTGRES_HOST: localhost`, `POSTGRES_PORT: 5432`, `POSTGRES_PASSWORD: <testpw>`, `JWT_SECRET: <≥32-char throwaway>`, `BNS_ADMIN_PASSWORD: <testpw>`. Do NOT set `POSTGRES_DB` (conftest force-sets `biznice_test`). No manual `alembic` step — conftest self-migrates.
- **Done when:** the job runs `pytest -q` against the service with the full env contract; no repo Secrets referenced.
- **Verify:** replicate locally against a throwaway postgres: `docker run -d --rm -e POSTGRES_PASSWORD=ci_test_pw -p 5432:5432 postgres:17` (or podman), then `cd backend && POSTGRES_HOST=localhost POSTGRES_PORT=5432 POSTGRES_PASSWORD=ci_test_pw JWT_SECRET=ci_test_jwt_secret_at_least_32_chars_long BNS_ADMIN_PASSWORD=ci_test_pw pytest -q` → expect **232 passed / 0 skipped**.
- **Parallel-ok:** no (same file as tasks 1, 3)

### [ ] 3. Add the `verify-scripts` job (14 non-API `verify_*` against migrated `biznice`)  (SC1, SC5)
- **Files:** `.github/workflows/ci.yml`
- **Do:** Add a `verify-scripts` job: same python/pip setup; `services.postgres` = `postgres:17` but this one **sets `env: POSTGRES_DB: biznice`** so the target DB is created at container init. Steps (`working-directory: backend`, with the same `POSTGRES_*`/`JWT_SECRET`/`BNS_ADMIN_PASSWORD` env, **plus `POSTGRES_DB: biznice`**):
  1. **Migrate:** `python -m alembic upgrade head` (alembic reads `settings.database_url_sync` from `POSTGRES_*`, `alembic/env.py:45` — hits `biznice` via psycopg2).
  2. **Run the subset:** a shell loop over the non-API scripts. Derive the list at author time by globbing and excluding `*_api.py` — the 14 are: `verify_ap.py verify_ar.py verify_gl.py verify_mousse.py verify_gelato.py verify_gelato_ship.py verify_inventory.py verify_purchasing.py verify_e2e_p8.py verify_crumb.py verify_crumb_so.py verify_reports.py verify_plum_vendor_paths.py verify_part_numbering.py`. Loop: `for s in <list>; do echo "== $s =="; python scripts/$s || exit 1; done` (fail-fast within the job so a red script blocks).
- **Done when:** job migrates `biznice` then runs exactly the 14 non-API scripts; each exits 0.
- **Verify:** `ls backend/scripts/verify_*.py | grep -v _api | wc -l` → 14 (list matches). Locally against a `POSTGRES_DB=biznice` service + `alembic upgrade head`, run the loop → all print PASS, exit 0. Confirm no `*_api.py` present in the loop.
- **Parallel-ok:** no (same file)

### [ ] 4. Commit the workflow and prove all jobs green on a pushed branch  (SC2)
- **Files:** `.github/workflows/ci.yml`; `docs/tasks/chore-ci-pipeline.md`
- **Do:** `git commit` the workflow (`ci: add GitHub Actions pipeline …`). `git push -u origin chore-ci-pipeline` (D-P3-3, owner-authorized). Watch the run with `gh run watch` / `gh run view`.
- **Done when:** the Actions run for the pushed HEAD shows all four jobs (`frontend`, `backend-lint`, `backend-tests`, `verify-scripts`) **green**; `backend-tests` log shows `232 passed` and `0 skipped` (SC5).
- **Verify:** `gh run list --branch chore-ci-pipeline --limit 1` (status = completed/success); `gh run view <id> --log | grep -E "passed|skipped"` shows 232 passed / 0 skipped.
- **Parallel-ok:** no (needs tasks 1–3)

### [ ] 5. Demonstrate red on a deliberately-broken backend test, then revert  (SC3)
- **Files:** a throwaway commit touching one existing test in `backend/tests/` (e.g. flip an assert); reverted after.
- **Do:** On a scratch commit on `chore-ci-pipeline` (or a child branch), introduce a guaranteed-failing assertion in one existing pytest test, push, confirm the `backend-tests` job goes **red** and the overall status is failing/blocking. Then `git revert`/reset the change and push so HEAD is green again. **No product-code change** — test-only, and reverted. (If a genuine product-code touch ever seems required to make a job pass → STOP and flag; infra-only phase.)
- **Done when:** one Actions run shows `backend-tests` red due to the injected failure; a subsequent run on the reverted HEAD is green.
- **Verify:** `gh run list --branch chore-ci-pipeline` shows the failing run then the passing run; `gh run view <failing-id>` attributes failure to the pytest job.
- **Parallel-ok:** no

### [ ] 6. Demonstrate red on a deliberately-introduced lint violation (ruff AND eslint), then revert  (SC4)
- **Files:** throwaway edits: one `backend/**.py` (ruff violation, e.g. unused import) and one `frontend/src/**.ts(x)` (eslint violation, e.g. `let` never reassigned / unused var); reverted after.
- **Do:** Introduce one ruff-detectable and one eslint-detectable violation, push, confirm `backend-lint` **and** `frontend` jobs go **red** (eslint runs `--max-warnings 0`). Revert both; confirm green.
- **Done when:** an Actions run shows both lint jobs red from the injected violations; the reverted HEAD run is green.
- **Verify:** `gh run view <failing-id> --log | grep -iE "ruff|eslint|error"`; final `gh run list` top entry = success.
- **Parallel-ok:** no

### [ ] 7. Open the PR to `master` and configure required-status branch protection  (SC6)
- **Files:** none in-repo (GitHub config via `gh`/API)
- **Do:** `gh pr create --base master --head chore-ci-pipeline` (title `ci: GitHub Actions CI pipeline (v4.0 Phase 3)`, body summarizing NFR-4 coverage + the green/red demos). Configure branch protection on `master` requiring the four status checks (`frontend`, `backend-lint`, `backend-tests`, `verify-scripts`) via `gh api -X PUT repos/badLifeChoizes/BizNiceSweets/branches/master/protection` with `required_status_checks.contexts` naming those job/check names (confirm exact check names from a completed run's `gh pr checks`). Confirm the PR shows the checks running and gating.
- **Done when:** the PR page shows all four checks green and merge is blocked until they pass; branch protection lists them as required.
- **Verify:** `gh pr checks <pr#>` lists the four checks with pass; `gh api repos/badLifeChoizes/BizNiceSweets/branches/master/protection --jq '.required_status_checks.contexts'` returns the four names.
- **Parallel-ok:** no

### [ ] 8. Close the phase: update NFR-4 status + requirements-progress  (SC1–SC7 recorded)
- **Files:** `.zj/SRD.md` (NFR-4 block ~line 694), `docs/features/requirements-progress.md`, `docs/tasks/chore-ci-pipeline.md`
- **Do:** Flip NFR-4 **Status: planned → done** with evidence (workflow path, PR #, run IDs for the green/red-test/red-lint demos, `232 passed / 0 skipped`, branch-protection confirmed). Add/update the NFR-4 row in `requirements-progress.md`. Tick the checklist; archive it to `docs/tasks/_completed/2026-07-24-chore-ci-pipeline.md` on completion.
- **Done when:** NFR-4 reads `done` with cited run/PR evidence; `requirements-progress.md` reflects it.
- **Verify:** `grep -n "NFR-4" .zj/SRD.md docs/features/requirements-progress.md` shows `done` + evidence; `git log --oneline` shows a `docs(zj):` closing commit.
- **Parallel-ok:** no

## Deviations
- **T0 (trivial):** Branch cut from the plan-carrying tip `8a27a46` (code-identical to `4960d32` + the
  Phase-3 plan doc) rather than the bare `4960d32`, so `PLAN.md` is present on the build branch — same
  pattern as phases 2a/2b Task 0.
- **T2 (MATERIAL → owner, D-P3-4):** The plan's core assumption — "pytest is self-provisioning; the
  Postgres service just needs to exist" — was wrong on a *fresh* server. conftest's reachability probe
  (`_check_db_available`) connected to `biznice_test`, which does not exist until `_provision_test_database`
  creates it, so on the always-empty CI `postgres:17` service the probe returned False and aborted the
  session before provisioning. The 2a/2b "232 passed" runs only worked because `biznice_test` persisted
  from earlier local sessions. **Fix (owner-chosen):** point the probe at the maintenance `postgres` DB
  (test-infra only, `backend/tests/conftest.py`; no product-code change). Verified: fresh `postgres:17`
  self-provisions → 232 passed / 0 skipped / exit 0. Recorded as D-P3-4.
- **T2 (trivial):** The plan's backend-tests service config (and its local-verify command) omitted
  `POSTGRES_USER: app`; conftest connects as role `app` (config default), so the `postgres:17` service must
  create that role. Added `POSTGRES_USER: app` to the service env (image also makes an `app` DB; the
  `postgres` maintenance DB still exists for the CREATE step). Same correction applies to the T3
  verify-scripts service.

- **T3 (build correction, no owner call — obvious required steps the plan omitted):** The plan claimed the
  non-API `verify_*` scripts need only a "pre-migrated `biznice`". Running them against a migrated-only DB
  surfaced two missing preconditions (the plan's local-verify was evidently never executed): (1) the scripts
  do `from app...` and need the backend root importable — their own docstrings run them with `PYTHONPATH=/app`;
  added `PYTHONPATH: ${{ github.workspace }}/backend` to the job env. (2) They assume the reference seeds the
  app runs at lifespan startup (notably the GL Chart of Accounts — "GL account 5100 not seeded" otherwise);
  alembic migrates schema only. Added a seed step that calls `app.core.seed.run_seeds` exactly as
  `app.main`'s lifespan does, after migrate and before the loop. Also switched the loop from a hardcoded
  14-name list to a dynamic `scripts/verify_*.py` glob excluding `*_api.py` (maintenance-proof). Verified on a
  fresh `postgres:17` (`POSTGRES_DB=biznice`): migrate → seed → 14/14 scripts exit 0.

## Risks
- **DB-naming collision (the one real integration risk) — RESOLVED by job isolation.** pytest wants a maintenance `postgres` DB and self-creates/migrates `biznice_test`; the non-API `verify_*` scripts assume a pre-existing, already-migrated `biznice` and do **not** self-create or migrate (confirmed: no `create_all`/`CREATE DATABASE`/`alembic` in the scripts). Resolution: put them in **separate jobs, each with its own `postgres:17` service** — `backend-tests` leaves `POSTGRES_DB` unset (default `postgres` present → conftest makes `biznice_test`); `verify-scripts` sets the service `POSTGRES_DB: biznice` and runs `alembic upgrade head` before the loop. No shared container, no collision. **Early-warning sign:** a verify script erroring with `relation "…" does not exist` or `database "biznice" does not exist` = the migrate step or service `POSTGRES_DB` env is missing.
- **Exact check names for branch protection** aren't known until a run completes — Task 7 reads them from `gh pr checks` before PUTting protection, rather than guessing. Sign of trouble: protection PUT accepted but PR still mergeable → context name mismatch.
- **`legacy-peer-deps` peer-masking (D-P1-1)** can hide an incompatible transitive peer so `npm ci` "resolves" a broken tree. Not blocking this phase (lockfile is pinned), but a green `npm ci` is not proof of peer sanity on future bumps — noted for Phase 4+.
- **Postgres service readiness race** — pytest/alembic can connect before Postgres is ready. Mitigated by the service `health-cmd`/`pg_isready` options; sign of trouble = intermittent connection-refused on `backend-tests`.

## Noticed  (Phase-3 build)
- **Node 20 deprecation warning (p3, non-blocking):** the runs annotate that `actions/checkout@v4`,
  `actions/setup-python@v5`, `actions/setup-node@v4` target Node 20 (force-run on Node 24 by GitHub);
  a future bump to the `@v5`/latest action majors clears the warning. Cosmetic — all jobs pass green.

## Noticed  (Phase-1/2a homed items — not blocking, for backlog)
- **Standing automated lint enforce-smoke** (p3): SC4 here is a one-time manual demo; a permanent, self-restoring "inject → expect red → revert" smoke is a future nicety, not built this phase.
- **Back-to-back pytest rerun step** (p3): a second `pytest` invocation to catch order/state leakage — deferred.
- **Committed non-vacuity** already pinned by `backend/tests/.../test_harness_selfcheck.py` (Phase 2b) — no action.
- **Dependency caching** (`setup-node cache: npm`, `setup-python cache: pip`) folded into tasks 1–3 as a nice-to-have; drop if it complicates a first green run.

## Out of scope
- Any change to product code (`backend/app/`, `frontend/src/`) — infra-only; a needed product-code touch is a STOP-and-flag.
- Running the 9 `*_api.py` verify scripts in CI (D-P3-1 — need a booted uvicorn; behavior ported to pytest HTTP tests in 2b).
- Building/publishing container images, deploy pipelines, coverage gates, matrix builds across OS/versions — not in NFR-4.
- Merging the PR to master and the rest of the v4.0 stack (Phases 4–8) — Phase 3 delivers the pipeline + a demonstrated, blocking PR, not the merge.
