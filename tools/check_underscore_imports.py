#!/usr/bin/env python3
"""AST-based checker for underscored imports from rcx_pi in tests/ and archive/prototypes/.

Replaces the grep-based check which could be bypassed by multiline imports:
    from rcx_pi.selfhost.step_mu import (
        _private_function,   # grep misses this
    )

Usage: python3 tools/check_underscore_imports.py
Exit 0: clean, Exit 1: violations found
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Files allowed to import underscored names from rcx_pi
FILE_ALLOWLIST = frozenset({
    "test_type_tag_security.py",
})

SCAN_DIRS = ["tests", "archive/prototypes"]


def check_file(filepath: Path) -> list[str]:
    """Return list of violation messages for a single file."""
    if filepath.name in FILE_ALLOWLIST:
        return []

    try:
        source = filepath.read_text()
    except (OSError, UnicodeDecodeError):
        return []

    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    source_lines = source.splitlines()
    violations = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if not node.module or not node.module.startswith("rcx_pi"):
            continue
        for alias in node.names:
            name = alias.name
            asname = alias.asname
            # Flag if the imported name starts with _ OR the alias starts with _
            # Catches: `from rcx_pi... import _foo` and `from rcx_pi... import foo as _bar`
            flagged_name = None
            if name.startswith("_"):
                flagged_name = name
            elif asname and asname.startswith("_"):
                flagged_name = f"{name} as {asname}"
            if not flagged_name:
                continue
            # Check if the import line has # ANTICHEAT_OK
            lineno = alias.lineno if hasattr(alias, 'lineno') else node.lineno
            if lineno <= len(source_lines):
                line_text = source_lines[lineno - 1]
                if "# ANTICHEAT_OK" in line_text:
                    continue
            violations.append(
                f"  {filepath}:{lineno}: from {node.module} import {flagged_name}"
            )

    return violations


def main() -> int:
    all_violations = []

    for scan_dir in SCAN_DIRS:
        dirpath = ROOT / scan_dir
        if not dirpath.exists():
            continue
        for pyfile in sorted(dirpath.rglob("*.py")):
            if "__pycache__" in str(pyfile):
                continue
            all_violations.extend(check_file(pyfile))

    if all_violations:
        print("ERROR: Found underscored imports from rcx_pi:")
        for v in all_violations:
            print(v)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
