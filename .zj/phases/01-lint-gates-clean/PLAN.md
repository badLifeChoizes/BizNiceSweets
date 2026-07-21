# Plan: 01 — Lint gates fixed-to-clean
Goal: Both static-analysis lint gates (frontend ESLint 10 flat, backend ruff) run, pass clean on a zero-violation baseline, and are proven enforcing — with zero runtime regression.
Status: draft

## Success criteria
Implements **NFR-6** (`.zj/SRD.md:722`), fix-to-clean per **D-M4-3**. The CI-wiring clause of NFR-6 is OUT of scope (Phase 3 / NFR-4).

- **SC1 (FE config):** `frontend/eslint.config.js` flat config exists (recommended rulesets only + the `no-unused-vars` `^_` tweak + dist/coverage ignores); needed devDeps added; `.eslintrc.cjs` deleted; `lint` script fixed for ESLint 10.
- **SC2 (FE clean):** `npm run lint` exits 0 on the clean tree.
- **SC3 (BE gate runnable + clean):** ruff available in dev env with a documented convention; `ruff check .` (from `backend/`) exits 0 on the clean tree.
- **SC4 (gates proven enforcing):** for each gate, a deliberate violation makes the command exit non-zero; removing it returns green (red→green proof recorded).
- **SC5 (no regression — CRITICAL):** all 23 `backend/scripts/verify_*.py` exit 0 in-container, full Vitest suite passes, `npm run build` + `tsc -b` clean, AND a cold backend process boots (guards the F401 side-effect-import hazard).

## Context
**Branch:** branch fresh off master — `git checkout -b chore-lint-gates-clean origin/master` (no local `master`; current `feature-syerp-ar-invoicing` is fully merged, 0 ahead). This is a `chore-*` — ships no capability.

**Frontend (verified today):**
- `eslint@10.5.0` + `typescript-eslint@8.62.0` (with all `@typescript-eslint/*` subpkgs) ALREADY in `frontend/package.json` devDeps + node_modules. **Missing/needed:** `@eslint/js`, `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`.
- No flat `eslint.config.js`. Legacy `frontend/.eslintrc.cjs` present (old `@typescript-eslint/parser`+plugin names, ignored by ESLint 10).
- Current `lint` script: `eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0` — the `--ext` flag was REMOVED in ESLint 10.
- `tsconfig.app.json` has `strict` + `noUnusedLocals` + `noUnusedParameters` all true and `build` runs `tsc -b`, so unused vars/imports are already impossible. 163 ts/tsx files under `frontend/src`.
- **Deviation logged at build (D-P1-1):** the installed react-hooks was **v7.1.1**, whose `recommended` bundles the React-Compiler ruleset (54 errors / 41 files, 42 behavior-sensitive) — out of scope. **Pinned to `^5`** so `recommended` == the intended classic 2-rule set (11 errors / 9 files residual, resolved in Task 4). Also: **only 2 of the 6** pre-existing `exhaustive-deps` disables are actually USED — the other 4 (`AvlLinkSheet:210`, `BomLineSheet:181`, `PartSheet:162`, `JournalEntryDialog:162`) are stale no-ops and are deleted in Task 4.
- **6 pre-existing** `// eslint-disable-next-line react-hooks/exhaustive-deps` directives (confirmed): `frontend/src/routes/syerp/components/JournalEntryDialog.tsx`, `.../syerp/components/PartnerSheet.tsx`, `.../plum/components/BomLineSheet.tsx`, `.../plum/components/NewRevisionDialog.tsx`, `.../plum/components/PartSheet.tsx`, `.../plum/components/AvlLinkSheet.tsx`. With `react-hooks` loaded these become valid suppressions; under `--report-unused-disable-directives` they REQUIRE the rule to be loaded (proves react-hooks is the intended ruleset). Expect near-zero NEW hand-fixes — but run the real config and fix whatever actually surfaces (do not assume zero).

