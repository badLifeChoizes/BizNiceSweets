#!/usr/bin/env python3
"""
Style Checker
Validates code against style rules (detected or configured).
Reports issues without modifying files.
"""

import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class StyleIssue:
    file: str
    line: int
    column: int
    rule: str
    message: str
    severity: str = 'warning'  # error, warning, info
    suggestion: Optional[str] = None


class PythonStyleChecker:
    """Check Python code against style rules."""
    
    def __init__(self, rules: Dict):
        self.rules = rules
        self.issues: List[StyleIssue] = []
    
    def check_file(self, filepath: Path) -> List[StyleIssue]:
        """Check a single Python file."""
        self.issues = []
        
        try:
            source = filepath.read_text(encoding='utf-8')
            lines = source.split('\n')
        except:
            return []
        
        # Line-level checks
        self._check_lines(filepath, lines)
        
        # AST checks
        try:
            tree = ast.parse(source)
            self._check_ast(filepath, tree, source)
        except SyntaxError as e:
            self.issues.append(StyleIssue(
                file=str(filepath),
                line=e.lineno or 1,
                column=e.offset or 0,
                rule='syntax',
                message=f"Syntax error: {e.msg}",
                severity='error'
            ))
        
        return self.issues
    
    def _check_lines(self, filepath: Path, lines: List[str]) -> None:
        """Check line-level style issues."""
        max_length = self.rules.get('line_length', 100)
        expected_indent = self.rules.get('indentation', '4-space')
        expected_quotes = self.rules.get('quotes', 'double')
        
        for i, line in enumerate(lines, 1):
            # Line length
            if len(line) > max_length:
                self.issues.append(StyleIssue(
                    file=str(filepath),
                    line=i,
                    column=max_length,
                    rule='line-length',
                    message=f"Line too long ({len(line)} > {max_length})",
                    severity='warning'
                ))
            
            # Trailing whitespace
            if line != line.rstrip():
                self.issues.append(StyleIssue(
                    file=str(filepath),
                    line=i,
                    column=len(line.rstrip()),
                    rule='trailing-whitespace',
                    message="Trailing whitespace",
                    severity='info'
                ))
            
            # Indentation
            if line and line[0].isspace():
                indent = len(line) - len(line.lstrip())
                if expected_indent == '4-space' and indent % 4 != 0:
                    self.issues.append(StyleIssue(
                        file=str(filepath),
                        line=i,
                        column=0,
                        rule='indentation',
                        message=f"Indentation should be multiple of 4 (got {indent})",
                        severity='warning'
                    ))
                elif expected_indent == 'tab' and ' ' in line[:indent]:
                    self.issues.append(StyleIssue(
                        file=str(filepath),
                        line=i,
                        column=0,
                        rule='indentation',
                        message="Use tabs for indentation",
                        severity='warning'
                    ))
            
            # Quote consistency (simple check)
            if expected_quotes == 'single':
                # Check for double quotes not in f-strings or containing single quotes
                if re.search(r'(?<!f)"[^"\']*"', line):
                    self.issues.append(StyleIssue(
                        file=str(filepath),
                        line=i,
                        column=line.find('"'),
                        rule='quotes',
                        message="Use single quotes for strings",
                        severity='info'
                    ))
            elif expected_quotes == 'double':
                # Check for single quotes not containing double quotes
                if re.search(r"'[^'\"]*'", line) and '"' not in line:
                    pass  # Don't flag - single quotes are often used for various reasons
    
    def _check_ast(self, filepath: Path, tree: ast.AST, source: str) -> None:
        """Check AST-level style issues."""
        naming_rules = self.rules.get('naming', {})
        require_docstrings = self.rules.get('require_docstrings', False)
        require_type_hints = self.rules.get('require_type_hints', False)
        
        for node in ast.walk(tree):
            # Function naming
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                expected = naming_rules.get('functions', 'snake_case')
                if not self._check_naming(node.name, expected):
                    self.issues.append(StyleIssue(
                        file=str(filepath),
                        line=node.lineno,
                        column=node.col_offset,
                        rule='naming-convention',
                        message=f"Function '{node.name}' should use {expected}",
                        severity='warning',
                        suggestion=self._convert_name(node.name, expected)
                    ))
                
                # Docstring check
                if require_docstrings and not node.name.startswith('_'):
                    has_docstring = (
                        node.body and 
                        isinstance(node.body[0], ast.Expr) and
                        isinstance(node.body[0].value, ast.Constant) and
                        isinstance(node.body[0].value.value, str)
                    )
                    if not has_docstring:
                        self.issues.append(StyleIssue(
                            file=str(filepath),
                            line=node.lineno,
                            column=node.col_offset,
                            rule='missing-docstring',
                            message=f"Function '{node.name}' missing docstring",
                            severity='warning'
                        ))
                
                # Type hints check
                if require_type_hints and not node.name.startswith('_'):
                    missing_hints = []
                    for arg in node.args.args:
                        if arg.arg not in ('self', 'cls') and not arg.annotation:
                            missing_hints.append(arg.arg)
                    if not node.returns and node.name != '__init__':
                        missing_hints.append('return')
                    
                    if missing_hints:
                        self.issues.append(StyleIssue(
                            file=str(filepath),
                            line=node.lineno,
                            column=node.col_offset,
                            rule='missing-type-hints',
                            message=f"Missing type hints for: {', '.join(missing_hints)}",
                            severity='info'
                        ))
            
            # Class naming
            elif isinstance(node, ast.ClassDef):
                expected = naming_rules.get('classes', 'PascalCase')
                if not self._check_naming(node.name, expected):
                    self.issues.append(StyleIssue(
                        file=str(filepath),
                        line=node.lineno,
                        column=node.col_offset,
                        rule='naming-convention',
                        message=f"Class '{node.name}' should use {expected}",
                        severity='warning',
                        suggestion=self._convert_name(node.name, expected)
                    ))
            
            # Constant naming
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # Heuristic: module-level CAPS = constant
                        if target.id.isupper():
                            expected = naming_rules.get('constants', 'SCREAMING_SNAKE_CASE')
                            if not self._check_naming(target.id, expected):
                                self.issues.append(StyleIssue(
                                    file=str(filepath),
                                    line=node.lineno,
                                    column=node.col_offset,
                                    rule='naming-convention',
                                    message=f"Constant '{target.id}' should use {expected}",
                                    severity='info'
                                ))
    
    def _check_naming(self, name: str, convention: str) -> bool:
        """Check if name follows convention."""
        if name.startswith('_'):
            return True  # Skip private names
        
        if convention == 'snake_case':
            return bool(re.match(r'^[a-z][a-z0-9_]*$', name))
        elif convention == 'PascalCase':
            return bool(re.match(r'^[A-Z][a-zA-Z0-9]*$', name))
        elif convention == 'camelCase':
            return bool(re.match(r'^[a-z][a-zA-Z0-9]*$', name))
        elif convention == 'SCREAMING_SNAKE_CASE':
            return bool(re.match(r'^[A-Z][A-Z0-9_]*$', name))
        
        return True
    
    def _convert_name(self, name: str, convention: str) -> Optional[str]:
        """Suggest converted name."""
        # Split on case boundaries and underscores
        parts = re.split(r'_|(?<=[a-z])(?=[A-Z])', name)
        parts = [p for p in parts if p]
        
        if convention == 'snake_case':
            return '_'.join(p.lower() for p in parts)
        elif convention == 'PascalCase':
            return ''.join(p.capitalize() for p in parts)
        elif convention == 'camelCase':
            if not parts:
                return name
            return parts[0].lower() + ''.join(p.capitalize() for p in parts[1:])
        elif convention == 'SCREAMING_SNAKE_CASE':
            return '_'.join(p.upper() for p in parts)
        
        return None


