# Context Skill Refinement Workflow

How to iteratively improve project context skills from initial generation to production quality.

## The Refinement Loop

```
┌─────────────────┐
│ Generate/Update │
└────────┬────────┘
         ↓
┌─────────────────┐
│ Use on Real Task│
└────────┬────────┘
         ↓
┌─────────────────┐
│ Identify Gaps   │
└────────┬────────┘
         ↓
┌─────────────────┐
│ Refine Context  │
└────────┬────────┘
         ↓
    (loop back)
```

## Phase 1: Initial Generation

### Quick Start Questionnaire

Ask the user these questions to bootstrap context:

```markdown
## Project Context Questions

### Purpose
1. What does this project do in one sentence?
2. Who uses it and for what?
3. What problem does it solve?

### Technical
4. What's the primary language/framework?
5. How do you run it locally?
6. How do you run the tests?
7. How is it deployed?

### Constraints
8. Any performance requirements? (response time, memory limits)
9. Any compatibility requirements? (browser versions, OS, hardware)
10. Any security considerations?

### Team
11. How many people work on this?
12. Are there coding style guides or conventions?
13. Any tribal knowledge that's not documented?
```

### From Codebase-Analyzer Output

If starting from analyzer output:

1. Run `python scripts/analyze.py /path/to/project --generate-skill`
2. Read the generated `synthesis_prompt.md`
3. Answer the open questions
4. Delete hollow/generic sections
5. Add guardrails and gotchas

## Phase 2: Validation

### Hollow Advice Detector

Scan the context skill for these anti-patterns:

| Pattern | Example | Problem |
|---------|---------|---------|
| Generic imperative | "Follow best practices" | Not specific |
| Obvious statement | "Write clean code" | Adds nothing |
| Vague reference | "See documentation" | Which documentation? |
| Undefined term | "Use standard patterns" | What standard? |
| Missing example | "Use consistent naming" | Like what? |

**Auto-detect regex patterns:**
```
/follow (best|existing|standard) (practices|patterns|conventions)/i
/write (clean|good|quality) code/i
/use (consistent|proper|appropriate)/i
/see (the )?(documentation|docs|readme)/i
/as (needed|appropriate|necessary)/i
```

### Completeness Checklist

```markdown
## Required Sections
- [ ] What the project does (business purpose)
- [ ] How to run locally
- [ ] How to run tests
- [ ] Key directories and their purpose
- [ ] Critical guardrails (at least 3 DO NOTs)

## Recommended Sections
- [ ] How to deploy
- [ ] Architecture overview
- [ ] Naming conventions with examples
- [ ] Common gotchas (at least 2)
- [ ] Key dependencies and why they're used

## Optional but Valuable
- [ ] Historical context (why things are the way they are)
- [ ] Performance considerations
- [ ] Security considerations
- [ ] Links to external documentation
```

### Test the Context

Use the context skill on a real task and observe:

```markdown
## Test Scenarios

### Scenario 1: New Feature
Ask Claude to add a small feature. Check if it:
- [ ] Puts files in the right directories
- [ ] Follows naming conventions
- [ ] Uses correct patterns (not inventing new ones)
- [ ] Respects guardrails

### Scenario 2: Bug Fix
Ask Claude to fix a bug. Check if it:
- [ ] Finds relevant code correctly
- [ ] Understands the architecture
- [ ] Makes minimal changes (no over-engineering)
- [ ] Runs tests appropriately

### Scenario 3: Explanation
Ask Claude to explain a component. Check if it:
- [ ] Understands the business purpose
- [ ] Knows how parts connect
- [ ] Can identify key constraints
```

## Phase 3: Refinement

### Adding Missing Information

When a gap is identified, add context at the right level:

| Gap Type | Where to Add |
|----------|--------------|
| High-level understanding | SKILL.md overview |
| Architectural detail | references/architecture.md |
| Code pattern | references/conventions.md |
| Common mistake | references/gotchas.md |
| Process/workflow | references/workflows.md |
| Critical constraint | SKILL.md guardrails |

### Improving Existing Sections

Transform weak context into strong context:

**Weak:**
```markdown
## Testing
Run tests with pytest.
```

**Strong:**
```markdown
## Testing

### Running Tests
```bash
# All tests
pytest

# Specific module
pytest tests/unit/test_payment.py

# With coverage
pytest --cov=src --cov-report=html
```

### Test Organization
- Unit tests: `tests/unit/` - mock all external dependencies
- Integration tests: `tests/integration/` - use test database
- E2E tests: `tests/e2e/` - require full stack running

### Writing New Tests
- Name test files `test_*.py`
- Name test functions `test_<what>_<condition>_<expected>`
- Use fixtures from `tests/conftest.py`
- Don't add new fixtures without discussing
```

### Removing Stale Information

After project changes, update context:

```markdown
## Staleness Indicators
- [ ] File paths that no longer exist
- [ ] Dependencies that were removed
- [ ] Patterns that changed
- [ ] Features that were deprecated
- [ ] Commands that don't work

## Update Triggers
- Major version releases
- Architecture changes
- New team members joining
- Repeated AI mistakes
```

## Interactive Refinement Prompts

### For Initial Setup

```
I've generated a project context skill for [project].
Let's refine it together.

1. Is the project description accurate?
2. Are there any critical constraints I'm missing?
3. What are the top 3 things an AI should NOT do in this codebase?
4. Any non-obvious gotchas from past experience?
```

### After Using the Context

```
I just used the [project] context skill for a task.
I noticed some gaps:

1. I wasn't sure where to put [X]
2. I couldn't find the pattern for [Y]
3. I may have violated a convention with [Z]

Should I update the context skill with this information?
```

### Periodic Review

```
It's been [X months] since the [project] context was last updated.

Let me check for staleness:
- Any major changes to the codebase?
- Any new conventions or patterns?
- Any deprecated approaches to remove?
- Any new gotchas discovered?
```

## Quality Metrics

Track these over time:

| Metric | Good | Needs Work |
|--------|------|------------|
| AI follows conventions | >90% | <70% |
| AI finds correct files | >95% | <80% |
| AI respects guardrails | 100% | <100% |
| Unnecessary clarification questions | <2 per task | >5 per task |
| Over-engineering instances | 0 | >0 |
