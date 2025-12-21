#!/usr/bin/env python3
"""
Style Detector
Analyzes existing code to detect and document the style conventions in use.
Learns from the codebase rather than imposing external rules.
"""

import ast
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


class PythonStyleDetector:
    """Detect Python code style patterns."""
    
    def __init__(self):
        self.stats = {
            'indent': Counter(),  # 2, 4, tab
            'quotes': Counter(),  # single, double
            'naming': {
                'functions': Counter(),
                'classes': Counter(),
                'constants': Counter(),
                'variables': Counter(),
            },
            'imports': {
                'style': Counter(),  # absolute, relative
                'grouping': [],  # stdlib, third_party, local order
            },
            'docstrings': {
                'style': Counter(),  # google, numpy, sphinx, none
                'coverage': {'with': 0, 'without': 0},
            },
            'type_hints': {'with': 0, 'without': 0},
            'line_length': [],
            'blank_lines': {
                'between_functions': Counter(),
                'between_classes': Counter(),
            },
            'trailing_commas': Counter(),  # yes, no
            'string_formatting': Counter(),  # f-string, format, percent
        }
    
    def analyze_file(self, filepath: Path) -> None:
        """Analyze a single Python file."""
        try:
            source = filepath.read_text(encoding='utf-8')
            lines = source.split('\n')
        except:
            return
        
        # Line-level analysis
        self._analyze_lines(lines)
        
        # AST analysis
        try:
            tree = ast.parse(source)
            self._analyze_ast(tree, source)
        except SyntaxError:
            pass
    
    def _analyze_lines(self, lines: List[str]) -> None:
        """Analyze line-level style."""
        prev_indent = 0
        
        for i, line in enumerate(lines):
            if not line.strip():
                continue
            
            # Line length
            self.stats['line_length'].append(len(line))
            
            # Indentation
            if line and not line[0].isspace():
                continue
            
            indent = len(line) - len(line.lstrip())
            if indent > 0:
                if '\t' in line[:indent]:
                    self.stats['indent']['tab'] += 1
                elif indent % 4 == 0:
                    self.stats['indent']['4-space'] += 1
                elif indent % 2 == 0:
                    self.stats['indent']['2-space'] += 1
            
            # Quote style in strings
            for match in re.finditer(r'(["\'])(?:(?!\1).)*\1', line):
                quote = match.group(1)
                self.stats['quotes']['double' if quote == '"' else 'single'] += 1
            
            # String formatting
            if 'f"' in line or "f'" in line:
                self.stats['string_formatting']['f-string'] += 1
            elif '.format(' in line:
                self.stats['string_formatting']['.format()'] += 1
            elif re.search(r'%\s*[(\']', line):
                self.stats['string_formatting']['%-formatting'] += 1
            
            # Trailing commas
            stripped = line.rstrip()
            if stripped.endswith(',)') or stripped.endswith(',]') or stripped.endswith(',}'):
                self.stats['trailing_commas']['yes'] += 1
            elif stripped.endswith(')') or stripped.endswith(']') or stripped.endswith('}'):
                # Check if previous content suggests a list/dict
                if re.search(r'[,\[({\s]$', lines[i-1].rstrip() if i > 0 else ''):
                    self.stats['trailing_commas']['no'] += 1
    
    def _analyze_ast(self, tree: ast.AST, source: str) -> None:
        """Analyze AST for naming and structure."""
        prev_node_end = 0
        
        for node in ast.walk(tree):
            # Function/method naming and style
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._classify_name(node.name, 'functions')
                
                # Docstring
                if (node.body and isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Constant) and
                    isinstance(node.body[0].value.value, str)):
                    self.stats['docstrings']['coverage']['with'] += 1
                    self._classify_docstring_style(node.body[0].value.value)
                else:
                    self.stats['docstrings']['coverage']['without'] += 1
                
                # Type hints
                has_hints = node.returns is not None or any(
                    arg.annotation for arg in node.args.args
                )
                if has_hints:
                    self.stats['type_hints']['with'] += 1
                else:
                    self.stats['type_hints']['without'] += 1
            
            # Class naming
            elif isinstance(node, ast.ClassDef):
                self._classify_name(node.name, 'classes')
            
            # Variable/constant naming
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id.isupper():
                            self._classify_name(target.id, 'constants')
                        else:
                            self._classify_name(target.id, 'variables')
            
            # Import style
            elif isinstance(node, ast.Import):
                self.stats['imports']['style']['absolute'] += 1
            elif isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    self.stats['imports']['style']['relative'] += 1
                else:
                    self.stats['imports']['style']['absolute'] += 1
    
    def _classify_name(self, name: str, category: str) -> None:
        """Classify naming convention."""
        if name.startswith('_'):
            return  # Skip private names
        
        if name.isupper() or (name.upper() == name and '_' in name):
            self.stats['naming'][category]['SCREAMING_SNAKE_CASE'] += 1
        elif '_' in name and name.islower():
            self.stats['naming'][category]['snake_case'] += 1
        elif name[0].isupper() and not '_' in name:
            self.stats['naming'][category]['PascalCase'] += 1
        elif name[0].islower() and any(c.isupper() for c in name):
            self.stats['naming'][category]['camelCase'] += 1
        elif name.islower():
            self.stats['naming'][category]['lowercase'] += 1
    
    def _classify_docstring_style(self, docstring: str) -> None:
        """Classify docstring style."""
        if 'Args:' in docstring or 'Returns:' in docstring:
            self.stats['docstrings']['style']['google'] += 1
        elif ':param ' in docstring or ':returns:' in docstring:
            self.stats['docstrings']['style']['sphinx'] += 1
        elif 'Parameters' in docstring and '----------' in docstring:
            self.stats['docstrings']['style']['numpy'] += 1
        else:
            self.stats['docstrings']['style']['simple'] += 1
    
    def get_report(self) -> Dict:
        """Generate style report."""
        report = {
            'indentation': self._get_dominant(self.stats['indent']),
            'quotes': self._get_dominant(self.stats['quotes']),
            'naming': {
                cat: self._get_dominant(counts)
                for cat, counts in self.stats['naming'].items()
                if counts
            },
            'imports': {
                'style': self._get_dominant(self.stats['imports']['style']),
            },
            'docstrings': {
                'style': self._get_dominant(self.stats['docstrings']['style']),
                'coverage_percent': self._calc_percent(
                    self.stats['docstrings']['coverage']['with'],
                    self.stats['docstrings']['coverage']['without']
                ),
            },
            'type_hints': {
                'usage_percent': self._calc_percent(
                    self.stats['type_hints']['with'],
                    self.stats['type_hints']['without']
                ),
            },
            'line_length': {
                'max': max(self.stats['line_length']) if self.stats['line_length'] else 0,
                'avg': sum(self.stats['line_length']) // len(self.stats['line_length']) if self.stats['line_length'] else 0,
                'over_80': sum(1 for l in self.stats['line_length'] if l > 80),
                'over_100': sum(1 for l in self.stats['line_length'] if l > 100),
            },
            'string_formatting': self._get_dominant(self.stats['string_formatting']),
            'trailing_commas': self._get_dominant(self.stats['trailing_commas']),
        }
        return report
    
    def _get_dominant(self, counter: Counter) -> str:
        """Get the most common value."""
        if not counter:
            return 'unknown'
        return counter.most_common(1)[0][0]
    
    def _calc_percent(self, with_count: int, without_count: int) -> int:
        """Calculate percentage."""
        total = with_count + without_count
        if total == 0:
            return 0
        return round(with_count / total * 100)