**Backend (verified today):**
- `ruff==0.15.18` pinned in `backend/requirements-dev.txt`, NOT in the container image; reconnaissance installed it at `backend/.venv/bin/ruff` (works). `[tool.ruff]` config already committed in `backend/pyproject.toml` (`line-length=100`, `target-version=py313`, `select=[E,F,I,UP]`, `ignore=[E501,UP007]`). No Makefile/lint-script convention exists.
- `ruff check app scripts tests alembic`: **1159 errors, 1088 SAFE-auto-fixable** (`--fix`), 2 hidden UNSAFE fixes (`--unsafe-fixes`). Rules (full tree, pre-fix): F401 419, UP045 270, UP037 252, I001 101, UP017 66, UP035 23, F811 10, UP006 8, **F821 4**, E741 2, F841 2, UP043 2. 75 py under `app`, 23 under `scripts`, plus tests + alembic.
- **After safe `--fix`, ~71 violations remain (1159 − 1088). This set is LARGER than the hand-inspected items below — DO NOT assume it is only those 18.** Expected composition of the remaining ~71: the **18 enumerated below** (F821 4 + F811 10 + E741 2 + F841 2, owned by Tasks 8–9); **UP035 deprecated-import (~23)** — mechanical import-path rewrites ruff won't remove under safe-fix, owned by Task 9b; the **2 hidden unsafe fixes** — owned by Task 9b; and a **remainder (~28)** that safe-fix leaves untouched, most plausibly F401 imports ruff declines to auto-remove (e.g. `__init__.py` re-exports / possible `__all__` members). Task 7 MUST re-derive the exact remaining set from `--statistics` and confirm every category has a named owning task before proceeding.
- **Manual (non-auto-fix) items, sites confirmed (18 of the ~71):**
  - **F821 (4):** `app/modules/plum/service.py:2635` (`ImportPreviewResponse`) + `:2760` (`ImportCommitResponse`); `app/modules/syerp/service/bills.py:769` + `:956` (`PaymentRead`). All are quoted forward-ref return annotations; app imports clean and verify_* pass, so almost certainly unresolved string annotations, not runtime bugs — INSPECT each and either import the name or confirm harmless.
  - **F811 (10):** `app/modules/syerp/service/partners.py:67` (duplicate `func` import — auto-fixable) + 9× `seeded_db` fixture redefinitions in `tests/auth/test_seed_admin.py`.
  - **E741 (2):** ambiguous `l` in `scripts/verify_crumb.py:590`.
  - **F841 (2):** `draft_bill` in `scripts/verify_reports.py:373`; plus one `user_data`.

**CRITICAL HAZARD — F401 auto-fix vs. import-for-side-effects:** the app self-registers modules at import time (`registry.register(...)` in each `app/modules/*/__init__.py`); `app/main.py:95` does `importlib.import_module("app.core.models")` so FK metadata resolves at boot (the Phase-13 boot-500 fix). `app/core/models.py` is a model aggregator whose imports ARE the side effect — it already guards them with `# noqa: F401` (confirmed: every import line carries `# noqa: F401`). A blind `--fix` that strips a load-bearing F401 elsewhere re-introduces a cold-boot 500. Therefore: apply auto-fixes but treat F401 removals as REVIEW-REQUIRED, audit side-effect aggregators, protect with `# noqa: F401`, and gate empirically with the SC5 cold-boot + full verify_* run.

**Verification environment:**
- Live stack: `podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d`. Verify in-container: `podman exec -e PYTHONPATH=/app compose_api_1 python scripts/<name>.py`. 23 `verify_*.py` scripts; bar is 23/23 exit 0.
- Local ruff: `backend/.venv/bin/ruff`. Convention to document: `ruff check .` from `backend/`.
- Frontend: `npm run lint` / `npm run test` / `npm run build` from `frontend/`.

**Repo conventions:** conventional commits (`chore:`/`fix:`/`refactor:`/`docs:`); NEVER add co-authored / generated-with-Claude lines; never edit `CHANGELOG.md`; per-branch checklist at `docs/tasks/chore-lint-gates-clean.md` updated + committed per task; atomic commits.

