#!/usr/bin/env python3
"""
C/C++ analyzer for embedded systems code.
Uses regex patterns optimized for common embedded C patterns.

For complex C++ codebases, consider using libclang or tree-sitter-c.
This handles typical embedded C well: functions, structs, macros, typedefs.
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional


class CAnalyzer:
    def __init__(self, source: str, filepath: str):
        self.source = source
        self.lines = source.split('\n')
        self.filepath = filepath
        self.is_header = filepath.endswith(('.h', '.hpp'))
        self.is_cpp = filepath.endswith(('.cpp', '.cc', '.hpp', '.cxx'))
    
    def extract_doxygen(self, end_line: int) -> Optional[str]:
        """Extract Doxygen comment preceding a line."""
        search_start = max(0, end_line - 30)
        
        # Look for /** ... */ or /*! ... */ block
        for i in range(end_line - 1, search_start - 1, -1):
            line = self.lines[i].rstrip()
            
            # End of doc block
            if line.endswith('*/'):
                # Find start of block
                doc_lines = []
                for j in range(i, search_start - 1, -1):
                    doc_lines.insert(0, self.lines[j])
                    if '/**' in self.lines[j] or '/*!' in self.lines[j]:
                        # Clean and return
                        doc = '\n'.join(doc_lines)
                        doc = re.sub(r'/\*[*!]|\*/', '', doc)
                        doc = re.sub(r'^\s*\*\s?', '', doc, flags=re.MULTILINE)
                        return doc.strip()
                break
            
            # Single-line /// or //! comments
            if line.strip().startswith('///') or line.strip().startswith('//!'):
                doc_lines = []
                for j in range(i, search_start - 1, -1):
                    stripped = self.lines[j].strip()
                    if stripped.startswith('///') or stripped.startswith('//!'):
                        doc_lines.insert(0, re.sub(r'^//[/!]\s?', '', stripped))
                    else:
                        break
                return '\n'.join(doc_lines).strip()
            
            # Non-empty, non-comment line - stop searching
            if line.strip() and not line.strip().startswith('//'):
                break
        
        return None
    
    def parse_params(self, params_str: str) -> list:
        """Parse C function parameters."""
        params = []
        if not params_str.strip() or params_str.strip() == 'void':
            return params
        
        for param in params_str.split(','):
            param = param.strip()
            if not param:
                continue
            
            # Match: type name, type *name, type name[], const type *name, etc.
            match = re.match(
                r'^((?:const\s+|volatile\s+|static\s+)*\w+(?:\s*\*+)?)\s+(\**)(\w+)(\[.*\])?$',
                param
            )
            
            if match:
                type_part = match.group(1) + match.group(2)
                name = match.group(3)
                array = match.group(4) or ''
                params.append({
                    'name': name,
                    'type': type_part.strip() + array,
                })
            else:
                # Fallback: just split on last space
                parts = param.rsplit(None, 1)
                if len(parts) == 2:
                    params.append({'name': parts[1].strip('*[]'), 'type': parts[0]})
                else:
                    params.append({'name': param, 'type': None})
        
        return params
    
    def analyze(self) -> dict:
        """Analyze the source file."""
        elements = []
        
        # Join all lines for multi-line matching
        full_source = self.source
        
        # Function pattern: return_type name(params) { or ;
        func_pattern = re.compile(
            r'^[ \t]*((?:static\s+|inline\s+|extern\s+|const\s+)*'  # modifiers
            r'(?:unsigned\s+|signed\s+)?'  # sign
            r'\w+(?:\s*\*+)?)\s+'  # return type
            r'(\w+)\s*'  # function name
            r'\(([^)]*)\)\s*'  # parameters
            r'([{;])',  # body start or declaration
            re.MULTILINE
        )
        
        for match in func_pattern.finditer(full_source):
            return_type = match.group(1).strip()
            name = match.group(2)
            params_str = match.group(3)
            is_definition = match.group(4) == '{'
            
            # Skip control statements
            if name in ('if', 'while', 'for', 'switch', 'return', 'sizeof', 'typeof'):
                continue
            
            line_num = full_source[:match.start()].count('\n') + 1
            params = self.parse_params(params_str)
            
            # Build signature
            param_strs = [f"{p['type']} {p['name']}" if p['type'] else p['name'] for p in params]
            signature = f"{return_type} {name}({', '.join(param_strs) if param_strs else 'void'})"
            
            element = {
                'type': 'function',
                'name': name,
                'line': line_num,
                'signature': signature,
                'params': params,
                'returns': return_type,
                'docstring': self.extract_doxygen(line_num - 1),
                'is_static': 'static' in return_type,
                'is_definition': is_definition,
            }
            
            # Avoid duplicates
            if not any(e['name'] == name and e['line'] == line_num for e in elements):
                elements.append(element)
        
        # Struct/typedef pattern
        struct_pattern = re.compile(
            r'typedef\s+struct\s*(?:\w+)?\s*\{[^}]*\}\s*(\w+)\s*;',
            re.DOTALL
        )
        
        for match in struct_pattern.finditer(full_source):
            name = match.group(1)
            line_num = full_source[:match.start()].count('\n') + 1
            
            elements.append({
                'type': 'struct',
                'name': name,
                'line': line_num,
                'docstring': self.extract_doxygen(line_num - 1),
            })
        
        # Enum pattern
        enum_pattern = re.compile(
            r'typedef\s+enum\s*(?:\w+)?\s*\{[^}]*\}\s*(\w+)\s*;',
            re.DOTALL
        )
        
        for match in enum_pattern.finditer(full_source):
            name = match.group(1)
            line_num = full_source[:match.start()].count('\n') + 1
            
            elements.append({
                'type': 'enum',
                'name': name,
                'line': line_num,
                'docstring': self.extract_doxygen(line_num - 1),
            })
        
        # Macro pattern
        macro_pattern = re.compile(
            r'^[ \t]*#define\s+(\w+)(?:\(([^)]*)\))?\s+(.+?)(?:\\\n.*)*$',
            re.MULTILINE
        )
        
        for match in macro_pattern.finditer(full_source):
            name = match.group(1)
            params_str = match.group(2)
            
            line_num = full_source[:match.start()].count('\n') + 1
            
            element = {
                'type': 'macro',
                'name': name,
                'line': line_num,
                'docstring': self.extract_doxygen(line_num - 1),
            }
            
            if params_str is not None:
                element['params'] = [{'name': p.strip()} for p in params_str.split(',') if p.strip()]
                element['signature'] = f"#define {name}({params_str})"
            else:
                element['signature'] = f"#define {name}"
            
            elements.append(element)
        
        return {
            'filepath': self.filepath,
            'language': 'cpp' if self.is_cpp else 'c',
            'is_header': self.is_header,
            'elements': elements
        }


def analyze_file(filepath: str) -> dict:
    """Analyze a single C/C++ file."""
    path = Path(filepath)
    try:
        source = path.read_text(encoding='utf-8', errors='replace')
        analyzer = CAnalyzer(source, filepath)
        return analyzer.analyze()
    except Exception as e:
        return {'error': str(e), 'filepath': filepath}


def analyze_directory(dirpath: str) -> list:
    """Analyze all C/C++ files in a directory."""
    results = []
    extensions = ('.c', '.h', '.cpp', '.hpp', '.cc', '.hh', '.cxx')
    
    for ext in extensions:
        for cfile in Path(dirpath).rglob(f'*{ext}'):
            if 'build' not in str(cfile).lower():
                results.append(analyze_file(str(cfile)))
    
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_c.py <file_or_dir> [--output file.json]", file=sys.stderr)
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
