#!/usr/bin/env python3
"""
RCX Structural Linter - Catches RCX-specific violations at save time.

Checks for:
- Python lists [] where linked lists expected (in Mu-handling code)
- Missing @host_debt markers on functions using Python semantics
- == comparison on Mu values (should use mu_equal)
- Python for/while loops in kernel code (should use kernel iteration)
- isinstance() calls in structural code

Usage:
    python tools/docs/structural_lint.py                    # Check all files
    python tools/docs/structural_lint.py rcx_pi/selfhost/  # Check specific path
    python tools/docs/structural_lint.py --watch           # Watch mode (continuous)
    python tools/docs/structural_lint.py --fix-hints       # Show suggested fixes
"""

import argparse
import ast
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Generator


@dataclass
class Violation:
    """A linting violation."""
    file: str
    line: int
    col: int
    code: str
    message: str
    severity: str  # "error", "warning", "info"
    fix_hint: str | None = None


# Files/patterns to check
MU_HANDLING_PATHS = [
    "rcx_pi/selfhost/",
    "rcx_pi/eval_seed.py",
    "rcx_pi/mu_type.py",
]

# Files to skip
SKIP_PATTERNS = [
    "test_",
    "__pycache__",
    ".pyc",
    "conftest.py",
]


class StructuralLinter(ast.NodeVisitor):
    """AST-based linter for RCX structural violations."""

    def __init__(self, filename: str, source: str):
        self.filename = filename
        self.source = source
        self.lines = source.split("\n")
        self.violations: list[Violation] = []
        self.in_function: str | None = None
        self.has_host_debt_marker = False
        self.function_uses_host_semantics = False
        self.host_semantic_locations: list[tuple[int, str]] = []

    def add_violation(
        self,
        node: ast.AST,
        code: str,
        message: str,
        severity: str = "warning",
        fix_hint: str | None = None,
    ):
        self.violations.append(Violation(
            file=self.filename,
            line=node.lineno,
            col=node.col_offset,
            code=code,
            message=message,
            severity=severity,
            fix_hint=fix_hint,
        ))

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Track function context and check for @host_debt markers."""
        # Check for @host_debt decorator
        self.has_host_debt_marker = any(
            (isinstance(d, ast.Name) and d.id == "host_debt") or
            (isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "host_debt")
            for d in node.decorator_list
        )

        self.in_function = node.name
        self.function_uses_host_semantics = False
        self.host_semantic_locations = []

        # Visit function body
        self.generic_visit(node)

        # After visiting, check if function uses host semantics without marker
        if self.function_uses_host_semantics and not self.has_host_debt_marker:
            if self._is_mu_handling_function(node):
                locations = ", ".join(f"L{l}" for l, _ in self.host_semantic_locations[:3])
                self.add_violation(
                    node,
                    "RCX001",
                    f"Function '{node.name}' uses host semantics ({locations}) without @host_debt marker",
                    severity="warning",
                    fix_hint=f"Add @host_debt('L?', 'reason') decorator to {node.name}",
                )

        self.in_function = None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Handle async functions the same way."""
        self.visit_FunctionDef(node)  # type: ignore

    def _is_mu_handling_function(self, node: ast.FunctionDef) -> bool:
        """Check if function likely handles Mu values based on name/args."""
        mu_indicators = ["mu", "projection", "kernel", "step", "match", "subst", "binding"]
        name_lower = node.name.lower()
        return any(ind in name_lower for ind in mu_indicators)

    def visit_List(self, node: ast.List):
        """Check for Python lists in suspicious contexts."""
        # Only flag in Mu-handling code and if it looks like data structure creation
        if len(node.elts) > 0 and self._in_mu_context():
            # Check if this looks like a linked list should be used
            # Heuristic: list with dicts that have 'head'/'tail' or similar keys nearby
            source_line = self.lines[node.lineno - 1] if node.lineno <= len(self.lines) else ""

            # Skip obvious non-Mu contexts
            if any(skip in source_line for skip in ["import", "from", "def ", "class ", "@"]):
                return

            # Flag if we're in a return statement or assignment in Mu code
            if self._in_mu_context() and not self._is_test_context():
                # Only flag if list contains dicts (potential Mu structures)
                has_dicts = any(isinstance(e, ast.Dict) for e in node.elts)
                if has_dicts:
                    self.add_violation(
                        node,
                        "RCX002",
                        "Python list [] may need to be linked list {head:..., tail:...}",
                        severity="info",
                        fix_hint="Use mu_list_from_python() or explicit {\"head\": x, \"tail\": ...}",
                    )

        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare):
        """Check for == comparison that might be on Mu values."""
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.NotEq)):
            if self._in_mu_context():
                source_line = self.lines[node.lineno - 1] if node.lineno <= len(self.lines) else ""
                # Check if comparing variables that look like Mu
                left_name = self._get_name(node.left)
                right_name = self._get_name(node.comparators[0]) if node.comparators else None

                mu_indicators = ["mu", "state", "term", "value", "pattern", "binding", "projection"]
                if left_name and any(ind in left_name.lower() for ind in mu_indicators):
                    self.add_violation(
                        node,
                        "RCX003",
                        f"Using == on potential Mu value '{left_name}'",
                        severity="info",
                        fix_hint="Use mu_equal(a, b) for structural comparison",
                    )

        self.generic_visit(node)

    def visit_For(self, node: ast.For):
        """Flag Python for loops in kernel code."""
        if self._in_kernel_context():
            self.function_uses_host_semantics = True
            self.host_semantic_locations.append((node.lineno, "for loop"))

            self.add_violation(
                node,
                "RCX004",
                "Python for loop in kernel code - should use kernel iteration",
                severity="warning",
                fix_hint="Use linked list traversal with step() projections",
            )

        self.generic_visit(node)

    def visit_While(self, node: ast.While):
        """Flag Python while loops in kernel code."""
        if self._in_kernel_context():
            self.function_uses_host_semantics = True
            self.host_semantic_locations.append((node.lineno, "while loop"))

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Check for isinstance() and other host operations."""
        func_name = self._get_call_name(node)

        if func_name == "isinstance" and self._in_mu_context():
            self.function_uses_host_semantics = True
            self.host_semantic_locations.append((node.lineno, "isinstance"))

            # Only warn if checking Mu-like types
            if len(node.args) >= 2:
                type_arg = node.args[1]
                type_name = self._get_name(type_arg)
                python_types = ["dict", "list", "str", "int", "bool", "float", "tuple"]
                if type_name and type_name.lower() in python_types:
                    self.add_violation(
                        node,
                        "RCX005",
                        f"isinstance({self._get_name(node.args[0])}, {type_name}) in Mu code",
                        severity="info",
                        fix_hint="Use structural pattern matching instead of type checking",
                    )

        self.generic_visit(node)

    def _get_name(self, node: ast.AST) -> str | None:
        """Get the name from a Name node or similar."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return None

    def _get_call_name(self, node: ast.Call) -> str | None:
        """Get the function name from a Call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

    def _in_mu_context(self) -> bool:
        """Check if we're in a file that handles Mu values."""
        return any(p in self.filename for p in MU_HANDLING_PATHS)

    def _in_kernel_context(self) -> bool:
        """Check if we're in kernel-specific code."""
        return "step_mu" in self.filename or "kernel" in (self.in_function or "").lower()

    def _is_test_context(self) -> bool:
        """Check if we're in test code."""
        return "test" in self.filename.lower()


