---
description: Scan a project for documentation coverage and generate overview report
---

# Documentation Scan

Perform an initial scan of a project to analyze documentation coverage.

## Arguments

- `$ARGUMENTS`: Path to the project directory (default: current directory)

## Instructions

1. Invoke the `code-docs` skill first
2. Determine the project path from arguments or use current directory
3. Run the overview generator:
   ```bash
   python .claude/skills/code-docs/scripts/generate_overview.py "$ARGUMENTS" --output scan-overview.md
   ```
4. If that succeeds, also run the full analysis:
   ```bash
   python .claude/skills/code-docs/scripts/analyze.py "$ARGUMENTS" --output scan-analysis.json
   python .claude/skills/code-docs/scripts/audit.py scan-analysis.json --format markdown --output scan-audit.md
   ```
5. Present a summary to the user including:
   - Overall documentation coverage percentage
   - Number of files scanned
   - Files with critical coverage (<50%)
   - Files with warning coverage (50-79%)
   - Top 5 files needing immediate attention
6. Ask the user what they'd like to do next:
   - Document specific files
   - Generate documentation templates
   - Create a documentation checklist
