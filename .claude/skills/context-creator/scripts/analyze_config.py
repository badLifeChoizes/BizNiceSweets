#!/usr/bin/env python3
"""
Configuration and Secrets Analyzer
Detects configuration patterns, environment variables, secrets usage,
and feature flags across multiple languages and frameworks.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set


DETECTED = "detected"
INFERRED = "inferred"
WARNING = "warning"


# ========== Configuration File Patterns ==========

CONFIG_FILES = {
    # Environment files
    '.env': 'dotenv',
    '.env.local': 'dotenv',
    '.env.development': 'dotenv',
    '.env.production': 'dotenv',
    '.env.test': 'dotenv',
    '.env.example': 'dotenv-template',
    '.env.sample': 'dotenv-template',

    # Python
    'settings.py': 'python-settings',
    'config.py': 'python-config',
    'pyproject.toml': 'python-project',

    # JavaScript/TypeScript
    'config.json': 'json-config',
    'config.js': 'js-config',
    'config.ts': 'ts-config',
    '.env.local': 'dotenv',
    'next.config.js': 'nextjs-config',
    'next.config.mjs': 'nextjs-config',
    'nuxt.config.js': 'nuxt-config',
    'nuxt.config.ts': 'nuxt-config',
    'vite.config.js': 'vite-config',
    'vite.config.ts': 'vite-config',

    # Go
    'config.yaml': 'yaml-config',
    'config.yml': 'yaml-config',
    'config.toml': 'toml-config',

    # C#/.NET
    'appsettings.json': 'dotnet-config',
    'appsettings.Development.json': 'dotnet-config',
    'appsettings.Production.json': 'dotnet-config',
    'web.config': 'dotnet-legacy',
    'app.config': 'dotnet-legacy',

    # Java
    'application.properties': 'spring-properties',
    'application.yml': 'spring-yaml',
    'application.yaml': 'spring-yaml',
    'application-dev.properties': 'spring-properties',
    'application-prod.properties': 'spring-properties',

    # Rust
    'Cargo.toml': 'rust-cargo',
    'config.toml': 'toml-config',

    # Docker/Kubernetes
    'docker-compose.yml': 'docker-compose',
    'docker-compose.yaml': 'docker-compose',
    'docker-compose.override.yml': 'docker-compose',
    'kubernetes.yml': 'kubernetes',
    'deployment.yaml': 'kubernetes',
}


# ========== Secret Patterns ==========

SECRET_PATTERNS = [
    # API keys
    (r'(?:api[_-]?key|apikey)\s*[=:]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?', 'api_key'),
    (r'(?:OPENAI|ANTHROPIC|STRIPE|GITHUB|AWS|GOOGLE|AZURE)_(?:API_)?KEY\s*[=:]\s*["\']?([^\s"\']+)["\']?', 'api_key'),

    # Passwords
    (r'(?:password|passwd|pwd)\s*[=:]\s*["\']([^"\']{8,})["\']', 'password'),
    (r'(?:DB_PASSWORD|DATABASE_PASSWORD|MYSQL_PASSWORD|POSTGRES_PASSWORD)\s*[=:]\s*["\']?([^\s"\']+)["\']?', 'database_password'),

    # Tokens
    (r'(?:token|access_token|auth_token|bearer)\s*[=:]\s*["\']?([a-zA-Z0-9_\-\.]{20,})["\']?', 'token'),
    (r'(?:JWT_SECRET|SECRET_KEY|SESSION_SECRET)\s*[=:]\s*["\']?([^\s"\']+)["\']?', 'secret_key'),

    # Connection strings
    (r'(?:connection_string|conn_str|database_url)\s*[=:]\s*["\']([^"\']+)["\']', 'connection_string'),
    (r'(?:mongodb|postgres|mysql|redis)://[^\s"\']+', 'connection_string'),

    # AWS
    (r'AKIA[0-9A-Z]{16}', 'aws_access_key'),
    (r'(?:aws_secret|AWS_SECRET)[_\s]*[=:]\s*["\']?([a-zA-Z0-9/+=]{40})["\']?', 'aws_secret'),

    # Private keys
    (r'-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----', 'private_key'),
    (r'-----BEGIN OPENSSH PRIVATE KEY-----', 'ssh_private_key'),
]


# ========== Environment Variable Patterns by Language ==========

def extract_env_vars_python(source: str) -> List[Dict]:
    """Extract environment variable usage from Python code."""
    env_vars = []

    # os.environ['VAR'] or os.environ.get('VAR')
    for match in re.finditer(r'os\.environ(?:\.get)?\s*\(\s*["\'](\w+)["\'](?:\s*,\s*([^)]+))?\)', source):
        env_vars.append({
            'name': match.group(1),
            'default': match.group(2).strip().strip('"\'') if match.group(2) else None,
            'method': 'os.environ',
            'line': source[:match.start()].count('\n') + 1,
        })

    # os.getenv('VAR')
    for match in re.finditer(r'os\.getenv\s*\(\s*["\'](\w+)["\'](?:\s*,\s*([^)]+))?\)', source):
        env_vars.append({
            'name': match.group(1),
            'default': match.group(2).strip().strip('"\'') if match.group(2) else None,
            'method': 'os.getenv',
            'line': source[:match.start()].count('\n') + 1,
        })

    # python-dotenv: load_dotenv()
    if 'load_dotenv' in source:
        env_vars.append({
            'name': '__DOTENV_LOADED__',
            'method': 'python-dotenv',
            'note': 'Uses python-dotenv for .env loading',
            'line': source.find('load_dotenv'),
        })

    # pydantic settings
    for match in re.finditer(r'class\s+\w+\s*\(\s*BaseSettings\s*\)', source):
        env_vars.append({
            'name': '__PYDANTIC_SETTINGS__',
            'method': 'pydantic',
            'note': 'Uses Pydantic BaseSettings for configuration',
            'line': source[:match.start()].count('\n') + 1,
        })

    return env_vars


def extract_env_vars_js(source: str) -> List[Dict]:
    """Extract environment variable usage from JavaScript/TypeScript."""
    env_vars = []

    # process.env.VAR or process.env['VAR']
    for match in re.finditer(r'process\.env\.(\w+)', source):
        env_vars.append({
            'name': match.group(1),
            'method': 'process.env',
            'line': source[:match.start()].count('\n') + 1,
        })

    for match in re.finditer(r'process\.env\[["\'](\w+)["\']\]', source):
        env_vars.append({
            'name': match.group(1),
            'method': 'process.env',
            'line': source[:match.start()].count('\n') + 1,
        })

    # Vite: import.meta.env.VITE_VAR
    for match in re.finditer(r'import\.meta\.env\.(\w+)', source):
        env_vars.append({
            'name': match.group(1),
            'method': 'import.meta.env',
            'line': source[:match.start()].count('\n') + 1,
        })

    # Next.js: NEXT_PUBLIC_ prefix
    for match in re.finditer(r'(?:process\.env\.|import\.meta\.env\.)(NEXT_PUBLIC_\w+)', source):
        env_vars.append({
            'name': match.group(1),
            'method': 'nextjs-public',
            'public': True,
            'line': source[:match.start()].count('\n') + 1,
        })

    return env_vars


def extract_env_vars_go(source: str) -> List[Dict]:
    """Extract environment variable usage from Go code."""
    env_vars = []

    # os.Getenv("VAR")
    for match in re.finditer(r'os\.Getenv\s*\(\s*["`](\w+)["`]\s*\)', source):
        env_vars.append({
            'name': match.group(1),
            'method': 'os.Getenv',
            'line': source[:match.start()].count('\n') + 1,
        })

    # os.LookupEnv("VAR")
    for match in re.finditer(r'os\.LookupEnv\s*\(\s*["`](\w+)["`]\s*\)', source):
        env_vars.append({
            'name': match.group(1),
            'method': 'os.LookupEnv',
            'line': source[:match.start()].count('\n') + 1,
        })

    # Viper: viper.GetString("key")
    for match in re.finditer(r'viper\.(?:Get|GetString|GetInt|GetBool)\s*\(\s*["`](\w+)["`]\s*\)', source):
        env_vars.append({
            'name': match.group(1),
            'method': 'viper',
            'line': source[:match.start()].count('\n') + 1,
        })

    return env_vars


def extract_env_vars_csharp(source: str) -> List[Dict]:
    """Extract environment variable usage from C# code."""
    env_vars = []

    # Environment.GetEnvironmentVariable("VAR")
    for match in re.finditer(r'Environment\.GetEnvironmentVariable\s*\(\s*["\'](\w+)["\']\s*\)', source):
        env_vars.append({
            'name': match.group(1),
            'method': 'Environment.GetEnvironmentVariable',
            'line': source[:match.start()].count('\n') + 1,
        })

    # IConfiguration: configuration["Key"] or configuration.GetValue<T>("Key")
    for match in re.finditer(r'(?:_?configuration|config)\s*\[\s*["\']([^"\']+)["\']\s*\]', source):
        env_vars.append({
            'name': match.group(1),
            'method': 'IConfiguration',
            'line': source[:match.start()].count('\n') + 1,
        })

    for match in re.finditer(r'\.GetValue<\w+>\s*\(\s*["\']([^"\']+)["\']\s*\)', source):
        env_vars.append({
            'name': match.group(1),
            'method': 'IConfiguration.GetValue',
            'line': source[:match.start()].count('\n') + 1,
        })

    return env_vars


