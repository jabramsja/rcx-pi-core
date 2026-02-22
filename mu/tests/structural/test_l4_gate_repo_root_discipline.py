"""
Source lock: L4 gate test files must use the shared repo_root helper.

Prevents reintroduction of fragile Path(__file__).parents[N] patterns
in mu/tests/l4_gates/.  All gate files that reference REPO_ROOT must
import it from tests.repo_root (which walks upward to pyproject.toml).

Usage:
    PYTHONHASHSEED=0 pytest tests/structural/test_l4_gate_repo_root_discipline.py -v
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

L4_GATES_DIR = REPO_ROOT / "mu" / "tests" / "l4_gates"
SHARED_HELPER = "tests.repo_root"

# Patterns that indicate fragile root resolution
FRAGILE_PATTERNS = [
    re.compile(r"Path\s*\(\s*__file__\s*\)\.parents\s*\["),
    re.compile(r"Path\s*\(\s*__file__\s*\)\.resolve\(\)\.parents\s*\["),
    re.compile(r'os\.path\.dirname\s*\(\s*os\.path\.abspath\s*\(\s*__file__\s*\)\s*\)'),
]


def _get_gate_test_files() -> list[Path]:
    """Return all test_*.py files under mu/tests/l4_gates/."""
    return sorted(L4_GATES_DIR.glob("test_*.py"))


class TestNoFragilePathResolution:
    """L4 gate files must not use Path(__file__).parents[N] for root resolution."""

    def test_gate_dir_exists(self):
        """mu/tests/l4_gates/ must exist."""
        assert L4_GATES_DIR.is_dir(), f"L4 gates directory not found: {L4_GATES_DIR}"

    def test_gate_files_exist(self):
        """At least one gate test file must exist."""
        files = _get_gate_test_files()
        assert len(files) > 0, "No test_*.py files found in mu/tests/l4_gates/"

    def test_no_fragile_parents_pattern(self):
        """No gate file may use Path(__file__).parents[N] for root resolution."""
        violations = []
        for path in _get_gate_test_files():
            source = path.read_text()
            for pattern in FRAGILE_PATTERNS:
                matches = pattern.findall(source)
                if matches:
                    violations.append(f"{path.name}: {matches[0]}")
        assert not violations, (
            "Fragile root resolution found in L4 gate files.\n"
            "Use `from tests.repo_root import REPO_ROOT` instead.\n"
            f"Violations:\n  " + "\n  ".join(violations)
        )


class TestRepoRootImportDiscipline:
    """Gate files using REPO_ROOT must import from the shared helper."""

    def test_repo_root_users_import_shared_helper(self):
        """Every gate file referencing REPO_ROOT must import from tests.repo_root."""
        violations = []
        for path in _get_gate_test_files():
            source = path.read_text()
            if "REPO_ROOT" not in source:
                continue
            if f"from {SHARED_HELPER} import REPO_ROOT" not in source:
                violations.append(path.name)
        assert not violations, (
            "L4 gate files use REPO_ROOT but do not import from tests.repo_root.\n"
            "Add: from tests.repo_root import REPO_ROOT\n"
            f"Violations: {violations}"
        )

    def test_no_sys_path_insert_for_repo_root(self):
        """Gate files must not use sys.path.insert to set up REPO_ROOT."""
        violations = []
        pattern = re.compile(r"sys\.path\.insert\s*\(\s*0\s*,\s*str\s*\(\s*REPO_ROOT\s*\)")
        for path in _get_gate_test_files():
            source = path.read_text()
            if pattern.search(source):
                violations.append(path.name)
        assert not violations, (
            "L4 gate files use sys.path.insert(0, str(REPO_ROOT)).\n"
            "The shared tests.repo_root helper handles path setup.\n"
            f"Violations: {violations}"
        )


class TestSharedHelperExists:
    """The shared repo_root helper must exist and export REPO_ROOT."""

    def test_repo_root_module_exists(self):
        """tests/repo_root.py must exist."""
        helper = REPO_ROOT / "tests" / "repo_root.py"
        assert helper.is_file(), f"Shared helper not found: {helper}"

    def test_repo_root_module_exports_repo_root(self):
        """tests/repo_root.py must define REPO_ROOT at module level."""
        helper = REPO_ROOT / "tests" / "repo_root.py"
        source = helper.read_text()
        tree = ast.parse(source)
        top_level_names = {
            node.targets[0].id
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        }
        assert "REPO_ROOT" in top_level_names, (
            "tests/repo_root.py does not define REPO_ROOT at module level"
        )