## Decisions needed
None open. The three scope decisions are already bound: **D-M4-3** (fix-to-clean, not ratchet); **rule strictness = recommended sets only** (FE js.recommended + typescript-eslint recommended + react-hooks + react-refresh; BE keep E/F/I/UP — do NOT add recommendedTypeChecked or B/SIM/RUF); **formatter scope = lint check only** (no `ruff format` / `prettier --check`; E501 stays ignored). If Task 8's inspection reveals any F821 is an actual runtime bug (not a string annotation), STOP and surface to owner — that is a correctness finding outside a mechanical lint phase.

## Tasks

### [ ] 0. Branch off master and open the task checklist
- **Files:** `docs/tasks/chore-lint-gates-clean.md` (new)
- **Do:** `git checkout -b chore-lint-gates-clean origin/master`. Create the checklist file listing tasks 1–12 from this plan. (Serves NFR-6 setup; no SC directly but required by repo convention.)
- **Done when:** `git branch --show-current` is `chore-lint-gates-clean`; `git rev-list --count HEAD..origin/master` is 0; checklist file exists and is committed.
- **Verify:** `git status` clean after `git add docs/tasks/chore-lint-gates-clean.md && git commit -m "chore: open lint-gates-clean checklist"`.
- **Parallel-ok:** no (blocks all)

---
### WAVE A — Frontend gate (SC1, SC2). Parallel-safe vs. Wave B.

