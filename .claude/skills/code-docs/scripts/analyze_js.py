#!/usr/bin/env python3
"""
JavaScript/TypeScript analyzer using regex patterns optimized for
common code patterns. For complex codebases, consider using the
TypeScript compiler API via a Node.js script.

This provides 80/20 coverage - handles most real-world code well.
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional


class JSAnalyzer:
    def __init__(self, source: str, filepath: str):
        self.source = source
        self.lines = source.split('\n')
        self.filepath = filepath
        self.is_typescript = filepath.endswith(('.ts', '.tsx'))
    
    def extract_jsdoc(self, end_line: int) -> Optional[str]:
        """Extract JSDoc comment immediately preceding a line."""
        # Look backwards for /** ... */
        search_start = max(0, end_line - 20)
        block = '\n'.join(self.lines[search_start:end_line])
        
        # Find last JSDoc in the block that ends near our target
        matches = list(re.finditer(r'/\*\*(.*?)\*/', block, re.DOTALL))
        if matches:
            last_match = matches[-1]
            # Check it's close to the function (within 2 lines of whitespace)
            after_doc = block[last_match.end():]
            if after_doc.strip() == '' or after_doc.count('\n') <= 2:
                doc = last_match.group(1)
                # Clean up the doc
                lines = doc.split('\n')
                cleaned = []
                for line in lines:
                    line = re.sub(r'^\s*\*\s?', '', line)
                    cleaned.append(line)
                return '\n'.join(cleaned).strip()
        return None
    
    def parse_params(self, params_str: str) -> list:
        """Parse parameter string into structured list."""
        if not params_str.strip():
            return []
        
        params = []
        depth = 0
        current = ""
        
        for char in params_str:
            if char in '<([{':
                depth += 1
            elif char in '>)]}':
                depth -= 1
            elif char == ',' and depth == 0:
                if current.strip():
                    params.append(self._parse_single_param(current.strip()))
                current = ""
                continue
            current += char
        
        if current.strip():
            params.append(self._parse_single_param(current.strip()))
        
        return params
    
    def _parse_single_param(self, param: str) -> dict:
        """Parse a single parameter."""
        result = {'name': param, 'type': None, 'default': None, 'optional': False}
        
        # Rest params
        if param.startswith('...'):
            param = param[3:]
            result['rest'] = True
        
        # Default value
        if '=' in param:
            param, default = param.split('=', 1)
            result['default'] = default.strip()
            param = param.strip()
        
        # Type annotation
        if ':' in param:
            param, type_hint = param.split(':', 1)
            result['type'] = type_hint.strip()
            param = param.strip()
        
        # Optional marker
        if param.endswith('?'):
            result['optional'] = True
            param = param[:-1]
        
        result['name'] = param
        return result
    
    def analyze(self) -> dict:
        """Analyze the source file."""
        elements = []
        
        # Pattern for functions (regular and arrow)
        patterns = [
            # export function name(...) { or function name(...) {
            (r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*(<[^>]+>)?\s*\(([^)]*)\)(?:\s*:\s*([^{]+))?\s*\{',
             'function'),
            # export const name = (...) => or const name = function(...) {
            (r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*(?::\s*[^=]+)?\s*=\s*(?:async\s+)?(?:function\s*)?\(([^)]*)\)(?:\s*:\s*([^=>{]+))?\s*(?:=>|{)',
             'function'),
            # class Name { or export class Name {
            (r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+(\w+))?(?:\s+implements\s+[^{]+)?\s*\{',
             'class'),
            # method inside class: name(...) { or async name(...) {
            (r'^\s+(?:static\s+)?(?:async\s+)?(\w+)\s*(<[^>]+>)?\s*\(([^)]*)\)(?:\s*:\s*([^{]+))?\s*\{',
             'method'),
        ]
        
        for i, line in enumerate(self.lines):
            for pattern, elem_type in patterns:
                match = re.match(pattern, line if elem_type == 'method' else '\n'.join(self.lines[max(0,i-1):i+1]))
                if not match:
                    match = re.search(pattern, line)
                
                if match:
                    groups = match.groups()
                    
                    if elem_type == 'class':
                        element = {
                            'type': 'class',
                            'name': groups[0],
                            'line': i + 1,
                            'extends': groups[1] if len(groups) > 1 else None,
                            'docstring': self.extract_jsdoc(i),
                        }
                    else:
                        name = groups[0]
                        params_str = groups[2] if len(groups) > 2 and groups[2] else (groups[1] if len(groups) > 1 else "")
                        returns = None
                        for g in groups:
                            if g and g not in [name, params_str] and not g.startswith('<'):
                                returns = g.strip()
                        
                        params = self.parse_params(params_str) if params_str else []
                        
                        is_async = 'async' in line
                        is_static = 'static' in line
                        is_export = 'export' in line
                        
                        sig_parts = []
                        if is_export:
                            sig_parts.append('export')
                        if is_async:
                            sig_parts.append('async')
                        sig_parts.append(f'function {name}({params_str})')
                        if returns:
                            sig_parts.append(f': {returns}')
                        
                        element = {
                            'type': elem_type,
                            'name': name,
                            'line': i + 1,
                            'signature': ' '.join(sig_parts),
                            'params': params,
                            'returns': returns,
                            'docstring': self.extract_jsdoc(i),
                            'is_async': is_async,
                            'is_static': is_static,
                            'is_export': is_export,
                            'is_private': name.startswith('_') or name.startswith('#'),
                        }
                    
                    # Avoid duplicates
                    if not any(e['name'] == element['name'] and e['line'] == element['line'] for e in elements):
                        elements.append(element)
        
        return {
            'filepath': self.filepath,
            'language': 'typescript' if self.is_typescript else 'javascript',
            'elements': elements
        }


def analyze_file(filepath: str) -> dict:
    """Analyze a single JS/TS file."""
    path = Path(filepath)
    try:
        source = path.read_text(encoding='utf-8')
        analyzer = JSAnalyzer(source, filepath)
        return analyzer.analyze()
    except Exception as e:
        return {'error': str(e), 'filepath': filepath}


def analyze_directory(dirpath: str) -> list:
    """Analyze all JS/TS files in a directory."""
    results = []
    extensions = ('.js', '.jsx', '.ts', '.tsx', '.mjs')
    
    for ext in extensions:
        for jsfile in Path(dirpath).rglob(f'*{ext}'):
            if 'node_modules' not in str(jsfile) and 'dist' not in str(jsfile):
                results.append(analyze_file(str(jsfile)))
    
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_js.py <file_or_dir> [--output file.json]", file=sys.stderr)
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