def extract_env_vars_rust(source: str) -> List[Dict]:
    """Extract environment variable usage from Rust code."""
    env_vars = []

    # std::env::var("VAR")
    for match in re.finditer(r'(?:std::)?env::var\s*\(\s*["\'](\w+)["\']\s*\)', source):
        env_vars.append({
            'name': match.group(1),
            'method': 'std::env::var',
            'line': source[:match.start()].count('\n') + 1,
        })

    # dotenvy or dotenv crate
    if 'dotenv' in source or 'dotenvy' in source:
        env_vars.append({
            'name': '__DOTENV_LOADED__',
            'method': 'dotenvy',
            'note': 'Uses dotenvy/dotenv for .env loading',
            'line': 0,
        })

    return env_vars


# ========== Feature Flag Detection ==========

def extract_feature_flags(source: str, filepath: Path) -> List[Dict]:
    """Detect feature flag usage patterns."""
    flags = []

    # LaunchDarkly
    for match in re.finditer(r'(?:ldclient|ld_client)\.(?:variation|bool_variation)\s*\(\s*["\']([^"\']+)["\']', source, re.IGNORECASE):
        flags.append({
            'name': match.group(1),
            'provider': 'launchdarkly',
            'line': source[:match.start()].count('\n') + 1,
        })

    # Unleash
    for match in re.finditer(r'unleash\.(?:isEnabled|is_enabled)\s*\(\s*["\']([^"\']+)["\']', source, re.IGNORECASE):
        flags.append({
            'name': match.group(1),
            'provider': 'unleash',
            'line': source[:match.start()].count('\n') + 1,
        })

    # Generic feature flag patterns
    for match in re.finditer(r'(?:feature_flag|featureFlag|FEATURE_FLAG)s?\.(?:isEnabled|is_enabled|get)\s*\(\s*["\']([^"\']+)["\']', source, re.IGNORECASE):
        flags.append({
            'name': match.group(1),
            'provider': 'generic',
            'line': source[:match.start()].count('\n') + 1,
        })

    # Environment-based feature flags (FEATURE_*, ENABLE_*, FF_*)
    for match in re.finditer(r'(?:FEATURE|ENABLE|FF)_(\w+)', source):
        flags.append({
            'name': match.group(0),
            'provider': 'env-based',
            'line': source[:match.start()].count('\n') + 1,
        })

    return flags


