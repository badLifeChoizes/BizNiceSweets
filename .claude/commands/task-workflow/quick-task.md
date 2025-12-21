# Quick Task

Quickly capture a new task without interrupting current work. Includes lightweight requirements detection.

Use when you discover something that needs doing but don't want to context-switch.

## Usage

```text
/project:quick-task {type}-{name} "{brief description}"
```

## Examples

```text
/project:quick-task bugfix-null-check "Handle null user in dashboard"
/project:quick-task feature-export "Add CSV export to reports"
/project:quick-task refactor-queries "Consolidate duplicate SQL queries"
```

## Process

### 1. Stay on Current Branch

Do NOT switch branches - this is a capture-only operation.

### 2. Quick Requirements Detection

**Lightweight detection** (non-blocking):

a. Analyze branch name + description for keywords
b. Quick-match against feature keywords (no full requirements search)
c. Store detected feature and suggested prefix in task file

```text
📌 Quick-capturing: feature-export

Detected feature: Sessions (keywords: export, csv)
Suggested requirements: SESS-036 to SESS-039 (export-related)

These will be confirmed when you start the task.
```

### 3. Create Minimal Task File

Create `docs/tasks/{type}-{name}.md`:

```markdown
# {Name humanized}

**Branch:** `{type}-{name}`
**Created:** {today}
**Status:** Pending
**Priority:** Normal

## Goal

{description from command}

## Related Requirements

<!-- Auto-detected: {feature} feature -->
<!-- Suggested: {PREFIX}-* requirements -->
<!-- Run /project:start-task to confirm and populate -->

**Detected Feature:** {feature-name}
**Feature Doc:** @docs/features/{feature}.md

## Checklist

- [ ] Confirm requirements (run /project:start-task)
- [ ] Implement solution
- [ ] Test changes
- [ ] Update relevant docs

## Notes

Quick-captured during work on: {current-branch}
Detection confidence: {high/medium/low/none}
```

### 4. Handle No Feature Match

If no feature detected:

```markdown
## Related Requirements

<!-- No feature auto-detected -->
<!-- Options when starting task:
     1. Search requirements manually
     2. Create new feature
     3. Proceed without requirements
-->

**Detected Feature:** None
**Suggestion:** Run /project:start-task to search or create requirements

## Checklist

- [ ] Determine feature scope (run /project:start-task)
- [ ] Implement solution
- [ ] Test changes
```

### 5. Report Without Disrupting Flow

```text
📌 Captured: {type}-{name}
   "{description}"

   Detected: {feature} feature ({confidence})
   Requirements: Will be confirmed on start

   Continue current work. Start later with:
   /project:start-task {type}-{name}
```

## Quick Capture Aliases

For even faster capture, recognize shorthand:

- `bug:` → `bugfix-`
- `feat:` → `feature-`
- `fix:` → `bugfix-`
- `ref:` → `refactor-`
- `doc:` → `docs-`

Example:
```text
/project:quick-task bug:null-user "Crashes when user is null"
```
Creates: `docs/tasks/bugfix-null-user.md`

## Batch Quick Capture

If multiple items separated by `|`:
```text
/project:quick-task batch "bug:thing1 | feat:thing2 | fix:thing3"
```

Creates three separate task files, all marked as Pending.
Each gets its own quick detection.

## Priority Flag

Add priority inline:
```text
/project:quick-task bug:security-hole "SQL injection in search" !high
/project:quick-task feat:nice-to-have "Dark mode" !low
```

Sets Priority field in task file accordingly.

## Detection Behavior by Task Type

| Type | Detection Behavior |
|------|-------------------|
| `feature-*` | Full detection - match feature + suggest requirements |
| `bugfix-*` | Search for related requirements as reference |
| `hotfix-*` | Minimal detection - focus on speed |
| `refactor-*` | Skip detection - typically no requirements |
| `docs-*` | Skip detection - documentation task |

## Integration with start-task

When user later runs `/project:start-task {task-name}`:

1. Read the quick-captured task file
2. Check `Detected Feature` field
3. If feature detected:
   - Run full requirements detection
   - Populate `## Related Requirements` section
   - Show confirmation before starting work
4. If no feature detected:
   - Prompt user to search, create, or skip
5. Create branch and begin work

This ensures quick capture is fast, but requirements are always confirmed before implementation.
