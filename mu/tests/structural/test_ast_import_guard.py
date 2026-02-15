"""
Structural guard: `import ast` must not appear in runtime code paths.

AST is allowed in tools/ and tests/ (static analysis, linting, test helpers).
It must NEVER appear in rcx_pi/ (the runtime kernel and selfhost layer).

This prevents accidental coupling of runtime behavior to Python's AST module,
which would violate structural purity (the kernel must be substrate-independent).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent

# Directories where `import ast` is forbidden (runtime code)
FORBIDDEN_DIRS = [
    REPO_ROOT / "rcx_pi",
]

# Directories where `import ast` is allowed (tooling + tests)
ALLOWED_DIRS = [
    REPO_ROOT / "tools",
    REPO_ROOT / "tests",
    REPO_ROOT / "scripts",
]

AST_IMPORT_PATTERN = re.compile(r"^\s*(import\s+ast|from\s+ast\s+import)\b", re.MULTILINE)


class TestNoAstInRuntime:
    """Fail if any runtime file imports the ast module."""

    def test_no_ast_import_in_runtime(self):
        """Runtime code (rcx_pi/) must not import ast."""
        violations = []
        for forbidden_dir in FORBIDDEN_DIRS:
            if not forbidden_dir.exists():
                continue
            for py_file in sorted(forbidden_dir.rglob("*.py")):
                lines = py_file.read_text(encoding="utf-8").splitlines()
                for line_num, line in enumerate(lines, 1):
                    if AST_IMPORT_PATTERN.match(line):
                        rel = py_file.relative_to(REPO_ROOT)
                        violations.append(f"  {rel}:{line_num}: {line.strip()}")

        assert not violations, (
            "Runtime code must not import ast (violates structural purity).\n"
            "AST is allowed in tools/ and tests/ only.\n"
            "Violations:\n" + "\n".join(violations)
        )

    def test_allowed_dirs_have_ast_imports(self):
        """Sanity check: at least one allowed file uses ast (test not vacuous)."""
        found = False
        for allowed_dir in ALLOWED_DIRS:
            if not allowed_dir.exists():
                continue
            for py_file in allowed_dir.rglob("*.py"):
                content = py_file.read_text(encoding="utf-8")
                if AST_IMPORT_PATTERN.search(content):
                    found = True
                    break
            if found:
                break
        assert found, (
            "Expected at least one file in tools/ or tests/ to import ast. "
            "If all ast usage was removed, this guard test should be updated."
        )
