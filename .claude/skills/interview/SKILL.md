---
name: interview
description: Conduct planning, discovery, and decision-making sessions using an incremental documentation approach. Use when (1) architecture planning, (2) feature discovery and requirements gathering, (3) design decisions requiring user input, or (4) any multi-question planning process. Creates or updates documentation incrementally with one question at a time, recording decisions before proceeding.
---

# Interview - Structured Discovery & Planning

Conduct structured interviews for planning, discovery, and decision-making with incremental documentation.

## Philosophy

**One question at a time, document before proceeding.** This skill ensures decisions are captured incrementally rather than at the end. Each question includes analysis, options, pros/cons, and Claude's recommendation. Decisions are recorded immediately before moving to the next topic.

## Quick Start

### Start an Interview Session
```
/interview architecture         # Architecture decisions
/interview feature-auth        # Feature-specific decisions
/interview "database strategy" # Specific topic
```

## Workflow

### 1. Create or Identify the Decisions Document

Before asking questions, create or open a decisions document:

```
docs/decisions.md                      # Project-wide decisions
docs/features/{name}/decisions.md      # Feature-specific decisions
```

Initialize with a Decision Log table:

```markdown
# {Topic} Decisions

**Created:** {date}
**Status:** In Progress

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
4. **Commit if appropriate** - Save progress incrementally

**Only AFTER updating documentation, proceed to the next question.**

### 4. Summary at Completion

When all decisions are made:

1. Update document status to "Complete"
2. Add a Summary section with all decisions
3. List Next Steps / Action Items
4. Commit the final document

## Example Session Flow

```
Claude: Creates docs/decisions.md with Decision Log
Claude: Presents Question 1 with options A, B, C and recommendation
User: "Option B"
Claude: Updates Decision 1 in document, marks as DECIDED
Claude: Presents Question 2 with options and recommendation
User: "Option A with modification X"
Claude: Updates Decision 2, incorporates user's modification
... continues until all decisions made ...
Claude: Updates status to Complete, adds Summary
```

## Key Principles

| Principle | Description |
|-----------|-------------|
| **Incremental documentation** | Update docs after EACH decision, not at the end |
| **One question at a time** | Don't overwhelm with multiple questions |
| **Always recommend** | Claude provides opinion with reasoning |
| **Pros and cons** | Help user understand trade-offs |
| **Record rationale** | Capture WHY decisions were made, not just WHAT |
| **Commit progress** | Use checkpoints to save work incrementally |

## Output Format

All decisions should be recorded in markdown with:

- Clear headings for each decision
- Tables for options comparison
- Status indicators (Pending, DECIDED)
- Date stamps
- Action items where applicable

## Decision Template

```markdown
## Decision {N}: {Topic}

**Status:** DECIDED

### Question
{The question that was asked}

### Decision
**{Option Letter}: {Option Name}**

{Summary of what was decided}

### Rationale
{Why this decision was made, including user's reasoning if provided}

### Action Items
- [ ] {Any follow-up tasks}
```

## Tips

- **Start with context** - Ensure you understand the domain before asking questions
- **Group related decisions** - Order questions logically
- **Be specific** - Vague options lead to unclear decisions
- **Capture modifications** - Users often say "Option A but with X" - record both
- **Use checkpoints** - Commit after major decision blocks