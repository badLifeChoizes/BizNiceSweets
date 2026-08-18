# Task: chore-lint-gates-clean (v4.0 Phase 1 — NFR-6)

Both static-analysis lint gates (frontend ESLint 10 flat, backend ruff) run, pass clean on a
zero-violation baseline, and are proven enforcing — with zero runtime regression.

Plan: `.zj/phases/01-lint-gates-clean/PLAN.md`. Scope bound by D-M4-3 (fix-to-clean),
recommended-sets-only, lint-check-only.

## Conventions recorded
- **Backend lint convention:** run `ruff check .` from `backend/` (dev venv ruff at
  `backend/.venv/bin/ruff`, pinned `0.15.18` in `requirements-dev.txt`). Container-image ruff
  is Phase 3/CI's concern, out of scope here.
- **Frontend lint:** `npm run lint` from `frontend/`.

## Checklist

- [x] 0. Branch off master (via plan-carrying tip) and open this checklist
- [x] 1. Add the three missing ESLint flat-config devDependencies (Wave A)
- [x] 2. Write `frontend/eslint.config.js` flat config (Wave A)
- [x] 3. Fix the `lint` script and delete legacy `.eslintrc.cjs` (Wave A)
- [x] 4. Run `npm run lint` and fix every surfaced FE violation to zero (Wave A)
- [x] 5. Ensure ruff availability + document the invocation convention (Wave B)
- [x] 6. Audit and protect load-bearing side-effect imports BEFORE auto-fix (Wave B)
- [x] 7. Apply safe ruff auto-fixes, review F401 removal diff, enumerate remaining set (Wave B)
- [x] 8. Inspect and resolve the 4 F821 undefined-name annotations (Wave B)
- [x] 9. Resolve remaining hand-inspect items: F811, E741, F841 (Wave B)
- [x] 9b. Resolve UP035 deprecated-imports and the 2 unsafe fixes (Wave B)
- [x] 10. Prove no regression across the full behavioral safety net (Wave C)
- [x] 11. Demonstrate both gates are enforcing (red→green proof) (Wave C)
- [x] 12. Update requirements-progress, flip NFR-6 status, final commit (Wave C)

## Notes / evidence
(filled in per task)

### Task 10 — no-regression gate (Wave C, coordinator-run) — all green
Dev stack up (`podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d`), api mounts
`../backend:/app` so it runs the autofixed source live.
- **Cold boot (2 ways):** freshly-started api container → `GET /health/ready` = **200** (liveness+DB);
  explicit `podman exec compose_api_1 python -c "import app.main; print('BOOT_OK')"` → **BOOT_OK**.
  This is the empirical guard for a stripped side-effect import / UP-rewrite import target — PASS.
