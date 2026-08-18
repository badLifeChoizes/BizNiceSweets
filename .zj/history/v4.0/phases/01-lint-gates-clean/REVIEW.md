# Review: Phase 1 — Lint gates fixed-to-clean (`origin/master..HEAD`, `chore-lint-gates-clean`)
Date: 2026-07-21

## Verdict

**Clean.** No blockers, majors, or minors. Every hazard class flagged for this phase was
audited against the actual code (not just the diff) and independently verified to be
behavior-preserving. Both gates were run and pass.

## What was verified (evidence)

- **F401 side-effect imports (highest risk) — SAFE.** Compared the full set of `import`
  statements before/after in every load-bearing file (`app/core/models.py`, `app/main.py`,
  `app/core/seed.py`, `app/modules/syerp/service/__init__.py`, `app/core/registry.py`): the
  import sets are **identical** — the autofix only reordered (I001), it removed nothing. All
  `# noqa: F401` guards on the module-registration / metadata imports survived and sit on the
  correct lines. The 51 re-exports in `syerp/service/__init__.py` are intact.
  Independent proof: `POSTGRES_PASSWORD=x JWT_SECRET=x BNS_ADMIN_PASSWORD=x python -c "import
  app.main"` imports the whole graph cleanly and `Base.metadata.sorted_tables` resolves all
  **46 tables** (the `crumb_lead↔crumb_opportunity` cycle warning is pre-existing, unrelated).
  Net per-file `import`-line "removals" were all reformats (e.g. `from datetime import date,
  datetime, timezone` → `date, datetime` after UP017 `datetime.UTC`), not symbol loss. Spot-
  checked the one scary case — `syerp/service/reports.py` dropping `from fastapi import
  HTTPException, status`: `HTTPException` has zero references and every `status` hit is a
  `.status` column, so both were genuinely unused.

- **F821 (`ImportPreviewResponse`/`ImportCommitResponse` in `plum/service.py`; `PaymentRead`
  in `syerp/service/bills.py`) — SAFE.** Both files carry `from __future__ import annotations`
  (plum:58, bills:2), so annotations are strings and never evaluated at runtime — no NameError
  risk. All three schemas exist (`plum/schemas.py:461,476`, `syerp/schemas.py:894`) and are
  still runtime-imported inside the function bodies that construct them (plum:2669,2802;
  bills:780,938). The TYPE_CHECKING additions resolve the annotation for ruff/type-checkers
  only. Return types are honest.

- **F811 `seeded_db` fixture move — SAFE.** Exactly one definition exists
  (`tests/auth/conftest_helpers.py:52`), function-scoped (`@pytest.fixture`, no `scope=`), now
  re-exported once via the new `tests/auth/conftest.py`. No competing/local `seeded_db` in any
  other test file, so no collision and no scope change — per-test DB isolation is preserved.

- **E741 / F841 — SAFE.** `l`→`line` rename is complete (no stray `\bl\b` remains in
  `verify_crumb.py`; comprehension-scoped in both sites). Removed bindings `draft_bill`
  (`verify_reports.py`) and `user_data` (`test_modules.py`) have **no later references**, and
  the side-effectful `await`-RHS was retained in both cases (only the unused binding dropped).

- **UP035 `AsyncGenerator`** moved `typing`→`collections.abc` in `main.py` — runtime-equivalent
  on py3.13 (venv here is 3.12; `datetime.UTC` from UP017 also fine, added in 3.11).

- **Frontend — SAFE.** `useVisibleModules`→`getVisibleModules` rename is complete (no stray
  refs; all 3 call sites + test comment updated). The 4 removed `react-hooks/exhaustive-deps`
  disable comments did **not** touch any deps array — runtime effect timing is unchanged — and
  they were genuinely stale (effects reference only listed deps + stable setState setters /
  module-level fns), so `--report-unused-disable-directives` correctly required their removal;
  the 2 disables that are still needed survive (`PartnerSheet.tsx`, `NewRevisionDialog.tsx`).
  New flat config is a strict **superset** of the deleted `.eslintrc.cjs` rules (adds
  react-hooks + react-refresh; preserves the `^_` unused-vars tweak) — no enforced rule
  dropped. `@testing-library/dom@10.4.1` re-declared and installed.
  Ran both gates: **`npm run lint` → exit 0**, **`tsc -b` → exit 0**, and backend
  **`ruff check .` → All checks passed!**

## Questions / notes (not defects)

- `frontend/.npmrc` `legacy-peer-deps=true` is global and masks peer-dependency conflicts for
  every `npm install`/`npm ci`, not just the react-hooks-v5/eslint-10 pair it was added for
  (D-P1-1). Proven harmless here (lint runs under react-hooks 5.2.0 + eslint 10), but it means
  a future genuinely-incompatible dep bump won't surface at install time in CI. Worth a
  one-line CI note; not a blocker for this phase.
