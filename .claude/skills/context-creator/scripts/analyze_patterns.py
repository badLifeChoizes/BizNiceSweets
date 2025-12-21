#!/usr/bin/env python3
"""
Patterns Analyzer v2
Detects coding patterns across multiple languages: Python, JavaScript/TypeScript,
Go, Rust, Java, C/C++, and C#.
"""

import ast
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional


DETECTED = "detected"
INFERRED = "inferred"


def detect_naming_convention(names: List[str]) -> Dict[str, int]:
    """Detect naming conventions from a list of names."""
    conventions = Counter()
    
    for name in names:
        if not name or name.startswith('_'):
            continue
        
        if name.isupper() or (name.upper() == name and '_' in name):
            conventions['SCREAMING_SNAKE_CASE'] += 1
        elif '_' in name and name.islower():
            conventions['snake_case'] += 1
        elif '_' in name:
            conventions['mixed_snake'] += 1
        elif name[0].isupper() and any(c.isupper() for c in name[1:]):
            conventions['PascalCase'] += 1
        elif name[0].islower() and any(c.isupper() for c in name):
            conventions['camelCase'] += 1
        elif name.islower():
            conventions['lowercase'] += 1
    
    return dict(conventions)


# ========== Python Analysis ==========

def analyze_python_file(filepath: Path) -> Dict:
    """Analyze a Python file for patterns."""
    try:
        source = filepath.read_text(encoding='utf-8')
        tree = ast.parse(source)
    except:
        return {}
    
    patterns = {
        'classes': [],
        'functions': [],
        'decorators': Counter(),
        'type_hints': 0,
        'no_type_hints': 0,
        'docstrings': 0,
        'no_docstrings': 0,
        'async_functions': 0,
        'dataclasses': 0,
        'imports': {'stdlib': [], 'third_party': [], 'local': []},
    }
    
    stdlib_modules = {
        'os', 'sys', 'json', 're', 'typing', 'collections', 'functools',
        'itertools', 'pathlib', 'datetime', 'time', 'logging', 'unittest',
        'dataclasses', 'enum', 'abc', 'io', 'copy', 'math', 'random',
        'subprocess', 'threading', 'multiprocessing', 'asyncio', 'socket',
        'http', 'urllib', 'argparse', 'configparser', 'hashlib', 'pickle'
    }
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            patterns['classes'].append(node.name)
            for dec in node.decorator_list:
                dec_name = ast.unparse(dec) if hasattr(ast, 'unparse') else ''
                if dec_name:
                    patterns['decorators'][dec_name] += 1
                    if 'dataclass' in dec_name:
                        patterns['dataclasses'] += 1
        
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            patterns['functions'].append(node.name)
            
            if isinstance(node, ast.AsyncFunctionDef):
                patterns['async_functions'] += 1
            
            # Type hints
            has_hints = node.returns or any(arg.annotation for arg in node.args.args)
            if has_hints:
                patterns['type_hints'] += 1
            else:
                patterns['no_type_hints'] += 1
            
            # Docstrings
            has_doc = (node.body and isinstance(node.body[0], ast.Expr) and
                      isinstance(node.body[0].value, ast.Constant) and
                      isinstance(node.body[0].value.value, str))
            if has_doc:
                patterns['docstrings'] += 1
            else:
                patterns['no_docstrings'] += 1
            
            for dec in node.decorator_list:
                dec_name = ast.unparse(dec) if hasattr(ast, 'unparse') else ''
                if dec_name:
                    patterns['decorators'][dec_name] += 1
        
        elif isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split('.')[0]
                if module in stdlib_modules:
                    patterns['imports']['stdlib'].append(module)
                else:
                    patterns['imports']['third_party'].append(module)
        
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module.split('.')[0]
                if module in stdlib_modules:
                    patterns['imports']['stdlib'].append(module)
                elif node.level > 0:
                    patterns['imports']['local'].append(node.module or '')
                else:
                    patterns['imports']['third_party'].append(module)
    
    patterns['decorators'] = dict(patterns['decorators'])
    for key in patterns['imports']:
        patterns['imports'][key] = list(set(patterns['imports'][key]))
    
    return patterns


