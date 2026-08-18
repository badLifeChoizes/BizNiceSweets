# Verification: 01 — Lint gates fixed-to-clean
Date: 2026-07-21 | Commits: 55eb7b5..ee11674 (branch chore-lint-gates-clean; plan a6ee1fb)
Verdict: PASS (2 minor stale-doc gaps)

Implements SRD NFR-6 (fix-to-clean per D-M4-3). CI-wiring clause confirmed genuinely
deferred to Phase 3 / NFR-4 (not silently dropped — see CI deferral note below). Every
success criterion re-run empirically by the verifier; nothing taken on report.

## Criteria

### SC1 (FE flat config exists + wired) — PASS
| Truth | Exists | Wired | Works | Evidence |
|---|---|---|---|---|
| `frontend/eslint.config.js` flat config | yes | yes | yes | file present; `npx eslint --print-config src/main.tsx` prints `react-hooks/rules-of-hooks`, `react-hooks/exhaustive-deps`, and `@typescript-eslint/no-unused-vars: [2,{argsIgnorePattern:"^_"}]` |
| recommended rulesets only | yes | yes | yes | composes `js.configs.recommended` + `tseslint.configs.recommended` + `reactHooks.configs['recommended-latest']` + `reactRefresh.configs.vite`; no `recommendedTypeChecked` |
| `^_` no-unused-vars tweak preserved | yes | yes | yes | printed config confirms `argsIgnorePattern:"^_"` |
| dist/coverage ignores | yes | — | yes | `ignores: ['dist','coverage']` |
| needed devDeps added | yes | yes | yes | `@eslint/js ^10.0.1`, `eslint-plugin-react-hooks ^5.2.0` (installed 5.2.0 — D-P1-1 pin), `eslint-plugin-react-refresh ^0.5.3`; `require()` of all three exits 0; `eslint 10.5.0` / `typescript-eslint 8.62.0` unchanged |
| `.eslintrc.cjs` deleted | yes | — | yes | `ls` reports No such file |
| `lint` script fixed for ESLint 10 | yes | yes | yes | `"eslint . --report-unused-disable-directives --max-warnings 0"` — no `--ext` |

Note: 2 `react-hooks/exhaustive-deps` disable directives remain (NewRevisionDialog.tsx,
PartnerSheet.tsx); plan deleted 4 stale ones (D-P1-1). Because lint passes under
`--report-unused-disable-directives --max-warnings 0`, both are validated USED — proving
the react-hooks ruleset is actually loaded and enforcing, not merely declared.

### SC2 (FE clean) — PASS
| Truth | Works | Evidence |
|---|---|---|
| `npm run lint` exit 0 on clean tree | yes | ran from `frontend/`: `LINT_EXIT=0`, no warnings/errors |

### SC3 (BE gate runnable + clean) — PASS
| Truth | Exists | Works | Evidence |
|---|---|---|---|
| ruff in dev env, v0.15.18 | yes | yes | `backend/.venv/bin/ruff --version` → `ruff 0.15.18` |
| `ruff check .` exit 0 from `backend/` | — | yes | `All checks passed!` `RUFF_EXIT=0` |
| F821 resolved cleanly (no blanket noqa) | yes | yes | plum/service.py resolves `ImportPreviewResponse`/`ImportCommitResponse` via `if TYPE_CHECKING:` import block; `grep noqa.*F821` returns nothing |
| side-effect F401 imports guarded | yes | yes | 51 `# noqa: F401` in `syerp/service/__init__.py` (matches claim); cold-boot confirms none stripped |

### SC4 (both gates proven enforcing) — PASS (independently re-proven)
| Gate | Red exit | Green exit | Evidence |
|---|---|---|---|
| Frontend ESLint | 1 | 0 | planted unused non-`_` var in throwaway `src/__lint_probe__.ts` → `npm run lint` exit 1; removed → exit 0 |
| Backend ruff | 1 | 0 | planted unused `import os` in `scripts/__ruff_probe__.py` → `ruff check .` exit 1; removed → exit 0 |

Working tree clean after proof (`git status --porcelain` empty; probe files removed).

