#!/usr/bin/env python3
"""
Structure Analyzer v2
Extracts directory structure with confidence-tagged purpose detection.
Includes README content and flags uncertain areas.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# Confidence levels
DETECTED = "detected"      # High confidence from explicit signals
INFERRED = "inferred"      # Heuristic guess from patterns
UNKNOWN = "unknown"        # Needs Claude verification

# Directory purposes with detection confidence
# Format: {name: (purpose, confidence)}
DIRECTORY_PURPOSES = {
    # High confidence - explicit names
    'src': ('source', DETECTED),
    'source': ('source', DETECTED),
    'lib': ('library', DETECTED),
    'test': ('tests', DETECTED),
    'tests': ('tests', DETECTED),
    '__tests__': ('tests', DETECTED),
    'spec': ('tests', DETECTED),
    'specs': ('tests', DETECTED),
    'docs': ('documentation', DETECTED),
    'doc': ('documentation', DETECTED),
    'documentation': ('documentation', DETECTED),
    
    # Medium confidence - common conventions
    'api': ('api', INFERRED),
    'routes': ('api', INFERRED),
    'endpoints': ('api', INFERRED),
    'handlers': ('api', INFERRED),
    'controllers': ('controllers', INFERRED),
    'views': ('views', INFERRED),
    'pages': ('pages', INFERRED),
    'components': ('components', INFERRED),
    'widgets': ('components', INFERRED),
    'models': ('models', INFERRED),
    'entities': ('models', INFERRED),
    'schemas': ('schemas', INFERRED),
    'services': ('services', INFERRED),
    'repositories': ('repositories', INFERRED),
    'utils': ('utilities', INFERRED),
    'utilities': ('utilities', INFERRED),
    'helpers': ('utilities', INFERRED),
    'common': ('utilities', INFERRED),
    'shared': ('shared', INFERRED),
    'config': ('configuration', INFERRED),
    'configs': ('configuration', INFERRED),
    'configuration': ('configuration', INFERRED),
    'settings': ('configuration', INFERRED),
    'scripts': ('scripts', INFERRED),
    'bin': ('scripts', INFERRED),
    'tools': ('tools', INFERRED),
    'assets': ('assets', INFERRED),
    'static': ('assets', INFERRED),
    'public': ('assets', INFERRED),
    'resources': ('resources', INFERRED),
    'res': ('resources', INFERRED),
    'styles': ('styles', INFERRED),
    'css': ('styles', INFERRED),
    'scss': ('styles', INFERRED),
    'migrations': ('migrations', INFERRED),
    'db': ('database', INFERRED),
    'database': ('database', INFERRED),
    'middleware': ('middleware', INFERRED),
    'hooks': ('hooks', INFERRED),
    'types': ('types', INFERRED),
    'interfaces': ('types', INFERRED),
    'store': ('state', INFERRED),
    'stores': ('state', INFERRED),
    'redux': ('state', INFERRED),
    'state': ('state', INFERRED),
    
    # Language-specific
    'cmd': ('entrypoints', INFERRED),  # Go
    'pkg': ('packages', INFERRED),      # Go
    'internal': ('internal', INFERRED), # Go
    'crates': ('packages', INFERRED),   # Rust
    'packages': ('packages', INFERRED), # Monorepo
    'apps': ('applications', INFERRED), # Monorepo
    'modules': ('modules', INFERRED),
    'plugins': ('plugins', INFERRED),
    'extensions': ('extensions', INFERRED),
    'vendor': ('vendor', DETECTED),
    'third_party': ('vendor', DETECTED),
    'examples': ('examples', DETECTED),
    'example': ('examples', DETECTED),
    'samples': ('examples', DETECTED),
    'benchmarks': ('benchmarks', DETECTED),
    'bench': ('benchmarks', DETECTED),
}

# Skip these directories
SKIP_DIRS = {
    'node_modules', '.git', '.svn', '.hg', '__pycache__', '.pytest_cache',
    '.mypy_cache', '.tox', '.nox', 'venv', '.venv', 'env', '.env',
    'dist', 'build', '.build', 'target', 'out', '.next', '.nuxt',
    'coverage', '.coverage', '.nyc_output', 'htmlcov',
    '.idea', '.vscode', '.vs', '.eggs', '.cache',
}

# File extension to language mapping
EXTENSION_MAP = {
    '.py': 'python', '.pyx': 'python', '.pyi': 'python',
    '.js': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript',
    '.jsx': 'react',
    '.ts': 'typescript', '.tsx': 'typescript-react',
    '.go': 'go',
    '.rs': 'rust',
    '.java': 'java', '.kt': 'kotlin', '.scala': 'scala',
    '.c': 'c', '.h': 'c-header',
    '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.hpp': 'cpp-header',
    '.cs': 'csharp',
    '.rb': 'ruby',
    '.php': 'php',
    '.swift': 'swift',
    '.m': 'objective-c', '.mm': 'objective-cpp',
    '.vue': 'vue', '.svelte': 'svelte',
    '.sql': 'sql',
    '.sh': 'shell', '.bash': 'shell', '.zsh': 'shell',
    '.yaml': 'yaml', '.yml': 'yaml',
    '.json': 'json',
    '.xml': 'xml',
    '.md': 'markdown', '.rst': 'rst',
    '.proto': 'protobuf',
    '.graphql': 'graphql', '.gql': 'graphql',
}


def should_skip(name: str) -> bool:
    """Check if directory should be skipped."""
    if name in SKIP_DIRS:
        return True
    if name.startswith('.') and name not in {'.github', '.circleci', '.gitlab'}:
        return True
    if name.endswith('.egg-info'):
        return True
    return False


def detect_purpose(dir_info: Dict, files: List[Dict]) -> Tuple[str, str]:
    """Detect directory purpose with confidence level."""
    name = dir_info['name'].lower()
    
    # Check explicit mapping
    if name in DIRECTORY_PURPOSES:
        return DIRECTORY_PURPOSES[name]
    
    # Infer from file contents
    file_categories = [f.get('language', '') for f in files]
    
    # All test files
    if all('test' in f.get('name', '').lower() for f in files if f.get('language')):
        return ('tests', INFERRED)
    
    # All documentation
    if all(f.get('language') in ('markdown', 'rst') for f in files if f.get('language')):
        return ('documentation', INFERRED)
    
    # All assets
    asset_langs = {'css', 'scss', 'image', 'font'}
    if all(f.get('language') in asset_langs for f in files if f.get('language')):
        return ('assets', INFERRED)
    
    return ('unknown', UNKNOWN)


def extract_readme(project_path: Path) -> Optional[Dict]:
    """Extract README content."""
    readme_names = ['README.md', 'README.rst', 'README.txt', 'README', 'readme.md']
    
    for name in readme_names:
        readme_path = project_path / name
        if readme_path.exists():
            try:
                content = readme_path.read_text(encoding='utf-8', errors='replace')
                
                # Extract sections
                sections = {}
                current_section = 'overview'
                current_content = []
                
                for line in content.split('\n'):
                    # Detect headers
                    if line.startswith('#'):
                        if current_content:
                            sections[current_section] = '\n'.join(current_content).strip()
                        current_section = line.lstrip('#').strip().lower()
                        current_content = []
                    else:
                        current_content.append(line)
                
                if current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                return {
                    'file': name,
                    'content': content[:5000],  # Limit size
                    'sections': {k: v[:1000] for k, v in sections.items()},  # Limit sections
                }
            except:
                pass
    
    return None


def analyze_structure(project_path: str, max_depth: int = 8) -> Dict:
    """Analyze project structure with confidence tagging."""
    root = Path(project_path).resolve()
    
    result = {
        'root': str(root),
        'name': root.name,
        'readme': extract_readme(root),
        'tree': None,
        'statistics': {
            'total_files': 0,
            'total_dirs': 0,
            'languages': defaultdict(int),
            'by_category': defaultdict(int),
        },
        'confidence_summary': {
            DETECTED: 0,
            INFERRED: 0,
            UNKNOWN: 0,
        },
        'uncertain_areas': [],  # For Claude to verify
    }
    
    def scan_dir(path: Path, depth: int = 0) -> Optional[Dict]:
        if depth > max_depth:
            return None
        
        dir_info = {
            'name': path.name,
            'path': str(path.relative_to(root)) if path != root else '.',
            'depth': depth,
            'purpose': None,
            'confidence': None,
            'children': [],
            'files': [],
            'file_count': 0,
        }
        
        try:
            entries = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        except PermissionError:
            return dir_info
        
        for entry in entries:
            if entry.is_dir():
                if should_skip(entry.name):
                    continue
                result['statistics']['total_dirs'] += 1
                child = scan_dir(entry, depth + 1)
                if child:
                    dir_info['children'].append(child)
            else:
                result['statistics']['total_files'] += 1
                
                suffix = entry.suffix.lower()
                language = EXTENSION_MAP.get(suffix, 'other')
                result['statistics']['languages'][language] += 1
                
                file_info = {
                    'name': entry.name,
                    'language': language,
                    'size': entry.stat().st_size if entry.exists() else 0,
                }
                
                dir_info['files'].append(file_info)
                dir_info['file_count'] += 1
        
        # Detect purpose
        purpose, confidence = detect_purpose(dir_info, dir_info['files'])
        dir_info['purpose'] = purpose
        dir_info['confidence'] = confidence
        
        result['confidence_summary'][confidence] += 1
        
        # Track uncertain areas
        if confidence == UNKNOWN and dir_info['file_count'] > 0:
            result['uncertain_areas'].append({
                'path': dir_info['path'],
                'file_count': dir_info['file_count'],
                'sample_files': [f['name'] for f in dir_info['files'][:5]],
                'question': f"What is the purpose of '{dir_info['path']}'? Contains {dir_info['file_count']} files.",
            })
        
        # Limit files stored (keep structure manageable)
        if len(dir_info['files']) > 20:
            dir_info['files'] = dir_info['files'][:20]
            dir_info['files_truncated'] = True
        
        return dir_info
    
    result['tree'] = scan_dir(root)
    result['statistics']['languages'] = dict(result['statistics']['languages'])
    result['statistics']['by_category'] = dict(result['statistics']['by_category'])
    
    return result


def format_tree(node: Dict, prefix: str = '', is_last: bool = True) -> str:
    """Format directory tree as text."""
    lines = []
    
    connector = '└── ' if is_last else '├── '
    conf_icon = {'detected': '✓', 'inferred': '?', 'unknown': '⚠'}
    
    purpose = node.get('purpose', '')
    confidence = node.get('confidence', '')
    icon = conf_icon.get(confidence, '')
    
    purpose_str = f" [{purpose}]{icon}" if purpose and purpose != 'unknown' else f" [?]{icon}" if confidence == 'unknown' else ""
    file_count = f" ({node.get('file_count', 0)} files)" if node.get('file_count', 0) > 0 else ""
    
    lines.append(f"{prefix}{connector}{node['name']}/{purpose_str}{file_count}")
    
    prefix += '    ' if is_last else '│   '
    
    children = node.get('children', [])
    for i, child in enumerate(children):
        lines.append(format_tree(child, prefix, i == len(children) - 1))
    
    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_structure.py <project_path> [--output file.json] [--tree]", file=sys.stderr)
        sys.exit(1)
    
    project_path = sys.argv[1]
    output_file = None
    show_tree = '--tree' in sys.argv
    
    if '--output' in sys.argv:
        output_file = sys.argv[sys.argv.index('--output') + 1]
    
    result = analyze_structure(project_path)
    
    if show_tree:
        print(f"\n📁 {result['name']}")
        print(f"   {result['statistics']['total_files']} files, {result['statistics']['total_dirs']} directories\n")
        
        # Confidence summary
        cs = result['confidence_summary']
        print(f"Confidence: {cs[DETECTED]} detected, {cs[INFERRED]} inferred, {cs[UNKNOWN]} unknown\n")
        
        if result.get('readme'):
            print(f"📄 README found: {result['readme']['file']}\n")
        
        if result.get('tree'):
            print(format_tree(result['tree']))
        
        if result.get('uncertain_areas'):
            print(f"\n⚠️  Uncertain Areas ({len(result['uncertain_areas'])}):")
            for area in result['uncertain_areas'][:5]:
                print(f"   • {area['path']}: {area['question']}")
    
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\nStructure written to {output_file}")
    elif not show_tree:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
