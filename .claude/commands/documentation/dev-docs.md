---
description: Generate developer documentation (API docs, architecture, internals)
---

# Generate Developer Documentation

Create developer-focused documentation including API references, architecture guides, and internal documentation.

## Arguments

- `$ARGUMENTS`: Type of documentation (api, architecture, internals, contributing) and optional focus area

## Instructions

1. Parse arguments to determine documentation type:
   - `api` - Generate API reference documentation
   - `architecture` - Create architecture overview
   - `internals` - Document internal workings
   - `contributing` - Developer contribution guide
   - If empty, ask user what type they need

2. Invoke the `code-docs` skill

3. Analyze the codebase:
   ```bash
   python .claude/skills/code-docs/scripts/analyze.py . --output dev-analysis.json
   python .claude/skills/code-docs/scripts/audit.py dev-analysis.json --format markdown --output dev-audit.md
   ```

4. Based on documentation type:

   **For API Documentation:**
   - Document all public interfaces
   - Include function signatures with types
   - Parameter descriptions
   - Return value documentation
   - Usage examples for each endpoint/function
   - Error codes and handling
   - Output to: docs/api/

   **For Architecture Documentation:**
   - High-level system overview
   - Component diagram (describe in text/mermaid)
   - Data flow between components
   - Key design decisions and rationale
   - Dependencies and their purposes
   - Directory structure explanation
   - Output to: docs/architecture.md

   **For Internals Documentation:**
   - How the system works under the hood
   - Key algorithms and data structures
   - Performance considerations
   - Security considerations
   - Extension points
   - Output to: docs/internals/

   **For Contributing Guide:**
   - Development environment setup
   - Code style and conventions
   - Testing requirements
   - Pull request process
   - Code review guidelines
   - Output to: CONTRIBUTING.md

5. Read source files to ensure accuracy:
   - Core modules and their responsibilities
   - Public APIs and interfaces
   - Configuration and environment setup
   - Test files for usage patterns

6. Generate documentation with:
   - Technical accuracy (based on actual code)
   - Code examples from the codebase
   - Diagrams where helpful (mermaid syntax)
   - Cross-references between related sections

7. If generating multiple doc types, create a docs/README.md index
