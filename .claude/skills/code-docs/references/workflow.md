# Code Documentation Workflow Guide

Detailed usage instructions for the code-docs skill.

## Best Practice: Organize Output by Date

For tracking documentation progress over time, organize analysis outputs in dated subdirectories:

```bash
# Create dated output directory
DATE=$(date +%Y-%m-%d)
mkdir -p docs/documentation-analysis/$DATE

# Analyze with dated output
python scripts/analyze.py src \
  --output docs/documentation-analysis/$DATE/src-analysis.json \
  --languages js,ts
```

This allows you to:

- Track documentation coverage improvements over time
- Compare analyses from different dates
- Know when analysis becomes stale (recommend re-running monthly)
- Archive historical analyses

## Step 1: Analyze Code Structure

```bash
# Auto-detect language, analyze directory
python scripts/analyze.py /path/to/project --output analysis.json

# Specific languages only
python scripts/analyze.py /path/to/project --languages py,cs,go

# Single language analyzers also available
python scripts/analyze_python.py src/
python scripts/analyze_csharp.py src/

# Recommended: Use dated output directory
DATE=$(date +%Y-%m-%d)
python scripts/analyze.py src --output docs/documentation-analysis/$DATE/src-analysis.json
```

Analysis provides: signatures, parameter types, existing docs, class hierarchies, public/private/async/static modifiers, and staleness issues.

## Step 2: Audit Documentation Coverage

```bash
python scripts/audit.py analysis.json --format markdown --output report.md
```

Outputs coverage percentage, stale doc warnings, health score, and per-file breakdown. See `staleness-detection.md` for issue types.

### Generate Documentation Checklist

```bash
# Generate checklist from analysis
python scripts/generate_checklist.py analysis.json --output checklist.yml

# Include only files below 80% coverage
python scripts/generate_checklist.py analysis.json --min-coverage 80 --output checklist.yml

# Recommended: Use dated output directory
DATE=$(date +%Y-%m-%d)
python scripts/generate_checklist.py docs/documentation-analysis/$DATE/src-analysis.json \
  --output docs/documentation-analysis/$DATE/documentation-checklist.yml \
  --min-coverage 80
```

Creates a YAML checklist of files that need documentation. The checklist includes:

- File paths with priority levels (critical, high, medium, low)
- Current coverage percentage
- Number of undocumented elements
- Status tracking (pending, in_progress, completed)
- Completion timestamps and notes

### Update Documentation Checklist

```bash
# Mark a file as completed
python scripts/update_checklist.py checklist.yml \
  --file "lessonPlanController.ts" \
  --status completed \
  --notes "Added comprehensive JSDoc documentation"

# Mark as in progress
python scripts/update_checklist.py checklist.yml \
  --file "validator.ts" \
  --status in_progress

# Update multiple files with wildcard
python scripts/update_checklist.py checklist.yml \
  --file "src/api/controllers/*.ts" \
  --status completed
```

### Automated Checklist Update Workflow

After documenting a file, automatically re-analyze it and update checklists:

```bash
# Windows
scripts\update_docs_checklist.bat src\api\controllers\lessonPlanController.ts

# Windows with notes
scripts\update_docs_checklist.bat src\api\controllers\lessonPlanController.ts "Added comprehensive JSDoc documentation"

# Linux/Mac
./scripts/update_docs_checklist.sh src/api/controllers/lessonPlanController.ts

# Linux/Mac with notes
./scripts/update_docs_checklist.sh src/api/controllers/lessonPlanController.ts "Added comprehensive JSDoc documentation"
```

This workflow script:

1. Re-analyzes the file to get current documentation coverage
2. Automatically updates the YAML checklist (marks as completed if coverage >= 100%)
3. Provides guidance for updating the Markdown checklist
4. Shows coverage status with visual feedback

**Recommended workflow:**

1. Read the file and understand its purpose
2. Add JSDoc/TSDoc comments to all functions, classes, and interfaces
3. Run `update_docs_checklist.bat` to verify coverage and update checklists
4. Commit changes if coverage is satisfactory

## Step 3: Score README (Optional)

```bash
python scripts/score_readme.py /path/to/project
```

Checks for essential sections, code examples, badges, images, and table of contents.

## Step 4: Generate Templates for Undocumented Code

```bash
python scripts/generate_templates.py analysis.json
python scripts/generate_templates.py analysis.json --style google  # Force Python style
```

Generates doc templates in the appropriate format per language. See `standards.md` for format details.

## Step 5: Write Documentation

Using analysis output, write documentation that:

- Describes **what the code actually does** (read the implementation)
- Documents **all parameters** with actual types and purposes
- Explains **return values** and when they vary
- Notes **side effects**, **exceptions**, and **edge cases**
- Uses correct style per language (see `standards.md`)

## Tips

- **Read the code**: Analysis gives structure; understanding comes from reading
- **Fix stale docs first**: Wrong documentation is worse than none
- **Be specific**: "Validates user input" → "Validates email format and checks domain against blocklist"
- **Document behavior**: What happens with null? Empty arrays? Negative numbers?
- **Skip obvious**: `__init__` that just assigns `self.x = x` needs minimal docs
- **Match codebase style**: Continue existing patterns (Args:/Returns:, @param, etc.)
- **Use templates**: Don't start from scratch—use `generate_templates.py` output
- **Set coverage targets**: Aim for 100%+ on public APIs
- **Organize by date**: Use `docs/documentation-analysis/YYYY-MM-DD/` structure to track progress