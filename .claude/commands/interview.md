# Interview - Structured Discovery & Planning

Conduct planning, discovery, and decision-making sessions using an incremental documentation approach.

## When to Use

- Architecture planning sessions
- Feature discovery and requirements gathering
- Design decisions that need user input
- Any multi-question planning process

## Process

### 1. Create or Identify the Decisions Document

Before asking questions, create or open a decisions document:

```
docs/decisions.md           # For architecture/project-wide decisions
docs/features/{name}/decisions.md  # For feature-specific decisions
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

Only AFTER updating documentation, proceed to the next question.

### 4. Summary at Completion

When all decisions are made:

1. Update document status to "Complete"
2. Add a Summary section with all decisions
3. List Next Steps / Action Items
4. Commit the final document

## Example Flow

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

1. **Incremental documentation** - Update docs after EACH decision, not at the end
2. **One question at a time** - Don't overwhelm with multiple questions
3. **Always recommend** - Claude provides opinion with reasoning
4. **Pros and cons** - Help user understand trade-offs
5. **Record rationale** - Capture WHY decisions were made, not just WHAT
6. **Commit progress** - Use checkpoints to save work incrementally

## Arguments

```
$ARGUMENTS = topic or context for the interview session
```

Examples:
- `/interview architecture` - Architecture decisions
- `/interview feature-auth` - Auth feature decisions
- `/interview "database migration strategy"` - Specific topic

## Output Format

All decisions should be recorded in markdown with:
- Clear headings for each decision
- Tables for options comparison
- Status indicators (Pending, DECIDED)
- Date stamps
- Action items where applicable