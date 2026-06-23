# External Integrations

**Analysis Date:** 2026-06-22

## APIs & External Services

**CDN Libraries:**
- SheetJS (xlsx) v0.18.5 — Excel/CSV import and export
  - URL: `https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js`
  - Used by: PLUM (`plum/app/plm_v54.html` line 1), FLAN (`flan/app/prj-mgmt-v24.html` line 8)
  - Auth: None
- jsPDF v2.5.1 — PDF report generation
  - URL: `https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js`
  - Used by: FLAN (`flan/app/prj-mgmt-v24.html` line 7)
  - Auth: None

**Web Fonts:**
- Google Fonts — Plus Jakarta Sans and JetBrains Mono
  - URL: `https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap`
  - Used by: FLAN (`flan/app/prj-mgmt-v24.html` line 9)
  - Auth: None
  - Note: PLUM uses system fonts only — no Google Fonts dependency

## Data Storage

**Databases:**
- None — no SQL or NoSQL database server
- All persistent data stored as JSON files on user's local filesystem or SharePoint

**File-based Storage:**
- PLUM database: `plum/data/plm_database.json` (versioned JSON with `version` integer field and `lastModifiedBy` tracking)
- FLAN sample data: `flan/data/Crisis.json`
- FLAN project template: `flan/templates/project_template.json`
- Excel import templates: `plum/templates/Parts_Import_Template.xlsx`, `plum/templates/Assembly_Template.xlsx`, `plum/templates/Vendors_Import_Template.xlsx`, `flan/templates/phases_template.csv`, `flan/templates/deliveries_template.csv`

**Browser Storage:**
- localStorage — primary runtime persistence for both PLUM and FLAN
  - PLUM stores user config, sync timestamps, part numbering config
  - FLAN stores all project data, user preferences, theme, pinned/recent projects

**File Storage:**
- No cloud file storage API — team sync is manual (download JSON from SharePoint, import into app)

**Caching:**
- None — no Redis or service worker caching

## Authentication & Identity

**Auth Provider:**
- None — no authentication system
- PLUM username stored in `localStorage` key `plmUsername` (user-entered freeform string)
- No login, sessions, or access control

## Team Sync / Collaboration

**SharePoint (manual integration):**
- No SharePoint API — sync is a manual workflow
- PLUM workflow: export `.json` file → upload to SharePoint → teammates download and import
- UI references this workflow in the "Sync" modal (`plum/app/plm_v54.html` ~line 23771)
- Supported attachment link types in PLUM parts: SharePoint URLs, Confluence URLs, Jira URLs, and generic URLs (stored as metadata, not fetched)

**JIRA:**
- No API integration — FLAN supports importing a hierarchical CSV export from Jira (Epic/Task mapping)
- Auth: None

## Import / Export Formats

**PLUM exports:**
- JSON database export (for SharePoint team sync)
- Excel (.xlsx) — parts, filtered parts, selected parts, full database
- Dashboard report (Excel)

**FLAN exports:**
- JSON project export
- CSV (phases, deliveries)
- PDF report (via jsPDF)
- HTML report
- Excel (.xlsx) via SheetJS
- ICS calendar export (`.ics` file, no external calendar API)
- Invoice (rendered HTML)
- JIRA hierarchical CSV import

## Monitoring & Observability

**Error Tracking:**
- None

**Logs:**
- Browser console only (`console.log`, `console.error` in application scripts)
- No structured logging or external log sink

## CI/CD & Deployment

**Hosting:**
- No deployment infrastructure — apps opened directly in a browser from filesystem or any static host
- Version history tracked by archiving previous HTML files into `archive/` directories within each suite

**CI Pipeline:**
- None — no GitHub Actions, CI runners, or automated checks

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Environment Configuration

**Required env vars:**
- None — no environment variables at all

**Secrets location:**
- No secrets — no API keys, tokens, or credentials required

## Browser APIs Used

| API | Suite | Purpose |
|-----|-------|---------|
| `localStorage` | PLUM, FLAN | All runtime persistence |
| `File` / `FileReader` | PLUM, FLAN | Reading uploaded import files |
| `URL.createObjectURL` | PLUM, FLAN | Download links for export files |
| `SVG` (inline DOM) | PLUM | Custom pie, bar, donut, progress ring charts |
| `SVG` / HTML (inline DOM) | FLAN | Gantt chart, pie chart, bar chart |

---

*Integration audit: 2026-06-22*