def lint_file(filepath: str) -> list[Violation]:
    """Lint a single file."""
    try:
        with open(filepath, "r") as f:
            source = f.read()
    except Exception as e:
        return [Violation(
            file=filepath,
            line=0,
            col=0,
            code="RCX000",
            message=f"Could not read file: {e}",
            severity="error",
        )]

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [Violation(
            file=filepath,
            line=e.lineno or 0,
            col=e.offset or 0,
            code="RCX000",
            message=f"Syntax error: {e.msg}",
            severity="error",
        )]

    linter = StructuralLinter(filepath, source)
    linter.visit(tree)
    return linter.violations


def find_python_files(path: str) -> Generator[str, None, None]:
    """Find Python files to lint."""
    path_obj = Path(path)

    if path_obj.is_file():
        if path_obj.suffix == ".py":
            yield str(path_obj)
        return

    for root, dirs, files in os.walk(path_obj):
        # Skip hidden and cache directories
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

        for f in files:
            if not f.endswith(".py"):
                continue
            if any(skip in f for skip in SKIP_PATTERNS):
                continue

            filepath = os.path.join(root, f)
            # Only lint Mu-handling code
            if any(p in filepath for p in MU_HANDLING_PATHS):
                yield filepath


def format_violation(v: Violation, show_fix: bool = False) -> str:
    """Format a violation for output."""
    severity_icons = {"error": "🔴", "warning": "🟡", "info": "⚪"}
    icon = severity_icons.get(v.severity, "⚪")

    msg = f"{icon} {v.file}:{v.line}:{v.col} [{v.code}] {v.message}"
    if show_fix and v.fix_hint:
        msg += f"\n   💡 Fix: {v.fix_hint}"
    return msg


def main():
    parser = argparse.ArgumentParser(description="RCX Structural Linter")
    parser.add_argument(
        "paths",
        nargs="*",
        default=["rcx_pi/"],
        help="Files or directories to lint",
    )
    parser.add_argument(
        "--fix-hints",
        action="store_true",
        help="Show fix suggestions",
    )
    parser.add_argument(
        "--severity",
        choices=["error", "warning", "info"],
        default="info",
        help="Minimum severity to report",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch mode (requires watchdog)",
    )

    args = parser.parse_args()

    severity_order = {"error": 0, "warning": 1, "info": 2}
    min_severity = severity_order[args.severity]

    all_violations = []

    for path in args.paths:
        for filepath in find_python_files(path):
            violations = lint_file(filepath)
            # Filter by severity
            violations = [v for v in violations if severity_order[v.severity] <= min_severity]
            all_violations.extend(violations)

    if args.json:
        import json
        print(json.dumps([
            {
                "file": v.file,
                "line": v.line,
                "col": v.col,
                "code": v.code,
                "message": v.message,
                "severity": v.severity,
                "fix_hint": v.fix_hint,
            }
            for v in all_violations
        ], indent=2))
    else:
        if not all_violations:
            print("✅ No structural violations found")
            sys.exit(0)

        # Group by file
        by_file: dict[str, list[Violation]] = {}
        for v in all_violations:
            if v.file not in by_file:
                by_file[v.file] = []
            by_file[v.file].append(v)

        print(f"Found {len(all_violations)} violation(s) in {len(by_file)} file(s):\n")

        for filepath, violations in sorted(by_file.items()):
            print(f"📄 {filepath}")
            for v in sorted(violations, key=lambda x: x.line):
                print(f"   {format_violation(v, show_fix=args.fix_hints)}")
            print()

        # Summary
        errors = sum(1 for v in all_violations if v.severity == "error")
        warnings = sum(1 for v in all_violations if v.severity == "warning")
        infos = sum(1 for v in all_violations if v.severity == "info")

        print(f"Summary: 🔴 {errors} errors, 🟡 {warnings} warnings, ⚪ {infos} info")

        if errors > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
