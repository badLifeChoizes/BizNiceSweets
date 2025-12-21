#!/usr/bin/env python3
"""
Codebase Analyzer v3 - Two-Phase Hybrid Analysis

Phase 1 (Automated): Run static analysis to gather raw data
Phase 2 (Claude-Assisted): Claude synthesizes insights from raw data + file sampling

This script runs Phase 1 and outputs data formatted for Phase 2 Claude synthesis.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from analyze_structure import analyze_structure
from analyze_deps import analyze_dependencies
from analyze_patterns import analyze_project_patterns
from build_graph import build_dependency_graph

# Import extended analyzers
try:
    from analyze_api import analyze_api
except ImportError:
    analyze_api = None

try:
    from analyze_models import analyze_models
except ImportError:
    analyze_models = None

try:
    from analyze_config import analyze_config
except ImportError:
    analyze_config = None

try:
    from analyze_embedded import analyze_embedded
except ImportError:
    analyze_embedded = None


def analyze_project(project_path: str, include_extended: bool = True) -> Dict:
    """Run complete project analysis (Phase 1)."""
    root = Path(project_path).resolve()

    print(f"📁 Analyzing: {root.name}")
    print()

    # Core analysis
    print("  → Analyzing structure...")
    structure = analyze_structure(str(root))

    print("  → Analyzing dependencies...")
    deps = analyze_dependencies(str(root))

    print("  → Detecting patterns...")
    patterns = analyze_project_patterns(str(root))

    print("  → Building dependency graph...")
    graph = build_dependency_graph(str(root))

    # Extended analysis (new analyzers)
    api_analysis = None
    models_analysis = None
    config_analysis = None
    embedded_analysis = None

    if include_extended:
        if analyze_api:
            print("  → Detecting API endpoints...")
            api_analysis = analyze_api(str(root))

        if analyze_models:
            print("  → Extracting data models...")
            models_analysis = analyze_models(str(root))

        if analyze_config:
            print("  → Analyzing configuration...")
            config_analysis = analyze_config(str(root))

        if analyze_embedded:
            print("  → Detecting embedded/IoT patterns...")
            embedded_analysis = analyze_embedded(str(root))

    print()

    # Combine results
    analysis = {
        'name': root.name,
        'path': str(root),
        'analyzed_at': datetime.now().isoformat(),
        'version': '3.0',
        'summary': {
            'total_files': structure['statistics']['total_files'],
            'total_dirs': structure['statistics']['total_dirs'],
            'languages': structure['statistics']['languages'],
            'primary_language': deps.get('primary_language'),
            'frameworks': deps.get('frameworks', []),
            'is_monorepo': deps.get('is_monorepo', False),
            'architectural_patterns': patterns.get('architectural_patterns', []),
        },
        'confidence': {
            'detected': structure['confidence_summary']['detected'],
            'inferred': structure['confidence_summary']['inferred'],
            'unknown': structure['confidence_summary']['unknown'],
        },
        'uncertain_areas': structure.get('uncertain_areas', []),
        'readme': structure.get('readme'),
        'structure': structure,
        'dependencies': deps,
        'patterns': patterns,
        'dependency_graph': graph,
    }

    # Add extended analysis results
    if api_analysis:
        analysis['api'] = api_analysis
        analysis['summary']['api_endpoints'] = api_analysis['summary']['total_endpoints']
        analysis['summary']['api_frameworks'] = api_analysis.get('frameworks_detected', [])

    if models_analysis:
        analysis['models'] = models_analysis
        analysis['summary']['data_models'] = models_analysis['summary']['total_models']
        analysis['summary']['orms'] = models_analysis.get('orms_detected', [])

    if config_analysis:
        analysis['config'] = config_analysis
        analysis['summary']['env_vars'] = config_analysis['summary']['unique_env_vars']
        analysis['summary']['config_files'] = config_analysis['summary']['config_files_found']
        if config_analysis['summary']['potential_secrets_count'] > 0:
            analysis['summary']['potential_secrets_warning'] = config_analysis['summary']['potential_secrets_count']

    if embedded_analysis and embedded_analysis.get('is_embedded_project'):
        analysis['embedded'] = embedded_analysis
        analysis['summary']['is_embedded'] = True
        analysis['summary']['embedded_platform'] = embedded_analysis.get('platform')
        analysis['summary']['rtos'] = embedded_analysis.get('rtos')
        analysis['summary']['mcu_family'] = embedded_analysis.get('mcu_family')

    # Generate questions and synthesis prompt
    analysis['questions_for_claude'] = generate_questions(analysis)
    analysis['synthesis_prompt'] = generate_synthesis_prompt(analysis)
    analysis['key_files_to_sample'] = identify_key_files(analysis)

    # Print summary
    print_summary(analysis)

    return analysis


def generate_questions(analysis: Dict) -> List[Dict]:
    """Generate questions for Claude to investigate during synthesis."""
    questions = []

    structure = analysis.get('structure', {})
    deps = analysis.get('dependencies', {})
    patterns = analysis.get('patterns', {})
    graph = analysis.get('dependency_graph', {})
    api = analysis.get('api', {})
    models = analysis.get('models', {})
    config = analysis.get('config', {})

    # Questions about uncertain directories
    for area in structure.get('uncertain_areas', [])[:5]:
        questions.append({
            'category': 'structure',
            'priority': 'medium',
            'question': area['question'],
            'context': f"Contains files: {', '.join(area['sample_files'])}",
            'action': 'Read sample files to determine purpose',
        })

    # Questions about architecture
    if not patterns.get('architectural_patterns'):
        questions.append({
            'category': 'architecture',
            'priority': 'high',
            'question': 'What architectural pattern does this project follow?',
            'context': 'No clear pattern detected from directory structure',
            'action': 'Review entry points and key modules to infer architecture',
        })

    # Questions about API design
    if api and api['summary']['total_endpoints'] > 0:
        if not api.get('graphql', {}).get('queries') and not api.get('grpc', {}).get('services'):
            questions.append({
                'category': 'api',
                'priority': 'medium',
                'question': 'What is the API versioning strategy?',
                'context': f"Found {api['summary']['total_endpoints']} REST endpoints",
                'action': 'Check endpoint paths for versioning patterns (/v1/, /api/v2/)',
            })

    # Questions about data flow
    if models and models['summary']['total_models'] > 0:
        questions.append({
            'category': 'data',
            'priority': 'medium',
            'question': 'How does data flow through the application?',
            'context': f"Found {models['summary']['total_models']} data models",
            'action': 'Trace relationships between models and API endpoints',
        })

    # Questions about configuration
    if config:
        if config['summary']['unique_env_vars'] > 10:
            questions.append({
                'category': 'configuration',
                'priority': 'low',
                'question': 'What are the critical configuration values for this application?',
                'context': f"Found {config['summary']['unique_env_vars']} environment variables",
                'action': 'Identify which env vars are required vs optional',
            })

        if config['summary'].get('potential_secrets_count', 0) > 0:
            questions.append({
                'category': 'security',
                'priority': 'high',
                'question': 'Are there exposed secrets in the codebase?',
                'context': f"Detected {config['summary']['potential_secrets_count']} potential secrets",
                'action': 'Review flagged locations and verify if they are actual secrets',
            })

    # Questions about monorepo structure
    if deps.get('is_monorepo'):
        questions.append({
            'category': 'structure',
            'priority': 'high',
            'question': 'How are the packages/workspaces in this monorepo related?',
            'context': 'Detected monorepo structure',
            'action': 'Examine package dependencies to understand relationships',
        })

    # Questions about circular dependencies
    if graph.get('circular_dependencies'):
        for cycle in graph['circular_dependencies'][:2]:
            questions.append({
                'category': 'dependencies',
                'priority': 'medium',
                'question': f'Is the circular dependency {" → ".join(cycle)} intentional?',
                'context': 'Circular dependencies can indicate design issues',
                'action': 'Review if these modules should be refactored',
            })

    # Questions about missing documentation
    if not structure.get('readme'):
        questions.append({
            'category': 'documentation',
            'priority': 'high',
            'question': 'What is the purpose and setup process for this project?',
            'context': 'No README found',
            'action': 'Ask the user or examine main entry points',
        })

    return questions


def identify_key_files(analysis: Dict) -> List[Dict]:
    """Identify key files Claude should read for deeper understanding."""
    key_files = []

    # README
    if analysis.get('readme'):
        key_files.append({
            'file': analysis['readme']['file'],
            'reason': 'Project documentation',
            'priority': 'high',
        })

    # Entry points from dependency graph
    graph = analysis.get('dependency_graph', {})
    for ep in graph.get('entry_points', [])[:3]:
        key_files.append({
            'file': ep,
            'reason': 'Entry point - shows application startup',
            'priority': 'high',
        })

    # Core modules
    for cm in graph.get('core_modules', [])[:3]:
        key_files.append({
            'file': cm,
            'reason': 'Core module - highly imported',
            'priority': 'medium',
        })

    # API route files
    api = analysis.get('api', {})
    if api:
        route_files = set()
        for endpoint in api.get('endpoints', [])[:10]:
            route_files.add(endpoint.get('file'))
        for rf in list(route_files)[:2]:
            if rf:
                key_files.append({
                    'file': rf,
                    'reason': 'API routes definition',
                    'priority': 'medium',
                })

    # Model files
    models = analysis.get('models', {})
    if models:
        model_files = set()
        for model in models.get('models', [])[:10]:
            model_files.add(model.get('file'))
        for mf in list(model_files)[:2]:
            if mf:
                key_files.append({
                    'file': mf,
                    'reason': 'Data model definitions',
                    'priority': 'medium',
                })

    # Config files
    config = analysis.get('config', {})
    if config:
        for cf in config.get('config_files', [])[:2]:
            key_files.append({
                'file': cf['file'],
                'reason': f"Configuration ({cf['type']})",
                'priority': 'low',
            })

    return key_files


def generate_synthesis_prompt(analysis: Dict) -> str:
    """Generate a prompt for Claude to synthesize the analysis into a useful context skill."""
    name = analysis['name']

    prompt = f"""# Phase 2: Synthesize Project Context for {name}

