#!/usr/bin/env python3
"""AST-based vacuous-assertion checker for test-theater detection.

Replaces the six TEXT-based vacuous-assertion `check_pattern` greps in
`tools/checks/check_test_theater.sh` (`assert True`, `assert 1`,
`assertTrue(True)`, `assertEqual(True, True)` / `(1, 1)` / `(0, 0)`).

Motivation (BUG #1): the legacy greps matched those tokens wherever they
appeared in the file text, INCLUDING inside string-literal test FIXTURES
(e.g. `f.write_text(textwrap.dedent('''... assert True ...'''))` that
exercises a classifier). That is a false positive (observed 2026-06-03,
PR #1065, worked around with THEATER_OK). The AST visitor walks
`ast.Assert` / `ast.Call` nodes only, so a vacuous assertion that lives
inside a string literal or docstring is represented as an `ast.Constant`
(str) leaf and is inherently invisible -- fixture strings are ignored,
which is the whole point.

Detection scope (vacuous assertions ONLY -- the gate's other checks
(self-comparison, empty bodies, skip-without-reason, commented-out
assertions, TODO/FIXME) are PRESERVED in the wrapper and NOT subsumed):
  - `ast.Assert` whose test is a constant-truthy literal
    (`assert True` / `assert 1` / any always-true constant).
  - `assertTrue(<constant-truthy>)` -- e.g. `assertTrue(True)`.
  - `assertEqual(c, c)` with two identical same-type constant literals
    -- e.g. `assertEqual(True, True)` / `(1, 1)` / `(0, 0)` -- a tautology.

A trailing `# THEATER_OK: reason` on any line spanned by the offending
node whitelists it (parity with the wrapper's `grep -v THEATER_OK`).

CLI CONTRACT (this is the bridge-round-2 fix -- see BUG #3):
  argv[1] is the directory to scan DIRECTLY; it is walked recursively for
  `*.py` files. It is NOT treated as a repo ROOT under which hard-coded
  `tests/` + `mu/tests/` are re-discovered. Mirroring
  `check_private_attr_access.py`'s `scan(root)` literally (argv-as-root +
  `SCAN_DIRS` re-discovery) under the wrapper call
  `check_test_theater.py "$TESTS_DIR"` (TESTS_DIR=tests) would search
  `tests/tests` + `tests/mu/tests`, match nothing, and exit 0 CLEAN -- a
  SCAN-NOTHING FAIL-OPEN. This linter mirrors ONLY the exemplar's
  NodeVisitor + per-file try-except STRUCTURE, not its path-discovery.

Usage:
  `python3 tools/checks/linters/check_test_theater.py <dir-to-scan>`

EXIT-CODE CONTRACT (detection is BY EXIT CODE, not stdout-presence -- the
wrapper captures rc with a `set -e`-safe guard and fails closed on any
nonzero):
  0  -- scanned cleanly, no vacuous findings.
  1  -- scanned, real vacuous finding(s) found (printed `file:line` to
        stdout).
  >=2 -- EXECUTION ERROR (could NOT scan): no scan target, a target that
        resolves to ZERO `*.py` files (scanning nothing FAILS closed and
        never exits 0), an unreadable/unparseable file (per-file try-except
        turns it into an execution error, NOT a silent skip), or any other
        internal failure. Belt-and-suspenders fail-closure.
"""
import ast
import sys
from pathlib import Path


def _call_name(func: ast.expr) -> str | None:
    """Return the called name for `assertTrue(...)` / `self.assertEqual(...)`."""
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


