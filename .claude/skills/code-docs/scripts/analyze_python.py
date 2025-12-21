#!/usr/bin/env python3
"""
Python code analyzer using AST parsing.
Extracts accurate structure for documentation generation.
"""

import ast
import json
import sys
from pathlib import Path
from typing import Optional


class PythonAnalyzer(ast.NodeVisitor):
    def __init__(self, source: str, filepath: str):
        self.source = source
        self.lines = source.split('\n')
        self.filepath = filepath
        self.elements = []
        self.current_class = None
    
    def get_docstring(self, node) -> Optional[str]:
        """Extract docstring from a node."""
        return ast.get_docstring(node)
    
    def get_source_segment(self, node) -> str:
        """Get the source code for a node."""
        return ast.get_source_segment(self.source, node) or ""
    
    def format_annotation(self, node) -> Optional[str]:
        """Convert annotation AST to string."""
        if node is None:
            return None
        return ast.unparse(node)
    
    def extract_params(self, args: ast.arguments) -> list:
        """Extract parameter information from function arguments."""
        params = []
        
        # Regular args
        defaults_offset = len(args.args) - len(args.defaults)
        for i, arg in enumerate(args.args):
            default_idx = i - defaults_offset
            param = {
                'name': arg.arg,
                'type': self.format_annotation(arg.annotation),
                'default': ast.unparse(args.defaults[default_idx]) if default_idx >= 0 else None
            }
            params.append(param)
        
        # *args
        if args.vararg:
            params.append({
                'name': args.vararg.arg,
                'type': self.format_annotation(args.vararg.annotation),
                'kind': 'vararg'
            })
        
        # **kwargs
        if args.kwarg:
            params.append({
                'name': args.kwarg.arg,
                'type': self.format_annotation(args.kwarg.annotation),
                'kind': 'kwarg'
            })
        
        return params
    
    def visit_Module(self, node):
        """Visit module and extract module-level docstring."""
        self.module_doc = ast.get_docstring(node)
        self.generic_visit(node)
    
    def visit_ClassDef(self, node):
        """Visit class definition."""
        element = {
            'type': 'class',
            'name': node.name,
            'line': node.lineno,
            'end_line': node.end_lineno,
            'docstring': self.get_docstring(node),
            'decorators': [ast.unparse(d) for d in node.decorator_list],
            'bases': [ast.unparse(b) for b in node.bases],
            'methods': []
        }
        
        # Visit methods within class context
        old_class = self.current_class
        self.current_class = element
        
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.visit_function(child, is_method=True)
        
        self.current_class = old_class
        self.elements.append(element)
    
    def visit_FunctionDef(self, node):
        """Visit function definition."""
        if self.current_class is None:
            self.visit_function(node, is_method=False)
    
    def visit_AsyncFunctionDef(self, node):
        """Visit async function definition."""
        if self.current_class is None:
            self.visit_function(node, is_method=False, is_async=True)
    
    def visit_function(self, node, is_method=False, is_async=False):
        """Process a function/method node."""
        if isinstance(node, ast.AsyncFunctionDef):
            is_async = True
        
        params = self.extract_params(node.args)
        
        # Filter out 'self' and 'cls' from display but note them
        has_self = params and params[0]['name'] in ('self', 'cls')
        display_params = params[1:] if has_self else params
        
        element = {
            'type': 'method' if is_method else 'function',
            'name': node.name,
            'line': node.lineno,
            'end_line': node.end_lineno,
            'docstring': self.get_docstring(node),
            'params': display_params,
            'returns': self.format_annotation(node.returns),
            'decorators': [ast.unparse(d) for d in node.decorator_list],
            'is_async': is_async,
            'is_private': node.name.startswith('_'),
            'is_dunder': node.name.startswith('__') and node.name.endswith('__'),
        }
        
        # Build signature
        param_strs = []
        for p in params:
            s = p['name']
            if p.get('type'):
                s += f": {p['type']}"
            if p.get('default'):
                s += f" = {p['default']}"
            if p.get('kind') == 'vararg':
                s = '*' + s
            elif p.get('kind') == 'kwarg':
                s = '**' + s
            param_strs.append(s)
        
        sig = f"{'async ' if is_async else ''}def {node.name}({', '.join(param_strs)})"
        if node.returns:
            sig += f" -> {self.format_annotation(node.returns)}"
        element['signature'] = sig
        
        if is_method and self.current_class:
            self.current_class['methods'].append(element)
        else:
            self.elements.append(element)


def analyze_file(filepath: str) -> dict:
    """Analyze a single Python file."""
    path = Path(filepath)
    
    try:
        source = path.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=filepath)
    except SyntaxError as e:
        return {'error': f"Syntax error: {e}", 'filepath': filepath}
    except Exception as e:
        return {'error': str(e), 'filepath': filepath}
    
    analyzer = PythonAnalyzer(source, filepath)
    analyzer.visit(tree)
    
    return {
        'filepath': str(path),
        'language': 'python',
        'module_docstring': analyzer.module_doc,
        'elements': analyzer.elements
    }


def analyze_directory(dirpath: str) -> list:
    """Analyze all Python files in a directory."""
    results = []
    for pyfile in Path(dirpath).rglob('*.py'):
        if '__pycache__' not in str(pyfile) and '.venv' not in str(pyfile):
            results.append(analyze_file(str(pyfile)))
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_python.py <file_or_dir> [--output file.json]", file=sys.stderr)
        sys.exit(1)
    
    target = sys.argv[1]
    output_file = None
    if '--output' in sys.argv:
        output_file = sys.argv[sys.argv.index('--output') + 1]
    
    path = Path(target)
    if path.is_file():
        result = analyze_file(target)
    elif path.is_dir():
        result = {'files': analyze_directory(target)}
    else:
        print(f"Error: {target} not found", file=sys.stderr)
        sys.exit(1)
    
    output = json.dumps(result, indent=2)
    
    if output_file:
        Path(output_file).write_text(output)
        print(f"Written to {output_file}")
    else:
        print(output)


if __name__ == "__main__":
    main()
