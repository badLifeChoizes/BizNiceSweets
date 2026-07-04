# Code Conventions

**Analysis Date:** 2026-06-22

> Conventions are inferred from the two active suites (`plum/app/plm_v54.html`, `flan/app/prj-mgmt-v24.html`). There is no linter, formatter, or style config in the repo, so these are observed practices, not enforced rules.

## Language & Style

- **Vanilla ES6+ JavaScript**, inline in `<script>` blocks. No modules (`import`/`export`), no TypeScript, no JSX.
- **Variable declarations:** `const` is dominant (~2,900 occurrences in PLUM), `let` for mutable locals/state (~260). `var` is essentially absent in JS (raw counts are inflated by CSS `var(--token)` custom properties).
- **Strings:** template literals are used heavily for HTML generation (`` `<div>${x}</div>` ``).
- **Semicolons:** present (conventional JS).
- **Indentation:** inconsistent — generated/edited sections vary between compact (1–2 space) and standard indentation within the same file. No formatter enforces it.

## Naming

| Element | Convention | Example |
|---------|-----------|---------|
| Domain module objects | `PascalCase` object literal | `const Parts = { ... }`, `const ECO`, `const RFQ` |
| Global state container | `UPPER`/`PascalCase` const | `const DB = { ... }` |
| Functions | `camelCase`, verb-first | `sortParts()`, `checkoutDatabase()`, `markUnsaved()` |
| Render functions | `render` + `PascalCase` view name | `renderDashboard()`, `renderBomView()`, `renderWhereUsedView()` |
| Prompt/handler functions | `prompt`/`toggle`/`update` prefixes | `promptForUsername()`, `toggleSort()`, `updateSyncStatus()` |
| Local variables | `camelCase` | `partNumber`, `selectedProduct` |
| JSON data keys | `camelCase` | `checkedOutBy`, `costAvg`, `countryOfOrigin` |
| localStorage keys | suite-prefixed | PLUM `plm*` (`plmUsername`), FLAN `prj_mgmt_*` |
| CSS classes / custom props | `kebab-case` / `--token` | `--color`, `.breadcrumb-nav` |

## Code Organization Patterns

- **Namespace-by-object:** each domain concern is a single `const Name = { method(){}, ... }` object literal grouping its logic. PLUM has 30+ such modules (`Parts`, `BomConfigurations`, `Compliance`, `VendorPerformance`, `SupplyChainRisk`, …). This is the primary modularization unit in lieu of files/imports.
- **Section banners:** CSS and JS are divided with comment banners — `/* ===== HEADER ===== */`, `/* ===== TABLES ===== */`, and `// STATE MANAGEMENT`-style markers — used to navigate the large single files.
- **Render-everything orchestration:** a single `renderAll()` calls all per-view render functions; views own their DOM region and rebuild it via `innerHTML`.
- **String-template rendering:** views build HTML as template-literal strings and assign to `element.innerHTML` (no DOM node construction APIs, no framework).

## Error Handling

- **`try/catch` around risky operations** — primarily JSON parsing, `localStorage` access, and Excel/PDF import-export. PLUM: ~22 try/catch pairs; FLAN: ~8 try / ~10 catch.
- **User feedback via native dialogs:** `alert()`, `confirm()`, and `prompt()` are used directly (PLUM ~53 call sites, FLAN ~7) for confirmations, errors, and simple input (e.g. `promptForUsername`, delete confirmations). There is no toast/notification abstraction shared across suites.
- No centralized error logger; failures are surfaced inline at the call site.

## DOM & UI

- Event handling is mostly **inline `onclick`/`oninput` attributes** in generated HTML strings calling global functions.
- Heavy reliance on `innerHTML` for both reads and writes (PLUM 145, FLAN 117 occurrences) — see `.planning/codebase/CONCERNS.md` for the XSS/perf implications.
- Charts are **hand-rolled inline SVG** (PLUM `Charts` object; FLAN `renderPieChart`/`renderBarChart`) rather than a charting library.

## Persistence Conventions

- Session/UI state → `localStorage` under a suite-specific prefix.
- Canonical data → JSON file, imported/exported explicitly by the user (SheetJS for Excel/CSV, native JSON for the database).
- PLUM adds advisory checkout metadata (`checkedOutBy`, `checkedOutAt`) to support manual multi-user sync.

## Commit & Workflow Conventions (from `CLAUDE.md`)

- **Conventional commits:** `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
- **Do NOT** include "co-authored", "powered by", or "generated with Claude" lines in commit messages (explicit project rule).
- Branch naming: `feature-*`, `bugfix-*`, `hotfix-*`, `chore-*`.
- Every code-changing task must have a checklist file at `docs/tasks/{branch-name}.md`; update it before each commit.
- `CHANGELOG.md` is generated from commits — never edit it directly.
- Feature work must reference requirement IDs and update `docs/features/requirements-progress.md`.

## What's Absent (by design)

- No linter / formatter / style config (no ESLint, Prettier, `.editorconfig`).
- No type system.
- No build or bundling step — code must run directly in the browser.
- No shared/common library across suites — patterns are duplicated per suite.

---

*Conventions analysis: 2026-06-22*