# ========== JavaScript/TypeScript Analysis ==========

def analyze_js_file(filepath: Path) -> Dict:
    """Analyze JavaScript/TypeScript file for patterns."""
    try:
        source = filepath.read_text(encoding='utf-8')
    except:
        return {}
    
    patterns = {
        'functions': [],
        'classes': [],
        'exports': [],
        'imports': [],
        'arrow_functions': 0,
        'regular_functions': 0,
        'async_functions': 0,
        'react_components': [],
        'hooks': [],
        'typescript_types': [],
        'interfaces': [],
    }
    
    # Functions
    for match in re.finditer(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)', source):
        patterns['functions'].append(match.group(1))
        patterns['regular_functions'] += 1
    
    # Arrow functions
    for match in re.finditer(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>', source):
        patterns['functions'].append(match.group(1))
        patterns['arrow_functions'] += 1
    
    # Async count
    patterns['async_functions'] = len(re.findall(r'\basync\s+(?:function|\([^)]*\)\s*=>)', source))
    
    # Classes
    for match in re.finditer(r'class\s+(\w+)', source):
        patterns['classes'].append(match.group(1))
    
    # Exports
    for match in re.finditer(r'export\s+(?:default\s+)?(?:const|let|var|function|class)\s+(\w+)', source):
        patterns['exports'].append(match.group(1))
    
    # Imports
    for match in re.finditer(r"import\s+.*?from\s+['\"]([^'\"]+)['\"]", source):
        patterns['imports'].append(match.group(1))
    
    # React components (PascalCase functions returning JSX)
    for match in re.finditer(r'(?:function|const)\s+([A-Z]\w+)', source):
        if '<' in source[match.end():match.end()+500]:  # Rough JSX check
            patterns['react_components'].append(match.group(1))
    
    # Hooks
    patterns['hooks'] = list(set(re.findall(r'\buse[A-Z]\w+', source)))
    
    # TypeScript types/interfaces
    for match in re.finditer(r'(?:type|interface)\s+(\w+)', source):
        if 'interface' in match.group(0):
            patterns['interfaces'].append(match.group(1))
        else:
            patterns['typescript_types'].append(match.group(1))
    
    patterns['imports'] = list(set(patterns['imports']))
    
    return patterns


# ========== Go Analysis ==========

def analyze_go_file(filepath: Path) -> Dict:
    """Analyze Go file for patterns."""
    try:
        source = filepath.read_text(encoding='utf-8')
    except:
        return {}
    
    patterns = {
        'package': '',
        'functions': [],
        'methods': [],
        'structs': [],
        'interfaces': [],
        'imports': [],
        'goroutines': 0,
        'channels': 0,
        'exported': [],  # Public (capitalized)
        'unexported': [],  # Private (lowercase)
    }
    
    # Package
    match = re.search(r'^package\s+(\w+)', source, re.MULTILINE)
    if match:
        patterns['package'] = match.group(1)
    
    # Imports
    import_block = re.search(r'import\s*\((.*?)\)', source, re.DOTALL)
    if import_block:
        for match in re.finditer(r'["\']([^"\']+)["\']', import_block.group(1)):
            patterns['imports'].append(match.group(1))
    for match in re.finditer(r'import\s+["\']([^"\']+)["\']', source):
        patterns['imports'].append(match.group(1))
    
    # Functions
    for match in re.finditer(r'func\s+(\w+)\s*\(', source):
        name = match.group(1)
        patterns['functions'].append(name)
        if name[0].isupper():
            patterns['exported'].append(name)
        else:
            patterns['unexported'].append(name)
    
    # Methods (func (receiver) Name())
    for match in re.finditer(r'func\s+\([^)]+\)\s+(\w+)\s*\(', source):
        patterns['methods'].append(match.group(1))
    
    # Structs
    for match in re.finditer(r'type\s+(\w+)\s+struct\s*\{', source):
        patterns['structs'].append(match.group(1))
    
    # Interfaces
    for match in re.finditer(r'type\s+(\w+)\s+interface\s*\{', source):
        patterns['interfaces'].append(match.group(1))
    
    # Goroutines and channels
    patterns['goroutines'] = len(re.findall(r'\bgo\s+\w+', source))
    patterns['channels'] = len(re.findall(r'\bchan\s+\w+|<-\s*\w+|\w+\s*<-', source))
    
    patterns['imports'] = list(set(patterns['imports']))
    
    return patterns


# ========== Rust Analysis ==========

def analyze_rust_file(filepath: Path) -> Dict:
    """Analyze Rust file for patterns."""
    try:
        source = filepath.read_text(encoding='utf-8')
    except:
        return {}
    
    patterns = {
        'functions': [],
        'structs': [],
        'enums': [],
        'traits': [],
        'impls': [],
        'mods': [],
        'uses': [],
        'macros': [],
        'pub_items': [],
        'async_functions': 0,
        'unsafe_blocks': 0,
    }
    
    # Functions
    for match in re.finditer(r'(?:pub\s+)?(?:async\s+)?fn\s+(\w+)', source):
        patterns['functions'].append(match.group(1))
        if 'pub ' in match.group(0):
            patterns['pub_items'].append(match.group(1))
    
    # Async functions
    patterns['async_functions'] = len(re.findall(r'\basync\s+fn\b', source))
    
    # Structs
    for match in re.finditer(r'(?:pub\s+)?struct\s+(\w+)', source):
        patterns['structs'].append(match.group(1))
    
    # Enums
    for match in re.finditer(r'(?:pub\s+)?enum\s+(\w+)', source):
        patterns['enums'].append(match.group(1))
    
    # Traits
    for match in re.finditer(r'(?:pub\s+)?trait\s+(\w+)', source):
        patterns['traits'].append(match.group(1))
    
    # Impl blocks
    for match in re.finditer(r'impl(?:<[^>]+>)?\s+(?:(\w+)\s+for\s+)?(\w+)', source):
        trait_name = match.group(1)
        type_name = match.group(2)
        if trait_name:
            patterns['impls'].append(f"{trait_name} for {type_name}")
        else:
            patterns['impls'].append(type_name)
    
    # Modules
    for match in re.finditer(r'(?:pub\s+)?mod\s+(\w+)', source):
        patterns['mods'].append(match.group(1))
    
    # Uses
    for match in re.finditer(r'use\s+([\w:]+)', source):
        patterns['uses'].append(match.group(1))
    
    # Macro definitions
    for match in re.finditer(r'macro_rules!\s+(\w+)', source):
        patterns['macros'].append(match.group(1))
    
    # Unsafe blocks
    patterns['unsafe_blocks'] = len(re.findall(r'\bunsafe\s*\{', source))
    
    return patterns


# ========== Java Analysis ==========

def analyze_java_file(filepath: Path) -> Dict:
    """Analyze Java file for patterns."""
    try:
        source = filepath.read_text(encoding='utf-8')
    except:
        return {}
    
    patterns = {
        'package': '',
        'classes': [],
        'interfaces': [],
        'enums': [],
        'methods': [],
        'imports': [],
        'annotations': [],
        'extends': [],
        'implements': [],
    }
    
    # Package
    match = re.search(r'package\s+([\w.]+)\s*;', source)
    if match:
        patterns['package'] = match.group(1)
    
    # Imports
    for match in re.finditer(r'import\s+([\w.*]+)\s*;', source):
        patterns['imports'].append(match.group(1))
    
    # Classes
    for match in re.finditer(r'(?:public\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?', source):
        patterns['classes'].append(match.group(1))
        if match.group(2):
            patterns['extends'].append(match.group(2))
        if match.group(3):
            patterns['implements'].extend([i.strip() for i in match.group(3).split(',')])
    
    # Interfaces
    for match in re.finditer(r'(?:public\s+)?interface\s+(\w+)', source):
        patterns['interfaces'].append(match.group(1))
    
    # Enums
    for match in re.finditer(r'(?:public\s+)?enum\s+(\w+)', source):
        patterns['enums'].append(match.group(1))
    
    # Methods
    for match in re.finditer(r'(?:public|private|protected)?\s*(?:static\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{', source):
        patterns['methods'].append(match.group(1))
    
    # Annotations
    patterns['annotations'] = list(set(re.findall(r'@(\w+)', source)))
    
    return patterns


# ========== C/C++ Analysis ==========

def analyze_c_file(filepath: Path) -> Dict:
    """Analyze C/C++ file for patterns."""
    try:
        source = filepath.read_text(encoding='utf-8')
    except:
        return {}
    
    patterns = {
        'functions': [],
        'structs': [],
        'classes': [],  # C++ only
        'enums': [],
        'typedefs': [],
        'macros': [],
        'includes': [],
        'namespaces': [],  # C++ only
        'templates': 0,  # C++ only
    }
    
    # Includes
    for match in re.finditer(r'#include\s*[<"]([^>"]+)[>"]', source):
        patterns['includes'].append(match.group(1))
    
    # Macros
    for match in re.finditer(r'#define\s+(\w+)', source):
        patterns['macros'].append(match.group(1))
    
    # Functions (simplified - won't catch all)
    for match in re.finditer(r'^(?:static\s+)?(?:inline\s+)?(?:const\s+)?(?:\w+\s*\*?\s+)+(\w+)\s*\([^;]*\)\s*\{', source, re.MULTILINE):
        name = match.group(1)
        if name not in ('if', 'while', 'for', 'switch'):
            patterns['functions'].append(name)
    
    # Structs
    for match in re.finditer(r'(?:typedef\s+)?struct\s+(\w+)', source):
        patterns['structs'].append(match.group(1))
    
    # Enums
    for match in re.finditer(r'(?:typedef\s+)?enum\s+(\w+)', source):
        patterns['enums'].append(match.group(1))
    
    # Typedefs
    for match in re.finditer(r'typedef\s+.*?(\w+)\s*;', source):
        patterns['typedefs'].append(match.group(1))
    
    # C++ specific
    if filepath.suffix in ('.cpp', '.cc', '.cxx', '.hpp'):
        # Classes
        for match in re.finditer(r'class\s+(\w+)', source):
            patterns['classes'].append(match.group(1))
        
        # Namespaces
        for match in re.finditer(r'namespace\s+(\w+)', source):
            patterns['namespaces'].append(match.group(1))
        
        # Templates
        patterns['templates'] = len(re.findall(r'template\s*<', source))
    
    return patterns


# ========== C# Analysis ==========

def analyze_csharp_file(filepath: Path) -> Dict:
    """Analyze C# file for patterns."""
    try:
        source = filepath.read_text(encoding='utf-8')
    except:
        return {}
    
    patterns = {
        'namespace': '',
        'classes': [],
        'interfaces': [],
        'structs': [],
        'enums': [],
        'methods': [],
        'properties': [],
        'usings': [],
        'attributes': [],
        'async_methods': 0,
        'linq_usage': 0,
        'nullable_enabled': False,
    }
    
    # Namespace
    match = re.search(r'namespace\s+([\w.]+)', source)
    if match:
        patterns['namespace'] = match.group(1)
    
    # Usings
    for match in re.finditer(r'using\s+([\w.]+)\s*;', source):
        patterns['usings'].append(match.group(1))
    
    # Classes
    for match in re.finditer(r'(?:public|private|internal|protected)?\s*(?:partial\s+)?(?:static\s+)?(?:abstract\s+)?(?:sealed\s+)?class\s+(\w+)', source):
        patterns['classes'].append(match.group(1))
    
    # Interfaces
    for match in re.finditer(r'(?:public|internal)?\s*interface\s+(I\w+)', source):
        patterns['interfaces'].append(match.group(1))
    
    # Structs
    for match in re.finditer(r'(?:public|private|internal)?\s*(?:readonly\s+)?struct\s+(\w+)', source):
        patterns['structs'].append(match.group(1))
    
    # Enums
    for match in re.finditer(r'(?:public|private|internal)?\s*enum\s+(\w+)', source):
        patterns['enums'].append(match.group(1))
    
    # Methods
    for match in re.finditer(r'(?:public|private|protected|internal)\s+(?:static\s+)?(?:async\s+)?(?:virtual\s+)?(?:override\s+)?(?:[\w<>\[\],\s]+)\s+(\w+)\s*\([^)]*\)', source):
        patterns['methods'].append(match.group(1))
    
    # Async methods
    patterns['async_methods'] = len(re.findall(r'\basync\s+Task', source))
    
    # Properties
    for match in re.finditer(r'(?:public|private|protected|internal)\s+(?:static\s+)?(?:virtual\s+)?(?:[\w<>\[\]?]+)\s+(\w+)\s*\{\s*(?:get|set)', source):
        patterns['properties'].append(match.group(1))
    
    # Attributes
    patterns['attributes'] = list(set(re.findall(r'\[(\w+)(?:\([^)]*\))?\]', source)))
    
    # LINQ usage
    patterns['linq_usage'] = len(re.findall(r'\.(Select|Where|OrderBy|GroupBy|FirstOrDefault|ToList|Any|All)\s*\(', source))
    
    # Nullable reference types
    patterns['nullable_enabled'] = '#nullable enable' in source or '<Nullable>enable</Nullable>' in source
    
    return patterns


# ========== Main Aggregation ==========

def analyze_project_patterns(project_path: str) -> Dict:
    """Analyze patterns across entire project."""
    root = Path(project_path).resolve()
    
    result = {
        'root': str(root),
        'naming': {
            'classes': Counter(),
            'functions': Counter(),
            'files': Counter(),
        },
        'languages': {},
        'architectural_patterns': [],
        'confidence': DETECTED,
    }
    
    all_classes = []
    all_functions = []
    all_filenames = []
    
    # Skip patterns
    skip_dirs = {'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build', '.git', 'vendor', 'target'}
    
    # Language-specific aggregation
    lang_stats = {
        'python': {'files': 0, 'patterns': []},
        'javascript': {'files': 0, 'patterns': []},
        'typescript': {'files': 0, 'patterns': []},
        'go': {'files': 0, 'patterns': []},
        'rust': {'files': 0, 'patterns': []},
        'java': {'files': 0, 'patterns': []},
        'c': {'files': 0, 'patterns': []},
        'cpp': {'files': 0, 'patterns': []},
        'csharp': {'files': 0, 'patterns': []},
    }
    
    # Analyze files
    for filepath in root.rglob('*'):
        if any(skip in filepath.parts for skip in skip_dirs):
            continue
        if not filepath.is_file():
            continue
        
        suffix = filepath.suffix.lower()
        all_filenames.append(filepath.stem)
        
        patterns = None
        lang = None
        
        if suffix == '.py':
            patterns = analyze_python_file(filepath)
            lang = 'python'
        elif suffix in ('.js', '.jsx', '.mjs'):
            patterns = analyze_js_file(filepath)
            lang = 'javascript'
        elif suffix in ('.ts', '.tsx'):
            patterns = analyze_js_file(filepath)
            lang = 'typescript'
        elif suffix == '.go':
            patterns = analyze_go_file(filepath)
            lang = 'go'
        elif suffix == '.rs':
            patterns = analyze_rust_file(filepath)
            lang = 'rust'
        elif suffix == '.java':
            patterns = analyze_java_file(filepath)
            lang = 'java'
        elif suffix in ('.c', '.h'):
            patterns = analyze_c_file(filepath)
            lang = 'c'
        elif suffix in ('.cpp', '.cc', '.cxx', '.hpp'):
            patterns = analyze_c_file(filepath)
            lang = 'cpp'
        elif suffix == '.cs':
            patterns = analyze_csharp_file(filepath)
            lang = 'csharp'
        
        if patterns and lang:
            lang_stats[lang]['files'] += 1
            lang_stats[lang]['patterns'].append(patterns)
            
            all_classes.extend(patterns.get('classes', []))
            all_classes.extend(patterns.get('structs', []))
            all_functions.extend(patterns.get('functions', []))
            all_functions.extend(patterns.get('methods', []))
    
    # Aggregate language stats
    for lang, stats in lang_stats.items():
        if stats['files'] == 0:
            continue
        
        result['languages'][lang] = {
            'files': stats['files'],
        }
        
        # Python specific
        if lang == 'python':
            all_patterns = stats['patterns']
            type_hints = sum(p.get('type_hints', 0) for p in all_patterns)
            no_hints = sum(p.get('no_type_hints', 0) for p in all_patterns)
            docstrings = sum(p.get('docstrings', 0) for p in all_patterns)
            no_docs = sum(p.get('no_docstrings', 0) for p in all_patterns)
            
            result['languages'][lang].update({
                'type_hint_coverage': round(type_hints / (type_hints + no_hints) * 100) if (type_hints + no_hints) > 0 else 0,
                'docstring_coverage': round(docstrings / (docstrings + no_docs) * 100) if (docstrings + no_docs) > 0 else 0,
                'async_usage': sum(p.get('async_functions', 0) for p in all_patterns),
                'dataclasses': sum(p.get('dataclasses', 0) for p in all_patterns),
            })
        
        # JavaScript/TypeScript specific
        elif lang in ('javascript', 'typescript'):
            all_patterns = stats['patterns']
            result['languages'][lang].update({
                'arrow_functions': sum(p.get('arrow_functions', 0) for p in all_patterns),
                'regular_functions': sum(p.get('regular_functions', 0) for p in all_patterns),
                'async_usage': sum(p.get('async_functions', 0) for p in all_patterns),
                'react_components': sum(len(p.get('react_components', [])) for p in all_patterns),
                'hooks_used': list(set(h for p in all_patterns for h in p.get('hooks', []))),
            })
        
        # Go specific
        elif lang == 'go':
            all_patterns = stats['patterns']
            result['languages'][lang].update({
                'goroutines': sum(p.get('goroutines', 0) for p in all_patterns),
                'channels': sum(p.get('channels', 0) for p in all_patterns),
                'interfaces': sum(len(p.get('interfaces', [])) for p in all_patterns),
            })
        
        # Rust specific
        elif lang == 'rust':
            all_patterns = stats['patterns']
            result['languages'][lang].update({
                'async_usage': sum(p.get('async_functions', 0) for p in all_patterns),
                'unsafe_blocks': sum(p.get('unsafe_blocks', 0) for p in all_patterns),
                'traits': sum(len(p.get('traits', [])) for p in all_patterns),
            })
        
        # C# specific
        elif lang == 'csharp':
            all_patterns = stats['patterns']
            result['languages'][lang].update({
                'async_usage': sum(p.get('async_methods', 0) for p in all_patterns),
                'linq_usage': sum(p.get('linq_usage', 0) for p in all_patterns),
                'interfaces': sum(len(p.get('interfaces', [])) for p in all_patterns),
                'attributes_used': list(set(a for p in all_patterns for a in p.get('attributes', []))),
            })
    
    # Naming conventions
    result['naming']['classes'] = detect_naming_convention(all_classes)
    result['naming']['functions'] = detect_naming_convention(all_functions)
    result['naming']['files'] = detect_naming_convention(all_filenames)
    
    # Detect architectural patterns from directory structure
    dirs = set(d.name.lower() for d in root.iterdir() if d.is_dir())
    
    if 'components' in dirs and ('pages' in dirs or 'views' in dirs):
        result['architectural_patterns'].append('component-based')
    if 'models' in dirs and 'views' in dirs and 'controllers' in dirs:
        result['architectural_patterns'].append('mvc')
    if 'services' in dirs or 'repositories' in dirs:
        result['architectural_patterns'].append('layered')
    if 'api' in dirs or 'routes' in dirs:
        result['architectural_patterns'].append('api-driven')
    if 'domain' in dirs or 'entities' in dirs:
        result['architectural_patterns'].append('domain-driven')
    if 'cmd' in dirs and 'pkg' in dirs:
        result['architectural_patterns'].append('go-standard')
    if 'src' in dirs and 'tests' in dirs:
        result['architectural_patterns'].append('src-tests-split')
    
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_patterns.py <project_path> [--output file.json]", file=sys.stderr)
        sys.exit(1)
    
    project_path = sys.argv[1]
    output_file = None
    
    if '--output' in sys.argv:
        output_file = sys.argv[sys.argv.index('--output') + 1]
    
    result = analyze_project_patterns(project_path)
    
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Patterns written to {output_file}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
