"""
Subtree taxonomy guardrail: tests must not live in mu/tools/ or mu/scripts/.

Tests belong under mu/tests/ (organized by domain). The only exceptions
are fixtures, testdata, and conftest.py files used by the tools/scripts
themselves.

This guard prevents future drift back to pre-governance state where
22 test files accumulated under mu/scripts/tests/.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

# Directories where test files must NOT appear.
FORBIDDEN_TEST_DIRS = ["mu/tools", "mu/scripts"]

# Subdirectory names that are exempt (fixtures, testdata, conftest).
EXEMPT_BASENAMES = {"conftest.py"}
EXEMPT_DIRS = {"fixtures", "testdata"}


def _find_test_files_in(git_prefix: str) -> list[str]:
    """Find tracked test_*.py files under a git path prefix."""
    result = subprocess.run(
        ["git", "ls-files", f"{git_prefix}/"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    violations = []
    for path in result.stdout.strip().splitlines():
        if not path:
            continue
        name = path.rsplit("/", 1)[-1]
        # Only flag test_*.py files
        if not name.startswith("test_") or not name.endswith(".py"):
            continue
        # Exempt if inside a fixtures/ or testdata/ subdirectory
        parts = path.split("/")
        if any(p in EXEMPT_DIRS for p in parts):
            continue
        # Exempt specific basenames
        if name in EXEMPT_BASENAMES:
            continue
        violations.append(path)
    return violations


class TestSubtreeTaxonomyGuard:
    """Prevent test files from accumulating in tools/ or scripts/."""

    def test_no_tests_in_mu_tools(self):
        """Test files must not live under mu/tools/."""
        violations = _find_test_files_in("mu/tools")
        assert not violations, (
            "Test files found under mu/tools/ — move them to mu/tests/.\n"
            "Tests belong under mu/tests/ (organized by domain).\n"
            f"Violations: {violations}"
        )

    def test_no_tests_in_mu_scripts(self):
        """Test files must not live under mu/scripts/."""
        violations = _find_test_files_in("mu/scripts")
        assert not violations, (
            "Test files found under mu/scripts/ — move them to mu/tests/.\n"
            "Tests belong under mu/tests/ (organized by domain).\n"
            f"Violations: {violations}"
        )

    def test_no_root_level_fuzzers(self):
        """Fuzzer test files (test_*_fuzzer.py) must not be at mu/tests/ root level."""
        result = subprocess.run(
            ["git", "ls-files", "mu/tests/"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        violations = []
        for path in result.stdout.strip().splitlines():
            if not path:
                continue
            # Only check root-level files (no subdirectory)
            parts = path.split("/")
            if len(parts) != 3:  # mu/tests/filename.py = 3 parts
                continue
            name = parts[2]
            if name.endswith("_fuzzer.py") and name.startswith("test_"):
                violations.append(path)
        assert not violations, (
            "Fuzzer test files found at mu/tests/ root level.\n"
            "Move *_fuzzer.py files to mu/tests/fuzz/ for organization.\n"
            f"Violations: {violations}"
        )
