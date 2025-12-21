---
description: Explain features, architecture, or code sections in detail
---

# Explain Code

Provide detailed explanations of features, architecture patterns, or specific code sections.

## Arguments

- `$ARGUMENTS`: What to explain - can be a file path, feature name, or architectural concept

## Instructions

1. Parse arguments to determine what to explain:
   - File path: Explain that specific file
   - Feature name: Explain how that feature works
   - "architecture": Explain overall system architecture
   - "flow:{name}": Explain a specific data/control flow
   - Empty: Ask user what they want explained

2. Invoke the `code-docs` skill

3. Gather context:
   ```bash
   python .claude/skills/code-docs/scripts/generate_overview.py . --output context-overview.md --depth 2
   ```

4. Based on what's being explained:

   **For a specific file:**
   - Read the file completely
   - Explain the file's purpose and responsibility
   - Walk through key functions/classes
   - Explain how it fits into the larger system
   - Note any important patterns or design decisions

   **For a feature:**
   - Identify all files involved in the feature
   - Trace the code path from entry to completion
   - Explain the data transformations
   - Document any external dependencies
   - Provide usage examples

   **For architecture:**
   - Describe the overall system design
   - Explain the layer/module structure
   - Document communication patterns
   - Highlight key abstractions
   - Explain the "why" behind design choices

   **For a specific flow:**
   - Start from the trigger/entry point
   - Trace through each step
   - Document data transformations
   - Note async/sync boundaries
   - Explain error handling

5. Explanation format:
   - Start with a high-level summary (1-2 sentences)
   - Provide detailed breakdown with code references
   - Use diagrams (mermaid) for complex flows
   - Include relevant code snippets
   - End with related topics or next steps

6. Output options:
   - Direct response for quick explanations
   - Save to docs/explanations/{topic}.md for detailed ones
   - Ask user preference for length/depth

7. Always cite specific file:line references for code mentions
