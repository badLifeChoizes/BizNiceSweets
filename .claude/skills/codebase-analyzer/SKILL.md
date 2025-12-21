---
name: codebase-analyzer
description: Analyze any codebase to understand structure, patterns, and conventions. Uses a two-phase hybrid approach - automated static analysis followed by Claude-assisted synthesis for meaningful project context. Supports Python, JavaScript/TypeScript, Go, Rust, Java, C/C++, and C#. Use when starting work on a new project, need to understand architecture, or creating a project context skill. (project)
---

# Codebase Analyzer v3

Two-phase hybrid analysis that combines automated static analysis with Claude-assisted synthesis to create meaningful, actionable project context.

## Why Two Phases?

**Phase 1 (Automated)** collects raw data fast:
- Directory structure and file distribution
- Dependencies and frameworks
- API endpoints, data models, configuration
- Code patterns and naming conventions

**Phase 2 (Claude-Assisted)** adds understanding:
- What the project actually *does* (business purpose)
- How code flows in practice
- Gotchas and non-obvious patterns
- Validated context from the user

## Quick Start

### Basic Usage
```bash
# Run Phase 1 analysis and generate skill folder
python scripts/analyze.py /path/to/project --generate-skill

# Output: <project>-context/ folder with SKILL.md and analysis data
```

### Two-Phase Workflow
```bash
# Phase 1: Generate raw analysis
python scripts/analyze.py /path/to/project --generate-skill

# Phase 2: Ask Claude to synthesize
# "Read the synthesis_prompt.md and key files, then update SKILL.md with your understanding"
```

## What Gets Analyzed

### Core Analysis
| Component | What It Detects |
|-----------|-----------------|
| Structure | Directory hierarchy, file distribution, README extraction |
| Dependencies | package.json, requirements.txt, Cargo.toml, go.mod, etc. |
| Patterns | Naming conventions, async usage, type hints, decorators |
| Module Graph | Entry points, core modules, circular dependencies |

### Extended Analysis (v3)
| Component | What It Detects |
|-----------|-----------------|
| **API Endpoints** | REST routes, GraphQL schemas, gRPC services |
| **Data Models** | SQLAlchemy, Django, Prisma, TypeORM, EF, GORM, Diesel |
| **Configuration** | .env files, config patterns, environment variables |
| **Secrets** | Potential exposed secrets (warnings only) |

## Scripts

| Script | Purpose |
|--------|---------|
| `analyze.py` | Main entry - runs all analysis, generates skill |
| `analyze_structure.py` | Directory structure with confidence tagging |
| `analyze_deps.py` | Dependency and config file parsing |
| `analyze_patterns.py` | Language-specific pattern detection |
| `build_graph.py` | Module dependency graph |
| `analyze_api.py` | API endpoint detection (REST, GraphQL, gRPC) |
| `analyze_models.py` | Database model extraction |
| `analyze_config.py` | Configuration and secrets analysis |

## Command Line Options

```bash
python scripts/analyze.py <project_path> [options]

Options:
  --output FILE       Save full analysis to JSON file
  --generate-skill    Generate context skill folder
  --basic             Skip extended analysis (API, models, config)
  --synthesis-only    Only output the synthesis prompt for Phase 2
```

## Generated Skill Structure

```
<project>-context/
├── SKILL.md                         # Context for Claude (Phase 1 or 2)
└── references/
    ├── full_analysis.json           # Complete raw data
    ├── synthesis_prompt.md          # Instructions for Phase 2
    ├── api_analysis.json            # API endpoints detail
    ├── models_analysis.json         # Data models detail
    ├── config_analysis.json         # Configuration detail
    └── dependency_graph.json        # Module relationships
```

## Phase 2 Synthesis Guide

After running Phase 1, Claude should:

1. **Read `synthesis_prompt.md`** - Contains specific instructions and questions
2. **Read key files** - Entry points, core modules, route files, models
3. **Answer open questions** - Investigate uncertain areas flagged by analysis
4. **Write meaningful context** - Not data dumps, but practical guidance:
   - What does this project DO?
   - How do I run/test/deploy it?
   - What are the key concepts?
   - What gotchas should I know?
5. **Validate with user** - Confirm understanding of inferred patterns

## Confidence Levels

Analysis results are tagged with confidence:
- **detected**: High confidence from explicit signals (e.g., `tests/` directory)
- **inferred**: Heuristic guess from patterns (e.g., files named `*_test.py`)
- **unknown**: Needs verification by Claude or user

## Example Output

```
📁 Analyzing: my-webapp

  → Analyzing structure...
  → Analyzing dependencies...
  → Detecting patterns...
  → Building dependency graph...
  → Detecting API endpoints...
  → Extracting data models...
  → Analyzing configuration...

📊 Summary for my-webapp:
   Files: 245
   Directories: 32
   Languages: python(120), typescript(80), json(45)
   Frameworks: FastAPI, React
   API Endpoints: 24
   Data Models: 12
   Env Variables: 18
   Confidence: 22 detected, 8 inferred, 2 unknown
   ⚠️  2 areas need verification

✅ Generated skill at: my-webapp-context

📋 Next Steps (Phase 2):
   1. Read: my-webapp-context/references/synthesis_prompt.md
   2. Read key files listed in the prompt
   3. Update my-webapp-context/SKILL.md with synthesized insights
```

## References

| File | Contents |
|------|----------|
| `references/workflow.md` | Detailed usage examples and tips |
| `references/language-support.md` | Supported languages, patterns, and confidence levels |
