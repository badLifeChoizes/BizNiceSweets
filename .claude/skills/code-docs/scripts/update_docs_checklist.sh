#!/bin/bash
# Update Documentation Checklist after documenting a file
#
# Usage:
#   ./update_docs_checklist.sh path/to/file.ts
#   ./update_docs_checklist.sh path/to/file.ts "Added comprehensive JSDoc comments"

set -e

FILE_PATH="$1"
NOTES="$2"

if [ -z "$FILE_PATH" ]; then
    echo "❌ Error: File path required"
    echo "Usage: $0 <file_path> [notes]"
    exit 1
fi

if [ ! -f "$FILE_PATH" ]; then
    echo "❌ Error: File not found: $FILE_PATH"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find project root (directory containing .claude)
CURRENT_DIR="$(pwd)"
PROJECT_ROOT=""

while [ "$CURRENT_DIR" != "/" ]; do
    if [ -d "$CURRENT_DIR/.claude" ]; then
        PROJECT_ROOT="$CURRENT_DIR"
        break
    fi
    CURRENT_DIR="$(dirname "$CURRENT_DIR")"
done

if [ -z "$PROJECT_ROOT" ]; then
    echo "⚠️  Warning: Could not find project root (.claude directory)"
    PROJECT_ROOT="$(pwd)"
fi

# Find the most recent documentation analysis directory
DOC_ANALYSIS_DIR="$PROJECT_ROOT/docs/documentation-analysis"

if [ ! -d "$DOC_ANALYSIS_DIR" ]; then
    echo "❌ Error: Documentation analysis directory not found: $DOC_ANALYSIS_DIR"
    exit 1
fi

# Get the most recent dated directory
LATEST_DIR=$(ls -1d "$DOC_ANALYSIS_DIR"/*/ 2>/dev/null | sort -r | head -1)

if [ -z "$LATEST_DIR" ]; then
    echo "❌ Error: No dated analysis directories found in $DOC_ANALYSIS_DIR"
    exit 1
fi

LATEST_DIR="${LATEST_DIR%/}"  # Remove trailing slash

echo "📋 Documentation Checklist Updater"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📁 Analysis directory: $(basename "$LATEST_DIR")"
echo "📄 File: $FILE_PATH"
echo ""

# Find checklists
YAML_CHECKLIST="$LATEST_DIR/documentation-checklist.yml"
MARKDOWN_CHECKLIST="$LATEST_DIR/DOCUMENTATION_CHECKLIST.md"

if [ ! -f "$YAML_CHECKLIST" ] && [ ! -f "$MARKDOWN_CHECKLIST" ]; then
    echo "❌ Error: No checklists found in $LATEST_DIR"
    echo "   Expected: documentation-checklist.yml or DOCUMENTATION_CHECKLIST.md"
    exit 1
fi

# Step 1: Re-analyze the file
echo "🔍 Step 1: Re-analyzing file for documentation coverage..."
echo ""

ANALYSIS_OUTPUT=$(python -X utf8 "$SCRIPT_DIR/analyze.py" "$FILE_PATH" 2>&1)
ANALYSIS_EXIT=$?

if [ $ANALYSIS_EXIT -ne 0 ]; then
    echo "⚠️  Analysis had issues:"
    echo "$ANALYSIS_OUTPUT"
    echo ""
fi

# Extract coverage information from analysis output
COVERAGE=$(echo "$ANALYSIS_OUTPUT" | grep -oP 'Coverage:\s+\K[0-9.]+' | head -1)
DOCUMENTED=$(echo "$ANALYSIS_OUTPUT" | grep -oP 'Documented:\s+\K[0-9]+' | head -1)
TOTAL=$(echo "$ANALYSIS_OUTPUT" | grep -oP 'Total:\s+\K[0-9]+' | head -1)

if [ -z "$COVERAGE" ]; then
    echo "⚠️  Could not parse coverage information from analysis"
    echo "   Proceeding with manual update..."
    COVERAGE="unknown"
    DOCUMENTED="?"
    TOTAL="?"
else
    echo "📊 Coverage: ${COVERAGE}%"
    echo "   Elements: $DOCUMENTED/$TOTAL documented"
    echo ""
fi

# Get relative file path for checklist update
RELATIVE_PATH="$FILE_PATH"
if [[ "$FILE_PATH" == *"command-center"* ]]; then
    # Extract path after command-center
    RELATIVE_PATH="${FILE_PATH#*command-center/}"
    RELATIVE_PATH="${RELATIVE_PATH#*command-center\\}"
fi

# Step 2: Update YAML checklist if it exists
if [ -f "$YAML_CHECKLIST" ]; then
    echo "📝 Step 2a: Updating YAML checklist..."

    UPDATE_CMD="python -X utf8 \"$SCRIPT_DIR/update_checklist.py\" \"$YAML_CHECKLIST\" --file \"$RELATIVE_PATH\" --status completed"

    if [ -n "$NOTES" ]; then
        UPDATE_CMD="$UPDATE_CMD --notes \"$NOTES\""
    fi

    eval $UPDATE_CMD
    echo ""
fi

# Step 3: Update Markdown checklist if it exists
if [ -f "$MARKDOWN_CHECKLIST" ]; then
    echo "📝 Step 2b: Updating Markdown checklist..."

    # For Markdown, we need to manually edit since we don't have a dedicated updater yet
    # This is a TODO - for now just report what needs to be done
    echo "   ℹ️  Manual update required for Markdown checklist"
    echo "   File: $MARKDOWN_CHECKLIST"
    echo "   Pattern to find: $RELATIVE_PATH"
    echo "   Change: [ ] → [x] if coverage >= 100%"
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Checklist update complete!"
echo ""

if [ -n "$COVERAGE" ] && [ "$COVERAGE" != "unknown" ]; then
    if (( $(echo "$COVERAGE >= 100" | bc -l) )); then
        echo "🎉 File is fully documented! (${COVERAGE}%)"
    elif (( $(echo "$COVERAGE >= 70" | bc -l) )); then
        echo "🟡 File is partially documented (${COVERAGE}%) - consider adding more documentation"
    else
        echo "🔴 File needs more documentation (${COVERAGE}%) - only $DOCUMENTED/$TOTAL elements documented"
    fi
fi

exit 0
