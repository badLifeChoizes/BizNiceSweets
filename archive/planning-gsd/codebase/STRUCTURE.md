# Directory Structure

**Analysis Date:** 2026-06-22

## Top-Level Layout

```
BizNiceSweets/
├── CLAUDE.md              # Project rules: task workflow, commit conventions, feature alignment
├── README.md             # Suite overview and quick start
├── .gitignore
├── .claude/              # Slash commands, hooks, project skills
│   ├── commands/
│   ├── hooks/
│   └── skills/
├── .planning/            # GSD planning artifacts (this codebase map lives in codebase/)
│   └── codebase/
├── docs/                 # Cross-suite documentation
│   ├── features/         # Per-suite feature docs + _templates/
│   ├── interviews/       # Planning interview transcripts
│   ├── reports/          # Analysis reports
│   └── tasks/            # Task checklists (active + _completed/)
├── plum/                 # PLUM  — PLM  (ACTIVE, v54)
├── flan/                 # FLAN  — Project Mgmt (ACTIVE, v24)
├── crumb/                # CRUMB — CRM  (planned)
├── syerp/                # SYERP — ERP  (planned)
├── mousse/               # MOUSSE — MES (planned)
├── crisp/                # CRISP — QMS  (planned)
└── gelato/               # GELATO — WMS (planned)
```

## Per-Suite Structure (standard)

Every suite follows the same layout (active suites populate all of it; planned suites have only `CLAUDE.md` + docs):

```
{suite}/
├── CLAUDE.md       # Suite-specific rules/context
├── app/            # The current single-file application (one HTML file)
├── archive/        # Prior versions of the app (version history)
├── data/           # Database / sample JSON files
├── templates/      # Import/export templates (CSV, JSON)
└── docs/           # Suite documentation (roadmap, readme)
```

Note: not every suite has every folder yet — e.g. `crisp/`, `crumb/`, `gelato/`, `mousse/`, `syerp/` currently carry `app/ data/ templates/ docs/` scaffolding but no application file; only `plum/` and `flan/` have `archive/` with real history.

## Key Locations

| What | Where |
|------|-------|
| PLUM app (current) | `plum/app/plm_v54.html` |
| PLUM database | `plum/data/plm_database.json` (2.7 MB) |
| PLUM version history | `plum/archive/plm_v*.html`, `crisis_plm*.html` |
| FLAN app (current) | `flan/app/prj-mgmt-v24.html` |
| FLAN sample project | `flan/data/Crisis.json` |
| FLAN import templates | `flan/templates/*.csv`, `project_template.json` |
| FLAN version history | `flan/archive/prj-mgmt-v*.html` |
| Per-suite feature docs | `docs/features/{suite}/` (README, architecture, dependencies, INVARIANTS, ROADMAP, usage) |
| Doc templates | `docs/features/_templates/` |
| Suite index | `docs/features/INDEX.md` |
| Active task checklist | `docs/tasks/{branch-name}.md` |
| Completed tasks | `docs/tasks/_completed/{date}-{branch}.md` |
| Task template | `docs/tasks/_template.md` |

## Naming Conventions

- **App files:** `{suite-code}-v{N}.html` (FLAN: `prj-mgmt-v24.html`) or `{abbrev}_v{N}.html` (PLUM: `plm_v54.html`). Naming is **not** uniform across suites — PLUM uses `plm_v##`, FLAN uses `prj-mgmt-v##`.
- **Versioning:** each significant change produces a new numbered file in `app/`, and the prior file is moved to `archive/`. The highest-numbered file in `app/` is the live version.
- **Suite folders:** lowercase dessert codename (`plum`, `flan`, `crumb`, …).
- **Data files:** PascalCase (`Crisis.json`) or `{abbrev}_database.json` (`plm_database.json`).
- **Task files:** named after the git branch (`docs/tasks/{branch-name}.md`); completed ones are prefixed with date.
- **Docs:** per-suite docs use a fixed set of filenames mirrored from `docs/features/_templates/` (`README.md`, `architecture.md`, `dependencies.md`, `INVARIANTS.md`, `ROADMAP.md`, `usage.md`).

## Where to Add New Code

- **New feature in an existing suite:** edit the current `app/{suite}-v{N}.html` directly, or, for a release, copy it to `v{N+1}` and move the old file to `archive/`. Locate the relevant domain module (`const X = {...}`) and its `renderX()` view function.
- **New suite (activating a planned one):** create `app/{suite}-v1.html` following the single-file pattern; populate `data/`, `templates/`; add docs under `docs/features/{suite}/` from `_templates/`.
- **New documentation:** suite-scoped → `docs/features/{suite}/`; cross-suite → `docs/`.
- **New task:** create `docs/tasks/{branch-name}.md` from `_template.md` before starting work (required by `CLAUDE.md`).

## Notable Characteristics

- **Archive sprawl:** `plum/archive/` and `flan/archive/` hold 20+ historical HTML versions each — full copies, so the repo carries significant duplicated bulk.
- **Single source of truth per suite:** the live file is whichever has the highest version number in `app/`; tooling/docs must be kept pointing at it (README currently references `plm_v54.html` and `prj-mgmt-v24.html`).

---

*Structure analysis: 2026-06-22*