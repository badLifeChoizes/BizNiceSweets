---
name: code-docs
description: Analyze code documentation across multiple languages (Python, JavaScript/TypeScript, C/C++, C#, Go, Rust). Use when (1) auditing documentation coverage, (2) finding undocumented code, (3) generating doc templates, (4) assessing README quality, (5) detecting stale documentation, or (6) adding documentation comments (JSDoc, Sphinx, Doxygen, XML docs, Go doc, Rust doc). (project)
---

# Code Documentation Assistant

Analyze code structure to write accurate, professional documentation across 6 languages.

## Overview

This skill provides analysis tools to understand code structure accurately. Claude then applies reasoning to write meaningful documentation—not generic placeholders. The tools also detect stale documentation where docs no longer match code.

## Supported Languages

Python (AST), JavaScript/TypeScript, C/C++, C#, Go, Rust

## Core Workflow

1. **Analyze**: `python scripts/analyze.py /path/to/project --output analysis.json`
2. **Audit**: `python scripts/audit.py analysis.json --format markdown`
3. **Generate templates**: `python scripts/generate_templates.py analysis.json`
4. **Write documentation** using analysis output and correct style per language

See `references/workflow.md` for detailed usage examples and best practices.

## Scripts

| Script | Purpose |
|--------|---------|
| `analyze.py` | Multi-language code structure analysis |
| `audit.py` | Documentation coverage reporting |
| `generate_templates.py` | Generate doc templates for undocumented code |
| `generate_checklist.py` | Create YAML checklist of files needing docs |
| `update_checklist.py` | Update checklist status |
| `score_readme.py` | Assess README quality |

## References

| File | Contents |
|------|----------|
| `references/workflow.md` | Detailed usage examples and tips |
| `references/standards.md` | Doc format standards per language |
| `references/language-notes.md` | Language-specific parsing details |
| `references/staleness-detection.md` | Stale documentation issue types |
| `references/ci-integration.md` | CI/CD integration examples |
