# Task Checklists

This folder contains task checklists that correspond to git branches.

## Structure

```
tasks/
├── {branch-name}.md        # Active task checklists
├── _template.md            # Template for new tasks
└── _completed/             # Archived completed tasks
    └── {date}-{branch}.md
```

## Workflow

1. Create new task: `/project:new-task feature-something`
2. Check status: `/project:status`
3. Complete task: `/project:finish-task`

## Naming Convention

Task files match their branch names:
- `feature-user-auth.md` → branch `feature-user-auth`
- `bugfix-login-crash.md` → branch `bugfix-login-crash`
