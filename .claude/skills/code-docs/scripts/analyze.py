#!/usr/bin/env python3
"""
Code Documentation Analyzer v2 - Main Entry Point
Dispatches to language-specific analyzers and aggregates results.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List


def analyze_file(filepath: str) -> Dict:
    """Analyze a single file based on its extension."""
    path = Path(filepath)
    suffix = path.suffix.lower()
    
    if suffix == '.py':
        from analyze_python import analyze_file as analyze_python
        return analyze_python(filepath)
    elif suffix in ('.js', '.jsx', '.ts', '.tsx', '.mjs'):
        from analyze_js import analyze_file as analyze_js
        return analyze_js(filepath)
    elif suffix in ('.c', '.h', '.cpp', '.hpp', '.cc', '.cxx'):
        from analyze_c import analyze_file as analyze_c
        return analyze_c(filepath)
    elif suffix == '.cs':
        from analyze_csharp import analyze_file as analyze_csharp
        return analyze_csharp(filepath)
    elif suffix == '.go':
        from analyze_go import analyze_file as analyze_go
        return analyze_go(filepath)
    elif suffix == '.rs':
        from analyze_rust import analyze_file as analyze_rust
        return analyze_rust(filepath)
    else:
        return {'filepath': filepath, 'error': f'Unsupported file type: {suffix}'}


def analyze_directory(dirpath: str, languages: List[str] = None) -> Dict:
    """Analyze all supported files in a directory."""
    root = Path(dirpath).resolve()
    
    # Extension to language mapping
    extensions = {
        '.py': 'python',
        '.js': 'javascript', '.jsx': 'javascript', '.mjs': 'javascript',
        '.ts': 'typescript', '.tsx': 'typescript',
        '.c': 'c', '.h': 'c',
        '.cpp': 'cpp', '.hpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp',
        '.cs': 'csharp',
        '.go': 'go',
        '.rs': 'rust',
    }
    
    # Skip directories
    skip_dirs = {
        'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build',
        '.git', 'vendor', 'target', 'bin', 'obj', '.vs', 'packages',
        'TestResults', 'testdata', '.next', '.nuxt', 'coverage'
    }
    
    results = []
    stats = {
        'total_files': 0,
        'by_language': {},
        'total_elements': 0,
        'documented_elements': 0,
    }
    
    for filepath in root.rglob('*'):
        # Skip directories FIRST (before is_file() which can fail on symlinks)
        if any(skip in filepath.parts for skip in skip_dirs):
            continue

        try:
            if not filepath.is_file():
                continue
        except OSError:
            # Skip files that can't be accessed (symlinks, permission issues, etc.)
            continue
        
        suffix = filepath.suffix.lower()
        
        if suffix not in extensions:
            continue
        
        lang = extensions[suffix]
        
        # Filter by language if specified
        if languages and lang not in languages:
            continue
        
        # Analyze file
        result = analyze_file(str(filepath))
        
        if 'error' not in result:
            results.append(result)
            
            # Update stats
            stats['total_files'] += 1
            stats['by_language'][lang] = stats['by_language'].get(lang, 0) + 1
            
            elements = result.get('elements', [])
            stats['total_elements'] += len(elements)
            
            for elem in elements:
                if elem.get('docstring'):
                    stats['documented_elements'] += 1
                
                # Count methods too
                for method in elem.get('methods', []):
                    stats['total_elements'] += 1
                    if method.get('docstring'):
                        stats['documented_elements'] += 1
    
    # Calculate coverage
    if stats['total_elements'] > 0:
        stats['coverage'] = round(stats['documented_elements'] / stats['total_elements'] * 100, 1)
    else:
        stats['coverage'] = 100.0
    
    return {
        'root': str(root),
        'stats': stats,
        'files': results
    }


def format_summary(analysis: Dict) -> str:
    """Format analysis summary."""
    stats = analysis.get('stats', {})

    lines = [
        f"=== Documentation Analysis ===",
        f"",
        f"Root: {analysis.get('root', 'unknown')}",
        f"Files: {stats.get('total_files', 0)}",
        f"Elements: {stats.get('total_elements', 0)}",
        f"Documented: {stats.get('documented_elements', 0)}",
        f"Coverage: {stats.get('coverage', 0)}%",
        f"",
        f"By Language:"
    ]
    
    for lang, count in sorted(stats.get('by_language', {}).items()):
        lines.append(f"  {lang}: {count} files")
    
    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze.py <file_or_dir> [--output file.json] [--languages py,js,cs] [--summary]", file=sys.stderr)
        sys.exit(1)
    
    target = sys.argv[1]
    output_file = None
    languages = None
    show_summary = '--summary' in sys.argv
    
    if '--output' in sys.argv:
        output_file = sys.argv[sys.argv.index('--output') + 1]
    
    if '--languages' in sys.argv:
        lang_str = sys.argv[sys.argv.index('--languages') + 1]
        # Map short names to full names
        lang_map = {
            'py': 'python', 'python': 'python',
            'js': 'javascript', 'javascript': 'javascript',
            'ts': 'typescript', 'typescript': 'typescript',
            'c': 'c', 'cpp': 'cpp', 'c++': 'cpp',
            'cs': 'csharp', 'csharp': 'csharp',
            'go': 'go', 'golang': 'go',
            'rs': 'rust', 'rust': 'rust',
        }
        languages = [lang_map.get(l.strip(), l.strip()) for l in lang_str.split(',')]
    
    path = Path(target)
    
    if path.is_file():
        result = analyze_file(str(path))
    elif path.is_dir():
        result = analyze_directory(str(path), languages)
    else:
        print(f"Error: {target} not found", file=sys.stderr)
        sys.exit(1)
    
    if show_summary and 'stats' in result:
        print(format_summary(result))
    elif output_file:
        Path(output_file).write_text(json.dumps(result, indent=2))
        print(f"Analysis written to {output_file}")
        if 'stats' in result:
            print(f"Coverage: {result['stats']['coverage']}%")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