You have received automated analysis data for the "{name}" project. Your task is to synthesize this into a meaningful, actionable context skill that will help you (or another Claude instance) work effectively on this codebase.

## What You Have

The automated analysis includes:
- **Structure**: {analysis['summary']['total_files']} files across {analysis['summary']['total_dirs']} directories
- **Languages**: {', '.join(f"{k} ({v})" for k, v in sorted(analysis['summary'].get('languages', {}).items(), key=lambda x: -x[1])[:3])}
- **Frameworks**: {', '.join(analysis['summary'].get('frameworks', [])) or 'None detected'}
"""

    if analysis['summary'].get('api_endpoints'):
        prompt += f"- **API Endpoints**: {analysis['summary']['api_endpoints']} endpoints\n"

    if analysis['summary'].get('data_models'):
        prompt += f"- **Data Models**: {analysis['summary']['data_models']} models\n"

    if analysis['summary'].get('env_vars'):
        prompt += f"- **Environment Variables**: {analysis['summary']['env_vars']} unique variables\n"

    if analysis['summary'].get('is_embedded'):
        platform = analysis['summary'].get('embedded_platform', 'Unknown')
        rtos = analysis['summary'].get('rtos', 'None')
        mcu = analysis['summary'].get('mcu_family', 'Unknown')
        prompt += f"- **Embedded Platform**: {platform} (RTOS: {rtos}, MCU: {mcu})\n"

    prompt += f"""
