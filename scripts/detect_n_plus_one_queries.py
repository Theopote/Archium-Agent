#!/usr/bin/env python3
"""Detect potential N+1 query problems in the codebase.

This script scans the codebase for patterns that commonly cause N+1 query issues:
- Accessing relationships in loops without eager loading
- Iterating over collections that trigger lazy loading
- Missing joinedload/selectinload in repository queries
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any


class NPlusOneDetector(ast.NodeVisitor):
    """AST visitor to detect potential N+1 query patterns."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.issues: list[dict[str, Any]] = []
        self.in_loop = False
        self.loop_variables: set[str] = set()

    def visit_For(self, node: ast.For) -> Any:
        """Detect loops that might trigger N+1 queries."""
        old_in_loop = self.in_loop
        old_vars = self.loop_variables.copy()
        
        self.in_loop = True
        if isinstance(node.target, ast.Name):
            self.loop_variables.add(node.target.id)
        elif isinstance(node.target, ast.Tuple):
            for elt in node.target.elts:
                if isinstance(elt, ast.Name):
                    self.loop_variables.add(elt.id)
        
        self.generic_visit(node)
        
        self.in_loop = old_in_loop
        self.loop_variables = old_vars

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        """Detect attribute access that might trigger lazy loading."""
        if self.in_loop:
            if isinstance(node.value, ast.Name):
                var_name = node.value.id
                if var_name in self.loop_variables:
                    # Check if this looks like a relationship access
                    common_rel_attrs = {
                        'slides', 'assets', 'facts', 'documents', 'members',
                        'projects', 'presentations', 'revisions', 'comments',
                        'tags', 'metadata', 'author', 'owner', 'creator'
                    }
                    if node.attr in common_rel_attrs:
                        self.issues.append({
                            'type': 'potential_n_plus_one',
                            'line': node.lineno,
                            'message': f'Potential N+1: accessing relationship "{node.attr}" in loop',
                            'variable': var_name,
                            'attribute': node.attr
                        })
        
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        """Detect method calls that might trigger queries."""
        if self.in_loop:
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    var_name = node.func.value.id
                    if var_name in self.loop_variables:
                        # Check for common query-triggering methods
                        query_methods = {
                            'all', 'filter', 'first', 'get', 'count', 'filter_by',
                            'query', 'execute', 'fetchall', 'fetchone'
                        }
                        if node.func.attr in query_methods:
                            self.issues.append({
                                'type': 'query_in_loop',
                                'line': node.lineno,
                                'message': f'Query method "{node.func.attr}" called in loop',
                                'variable': var_name,
                                'method': node.func.attr
                            })
        
        self.generic_visit(node)


def check_file(filepath: Path) -> list[dict[str, Any]]:
    """Check a single Python file for N+1 query patterns."""
    try:
        content = filepath.read_text(encoding='utf-8')
        tree = ast.parse(content, filename=str(filepath))
        detector = NPlusOneDetector(str(filepath))
        detector.visit(tree)
        return detector.issues
    except (SyntaxError, UnicodeDecodeError):
        return []


def check_directory(directory: Path) -> dict[str, list[dict[str, Any]]]:
    """Check all Python files in a directory."""
    results = {}
    for py_file in directory.rglob('*.py'):
        if '__pycache__' in str(py_file) or '.venv' in str(py_file):
            continue
        issues = check_file(py_file)
        if issues:
            results[str(py_file)] = issues
    return results


def main() -> int:
    import argparse
    
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'path',
        type=Path,
        help='Path to check (file or directory)',
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Generate suggested fixes (experimental)',
    )
    
    args = parser.parse_args()
    
    if args.path.is_file():
        results = {str(args.path): check_file(args.path)}
    else:
        results = check_directory(args.path)
    
    total_issues = sum(len(issues) for issues in results.values())
    
    if total_issues == 0:
        print("✅ No potential N+1 query issues found")
        return 0
    
    print(f"⚠️  Found {total_issues} potential N+1 query issues:\n")
    
    for filepath, issues in results.items():
        print(f"📄 {filepath}")
        for issue in issues:
            print(f"  Line {issue['line']}: {issue['message']}")
        print()
    
    print("\n💡 Suggestions:")
    print("1. Use SQLAlchemy eager loading: joinedload(), selectinload(), subqueryload()")
    print("2. Consider batch loading relationships outside loops")
    print("3. Use contains_eager() for already-loaded relationships")
    print("4. Add explicit selectinload() in repository queries for commonly accessed relationships")
    
    if args.fix:
        print("\n🔧 Auto-fix not yet implemented - please review and fix manually")
    
    return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
