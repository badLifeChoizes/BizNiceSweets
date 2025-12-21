---
name: interview
description: Conduct planning, discovery, and decision-making sessions using an incremental documentation approach. Use when (1) architecture planning, (2) feature discovery and requirements gathering, (3) design decisions requiring user input, or (4) any multi-question planning process. Creates or updates documentation incrementally with one question at a time, recording decisions before proceeding. (project)
---

# Interview - Structured Discovery & Planning

Conduct structured interviews for planning, discovery, and decision-making with incremental documentation.

## Philosophy

**One question at a time, document before proceeding.** This skill ensures decisions are captured incrementally rather than at the end. Each question includes analysis, options, pros/cons, and Claude's recommendation. Decisions are recorded immediately before moving to the next topic.

## Quick Start

### Interview Types

```text
/interview discovery {topic}    # Feature discovery and requirements gathering
/interview planning {topic}     # Architecture or implementation planning
/interview decision {topic}     # Specific decision point needing resolution
/interview scoping {task-name}  # Scope a new task (integrates with task workflow)
```

### Task Workflow Integration

When working within the task workflow, interview sessions can directly populate:

- **Task checklists** - Decisions become checklist items in `docs/tasks/{branch}.md`
- **Requirements** - Discovered requirements get IDs and link to `docs/features/requirements.md`
- **Feature docs** - New features created via `add-feature.md` pattern

## Interview Modes

### Mode 1: Discovery Interview

**Purpose:** Gather requirements for a new feature or explore a problem space.

**Output:** Populates `## Related Requirements` section in task file, or creates new feature doc.

**Triggers:**
- `/interview discovery {feature-name}`
- Called by `/project:add-feature` when gathering requirements
- Called by `/project:new-task` when no matching requirements found

**Flow:**
```text
1. Context Analysis
   - What problem are we solving?
   - Who are the users?
   - What existing features relate?

2. Core Requirements (iterate until complete)
   - Present question with options
   - Record each requirement with ID
   - Categorize: Must / Should / Could

3. Edge Cases
   - Identify boundary conditions
   - Capture error scenarios

4. Output
   - Requirements list with IDs
   - Ready for task file population
```

### Mode 2: Planning Interview

**Purpose:** Plan implementation approach for a defined scope.

**Output:** Populates `## Checklist` section in task file with implementation steps.

**Triggers:**
- `/interview planning {task-name}`
- Called by `/project:start-task` for complex tasks
- User requests implementation plan

**Flow:**
```text
1. Scope Confirmation
   - What requirements are we implementing?
   - What is out of scope?

2. Architecture Decisions (iterate)
   - Data model questions
   - State management questions
   - UI/UX questions

3. Implementation Steps
   - Break down into checklist items
   - Order by dependency

4. Output
   - Ordered checklist items
   - Architecture decision record
```

### Mode 3: Decision Interview

**Purpose:** Resolve a specific decision point.

**Output:** Single decision record, optionally updates task file.

**Triggers:**
- `/interview decision "{question}"`
- When implementation hits a fork in the road
- Architecture trade-off needed

**Flow:**
```text
1. Frame the Decision
   - What specific choice needs to be made?
   - What are the constraints?

2. Present Options
   - Option A with pros/cons
   - Option B with pros/cons
   - (Optional) Option C

3. Recommendation
   - Claude's recommendation with reasoning

4. Record Decision
   - Add to task file or decisions log
```

### Mode 4: Scoping Interview

**Purpose:** Scope a new task before creating it.

**Output:** Directly creates task file via `/project:new-task` pattern.

**Triggers:**
- `/interview scoping {branch-name}`
- When user has vague idea needing refinement
- Before `/project:new-task` for complex tasks

**Flow:**
```text
1. Goal Clarification
   - What are you trying to accomplish?
   - What triggered this task?

2. Feature Detection
   - Run detect-requirements analysis
   - Present matching features/requirements

3. Scope Definition
   - Which requirements to include?
   - What's explicitly out of scope?

4. Output
   - Populated task file ready for work
   - Requirements linked to feature docs
```

