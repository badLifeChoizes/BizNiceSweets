#!/usr/bin/env python3
"""
Documentation Coverage Auditor v2
Enhanced with staleness detection and multi-language support.
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


def check_param_staleness(docstring: str, params: List[Dict], language: str) -> List[Dict]:
    """Check if documented params match actual params."""
    issues = []
    
    if not docstring or not params:
        return issues
    
    doc_lower = docstring.lower()
    actual_names = {p.get('name', '').lower() for p in params if p.get('name') not in ('self', 'cls', 'this', 'ctx')}
    
    # Find documented params based on language patterns
    doc_params = set()
    
    # Python Google style: Args:\n    param_name (type): description
    # Stop at blank lines or known section headers (Returns:, Raises:, Example:, Note:, Yields:, Attributes:)
    section_headers = r'(?:returns?|raises?|examples?|notes?|yields?|attributes?|see also|warning|todo):'
    for match in re.finditer(r'(?:args?|parameters?):\s*\n((?:[ \t]+[^\n]+\n?)+)', doc_lower, re.IGNORECASE):
        block = match.group(1)
        # Stop at next section header or blank line
        section_end = re.search(rf'^\s*{section_headers}|\n\s*\n', block, re.MULTILINE | re.IGNORECASE)
        if section_end:
            block = block[:section_end.start()]
        # Extract param names: word followed by space/paren/colon (not type names like 'bool', 'str')
        for pm in re.finditer(r'^\s+(\w+)\s*(?:\([^)]*\)\s*)?:', block, re.MULTILINE):
            param_name = pm.group(1).lower()
            # Skip common type names that appear as "type: description" in Returns/other sections
            type_keywords = {'bool', 'str', 'int', 'float', 'dict', 'list', 'tuple', 'set',
                           'none', 'any', 'optional', 'union', 'callable', 'iterator', 'path'}
            if param_name not in type_keywords:
                doc_params.add(param_name)
    
    # Python Sphinx style: :param name:
    for match in re.finditer(r':param\s+(\w+):', doc_lower):
        doc_params.add(match.group(1).lower())
    
    # JSDoc style: @param {type} name or @param name
    for match in re.finditer(r'@param\s+(?:\{[^}]+\}\s+)?(\w+)', doc_lower):
        doc_params.add(match.group(1).lower())
    
    # XML doc style: <param name="name">
    for match in re.finditer(r'<param\s+name="(\w+)"', doc_lower):
        doc_params.add(match.group(1).lower())
    
    # Check for missing params in doc
    missing_in_doc = actual_names - doc_params
    for param in missing_in_doc:
        issues.append({
            'severity': 'warning',
            'type': 'undocumented_param',
            'message': f"Parameter '{param}' not documented"
        })
    
    # Check for extra params in doc (stale)
    extra_in_doc = doc_params - actual_names
    for param in extra_in_doc:
        issues.append({
            'severity': 'warning',
            'type': 'stale_param',
            'message': f"Documented parameter '{param}' no longer exists"
        })
    
    return issues


def check_return_staleness(docstring: str, returns: Optional[str], language: str) -> List[Dict]:
    """Check if documented return matches actual return."""
    issues = []
    
    if not docstring:
        return issues
    
    doc_lower = docstring.lower()
    
    # Detect if doc mentions return
    has_return_doc = any(kw in doc_lower for kw in ['return', '@return', ':return', 'yields', '<returns>'])
    
    # Check actual return
    has_actual_return = returns and returns.lower() not in ('void', 'none', 'null', 'undefined', '()', 'task')
    
    if has_actual_return and not has_return_doc:
        issues.append({
            'severity': 'info',
            'type': 'undocumented_return',
            'message': f"Return value ({returns}) not documented"
        })
    elif has_return_doc and not has_actual_return:
        issues.append({
            'severity': 'warning',
            'type': 'stale_return',
            'message': "Documentation mentions return but function returns nothing"
        })
    
    return issues


def audit_element(element: Dict, language: str) -> Dict:
    """Audit a single code element for documentation issues."""
    issues = []
    name = element.get('name', 'unknown')
    elem_type = element.get('type', 'unknown')
    docstring = element.get('docstring')
    params = element.get('params', [])
    returns = element.get('returns')
    line = element.get('line', 0)
    
    is_private = element.get('is_private', False) or name.startswith('_')
    is_dunder = element.get('is_dunder', False) or (name.startswith('__') and name.endswith('__'))
    is_exported = element.get('is_exported', True)  # Go: exported = capitalized
    is_pub = element.get('is_pub', True)  # Rust: pub
    
    # Language-specific visibility
    if language == 'go':
        is_private = not name[0].isupper() if name else True
    elif language == 'rust':
        is_private = not element.get('is_pub', False)
    
    # Determine severity for missing docs
    if is_dunder:
        severity = 'skip'
    elif is_private:
        severity = 'info'
    elif elem_type in ('class', 'function', 'method', 'struct', 'interface', 'trait', 'fn'):
        severity = 'warning'
    else:
        severity = 'info'
    
    has_doc = bool(docstring)
    
    # Missing doc check
    if not has_doc and severity != 'skip':
        issues.append({
            'severity': severity,
            'type': 'missing_doc',
            'message': f"No documentation for {elem_type} '{name}'"
        })
    
    # Staleness checks (only if there's a docstring)
    if has_doc:
        issues.extend(check_param_staleness(docstring, params, language))
        issues.extend(check_return_staleness(docstring, returns, language))
        
        # Check for TODO/FIXME in docstring
        for marker in ['TODO', 'FIXME', 'XXX', 'HACK']:
            if marker in docstring.upper():
                issues.append({
                    'severity': 'info',
                    'type': 'incomplete_doc',
                    'message': f"Documentation contains {marker}"
                })
                break
        
        # Check doc quality (very short docs)
        if len(docstring.strip()) < 20 and elem_type in ('class', 'function', 'struct', 'trait'):
            issues.append({
                'severity': 'info',
                'type': 'brief_doc',
                'message': "Documentation is very brief"
            })
    
    return {
        'name': name,
        'type': elem_type,
        'line': line,
        'has_doc': has_doc,
        'is_private': is_private,
        'issues': issues
    }


def audit_file(file_data: Dict) -> Dict:
    """Audit a single file's documentation."""
    filepath = file_data.get('filepath', 'unknown')
    language = file_data.get('language', 'unknown')
    elements = file_data.get('elements', [])
    module_doc = file_data.get('module_docstring')
    
    if 'error' in file_data:
        return {
            'filepath': filepath,
            'error': file_data['error'],
            'coverage': 0,
            'elements': []
        }
    
    audited = []
    total_auditable = 0
    documented = 0
    all_issues = []
    stale_count = 0
    
    # Check module-level doc (Python only)
    if not module_doc and language == 'python':
        all_issues.append({
            'severity': 'info',
            'line': 1,
            'type': 'missing_module_doc',
            'message': 'No module-level docstring'
        })
    
    for element in elements:
        result = audit_element(element, language)
        
        # Count for coverage (skip private/dunder)
        if not result['is_private']:
            name = element.get('name', '')
            if not (name.startswith('__') and name.endswith('__') and name != '__init__'):
                total_auditable += 1
                if result['has_doc']:
                    documented += 1
        
        # Collect issues
        for issue in result['issues']:
            issue['line'] = result['line']
            issue['element'] = f"{result['type']} {result['name']}"
            all_issues.append(issue)
            
            if 'stale' in issue.get('type', ''):
                stale_count += 1
        
        audited.append(result)
        
        # Audit methods within classes
        for method in element.get('methods', []):
            method_result = audit_element(method, language)
            
            if not method_result['is_private']:
                method_name = method.get('name', '')
                if not (method_name.startswith('__') and method_name.endswith('__')):
                    total_auditable += 1
                    if method_result['has_doc']:
                        documented += 1
            
            for issue in method_result['issues']:
                issue['line'] = method_result['line']
                issue['element'] = f"method {element['name']}.{method_result['name']}"
                all_issues.append(issue)
                
                if 'stale' in issue.get('type', ''):
                    stale_count += 1
    
    coverage = (documented / total_auditable * 100) if total_auditable > 0 else 100
    
    return {
        'filepath': filepath,
        'language': language,
        'coverage': round(coverage, 1),
        'documented': documented,
        'total': total_auditable,
        'stale_docs': stale_count,
        'issues': all_issues
    }


