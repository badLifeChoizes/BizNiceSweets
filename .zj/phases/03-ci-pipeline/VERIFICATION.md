# Verification: Phase 03 — CI pipeline (GitHub Actions, NFR-4)
Date: 2026-07-24 | Commits: `4960d32..cf2a805` (work `6caf63a..cf2a805`, D-P3-4 in `3fd37ce`)
Verdict: PASS

Phase goal — every push/PR runs a blocking GitHub Actions pipeline executing all
lint / type-check / build / frontend-test / DB-backed pytest / service-layer `verify_*`
checks, red-blocks-merge — is **actually true now**. Confirmed both by inspecting the live
GitHub state (authed `gh` reached repo `badLifeChoizes/BizNiceSweets`) and by reproducing
every CI check locally against a fresh `postgres:17` container.

## Environment notes
- `gh` authed as `badLifeChoizes` (scopes incl. `repo`, `workflow`); all claimed run IDs,
  PR #4, and branch protection independently re-verified live — **not** taken on trust.
- `podman` available (`docker` absent). Spun a fresh throwaway `postgres:17-alpine` on
  `localhost:5432` with `POSTGRES_USER=app` and **no** `biznice_test` — so the D-P3-4
  self-provisioning path was genuinely exercised, not shortcut by a pre-existing DB.
- Local backend venv is Python 3.12.3 (CI uses 3.13); immaterial to the results below.

## Criteria

### SC1 — workflow triggers + all named checks present — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| `on: [push, pull_request]` | Y | Y | Y | `ci.yml:6-8` |
| 4 independent jobs, no `needs:` | Y | Y | Y | `frontend`/`backend-lint`/`backend-tests`/`verify-scripts`; grep shows no `needs:` — a failure never masks another |
| YAML valid | Y | — | Y | `yaml.safe_load` → YAML-OK |
| `ruff check .` from backend | Y | Y | Y | `ci.yml:45` + `working-directory: backend`; local `ruff check .` exit 0 |
| `npm run lint` / `tsc -b` / `vitest run` / `npm run build` | Y | Y | Y | `ci.yml:26-29`; all run locally exit 0 |
| `pytest` vs `postgres:17` service | Y | Y | Y | `ci.yml:54-89` |
| non-API `verify_*` glob excludes `*_api.py` | Y | Y | Y | `ci.yml:158-163` dynamic glob; `ls verify_*.py \| grep -v _api \| wc -l` = 14 |
| `frontend/.npmrc` legacy-peer-deps | Y | — | Y | `legacy-peer-deps=true` present |

### SC2 — clean tree, all jobs green on a real run — PASS
Run **30140504003** (`gh run view`): `backend-lint` ✓, `backend-tests` ✓ (2m38s),
`verify-scripts` ✓, `frontend` ✓. Independently reproduced every check locally green
(pytest 232, verify 14/14, FE lint/tsc/vitest/build all exit 0).

### SC3 — broken backend test turns red, then reverted — PASS
Run **30140642516**: `backend-tests` **X**, other three ✓. Log attributes failure to
`tests/test_harness_selfcheck.py::test_db_available_flag_true` (`assert True is False`),
`1 failed, 231 passed`. Revert run **30140733237**: all four ✓.

### SC4 — lint violation (ruff AND eslint) turns red, then reverted — PASS
Run **30140870255**: `backend-lint` **X** (`ruff check .` step failed) **and** `frontend`
**X**; `verify-scripts` ✓. Revert run **30140959653**: all four ✓. (Commits `e1a6ac8`
inject / `08e38ca` revert are in the local history too.)

### SC5 — DB-backed pytest, 0 silent skips, cruxes execute — PASS
CI log (run 30140504003, job 89632698191): `232 passed, 246 warnings` — **no "skipped"**
token → 0 skipped. Reproduced locally on the **fresh** container: `232 passed, 246
warnings in 198.41s`, exit 0. Fresh-DB provisioning confirmed empirically: `biznice_test`
was **absent** before the run and **present** mid-run (queried `pg_database`), proving the
D-P3-4 probe fix self-provisions. Ported cruxes ran: `test_ar_posting_ties_crux`,
`test_gl_posting_ties_crux`, `test_moving_average_service_crux` all in the pass set.
verify-scripts reproduced locally: created `biznice` → `alembic upgrade head` → `run_seeds`
→ 14/14 scripts exit 0.

