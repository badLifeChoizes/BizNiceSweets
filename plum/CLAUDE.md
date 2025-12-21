# PLUM - Project Rules

> Product Lifecycle Management Suite

## Task Management

Tasks for PLUM are tracked in `docs/tasks/`. Each task has a checklist file:

```
docs/tasks/{branch-name}.md
```

Use templates from `docs/tasks/_templates/` when creating new tasks or features.

## Git Workflow

- Branch from: `master` or `chore-suite-structure` (current)
- Branch naming: `plum/feature-*`, `plum/bugfix-*`, `plum/hotfix-*`
- Commits: conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`)

## Before Every Commit

1. Update the checklist in `docs/tasks/{branch-name}.md`
2. Stage relevant files
3. Write conventional commit message
4. Confirm: "Checklist updated | Committed"

## Feature Documentation

Features are documented in `docs/features/`. Use templates:

| Template | Purpose |
|----------|---------|
| `_templates/feature-readme.md` | Feature overview and status |
| `_templates/architecture.md` | Data models, state machines, APIs |
| `_templates/dependencies.md` | Integration points with other suites |
| `_templates/invariants.md` | Rules that must never be violated |
| `_templates/usage.md` | User workflows and examples |

## Finishing a Task

1. Verify all checklist items are checked
2. Run tests if applicable
3. Move task file to `docs/tasks/_completed/{date}-{branch-name}.md`

## Key Files

| File | Purpose |
|------|---------|
| `app/plm_v54.html` | Current application |
| `archive/` | Version history |
| `data/plm_database.json` | Database |
| `docs/PLM_FEATURE_ROADMAP.md` | Feature roadmap |
