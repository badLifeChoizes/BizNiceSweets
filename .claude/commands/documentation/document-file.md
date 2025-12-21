---
description: Analyze and add documentation to a specific file
---

# Document File

Analyze a specific file and add appropriate documentation comments.

## Arguments

- `$ARGUMENTS`: Path to the file to document

## Instructions

1. If no file path provided, ask the user which file to document
2. Read the file to understand its contents and purpose
3. Invoke the `code-docs` skill
4. Analyze the specific file:
   ```bash
   python .claude/skills/code-docs/scripts/analyze.py "$ARGUMENTS" --output file-analysis.json
   ```
5. Generate documentation templates for undocumented elements:
   ```bash
   python .claude/skills/code-docs/scripts/generate_templates.py file-analysis.json
   ```
6. Based on the file language, add appropriate documentation:
   - **Python**: Google-style docstrings (Args, Returns, Raises)
   - **JavaScript/TypeScript**: JSDoc comments (@param, @returns, @throws)
   - **C/C++**: Doxygen comments (@brief, @param, @return)
   - **C#**: XML documentation (summary, param, returns)
   - **Go**: Go doc comments (package and function comments)
   - **Rust**: Rust doc comments (///, //!)
7. For each undocumented function/class/method:
   - Read the implementation to understand what it actually does
   - Document parameters with their types and purposes
   - Document return values and when they vary
   - Note any side effects, exceptions, or edge cases
8. Apply the documentation using the Edit tool
9. Re-analyze to verify coverage improved:
   ```bash
   python .claude/skills/code-docs/scripts/analyze.py "$ARGUMENTS" --output file-analysis-after.json
   python .claude/skills/code-docs/scripts/audit.py file-analysis-after.json --format markdown
   ```
10. Report the before/after coverage improvement
