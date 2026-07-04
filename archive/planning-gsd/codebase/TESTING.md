# Testing

**Analysis Date:** 2026-06-22

## Summary

**There is no automated testing in this codebase.** No test framework, no test files, no CI test pipeline, and no test runner configuration exist anywhere in the repository as of 2026-06-22.

## Evidence

- No `*.test.*`, `*.spec.*`, `__tests__/`, or `test/` directories found across the repo.
- No `package.json` (root or per-suite), so no npm test scripts and no dev dependencies.
- No test-runner config: no Jest, Vitest, Mocha, Playwright, Cypress, or Selenium configuration present.
- No CI configuration that runs tests (no `.github/workflows/`, etc.).
- The `test:` conventional-commit prefix is reserved in `CLAUDE.md`/`README.md` but is currently unused for actual test code.

## Current Quality Assurance (de facto)

In the absence of automated tests, correctness is maintained by:

- **In-app validation modules** — e.g. PLUM's `const Validation` (`plum/app/plm_v54.html:2946`), `RefDesValidation`, `BomHealthScore`, and `PartNumbering` enforce data rules at runtime. These are application logic, not tests, but they catch malformed input.
- **Manual / exploratory testing in the browser** — the apps are opened directly and exercised by hand.
- **Documented invariants** — `docs/features/{plum,flan}/INVARIANTS.md` capture rules the app is expected to uphold; these are candidates to be turned into automated assertions.
- **Versioned archives** — prior app versions in `{suite}/archive/` provide a manual rollback path if a change regresses behavior.

## Implications

- Refactoring the large single-file apps (PLUM ~31k lines, FLAN ~11.5k lines) is high-risk with no regression safety net.
- Data-integrity logic (BOM traversal, ECO workflow, checkout/checkin, migration) is complex and untested — see `.planning/codebase/CONCERNS.md`.

## Recommended Testing Approach (if introduced)

Because the apps are framework-free, browser-based single files, a lightweight strategy fits best:

| Layer | Suggested tooling | Targets |
|-------|-------------------|---------|
| Unit (pure logic) | Vitest or plain JS assertions | Validation rules, part-number generation, BOM math, cost rollups — but logic is currently embedded in HTML and would need extraction or a test harness that loads the file |
| Integration / DOM | Playwright or jsdom | View rendering (`renderAll` and per-view renders), import/export round-trips |
| End-to-end | Playwright | Open the HTML file, drive UI flows (create part → add to BOM → export → re-import) |
| Data contracts | JSON schema validation | `plm_database.json`, `Crisis.json`, `project_template.json` shape |

Introducing any of these requires first adding a minimal toolchain (e.g. a `package.json` + Vitest/Playwright), which the project has deliberately avoided to keep apps build-free. A pragmatic first step is converting `INVARIANTS.md` rules into a small set of browser-loadable assertion checks.

## Mocking / Fixtures

- No mocking framework. Sample data exists and could serve as fixtures: `flan/data/Crisis.json`, `flan/templates/project_template.json`, `plum/data/plm_database.json`.

## Coverage

- **0% automated coverage.** Not measured; no coverage tooling configured.

---

*Testing analysis: 2026-06-22*
