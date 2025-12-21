# Start Task

Start working on an existing task. Auto-populates requirements if missing.

Use this when picking up a task that already has a file (e.g., from quick-task or migration).

## Input

```text
$ARGUMENTS = task name (e.g., "feature-user-auth")
```

If empty, show available tasks and prompt for selection.

## Process

### Step 1: Find the Task File

Look for `docs/tasks/$ARGUMENTS.md`

If not found:
```text
❌ No task file found: docs/tasks/$ARGUMENTS.md

Available tasks:
- feature-user-auth (2/5 complete) - Sessions
- bugfix-login-crash (0/3 complete) - No feature
- feature-export (0/4 complete) - Sessions [pending requirements]

Usage: /project:start-task feature-user-auth
```

### Step 2: Check Git State

```bash
# Check if branch already exists
git branch --list $ARGUMENTS

# Check for uncommitted changes
git status --porcelain
```

If uncommitted changes exist:
```text
⚠️ You have uncommitted changes on current branch.

Options:
1. Stash changes and continue: git stash
2. Commit current work first: /project:checkpoint
3. Abort and stay on current branch

What would you like to do?
```

### Step 3: Check Requirements Status

Read the task file and check `## Related Requirements` section:

#### Case A: Requirements Already Populated

```text
✓ Requirements found: SESS-036, SESS-037, SESS-038

Proceeding to start task...
```

#### Case B: Quick-Captured Task (Detected Feature, No Requirements)

If task has `**Detected Feature:**` but no requirement IDs:

```text
📋 This task was quick-captured with detected feature: Sessions

Running full requirements detection...

🎯 Suggested Requirements (based on "export csv reports"):
- [ ] SESS-036: System SHALL support PDF export format (Must) ⬜
- [ ] SESS-037: System SHALL support CSV export format (Must) ⬜
- [ ] SESS-038: System SHALL support JSON export format (Must) ⬜
- [ ] SESS-039: Plugins SHALL extend export formats (Should) ⬜

Feature doc: @docs/features/sessions.md

✓ Accept all  |  ✎ Edit selection  |  + Add more  |  ✗ Skip
```

After selection, update the task file with populated requirements.

#### Case C: No Detected Feature

If task has `**Detected Feature:** None`:

```text
⚠️ No feature was detected for this task.

Analyzing task goal: "Add user notifications system"

Options:
1. Search existing requirements
   → Scanning requirements.md for matches...
   → Found: SESS-028 (alert notifications) - weak match

2. Create new feature
   → Will create: docs/features/notifications.md
   → Will generate: NOTIF-001 to NOTIF-005 requirements

3. Proceed without requirements
   → Task will not update requirements-progress.md

Choice (1/2/3):
```

#### Case D: Legacy Task (No Requirements Section)

If task file has no `## Related Requirements` section at all:

```text
📋 Legacy task format detected (no requirements section)

Would you like to add requirements tracking?
1. Yes - detect and add requirements
2. No - keep legacy format

Choice (1/2):
```

If yes, run detection and insert the section.

### Step 4: Create or Switch to Branch

If branch doesn't exist:
```bash
git checkout -b $ARGUMENTS
```

If branch exists:
```bash
git checkout $ARGUMENTS
```

### Step 5: Update ACTIVE_TASK.md (if using)

If `ACTIVE_TASK.md` exists in project root, update it:
```markdown
# Current Focus
- @docs/tasks/$ARGUMENTS.md

# Last Updated
{timestamp}
```

### Step 6: Show Task Status

Read the task file and display:

```text
✓ Now working on: $ARGUMENTS

## Goal
{goal from task file}

## Feature: {detected/selected feature}
📖 @docs/features/{feature}.md

## Related Requirements
- [ ] SESS-036: PDF export (Must) ⬜
- [ ] SESS-037: CSV export (Must) ⬜
- [ ] SESS-038: JSON export (Must) ⬜

## Progress: {done}/{total} ({percentage}%)

### Next Items
- [ ] Review feature documentation
- [ ] SESS-037: Implement CSV export
```

