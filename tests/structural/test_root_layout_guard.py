"""
Root-layout guardrail: prevent root directory sprawl and artifact re-tracking.

Only allowlisted directories may exist at the repo root as tracked git
directories. This catches accidental introduction of new top-level
folders that create "root noise" and undermine the mu-centric layout.

Generated artifacts that are gitignored must not be re-tracked.

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


# Generated artifacts that must NEVER be tracked.
# These are gitignored output files that have been accidentally committed
# in the past. This guardrail prevents re-tracking via git add -f.
FORBIDDEN_TRACKED_ARTIFACTS: frozenset[str] = frozenset({
    ".rcx_manifest.json",
    "RCX_MINIMAL_SPINE_MANIFEST.json",
    "RCX_MINIMAL_SPINE_MANIFEST.md",
})


class TestGeneratedArtifactGuard:
    """Prevent re-tracking of generated manifest artifacts."""

    def test_no_generated_manifests_tracked(self):
        """Generated manifests must not be tracked (gitignored artifacts)."""
        result = subprocess.run(
            ["git", "ls-files"] + sorted(FORBIDDEN_TRACKED_ARTIFACTS),
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        tracked = set(result.stdout.strip().splitlines()) if result.stdout.strip() else set()

        assert not tracked, (
            "Generated manifest artifacts are tracked in git but should not be.\n"
            "These are gitignored generated output — untrack with: "
            "git rm --cached <file>\n"
            f"Violations: {sorted(tracked)}"
        )
