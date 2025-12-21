# Architecture

> This file describes the system architecture for {{PROJECT_NAME}}.
> Read this when you need to understand how components relate.

## System Overview

<!-- TODO: High-level description of the architecture -->

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Layer 1   │ ──→ │   Layer 2   │ ──→ │   Layer 3   │
└─────────────┘     └─────────────┘     └─────────────┘
```

## Module Structure

### Core Modules

| Module | Responsibility | Key Files |
|--------|----------------|-----------|
| [module1] | [What it does] | [Key files] |
| [module2] | [What it does] | [Key files] |

### Supporting Modules

| Module | Responsibility | Key Files |
|--------|----------------|-----------|
| [module1] | [What it does] | [Key files] |

## Key Design Decisions

### Decision 1: [Title]

**Context:** [Why this decision was needed]

**Decision:** [What was decided]

**Consequences:** [Impact of the decision]

### Decision 2: [Title]

**Context:** [Why this decision was needed]

**Decision:** [What was decided]

**Consequences:** [Impact of the decision]

## Data Flow

### [Flow Name] (e.g., Request Handling)

```
1. [Step 1]
   ↓
2. [Step 2]
   ↓
3. [Step 3]
```

### [Flow Name] (e.g., Background Processing)

```
1. [Step 1]
   ↓
2. [Step 2]
```

## External Dependencies

| Dependency | Purpose | Documentation |
|------------|---------|---------------|
| [Dep 1] | [Why we use it] | [Link] |
| [Dep 2] | [Why we use it] | [Link] |

## Integration Points

### [Integration Name]

- **Protocol:** [REST/gRPC/WebSocket/etc.]
- **Auth:** [How authentication works]
- **Rate Limits:** [Any limits to be aware of]
