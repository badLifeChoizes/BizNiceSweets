#!/usr/bin/env python3
"""
Go analyzer for documentation extraction.
Handles packages, functions, types, interfaces, and Go doc comments.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class GoElement:
    type: str  # package, function, method, type, interface, struct, const, var
    name: str
    line: int
    signature: str = ""
    docstring: Optional[str] = None
    params: List[Dict] = field(default_factory=list)
    returns: Optional[str] = None
    receiver: Optional[str] = None  # For methods
    is_exported: bool = False
    methods: List[Dict] = field(default_factory=list)


class GoAnalyzer:
    def __init__(self, source: str, filepath: str):
        self.source = source
        self.lines = source.split('\n')
        self.filepath = filepath
        self.package = ""
        self.elements: List[GoElement] = []
    
    def extract_doc_comment(self, end_line: int) -> Optional[str]:
        """Extract Go doc comment preceding a line."""
        doc_lines = []
        
        for i in range(end_line - 1, max(0, end_line - 50), -1):
            line = self.lines[i].strip()
            
            if line.startswith('//'):
                # Single line comment
                content = line[2:].strip()
                doc_lines.insert(0, content)
            elif line == '':
                # Empty line - stop if we have content
                if doc_lines:
                    break
            else:
                # Hit code
                break
        
        # Also check for /* */ block comments
        if not doc_lines:
            search_start = max(0, end_line - 30)
            block = '\n'.join(self.lines[search_start:end_line])
            
            # Find last block comment
            match = re.search(r'/\*(.*?)\*/', block, re.DOTALL)
            if match:
                doc = match.group(1)
                # Clean up
                lines = doc.split('\n')
                cleaned = []
                for line in lines:
                    line = re.sub(r'^\s*\*\s?', '', line)
                    cleaned.append(line)
                return '\n'.join(cleaned).strip()
        
        return '\n'.join(doc_lines) if doc_lines else None
    
    def parse_params(self, params_str: str) -> List[Dict]:
        """Parse Go function parameters."""
        if not params_str.strip():
            return []
        
        params = []
        # Go allows grouping: (a, b int, c string)
        # Need to handle this carefully
        
        parts = []
        depth = 0
        current = ""
        
        for char in params_str:
            if char in '([{':
                depth += 1
            elif char in ')]}':
                depth -= 1
            elif char == ',' and depth == 0:
                parts.append(current.strip())
                current = ""
                continue
            current += char
        
        if current.strip():
            parts.append(current.strip())
        
        # Now process parts, carrying type forward
        last_type = None
        temp_names = []
        
        for part in parts:
            # Check if this part has a type
            tokens = part.split()
            
            if len(tokens) >= 2:
                # Has type - flush temp names with this type
                type_str = ' '.join(tokens[1:])
                
                for name in temp_names:
                    params.append({'name': name, 'type': type_str})
                temp_names = []
                
                params.append({'name': tokens[0], 'type': type_str})
                last_type = type_str
            else:
                # Just a name - save for later
                temp_names.append(tokens[0])
        
        # Any remaining temp names get the last type
        for name in temp_names:
            params.append({'name': name, 'type': last_type})
        
        return params
    
    def parse_returns(self, returns_str: str) -> str:
        """Parse Go return types."""
        if not returns_str.strip():
            return None
        
        returns_str = returns_str.strip()
        
        # Remove parentheses if present
        if returns_str.startswith('(') and returns_str.endswith(')'):
            returns_str = returns_str[1:-1]
        
        return returns_str
    
    def analyze(self) -> Dict:
        """Analyze the source file."""
        
        # Extract package
        pkg_match = re.search(r'^package\s+(\w+)', self.source, re.MULTILINE)
        if pkg_match:
            self.package = pkg_match.group(1)
        
        # Find functions and methods
        func_pattern = re.compile(
            r'^func\s+'
            r'(?:\((\w+)\s+\*?(\w+)\)\s+)?'  # Optional receiver
            r'(\w+)\s*'  # Function name
            r'\(([^)]*)\)\s*'  # Parameters
            r'(\([^)]+\)|[\w\[\]*]+)?\s*'  # Return type(s)
            r'\{',
            re.MULTILINE
        )
        
        for match in func_pattern.finditer(self.source):
            line_num = self.source[:match.start()].count('\n') + 1
            receiver_name = match.group(1)
            receiver_type = match.group(2)
            name = match.group(3)
            params_str = match.group(4)
            returns_str = match.group(5)
            
            is_method = receiver_type is not None
            
            element = GoElement(
                type='method' if is_method else 'function',
                name=name,
                line=line_num,
                params=self.parse_params(params_str),
                returns=self.parse_returns(returns_str) if returns_str else None,
                receiver=f"({receiver_name} {receiver_type})" if is_method else None,
                docstring=self.extract_doc_comment(line_num - 1),
                is_exported=name[0].isupper(),
            )
            
            # Build signature
            sig = "func "
            if element.receiver:
                sig += f"{element.receiver} "
            sig += f"{name}({params_str})"
            if element.returns:
                sig += f" {element.returns}"
            element.signature = sig
            
            self.elements.append(element)
        
        # Find type declarations (struct, interface)
        type_pattern = re.compile(
            r'^type\s+(\w+)\s+(struct|interface)\s*\{',
            re.MULTILINE
        )
        
        for match in type_pattern.finditer(self.source):
            line_num = self.source[:match.start()].count('\n') + 1
            name = match.group(1)
            kind = match.group(2)
            
            element = GoElement(
                type=kind,
                name=name,
                line=line_num,
                docstring=self.extract_doc_comment(line_num - 1),
                is_exported=name[0].isupper(),
            )
            element.signature = f"type {name} {kind}"
            
            self.elements.append(element)
        
        # Find type aliases and simple types
        type_alias_pattern = re.compile(
            r'^type\s+(\w+)\s+(?!struct|interface)(\S+)',
            re.MULTILINE
        )
        
        for match in type_alias_pattern.finditer(self.source):
            line_num = self.source[:match.start()].count('\n') + 1
            name = match.group(1)
            base_type = match.group(2)
            
            element = GoElement(
                type='type',
                name=name,
                line=line_num,
                returns=base_type,
                docstring=self.extract_doc_comment(line_num - 1),
                is_exported=name[0].isupper(),
            )
            element.signature = f"type {name} {base_type}"
            
            self.elements.append(element)
        
        # Find const blocks
        const_pattern = re.compile(
            r'^const\s+(\w+)\s*(?:[\w\[\]]+)?\s*=',
            re.MULTILINE
        )
        
        for match in const_pattern.finditer(self.source):
            line_num = self.source[:match.start()].count('\n') + 1
            name = match.group(1)
            
            element = GoElement(
                type='const',
                name=name,
                line=line_num,
                docstring=self.extract_doc_comment(line_num - 1),
                is_exported=name[0].isupper(),
            )
            element.signature = f"const {name}"
            
            self.elements.append(element)
        
        # Find var declarations
        var_pattern = re.compile(
            r'^var\s+(\w+)\s+(\S+)',
            re.MULTILINE
        )
        
        for match in var_pattern.finditer(self.source):
            line_num = self.source[:match.start()].count('\n') + 1
            name = match.group(1)
            var_type = match.group(2)
            
            element = GoElement(
                type='var',
                name=name,
                line=line_num,
                returns=var_type,
                docstring=self.extract_doc_comment(line_num - 1),
                is_exported=name[0].isupper(),
            )
            element.signature = f"var {name} {var_type}"
            
            self.elements.append(element)
        
        return {
            'filepath': self.filepath,
            'language': 'go',
            'package': self.package,
            'elements': [asdict(e) for e in self.elements]
        }


def analyze_file(filepath: str) -> Dict:
    """Analyze a single Go file."""
    path = Path(filepath)
    try:
        source = path.read_text(encoding='utf-8')
        analyzer = GoAnalyzer(source, filepath)
        return analyzer.analyze()
    except Exception as e:
        return {'error': str(e), 'filepath': filepath}


def analyze_directory(dirpath: str) -> List[Dict]:
    """Analyze all Go files in a directory."""
    results = []
    skip_dirs = {'vendor', 'testdata'}
    
    for gofile in Path(dirpath).rglob('*.go'):
        if not any(skip in gofile.parts for skip in skip_dirs):
            if not gofile.name.endswith('_test.go'):  # Skip test files
                results.append(analyze_file(str(gofile)))
    
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_go.py <file_or_dir> [--output file.json]", file=sys.stderr)
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