### SC6 — real PR to master, checks required/blocking — PASS
`gh pr view 4`: base `master`, head `chore-ci-pipeline`, OPEN, `mergeable: MERGEABLE`,
`mergeStateStatus: CLEAN`. `gh pr checks 4`: all four checks `pass`. Branch protection
`required_status_checks.contexts` = `["frontend","backend-lint","backend-tests","verify-scripts"]`
(exact). The historical BLOCKED→CLEAN transition can't be time-travel-verified, but a CLEAN
state gated by four required contexts corroborates it.

### SC7 — reproducible installs — PASS
`frontend/.npmrc` `legacy-peer-deps=true`; `npm ci` step reads it automatically (`ci.yml:25`);
`frontend` job green on CI and `npm run lint`/build resolved locally. Backend jobs
`pip install -r requirements-dev.txt` (ruff) and `requirements.txt -r requirements-dev.txt`
(`ci.yml:44,88,135`); ruff + pytest ran clean.

## Product-code boundary — CLEAN
`git diff 4960d32..cf2a805 -- backend/app/ frontend/src/` is **empty**. Only non-doc/workflow
change is `backend/tests/conftest.py` (+7/-2, D-P3-4: probe → maintenance `postgres` DB),
which is the explicitly-authorized test-infra fix. No product code touched.

## Regression protection
| Criterion | Pinned by |
|---|---|
| SC1 shape (jobs/checks present) | The workflow itself; **no meta-test** asserts its shape — deleting a job silently drops that check (minor gap below) |
| SC2 all-green | `.github/workflows/ci.yml` re-runs on **every push/PR** — standing |
| SC3 broken-test → red | `backend-tests` job runs `pytest -q` every push; the one-time red demo is **not** re-enforced (no standing enforce-smoke — PLAN `## Noticed`) |
| SC4 lint → red | `backend-lint` + `frontend` jobs run every push; one-time demo **not** re-enforced (same) |
| SC5 232 passed | `backend-tests` job every push |
| SC5 **0 skipped** | **Unpinned** — pytest job doesn't fail on a future silent skip (minor gap below) |
| SC5 D-P3-4 fresh-provision | CI Postgres is **fresh each run**, so a probe regression fails `backend-tests` loud — that freshness *is* the protection; conftest change itself has no unit test |
| SC5 cruxes non-vacuity | `tests/test_harness_selfcheck.py` (Phase 2b) pins db-availability/non-vacuity |
| SC6 required checks | GitHub branch-protection config — not automatable in-repo; can drift silently (manual) |
| SC7 lockfile resolve | `frontend` job `npm ci` every push |

## Test suite (reproduced locally, this environment)
- `backend`: `ruff check .` → exit 0 ("All checks passed!").
- `backend` pytest vs fresh `postgres:17`: **232 passed, 0 skipped**, exit 0.
- `backend` verify loop (14 non-API): **14/14 exit 0**.
- `frontend`: `npm run lint` exit 0; `npx tsc -b` exit 0; `npx vitest run` 44 files / 131 tests pass; `npm run build` exit 0.

## Gaps
1. **(minor) No standing lint/test enforce-smoke.** SC3/SC4 red-behavior was a one-time
   manual push demo; nothing continuously proves the gates still fail on a violation.
   Already logged in PLAN `## Noticed` (backlog). Suggested: a self-restoring inject→expect-red→revert
   smoke, or accept as backlog.
2. **(minor) SC5 "0 skipped" is unenforced.** A future test that silently `skip`s would
   still leave `backend-tests` green. Suggested: add `-p no:cacheprovider --strict-markers`
   is orthogonal; the real fix is a skip guard (e.g. `pytest ... -rs` + a CI assertion on
   the summary, or `--co` count check). File: `.github/workflows/ci.yml` `backend-tests` step.
3. **(minor) No meta-test on `ci.yml` shape.** Removing a job/check from the workflow
   wouldn't fail anything — the pipeline just silently stops checking it. Inherent to CI;
   low priority.
4. **(trivial) Checklist not yet archived.** `docs/tasks/chore-ci-pipeline.md` all-ticked
   but not moved to `docs/tasks/_completed/` (task 8 defers archival to completion; expected
   post-verify). Node 20 deprecation annotations on the actions are cosmetic (PLAN `## Noticed`).

## Docs — accurate
SRD NFR-4 (line ~694) flipped to `done` with correct workflow path, four jobs, run IDs,
232/0, PR #4, and branch-protection contexts. `docs/features/requirements-progress.md` NFR-4
row (line 94) matches the delivered pipeline. No stale claims found.
