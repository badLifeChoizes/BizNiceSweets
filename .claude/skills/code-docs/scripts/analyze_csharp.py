#!/usr/bin/env python3
"""
C# analyzer for documentation extraction.
Handles classes, interfaces, methods, properties, and XML doc comments.
Optimized for .NET and Unity codebases.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class CSharpParam:
    name: str
    type: Optional[str] = None
    default: Optional[str] = None
    is_out: bool = False
    is_ref: bool = False
    is_params: bool = False


@dataclass
class CSharpElement:
    type: str  # class, interface, struct, enum, method, property, field, event
    name: str
    line: int
    signature: str = ""
    docstring: Optional[str] = None
    params: List[Dict] = field(default_factory=list)
    returns: Optional[str] = None
    access: str = "private"  # public, private, protected, internal
    is_static: bool = False
    is_async: bool = False
    is_abstract: bool = False
    is_virtual: bool = False
    is_override: bool = False
    decorators: List[str] = field(default_factory=list)  # Attributes
    extends: Optional[str] = None
    implements: List[str] = field(default_factory=list)
    methods: List[Dict] = field(default_factory=list)
    properties: List[Dict] = field(default_factory=list)


class CSharpAnalyzer:
    def __init__(self, source: str, filepath: str):
        self.source = source
        self.lines = source.split('\n')
        self.filepath = filepath
        self.elements: List[CSharpElement] = []
        self.current_class: Optional[CSharpElement] = None
        self.namespace = ""
    
    def extract_xml_doc(self, end_line: int) -> Optional[str]:
        """Extract XML documentation comment preceding a line."""
        doc_lines = []
        
        # Look backwards for /// comments
        for i in range(end_line - 1, max(0, end_line - 50), -1):
            line = self.lines[i].strip()
            
            if line.startswith('///'):
                # Extract content after ///
                content = line[3:].strip()
                doc_lines.insert(0, content)
            elif line.startswith('[') and line.endswith(']'):
                # Skip attributes
                continue
            elif line == '' or line.startswith('//'):
                # Skip empty lines and regular comments
                if doc_lines:  # But stop if we already have doc lines
                    break
                continue
            else:
                # Hit actual code
                break
        
        if not doc_lines:
            return None
        
        # Parse XML doc to extract meaningful content
        full_doc = '\n'.join(doc_lines)
        
        # Extract summary
        summary_match = re.search(r'<summary>(.*?)</summary>', full_doc, re.DOTALL)
        summary = summary_match.group(1).strip() if summary_match else ""
        
        # Extract param descriptions
        params = {}
        for match in re.finditer(r'<param name="(\w+)">(.*?)</param>', full_doc, re.DOTALL):
            params[match.group(1)] = match.group(2).strip()
        
        # Extract returns
        returns_match = re.search(r'<returns>(.*?)</returns>', full_doc, re.DOTALL)
        returns = returns_match.group(1).strip() if returns_match else ""
        
        # Build readable docstring
        result_parts = []
        if summary:
            result_parts.append(summary)
        if params:
            result_parts.append("\nParameters:")
            for name, desc in params.items():
                result_parts.append(f"  {name}: {desc}")
        if returns:
            result_parts.append(f"\nReturns: {returns}")
        
        return '\n'.join(result_parts) if result_parts else full_doc
    
    def extract_attributes(self, end_line: int) -> List[str]:
        """Extract attributes (decorators) preceding a line."""
        attributes = []
        
        for i in range(end_line - 1, max(0, end_line - 20), -1):
            line = self.lines[i].strip()
            
            # Match [Attribute] or [Attribute(params)]
            for match in re.finditer(r'\[(\w+)(?:\([^)]*\))?\]', line):
                attributes.insert(0, match.group(1))
            
            if not line.startswith('[') and not line.startswith('///') and line:
                break
        
        return attributes
    
    def parse_params(self, params_str: str) -> List[Dict]:
        """Parse method parameters."""
        if not params_str.strip():
            return []
        
        params = []
        depth = 0
        current = ""
        
        for char in params_str:
            if char in '<([':
                depth += 1
            elif char in '>)]':
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
    
    def _parse_single_param(self, param: str) -> Dict:
        """Parse a single parameter."""
        result = {
            'name': '',
            'type': None,
            'default': None,
            'is_out': False,
            'is_ref': False,
            'is_params': False,
        }
        
        # Check modifiers
        if param.startswith('out '):
            result['is_out'] = True
            param = param[4:]
        elif param.startswith('ref '):
            result['is_ref'] = True
            param = param[4:]
        elif param.startswith('params '):
            result['is_params'] = True
            param = param[7:]
        elif param.startswith('in '):
            param = param[3:]
        
        # Check for default value
        if '=' in param:
            param, default = param.rsplit('=', 1)
            result['default'] = default.strip()
            param = param.strip()
        
        # Split type and name (type is everything except last word)
        parts = param.rsplit(None, 1)
        if len(parts) == 2:
            result['type'] = parts[0].strip()
            result['name'] = parts[1].strip()
        else:
            result['name'] = param.strip()
        
        return result
    
    def parse_access(self, modifiers: str) -> str:
        """Parse access modifier."""
        if 'public' in modifiers:
            return 'public'
        elif 'protected' in modifiers:
            return 'protected'
        elif 'internal' in modifiers:
            return 'internal'
        elif 'private' in modifiers:
            return 'private'
        return 'private'  # Default
    
    def analyze(self) -> Dict:
        """Analyze the source file."""
        
        # Extract namespace
        ns_match = re.search(r'namespace\s+([\w.]+)', self.source)
        if ns_match:
            self.namespace = ns_match.group(1)
        
        # Find classes, interfaces, structs
        type_pattern = re.compile(
            r'^(\s*)'  # indentation
            r'((?:public|private|protected|internal|static|abstract|sealed|partial)\s+)*'  # modifiers
            r'(class|interface|struct|enum)\s+'  # type keyword
            r'(\w+)'  # name
            r'(?:<[^>]+>)?'  # generic params
            r'(?:\s*:\s*([^{]+))?'  # inheritance
            r'\s*\{',  # opening brace
            re.MULTILINE
        )
        
        for match in type_pattern.finditer(self.source):
            line_num = self.source[:match.start()].count('\n') + 1
            modifiers = match.group(2) or ''
            type_kind = match.group(3)
            name = match.group(4)
            inheritance = match.group(5)
            
            extends = None
            implements = []
            
            if inheritance:
                parts = [p.strip() for p in inheritance.split(',')]
                for i, part in enumerate(parts):
                    if i == 0 and type_kind == 'class':
                        # First could be base class (not starting with I)
                        if not part.startswith('I') or part in ('IDisposable',):
                            extends = part
                        else:
                            implements.append(part)
                    else:
                        implements.append(part)
            
            element = CSharpElement(
                type=type_kind,
                name=name,
                line=line_num,
                docstring=self.extract_xml_doc(line_num - 1),
                access=self.parse_access(modifiers),
                is_static='static' in modifiers,
                is_abstract='abstract' in modifiers,
                decorators=self.extract_attributes(line_num - 1),
                extends=extends,
                implements=implements,
            )
            
            # Build signature
            sig_parts = []
            if element.access:
                sig_parts.append(element.access)
            if element.is_abstract:
                sig_parts.append('abstract')
            if element.is_static:
                sig_parts.append('static')
            sig_parts.extend([type_kind, name])
            if extends:
                sig_parts.append(f': {extends}')
            element.signature = ' '.join(sig_parts)
            
            self.elements.append(element)
        
        # Find methods and properties (simplified - not tracking class context)
        method_pattern = re.compile(
            r'^(\s+)'  # indentation (methods are inside classes)
            r'((?:public|private|protected|internal|static|virtual|override|abstract|async|sealed)\s+)*'
            r'([\w<>\[\],\s\?]+)\s+'  # return type
            r'(\w+)\s*'  # method name
            r'\(([^)]*)\)\s*'  # parameters
            r'(?:where\s+[^{]+)?'  # generic constraints
            r'[{;]',  # body or abstract
            re.MULTILINE
        )
        
        for match in method_pattern.finditer(self.source):
            line_num = self.source[:match.start()].count('\n') + 1
            modifiers = match.group(2) or ''
            return_type = match.group(3).strip()
            name = match.group(4)
            params_str = match.group(5)
            
            # Skip constructors (name matches a class name we found)
            if any(e.name == name for e in self.elements if e.type in ('class', 'struct')):
                # It's a constructor
                element = CSharpElement(
                    type='constructor',
                    name=name,
                    line=line_num,
                    params=self.parse_params(params_str),
                    docstring=self.extract_xml_doc(line_num - 1),
                    access=self.parse_access(modifiers),
                    is_static='static' in modifiers,
                    decorators=self.extract_attributes(line_num - 1),
                )
            else:
                # Regular method
                element = CSharpElement(
                    type='method',
                    name=name,
                    line=line_num,
                    params=self.parse_params(params_str),
                    returns=return_type,
                    docstring=self.extract_xml_doc(line_num - 1),
                    access=self.parse_access(modifiers),
                    is_static='static' in modifiers,
                    is_async='async' in modifiers,
                    is_virtual='virtual' in modifiers,
                    is_override='override' in modifiers,
                    is_abstract='abstract' in modifiers,
                    decorators=self.extract_attributes(line_num - 1),
                )
            
            # Build signature
            param_strs = []
            for p in element.params:
                s = ""
                if p.get('is_out'):
                    s += "out "
                if p.get('is_ref'):
                    s += "ref "
                if p.get('is_params'):
                    s += "params "
                if p.get('type'):
                    s += p['type'] + " "
                s += p['name']
                if p.get('default'):
                    s += f" = {p['default']}"
                param_strs.append(s)
            
            sig = f"{element.access} "
            if element.is_static:
                sig += "static "
            if element.is_async:
                sig += "async "
            if element.is_virtual:
                sig += "virtual "
            if element.is_override:
                sig += "override "
            if element.returns:
                sig += f"{element.returns} "
            sig += f"{name}({', '.join(param_strs)})"
            element.signature = sig.strip()
            
            self.elements.append(element)
        
        # Find properties
        prop_pattern = re.compile(
            r'^(\s+)'
            r'((?:public|private|protected|internal|static|virtual|override|abstract)\s+)*'
            r'([\w<>\[\],\s\?]+)\s+'  # type
            r'(\w+)\s*'  # name
            r'\{\s*(?:get|set)',  # property accessor
            re.MULTILINE
        )
        
        for match in prop_pattern.finditer(self.source):
            line_num = self.source[:match.start()].count('\n') + 1
            modifiers = match.group(2) or ''
            prop_type = match.group(3).strip()
            name = match.group(4)
            
            element = CSharpElement(
                type='property',
                name=name,
                line=line_num,
                returns=prop_type,
                docstring=self.extract_xml_doc(line_num - 1),
                access=self.parse_access(modifiers),
                is_static='static' in modifiers,
                decorators=self.extract_attributes(line_num - 1),
            )
            element.signature = f"{element.access} {prop_type} {name} {{ get; set; }}"
            
            self.elements.append(element)
        
        return {
            'filepath': self.filepath,
            'language': 'csharp',
            'namespace': self.namespace,
            'elements': [asdict(e) for e in self.elements]
        }


def analyze_file(filepath: str) -> Dict:
    """Analyze a single C# file."""
    path = Path(filepath)
    try:
        source = path.read_text(encoding='utf-8-sig')  # Handle BOM
        analyzer = CSharpAnalyzer(source, filepath)
        return analyzer.analyze()
    except Exception as e:
        return {'error': str(e), 'filepath': filepath}


def analyze_directory(dirpath: str) -> List[Dict]:
    """Analyze all C# files in a directory."""
    results = []
    skip_dirs = {'bin', 'obj', '.vs', 'packages', 'TestResults'}
    
    for csfile in Path(dirpath).rglob('*.cs'):
        if not any(skip in csfile.parts for skip in skip_dirs):
            results.append(analyze_file(str(csfile)))
    
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_csharp.py <file_or_dir> [--output file.json]", file=sys.stderr)
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