### SC5 (no regression — CRITICAL) — PASS
| Truth | Works | Evidence |
|---|---|---|
| 23/23 `verify_*.py` exit 0 in-container | yes | ran all 23 via `podman exec ... compose_api_1`: `PASS=23 FAIL=0`. Container source is bind-mounted (`../backend:/app:z` in compose.dev.yml) → runs current branch code (host/container files identical) |
| full Vitest suite passes | yes | `npm run test -- --run`: **44 test files, 131 tests, all passed**, exit 0 |
| `npm run build` (`tsc -b && vite build`) clean | yes | built in 486ms, `BUILD_EXIT=0` (chunk-size >500kB is a warning, not error) |
| cold backend boot (`import app.main`) | yes | `podman exec ... python -c "import app.main; print('BOOT_OK')"` → `BOOT_OK` — guards the F401 side-effect-import removal hazard |

**"44/131" ambiguity RESOLVED:** it means 44 test files / 131 individual tests, ALL PASSING
(0 failed, 0 skipped). Not "44 of 131 passed." SC5 is not undermined.

## Regression protection
| Criterion | Pinned by |
|---|---|
| SC2 (FE lint clean) | `npm run lint` — the gate itself is the durable check (auto-run in CI deferred to Phase 3/NFR-4) |
| SC3 (BE lint clean) | `ruff check .` — the gate itself is the durable check (auto-run in CI deferred to Phase 3/NFR-4) |
| SC4 (gates enforce) | manual: one-time red→green proof re-run by verifier; no standing automated "gate-fails-on-violation" test (feasible but non-standard — see gaps, minor) |
| SC5 (no regression) | Durable & automated: `frontend` Vitest (44 files/131 tests) + 23 `backend/scripts/verify_*.py` + `import app.main` cold boot. These scripts are re-runnable; auto-invocation in CI + pytest-harness port are NFR-4/Phase 3 (BACKLOG p1) |

## Test suite (actual results)
- `npm run lint` (frontend/): exit 0, clean.
- `ruff 0.15.18 check .` (backend/): `All checks passed!`, exit 0.
- `npm run test -- --run`: 44 files / 131 tests passed, exit 0.
- `npm run build`: exit 0.
- 23/23 `verify_*.py` in `compose_api_1`: PASS=23 FAIL=0.
- Cold boot `import app.main`: BOOT_OK.
- `npm ci --dry-run` (clean-install risk check): exit 0 — dependency tree resolves with
  `legacy-peer-deps=true`; `frontend/.npmrc` is git-tracked, so Phase-3 CI `npm ci` will pick
  it up. Re-declared `@testing-library/dom ^10.4.1` present. Risk mitigated but stands flagged
  for Phase 3 (a CI runner must honor `.npmrc`).

## CI deferral (confirmed genuinely deferred, not dropped)
- SRD NFR-6 status: `implemented ... CI-wiring clause pending NFR-4/Phase 3` (.zj/SRD.md:722).
- requirements-progress.md:94 NFR row: "CI-wiring clause deferred to NFR-4/Phase 3."
- BACKLOG.md:18 "CI pipeline" item remains open (p1), scoping ruff+pytest+eslint+vitest on push.
- Plan "Out of scope" explicitly lists CI wiring. Deferral is documented and traceable.

## Gaps
1. **minor — stale doc: CLAUDE.md:72** still asserts "**Both lint gates are currently
   non-functional**" and "`ruff` ... not installed in `backend/.venv`". Both are now false
   (this phase made them functional and installed ruff at `backend/.venv/bin/ruff`). The line
   sits in a section carrying a top-of-file stale-note caveat, which softens it, but the
   specific factual claim is now wrong and should be updated (e.g. "both lint gates fixed to a
   zero-violation baseline in v4.0 Phase 1; CI auto-run pending Phase 3"). Suggested fix: edit
   CLAUDE.md:72. Not a functional blocker.
2. **minor — stale doc: BACKLOG.md:44** the p1 item "**Neither lint gate runs**" is still
   unchecked `- [ ]` though this phase resolved it. Suggested fix: mark done / move to a
   resolved section citing Phase 1. (The separate CI-pipeline p1 item at :18 correctly stays
   open.)
3. **minor / note — SC4 has no standing automated enforce-test.** The gates are the durable
   checks for SC2/SC3, but "gate exits non-zero on a violation" is only proven by hand. A tiny
   CI smoke (plant→expect-fail→revert) would automate it; conventionally the gate's presence in
   CI (Phase 3) is deemed sufficient. Recorded as manual, low priority.

None of the gaps undermine the phase goal: all five success criteria pass empirically, both
gates run and are enforcing, and the full behavioral safety net is green with zero regression.