# ========== Config File Parsing ==========

def parse_dotenv(content: str) -> List[Dict]:
    """Parse .env file content."""
    vars = []

    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        match = re.match(r'^(\w+)\s*=\s*(.*)$', line)
        if match:
            name = match.group(1)
            value = match.group(2).strip().strip('"\'')

            # Check if it looks like a secret
            is_secret = any(kw in name.upper() for kw in ['KEY', 'SECRET', 'PASSWORD', 'TOKEN', 'CREDENTIAL', 'PRIVATE'])

            vars.append({
                'name': name,
                'has_value': bool(value),
                'is_placeholder': value in ('', 'xxx', 'your-key-here', 'changeme', 'TODO'),
                'likely_secret': is_secret,
            })

    return vars


def parse_json_config(content: str) -> Dict:
    """Parse JSON configuration file."""
    try:
        config = json.loads(content)
        return {
            'format': 'json',
            'keys': list(config.keys()) if isinstance(config, dict) else [],
            'nested_depth': _get_nested_depth(config),
        }
    except:
        return {'format': 'json', 'keys': [], 'error': 'parse_failed'}


def _get_nested_depth(obj, depth=0) -> int:
    """Get maximum nesting depth of a dict/list structure."""
    if isinstance(obj, dict):
        if not obj:
            return depth
        return max(_get_nested_depth(v, depth + 1) for v in obj.values())
    elif isinstance(obj, list):
        if not obj:
            return depth
        return max(_get_nested_depth(item, depth + 1) for item in obj)
    return depth