class JavaScriptStyleDetector:
    """Detect JavaScript/TypeScript code style patterns."""
    
    def __init__(self):
        self.stats = {
            'indent': Counter(),
            'quotes': Counter(),
            'semicolons': Counter(),
            'naming': {
                'functions': Counter(),
                'classes': Counter(),
                'constants': Counter(),
                'variables': Counter(),
            },
            'arrow_vs_function': Counter(),
            'const_let_var': Counter(),
            'trailing_commas': Counter(),
            'object_shorthand': Counter(),
            'template_literals': Counter(),
            'line_length': [],
        }
    
    def analyze_file(self, filepath: Path) -> None:
        """Analyze a single JS/TS file."""
        try:
            source = filepath.read_text(encoding='utf-8')
            lines = source.split('\n')
        except:
            return
        
        for line in lines:
            if not line.strip():
                continue
            
            # Line length
            self.stats['line_length'].append(len(line))
            
            # Indentation
            if line and line[0].isspace():
                indent = len(line) - len(line.lstrip())
                if '\t' in line[:indent]:
                    self.stats['indent']['tab'] += 1
                elif indent % 4 == 0:
                    self.stats['indent']['4-space'] += 1
                elif indent % 2 == 0:
                    self.stats['indent']['2-space'] += 1
            
            # Quotes
            single = line.count("'") - line.count("\\'")
            double = line.count('"') - line.count('\\"')
            backtick = line.count('`')
            
            if single > double:
                self.stats['quotes']['single'] += 1
            elif double > single:
                self.stats['quotes']['double'] += 1
            
            if backtick > 0:
                self.stats['template_literals']['yes'] += 1
            
            # Semicolons
            stripped = line.rstrip()
            if stripped.endswith(';'):
                self.stats['semicolons']['yes'] += 1
            elif stripped and not stripped.endswith(('{', '}', ',', '(', '/')):
                self.stats['semicolons']['no'] += 1
            
            # const/let/var
            if re.search(r'\bconst\s+', line):
                self.stats['const_let_var']['const'] += 1
            if re.search(r'\blet\s+', line):
                self.stats['const_let_var']['let'] += 1
            if re.search(r'\bvar\s+', line):
                self.stats['const_let_var']['var'] += 1
            
            # Arrow functions vs regular
            if '=>' in line:
                self.stats['arrow_vs_function']['arrow'] += 1
            if re.search(r'\bfunction\s*[\w(]', line):
                self.stats['arrow_vs_function']['function'] += 1
            
            # Trailing commas
            if re.search(r',\s*[)\]}]', line):
                self.stats['trailing_commas']['yes'] += 1
            
            # Naming conventions from declarations
            for match in re.finditer(r'\b(?:const|let|var)\s+([A-Z][A-Z0-9_]*)\s*=', line):
                self.stats['naming']['constants']['SCREAMING_SNAKE_CASE'] += 1
            
            for match in re.finditer(r'\b(?:const|let|var)\s+([a-z][a-zA-Z0-9]*)\s*=', line):
                name = match.group(1)
                if any(c.isupper() for c in name):
                    self.stats['naming']['variables']['camelCase'] += 1
                else:
                    self.stats['naming']['variables']['lowercase'] += 1
            
            for match in re.finditer(r'\bclass\s+([A-Z][a-zA-Z0-9]*)', line):
                self.stats['naming']['classes']['PascalCase'] += 1
            
            for match in re.finditer(r'\bfunction\s+([a-z][a-zA-Z0-9]*)', line):
                name = match.group(1)
                if any(c.isupper() for c in name):
                    self.stats['naming']['functions']['camelCase'] += 1
                else:
                    self.stats['naming']['functions']['lowercase'] += 1
    
    def get_report(self) -> Dict:
        """Generate style report."""
        report = {
            'indentation': self._get_dominant(self.stats['indent']),
            'quotes': self._get_dominant(self.stats['quotes']),
            'semicolons': self._get_dominant(self.stats['semicolons']),
            'naming': {
                cat: self._get_dominant(counts)
                for cat, counts in self.stats['naming'].items()
                if counts
            },
            'variable_declaration': self._get_dominant(self.stats['const_let_var']),
            'function_style': self._get_dominant(self.stats['arrow_vs_function']),
            'trailing_commas': self._get_dominant(self.stats['trailing_commas']),
            'template_literals': 'yes' in self.stats['template_literals'],
            'line_length': {
                'max': max(self.stats['line_length']) if self.stats['line_length'] else 0,
                'avg': sum(self.stats['line_length']) // len(self.stats['line_length']) if self.stats['line_length'] else 0,
            },
        }
        return report
    
    def _get_dominant(self, counter: Counter) -> str:
        if not counter:
            return 'unknown'
        return counter.most_common(1)[0][0]