class JavaScriptStyleChecker:
    """Check JavaScript/TypeScript code against style rules."""
    
    def __init__(self, rules: Dict):
        self.rules = rules
        self.issues: List[StyleIssue] = []
    
    def check_file(self, filepath: Path) -> List[StyleIssue]:
        """Check a single JS/TS file."""
        self.issues = []
        
        try:
            source = filepath.read_text(encoding='utf-8')
            lines = source.split('\n')
        except:
            return []
        
        self._check_lines(filepath, lines)
        
        return self.issues
    
    def _check_lines(self, filepath: Path, lines: List[str]) -> None:
        """Check line-level style issues."""
        max_length = self.rules.get('line_length', 100)
        expected_quotes = self.rules.get('quotes', 'single')
        expected_semi = self.rules.get('semicolons', 'yes')
        expected_var = self.rules.get('variable_declaration', 'const')
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Line length
            if len(line) > max_length:
                self.issues.append(StyleIssue(
                    file=str(filepath),
                    line=i,
                    column=max_length,
                    rule='line-length',
                    message=f"Line too long ({len(line)} > {max_length})",
                    severity='warning'
                ))
            
            # Trailing whitespace
            if line != line.rstrip():
                self.issues.append(StyleIssue(
                    file=str(filepath),
                    line=i,
                    column=len(line.rstrip()),
                    rule='trailing-whitespace',
                    message="Trailing whitespace",
                    severity='info'
                ))
            
            # Semicolons
            if stripped and not stripped.startswith('//'):
                ends_with_semi = stripped.endswith(';')
                should_have_semi = not stripped.endswith(('{', '}', ',', '(', ':', '*/'))
                
                if expected_semi == 'yes' and should_have_semi and not ends_with_semi:
                    # Simple heuristic - might have false positives
                    if re.match(r'^(const|let|var|return|throw|import|export)\s', stripped):
                        self.issues.append(StyleIssue(
                            file=str(filepath),
                            line=i,
                            column=len(stripped),
                            rule='semicolons',
                            message="Missing semicolon",
                            severity='warning'
                        ))
                elif expected_semi == 'no' and ends_with_semi:
                    self.issues.append(StyleIssue(
                        file=str(filepath),
                        line=i,
                        column=len(stripped) - 1,
                        rule='semicolons',
                        message="Unnecessary semicolon",
                        severity='warning'
                    ))
            
            # var usage
            if expected_var in ('const', 'let') and re.search(r'\bvar\s+', line):
                self.issues.append(StyleIssue(
                    file=str(filepath),
                    line=i,
                    column=line.find('var'),
                    rule='no-var',
                    message=f"Use '{expected_var}' instead of 'var'",
                    severity='warning'
                ))
            
            # console.log in production code
            if 'console.log' in line and 'test' not in str(filepath).lower():
                self.issues.append(StyleIssue(
                    file=str(filepath),
                    line=i,
                    column=line.find('console.log'),
                    rule='no-console',
                    message="Avoid console.log in production code",
                    severity='info'
                ))


