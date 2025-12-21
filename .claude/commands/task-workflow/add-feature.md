# Add Feature

Create new feature documentation and requirements when a task doesn't map to existing features.

## Usage

```text
/project:add-feature {feature-name} "{description}"
```

**Examples:**
- `/project:add-feature analytics "Usage analytics and reporting dashboard"`
- `/project:add-feature notifications "User notification system for alerts and updates"`
- `/project:add-feature integrations "Third-party service integrations"`

## When to Use

This command is triggered automatically when:
- `/project:new-task` detects no matching feature
- `/project:start-task` finds a task with no feature
- User explicitly wants to create a new feature area

## Process

### Step 1: Validate Feature Name

```text
Feature name: analytics
Prefix will be: ANALYTICS (or ANLT for shorter IDs)

Checking for conflicts...
✓ No existing feature named "analytics"
✓ Prefix ANLT is available
```

If conflict:
```text
⚠️ Feature "analytics" already exists: docs/features/analytics.md

Options:
1. Add requirements to existing feature
2. Choose different name
3. Cancel

Choice (1/2/3):
```

### Step 2: Gather Requirements

Requirements can be gathered in two ways:

#### Option A: Discovery Interview (Recommended)

Use the interview skill for structured requirements gathering:

```text
📋 Creating requirements for: Analytics

Starting discovery interview...
See: .claude/skills/interview/SKILL.md

The interview will:
1. Ask clarifying questions one at a time
2. Present options with pros/cons
3. Record each requirement with rationale
4. Assign proper requirement IDs
```

The discovery interview ensures:
- Requirements are well-thought-out with context
- Decisions are documented with rationale
- Edge cases are considered
- Priority is explicitly decided for each requirement

#### Option B: Quick Entry (For Simple Features)

For straightforward features, use quick entry:

```text
📋 Creating requirements for: Analytics

Enter requirements (one per line, empty line when done):
- Format: "{description}" or "Users SHALL be able to {action}"
- Type !must or !should to set priority (default: Should)

> View dashboard with usage metrics !must
> Filter analytics by date range !must
> Export analytics data to CSV
> View per-session analytics
> Compare analytics across time periods
>

Captured 5 requirements:
- ANLT-001: View dashboard with usage metrics (Must)
- ANLT-002: Filter analytics by date range (Must)
- ANLT-003: Export analytics data to CSV (Should)
- ANLT-004: View per-session analytics (Should)
- ANLT-005: Compare analytics across time periods (Should)

Continue? (y/edit/cancel)
```

### Step 3: Create Feature Documentation

Generate `docs/features/{feature-name}.md`:

```markdown
# Analytics

## Overview

{description from command}

## User Experience

### Core Capabilities

<!-- TODO: Expand based on requirements -->
1. View usage metrics dashboard
2. Filter and analyze data
3. Export analytics

### User Workflows

<!-- TODO: Define user workflows -->

## Architecture

### Data Model

<!-- TODO: Define data structures -->

### Integration Points

- **Depends On:** Sessions (usage data source)
- **Provides To:** Dashboard (analytics tiles)

## Edge Cases

<!-- TODO: Identify edge cases -->

## Requirements

See [requirements.md](requirements.md#analytics-anlt) for full requirements list.

| ID | Requirement | Priority |
|----|-------------|----------|
| ANLT-001 | View dashboard with usage metrics | Must |
| ANLT-002 | Filter analytics by date range | Must |
| ANLT-003 | Export analytics data to CSV | Should |
| ANLT-004 | View per-session analytics | Should |
| ANLT-005 | Compare analytics across time periods | Should |
```

### Step 4: Update Requirements Files

#### Add to requirements.md

Append new section:

```markdown
---

## Analytics (ANLT)

### Core Analytics

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| ANLT-001 | Users SHALL be able to view dashboard with usage metrics | Must | [analytics.md](analytics.md) |
| ANLT-002 | Users SHALL be able to filter analytics by date range | Must | [analytics.md](analytics.md) |
| ANLT-003 | Users SHALL be able to export analytics data to CSV | Should | [analytics.md](analytics.md) |
| ANLT-004 | Users SHALL be able to view per-session analytics | Should | [analytics.md](analytics.md) |
| ANLT-005 | Users SHALL be able to compare analytics across time periods | Should | [analytics.md](analytics.md) |
```

#### Add to requirements-progress.md

Append new tracking section:

```markdown
---

## Analytics (ANLT)

### Core Analytics

| ID | Status | Requirement | Notes | PR/Commit |
|----|--------|-------------|-------|-----------|
| ANLT-001 | ⬜ | View dashboard with usage metrics | | |
| ANLT-002 | ⬜ | Filter analytics by date range | | |
| ANLT-003 | ⬜ | Export analytics data to CSV | | |
| ANLT-004 | ⬜ | View per-session analytics | | |
| ANLT-005 | ⬜ | Compare analytics across time periods | | |
```

Also update the Progress Summary table at the top.

#### Update INDEX.md

Add to feature list:

```markdown
| Analytics | [analytics.md](analytics.md) | Usage analytics and reporting dashboard |
```

Add to Feature Relationships diagram if applicable.

#### Update GLOSSARY.md

Add relevant terms:

```markdown
## Analytics Terms

| Term | Definition | See Also |
|------|------------|----------|
| **Analytics Dashboard** | Central view for usage metrics and statistics | [analytics.md](analytics.md) |
```

### Step 5: Update Detection Keywords

Add to `.claude/feature-mappings.json` (creates if doesn't exist):

```json
{
  "analytics": {
    "doc": "docs/features/analytics.md",
    "prefix": "ANLT",
    "keywords": ["analytics", "metrics", "statistics", "usage", "report", "dashboard", "chart", "graph", "trend"]
  }
}
```

This file is automatically loaded by the inject-task-context hook, so the new feature will be detected immediately on future branch names containing "analytics".

### Step 6: Report Success

```text
✓ Created feature: Analytics

Files created/updated:
- docs/features/analytics.md (new)
- docs/features/requirements.md (5 requirements added)
- docs/features/requirements-progress.md (tracking added)
- docs/features/INDEX.md (feature listed)
- docs/features/GLOSSARY.md (terms added)

Requirements created:
- ANLT-001: View dashboard with usage metrics (Must)
- ANLT-002: Filter analytics by date range (Must)
- ANLT-003: Export analytics data to CSV (Should)
- ANLT-004: View per-session analytics (Should)
- ANLT-005: Compare analytics across time periods (Should)

To start working on this feature:
/project:new-task feature-analytics-dashboard

Or add more requirements:
/project:add-feature analytics --add-requirements
```

## Flags

- `--dry-run` : Preview changes without creating files
- `--add-requirements` : Add requirements to existing feature
- `--from-task {task}` : Create feature based on existing task's goal
- `--prefix {PREFIX}` : Use custom requirement prefix

## Integration with Task Workflow

When creating a new feature, the workflow can optionally create a task:

```text
✓ Feature "analytics" created with 5 requirements.

Would you like to start a task for this feature?
1. Yes - create feature-analytics task with all requirements
2. Yes - select specific requirements to implement first
3. No - just create the feature documentation

Choice (1/2/3):
```

If 1 or 2, delegates to `/project:new-task` or `/project:from-requirements`.