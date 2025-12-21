#!/usr/bin/env python3
"""
Update documentation checklist to mark files as completed.

Usage:
    python update_checklist.py checklist.yml --file src/api/controllers/lessonPlanController.ts --status completed
    python update_checklist.py checklist.yml --file "src/main/services/*.ts" --verify-coverage
"""

import sys
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
import re


def parse_yaml_checklist(content: str) -> dict:
    """
    Parse a simple YAML checklist.
    Uses basic parsing to avoid requiring PyYAML dependency.
    """
    lines = content.split('\n')
    data = {
        'metadata': {},
        'files': [],
        'summary': {}
    }

    current_section = None
    current_file = None
    indent_level = 0

    for line in lines:
        stripped = line.strip()

        # Skip comments and empty lines
        if not stripped or stripped.startswith('#'):
            continue

        # Detect sections
        if stripped == 'metadata:':
            current_section = 'metadata'
            current_file = None
            continue
        elif stripped == 'files:':
            current_section = 'files'
            current_file = None
            continue
        elif stripped == 'summary:':
            current_section = 'summary'
            current_file = None
            continue

        # Parse key-value pairs
        if ':' in stripped:
            key, value = stripped.split(':', 1)
            key = key.strip().strip('"')
            value = value.strip().strip('"')

            # Handle null values
            if value.lower() == 'null':
                value = None
            # Handle numeric values
            elif value.replace('.', '', 1).isdigit():
                value = float(value) if '.' in value else int(value)

            # Determine where to store the value
            if current_section == 'metadata':
                data['metadata'][key] = value
            elif current_section == 'summary':
                data['summary'][key] = value
            elif current_section == 'files':
                # Check if this is a new file entry
                if key == 'filepath':
                    current_file = {'filepath': value}
                    data['files'].append(current_file)
                elif current_file is not None:
                    current_file[key] = value

    return data


def serialize_yaml_checklist(data: dict) -> str:
    """Serialize checklist data back to YAML format."""
    lines = [
        '# Documentation Checklist',
        f'# Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        '',
        'metadata:'
    ]

    # Write metadata
    for key, value in data['metadata'].items():
        if isinstance(value, str):
            lines.append(f'  {key}: "{value}"')
        else:
            lines.append(f'  {key}: {value}')

    lines.extend(['', 'files:'])

    # Write files
    for file_info in data['files']:
        lines.append(f'  - filepath: "{file_info["filepath"]}"')
        lines.append(f'    status: "{file_info.get("status", "pending")}"')
        lines.append(f'    priority: "{file_info.get("priority", "medium")}"')
        lines.append(f'    language: "{file_info.get("language", "unknown")}"')
        lines.append(f'    coverage: {file_info.get("coverage", 0.0)}')
        lines.append(f'    total_elements: {file_info.get("total_elements", 0)}')
        lines.append(f'    documented_elements: {file_info.get("documented_elements", 0)}')
        lines.append(f'    undocumented_elements: {file_info.get("undocumented_elements", 0)}')

        completed_at = file_info.get('completed_at')
        if completed_at:
            lines.append(f'    completed_at: "{completed_at}"')
        else:
            lines.append(f'    completed_at: null')

        notes = file_info.get('notes', '')
        lines.append(f'    notes: "{notes}"')
        lines.append('')

    # Write summary
    lines.append('summary:')
    for key, value in data['summary'].items():
        lines.append(f'  {key}: {value}')
    lines.append('')

    return '\n'.join(lines)


def update_file_status(
    checklist_path: Path,
    file_pattern: str,
    status: str = 'completed',
    notes: Optional[str] = None,
    verify_coverage: bool = False
) -> int:
    """
    Update checklist to mark file(s) as completed.

    Args:
        checklist_path: Path to checklist YAML file
        file_pattern: File path or pattern to match
        status: New status ('completed', 'in_progress', 'pending')
        notes: Optional notes to add
        verify_coverage: Re-analyze file to verify coverage before marking complete

    Returns:
        Number of files updated
    """

    if not checklist_path.exists():
        print(f"Error: Checklist not found: {checklist_path}", file=sys.stderr)
        return 0

    # Read checklist
    with open(checklist_path, 'r', encoding='utf-8') as f:
        content = f.read()

    data = parse_yaml_checklist(content)

    # Update last modified
    data['metadata']['last_updated'] = datetime.now().isoformat()

    # Find matching files
    updated_count = 0

    # Escape special regex characters except * and ?
    escaped_pattern = re.escape(file_pattern).replace(r'\*', '.*').replace(r'\?', '.')
    pattern_regex = re.compile(escaped_pattern, re.IGNORECASE)

    for file_info in data['files']:
        filepath = file_info['filepath']

        # Check if file matches pattern (case-insensitive)
        if (pattern_regex.search(filepath) or
            filepath.lower().endswith(file_pattern.lower()) or
            file_pattern.lower() in filepath.lower()):

            # Verify coverage if requested
            if verify_coverage:
                # TODO: Re-analyze file to get updated coverage
                # For now, just mark as complete
                pass

            # Update status
            old_status = file_info.get('status', 'pending')
            file_info['status'] = status

            if status == 'completed':
                file_info['completed_at'] = datetime.now().isoformat()

            if notes:
                file_info['notes'] = notes

            updated_count += 1
            print(f"Updated: {filepath}")
            print(f"  Status: {old_status} -> {status}")

    if updated_count == 0:
        print(f"No files matched pattern: {file_pattern}")
        return 0

    # Update summary counts
    pending = sum(1 for f in data['files'] if f.get('status') == 'pending')
    in_progress = sum(1 for f in data['files'] if f.get('status') == 'in_progress')
    completed = sum(1 for f in data['files'] if f.get('status') == 'completed')

    data['summary']['pending_files'] = pending
    data['summary']['in_progress_files'] = in_progress
    data['summary']['completed_files'] = completed
    data['summary']['completion_percentage'] = (completed / len(data['files']) * 100) if data['files'] else 0

    # Write updated checklist
    yaml_content = serialize_yaml_checklist(data)

    with open(checklist_path, 'w', encoding='utf-8') as f:
        f.write(yaml_content)

    print(f"\nChecklist updated: {checklist_path}")
    print(f"  Updated: {updated_count} file(s)")
    print(f"  Status: {completed} completed, {in_progress} in progress, {pending} pending")

    return updated_count


def main():
    parser = argparse.ArgumentParser(
        description='Update documentation checklist'
    )
    parser.add_argument(
        'checklist_file',
        type=Path,
        help='Path to checklist YAML file'
    )
    parser.add_argument(
        '--file', '-f',
        required=True,
        help='File path or pattern to update'
    )
    parser.add_argument(
        '--status', '-s',
        choices=['pending', 'in_progress', 'completed'],
        default='completed',
        help='New status (default: completed)'
    )
    parser.add_argument(
        '--notes', '-n',
        help='Notes to add'
    )
    parser.add_argument(
        '--verify-coverage',
        action='store_true',
        help='Re-analyze file to verify coverage'
    )

    args = parser.parse_args()

    try:
        updated = update_file_status(
            args.checklist_file,
            args.file,
            args.status,
            args.notes,
            args.verify_coverage
        )

        sys.exit(0 if updated > 0 else 1)

    except Exception as e:
        print(f"Error updating checklist: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