- **23/23 `verify_*.py` in-container exit 0** (loop over `backend/scripts/verify_*.py`, `pass=23 fail=0`).
  Spot-checked real assertions ran: `verify_ar.py` (both FOR-UPDATE concurrency locks, aging↔1120 tie),
  `verify_gelato_ship.py` (COGS control↔subledger tie, double-ship blocker regression),
  `verify_reports.py` (accounting identity — this file was touched by Task 9's F841 fix).
- **Vitest: 44 files / 131 tests passed.**
- **Build: `tsc -b && vite build` exit 0** (pre-existing informational chunk-size >500kB warning only).

### Task 11 — gates proven enforcing (red→green) — both PASS
Used throwaway probe files (clean deletion = guaranteed revert; working tree confirmed clean after).
- **Frontend:** planted `frontend/src/__lint_probe__.ts` with an unused non-`_` var →
  `npm run lint` **exit=1** (`@typescript-eslint/no-unused-vars` error, `✖ 1 problem`); removed probe →
  `npm run lint` **exit=0**.
- **Backend:** planted `backend/scripts/__ruff_probe__.py` with an unused `import os` →
  `.venv/bin/ruff check .` **exit=1** (`F401 ... 'os' imported but unused`, `Found 1 error.`); removed
  probe → `.venv/bin/ruff check .` **exit=0** (`All checks passed!`).
- `git status --porcelain` empty afterward (no scratch left behind).

### Task 12 — docs + NFR-6 status flip — DONE
- `.zj/SRD.md` NFR-6: `Status: planned` → `implemented (v4.0 Phase 1 — both gates fixed-to-clean +
  enforcing; CI-wiring clause pending NFR-4/Phase 3)`; added a Phase-1 Evidence line. Not `verified`
  (that is `/zj:verify 1`'s call — this is the build stage).
- `docs/features/requirements-progress.md`: added a new **Infrastructure / Non-Functional (PRD-12,
  v4.0)** section with the NFR-6 row (evidence + commit hashes) + refreshed the footer.
- `CHANGELOG.md` NOT edited (generated from commits, per repo rule).
- Checklist archived to `docs/tasks/_completed/2026-07-21-chore-lint-gates-clean.md`.

**Phase 1 complete — all 13 tasks (0–12) done. Next: `/zj:verify 1`.**

### Task 5 — ruff availability + invocation convention
- `cd backend && .venv/bin/ruff --version` → `ruff 0.15.18` (matches `requirements-dev.txt`
  pin `ruff==0.15.18`); no `pip install` needed, dev venv already had it.
- No `backend/README.md` exists — convention stays in this checklist ("Conventions recorded"
  above): run `ruff check .` from `backend/`; container-image ruff is Phase 3/CI's concern.
- Did NOT add a Makefile (per plan).

### Task 6 — side-effect import audit (protected-import list)
Verify: `ruff check app/core/models.py app/main.py app/modules/*/__init__.py app/core/seed.py
--select F401` → **All checks passed! (F401_exit=0)** — every side-effect import below is
already referenced or `# noqa: F401`-guarded; Task 7's `--fix` must not strip these.

**Protected imports (side-effect, `# noqa: F401`-guarded — do NOT let autofix remove):**
- `app/core/models.py` — model-metadata aggregator, all guarded:
  `syerp models` (:15), `auth models` (:18), `Module` (:21), `Setting` (:22),
  `plum models` (:27), `mousse models` (:29), `crumb models` (:30), `gelato models` (:31)
  (flan/crisp lines are commented out).
- `app/modules/<x>/__init__.py` (auth, crumb, gelato, mousse, plum, syerp) — each
  `from app.modules.<x>.router import router  # noqa: F401` (self-registration surface);
  the `registry` import is USED (`registry.register(...)`), `sys` USED.
- `app/main.py` — module registration is **string-based** `importlib.import_module(...)`
  (not `import x`), so ruff cannot flag F401; top-level imports all used; :~107 `# noqa: E402`.
- `app/core/seed.py` — seed fn imports (`seed_admin_user`, `seed_modules_table`,
  `seed_default_settings`, `seed_gl_accounts`, `seed_default_location`, `seed_plum_data`) are
  **function-local and all called** (used, not F401-susceptible); `TYPE_CHECKING` guard used.
- No OTHER unguarded side-effect import found in seed/registry wiring.

### Task 7 — safe autofix + remaining-set enumeration + ownership map
**BEFORE (`ruff check . --statistics`):** 1159 errors, 1088 fixable —
`F401 419 · UP045 270 · UP037 252 · I001 101 · UP017 66 · UP035 23 · F811 10 ·
UP006 8 · F821 4 · E741 2 · F841 2 · UP043 2`.

**`ruff check . --fix` (SAFE only, no `--unsafe-fixes`):** `1139 fixed, 68 remaining`
(cascade fixes exceed the 1088 headline as reformatted lines re-qualify).

**Deleted-import review (guards SC5 — no side-effect import stripped):**
- `git diff | grep '^-.*# noqa: F401'` net-removed check → **0 net removals**; the guarded
  `models.py` lines appeared as `-`/`+` only from I001 re-sort (all 8 active guards still
  present, verified by grep). All 6 `app/modules/*/__init__.py` router guards survive.
- Genuine F401 removals (`pytest`, `PutawayRequest`, `gl_service` alias, stray `re`/`uuid`
  etc.) confirmed unused — safe.

**AFTER safe `--fix` (`--statistics`):** 68 errors →
`F401 51 · F811 9 · F821 4 · E741 2 · F841 2`. UP035 → **0** (safe `--fix` resolved all 23,
contra plan estimate — no manual UP035 work left for 9b). 2 hidden unsafe fixes remain,
both **F841** (== the 2 F841 items below; `--statistics --unsafe-fixes` shows only F841 `[*]`).

**The 51 F401 — LOAD-BEARING re-exports (resolved in THIS task, not deferred):** all 51 are
in `app/modules/syerp/service/__init__.py` — the private `_`-prefixed helpers imported but
absent from `__all__` (ruff treats `__init__` imports as used only if in `__all__`). The
service-split refactor (`chore-syerp-service-split`) deliberately re-exports the *full*
surface; these private names ARE imported *from the aggregator package* by
`app/modules/mousse/service.py`, `app/modules/gelato/service/shipments.py`,
`tests/syerp/test_inventory.py`, `test_gl_journal.py`, `test_ap.py`, `test_purchasing.py`.
Removing them would break those imports. Fix = `# noqa: F401` on each of the 51 re-export
lines (codebase's existing re-export convention, cf. `models.py`); `__all__` stays the true
public surface (private names NOT promoted into it). `ruff check . --select F401` → **0**.

**Remaining set after this task (17) → OWNERSHIP MAP (every category owned; none rely on a
Task-9 backstop alone):**
- `F401 51` → **Task 7** (this task — load-bearing re-export `# noqa`, resolved → 0)
- `UP035 23→0` → **Task 7** safe `--fix` (resolved → 0; Task 9b now only *verifies* UP035=0)
- `F821 4` → **Task 8**
- `F811 9` → **Task 9**
- `E741 2` → **Task 9**
- `F841 2` → **Task 9** (these two == the "2 hidden unsafe fixes" Task 9b referenced;
  hand-fixed under Task 9 to satisfy its own `--select F811,E741,F841` verify. Task 9b's
  substantive queue is thus empty post-Task-9 → 9b is the whole-tree `exit=0` backstop.)

### Task 8 — 4 F821 undefined-name annotations (NOT runtime bugs)
Sites (re-located by symbol post-Task-7): `plum/service.py:2650` (`-> ImportPreviewResponse`)
+ `:2775` (`-> ImportCommitResponse`); `syerp/service/bills.py:739` + `:926` (`PaymentRead`).
- **Root cause:** each function imports its response schema *inside the function body*
  (`plum/service.py:2667,2800`; `bills.py:779,937`), so the name is absent from module scope
  when the `-> Name` return annotation is evaluated at definition time → F821. Both files
  already carry `from __future__ import annotations` — which does NOT suppress F821 (ruff
  still requires the name be resolvable).
- **Verified NOT a runtime bug** (no escalation): all three schemas exist —
  `plum/schemas.py:461 ImportPreviewResponse`, `:476 ImportCommitResponse`,
  `syerp/schemas.py:894 PaymentRead` — and are runtime-imported in the bodies that build them.
- **Fix (plan-preferred TYPE_CHECKING form):** added each schema to the file's existing
  `if TYPE_CHECKING:` schema import block (`plum/service.py:71-83`, `bills.py:20-25`),
  preserving alphabetical order. Resolves F821 for ruff + type-checkers; the function-body
  runtime imports still construct the objects; no F401 (TYPE_CHECKING import used in an
  annotation is "used") and no circular-import risk (block not evaluated at runtime).
- Verify: `ruff check . --select F821` → **All checks passed! (exit=0)**.

### Task 9 — F811 (9) + E741 (2) + F841 (2)
(`partners.py` duplicate `func` F811 was already auto-fixed in Task 7 → 9 F811 remained.)
- **E741 (2)** — ambiguous loop var `l` in f-string list comprehensions: `verify_crumb.py:590`
  (`for l in ft_detail.lines`) + `verify_reports.py:536` (`for l in bs_3130`). Renamed
  `l`→`line` (descriptive; both iterate document lines). Behavior-neutral.
- **F841 (2)** — these ARE the "2 hidden unsafe fixes" (`--statistics --unsafe-fixes` showed
  only F841 `[*]`). Both RHS are **side-effectful `await`s**, so the unsafe autofix (delete the
  whole statement) would drop needed work — hand-fixed instead by dropping only the unused
  binding, keeping the call: `verify_reports.py:373` `draft_bill = await make_expense_bill(...)`
  → `await make_expense_bill(...)` (creates the DRAFT bill the next assertion checks does NOT
  appear); `tests/core/test_modules.py:138` `user_data = await create_regular_user(...)`
  → `await create_regular_user(...)` (creates the non-admin the test then logs in as).
- **F811 (9× `seeded_db` in `tests/auth/test_seed_admin.py`)** — NOT duplicate fixture defs.
  One fixture (`seeded_db`, defined in `conftest_helpers.py:52`) was imported at module level
  (line 15, `# noqa: F401`) so pytest could discover it; ruff flagged each of the 9 test
  `def …(seeded_db)` params as redefining that import. Minimal semantics-preserving refactor:
  created `tests/auth/conftest.py` re-exporting `seeded_db` (idiomatic pytest fixture sharing,
  mirroring `tests/core/conftest.py:16`'s `admin_login_token` re-export) and removed the
  module-level import from `test_seed_admin.py`. Fixture now auto-discovered → params reference
  it directly, no shadowing → F811 gone; also clears the line-15 F401. `skip_if_no_db` (the
  fixture's dep) resolves from root `tests/conftest.py:97`. Test behavior unchanged.
- Verify: `ruff check . --select F811,E741,F841` → **All checks passed! (exit=0)**;
  whole-tree `ruff check .` → **exit=0** already at this point.

### Task 9b — UP035 + 2 unsafe fixes (queue cleared by Tasks 7 & 9)
- **UP035 (23):** safe `ruff check . --fix` in Task 7 already rewrote all 23 deprecated
  imports (`typing.List`/`Sequence`/`Mapping`/`Iterable` → `collections.abc`, etc.); no
  manual/`--unsafe-fixes` UP035 work remained. `ruff check . --select UP035` → **exit=0**.
- **2 hidden unsafe fixes:** both were **F841** (`--statistics --unsafe-fixes` showed only
  F841 `[*]`) — the `draft_bill` + `user_data` pair, hand-fixed under Task 9 (dropped the
  unused binding, kept the side-effectful `await` — the correct behavior-preserving fix the
  blind unsafe autofix would have gotten wrong). No `--unsafe-fixes` was ever applied.
- This task therefore carried **no new code change** — it is the whole-tree backstop.
- **Verify:** `ruff check . --select UP035` → `up035=0`; `ruff check .` → **All checks
  passed! (exit=0)** — the SC3 backend gate is clean on a zero-violation baseline.
- **Cold-boot sanity (per coordinator note):** local `import app.main` initially failed on
  missing required secrets (no `.env`; `POSTGRES_PASSWORD`/`JWT_SECRET`/`BNS_ADMIN_PASSWORD`
  have no defaults — expected 12-factor behavior, NOT an import error). With dummy secrets:
  `POSTGRES_PASSWORD=dummy JWT_SECRET=dummy BNS_ADMIN_PASSWORD=dummy python -c "import
  app.main; print('BOOT_OK')"` → **BOOT_OK**. Also confirmed the 51 syerp-service re-exports
  (public + private) import cleanly. No side-effect import was stripped. (In-container 23/23
  cold-boot is Wave C / Task 10.)

### Task 1 — add eslint flat-config devDependencies
- `npm install -D @eslint/js eslint-plugin-react-hooks eslint-plugin-react-refresh` → added:
  `@eslint/js@^10.0.1`, `eslint-plugin-react-hooks@^7.1.1`, `eslint-plugin-react-refresh@^0.5.3`.
- `eslint` stayed `10.5.0`, `typescript-eslint` stayed `8.62.0` (verified via `require('.../package.json').version`).
- Lockfile diff: +469/-3; the 3 removals are only `"peer": true` flags flipping now that these
  are direct deps — no version churn.
- Verify: `node -e "require('@eslint/js');require('eslint-plugin-react-hooks');require('eslint-plugin-react-refresh')"` → `exit=0`.
- **AMENDED (D-P1-1):** Task 1 originally landed `eslint-plugin-react-hooks@^7.1.1` (npm's auto-pick,
  whose `recommended` is the full React-Compiler ruleset). Per owner decision D-P1-1, re-pinned to
  `^5.2.0` (its `recommended`/`recommended-latest` == classic `rules-of-hooks`+`exhaustive-deps`).
  v5.2.0 peer-declares `eslint` only up to `^9`, so the install needed `--legacy-peer-deps` (the rules
  are eslint-version-agnostic; ESLint 10 works). Unmet-peer implication for a future `npm ci`/CI flagged
  to coordinator (no CI exists yet — BACKLOG p1). `eslint.config.js` switched
  `reactHooks.configs.flat.recommended` (v7-only) → `reactHooks.configs['recommended-latest']` (v5's
  flat export; v5 `configs.recommended` is legacy eslintrc format and errors under flat config).
- **Regression + fix from the `--legacy-peer-deps` install:** that flag made npm prune npm-7's
  auto-installed peer subtree — notably `@testing-library/dom@10.4.1` (peer of `@testing-library/react`)
  — which broke all 44 Vitest files (`Cannot find module '@testing-library/dom'`). Restored by declaring
  `@testing-library/dom@^10.4.1` as an explicit devDependency and adding `frontend/.npmrc`
  (`legacy-peer-deps=true`) so `npm install`/`npm ci` are reproducible and don't re-prune. The `@babel/core`
  toolchain + `browserslist` were also dropped but are genuinely unused (Vite 8 uses rolldown; Vitest its
  own transform) — tests + build are green without them. `zod`/`zod-validation-error` were react-hooks-**v7**
  deps (React-Compiler runtime); their removal is correct.

### Task 2 — flat `eslint.config.js`
- New `frontend/eslint.config.js` (ESM `export default tseslint.config(...)`): `ignores: ['dist','coverage']`,
  `files: ['**/*.{ts,tsx}']`, extends `js.configs.recommended` + `tseslint.configs.recommended` +
  `reactHooks.configs.flat.recommended` + `reactRefresh.configs.vite`, plus the preserved
  `@typescript-eslint/no-unused-vars: ['error', { argsIgnorePattern: '^_' }]` override (matches the legacy
  `.eslintrc.cjs` verbatim). No `recommendedTypeChecked`; no formatter step.
- `--print-config src/App.tsx` resolved: `react-hooks/rules-of-hooks`=`[2]`,
  `@typescript-eslint/no-unused-vars`=`[2,{argsIgnorePattern:'^_'}]`, `react-refresh/only-export-components`=
  `[2,{allowConstantExport:true}]`, and `no-undef`=`[0]` (typescript-eslint recommended disables it, so no
  `globals` package is needed for browser globals).
- Verify: `npx eslint --print-config src/main.tsx >/dev/null && echo CONFIG_OK` → `CONFIG_OK`.

### Task 3 — fix `lint` script, drop legacy `.eslintrc.cjs`
- `lint` script now `eslint . --report-unused-disable-directives --max-warnings 0` (removed the
  ESLint-10-invalid `--ext ts,tsx`; kept the other two flags). `git rm frontend/.eslintrc.cjs`.
- Verify: `! test -f .eslintrc.cjs && grep -q -- '--report-unused-disable-directives' package.json && ! grep -q -- '--ext' package.json && echo SCRIPT_OK` → `SCRIPT_OK`.

### Task 4 — resolved to zero (v5 per D-P1-1)
- Owner decision **D-P1-1** = pin react-hooks `^5` (see Task 1 AMENDED note). Under the v5 classic
  ruleset `npm run lint` surfaced **11 errors / 9 files** (the 43 v7 React-Compiler violations were
  dropped, as predicted). All 11 resolved lint-only:
  - **4 stale unused `exhaustive-deps` disable directives deleted** (behaviour-neutral no-ops; the
    setState setters are stable so deps were already complete): `AvlLinkSheet:210`, `BomLineSheet:181`,
    `PartSheet:162`, `JournalEntryDialog:162`.
  - **1 `react-hooks/rules-of-hooks` false positive** — `AppShell`'s pure helper `useVisibleModules`
    (a `.filter()`, no hooks) tripped the rule via its `use` prefix when called after early returns.
    Renamed `useVisibleModules` → `getVisibleModules` (definition + the 2 importers `Home.tsx`,
    `SalesOrderDetail.tsx`, + a stale comment in `SalesOrderDetail.test.tsx`).
  - **6 `react-refresh/only-export-components`** — inline `// eslint-disable-next-line
    react-refresh/only-export-components` with a reason on each: `AppShell` (`getVisibleModules`),
    `ui/badge` (`badgeVariants`), `ui/button` (`buttonVariants`), `crumb/Pipeline` (`STAGE_ORDER`,
    `STAGE_LABELS`), `mousse/WorkOrderDetail` (`isUnderIssued`). Fast Refresh is dev-only DX; moving the
    shared exports out would touch many importers (out of scope for a lint chore).
- Verify: `cd frontend && npm run lint; echo "exit=$?"` → **`exit=0`** (0 errors / 0 warnings).
- Regression (touched `src/**`): `npm run test -- --run` → **44 files / 131 tests passed**;
  `npm run build` → **exit 0** (`✓ built in 505ms`, 317 modules). No behaviour changed.

### Deviations
- **Task 0 branch point:** Plan Task 0 says `git checkout -b chore-lint-gates-clean origin/master`,
  but the phase PLAN.md lives only in commit `a6ee1fb` (docs-only, on the feature branch, not on
  master). Branching off bare `origin/master` would drop the plan — same hazard amended in phases
  12a/12b/13. Cut off the current tip instead (code-identical to origin/master; only delta is the
  docs-only plan commit). Working tree was clean (unrelated `.vscode/settings.json` cosmetic edit
  stashed at owner's request).