def detect_project_style(project_path: str) -> Dict:
    """Detect style conventions across a project."""
    root = Path(project_path).resolve()
    
    py_detector = PythonStyleDetector()
    js_detector = JavaScriptStyleDetector()
    
    py_count = 0
    js_count = 0
    
    # Analyze Python files
    for pyfile in root.rglob('*.py'):
        if '__pycache__' in str(pyfile) or '.venv' in str(pyfile):
            continue
        py_detector.analyze_file(pyfile)
        py_count += 1
    
    # Analyze JS/TS files
    for ext in ['*.js', '*.jsx', '*.ts', '*.tsx']:
        for jsfile in root.rglob(ext):
            if 'node_modules' in str(jsfile) or 'dist' in str(jsfile):
                continue
            js_detector.analyze_file(jsfile)
            js_count += 1
    
    result = {
        'project': root.name,
        'files_analyzed': {
            'python': py_count,
            'javascript': js_count,
        },
    }
    
    if py_count > 0:
        result['python'] = py_detector.get_report()
    
    if js_count > 0:
        result['javascript'] = js_detector.get_report()
    
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: detect_style.py <project_path> [--output file.json]", file=sys.stderr)
        sys.exit(1)
    
    project_path = sys.argv[1]
    output_file = None
    
    if '--output' in sys.argv:
        output_file = sys.argv[sys.argv.index('--output') + 1]
    
    result = detect_project_style(project_path)
    
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Style report written to {output_file}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
