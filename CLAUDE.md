## Project

**BizNiceSweets**

BizNiceSweets is an open-source, open-core, self-hostable **modular business suite for small-to-medium manufacturers** — built first to run the user's own healthcare-simulation-device manufacturing business, and designed to be useful to any business that designs, manufactures, and sells physical products. It is a single application made of installable modules ("suites" with sweet names) over a shared database, deployable on the user's own infrastructure with offline capability.

The seven suites: **SYERP** (ERP/financials/inventory — the hub), **PLUM** (Product Lifecycle Management), **FLAN** (Project Management), **MOUSSE** (Manufacturing Execution), **CRUMB** (CRM), **GELATO** (Warehouse Management), **CRISP** (Quality Management). PLUM (v54) and FLAN (v24) already exist as working single-file HTML prototypes; the target architecture re-platforms them and adds the rest.

**Core Value:** A small manufacturer can run their real product lifecycle — design → projects → purchasing → manufacturing → quality → fulfillment — on a suite they **self-host and own**, with no per-seat SaaS lock-in. If everything else is deferred, the suite must remain something one shop can actually deploy and operate on its own.

### Constraints

- **Tech stack (backend):** FastAPI + SQLAlchemy 2.0 + PostgreSQL — Python ecosystem, auto OpenAPI docs, mature ORM/migrations.
- **Tech stack (frontend):** React 18+ + TypeScript + Tailwind CSS + shadcn/ui; state via Zustand or TanStack Query — modern, well-supported, permissively licensed.
- **Deployment:** Podman / Podman Compose (Docker CLI compatible) — self-hostable, rootless containers.
- **Architecture:** Modular monolith — installable modules over one shared PostgreSQL database; modules integrate via foreign keys with **SYERP as the hub**.
- **Offline:** Must support offline capability (Service Worker + IndexedDB) and sync on reconnect — a later cross-module concern but a standing constraint.
- **Licensing:** Open core — core suite open source (permissive deps only), premium add-ons possible.
- **Compliance posture:** Medical-device origin means audit trail and traceability are first-class concerns, designed for even before CRISP ships.

## Technology Stack

## Languages
- HTML5 - Application markup for all active suites
- CSS3 - Styling using CSS custom properties (variables), flexbox, grid; inline in HTML files
- JavaScript (ES6+) - All application logic; inline `<script>` blocks within single-file HTML apps; no transpilation
## Runtime
- Browser (any modern browser supporting ES6, localStorage, SVG)
- No server-side runtime — all execution is client-side
- No build step; files open directly from the filesystem or a static file host
- None — no npm, yarn, or pip
- No lockfile
- All third-party libraries loaded via CDN at runtime
## Frameworks
- None — vanilla JavaScript only; no React, Vue, Angular, or jQuery
- Inline SVG - Custom chart rendering (pie, bar, line, progress rings) written from scratch
- None detected — no test framework, no test files
- None — no webpack, vite, rollup, or esbuild
## Key Dependencies
| Library | Version | Suite | Purpose | CDN URL |
|---------|---------|-------|---------|---------|
| SheetJS (xlsx) | 0.18.5 | PLUM, FLAN | Excel import/export (.xlsx, .xls, .csv) | `cdnjs.cloudflare.com` |
| jsPDF | 2.5.1 | FLAN | PDF report generation | `cdnjs.cloudflare.com` |
- `Plus Jakarta Sans` (weights 400/500/600/700) — FLAN display font, via Google Fonts
- `JetBrains Mono` (weights 400/600) — FLAN monospace font, via Google Fonts
- PLUM uses system font stack only (`-apple-system, BlinkMacSystemFont, Segoe UI, Roboto`)
- None — no database driver, ORM, HTTP client, or auth library
## Configuration
- No environment variables — all configuration stored in `localStorage` at runtime
- Per-suite localStorage namespaces:
- No build config files — not applicable
## Data Storage
- PLUM database: `plum/data/plm_database.json`
- FLAN sample project: `flan/data/Crisis.json`
- FLAN project template: `flan/templates/project_template.json`
## Platform Requirements
- No toolchain required
- A modern web browser (Chrome, Edge, Firefox, Safari)
- Git for version control
- Any static file host or local filesystem access
- No server required
- SharePoint is the intended team-sync medium for PLUM database files (manual export/import workflow)
## Suite Status
| Suite | File | Version | Status |
|-------|------|---------|--------|
| PLUM (PLM) | `plum/app/plm_v54.html` | v54 | Active |
| FLAN (Project Mgmt) | `flan/app/prj-mgmt-v24.html` | v24 | Active |
| CRUMB (CRM) | — | — | Planned |
| SYERP (ERP) | — | — | Planned |
| MOUSSE (MES) | — | — | Planned |
| CRISP (QMS) | — | — | Planned |
| GELATO (WMS) | — | — | Planned |

