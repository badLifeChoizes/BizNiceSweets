#!/usr/bin/env python3
"""
Generate a Markdown documentation checklist from analysis JSON files.

Creates a markdown checklist with checkboxes for tracking documentation progress.

Usage:
    python generate_markdown_checklist.py analysis.json --output CHECKLIST.md
    python generate_markdown_checklist.py analysis.json --min-coverage 80 --output CHECKLIST.md
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any


def calculate_coverage(elements: List[Dict]) -> tuple:
    """Calculate documentation coverage from elements."""
    if not elements:
        return 100.0, 0, 0, 0

    total = len(elements)
    documented = sum(1 for el in elements if el.get('docstring'))
    undocumented = total - documented
    coverage = (documented / total * 100) if total > 0 else 100.0

    return coverage, total, documented, undocumented


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


def get_priority_emoji(priority: str) -> str:
    """Get emoji for priority level."""
    return {
        'critical': '🔴',
        'high': '🟠',
        'medium': '🟡',
        'low': '🟢'
    }.get(priority, '⚪')


def generate_markdown_checklist(
    analysis_file: Path,
    min_coverage: float = 100.0,
    output_file: Path = None
) -> str:
    """
    Generate a Markdown checklist from analysis JSON.

    Args:
        analysis_file: Path to analysis JSON file
        min_coverage: Minimum coverage threshold (files below this are included)
        output_file: Optional output file path

    Returns:
        Markdown checklist content as string
    """

    with open(analysis_file, 'r', encoding='utf-8') as f:
        analysis = json.load(f)

    # Collect files that need documentation
    files_to_document = []

    # Handle directory analysis
    if isinstance(analysis, dict) and 'files' in analysis:
        for file_data in analysis.get('files', []):
            elements = file_data.get('elements', [])
            if not elements:
                continue

            coverage, total, documented, undocumented = calculate_coverage(elements)

            if coverage < min_coverage:
                # Get relative path for display
                filepath = file_data['filepath']
                if 'root' in analysis:
                    root = analysis['root']
                    if filepath.startswith(root):
                        filepath = filepath[len(root):].lstrip('\\/')

                files_to_document.append({
                    'filepath': filepath,
                    'full_path': file_data['filepath'],
                    'coverage': coverage,
                    'undocumented': undocumented,
                    'total': total,
                    'documented': documented,
                    'priority': get_priority(coverage, undocumented),
                    'language': file_data.get('language', 'unknown')
                })

    # Sort by priority, then by undocumented count
    priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    files_to_document.sort(
        key=lambda x: (priority_order[x['priority']], -x['undocumented'])
    )

    # Generate Markdown checklist
    md_lines = [
        '# 📝 Documentation Checklist',
        '',
        f'**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}  ',
        f'**Source:** `{analysis_file.name}`  ',
        f'**Coverage Threshold:** {min_coverage}%  ',
        '',
        '## 📊 Summary',
        '',
        f'- **Total Files:** {len(files_to_document)}',
        f'- 🔴 **Critical:** {sum(1 for f in files_to_document if f["priority"] == "critical")}',
        f'- 🟠 **High:** {sum(1 for f in files_to_document if f["priority"] == "high")}',
        f'- 🟡 **Medium:** {sum(1 for f in files_to_document if f["priority"] == "medium")}',
        f'- 🟢 **Low:** {sum(1 for f in files_to_document if f["priority"] == "low")}',
        f'- **Total Undocumented Elements:** {sum(f["undocumented"] for f in files_to_document):,}',
        '',
        '## 🎯 Priority Legend',
        '',
        '- 🔴 **Critical**: 0% coverage or 30+ undocumented elements',
        '- 🟠 **High**: <40% coverage or 15+ undocumented elements',
        '- 🟡 **Medium**: <70% coverage or 5+ undocumented elements',
        '- 🟢 **Low**: 70%+ coverage',
        '',
        '---',
        ''
    ]

    # Group by priority
    for priority_name, priority_emoji in [
        ('critical', '🔴'),
        ('high', '🟠'),
        ('medium', '🟡'),
        ('low', '🟢')
    ]:
        priority_files = [f for f in files_to_document if f['priority'] == priority_name]

        if not priority_files:
            continue

        md_lines.extend([
            f'## {priority_emoji} {priority_name.upper()} Priority ({len(priority_files)} files)',
            ''
        ])

        for file_info in priority_files:
            # Create checkbox line
            coverage_bar = '█' * int(file_info['coverage'] / 10) + '░' * (10 - int(file_info['coverage'] / 10))

            md_lines.append(
                f'- [ ] **`{file_info["filepath"]}`**  '
            )
            md_lines.append(
                f'  Coverage: {file_info["coverage"]:.1f}% {coverage_bar} | '
                f'Elements: {file_info["documented"]}/{file_info["total"]} | '
                f'Undocumented: {file_info["undocumented"]} | '
                f'Lang: {file_info["language"]}'
            )
            md_lines.append('')

    # Add instructions
    md_lines.extend([
        '---',
        '',
        '## ✅ How to Use This Checklist',
        '',
        '1. **Choose a file** from the list above',
        '2. **Read the implementation** to understand what it does',
        '3. **Add JSDoc/TSDoc comments** to all public functions, classes, and interfaces',
        '4. **Mark complete** by changing `[ ]` to `[x]` when done',
        '5. **Commit your changes** with a descriptive message',
        '',
        '### Example Documentation',
        '',
        '```typescript',
        '/**',
        ' * Brief description of what the function does.',
        ' *',
        ' * More detailed explanation if needed. Describe behavior,',
        ' * side effects, and any important considerations.',
        ' *',
        ' * @param paramName - Description of the parameter',
        ' * @param anotherParam - Another parameter description',
        ' * @returns Description of return value',
        ' * @throws {ErrorType} When and why this error occurs',
        ' *',
        ' * @example',
        ' * ```typescript',
        ' * const result = myFunction("example", 42);',
        ' * console.log(result); // "Expected output"',
        ' * ```',
        ' */',
        'export function myFunction(paramName: string, anotherParam: number): string {',
        '  // implementation',
        '}',
        '```',
        '',
        '### Tips',
        '',
        '- Focus on **what** and **why**, not just **how**',
        '- Document all **parameters** with their types and valid values',
        '- Explain **return values** and when they vary',
        '- Note **side effects** (file writes, API calls, state changes)',
        '- Include **examples** for complex functions',
        '- Use **@throws** to document error conditions',
        '',
        f'**Last Updated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}',
        ''
    ])

    markdown_content = '\n'.join(md_lines)

    # Write to file if specified
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        print(f"✅ Markdown checklist generated: {output_file}")
        print(f"   Total files: {len(files_to_document)}")
        print(f"   🔴 Critical: {sum(1 for f in files_to_document if f['priority'] == 'critical')}")
        print(f"   🟠 High: {sum(1 for f in files_to_document if f['priority'] == 'high')}")
        print(f"   🟡 Medium: {sum(1 for f in files_to_document if f['priority'] == 'medium')}")
        print(f"   🟢 Low: {sum(1 for f in files_to_document if f['priority'] == 'low')}")

    return markdown_content


def main():
    parser = argparse.ArgumentParser(
        description='Generate Markdown documentation checklist from analysis JSON'
    )
    parser.add_argument(
        'analysis_file',
        type=Path,
        help='Path to analysis JSON file'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Output checklist file (Markdown)'
    )
    parser.add_argument(
        '--min-coverage',
        type=float,
        default=100.0,
        help='Minimum coverage threshold (default: 100.0)'
    )

    args = parser.parse_args()

    if not args.analysis_file.exists():
        print(f"❌ Error: Analysis file not found: {args.analysis_file}", file=sys.stderr)
        sys.exit(1)

    try:
        checklist = generate_markdown_checklist(
            args.analysis_file,
            args.min_coverage,
            args.output
        )

        if not args.output:
            print(checklist)

    except Exception as e:
        print(f"❌ Error generating checklist: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
