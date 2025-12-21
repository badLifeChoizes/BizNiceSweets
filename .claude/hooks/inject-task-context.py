#!/usr/bin/env python3
"""
Claude Code Hook: Inject Task Context

Runs on UserPromptSubmit to inject current task context into every prompt.
This keeps Claude aware of the active task even after compaction.

=== MIGRATION INSTRUCTIONS ===
This hook has two modes:
1. LEGACY MODE (current): Uses original feature doc paths
2. RESTRUCTURED MODE: Uses new _restructure/ paths with INVARIANTS

To switch to restructured mode:
1. Complete feature migration (Phase 4 of PROPOSAL.md)
2. Set USE_RESTRUCTURED_DOCS = True below
3. Remove the "# LEGACY:" comments and legacy code blocks
"""
import json
import sys
import os
import subprocess
from pathlib import Path


# =============================================================================
# CONFIGURATION: Restructured docs are now active
# =============================================================================
USE_RESTRUCTURED_DOCS = True


def get_current_branch():
    """Get the current git branch name."""
    try:
        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


# =============================================================================
# LEGACY: Archived original feature docs (kept for reference)
# =============================================================================
FEATURE_DOCS_LEGACY = {
    'session': ('docs/features/_archive/sessions.md', 'SESS'),
    'device': ('docs/features/_archive/devices.md', 'DEV'),
    'participant': ('docs/features/_archive/participants.md', 'PART'),
    'lesson': ('docs/features/_archive/lesson-plans.md', 'LP'),
    'plugin': ('docs/features/_archive/plugins.md', 'PLUG'),
    'provider': ('docs/features/_archive/provider-network.md', 'PN'),
    'arch': ('docs/features/INDEX.md', 'ARCH'),
}


# =============================================================================
# RESTRUCTURED: Feature mapping with INVARIANTS and dependencies
# =============================================================================
FEATURE_DOCS_RESTRUCTURED = {
    'session': {
        'name': 'Sessions',
        'readme': 'docs/features/sessions/README.md',
        'invariants': 'docs/features/sessions/INVARIANTS.md',
        'invariants_count': 27,
        'dependencies': ['devices', 'participants', 'bento-grid'],
        'prefix': 'SESS'
    },
    'device': {
        'name': 'Devices',
        'readme': 'docs/features/devices/README.md',
        'invariants': 'docs/features/devices/INVARIANTS.md',
        'invariants_count': 26,
        'dependencies': ['plugins'],
        'prefix': 'DEV'
    },
    'participant': {
        'name': 'Participants',
        'readme': 'docs/features/participants/README.md',
        'invariants': 'docs/features/participants/INVARIANTS.md',
        'invariants_count': 27,
        'dependencies': [],
        'prefix': 'PART'
    },
    'lesson': {
        'name': 'Lesson Plans',
        'readme': 'docs/features/lesson-plans/README.md',
        'invariants': 'docs/features/lesson-plans/INVARIANTS.md',
        'invariants_count': 24,
        'dependencies': ['participants', 'devices', 'plugins'],
        'prefix': 'LP'
    },
    'plugin': {
        'name': 'Plugins',
        'readme': 'docs/features/plugins/README.md',
        'invariants': 'docs/features/plugins/INVARIANTS.md',
        'invariants_count': 30,
        'dependencies': [],
        'prefix': 'PLUG'
    },
    'provider': {
        'name': 'Provider Network',
        'readme': 'docs/features/provider-network/README.md',
        'invariants': 'docs/features/provider-network/INVARIANTS.md',
        'invariants_count': 10,
        'dependencies': [],
        'prefix': 'PN'
    },
    'arch': {
        'name': 'Architecture',
        'readme': 'docs/features/INDEX.md',
        'invariants': None,
        'invariants_count': 0,
        'dependencies': [],
        'prefix': 'ARCH'
    },
    # UI / Cross-cutting concerns
    'bento': {
        'name': 'Bento Grid',
        'readme': 'docs/features/ui/bento-grid/README.md',
        'invariants': 'docs/features/ui/bento-grid/INVARIANTS.md',
        'invariants_count': 28,
        'dependencies': [],
        'prefix': None  # No requirements, just invariants
    },
    'ui': {
        'name': 'Bento Grid',  # Alias for bento
        'readme': 'docs/features/ui/bento-grid/README.md',
        'invariants': 'docs/features/ui/bento-grid/INVARIANTS.md',
        'invariants_count': 28,
        'dependencies': [],
        'prefix': None
    },
    'grid': {
        'name': 'Bento Grid',  # Alias for bento
        'readme': 'docs/features/ui/bento-grid/README.md',
        'invariants': 'docs/features/ui/bento-grid/INVARIANTS.md',
        'invariants_count': 28,
        'dependencies': [],
        'prefix': None
    },
    'tile': {
        'name': 'Bento Grid',  # Alias for bento
        'readme': 'docs/features/ui/bento-grid/README.md',
        'invariants': 'docs/features/ui/bento-grid/INVARIANTS.md',
        'invariants_count': 28,
        'dependencies': [],
        'prefix': None
    },
    'layout': {
        'name': 'Bento Grid',  # Alias for bento
        'readme': 'docs/features/ui/bento-grid/README.md',
        'invariants': 'docs/features/ui/bento-grid/INVARIANTS.md',
        'invariants_count': 28,
        'dependencies': [],
        'prefix': None
    },
}


