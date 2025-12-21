Migrate an existing implementation plan into the new task-based workflow.

## Input

$ARGUMENTS should be the path to the legacy implementation plan file.
If empty, look for common names:
- implementation-plan.md
- implementation-progress-checklist.md
- IMPLEMENTATION.md
- TODO.md
- docs/implementation-plan.md

## Process

### Step 1: Analyze the Legacy Plan

Read the file and identify:
- Logical groupings (features, bugfixes, refactors, docs)
- Dependencies between items
- Current completion status of each item
- Estimated complexity (small/medium/large based on description)

### Step 2: Propose Task Breakdown

Group related checklist items into discrete tasks. Each task should:
- Be completable in 1-3 focused sessions
- Have a clear, single goal
- Follow naming convention: `feature-*`, `bugfix-*`, `refactor-*`, `docs-*`

Present the breakdown to the user:

```
## Proposed Migration

Found {n} items in legacy plan. Proposing {m} tasks:

### 1. feature-user-auth (Medium - ~3 items)
- [ ] Implement JWT token generation
- [ ] Add refresh token endpoint  
- [ ] Update auth middleware
Status: 0/3 complete

### 2. bugfix-login-validation (Small - ~2 items)
- [x] Fix email validation regex
- [ ] Add rate limiting
Status: 1/2 complete

### 3. refactor-api-structure (Large - ~5 items)
- [ ] Extract route handlers
- [ ] Create service layer
- [ ] Add dependency injection
- [ ] Update tests
- [ ] Update API docs
Status: 0/5 complete

---
Proceed with this breakdown? (yes/no/modify)
```

### Step 3: Handle User Response

**If "yes"**: Proceed to Step 4

**If "modify"**: Ask what changes they want:
- Combine tasks?
- Split a task further?
- Rename?
- Change grouping?

**If "no"**: Ask for guidance on how they'd prefer to group items

### Step 4: Create Task Files

For each proposed task:

1. Create the task file at `docs/tasks/{task-name}.md`:

```markdown
# {Task Title}

**Branch:** `{task-name}`
**Created:** {today}
**Status:** In Progress
**Migrated from:** {legacy-file-path}

## Goal

{Inferred goal from grouped items}

## Checklist

{Migrated items, preserving [x] status}

## Notes

- Migrated from legacy implementation plan
- Original location: {legacy-file-path}
```

2. Do NOT create branches yet (user may want to prioritize first)

### Step 5: Update Legacy File

Add a migration notice to the top of the original file:

```markdown
> ⚠️ **MIGRATED**: This plan has been broken into individual task files.
> See `docs/tasks/` for the new workflow.
> 
> Migrated on: {date}
> Tasks created: {list of task names}

---

{original content preserved below for reference}
```

### Step 6: Report Summary

```
✓ Migration complete!

Created {n} task files:
- docs/tasks/feature-user-auth.md (0/3)
- docs/tasks/bugfix-login-validation.md (1/2)
- docs/tasks/refactor-api-structure.md (0/5)

Legacy file marked as migrated: {path}

## Next Steps

1. Review task files in docs/tasks/
2. Prioritize which task to start first
3. Start a task with: /project:start-task {task-name}
   (This creates the branch and sets it as active)

Or list all tasks with: /project:list-tasks
```

## Edge Cases

**Mixed completion states**: If a logical group has some items done and some not, keep them together but preserve the [x] marks.

**Orphan items**: Items that don't fit a clear group become their own small task, or ask user where to place them.

**Already-done sections**: If an entire logical group is 100% complete, ask user:
- Create as completed task in `_completed/`?
- Skip entirely?

**Very large groups**: If a group has >7 items, suggest splitting further:
```
⚠️ "feature-api-v2" has 12 items. Consider splitting:
- feature-api-v2-endpoints (6 items)
- feature-api-v2-auth (4 items)  
- feature-api-v2-docs (2 items)
```

**Dependencies**: If items have explicit dependencies, note them in the task file:
```markdown
## Dependencies
- Requires: feature-user-auth (must complete first)
- Blocks: feature-dashboard
```
