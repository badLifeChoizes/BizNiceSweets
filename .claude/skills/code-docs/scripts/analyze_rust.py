#!/usr/bin/env python3
"""
Rust analyzer for documentation extraction.
Handles functions, structs, enums, traits, impls, and doc comments.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class RustElement:
    type: str  # fn, struct, enum, trait, impl, mod, const, type, macro
    name: str
    line: int
    signature: str = ""
    docstring: Optional[str] = None
    params: List[Dict] = field(default_factory=list)
    returns: Optional[str] = None
    is_pub: bool = False
    is_async: bool = False
    is_unsafe: bool = False
    generics: Optional[str] = None
    attributes: List[str] = field(default_factory=list)
    trait_impl: Optional[str] = None  # For impl blocks
    methods: List[Dict] = field(default_factory=list)


class RustAnalyzer:
    def __init__(self, source: str, filepath: str):
        self.source = source
        self.lines = source.split('\n')
        self.filepath = filepath
        self.elements: List[RustElement] = []
    
    def extract_doc_comment(self, end_line: int) -> Optional[str]:
        """Extract Rust doc comment (/// or //!) preceding a line."""
        doc_lines = []
        
        for i in range(end_line - 1, max(0, end_line - 100), -1):
            line = self.lines[i].strip()
            
            if line.startswith('///') or line.startswith('//!'):
                # Doc comment
                content = line[3:].strip()
                doc_lines.insert(0, content)
            elif line.startswith('#['):
                # Attribute - skip but continue
                continue
            elif line == '':
                # Empty line - continue looking
                continue
            else:
                # Hit code
                break
        
        return '\n'.join(doc_lines) if doc_lines else None
    
    def extract_attributes(self, end_line: int) -> List[str]:
        """Extract #[attr] attributes preceding a line."""
        attributes = []
        
        for i in range(end_line - 1, max(0, end_line - 20), -1):
            line = self.lines[i].strip()
            
            if line.startswith('#['):
                match = re.match(r'#\[([^\]]+)\]', line)
                if match:
                    attributes.insert(0, match.group(1))
            elif line.startswith('///') or line.startswith('//!') or line == '':
                continue
            else:
                break
        
        return attributes
    
    def parse_params(self, params_str: str) -> List[Dict]:
        """Parse Rust function parameters."""
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
    
    def _parse_single_param(self, param: str) -> Dict:
        """Parse a single Rust parameter."""
        result = {'name': '', 'type': None, 'is_mut': False, 'is_ref': False}
        
        # Handle self
        if param in ('self', '&self', '&mut self', 'mut self'):
            result['name'] = 'self'
            if '&mut' in param:
                result['is_ref'] = True
                result['is_mut'] = True
            elif '&' in param:
                result['is_ref'] = True
            elif 'mut' in param:
                result['is_mut'] = True
            return result
        
        # Handle pattern: name: type
        if ':' in param:
            name_part, type_part = param.split(':', 1)
            name_part = name_part.strip()
            type_part = type_part.strip()
            
            # Check for mut
            if name_part.startswith('mut '):
                result['is_mut'] = True
                name_part = name_part[4:]
            
            result['name'] = name_part
            result['type'] = type_part
        else:
            result['name'] = param
        
        return result
    
    def analyze(self) -> Dict:
        """Analyze the source file."""
        
        # Find functions
        fn_pattern = re.compile(
            r'^(\s*)'
            r'(pub(?:\([^)]+\))?\s+)?'  # visibility
            r'(const\s+|async\s+|unsafe\s+)*'  # modifiers
            r'fn\s+'
            r'(\w+)'  # name
            r'(<[^>]+>)?'  # generics
            r'\s*\(([^)]*)\)'  # params
            r'(?:\s*->\s*([^{;]+?))?'  # return type
            r'\s*(?:where[^{]*)?'  # where clause
            r'[{;]',
            re.MULTILINE
        )
        
        for match in fn_pattern.finditer(self.source):
            line_num = self.source[:match.start()].count('\n') + 1
            vis = match.group(2)
            modifiers = match.group(3) or ''
            name = match.group(4)
            generics = match.group(5)
            params_str = match.group(6)
            returns = match.group(7)
            
            element = RustElement(
                type='fn',
                name=name,
                line=line_num,
                params=self.parse_params(params_str),
                returns=returns.strip() if returns else None,
                is_pub=vis is not None,
                is_async='async' in modifiers,
                is_unsafe='unsafe' in modifiers,
                generics=generics,
                docstring=self.extract_doc_comment(line_num - 1),
                attributes=self.extract_attributes(line_num - 1),
            )
            
            # Build signature
            sig = ""
            if element.is_pub:
                sig += "pub "
            if element.is_async:
                sig += "async "
            if element.is_unsafe:
                sig += "unsafe "
            sig += f"fn {name}"
            if generics:
                sig += generics
            sig += f"({params_str})"
            if returns:
                sig += f" -> {returns.strip()}"
            element.signature = sig
            
            self.elements.append(element)
        
        # Find structs
        struct_pattern = re.compile(
            r'^(\s*)(pub(?:\([^)]+\))?\s+)?struct\s+(\w+)(<[^>]+>)?',
            re.MULTILINE
        )
        
        for match in struct_pattern.finditer(self.source):
            line_num = self.source[:match.start()].count('\n') + 1
            vis = match.group(2)
            name = match.group(3)
            generics = match.group(4)
            
            element = RustElement(
                type='struct',
                name=name,
                line=line_num,
                is_pub=vis is not None,
                generics=generics,
                docstring=self.extract_doc_comment(line_num - 1),
                attributes=self.extract_attributes(line_num - 1),
            )
            sig = "pub " if element.is_pub else ""
            sig += f"struct {name}"
            if generics:
                sig += generics
            element.signature = sig
            
            self.elements.append(element)
        
        # Find enums
        enum_pattern = re.compile(
            r'^(\s*)(pub(?:\([^)]+\))?\s+)?enum\s+(\w+)(<[^>]+>)?',
            re.MULTILINE
        )
        
        for match in enum_pattern.finditer(self.source):
            line_num = self.source[:match.start()].count('\n') + 1
            vis = match.group(2)
            name = match.group(3)
            generics = match.group(4)
            
            element = RustElement(
                type='enum',
                name=name,
                line=line_num,
                is_pub=vis is not None,
                generics=generics,
                docstring=self.extract_doc_comment(line_num - 1),
                attributes=self.extract_attributes(line_num - 1),
            )
            sig = "pub " if element.is_pub else ""
            sig += f"enum {name}"
            if generics:
                sig += generics
            element.signature = sig
            
            self.elements.append(element)
        
        # Find traits
        trait_pattern = re.compile(
            r'^(\s*)(pub(?:\([^)]+\))?\s+)?trait\s+(\w+)(<[^>]+>)?',
            re.MULTILINE
        )
        
        for match in trait_pattern.finditer(self.source):
            line_num = self.source[:match.start()].count('\n') + 1
            vis = match.group(2)
            name = match.group(3)
            generics = match.group(4)
            
            element = RustElement(
                type='trait',
                name=name,
                line=line_num,
                is_pub=vis is not None,
                generics=generics,
                docstring=self.extract_doc_comment(line_num - 1),
                attributes=self.extract_attributes(line_num - 1),
            )
            sig = "pub " if element.is_pub else ""
            sig += f"trait {name}"
            if generics:
                sig += generics
            element.signature = sig
            
            self.elements.append(element)
        
        # Find impl blocks
        impl_pattern = re.compile(
            r'^impl(<[^>]+>)?\s+(?:(\w+)(<[^>]+>)?\s+for\s+)?(\w+)(<[^>]+>)?',
            re.MULTILINE
        )
        
        for match in impl_pattern.finditer(self.source):
            line_num = self.source[:match.start()].count('\n') + 1
            impl_generics = match.group(1)
            trait_name = match.group(2)
            type_name = match.group(4)
            
            element = RustElement(
                type='impl',
                name=type_name,
                line=line_num,
                trait_impl=trait_name,
                generics=impl_generics,
                docstring=self.extract_doc_comment(line_num - 1),
            )
            
            if trait_name:
                element.signature = f"impl {trait_name} for {type_name}"
            else:
                element.signature = f"impl {type_name}"
            
            self.elements.append(element)
        
        # Find type aliases
        type_pattern = re.compile(
            r'^(\s*)(pub(?:\([^)]+\))?\s+)?type\s+(\w+)(<[^>]+>)?\s*=\s*([^;]+)',
            re.MULTILINE
        )
        
        for match in type_pattern.finditer(self.source):
            line_num = self.source[:match.start()].count('\n') + 1
            vis = match.group(2)
            name = match.group(3)
            generics = match.group(4)
            aliased = match.group(5).strip()
            
            element = RustElement(
                type='type',
                name=name,
                line=line_num,
                is_pub=vis is not None,
                generics=generics,
                returns=aliased,
                docstring=self.extract_doc_comment(line_num - 1),
            )
            sig = "pub " if element.is_pub else ""
            sig += f"type {name} = {aliased}"
            element.signature = sig
            
            self.elements.append(element)
        
        return {
            'filepath': self.filepath,
            'language': 'rust',
            'elements': [asdict(e) for e in self.elements]
        }


def analyze_file(filepath: str) -> Dict:
    """Analyze a single Rust file."""
    path = Path(filepath)
    try:
        source = path.read_text(encoding='utf-8')
        analyzer = RustAnalyzer(source, filepath)
        return analyzer.analyze()
    except Exception as e:
        return {'error': str(e), 'filepath': filepath}


def analyze_directory(dirpath: str) -> List[Dict]:
    """Analyze all Rust files in a directory."""
    results = []
    skip_dirs = {'target', 'tests'}
    
    for rsfile in Path(dirpath).rglob('*.rs'):
        if not any(skip in rsfile.parts for skip in skip_dirs):
            results.append(analyze_file(str(rsfile)))
    
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_rust.py <file_or_dir> [--output file.json]", file=sys.stderr)
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