def check_project(project_path: str, rules: Optional[Dict] = None) -> Dict:
    """Check style across a project."""
    root = Path(project_path).resolve()
    
    if rules is None:
        # Try to load rules from project
        rules_file = root / '.style-rules.json'
        if rules_file.exists():
            with open(rules_file) as f:
                rules = json.load(f)
        else:
            # Use sensible defaults
            rules = {
                'python': {
                    'line_length': 100,
                    'indentation': '4-space',
                    'quotes': 'double',
                    'naming': {
                        'functions': 'snake_case',
                        'classes': 'PascalCase',
                        'constants': 'SCREAMING_SNAKE_CASE',
                    },
                    'require_docstrings': False,
                    'require_type_hints': False,
                },
                'javascript': {
                    'line_length': 100,
                    'quotes': 'single',
                    'semicolons': 'yes',
                    'variable_declaration': 'const',
                }
            }
    
    all_issues = []
    files_checked = {'python': 0, 'javascript': 0}
    
    # Check Python files
    py_checker = PythonStyleChecker(rules.get('python', {}))
    for pyfile in root.rglob('*.py'):
        if '__pycache__' in str(pyfile) or '.venv' in str(pyfile):
            continue
        issues = py_checker.check_file(pyfile)
        all_issues.extend(issues)
        files_checked['python'] += 1
    
    # Check JS/TS files
    js_checker = JavaScriptStyleChecker(rules.get('javascript', {}))
    for ext in ['*.js', '*.jsx', '*.ts', '*.tsx']:
        for jsfile in root.rglob(ext):
            if 'node_modules' in str(jsfile) or 'dist' in str(jsfile):
                continue
            issues = js_checker.check_file(jsfile)
            all_issues.extend(issues)
            files_checked['javascript'] += 1
    
    # Group by severity
    by_severity = {'error': 0, 'warning': 0, 'info': 0}
    for issue in all_issues:
        by_severity[issue.severity] += 1
    
    return {
        'project': root.name,
        'files_checked': files_checked,
        'total_issues': len(all_issues),
        'by_severity': by_severity,
        'issues': [
            {
                'file': issue.file,
                'line': issue.line,
                'column': issue.column,
                'rule': issue.rule,
                'message': issue.message,
                'severity': issue.severity,
                'suggestion': issue.suggestion,
            }
            for issue in all_issues
        ]
    }


def format_report(result: Dict, format: str = 'text') -> str:
    """Format the check results."""
    if format == 'json':
        return json.dumps(result, indent=2)
    
    lines = [
        f"Style Check: {result['project']}",
        f"Files: {result['files_checked']}",
        f"Issues: {result['total_issues']} ({result['by_severity']['error']} errors, {result['by_severity']['warning']} warnings)",
        ""
    ]
    
    # Group by file
    by_file = {}
    for issue in result['issues']:
        if issue['file'] not in by_file:
            by_file[issue['file']] = []
        by_file[issue['file']].append(issue)
    
    for filepath, issues in sorted(by_file.items()):
        lines.append(f"\n{Path(filepath).name}:")
        for issue in sorted(issues, key=lambda x: x['line']):
            severity_icon = {'error': '❌', 'warning': '⚠️', 'info': 'ℹ️'}[issue['severity']]
            lines.append(f"  {severity_icon} L{issue['line']}: [{issue['rule']}] {issue['message']}")
            if issue.get('suggestion'):
                lines.append(f"      → Suggestion: {issue['suggestion']}")
    
    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: check_style.py <project_path> [--rules file.json] [--format json|text]", file=sys.stderr)
        sys.exit(1)
    
    project_path = sys.argv[1]
    rules = None
    output_format = 'text'
    
    if '--rules' in sys.argv:
        rules_file = sys.argv[sys.argv.index('--rules') + 1]
        with open(rules_file) as f:
            rules = json.load(f)
    
    if '--format' in sys.argv:
        output_format = sys.argv[sys.argv.index('--format') + 1]
    
    result = check_project(project_path, rules)
    print(format_report(result, output_format))
    
    # Exit with error if there are errors
    if result['by_severity']['error'] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
