# Technology Stack

**Analysis Date:** 2026-06-22

## Languages

**Primary:**
- HTML5 - Application markup for all active suites
- CSS3 - Styling using CSS custom properties (variables), flexbox, grid; inline in HTML files
- JavaScript (ES6+) - All application logic; inline `<script>` blocks within single-file HTML apps; no transpilation

## Runtime

**Environment:**
- Browser (any modern browser supporting ES6, localStorage, SVG)
- No server-side runtime — all execution is client-side
- No build step; files open directly from the filesystem or a static file host

**Package Manager:**
- None — no npm, yarn, or pip
- No lockfile
- All third-party libraries loaded via CDN at runtime

## Frameworks

**Core:**
- None — vanilla JavaScript only; no React, Vue, Angular, or jQuery

**UI/Charting:**
- Inline SVG - Custom chart rendering (pie, bar, line, progress rings) written from scratch
  - See `Charts` object in `plum/app/plm_v54.html` (~line 13105)
  - See `renderPieChart()` and `renderBarChart()` functions in `flan/app/prj-mgmt-v24.html` (~line 5465)

**Testing:**
- None detected — no test framework, no test files

**Build/Dev:**
- None — no webpack, vite, rollup, or esbuild

## Key Dependencies

**Critical (loaded from CDN):**

| Library | Version | Suite | Purpose | CDN URL |
|---------|---------|-------|---------|---------|
| SheetJS (xlsx) | 0.18.5 | PLUM, FLAN | Excel import/export (.xlsx, .xls, .csv) | `cdnjs.cloudflare.com` |
| jsPDF | 2.5.1 | FLAN | PDF report generation | `cdnjs.cloudflare.com` |

**Fonts (loaded from CDN):**
- `Plus Jakarta Sans` (weights 400/500/600/700) — FLAN display font, via Google Fonts
- `JetBrains Mono` (weights 400/600) — FLAN monospace font, via Google Fonts
- PLUM uses system font stack only (`-apple-system, BlinkMacSystemFont, Segoe UI, Roboto`)

**Infrastructure:**
- None — no database driver, ORM, HTTP client, or auth library

## Configuration

**Environment:**
- No environment variables — all configuration stored in `localStorage` at runtime
- Per-suite localStorage namespaces:
  - PLUM: `plmUsername`, `plmPartNumberingConfig`, `plmTutorialCompleted`, `plmLastExport_*`, `plmLastImport_*`
  - FLAN: `prj_mgmt_theme`, `prj_mgmt_projects`, `prj_mgmt_density`, `prj_mgmt_collapsed_sections`, `prj_mgmt_pinned`, `prj_mgmt_recent`, `prj_mgmt_initialized`

**Build:**
- No build config files — not applicable

## Data Storage

**Persistence format:** JSON files on the local filesystem or SharePoint
- PLUM database: `plum/data/plm_database.json`
- FLAN sample project: `flan/data/Crisis.json`
- FLAN project template: `flan/templates/project_template.json`

**In-memory state:** JavaScript objects in module-level variables inside each HTML file (e.g., `DB` object in PLUM)

## Platform Requirements

**Development:**
- No toolchain required
- A modern web browser (Chrome, Edge, Firefox, Safari)
- Git for version control

**Production:**
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

---

*Stack analysis: 2026-06-22*