## Workflow

### 1. Create or Identify the Decisions Document

Interview sessions write to one of these locations:

| Interview Type | Output Location |
|----------------|-----------------|
| discovery | `docs/tasks/{branch}.md` → Related Requirements |
| planning | `docs/tasks/{branch}.md` → Checklist |
| decision | `docs/tasks/{branch}.md` → Decisions section |
| scoping | Creates new `docs/tasks/{branch}.md` |

For standalone decisions (no active task):
```text
docs/decisions/{topic}.md    # Architecture decisions
docs/features/{name}/decisions.md  # Feature-specific decisions
```

Initialize with a Decision Log table:

```markdown
# {Topic} Decisions

**Created:** {date}
**Status:** In Progress
**Related Task:** {branch-name or "standalone"}

## Decision Log

| # | Topic | Decision | Date |
|---|-------|----------|------|
| 1 | {First topic} | *Pending* | - |
| 2 | {Second topic} | *Pending* | - |
```

### 2. One Question at a Time

For each decision point:

#### A. Present the Question

```markdown
## Decision {N}: {Topic}

**Status:** Awaiting Decision

### Question

{Clear question that needs to be answered}

### Context

{Background information the user needs to make an informed decision}
```

#### B. Present Options with Analysis

For each option, include:

```markdown
#### Option A: {Name}

{Description of this option}

**Pros:**
- {Benefit 1}
- {Benefit 2}

**Cons:**
- {Drawback 1}
- {Drawback 2}
```

#### C. Provide Your Recommendation

Always include Claude's recommendation with reasoning:

```markdown
### My Recommendation

**{Option X}: {Name}**

Reasoning:
1. {Reason 1}
2. {Reason 2}
3. {Reason 3}
```

#### D. Wait for User Decision

End with a clear prompt:

```markdown
### Decision

Awaiting your input ({Option letters} or other)
```

### 3. Record Decision Before Proceeding

Once the user provides a decision:

1. **Update the Decision Log table** - Change *Pending* to the decision
2. **Update the Decision section** - Change status to DECIDED
3. **Add the decision details** - Record what was decided and why
4. **Update task file** - If applicable, add checklist items or requirements
5. **Commit if appropriate** - Use `/project:checkpoint` for significant decisions

**Only AFTER updating documentation, proceed to the next question.**

### 4. Summary at Completion

When all decisions are made:

1. Update document status to "Complete"
2. Add a Summary section with all decisions
3. List Next Steps / Action Items
4. Update task file with derived checklist items
5. Run `/project:checkpoint` with decision summary

## Task Workflow Integration

### Integration with new-task

When `/project:new-task` detects ambiguity, it can delegate to interview:

```text
/project:new-task feature-analytics

⚠️ No matching feature found for: feature-analytics

Would you like to:
1. Run discovery interview (recommended for new features)
2. Select from existing features manually
3. Proceed without requirements

Choice: 1

Starting discovery interview for: analytics
```

### Integration with add-feature

The `/project:add-feature` command uses interview for requirements gathering:

```text
/project:add-feature notifications

📋 Creating feature: Notifications

Starting discovery interview to gather requirements...

## Question 1: Core Functionality

What are the primary notification types needed?

A) System alerts only (errors, warnings)
B) User actions (mentions, assignments)
C) Both system and user notifications
D) Full notification system with preferences

My Recommendation: Option C...
```

### Integration with start-task

When starting a complex task, interview can help plan implementation:

```text
/project:start-task feature-session-export

📋 This task has 4 requirements to implement.

Would you like to run a planning interview? (recommended for 3+ requirements)
1. Yes - plan implementation approach
2. No - start working directly

Choice: 1

Starting planning interview for: feature-session-export
```

## Example Session Flow

### Discovery Interview Example

