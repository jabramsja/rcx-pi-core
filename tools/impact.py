#!/usr/bin/env python3
"""
RCX Impact Analyzer - Shows what's affected by a code change.

Given a file (or file:line), shows:
1. Functions in that file
2. What other files import this file
3. What tests cover this code
4. Downstream impact chain

Usage:
    python tools/impact.py rcx_pi/selfhost/step_mu.py
    python tools/impact.py rcx_pi/selfhost/step_mu.py:50
    python tools/impact.py --full  # Full dependency graph
"""

import argparse
import ast
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator


@dataclass
class FunctionInfo:
    """Info about a function."""
    name: str
    file: str
    line: int
    end_line: int
    calls: list[str] = field(default_factory=list)
    called_by: list[str] = field(default_factory=list)


@dataclass
class FileInfo:
    """Info about a file."""
    path: str
    imports: list[str] = field(default_factory=list)  # What this file imports
    imported_by: list[str] = field(default_factory=list)  # What imports this file
    functions: dict[str, FunctionInfo] = field(default_factory=dict)


class DependencyGraph:
    """Builds and queries a dependency graph of Python files."""

    def __init__(self, root: str = "."):
        self.root = Path(root)
        self.files: dict[str, FileInfo] = {}
        self.module_to_file: dict[str, str] = {}  # "rcx_pi.eval_seed" -> "rcx_pi/eval_seed.py"

    def build(self, paths: list[str] | None = None):
        """Build the dependency graph."""
        if paths is None:
            paths = ["rcx_pi/", "tests/"]

        # Find all Python files
        python_files = []
        for path in paths:
            full_path = self.root / path
            if full_path.is_file():
                python_files.append(str(full_path))
            elif full_path.is_dir():
                for f in full_path.rglob("*.py"):
                    if "__pycache__" not in str(f):
                        python_files.append(str(f))

        # Parse each file
        for filepath in python_files:
            self._parse_file(filepath)

        # Build reverse mappings (imported_by, called_by)
        self._build_reverse_mappings()

    def _parse_file(self, filepath: str):
        """Parse a single Python file."""
        try:
            with open(filepath, "r") as f:
                source = f.read()
            tree = ast.parse(source)
        except Exception:
            return

        rel_path = os.path.relpath(filepath, self.root)
        file_info = FileInfo(path=rel_path)

        # Build module name
        module_name = rel_path.replace("/", ".").replace(".py", "")
        self.module_to_file[module_name] = rel_path

        # Extract imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    file_info.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    file_info.imports.append(node.module)

        # Extract functions and their calls
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_info = FunctionInfo(
                    name=node.name,
                    file=rel_path,
                    line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                )

                # Find function calls within this function
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        call_name = self._get_call_name(child)
                        if call_name:
                            func_info.calls.append(call_name)

                file_info.functions[node.name] = func_info

        self.files[rel_path] = file_info

    def _get_call_name(self, node: ast.Call) -> str | None:
        """Get the name of a called function."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

    def _build_reverse_mappings(self):
        """Build imported_by and called_by relationships."""
        # Build imported_by
        for filepath, file_info in self.files.items():
            for imp in file_info.imports:
                # Find the file that provides this import
                if imp in self.module_to_file:
                    target_file = self.module_to_file[imp]
                    if target_file in self.files:
                        self.files[target_file].imported_by.append(filepath)

        # Build called_by (within same file for now)
        for filepath, file_info in self.files.items():
            func_names = set(file_info.functions.keys())
            for func_name, func_info in file_info.functions.items():
                for call in func_info.calls:
                    if call in func_names and call != func_name:
                        if call in file_info.functions:
                            file_info.functions[call].called_by.append(func_name)

    def get_function_at_line(self, filepath: str, line: int) -> FunctionInfo | None:
        """Get the function containing the given line."""
        rel_path = os.path.relpath(filepath, self.root)
        if rel_path not in self.files:
            return None

        for func_info in self.files[rel_path].functions.values():
            if func_info.line <= line <= func_info.end_line:
                return func_info
        return None

    def get_tests_for_file(self, filepath: str) -> list[str]:
        """Find tests that likely cover a file."""
        rel_path = os.path.relpath(filepath, self.root)
        base_name = Path(rel_path).stem  # e.g., "step_mu" from "rcx_pi/selfhost/step_mu.py"

        tests = []
        for file_path, file_info in self.files.items():
            if not file_path.startswith("tests/"):
                continue

            # Check if test file imports the target
            for imp in file_info.imports:
                if base_name in imp or rel_path.replace("/", ".").replace(".py", "") in imp:
                    tests.append(file_path)
                    break

            # Also check by naming convention
            if f"test_{base_name}" in file_path or f"test_{base_name.replace('_', '')}" in file_path:
                if file_path not in tests:
                    tests.append(file_path)

        return tests

    def analyze_impact(self, filepath: str, line: int | None = None) -> dict:
        """Analyze the impact of changing a file or line."""
        rel_path = os.path.relpath(filepath, self.root)

        result = {
            "target": rel_path,
            "target_line": line,
            "function": None,
            "functions_in_file": [],
            "imported_by": [],
            "tests": [],
            "downstream_files": [],
        }

        if rel_path not in self.files:
            return result

        file_info = self.files[rel_path]

        # Functions in file
        result["functions_in_file"] = [
            {"name": f.name, "lines": f"{f.line}-{f.end_line}"}
            for f in sorted(file_info.functions.values(), key=lambda x: x.line)
        ]

        # If line specified, find specific function
        if line:
            func = self.get_function_at_line(filepath, line)
            if func:
                result["function"] = {
                    "name": func.name,
                    "lines": f"{func.line}-{func.end_line}",
                    "calls": func.calls[:10],  # Limit
                    "called_by": func.called_by[:10],
                }

        # What imports this file
        result["imported_by"] = file_info.imported_by

        # Tests covering this file
        result["tests"] = self.get_tests_for_file(filepath)

        # Downstream files (transitive imports)
        visited = set()
        to_visit = list(file_info.imported_by)
        while to_visit:
            next_file = to_visit.pop(0)
            if next_file in visited:
                continue
            visited.add(next_file)
            result["downstream_files"].append(next_file)
            if next_file in self.files:
                to_visit.extend(self.files[next_file].imported_by)

        return result


def format_impact_report(impact: dict) -> str:
    """Format impact analysis as readable report."""
    lines = [
        f"═══ Impact Analysis ═══",
        f"",
        f"📄 Target: {impact['target']}"
    ]

    if impact['target_line']:
        lines.append(f"   Line: {impact['target_line']}")

    if impact['function']:
        func = impact['function']
        lines.extend([
            f"",
            f"🎯 Function at line: {func['name']} (lines {func['lines']})",
        ])
        if func['calls']:
            lines.append(f"   Calls: {', '.join(func['calls'][:5])}")
        if func['called_by']:
            lines.append(f"   Called by: {', '.join(func['called_by'][:5])}")

    if impact['functions_in_file']:
        lines.extend([
            f"",
            f"📋 Functions in file ({len(impact['functions_in_file'])}):",
        ])
        for f in impact['functions_in_file'][:10]:
            lines.append(f"   • {f['name']} ({f['lines']})")
        if len(impact['functions_in_file']) > 10:
            lines.append(f"   ... and {len(impact['functions_in_file']) - 10} more")

    if impact['imported_by']:
        lines.extend([
            f"",
            f"📥 Imported by ({len(impact['imported_by'])} files):",
        ])
        for f in impact['imported_by'][:10]:
            lines.append(f"   • {f}")
        if len(impact['imported_by']) > 10:
            lines.append(f"   ... and {len(impact['imported_by']) - 10} more")

    if impact['tests']:
        lines.extend([
            f"",
            f"🧪 Tests covering this ({len(impact['tests'])}):",
        ])
        for t in impact['tests'][:10]:
            lines.append(f"   • {t}")
        if len(impact['tests']) > 10:
            lines.append(f"   ... and {len(impact['tests']) - 10} more")

    if impact['downstream_files']:
        lines.extend([
            f"",
            f"🔗 Downstream impact ({len(impact['downstream_files'])} files):",
        ])
        for f in impact['downstream_files'][:10]:
            lines.append(f"   • {f}")
        if len(impact['downstream_files']) > 10:
            lines.append(f"   ... and {len(impact['downstream_files']) - 10} more")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="RCX Impact Analyzer",
        epilog="Example: python tools/impact.py rcx_pi/selfhost/step_mu.py:50"
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="File path or file:line to analyze",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Show full dependency graph summary",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    # Build graph
    print("Building dependency graph...", file=sys.stderr)
    graph = DependencyGraph()
    graph.build()
    print(f"Analyzed {len(graph.files)} files", file=sys.stderr)

    if args.full:
        # Show summary
        print("\n═══ Dependency Graph Summary ═══\n")

        # Most imported files
        by_imports = sorted(
            graph.files.items(),
            key=lambda x: len(x[1].imported_by),
            reverse=True
        )
        print("Most imported files:")
        for path, info in by_imports[:10]:
            if info.imported_by:
                print(f"  {len(info.imported_by):3d} imports ← {path}")

        # Most functions
        by_funcs = sorted(
            graph.files.items(),
            key=lambda x: len(x[1].functions),
            reverse=True
        )
        print("\nLargest files (by function count):")
        for path, info in by_funcs[:10]:
            if info.functions:
                print(f"  {len(info.functions):3d} functions  {path}")

        return

    if not args.target:
        print("Error: specify a target file or use --full")
        parser.print_help()
        sys.exit(1)

    # Parse target
    if ":" in args.target:
        filepath, line_str = args.target.rsplit(":", 1)
        line = int(line_str)
    else:
        filepath = args.target
        line = None

    # Analyze
    impact = graph.analyze_impact(filepath, line)

    if args.json:
        import json
        print(json.dumps(impact, indent=2))
    else:
        print(format_impact_report(impact))


if __name__ == "__main__":
    main()
