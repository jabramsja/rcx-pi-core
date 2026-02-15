"""
Root-layout guardrail: prevent root directory sprawl.

Only allowlisted directories may exist at the repo root as tracked git
directories. This catches accidental introduction of new top-level
folders that create "root noise" and undermine the mu-centric layout.

Untracked/gitignored directories (e.g. __pycache__, sandbox_runs/) are
excluded — this test only checks what git tracks.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Allowlisted root directories (tracked by git).
# Add new entries here ONLY with a governance reason.
ALLOWED_ROOT_DIRS: frozenset[str] = frozenset({
    # Infrastructure
    ".claude",
    ".githooks",
    ".github",
    # Active code
    "mu",
    "rcx_pi",
    "tests",
    "tools",
    "scripts",
    # Documentation
    "docs",
    "roadmap",
    # Archive + legacy
    "archive",
    ".rcx_library",
})


class TestRootLayoutGuard:
    """Prevent uncontrolled root directory sprawl."""

    def test_no_new_root_directories(self):
        """All tracked root directories must be in the allowlist."""
        result = subprocess.run(
            ["git", "ls-tree", "--name-only", "HEAD", "-d"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        tracked_dirs = set(result.stdout.strip().splitlines())

        violations = sorted(tracked_dirs - ALLOWED_ROOT_DIRS)
        assert not violations, (
            "New root directories detected that are not in the allowlist.\n"
            "If intentional, add them to ALLOWED_ROOT_DIRS in "
            "tests/structural/test_root_layout_guard.py.\n"
            f"Violations: {violations}"
        )

    def test_allowlisted_dirs_still_tracked(self):
        """Ensure allowlist doesn't go stale with phantom entries."""
        result = subprocess.run(
            ["git", "ls-tree", "--name-only", "HEAD", "-d"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        tracked_dirs = set(result.stdout.strip().splitlines())

        phantom = sorted(ALLOWED_ROOT_DIRS - tracked_dirs)
        assert not phantom, (
            "Allowlisted root directories no longer tracked by git.\n"
            "Remove stale entries from ALLOWED_ROOT_DIRS in "
            "tests/structural/test_root_layout_guard.py.\n"
            f"Phantom entries: {phantom}"
        )
