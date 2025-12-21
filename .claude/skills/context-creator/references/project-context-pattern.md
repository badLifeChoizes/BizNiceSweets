# Project Context Skill Patterns

Project context skills are fundamentally different from utility skills. This guide covers patterns specific to creating effective project context.

## How Context Skills Differ

| Aspect | Utility Skill | Context Skill |
|--------|---------------|---------------|
| **Purpose** | Enable specific operations | Keep AI aligned with project |
| **Content** | Procedures and workflows | Decisions and constraints |
| **Trigger** | User requests action | Working on the project |
| **Lifespan** | Stable across projects | Evolves with project |
| **Source** | Domain expertise | Project-specific knowledge |

## Anatomy of a Project Context Skill

```
project-context/
├── SKILL.md                    # High-level: purpose, constraints, guardrails
└── references/
    ├── architecture.md         # Module relationships, data flow, key decisions
    ├── conventions.md          # Naming, patterns, code style
    ├── gotchas.md              # Non-obvious quirks, past mistakes, edge cases
    └── workflows.md            # Build, test, deploy, debug procedures
```

### SKILL.md Structure

```markdown
---
name: project-context
description: Project context for [project]. Use when working on this project...
---

# [Project] Context

## What This Project Does
[Business purpose in 2-3 sentences - what problem does it solve?]

## Key Constraints
[Memory limits, performance requirements, compatibility needs, etc.]

## Guardrails
[What AI agents must NOT do when working on this project]

## Quick Reference
[Most common tasks and where to find things]

## References
- [architecture.md](references/architecture.md) - System design and module relationships
- [conventions.md](references/conventions.md) - Code style and naming patterns
- [gotchas.md](references/gotchas.md) - Non-obvious quirks and edge cases
- [workflows.md](references/workflows.md) - Build, test, deploy procedures
```

## The Guardrails Pattern

The most critical section for keeping AI agents aligned. Structure as explicit DO/DON'T lists:

```markdown
## Guardrails

### DO NOT (Critical)
- Add new dependencies without explicit approval
- Modify database schema without migration
- Change public API signatures
- Bypass the repository layer for database access
- Use raw SQL outside the query builder

### DO NOT (Style)
- Add comments to code you didn't write
- Refactor code beyond the immediate task
- Create abstractions for single-use cases
- Add error handling for impossible conditions

### ALWAYS
- Run tests before claiming task complete
- Use the project's logging framework (not print/console.log)
- Follow existing naming conventions exactly
- Put new files in the appropriate module directory
- Update relevant tests when changing behavior
```

## Quality Levels

### Level 1: Hollow (Avoid)

```markdown
## Conventions
- Follow existing patterns
- Use consistent naming
- Write clean code
```

This adds zero value - it's generic advice that applies to any project.

### Level 2: Basic (Minimum Acceptable)

```markdown
## Conventions
- Function names: snake_case
- Class names: PascalCase
- Constants: SCREAMING_SNAKE_CASE
- File names: kebab-case
```

Specific but still superficial - could be inferred from codebase.

### Level 3: Contextual (Good)

```markdown
## Conventions
- Function names: snake_case (e.g., `calculate_tax_rate`)
- Class names: PascalCase with module prefix (e.g., `PaymentProcessor`, not `Processor`)
- Constants: SCREAMING_SNAKE_CASE, defined in `config/constants.py`
- File names: kebab-case, one class per file in `models/`, grouped in `services/`
- Import order: stdlib → third-party → local, with blank lines between groups
```

Includes project-specific patterns with examples.

### Level 4: Strategic (Excellent)

```markdown
## Conventions

### Naming
- Function names: snake_case (e.g., `calculate_tax_rate`)
- Class names: PascalCase with module prefix (e.g., `PaymentProcessor`)

### Why These Matter
The module prefix convention exists because we have multiple processors (PaymentProcessor,
OrderProcessor, NotificationProcessor) and the prefix prevents ambiguity in imports.

### Historical Context
We switched from camelCase to snake_case in v2.0 (commit abc123). Some legacy code
in `legacy/` still uses camelCase - don't "fix" it, it will be removed in v3.0.

### Common Mistakes
- DON'T name handlers as `handle_x` - use `on_x` (e.g., `on_payment_received`)
- DON'T use abbreviations in names except: `ctx`, `req`, `res`, `db`
```

Includes rationale, history, and anti-patterns.

## Domain-Specific Context Sections

### For Embedded/IoT Projects

```markdown
## Hardware Constraints
- RAM: 320KB total, 256KB for application
- Flash: 4MB, OTA requires 2MB free
- CPU: Single core 240MHz, avoid blocking operations >10ms

## Power Management
- Device sleeps after 30s inactivity
- BLE connection kept alive via 1s heartbeat
- ADC readings only during active state

## Communication Protocol
- Uses custom binary protocol over BLE (see `docs/protocol.md`)
- Message format: [type:1][len:2][payload:n][crc:2]
- All multi-byte values are little-endian
```

### For Web Applications

```markdown
## API Design
- REST endpoints in `/api/v1/`
- All responses wrapped in `{ data: ..., error: ... }`
- Pagination: `?page=1&limit=20`, max 100 items

## Authentication
- JWT tokens in httpOnly cookies
- Refresh tokens in separate cookie with `/auth` path
- Token expiry: access=15min, refresh=7days

## Database
- PostgreSQL 14 with PostGIS for location data
- All queries through repository layer
- Soft delete using `deleted_at` timestamp
```

### For Libraries/SDKs

```markdown
## Public API
- All public functions in `src/index.ts`
- Breaking changes require major version bump
- Deprecated functions marked with `@deprecated` JSDoc

## Compatibility
- Supports Node.js 18+ and browsers (ES2020)
- Zero runtime dependencies policy
- TypeScript strict mode enabled

## Documentation
- All public functions require JSDoc with examples
- README examples must be tested in CI
```

## Integration with Codebase-Analyzer

When using codebase-analyzer output to create context skills:

1. **Filter the noise** - Ignore documentation artifacts, generated files
2. **Validate inferences** - Don't trust "inferred" confidence without checking
3. **Add what's missing** - Business context, constraints, rationale
4. **Reduce uncertainty** - Answer questions flagged by analyzer
5. **Delete hollow sections** - Remove generic advice that adds no value

See [codebase-analyzer-integration.md](codebase-analyzer-integration.md) for detailed workflow.