def audit_analysis(analysis: Dict) -> Dict:
    """Audit a full analysis result."""
    files = analysis.get('files', [])
    if not files and 'elements' in analysis:
        files = [analysis]
    
    results = []
    total_elements = 0
    total_documented = 0
    total_stale = 0
    total_issues = {'warning': 0, 'info': 0}
    
    for file_data in files:
        result = audit_file(file_data)
        results.append(result)
        
        total_elements += result.get('total', 0)
        total_documented += result.get('documented', 0)
        total_stale += result.get('stale_docs', 0)
        
        for issue in result.get('issues', []):
            sev = issue.get('severity', 'info')
            if sev in total_issues:
                total_issues[sev] += 1
    
    overall_coverage = (total_documented / total_elements * 100) if total_elements > 0 else 100
    
    # Health score: coverage - stale penalty
    health_score = max(0, overall_coverage - (total_stale * 2))
    
    return {
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_files': len(results),
            'total_elements': total_elements,
            'documented_elements': total_documented,
            'coverage': round(overall_coverage, 1),
            'stale_docs': total_stale,
            'health_score': round(health_score, 1),
            'issues': total_issues
        },
        'files': results
    }


def format_markdown(report: Dict) -> str:
    """Format report as Markdown."""
    summary = report['summary']
    
    # Health indicator
    if summary['health_score'] >= 80:
        health_icon = '🟢'
    elif summary['health_score'] >= 60:
        health_icon = '🟡'
    else:
        health_icon = '🔴'
    
    lines = [
        "# Documentation Audit Report",
        "",
        f"**Generated:** {report['timestamp'][:19]}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Files | {summary['total_files']} |",
        f"| Elements | {summary['total_elements']} |",
        f"| Documented | {summary['documented_elements']} |",
        f"| **Coverage** | **{summary['coverage']}%** |",
        f"| Stale Docs | {summary['stale_docs']} ⚠️ |",
        f"| **Health Score** | **{summary['health_score']}%** {health_icon} |",
        f"| Warnings | {summary['issues']['warning']} |",
        "",
        "## Files",
        ""
    ]
    
    for file_result in report['files']:
        filepath = Path(file_result['filepath']).name
        coverage = file_result.get('coverage', 0)
        stale = file_result.get('stale_docs', 0)
        issues = file_result.get('issues', [])
        
        # Coverage indicator
        if coverage >= 80:
            indicator = "✅"
        elif coverage >= 50:
            indicator = "⚠️"
        else:
            indicator = "❌"
        
        stale_warning = f" (⚠️ {stale} stale)" if stale > 0 else ""
        
        lines.append(f"### {indicator} `{filepath}` — {coverage}%{stale_warning}")
        lines.append("")
        
        if file_result.get('error'):
            lines.append(f"**Error:** {file_result['error']}")
            lines.append("")
            continue
        
        if issues:
            # Group by type
            stale_issues = [i for i in issues if 'stale' in i.get('type', '')]
            missing_issues = [i for i in issues if 'missing' in i.get('type', '')]
            other_issues = [i for i in issues if 'stale' not in i.get('type', '') and 'missing' not in i.get('type', '')]
            
            if stale_issues:
                lines.append("**Stale documentation:**")
                for issue in stale_issues[:5]:
                    lines.append(f"- ⚠️ Line {issue['line']}: {issue['message']}")
                lines.append("")
            
            if missing_issues:
                lines.append("**Missing documentation:**")
                for issue in missing_issues[:5]:
                    sev = "⚠️" if issue['severity'] == 'warning' else "ℹ️"
                    lines.append(f"- {sev} Line {issue['line']}: {issue['element']}")
                if len(missing_issues) > 5:
                    lines.append(f"- ... and {len(missing_issues) - 5} more")
                lines.append("")
        else:
            lines.append("No issues found. ✓")
            lines.append("")
    
    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: audit.py <analysis.json> [--format json|markdown] [--output file]", file=sys.stderr)
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_format = 'json'
    output_file = None
    
    if '--format' in sys.argv:
        output_format = sys.argv[sys.argv.index('--format') + 1]
    if '--output' in sys.argv:
        output_file = sys.argv[sys.argv.index('--output') + 1]
    
    try:
        with open(input_file, 'r') as f:
            analysis = json.load(f)
    except Exception as e:
        print(f"Error reading {input_file}: {e}", file=sys.stderr)
        sys.exit(1)
    
    report = audit_analysis(analysis)
    
    if output_format == 'markdown':
        output = format_markdown(report)
    else:
        output = json.dumps(report, indent=2)
    
    if output_file:
        Path(output_file).write_text(output, encoding='utf-8')
        print(f"Audit report written to {output_file}")
    else:
        print(output)


if __name__ == "__main__":
    main()
