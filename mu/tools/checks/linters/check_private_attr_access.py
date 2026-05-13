#!/usr/bin/env python3
"""AST-based checker for private-attr access in tests/ and mu/tests/.

Replaces the grep-based scan at `tools/audits/audit_fast.sh:113` and
`tools/audits/audit_all.sh:157` which was docstring-blind: the legacy
regex `\\._[a-zA-Z0-9]+` matched private-attr references appearing
inside Python docstrings (as prose citing a target helper by name),
raising a false positive.

The AST visitor walks `ast.Attribute` nodes only, so string-literal
docstring contents (represented as `ast.Constant(str)` inside
`ast.Expr`) are inherently invisible. Dunder attributes (`__init__`
etc.) match Python's magic-method convention and are NOT private, so
they are skipped, mirroring the legacy regex behavior (legacy pattern
required `[a-zA-Z0-9]+` after the underscore, so `.__init__` with its
leading `__` was not matched).

Allowlist parity with legacy grep (6 cases):
  - `self._foo` instance attribute access
  - `sys._getframe` / `sys._current_frames` stdlib helpers
  - lines containing `# ANTICHEAT_OK`
  - `_getframe` calls on a line containing `CONTRABAND_OK`
  - `test_contraband_detection.py` (grounding tests for contraband guard)
  - `__pycache__` directory (skipped during file discovery)

Usage: `python3 tools/checks/linters/check_private_attr_access.py`
Exit 0: clean. Exit 1: violations found (one per line to stdout).
"""
import ast
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
ROOT = _THIS.parent
while not (ROOT / ".git").exists() and ROOT != ROOT.parent:
    ROOT = ROOT.parent

FILE_ALLOWLIST = frozenset({
    "test_contraband_detection.py",
})

SCAN_DIRS = ("tests", "mu/tests")

_SYS_PRIVATES = frozenset({"_getframe", "_current_frames"})


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__") and len(name) >= 4


def _is_allowed(node: ast.Attribute, source_lines: list[str]) -> bool:
    value = node.value
    if isinstance(value, ast.Name) and value.id == "self":
        return True
    if (
        isinstance(value, ast.Name)
        and value.id == "sys"
        and node.attr in _SYS_PRIVATES
    ):
        return True
    lineno = getattr(node, "lineno", 0)
    if 1 <= lineno <= len(source_lines):
        line_text = source_lines[lineno - 1]
        if "# ANTICHEAT_OK" in line_text:
            return True
        if "_getframe" in node.attr and "CONTRABAND_OK" in line_text:
            return True
    return False


def check_file(filepath: Path) -> list[str]:
    """Return a list of violation messages for a single Python file."""
    if filepath.name in FILE_ALLOWLIST:
        return []
    try:
        source = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []
    source_lines = source.splitlines()
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        attr = node.attr
        if not attr.startswith("_"):
            continue
        if _is_dunder(attr):
            continue
        if _is_allowed(node, source_lines):
            continue
        lineno = getattr(node, "lineno", 0)
        violations.append(f"  {filepath}:{lineno}: .{attr}")
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
            if "__pycache__" in pyfile.parts:
                continue
            resolved = pyfile.resolve()
            if resolved in seen_files:
                continue
            seen_files.add(resolved)
            all_violations.extend(check_file(pyfile))
    return all_violations


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else ROOT
    violations = scan(root)
    if violations:
        print("ERROR: Found private attr access in tests/ or mu/tests/:")
        for v in violations:
            print(v)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
