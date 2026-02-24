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

from tests.repo_root import REPO_ROOT

# Allowlisted root directories and symlinks (tracked by git).
# Add new entries here ONLY with a governance reason.
ALLOWED_ROOT_DIRS: frozenset[str] = frozenset({
    # Infrastructure
    ".claude",
    ".githooks",
    ".github",
    # Active code (canonical)
    "mu",
    # Active docs (visible roadmap set)
    "roadmap",
    # Backward-compat symlinks (→ mu/)
    "rcx_pi",   # → mu/host/python/rcx_pi
    "tests",    # → mu/tests
    "tools",    # → mu/tools
    "scripts",  # → mu/scripts
    # Archive + legacy
    "archive",
    ".rcx_library",
    # L4 governance artifacts (force-tracked despite reports/ gitignore)
    "reports",
})


def _parse_dirs_and_symlinks(ls_tree_output: str) -> set[str]:
    """Parse git ls-tree output, returning names of directories and symlinks.

    Modes: 040000 = tree (directory), 120000 = symlink blob.
    """
    entries = set()
    for line in ls_tree_output.strip().splitlines():
        parts = line.split(None, 3)
        if len(parts) >= 4 and parts[0] in ("040000", "120000"):
            entries.add(parts[3])
    return entries


def _get_tracked_root_dirs() -> set[str]:
    """Get root-level tracked directories and symlinks from git.

    Prefers the index via ``git ls-files -s`` (lock-free read), which includes
    staged renames/moves without requiring ``git write-tree`` index locks.
    Falls back to HEAD tree parsing when index read fails.
    """
    index = subprocess.run(
        ["git", "ls-files", "-s"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    if index.returncode == 0 and index.stdout.strip():
        entries: set[str] = set()
        for line in index.stdout.strip().splitlines():
            parts = line.split(None, 3)
            if len(parts) < 4:
                continue
            mode, path = parts[0], parts[3]
            if "/" in path:
                entries.add(path.split("/", 1)[0])
            elif mode == "120000":
                entries.add(path)
        if entries:
            return entries

    # Fallback to HEAD tree entries
    result = subprocess.run(
        ["git", "ls-tree", "HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    return _parse_dirs_and_symlinks(result.stdout)


class TestRootLayoutGuard:
    """Prevent uncontrolled root directory sprawl."""

    def test_no_new_root_directories(self):
        """All tracked root directories must be in the allowlist."""
        tracked_dirs = _get_tracked_root_dirs()

        violations = sorted(tracked_dirs - ALLOWED_ROOT_DIRS)
        assert not violations, (
            "New root directories detected that are not in the allowlist.\n"
            "If intentional, add them to ALLOWED_ROOT_DIRS in "
            "tests/structural/test_root_layout_guard.py.\n"
            f"Violations: {violations}"
        )

    def test_allowlisted_dirs_still_tracked(self):
        """Ensure allowlist doesn't go stale with phantom entries."""
        tracked_dirs = _get_tracked_root_dirs()

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
