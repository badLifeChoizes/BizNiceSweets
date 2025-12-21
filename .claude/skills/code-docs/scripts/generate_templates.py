#!/usr/bin/env python3
"""
Documentation Template Generator
Generates documentation templates for undocumented code elements.
Supports multiple doc formats: JSDoc, docstrings, XML docs, Go docs, Rust docs.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional


def generate_python_docstring(element: Dict, style: str = 'google') -> str:
    """Generate Python docstring template."""
    name = element.get('name', 'unknown')
    params = element.get('params', [])
    returns = element.get('returns')
    elem_type = element.get('type', 'function')
    
    if style == 'google':
        lines = ['"""<Short description>.', '', '<Detailed description>.']
        
        if params:
            lines.append('')
            lines.append('Args:')
            for p in params:
                pname = p.get('name', '')
                ptype = p.get('type', 'Any')
                if pname not in ('self', 'cls'):
                    lines.append(f'    {pname} ({ptype}): <Description>.')
        
        if returns and returns.lower() not in ('none', 'void'):
            lines.append('')
            lines.append('Returns:')
            lines.append(f'    {returns}: <Description>.')
        
        if elem_type == 'class':
            lines.append('')
            lines.append('Attributes:')
            lines.append('    <attribute> (<type>): <Description>.')
        
        lines.append('"""')
    
    elif style == 'sphinx':
        lines = ['"""<Short description>.', '', '<Detailed description>.']
        
        if params:
            lines.append('')
            for p in params:
                pname = p.get('name', '')
                ptype = p.get('type', 'Any')
                if pname not in ('self', 'cls'):
                    lines.append(f':param {pname}: <Description>')
                    lines.append(f':type {pname}: {ptype}')
        
        if returns and returns.lower() not in ('none', 'void'):
            lines.append(f':returns: <Description>')
            lines.append(f':rtype: {returns}')
        
        lines.append('"""')
    
    elif style == 'numpy':
        lines = ['"""<Short description>.', '', '<Detailed description>.']
        
        if params:
            lines.append('')
            lines.append('Parameters')
            lines.append('----------')
            for p in params:
                pname = p.get('name', '')
                ptype = p.get('type', 'Any')
                if pname not in ('self', 'cls'):
                    lines.append(f'{pname} : {ptype}')
                    lines.append('    <Description>.')
        
        if returns and returns.lower() not in ('none', 'void'):
            lines.append('')
            lines.append('Returns')
            lines.append('-------')
            lines.append(f'{returns}')
            lines.append('    <Description>.')
        
        lines.append('"""')
    
    return '\n'.join(lines)


def generate_jsdoc(element: Dict) -> str:
    """Generate JSDoc template."""
    name = element.get('name', 'unknown')
    params = element.get('params', [])
    returns = element.get('returns')
    elem_type = element.get('type', 'function')
    
    lines = ['/**', ' * <Short description>.', ' *', ' * <Detailed description>.']
    
    if params:
        lines.append(' *')
        for p in params:
            pname = p.get('name', '')
            ptype = p.get('type', '*')
            if ptype:
                lines.append(f' * @param {{{ptype}}} {pname} - <Description>.')
            else:
                lines.append(f' * @param {pname} - <Description>.')
    
    if returns and returns.lower() not in ('void', 'undefined'):
        lines.append(f' * @returns {{{returns}}} <Description>.')
    
    if elem_type == 'class':
        lines.append(' * @class')
    
    lines.append(' */')
    
    return '\n'.join(lines)


def generate_xml_doc(element: Dict) -> str:
    """Generate C# XML documentation template."""
    name = element.get('name', 'unknown')
    params = element.get('params', [])
    returns = element.get('returns')
    elem_type = element.get('type', 'method')
    
    lines = ['/// <summary>', '/// <Short description>.', '/// </summary>']
    
    if params:
        for p in params:
            pname = p.get('name', '')
            lines.append(f'/// <param name="{pname}"><Description>.</param>')
    
    if returns and returns.lower() not in ('void', 'task'):
        lines.append(f'/// <returns><Description>.</returns>')
    
    if elem_type == 'class':
        lines.append('/// <remarks>')
        lines.append('/// <Detailed description>.')
        lines.append('/// </remarks>')
    
    return '\n'.join(lines)


def generate_go_doc(element: Dict) -> str:
    """Generate Go doc comment template."""
    name = element.get('name', 'unknown')
    params = element.get('params', [])
    returns = element.get('returns')
    
    lines = [f'// {name} <short description>.', '//']
    
    if params:
        for p in params:
            pname = p.get('name', '')
            if pname not in ('ctx',):  # Skip common obvious params
                lines.append(f'// {pname}: <description>.')
    
    if returns:
        lines.append(f'// Returns <description>.')
    
    return '\n'.join(lines)


def generate_rust_doc(element: Dict) -> str:
    """Generate Rust doc comment template."""
    name = element.get('name', 'unknown')
    params = element.get('params', [])
    returns = element.get('returns')
    elem_type = element.get('type', 'fn')
    
    lines = ['/// <Short description>.', '///', '/// <Detailed description>.']
    
    if params:
        lines.append('///')
        lines.append('/// # Arguments')
        lines.append('///')
        for p in params:
            pname = p.get('name', '')
            if pname != 'self':
                lines.append(f'/// * `{pname}` - <Description>.')
    
    if returns and returns not in ('()', 'Self'):
        lines.append('///')
        lines.append('/// # Returns')
        lines.append('///')
        lines.append(f'/// `{returns}` - <Description>.')
    
    if elem_type == 'fn':
        lines.append('///')
        lines.append('/// # Examples')
        lines.append('///')
        lines.append('/// ```')
        lines.append(f'/// // Example usage of {name}')
        lines.append('/// ```')
    
    return '\n'.join(lines)