### Step 6b: Offer Planning Interview (Complex Tasks)

For tasks with 3+ requirements, offer a planning interview:

```text
📋 This task has {count} requirements to implement.

Would you like to run a planning interview first?
1. Yes - plan implementation approach (recommended for complex tasks)
   → Uses /interview planning to structure the work
   → Creates ordered checklist with architecture decisions
   → See: .claude/skills/interview/SKILL.md

2. No - start working directly
   → Use existing checklist items
   → Good for straightforward implementations

Choice (1/2):
```

**When using planning interview (Option 1):**

The interview skill will:

1. Confirm scope and out-of-scope items
2. Ask architecture/implementation questions one at a time
3. Break down requirements into ordered checklist items
4. Record key decisions with rationale

The resulting checklist is added to the task file.

### Step 7: Preflight Check (INVARIANTS)

Check if INVARIANTS documentation exists for the detected feature:

```text
docs/features/{feature}/INVARIANTS.md
```

#### If INVARIANTS Exist:

Load and display INVARIANTS summary:

```text
---

📋 PREFLIGHT CHECK

## Primary Feature: {Feature Name}
   INVARIANTS: @docs/features/{feature}/INVARIANTS.md
   Rules: {count} (read before implementing)

## Most Critical Invariants:
   1. {First critical rule from INVARIANTS.md}
   2. {Second critical rule from INVARIANTS.md}
   3. {Third critical rule from INVARIANTS.md}

## Cross-Feature Dependencies:
```

Check the feature's `dependencies.md` or use built-in mapping:

| Feature | Dependencies |
|---------|--------------|
| sessions | devices, participants, bento-grid |
| devices | plugins |
| plugins | devices |
| participants | (none) |
| lesson-plans | (none) |
| *-ui, bento, grid, tile, layout | bento-grid |

For each dependency that has INVARIANTS:

```text
   ⚠️ {Dependency Name}:
      INVARIANTS: @docs/features/{dep}/INVARIANTS.md ({count} rules)
```

Total rules count:

```text
## Total: {sum of all invariant counts} rules must not be violated.

Have you reviewed these INVARIANTS? Proceeding assumes you have.

---
Ready to work. Use /project:checkpoint after completing each item.
```

#### If INVARIANTS Don't Exist (Legacy Mode):

Fall back to archived feature doc reference:

```text
---
📖 Feature doc: @docs/features/_archive/{feature}.md

Ready to work. Use /project:checkpoint after completing each item.
```

### Step 8: Log Preflight Acknowledgment

If restructured docs were shown, log to task file (optional):

Add a section or comment to the task file:

```markdown
## Preflight Acknowledged
- Date: {timestamp}
- Primary INVARIANTS: {feature}/INVARIANTS.md ({count} rules)
- Dependencies: {list}
- Total rules: {count}
```

This helps track that the AI acknowledged the invariants before starting work.

## Quick Start Options

### Pick Next Task

If $ARGUMENTS is "next" or "pick":
```text
/project:start-task next
```

- Show all incomplete tasks sorted by progress (most complete first)
- Include requirements status indicator
- Let user pick which to start

```text
Available tasks (sorted by progress):

1. feature-user-auth (4/5 - 80%) ✓ Requirements
   → Sessions: SESS-001, SESS-002

2. feature-export (2/4 - 50%) ✓ Requirements
   → Sessions: SESS-036, SESS-037

3. bugfix-timer-drift (0/3 - 0%) ⚠️ Pending requirements
   → Detected: Sessions

4. feature-analytics (0/5 - 0%) ❌ No feature
   → Needs: Feature creation or selection

Select task (1-4):
```

### Pick by Feature

If $ARGUMENTS is "feature:{name}":
```text
/project:start-task feature:sessions
```

Shows only tasks related to sessions feature.

## Flags

- `--no-requirements` : Skip requirements check/detection
- `--force` : Start even with uncommitted changes (stashes automatically)
- `--new` : If task doesn't exist, create it (delegates to new-task)