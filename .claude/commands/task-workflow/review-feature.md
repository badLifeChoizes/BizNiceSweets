# Review Feature Documentation

Review relevant feature documentation before starting work on a feature.

## Usage

```text
/project:review-feature {feature-name}
```

**Examples:**
- `/project:review-feature sessions`
- `/project:review-feature devices`
- `/project:review-feature participants`

## Feature Mapping

| Feature Name | Documentation File | Requirements Prefix |
|--------------|-------------------|---------------------|
| sessions | docs/features/sessions.md | SESS-* |
| devices | docs/features/devices.md | DEV-* |
| participants | docs/features/participants.md | PART-* |
| lesson-plans | docs/features/lesson-plans.md | LP-* |
| plugins | docs/features/plugins.md | PLUG-* |
| provider-network | docs/features/provider-network.md | PN-* |
| architecture | docs/features/INDEX.md | ARCH-* |

## Process

### Step 1: Validate Feature Name

Parse $ARGUMENTS to identify the feature.

If empty or not recognized:
```text
❌ Unknown feature: {input}

Available features:
- sessions (SESS-001 to SESS-045)
- devices (DEV-001 to DEV-039)
- participants (PART-001 to PART-030)
- lesson-plans (LP-001 to LP-031)
- plugins (PLUG-001 to PLUG-044)
- provider-network (PN-001 to PN-013)
- architecture (ARCH-001 to ARCH-019)

Usage: /project:review-feature sessions
```

### Step 2: Read Feature Documentation

**Check for feature folder:**

1. Check if `docs/features/{feature}/` exists (structured docs)
2. If yes, read structured docs (preferred)
3. If no, fall back to archived docs in `docs/features/_archive/`

**Structured docs (preferred):**

1. Read: `docs/features/{feature}/README.md`
2. Read: `docs/features/{feature}/INVARIANTS.md` (critical!)
3. Read: `docs/features/{feature}/dependencies.md`
4. Read: `docs/features/{feature}/architecture.md`
5. Read: `docs/features/{feature}/usage.md`

**Archived docs (fallback):**

1. Read the archived documentation file: `docs/features/_archive/{feature}.md`
2. Read relevant terms from: `docs/features/GLOSSARY.md`
3. Read requirements from: `docs/features/requirements.md` (filter by prefix)
4. Read current progress from: `docs/features/requirements-progress.md`

### Step 3: Generate Summary

**If using structured docs:**

```text
## Feature: {Feature Name}

### Overview
{First paragraph from README.md}

---

### INVARIANTS ({count} rules)

**CRITICAL - Read before implementing:**
@docs/features/{feature}/INVARIANTS.md

**Most Critical Rules:**
1. {First rule from INVARIANTS.md}
2. {Second rule from INVARIANTS.md}
3. {Third rule from INVARIANTS.md}

**Common Violations to Watch:**
- {First common violation}
- {Second common violation}
- {Third common violation}

---

### Cross-Feature Dependencies

**This feature depends on:**
{From dependencies.md}

| Feature | Why | INVARIANTS |
|---------|-----|------------|
| {dep1} | {reason} | @.../{dep1}/INVARIANTS.md ({count} rules) |
| {dep2} | {reason} | @.../{dep2}/INVARIANTS.md ({count} rules) |

**Other features depend on this:**
{From dependencies.md - what they expect}

---

### Requirements Summary
- **Total:** {count} requirements
- **Completed:** {count} ({percentage}%)
- **In Progress:** {count}
- **Not Started:** {count}

### Key Architecture Points
{From architecture.md - data model, state machine, events}

---
📖 Full docs: @docs/features/{feature}/
⚠️ INVARIANTS: @docs/features/{feature}/INVARIANTS.md
📋 Requirements: @docs/features/requirements.md#{prefix}
```

**If using archived docs (fallback):**

```text
## Feature: {Feature Name}

### Overview
{First paragraph from feature doc}

### Key Terms (from Glossary)
| Term | Definition |
|------|------------|
| {term1} | {brief definition} |
| {term2} | {brief definition} |

### Requirements Summary
- **Total:** {count} requirements
- **Must Have:** {count}
- **Should Have:** {count}
- **Completed:** {count} ({percentage}%)
- **In Progress:** {count}
- **Not Started:** {count}

### Must-Have Requirements
| ID | Requirement | Status |
|----|-------------|--------|
| {ID} | {brief requirement} | ⬜/🟡/✅ |

### Integration Points
- **Depends On:** {list from feature doc}
- **Provides To:** {list from feature doc}

### Edge Cases to Handle
{List from feature doc's Edge Cases section}

---
📖 Full documentation: @docs/features/{feature}.md
📋 All requirements: @docs/features/requirements.md#{prefix}
```

### Step 4: Suggest Next Actions

Based on current context:

**If on a matching feature branch:**
```text
Ready to implement. Your task file: docs/tasks/{branch}.md

Suggested workflow:
1. Add requirements to your task's "Related Requirements" section
2. Implement checklist items
3. Run /project:checkpoint after each item
4. Update requirements-progress.md when requirements complete
```

**If on main/master:**
```text
To start working on {feature}:
1. /project:new-task feature-{feature}-{description}
2. Select which requirements to implement
3. Begin development
```

## Flags

- `--full` : Show complete requirements list (not just Must-Have)
- `--progress` : Focus on implementation progress only
- `--terms` : Show extended glossary terms

## Examples

### Basic Review
```text
/project:review-feature sessions
```
Shows overview, key terms, must-have requirements, and integration points.

### Full Requirements List
```text
/project:review-feature devices --full
```
Shows all 39 device requirements with current status.

### Progress Check
```text
/project:review-feature plugins --progress
```
Shows only the implementation progress breakdown.