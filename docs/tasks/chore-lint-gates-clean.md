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
- [ ] 3. Fix the `lint` script and delete legacy `.eslintrc.cjs` (Wave A)
- [ ] 4. Run `npm run lint` and fix every surfaced FE violation to zero (Wave A)
- [ ] 5. Ensure ruff availability + document the invocation convention (Wave B)
- [ ] 6. Audit and protect load-bearing side-effect imports BEFORE auto-fix (Wave B)
- [ ] 7. Apply safe ruff auto-fixes, review F401 removal diff, enumerate remaining set (Wave B)
- [ ] 8. Inspect and resolve the 4 F821 undefined-name annotations (Wave B)
- [ ] 9. Resolve remaining hand-inspect items: F811, E741, F841 (Wave B)
- [ ] 9b. Resolve UP035 deprecated-imports and the 2 unsafe fixes (Wave B)
- [ ] 10. Prove no regression across the full behavioral safety net (Wave C)
- [ ] 11. Demonstrate both gates are enforcing (red→green proof) (Wave C)
- [ ] 12. Update requirements-progress, flip NFR-6 status, final commit (Wave C)

## Notes / evidence
(filled in per task)

### Task 1 — add eslint flat-config devDependencies
- `npm install -D @eslint/js eslint-plugin-react-hooks eslint-plugin-react-refresh` → added:
  `@eslint/js@^10.0.1`, `eslint-plugin-react-hooks@^7.1.1`, `eslint-plugin-react-refresh@^0.5.3`.
- `eslint` stayed `10.5.0`, `typescript-eslint` stayed `8.62.0` (verified via `require('.../package.json').version`).
- Lockfile diff: +469/-3; the 3 removals are only `"peer": true` flags flipping now that these
  are direct deps — no version churn.
- Verify: `node -e "require('@eslint/js');require('eslint-plugin-react-hooks');require('eslint-plugin-react-refresh')"` → `exit=0`.

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

### Deviations
- **Task 0 branch point:** Plan Task 0 says `git checkout -b chore-lint-gates-clean origin/master`,
  but the phase PLAN.md lives only in commit `a6ee1fb` (docs-only, on the feature branch, not on
  master). Branching off bare `origin/master` would drop the plan — same hazard amended in phases
  12a/12b/13. Cut off the current tip instead (code-identical to origin/master; only delta is the
  docs-only plan commit). Working tree was clean (unrelated `.vscode/settings.json` cosmetic edit
  stashed at owner's request).
