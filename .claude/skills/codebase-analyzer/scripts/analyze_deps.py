#!/usr/bin/env python3
"""
Dependencies Analyzer v2
Parses many more config file formats with confidence tagging.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DETECTED = "detected"
INFERRED = "inferred"


def parse_package_json(filepath: Path) -> Dict:
    """Parse Node.js package.json."""
    try:
        with open(filepath) as f:
            data = json.load(f)
        
        # Detect frameworks
        all_deps = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
        frameworks = []
        
        framework_indicators = {
            'react': 'React',
            'vue': 'Vue',
            'angular': 'Angular',
            '@angular/core': 'Angular',
            'svelte': 'Svelte',
            'next': 'Next.js',
            'nuxt': 'Nuxt',
            'gatsby': 'Gatsby',
            'express': 'Express',
            'fastify': 'Fastify',
            'koa': 'Koa',
            'nestjs': 'NestJS',
            '@nestjs/core': 'NestJS',
            'electron': 'Electron',
            'react-native': 'React Native',
        }
        
        for dep, name in framework_indicators.items():
            if dep in all_deps:
                frameworks.append(name)
        
        return {
            'file': str(filepath),
            'type': 'npm',
            'confidence': DETECTED,
            'name': data.get('name', ''),
            'version': data.get('version', ''),
            'description': data.get('description', ''),
            'main': data.get('main', ''),
            'scripts': data.get('scripts', {}),
            'dependencies': data.get('dependencies', {}),
            'dev_dependencies': data.get('devDependencies', {}),
            'peer_dependencies': data.get('peerDependencies', {}),
            'engines': data.get('engines', {}),
            'workspaces': data.get('workspaces', []),
            'detected_frameworks': frameworks,
            'is_monorepo': bool(data.get('workspaces')),
        }
    except Exception as e:
        return {'file': str(filepath), 'error': str(e)}


def parse_requirements_txt(filepath: Path) -> Dict:
    """Parse Python requirements.txt."""
    deps = []
    try:
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('-'):
                    continue
                
                match = re.match(r'^([a-zA-Z0-9_-]+)(.*)$', line)
                if match:
                    deps.append({
                        'name': match.group(1),
                        'version_spec': match.group(2).strip() or '*'
                    })
        
        return {
            'file': str(filepath),
            'type': 'pip',
            'confidence': DETECTED,
            'dependencies': deps
        }
    except Exception as e:
        return {'file': str(filepath), 'error': str(e)}


def parse_pyproject_toml(filepath: Path) -> Dict:
    """Parse Python pyproject.toml (PEP 621 and Poetry)."""
    try:
        content = filepath.read_text()
        result = {
            'file': str(filepath),
            'type': 'pyproject',
            'confidence': DETECTED,
            'name': '',
            'version': '',
            'dependencies': [],
            'dev_dependencies': [],
            'build_system': '',
            'detected_frameworks': [],
        }
        
        # Try to use tomllib (Python 3.11+) or fallback to regex
        try:
            import tomllib
            data = tomllib.loads(content)
            
            # PEP 621 format
            project = data.get('project', {})
            result['name'] = project.get('name', '')
            result['version'] = project.get('version', '')
            result['dependencies'] = project.get('dependencies', [])
            
            # Poetry format
            poetry = data.get('tool', {}).get('poetry', {})
            if poetry:
                result['name'] = result['name'] or poetry.get('name', '')
                result['version'] = result['version'] or poetry.get('version', '')
                if poetry.get('dependencies'):
                    result['dependencies'] = list(poetry['dependencies'].keys())
                if poetry.get('dev-dependencies'):
                    result['dev_dependencies'] = list(poetry['dev-dependencies'].keys())
            
            # Build system
            result['build_system'] = data.get('build-system', {}).get('build-backend', '')
            
        except ImportError:
            # Fallback to regex parsing
            match = re.search(r'^\s*name\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            if match:
                result['name'] = match.group(1)
            
            match = re.search(r'^\s*version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
            if match:
                result['version'] = match.group(1)
            
            # Extract dependencies
            for match in re.finditer(r'["\']([a-zA-Z0-9_-]+)["\']', content):
                dep = match.group(1)
                if dep not in result['dependencies']:
                    result['dependencies'].append(dep)
        
        # Detect frameworks
        all_deps = ' '.join(str(d) for d in result['dependencies'] + result['dev_dependencies']).lower()
        
        if 'django' in all_deps:
            result['detected_frameworks'].append('Django')
        if 'flask' in all_deps:
            result['detected_frameworks'].append('Flask')
        if 'fastapi' in all_deps:
            result['detected_frameworks'].append('FastAPI')
        if 'pytorch' in all_deps or 'torch' in all_deps:
            result['detected_frameworks'].append('PyTorch')
        if 'tensorflow' in all_deps:
            result['detected_frameworks'].append('TensorFlow')
        
        return result
    except Exception as e:
        return {'file': str(filepath), 'error': str(e)}


def parse_pipfile(filepath: Path) -> Dict:
    """Parse Pipfile."""
    try:
        content = filepath.read_text()
        result = {
            'file': str(filepath),
            'type': 'pipfile',
            'confidence': DETECTED,
            'dependencies': [],
            'dev_dependencies': [],
            'python_version': '',
        }
        
        current_section = None
        for line in content.split('\n'):
            line = line.strip()
            
            if line == '[packages]':
                current_section = 'packages'
            elif line == '[dev-packages]':
                current_section = 'dev'
            elif line == '[requires]':
                current_section = 'requires'
            elif line.startswith('['):
                current_section = None
            elif '=' in line and current_section:
                name = line.split('=')[0].strip().strip('"\'')
                if current_section == 'packages':
                    result['dependencies'].append(name)
                elif current_section == 'dev':
                    result['dev_dependencies'].append(name)
                elif current_section == 'requires' and 'python_version' in line:
                    match = re.search(r'["\']([^"\']+)["\']', line)
                    if match:
                        result['python_version'] = match.group(1)
        
        return result
    except Exception as e:
        return {'file': str(filepath), 'error': str(e)}


def parse_cargo_toml(filepath: Path) -> Dict:
    """Parse Rust Cargo.toml."""
    try:
        content = filepath.read_text()
        result = {
            'file': str(filepath),
            'type': 'cargo',
            'confidence': DETECTED,
            'name': '',
            'version': '',
            'dependencies': {},
            'dev_dependencies': {},
            'is_workspace': False,
        }
        
        # Check for workspace
        if '[workspace]' in content:
            result['is_workspace'] = True
            members = re.findall(r'members\s*=\s*\[(.*?)\]', content, re.DOTALL)
            if members:
                result['workspace_members'] = re.findall(r'["\']([^"\']+)["\']', members[0])
        
        # Extract name and version
        match = re.search(r'^\s*name\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if match:
            result['name'] = match.group(1)
        
        match = re.search(r'^\s*version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if match:
            result['version'] = match.group(1)
        
        # Parse dependencies
        current_section = None
        for line in content.split('\n'):
            line = line.strip()
            
            if line == '[dependencies]':
                current_section = 'deps'
            elif line == '[dev-dependencies]':
                current_section = 'dev'
            elif line.startswith('['):
                current_section = None
            elif '=' in line and current_section:
                parts = line.split('=', 1)
                name = parts[0].strip()
                version = parts[1].strip().strip('"\'')
                
                if current_section == 'deps':
                    result['dependencies'][name] = version
                else:
                    result['dev_dependencies'][name] = version
        
        return result
    except Exception as e:
        return {'file': str(filepath), 'error': str(e)}


def parse_go_mod(filepath: Path) -> Dict:
    """Parse Go go.mod."""
    try:
        content = filepath.read_text()
        result = {
            'file': str(filepath),
            'type': 'go',
            'confidence': DETECTED,
            'module': '',
            'go_version': '',
            'dependencies': [],
        }
        
        for line in content.split('\n'):
            line = line.strip()
            
            if line.startswith('module '):
                result['module'] = line[7:].strip()
            elif line.startswith('go '):
                result['go_version'] = line[3:].strip()
            elif line and not line.startswith('//') and not line in ('require (', ')'):
                if line.startswith('require '):
                    line = line[8:]
                parts = line.split()
                if len(parts) >= 2 and '/' in parts[0]:
                    result['dependencies'].append({
                        'name': parts[0],
                        'version': parts[1]
                    })
        
        return result
    except Exception as e:
        return {'file': str(filepath), 'error': str(e)}


def parse_gradle(filepath: Path) -> Dict:
    """Parse build.gradle or build.gradle.kts."""
    try:
        content = filepath.read_text()
        result = {
            'file': str(filepath),
            'type': 'gradle',
            'confidence': DETECTED,
            'dependencies': [],
            'plugins': [],
        }
        
        # Extract dependencies
        for match in re.finditer(r"implementation\s*['\"]([^'\"]+)['\"]", content):
            result['dependencies'].append(match.group(1))
        for match in re.finditer(r"compile\s*['\"]([^'\"]+)['\"]", content):
            result['dependencies'].append(match.group(1))
        
        # Extract plugins
        for match in re.finditer(r"id\s*['\"]([^'\"]+)['\"]", content):
            result['plugins'].append(match.group(1))
        
        return result
    except Exception as e:
        return {'file': str(filepath), 'error': str(e)}


def parse_cmake(filepath: Path) -> Dict:
    """Parse CMakeLists.txt."""
    try:
        content = filepath.read_text()
        result = {
            'file': str(filepath),
            'type': 'cmake',
            'confidence': DETECTED,
            'project_name': '',
            'cmake_minimum': '',
            'dependencies': [],
        }
        
        # Project name
        match = re.search(r'project\s*\(\s*(\w+)', content, re.IGNORECASE)
        if match:
            result['project_name'] = match.group(1)
        
        # CMake version
        match = re.search(r'cmake_minimum_required\s*\(\s*VERSION\s+([\d.]+)', content, re.IGNORECASE)
        if match:
            result['cmake_minimum'] = match.group(1)
        
        # Dependencies (find_package)
        for match in re.finditer(r'find_package\s*\(\s*(\w+)', content, re.IGNORECASE):
            result['dependencies'].append(match.group(1))
        
        return result
    except Exception as e:
        return {'file': str(filepath), 'error': str(e)}


def parse_gemfile(filepath: Path) -> Dict:
    """Parse Ruby Gemfile."""
    try:
        content = filepath.read_text()
        result = {
            'file': str(filepath),
            'type': 'bundler',
            'confidence': DETECTED,
            'ruby_version': '',
            'dependencies': [],
            'detected_frameworks': [],
        }
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Ruby version
            if line.startswith('ruby '):
                match = re.search(r'["\']([^"\']+)["\']', line)
                if match:
                    result['ruby_version'] = match.group(1)
            
            # Gems
            match = re.match(r"gem\s+['\"]([^'\"]+)['\"]", line)
            if match:
                result['dependencies'].append(match.group(1))
        
        # Detect frameworks
        deps_str = ' '.join(result['dependencies']).lower()
        if 'rails' in deps_str:
            result['detected_frameworks'].append('Rails')
        if 'sinatra' in deps_str:
            result['detected_frameworks'].append('Sinatra')
        
        return result
    except Exception as e:
        return {'file': str(filepath), 'error': str(e)}


def parse_composer_json(filepath: Path) -> Dict:
    """Parse PHP composer.json."""
    try:
        with open(filepath) as f:
            data = json.load(f)
        
        result = {
            'file': str(filepath),
            'type': 'composer',
            'confidence': DETECTED,
            'name': data.get('name', ''),
            'dependencies': data.get('require', {}),
            'dev_dependencies': data.get('require-dev', {}),
            'detected_frameworks': [],
        }
        
        # Detect frameworks
        all_deps = ' '.join(result['dependencies'].keys()).lower()
        if 'laravel' in all_deps:
            result['detected_frameworks'].append('Laravel')
        if 'symfony' in all_deps:
            result['detected_frameworks'].append('Symfony')
        
        return result
    except Exception as e:
        return {'file': str(filepath), 'error': str(e)}


def parse_makefile(filepath: Path) -> Dict:
    """Extract targets from Makefile."""
    try:
        content = filepath.read_text()
        targets = []
        
        for line in content.split('\n'):
            match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_-]*)\s*:', line)
            if match and not match.group(1).startswith('.'):
                targets.append(match.group(1))
        
        return {
            'file': str(filepath),
            'type': 'makefile',
            'confidence': DETECTED,
            'targets': targets
        }
    except Exception as e:
        return {'file': str(filepath), 'error': str(e)}


def parse_dockerfile(filepath: Path) -> Dict:
    """Parse Dockerfile for base image and exposed ports."""
    try:
        content = filepath.read_text()
        result = {
            'file': str(filepath),
            'type': 'dockerfile',
            'confidence': DETECTED,
            'base_images': [],
            'exposed_ports': [],
        }
        
        for line in content.split('\n'):
            line = line.strip()
            
            if line.upper().startswith('FROM '):
                image = line[5:].split()[0]
                result['base_images'].append(image)
            
            if line.upper().startswith('EXPOSE '):
                ports = line[7:].split()
                result['exposed_ports'].extend(ports)
        
        return result
    except Exception as e:
        return {'file': str(filepath), 'error': str(e)}


# Config file parsers
CONFIG_PARSERS = {
    'package.json': parse_package_json,
    'requirements.txt': parse_requirements_txt,
    'pyproject.toml': parse_pyproject_toml,
    'Pipfile': parse_pipfile,
    'Cargo.toml': parse_cargo_toml,
    'go.mod': parse_go_mod,
    'build.gradle': parse_gradle,
    'build.gradle.kts': parse_gradle,
    'CMakeLists.txt': parse_cmake,
    'Gemfile': parse_gemfile,
    'composer.json': parse_composer_json,
    'Makefile': parse_makefile,
    'Dockerfile': parse_dockerfile,
}


def analyze_dependencies(project_path: str) -> Dict:
    """Find and parse all dependency/config files."""
    root = Path(project_path).resolve()
    
    result = {
        'root': str(root),
        'configs': [],
        'primary_language': None,
        'frameworks': [],
        'is_monorepo': False,
        'build_systems': [],
    }
    
    # Search for config files (root and one level deep)
    search_paths = [root]
    for d in root.iterdir():
        if d.is_dir() and not d.name.startswith('.') and d.name not in {'node_modules', 'vendor', 'venv'}:
            search_paths.append(d)
    
    for search_dir in search_paths[:20]:  # Limit
        for config_name, parser in CONFIG_PARSERS.items():
            config_path = search_dir / config_name
            if config_path.exists():
                parsed = parser(config_path)
                if 'error' not in parsed:
                    result['configs'].append(parsed)
                    
                    # Collect frameworks
                    for fw in parsed.get('detected_frameworks', []):
                        if fw not in result['frameworks']:
                            result['frameworks'].append(fw)
                    
                    # Check monorepo
                    if parsed.get('is_monorepo') or parsed.get('is_workspace') or parsed.get('workspaces'):
                        result['is_monorepo'] = True
                    
                    # Track build systems
                    if parsed.get('type') not in ['makefile', 'dockerfile']:
                        if parsed.get('type') not in result['build_systems']:
                            result['build_systems'].append(parsed.get('type'))
    
    # Detect primary language
    lang_priority = ['npm', 'pyproject', 'pipfile', 'pip', 'cargo', 'go', 'gradle', 'cmake', 'bundler', 'composer']
    for lang in lang_priority:
        for config in result['configs']:
            if config.get('type') == lang:
                lang_map = {
                    'npm': 'javascript',
                    'pyproject': 'python', 'pipfile': 'python', 'pip': 'python',
                    'cargo': 'rust', 'go': 'go', 'gradle': 'java',
                    'cmake': 'c/cpp', 'bundler': 'ruby', 'composer': 'php'
                }
                result['primary_language'] = lang_map.get(lang, lang)
                break
        if result['primary_language']:
            break
    
    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_deps.py <project_path> [--output file.json]", file=sys.stderr)
        sys.exit(1)
    
    project_path = sys.argv[1]
    output_file = None
    
    if '--output' in sys.argv:
        output_file = sys.argv[sys.argv.index('--output') + 1]
    
    result = analyze_dependencies(project_path)
    
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Dependencies written to {output_file}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
