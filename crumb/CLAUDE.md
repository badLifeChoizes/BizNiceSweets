# CRUMB - Project Rules

> Customer Relationship Management Suite (CRM → CRUMB)

## Status: Planned

This suite is not yet implemented. Use this file to track development rules once work begins.

## Task Management

Tasks for CRUMB are tracked in `docs/tasks/`. Each task has a checklist file:

```
docs/tasks/{branch-name}.md
```

Use templates from `docs/tasks/_templates/` when creating new tasks or features.

## Git Workflow

- Branch from: `master`
- Branch naming: `crumb/feature-*`, `crumb/bugfix-*`, `crumb/hotfix-*`
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

## Integration Points

| Suite | Integration |
|-------|-------------|
| SYERP | Customer orders and invoicing |
| FLAN | Customer project tracking |
| CRISP | Customer satisfaction metrics |
