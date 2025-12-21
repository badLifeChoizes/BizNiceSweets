# Generate Task from Requirements

Create a task with checklist items derived from specific requirements.

## Usage

```text
/project:from-requirements {requirement-ids...}
```

**Examples:**
- `/project:from-requirements SESS-001 SESS-002 SESS-003`
- `/project:from-requirements DEV-001 DEV-002 DEV-003 DEV-004 DEV-005`
- `/project:from-requirements LP-001 LP-004 LP-005`

## Requirement ID Formats

| Prefix | Feature | Range |
|--------|---------|-------|
| SESS | Sessions | SESS-001 to SESS-045 |
| DEV | Devices | DEV-001 to DEV-039 |
| PART | Participants | PART-001 to PART-030 |
| LP | Lesson Plans | LP-001 to LP-031 |
| PLUG | Plugins | PLUG-001 to PLUG-044 |
| PN | Provider Network | PN-001 to PN-013 |
| ARCH | Architecture | ARCH-001 to ARCH-019 |

## Process

### Step 1: Parse Requirement IDs

Extract requirement IDs from $ARGUMENTS.

Support formats:
- Individual: `SESS-001 SESS-002 SESS-003`
- Range: `SESS-001:SESS-010` (expands to SESS-001 through SESS-010)
- Mixed: `SESS-001 SESS-005:SESS-010 SESS-020`

If no IDs provided:
```text
❌ No requirement IDs provided.

Usage: /project:from-requirements SESS-001 SESS-002
       /project:from-requirements DEV-001:DEV-010  (range)

Browse requirements: @docs/features/requirements.md
```

### Step 2: Validate and Look Up Requirements

1. Read `docs/features/requirements.md`
2. For each requirement ID:
   - Find matching row in the requirements table
   - Extract: ID, Requirement text, Priority, Source link
3. If ID not found, report error:
   ```text
   ⚠️ Unknown requirement ID: {ID}
   Valid IDs for this prefix: {PREFIX}-001 to {PREFIX}-{max}
   ```

### Step 3: Determine Feature and Branch Name

1. Identify primary feature from requirement prefixes:
   - All SESS-* → sessions
   - All DEV-* → devices
   - Mixed prefixes → use most common or prompt user

2. Generate branch name suggestion:
   ```text
   Suggested branch name: feature-{feature}-{descriptive-suffix}

   Examples based on requirements:
   - SESS-001 to SESS-008 → feature-session-lifecycle
   - DEV-006 to DEV-010 → feature-device-discovery
   - PLUG-027 to PLUG-032 → feature-plugin-dependencies

   Enter branch name or press Enter to accept suggestion:
   ```

### Step 4: Check Current Progress

Read `docs/features/requirements-progress.md` and check status of each requirement:

```text
📊 Requirements Status:
- SESS-001: ⬜ Not Started
- SESS-002: ⬜ Not Started
- SESS-003: 🟡 In Progress (on branch: feature-session-states)
- SESS-004: ✅ Completed (PR #42)

⚠️ Note: SESS-003 is already in progress. Include anyway? (y/n)
⚠️ Note: SESS-004 is already completed. Skip? (y/n)
```

### Step 5: Create Task File

Generate `docs/tasks/{branch-name}.md`:

```markdown
# {Humanized Task Name}

**Branch:** `{branch-name}`
**Created:** {today's date}
**Status:** In Progress

## Goal

Implement requirements {first-ID} through {last-ID} for the {feature} feature.

## Related Requirements

<!-- Requirements being implemented -->
- [ ] {ID}: {Requirement text} ({Priority})
- [ ] {ID}: {Requirement text} ({Priority})
- [ ] {ID}: {Requirement text} ({Priority})

**Feature Docs:**
- @docs/features/{feature}.md

## Checklist

- [ ] Review feature documentation: @docs/features/{feature}.md
- [ ] {ID}: {Implementation task derived from requirement}
- [ ] {ID}: {Implementation task derived from requirement}
- [ ] {ID}: {Implementation task derived from requirement}
- [ ] Write/update tests for implemented requirements
- [ ] Update requirements-progress.md with completed items

## Notes

Generated from requirements: {list of IDs}
Source: docs/features/requirements.md
```

### Step 6: Create Branch and Commit

```bash
git checkout -b {branch-name}
git add docs/tasks/{branch-name}.md
git commit -m "chore: start {branch-name}

Implementing requirements: {ID-list}"
```

### Step 7: Report Success

```text
✓ Created task from {count} requirements

Branch: {branch-name}
Task file: docs/tasks/{branch-name}.md

Requirements included:
- {ID}: {brief text} (Must)
- {ID}: {brief text} (Should)
- {ID}: {brief text} (Must)

Feature documentation: @docs/features/{feature}.md

Ready to start. Run /project:status to see your checklist.
```

## Flags

- `--dry-run` : Preview task file without creating branch
- `--no-branch` : Create task file only (use with existing branch)
- `--include-completed` : Include already-completed requirements
- `--must-only` : Only include Must-have priority requirements

## Examples

### Create Task for Session Lifecycle

```text
/project:from-requirements SESS-001 SESS-002 SESS-003 SESS-004 SESS-005 SESS-006 SESS-007 SESS-008
```

Creates `feature-session-lifecycle` with 8 checklist items covering session states and transitions.

### Create Task for Device Discovery (Range)

```text
/project:from-requirements DEV-006:DEV-010
```

Creates `feature-device-discovery` with 5 checklist items covering device scanning and pairing.

### Preview Without Creating

```text
/project:from-requirements PLUG-027:PLUG-032 --dry-run
```

Shows what the task file would contain without creating branch or files.

### Must-Have Requirements Only

```text
/project:from-requirements SESS-001:SESS-045 --must-only
```

Creates task with only the 35 Must-have session requirements (excludes 10 Should-have).