---
name: context-creator
description: Create project context skills that keep AI agents aligned with project goals and architecture. Use when (1) setting up a new project for AI assistance, (2) analyzing a codebase to understand its structure, (3) creating guardrails to prevent AI from deviating, (4) documenting project-specific patterns and constraints, or (5) improving an existing project context skill. Includes automated codebase analysis.
---

# Context Creator

Create **project context skills** that keep AI agents aligned with project goals and architecture. Includes automated codebase analysis and refinement workflow.

## Two-Phase Workflow

### Phase 1: Automated Analysis

Run the analyzer to collect raw data about a codebase:

```bash
python scripts/analyze.py /path/to/project --generate-skill
```

This creates a `<project>-context/` skill folder with:
- `SKILL.md` - Basic auto-generated context
- `references/synthesis_prompt.md` - Instructions for Phase 2
- `references/full_analysis.json` - Complete raw data

### Phase 2: Claude-Assisted Synthesis

Refine the raw analysis into quality context:

1. Read `synthesis_prompt.md` and key files it identifies
2. Answer open questions flagged by analysis
3. Apply quality patterns from this skill's references
4. Add guardrails and gotchas
5. Remove hollow/generic advice

## Alternative: Start from Template

For manual creation without analysis:

```bash
python scripts/init_context.py my-project --path .claude/skills
```

Creates structured templates with TODO placeholders:

```text
my-project-context/
├── SKILL.md                     # Purpose, constraints, guardrails
└── references/
    ├── architecture.md          # System design
    ├── conventions.md           # Coding standards
    ├── gotchas.md               # Non-obvious quirks
    └── workflows.md             # Build, test, deploy
```

## Core Principles for Context Skills

### 1. Encode Decisions, Not Just Data

**Bad:** "Uses Python 3.11"
**Good:** "Uses Python 3.11 for `tomllib`. Don't suggest 3.10 compatibility."

### 2. Be Specific About Boundaries

**Bad:** "Follow best practices"
**Good:** "All database access through `repositories/`. Never raw SQL in services."

### 3. Guardrails Are Critical

The most valuable section. Structure as explicit lists:

```markdown
## Guardrails

### DO NOT (Critical)
- Add dependencies without approval
- Modify public API signatures
- Bypass repository layer for database

### ALWAYS
- Run tests before claiming complete
- Use project's logging framework
- Follow existing naming exactly
```

## Quality Levels

| Level | Example | Value |
|-------|---------|-------|
| Hollow | "Follow best practices" | Zero - generic |
| Basic | "Functions: snake_case" | Low - obvious |
| Contextual | "Functions: snake_case (e.g., `calculate_tax`)" | Good - specific |
| Strategic | Above + "We switched from camelCase in v2" | Excellent - rationale |

See [project-context-pattern.md](references/project-context-pattern.md) for detailed examples.

## References

| File | Purpose |
|------|---------|
| [project-context-pattern.md](references/project-context-pattern.md) | Patterns for project context skills |
| [codebase-analyzer-integration.md](references/codebase-analyzer-integration.md) | Cleaning up analyzer output |
| [refinement-workflow.md](references/refinement-workflow.md) | Iterative improvement |
| [language-support.md](references/language-support.md) | Supported languages and frameworks |
| [output-patterns.md](references/output-patterns.md) | Template and example patterns |
| [workflows.md](references/workflows.md) | Sequential and conditional workflows |

## Scripts

### Analysis Scripts

| Script | Purpose |
|--------|---------|
| `analyze.py` | Main entry - runs all analysis, generates skill |
| `analyze_structure.py` | Directory structure with confidence tagging |
| `analyze_deps.py` | Dependency and config file parsing |
| `analyze_patterns.py` | Language-specific pattern detection |
| `analyze_api.py` | API endpoint detection (REST, GraphQL, gRPC) |
| `analyze_models.py` | Database model extraction |
| `analyze_config.py` | Configuration and secrets analysis |
| `build_graph.py` | Module dependency graph |

### Skill Management Scripts

| Script | Purpose |
|--------|---------|
| `init_context.py` | Initialize project context skill from template |
| `init_skill.py` | Initialize general utility skill |
| `package_skill.py` | Package skill for distribution |
| `quick_validate.py` | Validate skill structure |

## Command Line Options

```bash
python scripts/analyze.py <project_path> [options]

Options:
  --output FILE       Save full analysis to JSON file
  --generate-skill    Generate context skill folder
  --basic             Skip extended analysis (API, models, config)
  --synthesis-only    Only output the synthesis prompt for Phase 2
```

---

## Utility Skills Reference

For traditional utility skills (not project context), the following applies.

### Anatomy of a Skill

```text
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter (name, description)
│   └── Markdown instructions
└── Bundled Resources (optional)
    ├── scripts/      - Executable code
    ├── references/   - Documentation loaded as needed
    └── assets/       - Files used in output (templates, etc.)
```

### Core Principles

**Concise is Key:** Only add what Claude doesn't already know. Challenge each token.

**Progressive Disclosure:**
1. Metadata (name + description) - Always loaded (~100 words)
2. SKILL.md body - When triggered (<5k words)
3. References - As needed by Claude

**Degrees of Freedom:**
- High: Multiple valid approaches, use text instructions
- Medium: Preferred pattern exists, use pseudocode
- Low: Fragile operations, use specific scripts

### Creation Process

1. Understand skill with concrete examples
2. Plan reusable contents (scripts, references, assets)
3. Initialize with `init_skill.py`
4. Edit SKILL.md and resources
5. Package with `package_skill.py`
6. Iterate based on usage

### Frontmatter

```yaml
---
name: skill-name
description: What it does and when to use it. Include triggers.
---
```

Description is the primary trigger - include all "when to use" info here, not in body.

### What Not to Include

- README.md, CHANGELOG.md, INSTALLATION_GUIDE.md
- Setup/testing procedures
- User-facing documentation

Skills contain only what AI needs to do the job.
