#!/usr/bin/env python3
"""
Generate a documentation checklist from analysis JSON files.

Creates a YAML checklist file that tracks documentation progress for files
that need documentation. The checklist can be updated as files are documented.

Usage:
    python generate_checklist.py analysis.json --output checklist.yml
    python generate_checklist.py analysis.json --min-coverage 80 --output checklist.yml
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any


def calculate_coverage(element_stats: Dict[str, Any]) -> float:
    """Calculate documentation coverage percentage."""
    total = element_stats.get('total', 0)
    documented = element_stats.get('documented', 0)

    if total == 0:
        return 100.0

    return (documented / total) * 100


def get_priority(coverage: float, undocumented: int) -> str:
    """Determine priority level based on coverage and undocumented count."""
    if coverage == 0 or undocumented > 30:
        return 'critical'
    elif coverage < 40 or undocumented > 15:
        return 'high'
    elif coverage < 70 or undocumented > 5:
        return 'medium'
    else:
        return 'low'


def generate_checklist(analysis_file: Path, min_coverage: float = 100.0, output_file: Path = None) -> str:
    """
    Generate a YAML checklist from analysis JSON.

    Args:
        analysis_file: Path to analysis JSON file
        min_coverage: Minimum coverage threshold (files below this are included)
        output_file: Optional output file path

    Returns:
        YAML checklist content as string
    """

    with open(analysis_file, 'r', encoding='utf-8') as f:
        analysis = json.load(f)

    # Collect files that need documentation
    files_to_document = []

    # Handle different analysis structures
    if isinstance(analysis, dict) and 'files' in analysis:
        # Directory analysis with file list (most common format from analyze.py)
        for file_data in analysis.get('files', []):
            # Calculate stats from elements array
            elements = file_data.get('elements', [])
            if not elements:
                continue

            total = len(elements)
            documented = sum(1 for el in elements if el.get('docstring'))
            undocumented = total - documented
            coverage = (documented / total * 100) if total > 0 else 100.0

            if coverage < min_coverage:
                files_to_document.append({
                    'filepath': file_data['filepath'],
                    'coverage': coverage,
                    'undocumented': undocumented,
                    'total': total,
                    'documented': documented,
                    'priority': get_priority(coverage, undocumented),
                    'language': file_data.get('language', 'unknown')
                })

    elif isinstance(analysis, dict) and 'filepath' in analysis:
        # Single file analysis
        elements = analysis.get('elements', [])
        total = len(elements)
        documented = sum(1 for el in elements if el.get('docstring'))
        undocumented = total - documented
        coverage = (documented / total * 100) if total > 0 else 100.0

        if coverage < min_coverage:
            files_to_document.append({
                'filepath': analysis['filepath'],
                'coverage': coverage,
                'undocumented': undocumented,
                'total': total,
                'documented': documented,
                'priority': get_priority(coverage, undocumented),
                'language': analysis.get('language', 'unknown')
            })

    else:
        # Try element_stats format (legacy)
        files = analysis.get('files', []) if isinstance(analysis, dict) else (analysis if isinstance(analysis, list) else [analysis])
        for file_data in files:
            stats = file_data.get('element_stats', {})
            if stats:
                coverage = calculate_coverage(stats)
                if coverage < min_coverage:
                    undocumented = stats.get('undocumented', 0)
                    files_to_document.append({
                        'filepath': file_data['filepath'],
                        'coverage': coverage,
                        'undocumented': undocumented,
                        'total': stats.get('total', 0),
                        'documented': stats.get('documented', 0),
                        'priority': get_priority(coverage, undocumented),
                        'language': file_data.get('language', 'unknown')
                    })

    # Sort by priority, then by undocumented count
    priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    files_to_document.sort(
        key=lambda x: (priority_order[x['priority']], -x['undocumented'])
    )

    # Generate YAML checklist
    yaml_lines = [
        '# Documentation Checklist',
        f'# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        f'# Source: {analysis_file.name}',
        f'# Coverage threshold: {min_coverage}%',
        '',
        'metadata:',
        f'  generated_at: "{datetime.now().isoformat()}"',
        f'  source_file: "{analysis_file.name}"',
        f'  total_files: {len(files_to_document)}',
        f'  coverage_threshold: {min_coverage}',
        '',
        'files:'
    ]

    for file_info in files_to_document:
        yaml_lines.extend([
            f'  - filepath: "{file_info["filepath"]}"',
            f'    status: "pending"',
            f'    priority: "{file_info["priority"]}"',
            f'    language: "{file_info["language"]}"',
            f'    coverage: {file_info["coverage"]:.1f}',
            f'    total_elements: {file_info["total"]}',
            f'    documented_elements: {file_info["documented"]}',
            f'    undocumented_elements: {file_info["undocumented"]}',
            f'    completed_at: null',
            f'    notes: ""',
            ''
        ])

    # Add summary
    critical_count = sum(1 for f in files_to_document if f['priority'] == 'critical')
    high_count = sum(1 for f in files_to_document if f['priority'] == 'high')
    medium_count = sum(1 for f in files_to_document if f['priority'] == 'medium')
    low_count = sum(1 for f in files_to_document if f['priority'] == 'low')

    yaml_lines.extend([
        'summary:',
        f'  total_files: {len(files_to_document)}',
        f'  critical_priority: {critical_count}',
        f'  high_priority: {high_count}',
        f'  medium_priority: {medium_count}',
        f'  low_priority: {low_count}',
        f'  total_undocumented_elements: {sum(f["undocumented"] for f in files_to_document)}',
        ''
    ])

    yaml_content = '\n'.join(yaml_lines)

    # Write to file if specified
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(yaml_content)
        print(f"Checklist generated: {output_file}")
        print(f"  Total files: {len(files_to_document)}")
        print(f"  Critical: {critical_count}, High: {high_count}, Medium: {medium_count}, Low: {low_count}")

    return yaml_content


def main():
    parser = argparse.ArgumentParser(
        description='Generate documentation checklist from analysis JSON'
    )
    parser.add_argument(
        'analysis_file',
        type=Path,
        help='Path to analysis JSON file'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Output checklist file (YAML)'
    )
    parser.add_argument(
        '--min-coverage',
        type=float,
        default=100.0,
        help='Minimum coverage threshold (default: 100.0, include all files with < 100%% coverage)'
    )

    args = parser.parse_args()

    if not args.analysis_file.exists():
        print(f"Error: Analysis file not found: {args.analysis_file}", file=sys.stderr)
        sys.exit(1)

    try:
        checklist = generate_checklist(args.analysis_file, args.min_coverage, args.output)

        if not args.output:
            print(checklist)

    except Exception as e:
        print(f"Error generating checklist: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