# ========== Secret Detection ==========

def detect_secrets(source: str, filepath: Path) -> List[Dict]:
    """Detect potential secrets in source code."""
    secrets = []

    for pattern, secret_type in SECRET_PATTERNS:
        for match in re.finditer(pattern, source, re.IGNORECASE):
            # Skip if in a comment
            line_start = source.rfind('\n', 0, match.start()) + 1
            line = source[line_start:match.start()]

            if '//' in line or '#' in line or line.strip().startswith('*'):
                continue

            # Skip if it's clearly a placeholder
            value = match.group(1) if match.lastindex else match.group(0)
            if value.lower() in ('xxx', 'your-key-here', 'changeme', 'placeholder', 'example', 'test'):
                continue

            secrets.append({
                'type': secret_type,
                'file': str(filepath),
                'line': source[:match.start()].count('\n') + 1,
                'confidence': DETECTED if len(value) > 15 else INFERRED,
            })

    return secrets


# ========== Main Analysis ==========

def analyze_config(project_path: str) -> Dict:
    """Analyze project for configuration and secrets patterns."""
    root = Path(project_path).resolve()

    result = {
        'root': str(root),
        'config_files': [],
        'env_vars': [],
        'feature_flags': [],
        'potential_secrets': [],
        'summary': {
            'config_files_found': 0,
            'unique_env_vars': 0,
            'feature_flags_count': 0,
            'potential_secrets_count': 0,
            'has_dotenv': False,
            'has_docker_compose': False,
            'config_formats': [],
        },
    }

    skip_dirs = {'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build', '.git', 'vendor', 'target'}
    seen_env_vars: Set[str] = set()

    # First pass: find configuration files
    for filepath in root.rglob('*'):
        if any(skip in filepath.parts for skip in skip_dirs):
            continue
        if not filepath.is_file():
            continue

        filename = filepath.name
        rel_path = str(filepath.relative_to(root))

        # Check if it's a known config file
        if filename in CONFIG_FILES:
            config_type = CONFIG_FILES[filename]

            try:
                content = filepath.read_text(encoding='utf-8', errors='replace')
            except:
                continue

            config_info = {
                'file': rel_path,
                'type': config_type,
                'confidence': DETECTED,
            }

            # Parse specific formats
            if config_type == 'dotenv' or config_type == 'dotenv-template':
                vars = parse_dotenv(content)
                config_info['variables'] = vars
                config_info['variable_count'] = len(vars)
                result['summary']['has_dotenv'] = True

                # Check for secrets in .env
                secret_vars = [v for v in vars if v.get('likely_secret') and v.get('has_value') and not v.get('is_placeholder')]
                if secret_vars and config_type != 'dotenv-template':
                    for sv in secret_vars:
                        result['potential_secrets'].append({
                            'type': 'env_secret',
                            'file': rel_path,
                            'variable': sv['name'],
                            'confidence': WARNING,
                        })

            elif config_type == 'json-config' or config_type == 'dotnet-config':
                parsed = parse_json_config(content)
                config_info['keys'] = parsed.get('keys', [])

            elif config_type == 'docker-compose':
                result['summary']['has_docker_compose'] = True

            result['config_files'].append(config_info)

            if config_type not in result['summary']['config_formats']:
                result['summary']['config_formats'].append(config_type)

    # Second pass: scan source files for env var usage
    for filepath in root.rglob('*'):
        if any(skip in filepath.parts for skip in skip_dirs):
            continue
        if not filepath.is_file():
            continue

        suffix = filepath.suffix.lower()

        if suffix not in ('.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.cs', '.rs'):
            continue

        try:
            source = filepath.read_text(encoding='utf-8', errors='replace')
        except:
            continue

        rel_path = str(filepath.relative_to(root))
        env_vars = []

        # Extract env vars by language
        if suffix == '.py':
            env_vars = extract_env_vars_python(source)
        elif suffix in ('.js', '.ts', '.jsx', '.tsx'):
            env_vars = extract_env_vars_js(source)
        elif suffix == '.go':
            env_vars = extract_env_vars_go(source)
        elif suffix == '.cs':
            env_vars = extract_env_vars_csharp(source)
        elif suffix == '.rs':
            env_vars = extract_env_vars_rust(source)

        for ev in env_vars:
            ev['file'] = rel_path
            if ev['name'] not in seen_env_vars:
                result['env_vars'].append(ev)
                seen_env_vars.add(ev['name'])

        # Feature flags
        flags = extract_feature_flags(source, filepath)
        for flag in flags:
            flag['file'] = rel_path
            result['feature_flags'].append(flag)

        # Secrets detection (only in non-config source files)
        if suffix in ('.py', '.js', '.ts', '.go', '.cs', '.rs'):
            secrets = detect_secrets(source, filepath)
            result['potential_secrets'].extend(secrets)

    # Summary
    result['summary']['config_files_found'] = len(result['config_files'])
    result['summary']['unique_env_vars'] = len(seen_env_vars)
    result['summary']['feature_flags_count'] = len(result['feature_flags'])
    result['summary']['potential_secrets_count'] = len(result['potential_secrets'])

    # Deduplicate feature flags
    seen_flags = set()
    unique_flags = []
    for flag in result['feature_flags']:
        if flag['name'] not in seen_flags:
            unique_flags.append(flag)
            seen_flags.add(flag['name'])
    result['feature_flags'] = unique_flags

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_config.py <project_path> [--output file.json]", file=sys.stderr)
        sys.exit(1)

    project_path = sys.argv[1]
    output_file = None

    if '--output' in sys.argv:
        output_file = sys.argv[sys.argv.index('--output') + 1]

    result = analyze_config(project_path)

    # Print summary
    print(f"⚙️  Configuration Analysis for {Path(project_path).name}")
    print(f"   Config files: {result['summary']['config_files_found']}")
    print(f"   Environment variables: {result['summary']['unique_env_vars']}")
    print(f"   Feature flags: {result['summary']['feature_flags_count']}")

    if result['summary']['potential_secrets_count'] > 0:
        print(f"   ⚠️  Potential secrets: {result['summary']['potential_secrets_count']}")

    if result['summary']['config_formats']:
        print(f"   Formats: {', '.join(result['summary']['config_formats'])}")

    if result['config_files']:
        print("\n   Config files found:")
        for cf in result['config_files'][:5]:
            print(f"     • {cf['file']} ({cf['type']})")
        if len(result['config_files']) > 5:
            print(f"     ... and {len(result['config_files']) - 5} more")

    if result['env_vars']:
        print("\n   Environment variables used:")
        # Group by common prefixes
        prefixes = defaultdict(list)
        for ev in result['env_vars']:
            name = ev['name']
            if name.startswith('__'):
                continue
            prefix = name.split('_')[0] if '_' in name else name
            prefixes[prefix].append(name)

        for prefix, names in sorted(prefixes.items(), key=lambda x: -len(x[1]))[:5]:
            if len(names) > 1:
                print(f"     • {prefix}_*: {len(names)} vars")
            else:
                print(f"     • {names[0]}")

    if output_file:
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n💾 Saved to {output_file}")
    else:
        print()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