## Your Tasks

1. **Read Key Files**: Examine the files listed in `key_files_to_sample` to understand:
   - What does this application actually DO? (business purpose)
   - How is code organized? (architecture in practice, not just theory)
   - What are the main workflows/user journeys?

2. **Answer Open Questions**: The analysis flagged {len(analysis.get('questions_for_claude', []))} questions that need investigation:
"""

    for q in analysis.get('questions_for_claude', [])[:5]:
        prompt += f"   - [{q['priority'].upper()}] {q['question']}\n"

    prompt += """
3. **Synthesize Context**: Create a SKILL.md that includes:
   - **What This Project Does**: 2-3 sentences explaining the business purpose
   - **How to Work on It**: Practical guidance (how to run, test, add features)
   - **Key Concepts**: Domain-specific terms and their meanings
   - **Gotchas**: Things that aren't obvious but will trip someone up
   - **Code Examples**: Short snippets showing the project's conventions

4. **Validate with User**: Ask the user to confirm or correct your understanding of:
   - The project's main purpose
   - Any inferred conventions or patterns
   - Anything marked as "uncertain" in the analysis

## Quality Standards

### Avoid Hollow Advice
DO NOT include generic statements that apply to any project. Examples of hollow advice to avoid:
- "Follow existing patterns" (which patterns?)
- "Use appropriate error handling" (what's appropriate here?)
- "Consider performance" (what specific bottlenecks?)

INSTEAD provide specific, actionable guidance:
- "Use the `Result<T, AppError>` pattern from `src/error.rs` for all fallible functions"
- "Wrap database calls in `transaction_scope()` from `db/utils.py`"
- "Hot path is in `process_frame()` - avoid allocations there"

### Include Guardrails Section
Add a "## Guardrails" section with specific DO NOT / ALWAYS rules discovered from the codebase:

```markdown
## Guardrails

### DO NOT
- [ ] Add new npm dependencies without checking bundle size impact
- [ ] Modify files in `generated/` - they're auto-generated from protobuf
- [ ] Use `console.log` - use the `logger` from `src/utils/logger.ts`

### ALWAYS
- [ ] Run `make lint` before committing
- [ ] Add migration files for any database schema changes
- [ ] Update the CHANGELOG.md for user-facing changes
```

### Quality Checklist
Before finalizing, verify your context skill passes these tests:

1. **Specificity Test**: Would this advice apply to a different project? If yes, make it more specific.
2. **Actionability Test**: Can someone follow this without asking questions? If no, add details.
3. **Gotcha Test**: Have you documented things that would trip up a newcomer?
4. **Example Test**: Do your code examples come from this actual codebase?

## Output Format

Generate the SKILL.md content directly. The skill should be conversational and practical, not just a data dump. Focus on what would actually help someone work on this code.

"""

    return prompt


def generate_skill_content(analysis: Dict) -> str:
    """Generate lean SKILL.md content - detailed data goes in reference files."""
    name = analysis['name']
    summary = analysis['summary']

    # Build tech stack line
    tech_parts = []
    if summary.get('primary_language'):
        tech_parts.append(summary['primary_language'].title())
    if summary.get('frameworks'):
        tech_parts.append(', '.join(summary['frameworks'][:2]))
    tech_stack = ' + '.join(tech_parts) if tech_parts else 'Unknown'

    content = f'''---
name: {name}-context
description: Project context for {name}. {tech_stack} project with {summary['total_files']} files. Use when working on this codebase.
---

# {name.replace('-', ' ').replace('_', ' ').title()} Context

'''

    # Brief overview from README (truncated)
    if analysis.get('readme'):
        readme = analysis['readme']
        overview = readme.get('sections', {}).get('overview', '')[:300]
        if overview:
            # Truncate at sentence boundary if possible
            if len(overview) >= 300:
                last_period = overview.rfind('.')
                if last_period > 150:
                    overview = overview[:last_period + 1]
                else:
                    overview = overview[:297] + '...'
            content += f"{overview}\n\n"

    # Quick stats table
    content += f'''## Quick Stats

| Metric | Value |
|--------|-------|
| Files | {summary['total_files']} |
| Primary Language | {summary.get('primary_language', 'Unknown')} |
| Frameworks | {', '.join(summary.get('frameworks', [])) or 'None detected'} |
'''

    if summary.get('api_endpoints'):
        content += f"| API Endpoints | {summary['api_endpoints']} |\n"
    if summary.get('data_models'):
        content += f"| Data Models | {summary['data_models']} |\n"
    if summary.get('env_vars'):
        content += f"| Env Variables | {summary['env_vars']} |\n"

    content += "\n"

    # Architectural patterns (brief)
    if summary.get('architectural_patterns'):
        content += f"**Architecture:** {', '.join(summary['architectural_patterns'])}\n\n"

    # Reference files section
    content += '''## Reference Files

Detailed analysis data is in the `references/` folder:

| File | Contents |
|------|----------|
| `synthesis_prompt.md` | Instructions for Phase 2 Claude synthesis |
| `structure.md` | Directory hierarchy and purposes |
| `conventions.md` | Naming conventions and code patterns |
'''

    if analysis.get('api') and analysis['api']['summary']['total_endpoints'] > 0:
        content += "| `api.md` | API endpoints and routes |\n"
    if analysis.get('models') and analysis['models']['summary']['total_models'] > 0:
        content += "| `models.md` | Data models and schemas |\n"
    if analysis.get('config') and analysis['config']['summary']['config_files_found'] > 0:
        content += "| `config.md` | Configuration and environment |\n"
    if analysis.get('questions_for_claude'):
        content += "| `questions.md` | Open questions to investigate |\n"

    content += "| `full_analysis.json` | Complete raw analysis data |\n"
    content += "\n"

    # Brief guidelines
    content += '''## Working on This Project

1. **Read `references/synthesis_prompt.md`** for Phase 2 synthesis instructions
2. **Check `references/conventions.md`** before writing new code
3. **Review `references/questions.md`** for areas needing verification
4. **Ask the user** about anything marked as uncertain or inferred
'''

    # Security warning if needed
    if summary.get('potential_secrets_warning'):
        content += f"\n> ⚠️ **Security:** {summary['potential_secrets_warning']} potential secrets detected - see `references/config.md`\n"

    return content


def generate_structure_reference(analysis: Dict) -> str:
    """Generate structure.md reference file."""
    content = "# Project Structure\n\n"

    summary = analysis['summary']
    content += f"**Total:** {summary['total_files']} files in {summary['total_dirs']} directories\n\n"

    # Languages breakdown
    if summary.get('languages'):
        content += "## Languages\n\n"
        for lang, count in sorted(summary['languages'].items(), key=lambda x: -x[1])[:10]:
            content += f"- {lang}: {count} files\n"
        content += "\n"

    # Directory tree
    content += "## Directory Hierarchy\n\n"

    if analysis['structure'].get('tree'):
        tree = analysis['structure']['tree']
        for child in tree.get('children', []):
            purpose = child.get('purpose', 'unknown')
            confidence = child.get('confidence', 'unknown')
            conf_marker = '' if confidence == 'detected' else f' ({confidence})'
            file_count = child.get('file_count', 0)
            content += f"- **{child['name']}/** - {purpose}{conf_marker}"
            if file_count > 0:
                content += f" [{file_count} files]"
            content += "\n"

    content += "\n"

    # Entry points and core modules
    graph = analysis.get('dependency_graph', {})
    if graph.get('entry_points'):
        content += "## Entry Points\n\n"
        for ep in graph['entry_points'][:10]:
            content += f"- `{ep}`\n"
        content += "\n"

    if graph.get('core_modules'):
        content += "## Core Modules\n\n"
        content += "Most imported internal modules:\n\n"
        for cm in graph['core_modules'][:10]:
            content += f"- `{cm}`\n"
        content += "\n"

    # Uncertain areas
    if analysis.get('uncertain_areas'):
        content += "## Uncertain Areas\n\n"
        content += "These directories need verification:\n\n"
        for area in analysis['uncertain_areas']:
            content += f"- **{area['path']}**: {area['question']}\n"
            if area.get('sample_files'):
                content += f"  - Sample files: {', '.join(area['sample_files'][:3])}\n"
        content += "\n"

    return content


def generate_conventions_reference(analysis: Dict) -> str:
    """Generate conventions.md reference file."""
    content = "# Code Conventions\n\n"

    patterns = analysis.get('patterns', {})
    naming = patterns.get('naming', {})

    # Naming conventions
    content += "## Naming Conventions\n\n"

    if naming.get('classes'):
        dominant = max(naming['classes'].items(), key=lambda x: x[1])[0] if naming['classes'] else None
        if dominant:
            content += f"**Classes:** {dominant}\n\n"

    if naming.get('functions'):
        dominant = max(naming['functions'].items(), key=lambda x: x[1])[0] if naming['functions'] else None
        if dominant:
            content += f"**Functions:** {dominant}\n\n"

    if naming.get('files'):
        dominant = max(naming['files'].items(), key=lambda x: x[1])[0] if naming['files'] else None
        if dominant:
            content += f"**Files:** {dominant}\n\n"

    # Language-specific patterns
    for lang, stats in patterns.get('languages', {}).items():
        content += f"## {lang.title()}\n\n"

        if lang == 'python':
            hint_coverage = stats.get('type_hint_coverage', 0)
            doc_coverage = stats.get('docstring_coverage', 0)
            content += f"- Type hint coverage: {hint_coverage}%"
            content += " (maintain them)\n" if hint_coverage > 50 else "\n"
            content += f"- Docstring coverage: {doc_coverage}%"
            content += " (add them to new code)\n" if doc_coverage > 50 else "\n"
            if stats.get('dataclasses', 0) > 0:
                content += f"- Uses dataclasses ({stats['dataclasses']} found)\n"
            if stats.get('async_usage', 0) > 0:
                content += f"- Uses async/await ({stats['async_usage']} async functions)\n"

        elif lang in ('javascript', 'typescript'):
            arrow = stats.get('arrow_functions', 0)
            regular = stats.get('regular_functions', 0)
            if arrow + regular > 0:
                content += f"- Arrow functions: {arrow}, Regular functions: {regular}\n"
                if arrow > regular * 2:
                    content += "  - Prefer arrow functions\n"
            if stats.get('react_components', 0) > 0:
                content += f"- React components: {stats['react_components']}\n"
            if stats.get('hooks_used'):
                content += f"- Hooks used: {', '.join(stats['hooks_used'][:8])}\n"

        elif lang == 'csharp':
            if stats.get('async_usage', 0) > 0:
                content += f"- Async methods: {stats['async_usage']}\n"
            if stats.get('linq_usage', 0) > 0:
                content += f"- LINQ usage: {stats['linq_usage']} occurrences\n"
            if stats.get('attributes_used'):
                content += f"- Attributes: {', '.join(stats['attributes_used'][:8])}\n"

        elif lang == 'go':
            if stats.get('goroutines', 0) > 0:
                content += f"- Goroutines: {stats['goroutines']}\n"
            if stats.get('channels', 0) > 0:
                content += f"- Channels: {stats['channels']}\n"

        elif lang == 'rust':
            if stats.get('async_usage', 0) > 0:
                content += f"- Async functions: {stats['async_usage']}\n"
            if stats.get('unsafe_blocks', 0) > 0:
                content += f"- Unsafe blocks: {stats['unsafe_blocks']}\n"

        content += "\n"

    return content


def generate_api_reference(analysis: Dict) -> str:
    """Generate api.md reference file."""
    api = analysis.get('api', {})
    if not api:
        return ""

    content = "# API Endpoints\n\n"

    summary = api.get('summary', {})
    content += f"**Total:** {summary.get('total_endpoints', 0)} endpoints\n\n"

    if summary.get('by_method'):
        content += "**By Method:**\n"
        for method, count in sorted(summary['by_method'].items()):
            content += f"- {method}: {count}\n"
        content += "\n"

    if summary.get('by_framework'):
        content += "**By Framework:**\n"
        for fw, count in sorted(summary['by_framework'].items()):
            content += f"- {fw}: {count}\n"
        content += "\n"

    # Endpoints grouped by file
    content += "## Endpoints\n\n"
    endpoints_by_file = {}
    for ep in api.get('endpoints', []):
        file = ep.get('file', 'unknown')
        if file not in endpoints_by_file:
            endpoints_by_file[file] = []
        endpoints_by_file[file].append(ep)

    for file, endpoints in sorted(endpoints_by_file.items()):
        content += f"### {file}\n\n"
        for ep in endpoints:
            content += f"- `{ep['method']} {ep['path']}`"
            if ep.get('line'):
                content += f" (line {ep['line']})"
            content += "\n"
        content += "\n"

    # GraphQL
    graphql = api.get('graphql', {})
    if graphql.get('queries') or graphql.get('mutations'):
        content += "## GraphQL\n\n"
        if graphql.get('queries'):
            content += f"**Queries:** {', '.join(graphql['queries'])}\n\n"
        if graphql.get('mutations'):
            content += f"**Mutations:** {', '.join(graphql['mutations'])}\n\n"

    # gRPC
    grpc = api.get('grpc', {})
    if grpc.get('services'):
        content += "## gRPC Services\n\n"
        for svc in grpc['services']:
            content += f"- {svc}\n"
        content += "\n"

    return content


def generate_models_reference(analysis: Dict) -> str:
    """Generate models.md reference file."""
    models_data = analysis.get('models', {})
    if not models_data:
        return ""

    content = "# Data Models\n\n"

    summary = models_data.get('summary', {})
    content += f"**Total:** {summary.get('total_models', 0)} models, {summary.get('total_fields', 0)} fields, {summary.get('total_relationships', 0)} relationships\n\n"

    if summary.get('by_orm'):
        content += "**By ORM:**\n"
        for orm, count in sorted(summary['by_orm'].items()):
            content += f"- {orm}: {count}\n"
        content += "\n"

    # Models grouped by file
    content += "## Models\n\n"
    models_by_file = {}
    for model in models_data.get('models', []):
        file = model.get('file', 'unknown')
        if file not in models_by_file:
            models_by_file[file] = []
        models_by_file[file].append(model)

    for file, models in sorted(models_by_file.items()):
        content += f"### {file}\n\n"
        for model in models:
            content += f"**{model['name']}** ({model['orm']})"
            if model.get('table'):
                content += f" → `{model['table']}`"
            content += "\n\n"

            if model.get('fields'):
                content += "Fields:\n"
                for field in model['fields'][:15]:
                    content += f"- `{field['name']}`: {field.get('type', 'unknown')}\n"
                if len(model['fields']) > 15:
                    content += f"- ... and {len(model['fields']) - 15} more\n"
                content += "\n"

            if model.get('relationships'):
                content += "Relationships:\n"
                for rel in model['relationships']:
                    content += f"- `{rel['name']}` → {rel['target']}\n"
                content += "\n"

    return content


def generate_config_reference(analysis: Dict) -> str:
    """Generate config.md reference file."""
    config = analysis.get('config', {})
    if not config:
        return ""

    content = "# Configuration\n\n"

    summary = config.get('summary', {})
    content += f"**Config Files:** {summary.get('config_files_found', 0)}\n"
    content += f"**Environment Variables:** {summary.get('unique_env_vars', 0)}\n"
    if summary.get('potential_secrets_count', 0) > 0:
        content += f"**⚠️ Potential Secrets:** {summary['potential_secrets_count']}\n"
    content += "\n"

    # Config files
    if config.get('config_files'):
        content += "## Config Files\n\n"
        for cf in config['config_files']:
            content += f"- `{cf['file']}` ({cf['type']})"
            if cf.get('variable_count'):
                content += f" - {cf['variable_count']} variables"
            content += "\n"
        content += "\n"

    # Environment variables
    if config.get('env_vars'):
        content += "## Environment Variables\n\n"
        # Group by prefix
        by_prefix = {}
        for ev in config['env_vars']:
            name = ev['name']
            if name.startswith('__'):
                continue
            prefix = name.split('_')[0] if '_' in name else 'OTHER'
            if prefix not in by_prefix:
                by_prefix[prefix] = []
            by_prefix[prefix].append(ev)

        for prefix, vars in sorted(by_prefix.items()):
            content += f"### {prefix}_*\n\n"
            for ev in vars[:20]:
                content += f"- `{ev['name']}`"
                if ev.get('default'):
                    content += f" (default: {ev['default']})"
                if ev.get('file'):
                    content += f" - {ev['file']}"
                content += "\n"
            if len(vars) > 20:
                content += f"- ... and {len(vars) - 20} more\n"
            content += "\n"

    # Feature flags
    if config.get('feature_flags'):
        content += "## Feature Flags\n\n"
        for flag in config['feature_flags'][:20]:
            content += f"- `{flag['name']}` ({flag.get('provider', 'unknown')})\n"
        content += "\n"

    # Potential secrets warning
    if config.get('potential_secrets'):
        content += "## ⚠️ Potential Secrets\n\n"
        content += "These locations may contain exposed secrets:\n\n"
        for secret in config['potential_secrets'][:10]:
            content += f"- `{secret.get('file', 'unknown')}` line {secret.get('line', '?')}: {secret['type']}\n"
        content += "\n"

    return content


def generate_questions_reference(analysis: Dict) -> str:
    """Generate questions.md reference file."""
    questions = analysis.get('questions_for_claude', [])
    if not questions:
        return ""

    content = "# Open Questions\n\n"
    content += "These questions should be investigated during Phase 2 synthesis or asked to the user.\n\n"

    # Group by priority
    by_priority = {'high': [], 'medium': [], 'low': []}
    for q in questions:
        priority = q.get('priority', 'medium')
        by_priority[priority].append(q)

    for priority in ['high', 'medium', 'low']:
        if by_priority[priority]:
            content += f"## {priority.title()} Priority\n\n"
            for q in by_priority[priority]:
                content += f"### {q['question']}\n\n"
                content += f"**Category:** {q.get('category', 'general')}\n\n"
                if q.get('context'):
                    content += f"**Context:** {q['context']}\n\n"
                if q.get('action'):
                    content += f"**Suggested Action:** {q['action']}\n\n"

    return content


def generate_skill(analysis: Dict, output_dir: str) -> str:
    """Generate complete skill folder with lean SKILL.md and detailed references."""
    name = analysis['name']
    skill_name = f"{name}-context"
    skill_dir = Path(output_dir) / skill_name

    # Create directories
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / 'references').mkdir(exist_ok=True)

    # Generate lean SKILL.md
    skill_content = generate_skill_content(analysis)
    (skill_dir / 'SKILL.md').write_text(skill_content, encoding='utf-8')

    # Generate reference files (markdown for human readability)
    refs_dir = skill_dir / 'references'

    # Structure reference
    structure_content = generate_structure_reference(analysis)
    (refs_dir / 'structure.md').write_text(structure_content, encoding='utf-8')

    # Conventions reference
    conventions_content = generate_conventions_reference(analysis)
    (refs_dir / 'conventions.md').write_text(conventions_content, encoding='utf-8')

    # API reference (if applicable)
    if analysis.get('api') and analysis['api']['summary']['total_endpoints'] > 0:
        api_content = generate_api_reference(analysis)
        (refs_dir / 'api.md').write_text(api_content, encoding='utf-8')

    # Models reference (if applicable)
    if analysis.get('models') and analysis['models']['summary']['total_models'] > 0:
        models_content = generate_models_reference(analysis)
        (refs_dir / 'models.md').write_text(models_content, encoding='utf-8')

    # Config reference (if applicable)
    if analysis.get('config') and analysis['config']['summary']['config_files_found'] > 0:
        config_content = generate_config_reference(analysis)
        (refs_dir / 'config.md').write_text(config_content, encoding='utf-8')

    # Questions reference
    if analysis.get('questions_for_claude'):
        questions_content = generate_questions_reference(analysis)
        (refs_dir / 'questions.md').write_text(questions_content, encoding='utf-8')

    # Synthesis prompt
    if analysis.get('synthesis_prompt'):
        (refs_dir / 'synthesis_prompt.md').write_text(
            analysis['synthesis_prompt'], encoding='utf-8'
        )

    # Full analysis JSON (for programmatic access)
    (refs_dir / 'full_analysis.json').write_text(
        json.dumps(analysis, indent=2), encoding='utf-8'
    )

    return str(skill_dir)


def print_summary(analysis: Dict):
    """Print analysis summary to console."""
    print(f"📊 Summary for {analysis['name']}:")
    print(f"   Files: {analysis['summary']['total_files']}")
    print(f"   Directories: {analysis['summary']['total_dirs']}")

    if analysis['summary'].get('languages'):
        langs = ', '.join(f"{k}({v})" for k, v in sorted(
            analysis['summary']['languages'].items(), key=lambda x: -x[1]
        )[:5])
        print(f"   Languages: {langs}")

    if analysis['summary'].get('frameworks'):
        print(f"   Frameworks: {', '.join(analysis['summary']['frameworks'])}")

    if analysis['summary'].get('is_embedded'):
        platform = analysis['summary'].get('embedded_platform', 'Unknown')
        rtos = analysis['summary'].get('rtos', 'None')
        mcu = analysis['summary'].get('mcu_family', 'Unknown')
        print(f"   Embedded: {platform} (RTOS: {rtos}, MCU: {mcu})")

    if analysis['summary'].get('api_endpoints'):
        print(f"   API Endpoints: {analysis['summary']['api_endpoints']}")

    if analysis['summary'].get('data_models'):
        print(f"   Data Models: {analysis['summary']['data_models']}")

    if analysis['summary'].get('env_vars'):
        print(f"   Env Variables: {analysis['summary']['env_vars']}")

    conf = analysis['confidence']
    print(f"   Confidence: {conf['detected']} detected, {conf['inferred']} inferred, {conf['unknown']} unknown")

    if analysis.get('uncertain_areas'):
        print(f"   ⚠️  {len(analysis['uncertain_areas'])} areas need verification")

    if analysis['summary'].get('potential_secrets_warning'):
        print(f"   ⚠️  {analysis['summary']['potential_secrets_warning']} potential secrets detected")

    print()


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze.py <project_path> [options]", file=sys.stderr)
        print()
        print("Options:")
        print("  --output FILE       Save full analysis to JSON file")
        print("  --output-dir DIR    Directory for generated skill (default: current)")
        print("  --generate-skill    Generate context skill folder")
        print("  --basic             Skip extended analysis (API, models, config)")
        print("  --synthesis-only    Only output the synthesis prompt for Phase 2")
        print()
        print("Two-Phase Workflow:")
        print("  Phase 1: python analyze.py /path/to/project --generate-skill")
        print("  Phase 2: Ask Claude to read synthesis_prompt.md and key files")
        sys.exit(1)

    project_path = sys.argv[1]
    output_file = None
    output_dir = '.'
    generate = '--generate-skill' in sys.argv
    basic_only = '--basic' in sys.argv
    synthesis_only = '--synthesis-only' in sys.argv

    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]

    if '--output-dir' in sys.argv:
        idx = sys.argv.index('--output-dir')
        if idx + 1 < len(sys.argv):
            output_dir = sys.argv[idx + 1]

    # Run analysis
    analysis = analyze_project(project_path, include_extended=not basic_only)

    # Output options
    if synthesis_only:
        print(analysis.get('synthesis_prompt', 'No synthesis prompt generated'))
        return

    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2)
        print(f"💾 Analysis saved to: {output_file}")

    if generate:
        skill_dir = generate_skill(analysis, output_dir)
        print(f"✅ Generated skill at: {skill_dir}")
        print()
        print("📋 Next Steps (Phase 2):")
        print(f"   1. Read: {skill_dir}/references/synthesis_prompt.md")
        print(f"   2. Read key files listed in the prompt")
        print(f"   3. Update {skill_dir}/SKILL.md with synthesized insights")

    if not output_file and not generate and not synthesis_only:
        print(json.dumps(analysis, indent=2))


if __name__ == "__main__":
    main()
