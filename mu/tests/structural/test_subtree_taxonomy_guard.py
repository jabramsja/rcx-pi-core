"""
Subtree taxonomy guardrail: tests must not live in mu/tools/ or mu/scripts/.

Tests belong under mu/tests/ (organized by domain). The only exceptions
are fixtures, testdata, and conftest.py files used by the tools/scripts
themselves.

This guard prevents future drift back to pre-governance state where
22 test files accumulated under mu/scripts/tests/.

Wave2 addition: root-level test file ratchet prevents new test files
from accumulating at mu/tests/ root. New tests go into subdirectories:
fuzz/, structural/, scripts/, docs/, engine/, parity/, integration/, cli/.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.repo_root import REPO_ROOT

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


# Ratchet ceiling: root-level test_*.py count can only decrease.
# Wave1 baseline: 74. Wave2 moved 50 → ceiling 24. Wave3 moved 6 → ceiling 18.
# Wave4 moved 17 → ceiling 1 (only test_agent_tooling_smoke.py blocked).
# New test files MUST go into subdirectories.
ROOT_LEVEL_TEST_FILE_CEILING = 1


def _count_root_level_tests(repo_root: Path) -> list[str]:
    """Return root-level test_*.py files under mu/tests/."""
    result = subprocess.run(
        ["git", "ls-files", "mu/tests/"],
        capture_output=True, text=True, cwd=repo_root,
    )
    return [
        path for path in result.stdout.strip().splitlines()
        if path
        and len(path.split("/")) == 3
        and path.split("/")[2].startswith("test_")
        and path.split("/")[2].endswith(".py")
    ]


class TestRootLevelTestOrganization:
    """Prevent root-level test file sprawl via ratchet ceiling."""

    def test_root_level_file_count_cap(self):
        """Root-level test file count must not exceed the ratchet ceiling."""
        root_tests = _count_root_level_tests(REPO_ROOT)
        assert len(root_tests) <= ROOT_LEVEL_TEST_FILE_CEILING, (
            f"Root-level test file count increased: {len(root_tests)} > "
            f"{ROOT_LEVEL_TEST_FILE_CEILING}\n"
            "New test files must be added to mu/tests/<subdirectory>/.\n"
            "Available: fuzz/, structural/, scripts/, docs/, engine/, "
            "parity/, integration/, cli/, stress/\n"
            f"Files at root:\n" + "\n".join(sorted(root_tests))
        )


# Ratchet ceiling: root-level script files can only decrease.
# Wave4 organized 20 scripts → orbit/, mutation/, world/, snapshot/, utils/.
# Only __init__.py and green_gate.sh should remain at root.
ROOT_LEVEL_SCRIPT_FILE_CEILING = 2


def _count_root_level_scripts(repo_root: Path) -> list[str]:
    """Return root-level .sh/.py files under mu/scripts/ (excl subdirs)."""
    result = subprocess.run(
        ["git", "ls-files", "mu/scripts/"],
        capture_output=True, text=True, cwd=repo_root,
    )
    return [
        path for path in result.stdout.strip().splitlines()
        if path
        and len(path.split("/")) == 3
        and not path.endswith("__pycache__")
    ]


class TestRootLevelScriptOrganization:
    """Prevent root-level script file sprawl via ratchet ceiling."""

    def test_root_level_script_count_cap(self):
        """Root-level script file count must not exceed the ratchet ceiling."""
        root_scripts = _count_root_level_scripts(REPO_ROOT)
        assert len(root_scripts) <= ROOT_LEVEL_SCRIPT_FILE_CEILING, (
            f"Root-level script file count increased: {len(root_scripts)} > "
            f"{ROOT_LEVEL_SCRIPT_FILE_CEILING}\n"
            "New scripts must be added to mu/scripts/<subdirectory>/.\n"
            "Available: orbit/, mutation/, world/, snapshot/, utils/\n"
            f"Files at root:\n" + "\n".join(sorted(root_scripts))
        )