```text
Claude: 📋 Discovery Interview: User Notifications

## Question 1: Notification Scope

What events should trigger notifications?

### Context
We need to define which system and user events warrant notifications.
This affects both the event architecture and UI design.

### Options

#### Option A: Minimal (System Only)
System errors, warnings, and critical updates only.
- Pros: Simple, low noise
- Cons: Users miss important user-triggered events

#### Option B: Session Events
System + session-related events (start, stop, participant changes)
- Pros: Balanced coverage
- Cons: May miss device-related events

#### Option C: Comprehensive
All significant events across sessions, devices, and participants
- Pros: Full coverage
- Cons: Risk of notification fatigue

### My Recommendation

**Option B: Session Events**

Reasoning:
1. Sessions are the core workflow - events here are most actionable
2. Can expand later based on user feedback
3. Avoids notification fatigue while covering critical flows

### Decision

Awaiting your input (A/B/C or other)
```

```text
User: B, but also include device disconnection alerts

Claude: ✓ Recorded Decision 1: Session Events + Device Disconnection

Updating requirements...

New requirements captured:
- NOTIF-001: System SHALL display session start/stop notifications (Must)
- NOTIF-002: System SHALL alert on participant changes (Should)
- NOTIF-003: System SHALL alert on device disconnection (Must)

## Question 2: Notification Persistence...
```

## Key Principles

| Principle | Description |
|-----------|-------------|
| **Incremental documentation** | Update docs after EACH decision, not at the end |
| **One question at a time** | Don't overwhelm with multiple questions |
| **Always recommend** | Claude provides opinion with reasoning |
| **Pros and cons** | Help user understand trade-offs |
| **Record rationale** | Capture WHY decisions were made, not just WHAT |
| **Task integration** | Decisions flow into task checklists and requirements |
| **Checkpoint progress** | Use `/project:checkpoint` after major decisions |

## Output Format

All decisions should be recorded in markdown with:

- Clear headings for each decision
- Tables for options comparison
- Status indicators (Pending, DECIDED)
- Date stamps
- Requirement IDs where applicable
- Links to related task files

## Decision Template

```markdown
## Decision {N}: {Topic}

**Status:** DECIDED
**Related:** {requirement IDs or "N/A"}

### Question
{The question that was asked}

### Decision
**{Option Letter}: {Option Name}**

{Summary of what was decided}

### Rationale
{Why this decision was made, including user's reasoning if provided}

### Task Impact
- [ ] {Checklist item derived from this decision}
- [ ] {Another checklist item if applicable}
```

## Requirement Capture Template

When capturing requirements during discovery:

```markdown
## Captured Requirements

| ID | Requirement | Priority | Source |
|----|-------------|----------|--------|
| {PREFIX}-{N} | {SHALL statement} | {Must/Should/Could} | Decision {N} |

### Requirement Details

#### {PREFIX}-{N}: {Short name}

**Full requirement:** {Full SHALL statement}
**Priority:** {Must/Should/Could}
**Derived from:** Decision {N} - {brief decision summary}
**Acceptance criteria:**
- {Criterion 1}
- {Criterion 2}
```

## Tips

- **Start with context** - Ensure you understand the domain before asking questions
- **Group related decisions** - Order questions logically
- **Be specific** - Vague options lead to unclear decisions
- **Capture modifications** - Users often say "Option A but with X" - record both
- **Use checkpoints** - Run `/project:checkpoint` after major decision blocks
- **Link to features** - Reference `@docs/features/{name}.md` for context
- **Check INVARIANTS** - Before planning interviews, review relevant INVARIANTS files
- **Track requirements** - Assign IDs to captured requirements immediately

## Command Reference

| Command | Purpose | Output |
|---------|---------|--------|
| `/interview discovery {topic}` | Gather requirements | Requirements list |
| `/interview planning {topic}` | Plan implementation | Checklist items |
| `/interview decision {question}` | Resolve single decision | Decision record |
| `/interview scoping {branch}` | Scope new task | Task file |
| `/project:checkpoint` | Save progress | Commit with decisions |
| `/project:add-feature` | Create feature | Uses discovery interview |
| `/project:new-task` | Create task | May invoke scoping interview |
