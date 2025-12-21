# Create New Task

Create a new task branch and checklist file with auto-detected requirements.

## Usage

```text
/project:new-task {branch-name} [goal description]
```

**Examples:**
- `/project:new-task feature-session-export`
- `/project:new-task feature-device-firmware "Add OTA firmware updates"`
- `/project:new-task bugfix-null-participant`

## Steps

### 1. Parse Input

Parse the task name from: $ARGUMENTS
- If empty, ask user for a task name
- Ensure it follows naming convention: `feature-*`, `bugfix-*`, `hotfix-*`, `refactor-*`
- Extract optional goal description if provided in quotes

### 2. Auto-Detect Requirements

**Use the detect-requirements helper** (see [detect-requirements.md](detect-requirements.md)):

a. Analyze branch name for feature keywords
b. If goal provided, analyze goal text for additional keywords
c. Search `docs/features/requirements.md` for matching requirements
d. Score and rank results

**Handle detection results:**

#### High Confidence Match

```text
🎯 Detected Feature: Sessions

Auto-selected Requirements (based on "session-export"):
- [ ] SESS-036: System SHALL support PDF export format (Must)
- [ ] SESS-037: System SHALL support CSV export format (Must)
- [ ] SESS-038: System SHALL support JSON export format (Must)
- [ ] SESS-039: Plugins SHALL extend export with custom formats (Should)

Feature doc: @docs/features/sessions.md

✓ Accept  |  ✎ Edit selection  |  ✗ Skip requirements
```

#### Ambiguous Match (Multiple Features)

```text
⚠️ Multiple features match "feature-export-tools":

1. Sessions (export formats)
   → SESS-036, SESS-037, SESS-038, SESS-039

2. Plugins (export tool plugins)
   → PLUG-002: Export Tool plugins

Select primary feature: (1/2/both)
```

#### Low Confidence / No Match

```text
⚠️ No clear feature match for: feature-analytics

Options:
1. Run discovery interview (recommended for new features)
   → Uses /interview discovery to gather requirements
   → Creates feature doc with proper requirements
   → See: .claude/skills/interview/SKILL.md

2. Create new feature documentation
   → Creates docs/features/analytics.md stub
   → Generates placeholder requirements (ANALYTICS-001, etc.)

3. Select from existing features manually
   → Shows feature list

4. Proceed without requirements
   → Task will not track requirement progress

Choice (1/2/3/4):
```

**When using discovery interview (Option 1):**

The interview skill will:
1. Ask clarifying questions one at a time
2. Capture requirements with proper IDs
3. Record decisions with rationale
4. Create the feature doc and task file together

This is recommended for new features where scope is unclear.

### 3. Create Branch

```bash
git checkout -b $ARGUMENTS
```

### 4. Generate Task File

Create `docs/tasks/$ARGUMENTS.md` with auto-populated content:

```markdown
# {Task Name (humanized from branch)}

**Branch:** `{branch-name}`
**Created:** {today's date}
**Status:** In Progress

## Goal

{Goal from user input OR inferred from branch name}

## Related Requirements

{Auto-populated from detect-requirements}
- [ ] {REQ-ID}: {Requirement text} ({Priority})
- [ ] {REQ-ID}: {Requirement text} ({Priority})
- [ ] {REQ-ID}: {Requirement text} ({Priority})

**Feature Docs:**
- @docs/features/{detected-feature}.md

## Checklist

- [ ] Review feature documentation: @docs/features/{feature}.md
- [ ] {REQ-ID}: {Implementation task for requirement}
- [ ] {REQ-ID}: {Implementation task for requirement}
- [ ] {REQ-ID}: {Implementation task for requirement}
- [ ] Write/update tests
- [ ] Update requirements-progress.md

## Notes

Auto-detected from branch: {branch-name}
Requirements source: docs/features/requirements.md
```

### 5. Stage and Commit

```bash
git add docs/tasks/$ARGUMENTS.md
git commit -m "chore: start $ARGUMENTS

Requirements: {comma-separated list of IDs}"
```

### 6. Report Success

```text
✓ Created branch: {branch-name}
✓ Created checklist: docs/tasks/{branch-name}.md
✓ Auto-detected feature: {feature-name}
✓ Linked requirements: {count} items

Requirements included:
- {REQ-ID}: {brief text}
- {REQ-ID}: {brief text}
- {REQ-ID}: {brief text}

Feature documentation: @docs/features/{feature}.md

Ready to work. Run /project:status to see your checklist.
```

## Flags

- `--no-detect` : Skip auto-detection, use empty requirements section
- `--requirements {IDs}` : Explicitly specify requirements (skip detection)
- `--feature {name}` : Explicitly specify feature (narrows detection)
- `--dry-run` : Preview task file without creating

## Special Cases

### Bugfix Branches

For `bugfix-*` branches, detection searches for related requirements:

```text
/project:new-task bugfix-session-timer-drift

🔧 Bugfix detected. Searching for related requirements...

Possibly related:
- SESS-009: Session timer SHALL display elapsed time in HH:MM:SS
- SESS-010: Session timer SHALL exclude paused periods
- SESS-012: Timer SHALL stop during paused state and resume

Include these as reference? (y/n)
```

If included, they're marked as **reference** (not implemented):

```markdown
## Related Requirements

**Implementing fix for:**
- SESS-009: Session timer display format (reference)
- SESS-010: Timer pause exclusion (reference)

**Note:** This is a bugfix - requirements are for reference only.
```

### Refactor Branches

For `refactor-*` branches, no requirements typically needed:

```text
/project:new-task refactor-session-queries

🔄 Refactor detected. Requirements typically not applicable.

Proceed without requirements? (y/skip to search anyway)
```

### No Matching Feature - Create New

When user chooses to create new feature:

```text
Choice: 1 (Create new feature)

Creating: docs/features/analytics.md

Enter feature description: "Usage analytics and reporting dashboard"

Generated stub with:
- Overview section
- Placeholder requirements: ANALYTICS-001 to ANALYTICS-005
- Integration points (TBD)

Also updating:
- docs/features/requirements.md (new section)
- docs/features/requirements-progress.md (new tracking)
- docs/features/INDEX.md (feature list)

Continue? (y/n)
```