def generate_c_doxygen(element: Dict) -> str:
    """Generate C/C++ Doxygen template."""
    name = element.get('name', 'unknown')
    params = element.get('params', [])
    returns = element.get('returns')
    elem_type = element.get('type', 'function')
    
    lines = ['/**', ' * @brief <Short description>.', ' *', ' * <Detailed description>.']
    
    if params:
        lines.append(' *')
        for p in params:
            pname = p.get('name', '')
            lines.append(f' * @param {pname} <Description>.')
    
    if returns and returns.lower() not in ('void',):
        lines.append(f' * @return <Description>.')
    
    lines.append(' */')
    
    return '\n'.join(lines)


def generate_template(element: Dict, language: str, style: str = None) -> str:
    """Generate appropriate template based on language."""
    generators = {
        'python': lambda e: generate_python_docstring(e, style or 'google'),
        'javascript': generate_jsdoc,
        'typescript': generate_jsdoc,
        'csharp': generate_xml_doc,
        'go': generate_go_doc,
        'rust': generate_rust_doc,
        'c': generate_c_doxygen,
        'cpp': generate_c_doxygen,
    }
    
    generator = generators.get(language, generate_jsdoc)
    return generator(element)


def generate_templates_for_file(file_analysis: Dict, style: str = None) -> Dict:
    """Generate templates for all undocumented elements in a file."""
    language = file_analysis.get('language', 'python')
    elements = file_analysis.get('elements', [])
    
    templates = []
    
    for element in elements:
        if not element.get('docstring'):
            # Skip private elements
            name = element.get('name', '')
            is_private = element.get('is_private') or name.startswith('_')
            
            # Skip dunders except __init__
            is_dunder = name.startswith('__') and name.endswith('__')
            if is_dunder and name != '__init__':
                continue
            
            template = generate_template(element, language, style)
            
            templates.append({
                'name': element.get('name'),
                'type': element.get('type'),
                'line': element.get('line'),
                'signature': element.get('signature', ''),
                'template': template,
                'priority': 'high' if not is_private else 'low'
            })
        
        # Also check methods
        for method in element.get('methods', []):
            if not method.get('docstring'):
                name = method.get('name', '')
                is_private = method.get('is_private') or name.startswith('_')
                
                is_dunder = name.startswith('__') and name.endswith('__')
                if is_dunder and name != '__init__':
                    continue
                
                template = generate_template(method, language, style)
                
                templates.append({
                    'name': f"{element.get('name')}.{method.get('name')}",
                    'type': 'method',
                    'line': method.get('line'),
                    'signature': method.get('signature', ''),
                    'template': template,
                    'priority': 'high' if not is_private else 'low'
                })
    
    return {
        'filepath': file_analysis.get('filepath'),
        'language': language,
        'templates': templates
    }


def format_templates(result: Dict) -> str:
    """Format templates as readable output."""
    lines = [
        f"═══ Documentation Templates ═══",
        f"File: {result['filepath']}",
        f"Language: {result['language']}",
        f"Undocumented: {len(result['templates'])}",
        ""
    ]
    
    # Group by priority
    high_priority = [t for t in result['templates'] if t['priority'] == 'high']
    low_priority = [t for t in result['templates'] if t['priority'] == 'low']
    
    if high_priority:
        lines.append("── High Priority ──")
        for t in high_priority:
            lines.append("")
            lines.append(f"### {t['type']} `{t['name']}` (line {t['line']})")
            if t.get('signature'):
                lines.append(f"```")
                lines.append(t['signature'])
                lines.append(f"```")
            lines.append("")
            lines.append("Template:")
            lines.append("```")
            lines.append(t['template'])
            lines.append("```")
    
    if low_priority:
        lines.append("")
        lines.append("── Low Priority (private) ──")
        for t in low_priority[:5]:  # Limit
            lines.append(f"  • {t['name']} (line {t['line']})")
        if len(low_priority) > 5:
            lines.append(f"  ... and {len(low_priority) - 5} more")
    
    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: generate_templates.py <analysis.json> [--style google|sphinx|numpy] [--format json|text]", file=sys.stderr)
        sys.exit(1)
    
    input_file = sys.argv[1]
    style = None
    output_format = 'text'
    
    if '--style' in sys.argv:
        style = sys.argv[sys.argv.index('--style') + 1]
    if '--format' in sys.argv:
        output_format = sys.argv[sys.argv.index('--format') + 1]
    
    try:
        with open(input_file) as f:
            analysis = json.load(f)
    except Exception as e:
        print(f"Error reading {input_file}: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Handle single file or multi-file analysis
    if 'files' in analysis:
        results = []
        for file_analysis in analysis['files']:
            result = generate_templates_for_file(file_analysis, style)
            results.append(result)
        
        if output_format == 'json':
            print(json.dumps({'files': results}, indent=2))
        else:
            for result in results:
                if result['templates']:
                    print(format_templates(result))
                    print()
    else:
        result = generate_templates_for_file(analysis, style)
        
        if output_format == 'json':
            print(json.dumps(result, indent=2))
        else:
            print(format_templates(result))


if __name__ == "__main__":
    main()