class _VacuousAssertionVisitor(ast.NodeVisitor):
    """Collect vacuous (always-true) assertions as REAL statements.

    Only `ast.Assert` / `ast.Call` nodes are inspected, so tokens inside
    string literals / docstrings (leaf `ast.Constant` str) are never
    flagged.
    """

    def __init__(self, filepath: Path, source_lines: list[str]) -> None:
        self.filepath = filepath
        self.source_lines = source_lines
        self.findings: list[str] = []

    def _theater_ok(self, node: ast.AST) -> bool:
        start = getattr(node, "lineno", 0) or 0
        end = getattr(node, "end_lineno", start) or start
        for lineno in range(start, end + 1):
            if 1 <= lineno <= len(self.source_lines):
                if "THEATER_OK" in self.source_lines[lineno - 1]:
                    return True
        return False

    def _record(self, node: ast.AST, reason: str) -> None:
        if self._theater_ok(node):
            return
        lineno = getattr(node, "lineno", 0)
        self.findings.append(f"{self.filepath}:{lineno}: {reason}")

    def visit_Assert(self, node: ast.Assert) -> None:
        test = node.test
        if isinstance(test, ast.Constant) and bool(test.value):
            self._record(node, f"assert {test.value!r} - vacuous assertion (always true)")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        if name == "assertTrue":
            if (
                len(node.args) == 1
                and isinstance(node.args[0], ast.Constant)
                and bool(node.args[0].value)
            ):
                self._record(node, "assertTrue(<always-true>) - tautology")
        elif name == "assertEqual":
            if len(node.args) == 2 and all(
                isinstance(arg, ast.Constant) for arg in node.args
            ):
                left, right = node.args
                if left.value == right.value and type(left.value) is type(right.value):
                    self._record(
                        node,
                        f"assertEqual({left.value!r}, {right.value!r}) - tautology",
                    )
        self.generic_visit(node)


def check_file(filepath: Path) -> list[str]:
    """Return vacuous-assertion findings for one file.

    Raises on read/parse failure; the caller turns that into an EXECUTION
    ERROR (exit >=2) rather than a silent skip -- a file the linter cannot
    scan must FAIL the gate, never be treated as clean.
    """
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filepath))
    visitor = _VacuousAssertionVisitor(filepath, source.splitlines())
    visitor.visit(tree)
    return visitor.findings


def _iter_py_files(target: Path) -> list[Path]:
    """Collect `*.py` files at ``target`` DIRECTLY (recursive walk of a dir).

    argv[1] is the directory to scan -- NOT a root under which `tests/` /
    `mu/tests/` are re-discovered (see CLI CONTRACT in the module
    docstring). A single `*.py` file is also accepted for convenience.
    """
    if target.is_dir():
        return [
            p
            for p in sorted(target.rglob("*.py"))
            if "__pycache__" not in p.parts
        ]
    if target.is_file() and target.suffix == ".py":
        return [target]
    return []


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(
            "ERROR: check_test_theater.py requires a directory to scan (argv[1])",
            file=sys.stderr,
        )
        return 2
    target = Path(argv[1])
    if not target.exists():
        print(f"ERROR: scan target does not exist: {target}", file=sys.stderr)
        return 2

    py_files = _iter_py_files(target)
    if not py_files:
        print(
            f"ERROR: no *.py files under scan target: {target} "
            "(scanning nothing FAILS closed -- never exit 0)",
            file=sys.stderr,
        )
        return 2

    findings: list[str] = []
    scan_errors: list[str] = []
    for filepath in py_files:
        try:
            findings.extend(check_file(filepath))
        except (OSError, UnicodeDecodeError, SyntaxError, ValueError) as exc:
            scan_errors.append(f"{filepath}: {type(exc).__name__}: {exc}")

    if scan_errors:
        print(
            "ERROR: check_test_theater.py could not scan (fail-closed):",
            file=sys.stderr,
        )
        for err in scan_errors:
            print(f"  {err}", file=sys.stderr)
        return 2

    if findings:
        print("  ✗ THEATER: vacuous/tautological assertion(s) - always true, verify nothing")
        for finding in findings:
            print(f"      {finding}")
        return 1

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as exc:  # noqa: BLE001 -- fail-closed: any runtime error is an execution error
        print(f"ERROR: check_test_theater.py crashed: {exc}", file=sys.stderr)
        sys.exit(2)