def load_custom_features(project_dir):
    """Load additional feature mappings from config file (for dynamically added features)."""
    config_file = Path(project_dir) / '.claude' / 'feature-mappings.json'
    if config_file.exists():
        try:
            with open(config_file) as f:
                custom = json.load(f)
                # Merge with built-in (custom overrides built-in)
                if USE_RESTRUCTURED_DOCS:
                    for keyword, mapping in custom.items():
                        FEATURE_DOCS_RESTRUCTURED[keyword] = mapping
                else:
                    for keyword, mapping in custom.items():
                        FEATURE_DOCS_LEGACY[keyword] = (mapping['doc'], mapping['prefix'])
        except Exception:
            pass  # Silently ignore config errors


def get_feature_doc_for_branch_legacy(branch):
    """LEGACY: Detect feature from branch name and return doc path and prefix."""
    if not branch:
        return None, None

    branch_lower = branch.lower()
    for keyword, (doc_path, req_prefix) in FEATURE_DOCS_LEGACY.items():
        if keyword in branch_lower:
            return doc_path, req_prefix

    return None, None


def get_feature_for_branch_restructured(branch):
    """RESTRUCTURED: Detect feature from branch name and return full feature info."""
    if not branch:
        return None

    branch_lower = branch.lower()
    for keyword, feature_info in FEATURE_DOCS_RESTRUCTURED.items():
        if keyword in branch_lower:
            return feature_info

    return None


def get_dependency_invariants(feature_info, project_dir):
    """Get invariants info for all dependencies of a feature."""
    deps = []
    for dep_keyword in feature_info.get('dependencies', []):
        if dep_keyword in FEATURE_DOCS_RESTRUCTURED:
            dep_info = FEATURE_DOCS_RESTRUCTURED[dep_keyword]
            if dep_info.get('invariants'):
                # Check if the file actually exists
                inv_path = Path(project_dir) / dep_info['invariants']
                if inv_path.exists():
                    deps.append({
                        'name': dep_info['name'],
                        'invariants': dep_info['invariants'],
                        'count': dep_info.get('invariants_count', 0)
                    })
    return deps