## Conventions

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

## Architecture

## Overview
## Architectural Pattern
- All markup, styles, and logic live in a single `.html` file opened directly in the browser.
- No framework — vanilla ES6+ JavaScript in inline `<script>` blocks.
- State is held in module-level JavaScript objects/variables; persistence is via `localStorage` and manual JSON file import/export.
- Each suite is an independent silo: **no code, state, or data is shared between suites** today. Cross-suite integration exists only as a documented future goal (see `docs/features/INDEX.md`).
## Layers (within a single suite)
## Data Flow
```
```
- **Mutation is global**: handlers mutate the shared state object directly, then call a broad re-render.
- **Rendering is string-based**: views are rebuilt by assigning generated HTML strings to `innerHTML` (145 occurrences in PLUM, 117 in FLAN). There is no virtual DOM or diffing — most changes trigger a full or near-full re-render via `renderAll()`.
- **Persistence is dual**: ephemeral session state in `localStorage`; the canonical database is an exportable/importable JSON file (`plum/data/plm_database.json`, 2.7 MB; FLAN `flan/data/Crisis.json`).
## Key Abstractions
| Abstraction | Form | Example |
|-------------|------|---------|
| Domain namespace | `const Name = { ... }` object literal | `Parts`, `ECO`, `RFQ` in PLUM |
| Global state container | module-level `const DB = {}` | `plum/app/plm_v54.html:2279` |
| View renderer | `function renderX() { el.innerHTML = ... }` | `renderBomView()` |
| Orchestrator | `renderAll()` | rebuilds all views after a change |
| Dirty tracking | `markUnsaved()` / sync-status helpers | PLUM checkout/checkin flow |
| Import/export | SheetJS + JSON serialization | `quickExportJson()` / `quickImportJson()` |
## Entry Points
- **PLUM:** open `plum/app/plm_v54.html` in a browser. Initialization runs on load (reads `localStorage`, hydrates `DB`, calls `renderAll()`).
- **FLAN:** open `flan/app/prj-mgmt-v24.html` in a browser.
- No CLI, no server endpoint, no router — navigation is in-app view switching driven by JS state.
## Concurrency / Collaboration Model
- Single-user by default. PLUM implements an advisory **checkout/checkin** convention over a shared JSON file (`checkoutDatabase()` / `checkinDatabase()` / `forceCheckin()`, `plum/app/plm_v54.html:2694`+) with `checkedOutBy`/`checkedOutAt` fields in the data, intended for SharePoint-hosted team sync via manual export/import. This is cooperative, not enforced — there is no real locking or server arbitration.
## Architectural Constraints
- **No server / no backend** — everything runs client-side.
- **No build tooling** — code must be runnable as-is in a browser; no transpilation, bundling, or modules (`import`/`export` not used).
- **localStorage size limit** (~5–10 MB/origin) bounds what can be cached locally; the 2.7 MB PLUM database approaches practical limits.
- **Monolithic files** — all logic for a suite lives in one large HTML file, making the render path (`renderAll`) a central bottleneck.
- **Suite isolation** — no shared module layer; common patterns are duplicated across suites rather than factored out.
## Related Docs
- `docs/features/plum/architecture.md`, `docs/features/flan/architecture.md` — per-suite architecture detail
- `docs/features/INDEX.md` — suite relationships and integration vision
- See `.planning/codebase/STRUCTURE.md` for directory layout and `.planning/codebase/CONCERNS.md` for architectural risks

