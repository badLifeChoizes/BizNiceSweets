#!/usr/bin/env python3
"""
Dependency Graph Builder
Traces imports between modules to build a dependency graph.
Identifies entry points, core modules, and circular dependencies.
"""

import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple


class DependencyGraph:
    """Build and analyze module dependency graph."""
    
    def __init__(self, root: Path):
        self.root = root
        self.nodes: Dict[str, Dict] = {}  # module -> info
        self.edges: List[Tuple[str, str]] = []  # (from, to)
        self.reverse_edges: Dict[str, List[str]] = defaultdict(list)  # module -> dependents
    
    def add_module(self, module: str, filepath: str, language: str):
        """Add a module node."""
        self.nodes[module] = {
            'file': filepath,
            'language': language,
            'imports': [],
            'imported_by': [],
        }
    
    def add_dependency(self, from_module: str, to_module: str):
        """Add a dependency edge."""
        self.edges.append((from_module, to_module))
        if from_module in self.nodes:
            self.nodes[from_module]['imports'].append(to_module)
        if to_module in self.nodes:
            self.nodes[to_module]['imported_by'].append(from_module)
        self.reverse_edges[to_module].append(from_module)
    
    def find_entry_points(self) -> List[str]:
        """Find modules with no dependents (entry points)."""
        all_modules = set(self.nodes.keys())
        imported_modules = set(to_mod for _, to_mod in self.edges)
        
        entry_points = []
        for module in all_modules:
            # Entry points: not imported by any other internal module
            if module not in imported_modules:
                entry_points.append(module)
        
        # Also check for main/index patterns
        for module in all_modules:
            if any(x in module.lower() for x in ['main', 'index', 'app', '__main__']):
                if module not in entry_points:
                    entry_points.append(module)
        
        return entry_points
    
    def find_core_modules(self) -> List[str]:
        """Find most-imported modules (core/shared modules)."""
        import_counts = defaultdict(int)
        
        for _, to_module in self.edges:
            if to_module in self.nodes:  # Only internal modules
                import_counts[to_module] += 1
        
        # Sort by import count
        sorted_modules = sorted(import_counts.items(), key=lambda x: -x[1])
        
        # Return top modules (imported by 3+ others)
        return [mod for mod, count in sorted_modules if count >= 3][:10]
    
    def find_circular_dependencies(self) -> List[List[str]]:
        """Find circular dependencies using DFS."""
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(node: str, path: List[str]):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for _, to_node in self.edges:
                if _ != node:
                    continue
                if to_node not in self.nodes:
                    continue
                
                if to_node not in visited:
                    dfs(to_node, path.copy())
                elif to_node in rec_stack:
                    # Found cycle
                    cycle_start = path.index(to_node)
                    cycle = path[cycle_start:] + [to_node]
                    if cycle not in cycles:
                        cycles.append(cycle)
            
            rec_stack.remove(node)
        
        for node in self.nodes:
            if node not in visited:
                dfs(node, [])
        
        return cycles[:10]  # Limit
    
    def get_module_layers(self) -> Dict[str, int]:
        """Assign layers to modules based on dependency depth."""
        layers = {}
        
        # Start with entry points at layer 0
        entry_points = self.find_entry_points()
        for ep in entry_points:
            layers[ep] = 0
        
        # BFS to assign layers
        queue = list(entry_points)
        while queue:
            current = queue.pop(0)
            current_layer = layers.get(current, 0)
            
            for from_mod, to_mod in self.edges:
                if from_mod == current and to_mod in self.nodes:
                    if to_mod not in layers:
                        layers[to_mod] = current_layer + 1
                        queue.append(to_mod)
        
        return layers
    
    def to_dict(self) -> Dict:
        """Export graph as dictionary."""
        return {
            'modules': list(self.nodes.keys()),
            'module_count': len(self.nodes),
            'edge_count': len(self.edges),
            'nodes': self.nodes,
            'entry_points': self.find_entry_points(),
            'core_modules': self.find_core_modules(),
            'circular_dependencies': self.find_circular_dependencies(),
            'layers': self.get_module_layers(),
        }


def extract_python_imports(filepath: Path, root: Path) -> List[str]:
    """Extract imports from Python file."""
    try:
        source = filepath.read_text(encoding='utf-8')
        tree = ast.parse(source)
    except:
        return []
    
    imports = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                if node.level > 0:
                    # Relative import - resolve to absolute
                    parts = filepath.relative_to(root).parts[:-1]
                    base = '.'.join(parts)
                    if base:
                        imports.append(f"{base}.{node.module}")
                    else:
                        imports.append(node.module)
                else:
                    imports.append(node.module)
    
    return imports