### [ ] 1. Add the three missing ESLint flat-config devDependencies (NFR-6 / SC1)
- **Files:** `frontend/package.json`, `frontend/package-lock.json`
- **Do:** From `frontend/`, `npm install -D @eslint/js eslint-plugin-react-hooks@^5 eslint-plugin-react-refresh` (**react-hooks pinned to `^5`, D-P1-1** — v7's `recommended` redefines the preset to bundle the React-Compiler ruleset, out of scope for NFR-6). Do NOT touch `eslint` or `typescript-eslint` (already correct versions). Verify no unrelated dependency churn in the lockfile diff.
- **Done when:** the three packages appear in `devDependencies` and resolve in `node_modules`; `eslint`/`typescript-eslint` versions unchanged.
- **Verify:** `node -e "require('@eslint/js');require('eslint-plugin-react-hooks');require('eslint-plugin-react-refresh')"` exits 0.
- **Parallel-ok:** no (blocks Task 2/3 within Wave A)

### [ ] 2. Write `frontend/eslint.config.js` flat config (NFR-6 / SC1)
- **Files:** `frontend/eslint.config.js` (new)
- **Do:** Author an ESLint 10 flat config (ESM, `export default`): compose `@eslint/js` `js.recommended`, `typescript-eslint` `configs.recommended` (via `typescript-eslint`'s `config()` helper or a flat array), `eslint-plugin-react-hooks` recommended, and `eslint-plugin-react-refresh` (Vite variant). Add rule override `'@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }]` (preserving the legacy `.eslintrc.cjs` tweak). Add `ignores: ['dist', 'coverage']`. Do NOT enable `recommendedTypeChecked` (owner decision). Mirror the 6 existing `react-hooks/exhaustive-deps` disable sites as the ruleset-selection signal.
- **Done when:** `npx eslint --print-config src/App.tsx` (from `frontend/`) prints a config that includes `react-hooks/rules-of-hooks`, `@typescript-eslint/no-unused-vars` with `argsIgnorePattern:'^_'`, and does not error on load.
- **Verify:** `cd frontend && npx eslint --print-config src/main.tsx >/dev/null && echo CONFIG_OK`.
- **Parallel-ok:** no (needs Task 1)

### [ ] 3. Fix the `lint` script and delete the legacy `.eslintrc.cjs` (NFR-6 / SC1)
- **Files:** `frontend/package.json`, `frontend/.eslintrc.cjs` (delete)
- **Do:** Change the `lint` script to `eslint . --report-unused-disable-directives --max-warnings 0` (drop the removed `--ext ts,tsx`; keep the other two flags). `git rm frontend/.eslintrc.cjs`.
- **Done when:** `lint` script has no `--ext`; `frontend/.eslintrc.cjs` no longer exists.
- **Verify:** `cd frontend && ! test -f .eslintrc.cjs && grep -q -- '--report-unused-disable-directives' package.json && ! grep -q -- '--ext' package.json && echo SCRIPT_OK`.
- **Parallel-ok:** no (needs Task 2)

### [ ] 4. Run `npm run lint` and fix every surfaced frontend violation to zero (NFR-6 / SC2)
- **Files:** whatever surfaces under `frontend/src/**` (expected near-zero; the 6 `exhaustive-deps` disables should validate cleanly once react-hooks is loaded)
- **Do:** `cd frontend && npm run lint`. For each reported violation, hand-fix it (no rule disabling to dodge work; a genuinely needed suppression gets an inline `eslint-disable-next-line <rule>` with the real loaded rule name). Confirm the 6 pre-existing disable directives are reported as USED (not "unused disable directive"). Re-run to green.
- **Done when:** `npm run lint` exits 0 with no warnings/errors.
- **Verify:** `cd frontend && npm run lint; echo "exit=$?"` shows `exit=0`.
- **Parallel-ok:** no (needs Task 3)

---
### WAVE B — Backend gate (SC3). Parallel-safe vs. Wave A. Auto-fix + side-effect audit MUST precede the regression gate (Wave C).

### [ ] 5. Ensure ruff availability + document the invocation convention (NFR-6 / SC3)
- **Files:** `docs/tasks/chore-lint-gates-clean.md` (note the convention); optionally a short note in `backend/README.md` if one exists — otherwise record convention in the checklist only. Do NOT add a Makefile (out of scope, no existing convention).
- **Do:** Confirm `backend/.venv/bin/ruff --version` reports `0.15.18` (matches `requirements-dev.txt`); if a fresh venv lacks it, `pip install -r requirements-dev.txt`. Record the standing convention: **run `ruff check .` from `backend/`** (container-image ruff is Phase 3/CI's concern).
- **Done when:** `ruff --version` works from the dev venv and the convention is written in the checklist.
- **Verify:** `cd backend && .venv/bin/ruff --version` prints `0.15.18`.
- **Parallel-ok:** yes (independent of Wave A; blocks Tasks 6–9b)

### [ ] 6. Audit and protect load-bearing side-effect imports BEFORE auto-fix (NFR-6 / SC3, guards SC5)
- **Files:** `app/main.py`, `app/core/models.py`, each `app/modules/*/__init__.py` (auth, crumb, gelato, mousse, plum, syerp), `app/core/seed.py`, any seed/registry aggregator
- **Do:** Inventory every import whose purpose is a side effect (module self-registration via `registry.register`, model-metadata population, seed wiring). `app/core/models.py` already `# noqa: F401`-guards its lines (confirmed) — verify none were missed. Add `# noqa: F401` (or an explicit `__all__` re-export) to any side-effect import in the above files that ruff would otherwise flag F401. Produce a written list of protected imports in the checklist so Task 7's `--fix` cannot silently strip them.
- **Done when:** every side-effect import in the audited files is either referenced or `# noqa: F401`-guarded; the protected-import list is recorded.
- **Verify:** `cd backend && .venv/bin/ruff check app/core/models.py app/main.py app/modules/*/__init__.py app/core/seed.py --select F401; echo "exit=$?"` shows `exit=0` (these files clean of F401 before the bulk fix).
- **Parallel-ok:** no (needs Task 5; must precede Task 7)