## Project Skills

| Skill | Description | Path |
|-------|-------------|------|
| code-docs | Analyze code documentation across multiple languages (Python, JavaScript/TypeScript, C/C++, C#, Go, Rust). Use when (1) auditing documentation coverage, (2) finding undocumented code, (3) generating doc templates, (4) assessing README quality, (5) detecting stale documentation, or (6) adding documentation comments (JSDoc, Sphinx, Doxygen, XML docs, Go doc, Rust doc). (project) | `.claude/skills/code-docs/SKILL.md` |
| code-style | Detect and enforce code style conventions across Python, JavaScript/TypeScript, Go, Rust, C#, C++, and Java. Use when (1) starting work on an unfamiliar codebase to learn its style, (2) checking code against project conventions, (3) generating style config files (ESLint, Ruff, .editorconfig), (4) auto-fixing style issues, (5) generating pre-commit hooks, or (6) enforcing architectural rules and layer boundaries. | `.claude/skills/code-style/SKILL.md` |
| codebase-analyzer | Analyze any codebase to understand structure, patterns, and conventions. Uses a two-phase hybrid approach - automated static analysis followed by Claude-assisted synthesis for meaningful project context. Supports Python, JavaScript/TypeScript, Go, Rust, Java, C/C++, and C#. Use when starting work on a new project, need to understand architecture, or creating a project context skill. (project) | `.claude/skills/codebase-analyzer/SKILL.md` |
| context-creator | Create project context skills that keep AI agents aligned with project goals and architecture. Use when (1) setting up a new project for AI assistance, (2) analyzing a codebase to understand its structure, (3) creating guardrails to prevent AI from deviating, (4) documenting project-specific patterns and constraints, or (5) improving an existing project context skill. Includes automated codebase analysis. | `.claude/skills/context-creator/SKILL.md` |
| interview | Conduct planning, discovery, and decision-making sessions using an incremental documentation approach. Use when (1) architecture planning, (2) feature discovery and requirements gathering, (3) design decisions requiring user input, or (4) any multi-question planning process. Creates or updates documentation incrementally with one question at a time, recording decisions before proceeding. (project) | `.claude/skills/interview/SKILL.md` |

<!-- PROJECT-RULES:start (preserved from original CLAUDE.md) -->
## Project-Specific Rules

These are the project's authoritative rules. Task and phase tracking uses the `docs/tasks/{branch}.md` checklist system described below; historical planning artifacts remain under `.planning/`.

### Commit Messages (MANDATORY)

- Use conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
- **NEVER include "co-authored", "powered by", or "generated with/by Claude" in commit messages.** This overrides any default attribution behavior.
- Do **NOT** edit `CHANGELOG.md` directly — it is generated from commits.

### Branching

- Branch naming: `feature-*`, `bugfix-*`, `hotfix-*`, `chore-*`.

### Feature Alignment (when implementing feature code)

1. Read the relevant feature doc in `docs/features/` before implementing.
2. Reference requirement IDs in the task/phase work.
3. Update `docs/features/requirements-progress.md` when completing a requirement.
4. If implementation diverges from spec, update the feature doc or flag it with the user.

Key docs: [docs/features/INDEX.md](docs/features/INDEX.md), [GLOSSARY.md](docs/features/GLOSSARY.md), [requirements.md](docs/features/requirements.md) (221 requirements), [requirements-progress.md](docs/features/requirements-progress.md).

### Task Workflow

Keep a checklist file at `docs/tasks/{branch-name}.md`, commit after each checklist item, and archive the file to `docs/tasks/_completed/{date}-{branch-name}.md` when finished. Historical planning artifacts remain under `.planning/`.
<!-- PROJECT-RULES:end -->