def get_task_summary(project_dir, branch):
    """Read the task file and extract progress info."""
    task_file = Path(project_dir) / 'docs' / 'tasks' / f'{branch}.md'

    if not task_file.exists():
        return None

    try:
        content = task_file.read_text()
    except Exception:
        return None

    # Count checklist progress
    total = content.count('- [ ]') + content.count('- [x]')
    done = content.count('- [x]')

    # Find next unchecked item
    lines = content.split('\n')
    next_item = None
    for line in lines:
        if '- [ ]' in line:
            # Clean up the item text
            next_item = line.replace('- [ ]', '').strip()
            # Remove any trailing comments
            if '<!--' in next_item:
                next_item = next_item.split('<!--')[0].strip()
            break

    # Extract goal if present
    goal = None
    in_goal = False
    for line in lines:
        if line.strip() == '## Goal':
            in_goal = True
            continue
        if in_goal:
            if line.startswith('##'):
                break
            if line.strip():
                goal = line.strip()
                break

    return {
        'total': total,
        'done': done,
        'next': next_item,
        'goal': goal
    }


def build_context_legacy(branch, task, feature_doc, req_prefix):
    """LEGACY: Build context string using old format."""
    context_parts = []
    context_parts.append(f"Workflow reminder: Check /project:status for current task. Update docs/tasks/{{branch}}.md checklist after changes.")

    return "\n".join(context_parts)


def build_context_restructured(branch, task, feature_info, project_dir):
    """RESTRUCTURED: Build context string with INVARIANTS awareness."""
    context_parts = []

    # Basic task info
    context_parts.append(f"🎯 Active task: {branch}")

    if task:
        progress_pct = round((task['done'] / task['total']) * 100) if task['total'] > 0 else 0
        context_parts.append(f"📊 Progress: {task['done']}/{task['total']} ({progress_pct}%)")

        if task['next']:
            context_parts.append(f"➡️ Next item: {task['next']}")
        elif task['done'] == task['total'] and task['total'] > 0:
            context_parts.append("✅ All items complete! Run /project:finish-task")
    else:
        context_parts.append(f"⚠️ No task file: docs/tasks/{branch}.md")
        context_parts.append("Create one with: /project:new-task " + branch)

    # Feature and INVARIANTS info
    if feature_info:
        context_parts.append("")
        context_parts.append(f"📖 Feature: {feature_info['name']}")

        if feature_info.get('invariants'):
            inv_path = Path(project_dir) / feature_info['invariants']
            if inv_path.exists():
                count = feature_info.get('invariants_count', '?')
                context_parts.append(f"   INVARIANTS: @{feature_info['invariants']} ({count} rules)")

        if feature_info.get('prefix'):
            context_parts.append(f"   Requirements: {feature_info['prefix']}-*")

        # Cross-feature dependencies
        dep_invariants = get_dependency_invariants(feature_info, project_dir)
        if dep_invariants:
            context_parts.append("")
            context_parts.append("⚠️ Cross-feature dependencies (read INVARIANTS):")
            for dep in dep_invariants:
                context_parts.append(f"   - {dep['name']}: @{dep['invariants']} ({dep['count']} rules)")

    context_parts.append("")
    context_parts.append("📋 Update checklist after each change. Run /project:checkpoint to commit.")

    return "\n".join(context_parts)


def main():
    # Read input from Claude Code
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # Continue without injection if input is invalid

    project_dir = os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())

    # Load any custom feature mappings (from add-feature command)
    load_custom_features(project_dir)

    # Get current branch
    branch = get_current_branch()

    # Skip injection if on main/master or no branch
    if not branch or branch in ['main', 'master', 'develop']:
        sys.exit(0)

    # Get task info
    task = get_task_summary(project_dir, branch)

    # Build context based on mode
    if USE_RESTRUCTURED_DOCS:
        # RESTRUCTURED MODE: Use new paths with INVARIANTS
        feature_info = get_feature_for_branch_restructured(branch)
        context = build_context_restructured(branch, task, feature_info, project_dir)
    else:
        # LEGACY MODE: Use original paths
        feature_doc, req_prefix = get_feature_doc_for_branch_legacy(branch)
        context = build_context_legacy(branch, task, feature_doc, req_prefix)

    # Output JSON for Claude Code to inject
    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context
        }
    }

    print(json.dumps(output))
    sys.exit(0)


if __name__ == '__main__':
    main()
