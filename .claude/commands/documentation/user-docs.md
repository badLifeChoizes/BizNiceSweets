---
description: Generate user-facing documentation (README, guides, tutorials)
---

# Generate User Documentation

Create user-facing documentation such as README files, getting started guides, and user tutorials.

## Arguments

- `$ARGUMENTS`: Type of documentation to generate (readme, guide, tutorial) and optional focus area

## Instructions

1. Parse arguments to determine documentation type:
   - `readme` - Generate or improve README.md
   - `guide` - Create a getting started guide
   - `tutorial` - Create a step-by-step tutorial
   - If empty, default to `readme`

2. Invoke the `code-docs` skill

3. Analyze the project structure:
   ```bash
   python .claude/skills/code-docs/scripts/generate_overview.py . --output project-overview.md
   ```

4. If existing README exists, score it:
   ```bash
   python .claude/skills/code-docs/scripts/score_readme.py .
   ```

5. Based on the documentation type:

   **For README:**
   - Include project title and description
   - Installation instructions
   - Quick start / basic usage
   - Configuration options
   - API overview (if applicable)
   - Contributing guidelines
   - License information

   **For Getting Started Guide:**
   - Prerequisites
   - Installation steps
   - First-time setup
   - Basic usage examples
   - Common tasks walkthrough
   - Troubleshooting tips

   **For Tutorial:**
   - Learning objectives
   - Step-by-step instructions with code examples
   - Explanations of key concepts
   - Practice exercises
   - Next steps / further reading

6. Read relevant source files to ensure documentation accuracy:
   - Entry points (main.py, index.js, etc.)
   - Configuration files (package.json, setup.py, etc.)
   - Existing documentation

7. Generate the documentation with:
   - Clear, concise language
   - Code examples that actually work
   - Proper markdown formatting
   - Links to related documentation

8. Output location:
   - README: Project root as README.md
   - Guide: docs/getting-started.md
   - Tutorial: docs/tutorials/{topic}.md
