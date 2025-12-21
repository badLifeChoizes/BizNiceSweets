#!/usr/bin/env python3
"""
API Analyzer
Detects REST endpoints, GraphQL schemas, gRPC services, and WebSocket handlers
across multiple frameworks and languages.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple


DETECTED = "detected"
INFERRED = "inferred"


# ========== Framework Detection ==========

FRAMEWORK_INDICATORS = {
    # Python
    'flask': {'files': ['app.py', 'wsgi.py'], 'imports': ['flask', 'Flask']},
    'fastapi': {'files': ['main.py'], 'imports': ['fastapi', 'FastAPI']},
    'django': {'files': ['urls.py', 'views.py', 'settings.py'], 'imports': ['django']},
    'django-rest': {'imports': ['rest_framework']},

    # JavaScript/TypeScript
    'express': {'imports': ['express'], 'patterns': [r'app\.(get|post|put|delete|patch)\s*\(']},
    'fastify': {'imports': ['fastify'], 'patterns': [r'fastify\.(get|post|put|delete)\s*\(']},
    'nestjs': {'imports': ['@nestjs'], 'patterns': [r'@(Get|Post|Put|Delete|Patch)\s*\(']},
    'nextjs': {'files': ['next.config.js', 'next.config.mjs'], 'dirs': ['pages/api', 'app/api']},

    # Go
    'gin': {'imports': ['github.com/gin-gonic/gin']},
    'chi': {'imports': ['github.com/go-chi/chi']},
    'echo': {'imports': ['github.com/labstack/echo']},
    'fiber': {'imports': ['github.com/gofiber/fiber']},

    # C#
    'aspnet-core': {'files': ['Program.cs', 'Startup.cs'], 'patterns': [r'\[Http(Get|Post|Put|Delete)\]', r'\.MapGet\(', r'\.MapPost\(']},
    'aspnet-mvc': {'patterns': [r'\[Route\(', r'Controller\s*:\s*Controller']},

    # Java
    'spring': {'imports': ['org.springframework'], 'patterns': [r'@(GetMapping|PostMapping|RequestMapping)']},

    # Rust
    'actix': {'imports': ['actix_web'], 'patterns': [r'#\[(?:get|post|put|delete)\(']},
    'axum': {'imports': ['axum'], 'patterns': [r'\.route\s*\(']},
    'rocket': {'imports': ['rocket'], 'patterns': [r'#\[(?:get|post|put|delete)\(']},
}


# ========== Endpoint Extraction ==========

def extract_python_endpoints(filepath: Path, source: str) -> List[Dict]:
    """Extract endpoints from Python web frameworks."""
    endpoints = []

    # Flask/FastAPI decorators
    # @app.route('/path', methods=['GET', 'POST'])
    # @app.get('/path')
    # @router.post('/path')
    flask_pattern = r'@(?:app|router|bp|blueprint)\.(?:route\s*\(\s*[\'"]([^\'"]+)[\'"](?:.*?methods\s*=\s*\[([^\]]+)\])?|(?P<method>get|post|put|delete|patch)\s*\(\s*[\'"](?P<path>[^\'"]+)[\'"])'

    for match in re.finditer(flask_pattern, source, re.IGNORECASE | re.DOTALL):
        if match.group('method'):
            endpoints.append({
                'path': match.group('path'),
                'method': match.group('method').upper(),
                'framework': 'flask/fastapi',
                'confidence': DETECTED,
                'line': source[:match.start()].count('\n') + 1,
            })
        elif match.group(1):
            methods = ['GET']
            if match.group(2):
                methods = [m.strip().strip('\'"') for m in match.group(2).split(',')]
            for method in methods:
                endpoints.append({
                    'path': match.group(1),
                    'method': method.upper(),
                    'framework': 'flask',
                    'confidence': DETECTED,
                    'line': source[:match.start()].count('\n') + 1,
                })

    # FastAPI with APIRouter
    fastapi_pattern = r'@(?:router|app)\.(?:api_route\s*\(\s*[\'"]([^\'"]+)[\'"]|(?P<method>get|post|put|delete|patch|options|head)\s*\(\s*[\'"](?P<path>[^\'"]+)[\'"])'
    for match in re.finditer(fastapi_pattern, source, re.IGNORECASE):
        if match.group('method'):
            endpoints.append({
                'path': match.group('path'),
                'method': match.group('method').upper(),
                'framework': 'fastapi',
                'confidence': DETECTED,
                'line': source[:match.start()].count('\n') + 1,
            })

    # Django URL patterns
    # path('api/users/', views.user_list, name='user-list')
    # re_path(r'^api/users/(?P<pk>\d+)/$', views.user_detail)
    django_pattern = r'(?:path|re_path)\s*\(\s*[\'"]([^\'"]+)[\'"]'
    if 'urlpatterns' in source:
        for match in re.finditer(django_pattern, source):
            path = match.group(1)
            endpoints.append({
                'path': '/' + path.lstrip('/'),
                'method': 'VARIES',
                'framework': 'django',
                'confidence': INFERRED,
                'line': source[:match.start()].count('\n') + 1,
            })

    return endpoints


def extract_js_endpoints(filepath: Path, source: str) -> List[Dict]:
    """Extract endpoints from JavaScript/TypeScript frameworks."""
    endpoints = []

    # Express-style: app.get('/path', handler) or router.post('/path', ...)
    express_pattern = r'(?:app|router)\.(get|post|put|delete|patch|options|head|all)\s*\(\s*[\'"`]([^\'"` ]+)[\'"`]'
    for match in re.finditer(express_pattern, source, re.IGNORECASE):
        endpoints.append({
            'path': match.group(2),
            'method': match.group(1).upper(),
            'framework': 'express',
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    # NestJS decorators: @Get('/path'), @Post('/path')
    nestjs_pattern = r'@(Get|Post|Put|Delete|Patch|Options|Head)\s*\(\s*(?:[\'"`]([^\'"` ]*)[\'"`])?\s*\)'
    for match in re.finditer(nestjs_pattern, source):
        path = match.group(2) or '/'
        endpoints.append({
            'path': path,
            'method': match.group(1).upper(),
            'framework': 'nestjs',
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    # Next.js API routes (inferred from file path)
    if '/pages/api/' in str(filepath) or '/app/api/' in str(filepath):
        # Extract route from file path
        path_str = str(filepath)
        if '/pages/api/' in path_str:
            route = path_str.split('/pages/api/')[-1]
        else:
            route = path_str.split('/app/api/')[-1]

        route = '/' + route.replace('\\', '/').rsplit('.', 1)[0]
        route = re.sub(r'\[([^\]]+)\]', r':\1', route)  # [id] -> :id
        route = route.replace('/index', '').replace('/route', '')

        # Detect which methods are exported
        methods = []
        for method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
            if re.search(rf'export\s+(?:async\s+)?function\s+{method}\b|export\s+const\s+{method}\s*=', source):
                methods.append(method)

        if not methods:
            methods = ['GET']  # Default

        for method in methods:
            endpoints.append({
                'path': route or '/',
                'method': method,
                'framework': 'nextjs',
                'confidence': DETECTED,
                'line': 1,
            })

    return endpoints


def extract_go_endpoints(filepath: Path, source: str) -> List[Dict]:
    """Extract endpoints from Go web frameworks."""
    endpoints = []

    # Gin: router.GET("/path", handler)
    gin_pattern = r'\.(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\s*\(\s*["`]([^"`]+)["`]'
    for match in re.finditer(gin_pattern, source):
        endpoints.append({
            'path': match.group(2),
            'method': match.group(1).upper(),
            'framework': 'gin/echo/fiber',
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    # Chi: r.Get("/path", handler), r.Route("/path", func(r chi.Router) {...})
    chi_pattern = r'r\.(Get|Post|Put|Delete|Patch|Options|Head)\s*\(\s*["`]([^"`]+)["`]'
    for match in re.finditer(chi_pattern, source):
        endpoints.append({
            'path': match.group(2),
            'method': match.group(1).upper(),
            'framework': 'chi',
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    # Standard library: http.HandleFunc("/path", handler)
    stdlib_pattern = r'(?:http\.HandleFunc|mux\.HandleFunc|Handle)\s*\(\s*["`]([^"`]+)["`]'
    for match in re.finditer(stdlib_pattern, source):
        endpoints.append({
            'path': match.group(1),
            'method': 'ALL',
            'framework': 'net/http',
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    return endpoints


def extract_csharp_endpoints(filepath: Path, source: str) -> List[Dict]:
    """Extract endpoints from ASP.NET Core."""
    endpoints = []

    # Attribute routing: [HttpGet("path")], [HttpPost], [Route("api/[controller]")]
    attr_pattern = r'\[(Http(?:Get|Post|Put|Delete|Patch|Options|Head))(?:\s*\(\s*["\']([^"\']*)["\'])?\s*\]'
    for match in re.finditer(attr_pattern, source):
        method = match.group(1).replace('Http', '').upper()
        path = match.group(2) or ''
        endpoints.append({
            'path': path or '/',
            'method': method,
            'framework': 'aspnet',
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    # Minimal API: app.MapGet("/path", handler)
    minimal_pattern = r'\.Map(Get|Post|Put|Delete|Patch)\s*\(\s*["\']([^"\']+)["\']'
    for match in re.finditer(minimal_pattern, source):
        endpoints.append({
            'path': match.group(2),
            'method': match.group(1).upper(),
            'framework': 'aspnet-minimal',
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    # Controller Route attribute: [Route("api/[controller]")]
    route_pattern = r'\[Route\s*\(\s*["\']([^"\']+)["\']\s*\)\]'
    for match in re.finditer(route_pattern, source):
        # This is a base route, store for context
        endpoints.append({
            'path': match.group(1),
            'method': 'BASE_ROUTE',
            'framework': 'aspnet',
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    return endpoints


def extract_java_endpoints(filepath: Path, source: str) -> List[Dict]:
    """Extract endpoints from Spring Framework."""
    endpoints = []

    # @RequestMapping, @GetMapping, etc.
    mapping_pattern = r'@(RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)\s*\(\s*(?:value\s*=\s*)?["\']?([^"\')]+)["\']?\s*\)'
    for match in re.finditer(mapping_pattern, source):
        mapping_type = match.group(1)
        path = match.group(2).strip('"\'')

        if mapping_type == 'RequestMapping':
            method = 'ALL'
        else:
            method = mapping_type.replace('Mapping', '').upper()

        endpoints.append({
            'path': path,
            'method': method,
            'framework': 'spring',
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    return endpoints


def extract_rust_endpoints(filepath: Path, source: str) -> List[Dict]:
    """Extract endpoints from Rust web frameworks."""
    endpoints = []

    # Actix-web: #[get("/path")], #[post("/path")]
    actix_pattern = r'#\[(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']\s*\)\]'
    for match in re.finditer(actix_pattern, source, re.IGNORECASE):
        endpoints.append({
            'path': match.group(2),
            'method': match.group(1).upper(),
            'framework': 'actix',
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    # Axum: .route("/path", get(handler))
    axum_pattern = r'\.route\s*\(\s*["\']([^"\']+)["\']\s*,\s*(get|post|put|delete|patch)'
    for match in re.finditer(axum_pattern, source, re.IGNORECASE):
        endpoints.append({
            'path': match.group(1),
            'method': match.group(2).upper(),
            'framework': 'axum',
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    # Rocket: #[get("/path")], #[post("/path")]
    rocket_pattern = r'#\[(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']\s*\)\]'
    for match in re.finditer(rocket_pattern, source, re.IGNORECASE):
        endpoints.append({
            'path': match.group(2),
            'method': match.group(1).upper(),
            'framework': 'rocket',
            'confidence': DETECTED,
            'line': source[:match.start()].count('\n') + 1,
        })

    return endpoints


# ========== GraphQL Detection ==========

def extract_graphql(filepath: Path, source: str) -> Dict:
    """Extract GraphQL schema information."""
    graphql = {
        'queries': [],
        'mutations': [],
        'subscriptions': [],
        'types': [],
        'resolvers': [],
    }

    # GraphQL SDL in .graphql files or template strings
    is_graphql_file = filepath.suffix in ('.graphql', '.gql')

    if is_graphql_file:
        content = source
    else:
        # Look for template strings containing GraphQL
        gql_matches = re.findall(r'(?:gql|graphql)`([^`]+)`', source, re.DOTALL)
        content = '\n'.join(gql_matches)

    if content:
        # Extract type definitions
        for match in re.finditer(r'type\s+(\w+)\s*(?:@\w+(?:\([^)]*\))?\s*)*\{', content):
            type_name = match.group(1)
            if type_name == 'Query':
                # Extract query fields
                block_match = re.search(rf'type\s+Query\s*\{{([^}}]+)\}}', content, re.DOTALL)
                if block_match:
                    for field in re.finditer(r'(\w+)\s*(?:\([^)]*\))?\s*:', block_match.group(1)):
                        graphql['queries'].append(field.group(1))
            elif type_name == 'Mutation':
                block_match = re.search(rf'type\s+Mutation\s*\{{([^}}]+)\}}', content, re.DOTALL)
                if block_match:
                    for field in re.finditer(r'(\w+)\s*(?:\([^)]*\))?\s*:', block_match.group(1)):
                        graphql['mutations'].append(field.group(1))
            elif type_name == 'Subscription':
                block_match = re.search(rf'type\s+Subscription\s*\{{([^}}]+)\}}', content, re.DOTALL)
                if block_match:
                    for field in re.finditer(r'(\w+)\s*(?:\([^)]*\))?\s*:', block_match.group(1)):
                        graphql['subscriptions'].append(field.group(1))
            else:
                graphql['types'].append(type_name)

    # Python GraphQL resolvers (Strawberry, Ariadne, Graphene)
    if filepath.suffix == '.py':
        # Strawberry
        for match in re.finditer(r'@strawberry\.(?:field|mutation)\s*(?:\([^)]*\))?\s*def\s+(\w+)', source):
            graphql['resolvers'].append(match.group(1))

        # Graphene
        for match in re.finditer(r'class\s+(\w+)\s*\(\s*(?:graphene\.)?(?:ObjectType|Mutation)\s*\)', source):
            graphql['resolvers'].append(match.group(1))

    # JavaScript/TypeScript resolvers
    if filepath.suffix in ('.js', '.ts', '.jsx', '.tsx'):
        # Common resolver patterns
        for match in re.finditer(r'(?:Query|Mutation|Subscription)\s*:\s*\{([^}]+)\}', source, re.DOTALL):
            for resolver in re.finditer(r'(\w+)\s*(?::\s*(?:async\s*)?\(|:\s*\()', match.group(1)):
                graphql['resolvers'].append(resolver.group(1))

    return graphql


# ========== gRPC Detection ==========

def extract_grpc(filepath: Path, source: str) -> Dict:
    """Extract gRPC service definitions from .proto files."""
    grpc = {
        'services': [],
        'methods': [],
        'messages': [],
    }

    if filepath.suffix != '.proto':
        return grpc

    # Services
    for match in re.finditer(r'service\s+(\w+)\s*\{([^}]+)\}', source, re.DOTALL):
        service_name = match.group(1)
        grpc['services'].append(service_name)

        # Methods within service
        for method in re.finditer(r'rpc\s+(\w+)\s*\(\s*(\w+)\s*\)\s*returns\s*\(\s*(\w+)\s*\)', match.group(2)):
            grpc['methods'].append({
                'service': service_name,
                'name': method.group(1),
                'request': method.group(2),
                'response': method.group(3),
            })

    # Messages
    for match in re.finditer(r'message\s+(\w+)\s*\{', source):
        grpc['messages'].append(match.group(1))

    return grpc


# ========== Main Analysis ==========

def analyze_api(project_path: str) -> Dict:
    """Analyze project for API endpoints."""
    root = Path(project_path).resolve()

    result = {
        'root': str(root),
        'frameworks_detected': [],
        'endpoints': [],
        'graphql': {
            'queries': [],
            'mutations': [],
            'subscriptions': [],
            'types': [],
            'resolvers': [],
        },
        'grpc': {
            'services': [],
            'methods': [],
            'messages': [],
        },
        'websocket': [],
        'summary': {
            'total_endpoints': 0,
            'by_method': defaultdict(int),
            'by_framework': defaultdict(int),
        },
    }

    skip_dirs = {'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build', '.git', 'vendor', 'target'}

    # Scan for API files
    for filepath in root.rglob('*'):
        if any(skip in filepath.parts for skip in skip_dirs):
            continue
        if not filepath.is_file():
            continue

        suffix = filepath.suffix.lower()

        try:
            if suffix in ('.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.cs', '.java', '.rs', '.proto', '.graphql', '.gql'):
                source = filepath.read_text(encoding='utf-8', errors='replace')
            else:
                continue
        except:
            continue

        rel_path = str(filepath.relative_to(root))
        endpoints = []

        # Extract endpoints by language
        if suffix == '.py':
            endpoints = extract_python_endpoints(filepath, source)
        elif suffix in ('.js', '.ts', '.jsx', '.tsx'):
            endpoints = extract_js_endpoints(filepath, source)
        elif suffix == '.go':
            endpoints = extract_go_endpoints(filepath, source)
        elif suffix == '.cs':
            endpoints = extract_csharp_endpoints(filepath, source)
        elif suffix == '.java':
            endpoints = extract_java_endpoints(filepath, source)
        elif suffix == '.rs':
            endpoints = extract_rust_endpoints(filepath, source)

        # Add file reference to endpoints
        for ep in endpoints:
            ep['file'] = rel_path
            result['endpoints'].append(ep)

        # GraphQL
        graphql = extract_graphql(filepath, source)
        for key in graphql:
            result['graphql'][key].extend(graphql[key])

        # gRPC
        if suffix == '.proto':
            grpc = extract_grpc(filepath, source)
            for key in grpc:
                if isinstance(grpc[key], list):
                    result['grpc'][key].extend(grpc[key])

        # WebSocket detection
        if re.search(r'WebSocket|socket\.io|ws\.on|io\.on', source, re.IGNORECASE):
            result['websocket'].append(rel_path)

    # Deduplicate
    result['graphql']['queries'] = list(set(result['graphql']['queries']))
    result['graphql']['mutations'] = list(set(result['graphql']['mutations']))
    result['graphql']['types'] = list(set(result['graphql']['types']))
    result['graphql']['resolvers'] = list(set(result['graphql']['resolvers']))
    result['grpc']['services'] = list(set(result['grpc']['services']))
    result['grpc']['messages'] = list(set(result['grpc']['messages']))

    # Summary
    result['summary']['total_endpoints'] = len(result['endpoints'])
    for ep in result['endpoints']:
        result['summary']['by_method'][ep['method']] += 1
        result['summary']['by_framework'][ep['framework']] += 1

    result['summary']['by_method'] = dict(result['summary']['by_method'])
    result['summary']['by_framework'] = dict(result['summary']['by_framework'])

    # Detect frameworks
    result['frameworks_detected'] = list(result['summary']['by_framework'].keys())

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_api.py <project_path> [--output file.json]", file=sys.stderr)
        sys.exit(1)

    project_path = sys.argv[1]
    output_file = None

    if '--output' in sys.argv:
        output_file = sys.argv[sys.argv.index('--output') + 1]

    result = analyze_api(project_path)

    # Print summary
    print(f"🔌 API Analysis for {Path(project_path).name}")
    print(f"   Endpoints: {result['summary']['total_endpoints']}")

    if result['summary']['by_method']:
        methods = ', '.join(f"{k}: {v}" for k, v in sorted(result['summary']['by_method'].items()))
        print(f"   Methods: {methods}")

    if result['graphql']['queries'] or result['graphql']['mutations']:
        print(f"   GraphQL: {len(result['graphql']['queries'])} queries, {len(result['graphql']['mutations'])} mutations")

    if result['grpc']['services']:
        print(f"   gRPC: {len(result['grpc']['services'])} services, {len(result['grpc']['methods'])} methods")

    if result['websocket']:
        print(f"   WebSocket: {len(result['websocket'])} files")

    if output_file:
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n💾 Saved to {output_file}")
    else:
        print()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
