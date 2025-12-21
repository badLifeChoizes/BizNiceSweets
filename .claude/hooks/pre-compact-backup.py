#!/usr/bin/env python3
"""
Claude Code Hook: Pre-Compact Auto-Checkpoint

Runs before compaction to automatically save work in progress.
This ensures no progress is lost when context compacts.

Actions:
1. Check for uncommitted changes
2. Create WIP commit if changes exist
3. Add session note to task file
4. Create backup marker
"""
import json
import sys
import os
import subprocess
from datetime import datetime
from pathlib import Path


def run_git(*args, **kwargs):
    """Run a git command in the project directory."""
    cwd = kwargs.pop('cwd', os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
    result = subprocess.run(
        ['git'] + list(args),
        capture_output=True,
        text=True,
        timeout=10,
        cwd=cwd,
        **kwargs
    )
    return result


def get_current_branch():
    """Get the current git branch name."""
    try:
        result = run_git('branch', '--show-current')
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def has_uncommitted_changes():
    """Check if there are uncommitted changes."""
    try:
        # Check for staged or unstaged changes
        result = run_git('status', '--porcelain')
        return bool(result.stdout.strip())
    except Exception:
        return False


def get_diff_summary():
    """Get a brief summary of changes."""
    try:
        result = run_git('diff', '--stat', 'HEAD')
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

        # If no diff from HEAD, check staged changes
        result = run_git('diff', '--stat', '--cached')
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

        # Fall back to status
        result = run_git('status', '--short')
        return result.stdout.strip() if result.returncode == 0 else "Changes present"
    except Exception:
        return "Unable to determine changes"


def create_wip_commit(branch):
    """Create a work-in-progress commit."""
    try:
        # Stage all changes
        run_git('add', '-A')

        # Create commit message
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        commit_msg = f"wip: auto-checkpoint before compaction [{timestamp}]\n\nAuto-saved by PreCompact hook on branch {branch}."

        # Commit
        result = run_git('commit', '-m', commit_msg)

        if result.returncode == 0:
            # Get the commit hash
            hash_result = run_git('rev-parse', '--short', 'HEAD')
            commit_hash = hash_result.stdout.strip() if hash_result.returncode == 0 else "unknown"
            return commit_hash
        return None
    except Exception as e:
        print(f"Warning: Could not create WIP commit: {e}", file=sys.stderr)
        return None


def add_session_note_to_task(project_dir, branch, commit_hash, diff_summary):
    """Add a session note to the task file."""
    task_file = Path(project_dir) / 'docs' / 'tasks' / f'{branch}.md'

    if not task_file.exists():
        return False

    try:
        content = task_file.read_text()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

        # Create session note
        session_note = f"\n## Last Session ({timestamp})\n\n"
        session_note += f"**Auto-checkpointed:** Commit `{commit_hash}`\n\n"
        session_note += "**Changes:**\n```\n"
        session_note += diff_summary
        session_note += "\n```\n\n"
        session_note += "_Context compacted. Review changes and update checklist manually._\n"

        # Find where to insert (before existing "Last Session" or at end before "## Notes")
        if "## Last Session" in content:
            # Replace existing session note
            parts = content.split("## Last Session")
            before = parts[0]
            # Find the next ## section or end of file
            rest = "## Last Session" + parts[1]
            next_section_idx = rest.find("\n## ", 1)
            if next_section_idx > 0:
                after = rest[next_section_idx:]
                content = before + session_note + after
            else:
                content = before + session_note
        elif "## Notes" in content:
            # Insert before Notes section
            content = content.replace("## Notes", session_note + "## Notes")
        else:
            # Append at end
            content = content.rstrip() + "\n\n" + session_note

        task_file.write_text(content)
        return True
    except Exception as e:
        print(f"Warning: Could not update task file: {e}", file=sys.stderr)
        return False


def main():
    # Read input from Claude Code
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        input_data = {}

    project_dir = os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())
    trigger = input_data.get('trigger', 'unknown')
    session_id = input_data.get('session_id', 'unknown')

    # Get current context
    branch = get_current_branch()
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')

    # Create backup directory
    backup_dir = Path(project_dir) / '.claude' / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Initialize backup data
    backup_data = {
        'timestamp': timestamp,
        'trigger': trigger,
        'session_id': session_id,
        'branch': branch,
    }

    # Auto-checkpoint if on a task branch with changes
    if branch and branch not in ['main', 'master', 'develop']:
        task_file = Path(project_dir) / 'docs' / 'tasks' / f'{branch}.md'

        if task_file.exists():
            backup_data['task_file'] = str(task_file)

            # Check for uncommitted changes
            if has_uncommitted_changes():
                print(f"💾 Uncommitted changes detected. Auto-checkpointing...", file=sys.stderr)

                # Get diff summary before committing
                diff_summary = get_diff_summary()

                # Create WIP commit
                commit_hash = create_wip_commit(branch)

                if commit_hash:
                    print(f"   ✓ Created WIP commit: {commit_hash}", file=sys.stderr)
                    backup_data['wip_commit'] = commit_hash

                    # Add session note to task file
                    if add_session_note_to_task(project_dir, branch, commit_hash, diff_summary):
                        print(f"   ✓ Updated task file with session note", file=sys.stderr)

                    print(f"⚠️ Compacting context. Task: {branch}", file=sys.stderr)
                    print(f"   Resume with: /project:status", file=sys.stderr)
                else:
                    print(f"   ⚠️ Could not create WIP commit", file=sys.stderr)
                    print(f"   You may need to manually checkpoint your work", file=sys.stderr)
            else:
                # No changes, just warn
                print(f"📦 Compacting context. Task: {branch} (no uncommitted changes)", file=sys.stderr)
                print(f"   Task context will be re-injected on next prompt.", file=sys.stderr)

            # Read current progress for backup metadata
            try:
                content = task_file.read_text()
                total = content.count('- [ ]') + content.count('- [x]')
                done = content.count('- [x]')
                backup_data['progress'] = f"{done}/{total}"
            except Exception:
                pass
    else:
        # Not on a task branch
        if trigger == 'auto':
            print(f"⚠️ Auto-compacting context. Branch: {branch or 'none'}", file=sys.stderr)
        else:
            print(f"📦 Manual compact requested. Branch: {branch or 'none'}", file=sys.stderr)

    # Write backup marker
    backup_file = backup_dir / f'compact-{trigger}-{timestamp}.json'
    try:
        backup_file.write_text(json.dumps(backup_data, indent=2))
    except Exception as e:
        print(f"Warning: Could not write backup marker: {e}", file=sys.stderr)

    # Exit 0 to allow compaction to proceed
    sys.exit(0)


if __name__ == '__main__':
    main()