def extract_js_imports(filepath: Path, root: Path) -> List[str]:
    """Extract imports from JavaScript/TypeScript file."""
    try:
        source = filepath.read_text(encoding='utf-8')
    except:
        return []
    
    imports = []
    
    # ES6 imports
    for match in re.finditer(r"(?:import|export).*?from\s+['\"]([^'\"]+)['\"]", source):
        imp = match.group(1)
        if imp.startswith('.'):
            # Relative import - resolve
            imp_path = (filepath.parent / imp).resolve()
            try:
                rel = imp_path.relative_to(root)
                imports.append(str(rel).replace('/', '.').replace('\\', '.'))
            except ValueError:
                imports.append(imp)
        else:
            imports.append(imp)
    
    # require()
    for match in re.finditer(r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", source):
        imports.append(match.group(1))
    
    return imports


def extract_go_imports(filepath: Path) -> List[str]:
    """Extract imports from Go file."""
    try:
        source = filepath.read_text(encoding='utf-8')
    except:
        return []
    
    imports = []
    
    # Single import
    for match in re.finditer(r'import\s+["\']([^"\']+)["\']', source):
        imports.append(match.group(1))
    
    # Import block
    import_block = re.search(r'import\s*\((.*?)\)', source, re.DOTALL)
    if import_block:
        for match in re.finditer(r'["\']([^"\']+)["\']', import_block.group(1)):
            imports.append(match.group(1))
    
    return imports


def extract_csharp_imports(filepath: Path) -> List[str]:
    """Extract using statements from C# file."""
    try:
        source = filepath.read_text(encoding='utf-8')
    except:
        return []
    
    imports = []
    
    for match in re.finditer(r'using\s+([\w.]+)\s*;', source):
        imports.append(match.group(1))
    
    return imports


def build_dependency_graph(project_path: str) -> Dict:
    """Build dependency graph for project."""
    root = Path(project_path).resolve()
    graph = DependencyGraph(root)
    
    skip_dirs = {'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build', '.git', 'vendor', 'target'}
    
    # First pass: collect all modules
    module_files = {}  # normalized_path -> filepath
    
    for filepath in root.rglob('*'):
        if any(skip in filepath.parts for skip in skip_dirs):
            continue
        if not filepath.is_file():
            continue
        
        suffix = filepath.suffix.lower()
        
        if suffix in ('.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.cs'):
            rel_path = filepath.relative_to(root)
            module_name = str(rel_path.with_suffix('')).replace('/', '.').replace('\\', '.')
            
            lang = {
                '.py': 'python',
                '.js': 'javascript', '.jsx': 'javascript',
                '.ts': 'typescript', '.tsx': 'typescript',
                '.go': 'go',
                '.cs': 'csharp',
            }.get(suffix, 'unknown')
            
            graph.add_module(module_name, str(rel_path), lang)
            module_files[module_name] = filepath
    
    # Second pass: extract imports and build edges
    for module_name, filepath in module_files.items():
        suffix = filepath.suffix.lower()
        imports = []
        
        if suffix == '.py':
            imports = extract_python_imports(filepath, root)
        elif suffix in ('.js', '.ts', '.jsx', '.tsx'):
            imports = extract_js_imports(filepath, root)
        elif suffix == '.go':
            imports = extract_go_imports(filepath)
        elif suffix == '.cs':
            imports = extract_csharp_imports(filepath)
        
        for imp in imports:
            # Normalize import to match module names
            imp_normalized = imp.replace('/', '.').replace('\\', '.')
            
            # Check if it's an internal import
            for existing_module in graph.nodes:
                if existing_module == imp_normalized or existing_module.endswith('.' + imp_normalized):
                    graph.add_dependency(module_name, existing_module)
                    break
    
    return graph.to_dict()


def format_graph(graph: Dict) -> str:
    """Format dependency graph as readable text."""
    lines = [
        "═══ Dependency Graph ═══",
        "",
        f"Modules: {graph['module_count']}",
        f"Dependencies: {graph['edge_count']}",
        "",
    ]
    
    if graph['entry_points']:
        lines.append("Entry Points:")
        for ep in graph['entry_points'][:10]:
            lines.append(f"  → {ep}")
        lines.append("")
    
    if graph['core_modules']:
        lines.append("Core Modules (most imported):")
        for cm in graph['core_modules']:
            count = len(graph['nodes'].get(cm, {}).get('imported_by', []))
            lines.append(f"  ★ {cm} (imported by {count} modules)")
        lines.append("")
    
    if graph['circular_dependencies']:
        lines.append("⚠️  Circular Dependencies:")
        for cycle in graph['circular_dependencies']:
            lines.append(f"  • {' → '.join(cycle)}")
        lines.append("")
    
    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: build_graph.py <project_path> [--output file.json] [--format text|json]", file=sys.stderr)
        sys.exit(1)
    
    project_path = sys.argv[1]
    output_file = None
    output_format = 'text'
    
    if '--output' in sys.argv:
        output_file = sys.argv[sys.argv.index('--output') + 1]
    if '--format' in sys.argv:
        output_format = sys.argv[sys.argv.index('--format') + 1]
    
    graph = build_dependency_graph(project_path)
    
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(graph, f, indent=2)
        print(f"Graph written to {output_file}")
    elif output_format == 'json':
        print(json.dumps(graph, indent=2))
    else:
        print(format_graph(graph))


if __name__ == "__main__":
    main()
