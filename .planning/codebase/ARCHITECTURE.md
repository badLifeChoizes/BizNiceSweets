# Architecture

**Analysis Date:** 2026-06-22

## Overview

BizNiceSweets is a collection of seven independent **single-file browser applications** ("suites"), each a self-contained HTML document with inline CSS and JavaScript. There is no server, no build step, and no shared runtime. Two suites are active — **PLUM** (PLM, `plum/app/plm_v54.html`, ~31k lines) and **FLAN** (project management, `flan/app/prj-mgmt-v24.html`, ~11.5k lines); the other five (CRUMB, SYERP, MOUSSE, CRISP, GELATO) are planned and currently contain only a `CLAUDE.md` and docs scaffolding.

## Architectural Pattern

**Pattern:** Monolithic single-file client-side application (one HTML file = one deployable app).

- All markup, styles, and logic live in a single `.html` file opened directly in the browser.
- No framework — vanilla ES6+ JavaScript in inline `<script>` blocks.
- State is held in module-level JavaScript objects/variables; persistence is via `localStorage` and manual JSON file import/export.
- Each suite is an independent silo: **no code, state, or data is shared between suites** today. Cross-suite integration exists only as a documented future goal (see `docs/features/INDEX.md`).

## Layers (within a single suite)

A suite file is internally organized into informal layers (top → bottom of the `<script>`):

1. **State** — module-level variables (e.g. PLUM's `const DB = {...}` at `plum/app/plm_v54.html:2279`, plus UI state vars under the `// STATE MANAGEMENT` banner at line 2277).
2. **Domain modules** — namespaced object literals, one per domain concern. PLUM has ~30+: `Parts`, `BomConfigurations`, `ECO`, `ReleaseRequest`, `Compliance`, `VendorPerformance`, `RFQ`, `SupplyChainRisk`, etc. (`plum/app/plm_v54.html:3338`+). These hold the business logic (CRUD, validation, calculations).
3. **Utilities & validation** — `const Utils` (`plum/app/plm_v54.html:2910`), `const Validation` (line 2946), `const PartNumbering`, `const RefDesValidation`.
4. **Render layer** — `renderAll()` orchestrator (`plum/app/plm_v54.html:18005`) calls per-view render functions (`renderDashboard`, `renderPartsView`, `renderBomView`, `renderWhereUsedView`, …). FLAN mirrors this with `renderActivityLog`, `renderRisksTab`, `renderMilestonesTab`, etc.
5. **Charting** — hand-written inline SVG renderers (PLUM `Charts` object ~line 13105; FLAN `renderPieChart()`/`renderBarChart()` ~line 5465).
6. **Persistence** — `localStorage` read/write helpers and JSON/Excel/PDF import-export.

## Data Flow

```
User action (onclick/oninput in HTML)
   → handler / domain-module method (mutates DB / state object)
   → markUnsaved() (PLUM, plum/app/plm_v54.html:7820)
   → renderAll()  ─┬→ updateNavCounts()
                   ├→ renderDashboard()
                   ├→ renderPartsView()
                   └→ … (rebuilds DOM via innerHTML)
   → persist to localStorage / explicit JSON export
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

---

*Architecture analysis: 2026-06-22*