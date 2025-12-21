---
name: code-style
description: Detect and enforce code style conventions across Python, JavaScript/TypeScript, Go, Rust, C#, C++, and Java. Use when (1) starting work on an unfamiliar codebase to learn its style, (2) checking code against project conventions, (3) generating style config files (ESLint, Ruff, .editorconfig), (4) auto-fixing style issues, (5) generating pre-commit hooks, or (6) enforcing architectural rules and layer boundaries.
---

# Code Style

Detect and enforce coding conventions from existing code, including formatting, semantic rules, import organization, and architectural patterns.

## Philosophy

**Learn from the codebase, don't impose rules.** This skill detects what conventions are actually used in a project (formatting, structure, and architecture), then helps maintain consistency through detection, checking, and auto-fixing.

## Quick Start

### Detect Style from Existing Code
```bash
python scripts/detect_style.py /path/to/project
```

### Generate Rules File
```bash
python scripts/generate_rules.py /path/to/project --output .style-rules.json
```

### Check Code Against Rules
```bash
python scripts/check_style.py /path/to/project
```

### Auto-Fix Issues
```bash
python scripts/check_style.py /path/to/project --fix
```

### Generate Pre-Commit Hook
```bash
python scripts/generate_rules.py /path/to/project --hook
```

## Workflow

### 1. Detect Existing Conventions

```bash
python scripts/detect_style.py /path/to/project --output style-report.json
```

This analyzes the codebase and reports:
- **Formatting**: Indentation (2-space, 4-space, tabs), quote style, semicolons
- **Naming**: snake_case, camelCase, PascalCase across all languages
- **Semantic**: Function length, cyclomatic complexity, nesting depth
- **Imports**: Grouping patterns, ordering conventions
- **Architecture**: Layer boundaries, dependency directions
- **Documentation**: Docstring/comment style and coverage

### 2. Generate Style Rules

```bash
python scripts/generate_rules.py /path/to/project
```

Creates `.style-rules.json` based on detected patterns. Options:
- `--eslint` - Also generate `.eslintrc.json` (JavaScript/TypeScript)
- `--ruff` - Also generate `ruff.toml` (Python)
- `--editorconfig` - Generate `.editorconfig` (multi-language)
- `--hook` - Generate `.git/hooks/pre-commit` hook
- `--architecture` - Include architectural rules (layer boundaries)

### 3. Check Code

```bash
python scripts/check_style.py /path/to/project --rules .style-rules.json
```

Reports issues:
- ❌ Errors - Must fix (architectural violations, major inconsistencies)
- ⚠️ Warnings - Should fix (style deviations, complexity)
- ℹ️ Info - Consider fixing (minor suggestions)

### 4. Auto-Fix Issues

```bash
python scripts/check_style.py /path/to/project --fix
```

Automatically fixes:
- Indentation and spacing
- Quote style (single ↔ double)
- Trailing whitespace
- Import ordering
- Simple formatting issues

Complex issues requiring judgment are reported but not auto-fixed.

## What It Detects

### Formatting Conventions

| Language | Detections |
|----------|------------|
| **Python** | Indentation, quotes, line length, string formatting (f-string/.format()/%), import style |
| **JavaScript/TypeScript** | Indentation, quotes, semicolons, const/let/var, arrow vs function, trailing commas |
| **Go** | gofmt compliance, import grouping, receiver naming, error handling patterns |
| **Rust** | rustfmt compliance, import ordering, naming (snake_case/SCREAMING_SNAKE), visibility patterns |
| **C#** | Indentation, brace style, PascalCase/camelCase, async naming (suffix with Async) |
| **C++** | Indentation, brace style, naming (snake_case/camelCase/PascalCase), header guards |
| **Java** | Indentation, brace style, CamelCase conventions, import organization |

### Semantic Rules

**All Languages:**
- Function length (lines, recommended: <50)
- Cyclomatic complexity (branches, recommended: <10)
- Nesting depth (recommended: <4)
- Parameter count (recommended: <5)
- Class size (methods and lines)

### Import Organization

**Detected patterns:**
- Grouping (stdlib, third-party, local)
- Ordering within groups (alphabetical, by type)
- Blank lines between groups
- Relative vs absolute imports

**Languages:** Python, JavaScript/TypeScript, Go, Rust, C#, C++, Java

### Architectural Rules

**Layer boundaries:**
- Services shouldn't import from controllers/views
- Domain layer shouldn't import from infrastructure
- Core shouldn't depend on plugins

**Patterns detected:**
- Dependency direction (e.g., always inward toward domain)
- Circular dependencies
- Cross-cutting concerns (logging, config)

## Generated Files

### .style-rules.json
Project-specific rules for the checker:
```json
{
  "formatting": {
    "python": {"line_length": 100, "indentation": "4-space", "quotes": "double"},
    "javascript": {"quotes": "single", "semicolons": true},
    "csharp": {"brace_style": "next-line", "naming": "PascalCase"}
  },
  "semantic": {
    "max_function_length": 50,
    "max_complexity": 10,
    "max_nesting": 4,
    "max_parameters": 5
  },
  "imports": {
    "grouping": ["stdlib", "third-party", "local"],
    "ordering": "alphabetical",
    "blank_lines": true
  },
  "architecture": {
    "layers": ["domain", "application", "infrastructure"],
    "rules": [
      "domain cannot import from application",
      "domain cannot import from infrastructure"
    ]
  }
}
```

### .eslintrc.json (with --eslint)
ESLint config matching detected conventions.

### ruff.toml (with --ruff)
Ruff config for Python linting.

### .editorconfig (with --editorconfig)
Multi-language editor config for consistent formatting.

### .git/hooks/pre-commit (with --hook)
Pre-commit hook that runs style checks automatically before commits.

## Reference

See `references/conventions.md` for:
- Naming convention examples
- Docstring format templates
- Common anti-patterns to avoid
- Style consistency checklist

## Tips

- **Run detection first** - Understand the codebase before writing code
- **Match, don't change** - Follow existing patterns even if you prefer different ones
- **Use formatters** - Black, Prettier handle formatting automatically
- **Focus on consistency** - The specific choice matters less than being uniform