### [ ] 7. Apply safe ruff auto-fixes, review the F401 removal diff, and enumerate the COMPLETE remaining set (NFR-6 / SC3, guards SC5)
- **Files:** broad — up to ~1088 fixes across `app/`, `scripts/`, `tests/`, `alembic/`; `docs/tasks/chore-lint-gates-clean.md` (record the remaining-set inventory)
- **Do:** From `backend/`, run `.venv/bin/ruff check . --fix` (SAFE fixes only; do NOT pass `--unsafe-fixes` here — the 2 unsafe fixes are Task 9b). Then `git diff --stat` and review every DELETED import line (`git diff | grep -E '^-.*import'`): each removed import must be genuinely unused, NOT a side-effect import missed in Task 6 — restore + `# noqa: F401` any load-bearing removal. **Then run `.venv/bin/ruff check . --statistics` and record the EXACT remaining rule breakdown in the checklist.** Reconcile it against the expected composition (F821 → Task 8; F811/E741/F841 → Task 9; UP035 + 2 unsafe → Task 9b; any leftover F401/other). **Do NOT assume the remainder is only the 18 enumerated items** — if `--statistics` shows a rule category not owned by Tasks 8/9/9b (e.g. residual F401 ruff declined to auto-remove, or an unexpected UP rule), assign it to an owning task (extend Task 9b's scope and note it in the checklist) before proceeding. No remaining category may rely solely on Task 9's final backstop.
- **Done when:** safe-fixable violations resolved; deleted-import review complete with no side-effect import removed; the exact `--statistics` remaining breakdown is recorded and every category is mapped to an owning task.
- **Verify:** `cd backend && .venv/bin/ruff check . --statistics` output is captured in the checklist and every listed rule appears in the Task 8 / 9 / 9b ownership map.
- **Parallel-ok:** no (needs Task 6)

### [ ] 8. Inspect and resolve the 4 F821 undefined-name annotations (NFR-6 / SC3)
- **Files:** `app/modules/plum/service.py` (:2635 `ImportPreviewResponse`, :2760 `ImportCommitResponse`), `app/modules/syerp/service/bills.py` (:769, :956 `PaymentRead`)
- **Do:** For each, determine whether the quoted return-annotation name has a defining schema (likely in the module's `schemas.py`). If it exists, add the import (guarded so it doesn't itself become F401 if only used in a string annotation — use it in a real `from __future__ import annotations` context or import under `TYPE_CHECKING` with the annotation quoted). If no such symbol exists, the annotation is stale — replace with the correct type or a concrete return type. If any turns out to be a real runtime bug, STOP and surface to owner (see Decisions needed). Do NOT blanket-`# noqa` an F821 — resolve it.
- **Done when:** `ruff check --select F821 .` reports 0.
- **Verify:** `cd backend && .venv/bin/ruff check . --select F821; echo "exit=$?"` shows `exit=0`.
- **Parallel-ok:** no (needs Task 7)

### [ ] 9. Resolve remaining hand-inspect items: F811, E741, F841 (NFR-6 / SC3)
- **Files:** `app/modules/syerp/service/partners.py:67` (duplicate `func` — remove local re-import), `tests/auth/test_seed_admin.py` (9× `seeded_db` redefinition — inspect; benign-remove duplicate fixture defs keeping one), `scripts/verify_crumb.py:590` (rename ambiguous `l`), `scripts/verify_reports.py:373` (remove unused `draft_bill`) plus the one unused `user_data`
- **Do:** Fix each by inspection per the note above. For `seeded_db`, confirm the redefinitions are duplicate fixtures and collapse to a single definition without changing test behavior. Rename `l` → a descriptive name. Remove the two unused locals only if they have no side-effecting RHS (both are plain assignments — safe).
- **Done when:** `ruff check .` reports 0 for F811, E741, F841.
- **Verify:** `cd backend && .venv/bin/ruff check . --select F811,E741,F841; echo "exit=$?"` shows `exit=0`.
- **Parallel-ok:** no (needs Task 8)

### [ ] 9b. Resolve UP035 deprecated-imports and the 2 unsafe fixes (NFR-6 / SC3, feeds SC5)
- **Files:** the ~23 files carrying UP035 (deprecated `typing`/import-path usages — enumerate via `.venv/bin/ruff check . --select UP035`) + the 2 files carrying the hidden unsafe fixes (enumerate via `.venv/bin/ruff check . --statistics` / `--select` per Task 7's recorded breakdown), plus any additional residual category Task 7 assigned here
- **Do:** **UP035 (~23):** these are mechanical import-path rewrites (e.g. deprecated `typing.X` → its current module). Apply them — `.venv/bin/ruff check . --select UP035 --fix`; UP035 fixes that ruff marks unsafe require `--unsafe-fixes`, so run `--select UP035 --fix --unsafe-fixes` ONLY after eyeballing each rewrite is behavior-preserving (an import moved, not removed). **2 hidden unsafe fixes:** inspect each individually first (`--select <rule> --diff --unsafe-fixes`); apply with `--unsafe-fixes` ONLY if the rewrite is behavior-preserving — otherwise hand-fix. Because these touch imports, they feed directly into the SC5 cold-boot + verify_* gate (Task 10). Do NOT `# noqa` to dodge a rewrite; resolve it.
- **Done when:** `ruff check .` reports 0 for UP035 and for the 2 unsafe-fix rules; combined with Tasks 7–9, the whole-tree `ruff check .` (from `backend/`) exits 0.
- **Verify:** `cd backend && .venv/bin/ruff check . --select UP035; echo "up035=$?"` shows 0, then `.venv/bin/ruff check .; echo "exit=$?"` shows `exit=0` (whole backend clean — the SC3 backstop; every rule category is now owned).
- **Parallel-ok:** no (needs Task 9)

---
### WAVE C — Regression + enforce-proof (SC4, SC5). Depends on BOTH Wave A and Wave B.

### [ ] 10. Prove no regression across the full behavioral safety net (NFR-6 / SC5)
- **Files:** none (verification only)
- **Do:** Bring up the dev stack: `podman-compose -f compose/compose.yml -f compose/compose.dev.yml up -d`. Run all 23 `backend/scripts/verify_*.py` in-container (`for f in backend/scripts/verify_*.py; do podman exec -e PYTHONPATH=/app compose_api_1 python scripts/$(basename $f) || echo "FAIL $f"; done`) and confirm 23/23 exit 0. Run frontend Vitest (`cd frontend && npm run test -- --run`). Run `cd frontend && npm run build` (includes `tsc -b`). Run the **cold-boot** check: `podman exec -e PYTHONPATH=/app compose_api_1 python -c "import app.main; print('BOOT_OK')"` (or restart the api container and confirm a healthy start) — this is the empirical guard for a removed side-effect import AND for any UP035/unsafe import rewrite from Task 9b.
- **Done when:** 23/23 verify scripts exit 0; Vitest suite passes; `npm run build` succeeds; cold-boot prints `BOOT_OK` (or container comes up healthy).
- **Verify:** the aggregate command chain above reports no `FAIL` lines and each sub-command exits 0.
- **Parallel-ok:** no (needs Tasks 4 and 9b)

### [ ] 11. Demonstrate both gates are enforcing (red→green proof) (NFR-6 / SC4)
- **Files:** temporary scratch edits only (reverted); record proof in `docs/tasks/chore-lint-gates-clean.md`
- **Do:** **Frontend:** introduce a deliberate violation (e.g. an unused non-`_` variable or a hook called conditionally) in a throwaway spot, run `npm run lint`, confirm non-zero exit, revert, confirm exit 0. **Backend:** introduce a deliberate F-class violation (e.g. an unused import without `# noqa`), run `.venv/bin/ruff check .`, confirm non-zero exit, revert, confirm exit 0. Record both red exit codes and the restored green in the checklist. Ensure `git status` is clean afterward (no scratch edit left behind).
- **Done when:** each gate exited non-zero on its planted violation and returned to 0 after revert, recorded in the checklist; working tree clean.
- **Verify:** `git status --porcelain` is empty (apart from the checklist doc); the recorded exit codes show red-then-green for both gates.
- **Parallel-ok:** no (needs Task 10)

### [ ] 12. Update requirements-progress, flip NFR-6 status, final commit (NFR-6 / SC1–SC5)
- **Files:** `docs/features/requirements-progress.md`, `.zj/SRD.md` (NFR-6 `Status: planned` → met), `docs/tasks/chore-lint-gates-clean.md` (mark complete, then archive to `docs/tasks/_completed/2026-07-20-chore-lint-gates-clean.md`)
- **Do:** Add an NFR row/entry for NFR-6 to `requirements-progress.md` following the existing table format (Requirement | Description | Phase | Plans | Evidence | Status), citing this phase, the clean `npm run lint`/`ruff check .` runs, the 23/23 verify + cold-boot evidence, and the red→green proof from Task 11. In `.zj/SRD.md:722`, change NFR-6 `Status: planned` to the met keyword (leaving the CI-wiring clause noted as pending NFR-4/Phase 3). Do NOT edit `CHANGELOG.md`. Commit; archive the checklist.
- **Done when:** `requirements-progress.md` has the NFR-6 evidence entry; `.zj/SRD.md` NFR-6 no longer reads `Status: planned`; checklist archived.
- **Verify:** `grep -n 'NFR-6' docs/features/requirements-progress.md` shows the new entry; `grep -n 'NFR-6' .zj/SRD.md` shows the flipped status.
- **Parallel-ok:** no (needs Task 11)

## Risks
- **F401 auto-fix strips a side-effect import → cold-boot 500.** Early-warning: Task 7's deleted-import review flags a removal inside `app/modules/*/__init__.py`, `app/core/models.py`, or a registry/seed aggregator; the Task 10 cold-boot check fails. Mitigation is the Task 6 audit-and-guard-first sequencing plus the SC5 empirical gate.
- **The post-`--fix` remaining set is larger/different than the 18 hand-inspected items.** Confirmed: ~71 remain (UP035 ~23, 2 unsafe, ~28 remainder). Early-warning: Task 7's `--statistics` shows a rule category with no owning task. Mitigation: Task 7 reconciles the exact breakdown and Task 9b owns UP035 + unsafe (and absorbs any residual category) before the Task 9b whole-tree backstop.
- **A UP035/unsafe import rewrite (Task 9b) changes a runtime import target.** Early-warning: Task 10 cold-boot or a verify_* script fails after 9b. Mitigation: eyeball each rewrite is behavior-preserving (import moved, not removed) before applying `--unsafe-fixes`; the SC5 gate catches any that slip.
- **An F821 is a real runtime bug, not a stale string annotation.** Early-warning: the defining schema truly does not exist AND the code path is reachable at runtime. This exceeds a mechanical lint phase — Task 8 surfaces it to the owner rather than papering over it.
- **A hand-fixed frontend violation changes render/hook behavior.** Early-warning: Vitest or `tsc -b` regresses in Task 10. Fixes must be lint-only; a hook-deps fix that alters effect timing is a behavior change and must be reverted to a justified `eslint-disable` instead.

## Noticed
- **SC4 has no standing automated enforce-test (minor, logged at verify).** "Gate exits non-zero on a violation" is proven only by the one-time manual red→green proof (re-run independently by the verifier). Conventionally the gate's presence in CI (Phase 3 / NFR-4) is deemed sufficient standing protection; a tiny plant→expect-fail→revert CI smoke could automate it if desired. Low priority — deferred to the CI wiring in Phase 3.

## Out of scope
- CI wiring of the gates (GitHub Actions) — Phase 3 / NFR-4.
- Adopting `ruff format` or `prettier --check`; any whole-repo reformatting diff — owner: lint-check-only this phase.
- Broadening rulesets: typescript-eslint `recommendedTypeChecked`, ruff `B`/`SIM`/`RUF` selectors — deferred to a later ratchet.
- Un-ignoring E501 (line length) — stays ignored as configured.
- Installing ruff into the container image — Phase 3/CI concern.
