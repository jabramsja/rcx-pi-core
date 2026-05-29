#!/usr/bin/env python3
"""AST-based checker for underscored imports from rcx_pi in tests/.

Replaces the grep-based check which could be bypassed by multiline imports:
    from rcx_pi.selfhost.step_mu import (
        _private_function,   # grep misses this
    )

Usage:
  python3 tools/check_underscore_imports.py
  python3 tools/check_underscore_imports.py <root> <file>...
Exit 0: clean, Exit 1: violations found
"""

import ast
import sys
from pathlib import Path

# Walk up from this file to find repo root (directory containing .git).
# Fail-closed: if no .git found, ROOT stays at filesystem root and
# SCAN_DIRS won't match anything, so the checker reports 0 (safe default).
_THIS = Path(__file__).resolve()
ROOT = _THIS.parent
while not (ROOT / ".git").exists() and ROOT != ROOT.parent:
    ROOT = ROOT.parent

# Files allowed to import underscored names from rcx_pi
FILE_ALLOWLIST = frozenset({
    "test_type_tag_security.py",
})

SCAN_DIRS = ("tests", "mu/tests")


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


def scan(root: Path) -> list[str]:
    """Scan all Python files under SCAN_DIRS below ``root``."""
    all_violations: list[str] = []
    seen_files: set[Path] = set()
    for scan_dir in SCAN_DIRS:
        dirpath = root / scan_dir
        if not dirpath.exists():
            continue
        for pyfile in sorted(dirpath.rglob("*.py")):
            if "__pycache__" in str(pyfile):
                continue
            resolved = pyfile.resolve(strict=False)
            if resolved in seen_files:
                continue
            seen_files.add(resolved)
            all_violations.extend(check_file(pyfile))
    return all_violations


def _is_scan_path(root: Path, filepath: Path) -> bool:
    try:
        rel_path = filepath.resolve(strict=False).relative_to(root)
    except ValueError:
        return False
    for scan_dir in SCAN_DIRS:
        scan_parts = Path(scan_dir).parts
        if rel_path.parts[:len(scan_parts)] == scan_parts:
            return True
    return False


def scan_files(root: Path, files: list[str]) -> list[str]:
    """Scan only the requested Python files under SCAN_DIRS below ``root``."""
    all_violations: list[str] = []
    seen_files: set[Path] = set()
    for file_arg in files:
        filepath = Path(file_arg)
        if not filepath.is_absolute():
            filepath = root / filepath
        if filepath.suffix != ".py":
            continue
        if "__pycache__" in filepath.parts:
            continue
        resolved = filepath.resolve(strict=False)
        if resolved in seen_files:
            continue
        if not _is_scan_path(root, filepath):
            continue
        seen_files.add(resolved)
        all_violations.extend(check_file(filepath))
    return all_violations


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    root = Path(argv[1]).resolve() if len(argv) > 1 else ROOT
    all_violations = scan_files(root, argv[2:]) if len(argv) > 2 else scan(root)

    if all_violations:
        print("ERROR: Found underscored imports from rcx_pi:")
        for v in all_violations:
            print(v)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
