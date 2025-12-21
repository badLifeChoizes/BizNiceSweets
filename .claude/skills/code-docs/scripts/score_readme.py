#!/usr/bin/env python3
"""
README Quality Scorer
Assesses project documentation completeness and quality.
Checks for essential sections, examples, badges, and more.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict


@dataclass
class SectionScore:
    name: str
    present: bool
    quality: str  # good, fair, poor, missing
    score: int  # 0-10
    suggestions: List[str] = field(default_factory=list)


@dataclass
class ReadmeScore:
    filepath: str
    total_score: int  # 0-100
    grade: str  # A, B, C, D, F
    sections: List[SectionScore] = field(default_factory=list)
    has_badges: bool = False
    has_images: bool = False
    has_code_examples: bool = False
    has_table_of_contents: bool = False
    word_count: int = 0
    suggestions: List[str] = field(default_factory=list)


# Essential sections and their weights
SECTIONS = {
    'title': {'weight': 5, 'patterns': [r'^#\s+\w+']},
    'description': {'weight': 10, 'patterns': [r'(?:^|\n)(?:##?\s*)?(?:description|about|overview|what is)', r'^[A-Z][^#\n]{50,}']},
    'installation': {'weight': 15, 'patterns': [r'(?:^|\n)##?\s*(?:install|setup|getting started|quick start)', r'(?:npm install|pip install|cargo add|go get|dotnet add)']},
    'usage': {'weight': 15, 'patterns': [r'(?:^|\n)##?\s*(?:usage|how to use|examples?|basic usage)']},
    'api': {'weight': 10, 'patterns': [r'(?:^|\n)##?\s*(?:api|reference|methods|functions|endpoints)']},
    'configuration': {'weight': 5, 'patterns': [r'(?:^|\n)##?\s*(?:config|configuration|options|settings|environment)']},
    'contributing': {'weight': 5, 'patterns': [r'(?:^|\n)##?\s*(?:contributing|development|how to contribute)']},
    'license': {'weight': 5, 'patterns': [r'(?:^|\n)##?\s*license', r'MIT|Apache|GPL|BSD|ISC']},
    'requirements': {'weight': 5, 'patterns': [r'(?:^|\n)##?\s*(?:requirements|prerequisites|dependencies)', r'requires\s+(?:python|node|go|rust)']},
}


def find_section(content: str, patterns: List[str]) -> Tuple[bool, int, int]:
    """Find section in content, return (found, start_pos, length)."""
    content_lower = content.lower()
    
    for pattern in patterns:
        match = re.search(pattern, content_lower, re.MULTILINE | re.IGNORECASE)
        if match:
            # Find section length (until next ## header or end)
            start = match.start()
            next_header = re.search(r'\n##?\s+\w+', content[start + 1:])
            if next_header:
                length = next_header.start()
            else:
                length = len(content) - start
            return True, start, length
    
    return False, 0, 0


def assess_section_quality(content: str, section_name: str, start: int, length: int) -> str:
    """Assess quality of a section."""
    section_content = content[start:start + length]
    
    # Check length
    word_count = len(section_content.split())
    
    if section_name == 'installation':
        has_code = '```' in section_content or '    ' in section_content
        if has_code and word_count > 20:
            return 'good'
        elif has_code or word_count > 10:
            return 'fair'
        return 'poor'
    
    elif section_name == 'usage':
        has_code = '```' in section_content
        has_example = 'example' in section_content.lower()
        if has_code and word_count > 30:
            return 'good'
        elif has_code or has_example:
            return 'fair'
        return 'poor'
    
    elif section_name == 'api':
        # API docs should be substantial
        if word_count > 100:
            return 'good'
        elif word_count > 30:
            return 'fair'
        return 'poor'
    
    else:
        if word_count > 30:
            return 'good'
        elif word_count > 10:
            return 'fair'
        return 'poor'


def get_suggestions(section_name: str, quality: str) -> List[str]:
    """Get improvement suggestions for a section."""
    suggestions = []
    
    if quality == 'missing':
        suggestions.append(f"Add a {section_name} section")
    elif quality == 'poor':
        if section_name == 'installation':
            suggestions.append("Add step-by-step installation commands")
            suggestions.append("Include code blocks with install commands")
        elif section_name == 'usage':
            suggestions.append("Add code examples showing basic usage")
            suggestions.append("Include expected output or screenshots")
        elif section_name == 'api':
            suggestions.append("Document public functions/methods")
            suggestions.append("Add parameter descriptions and return types")
        elif section_name == 'description':
            suggestions.append("Expand the project description")
            suggestions.append("Explain what problem this solves")
    elif quality == 'fair':
        if section_name == 'installation':
            suggestions.append("Consider adding troubleshooting tips")
        elif section_name == 'usage':
            suggestions.append("Add more diverse examples")
        elif section_name == 'api':
            suggestions.append("Add more detailed parameter documentation")
    
    return suggestions


def score_readme(filepath: str) -> ReadmeScore:
    """Score a README file."""
    path = Path(filepath)
    
    try:
        content = path.read_text(encoding='utf-8')
    except:
        return ReadmeScore(
            filepath=filepath,
            total_score=0,
            grade='F',
            suggestions=['Could not read README file']
        )
    
    sections = []
    total_points = 0
    max_points = sum(s['weight'] for s in SECTIONS.values())
    
    # Score each section
    for section_name, config in SECTIONS.items():
        found, start, length = find_section(content, config['patterns'])
        
        if found:
            quality = assess_section_quality(content, section_name, start, length)
            quality_multiplier = {'good': 1.0, 'fair': 0.6, 'poor': 0.3}[quality]
            score = int(config['weight'] * quality_multiplier)
        else:
            quality = 'missing'
            score = 0
        
        total_points += score
        
        section_score = SectionScore(
            name=section_name,
            present=found,
            quality=quality,
            score=score,
            suggestions=get_suggestions(section_name, quality)
        )
        sections.append(section_score)
    
    # Bonus points
    bonus = 0
    
    # Badges
    has_badges = bool(re.search(r'!\[.*?\]\(.*?(?:badge|shield|img\.shields)', content))
    if has_badges:
        bonus += 5
    
    # Images/diagrams
    has_images = bool(re.search(r'!\[.*?\]\(.*?\.(png|jpg|gif|svg)', content))
    if has_images:
        bonus += 5
    
    # Code examples
    has_code = '```' in content
    code_blocks = content.count('```') // 2
    if code_blocks >= 3:
        bonus += 10
    elif code_blocks >= 1:
        bonus += 5
    
    # Table of contents
    has_toc = bool(re.search(r'##?\s*(?:table of contents|contents|toc)', content, re.IGNORECASE))
    has_toc = has_toc or content.count('](#') > 3  # Links to headers
    if has_toc:
        bonus += 5
    
    # Calculate final score
    base_score = int((total_points / max_points) * 75)  # Sections worth 75%
    final_score = min(100, base_score + bonus)
    
    # Assign grade
    if final_score >= 90:
        grade = 'A'
    elif final_score >= 80:
        grade = 'B'
    elif final_score >= 70:
        grade = 'C'
    elif final_score >= 60:
        grade = 'D'
    else:
        grade = 'F'
    
    # Overall suggestions
    overall_suggestions = []
    
    if not has_badges:
        overall_suggestions.append("Add badges (build status, version, license)")
    if not has_images and final_score < 80:
        overall_suggestions.append("Consider adding screenshots or diagrams")
    if not has_toc and len(content) > 3000:
        overall_suggestions.append("Add a table of contents for navigation")
    if code_blocks < 2:
        overall_suggestions.append("Add more code examples")
    
    # Collect section suggestions
    for section in sections:
        overall_suggestions.extend(section.suggestions)
    
    return ReadmeScore(
        filepath=filepath,
        total_score=final_score,
        grade=grade,
        sections=sections,
        has_badges=has_badges,
        has_images=has_images,
        has_code_examples=has_code,
        has_table_of_contents=has_toc,
        word_count=len(content.split()),
        suggestions=overall_suggestions[:10]  # Top 10
    )


def find_readme(dirpath: str) -> Optional[str]:
    """Find README file in directory."""
    readme_names = ['README.md', 'README.rst', 'README.txt', 'README', 
                    'readme.md', 'Readme.md']
    
    for name in readme_names:
        path = Path(dirpath) / name
        if path.exists():
            return str(path)
    
    return None


def format_report(score: ReadmeScore) -> str:
    """Format score as readable report."""
    grade_icons = {'A': '🏆', 'B': '✅', 'C': '⚠️', 'D': '🔶', 'F': '❌'}
    icon = grade_icons.get(score.grade, '?')
    
    lines = [
        f"═══ README Quality Report ═══",
        "",
        f"File: {score.filepath}",
        f"Score: {score.total_score}/100 {icon} Grade: {score.grade}",
        f"Words: {score.word_count}",
        "",
        "Features:",
        f"  {'✓' if score.has_badges else '✗'} Badges",
        f"  {'✓' if score.has_images else '✗'} Images/Diagrams",
        f"  {'✓' if score.has_code_examples else '✗'} Code Examples",
        f"  {'✓' if score.has_table_of_contents else '✗'} Table of Contents",
        "",
        "Sections:",
    ]
    
    for section in score.sections:
        quality_icon = {'good': '✓', 'fair': '○', 'poor': '✗', 'missing': '✗'}[section.quality]
        lines.append(f"  {quality_icon} {section.name}: {section.quality} ({section.score} pts)")
    
    if score.suggestions:
        lines.append("")
        lines.append("Suggestions:")
        for i, suggestion in enumerate(score.suggestions[:5], 1):
            lines.append(f"  {i}. {suggestion}")
    
    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: score_readme.py <readme_file_or_dir> [--format json|text]", file=sys.stderr)
        sys.exit(1)
    
    target = sys.argv[1]
    output_format = 'text'
    
    if '--format' in sys.argv:
        output_format = sys.argv[sys.argv.index('--format') + 1]
    
    path = Path(target)
    
    if path.is_file():
        filepath = str(path)
    elif path.is_dir():
        filepath = find_readme(str(path))
        if not filepath:
            print(f"No README found in {target}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"Error: {target} not found", file=sys.stderr)
        sys.exit(1)
    
    score = score_readme(filepath)
    
    if output_format == 'json':
        output = asdict(score)
        output['sections'] = [asdict(s) for s in score.sections]
        print(json.dumps(output, indent=2))
    else:
        print(format_report(score))


if __name__ == "__main__":
    main()
