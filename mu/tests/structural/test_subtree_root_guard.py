"""
Subtree root-level file guard: prevent loose file accumulation in mu/ subtrees.

After Wave 6, mu/tools/, mu/tests/, and mu/scripts/ have semantic subdirectories.
New files MUST be placed in the appropriate subdirectory, not at subtree root.

Root-level files are exception-only and must be allowlisted with rationale.
The allowlist count can only stay the same or decrease (ratchet rule).

This test fails CI when:
1. A new file appears at subtree root that is not allowlisted.
2. The allowlist count exceeds the ratchet ceiling.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


# ============================================================================
# Allowlists — add entries ONLY with rationale. Count can only decrease.
# ============================================================================

TOOLS_ROOT_ALLOWED: frozenset[str] = frozenset({
    # Package marker
    "__init__.py",
    # Backward-compat wrappers (exec → subdirectory canonical)
    "agents.sh",
    "audit_all.sh",
    "audit_fast.sh",
    "audit_semantic_purity.sh",
    "debt_dashboard.sh",
    "pr_to_dev.sh",
    "pre-commit-doc-check",
    "pre-push-fast",
})

TESTS_ROOT_ALLOWED: frozenset[str] = frozenset({
    # pytest infrastructure (must be at root)
    "conftest.py",
    # Shared test config/helpers imported by multiple subdirectories
    "fuzzer_config.py",
    "hemisphere_helpers.py",
    "repo_root.py",
    "strategies.py",
})

SCRIPTS_ROOT_ALLOWED: frozenset[str] = frozenset({
    # Package marker
    "__init__.py",
    # Primary CI entry point
    "green_gate.sh",
})

# Ratchet ceilings — can only stay same or decrease (never increase).
# If you need to add a root file, you must remove one first or get founder approval.
TOOLS_RATCHET_CEILING = 9
TESTS_RATCHET_CEILING = 5
SCRIPTS_RATCHET_CEILING = 2


def _get_root_files(subtree: str) -> set[str]:
    """Get git-tracked files at the root of a mu/ subtree (not in subdirectories)."""
    result = subprocess.run(
        ["git", "ls-files", f"mu/{subtree}/"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        return set()

    root_files = set()
    for line in result.stdout.strip().splitlines():
        # Extract path relative to mu/<subtree>/
        rel = line.removeprefix(f"mu/{subtree}/")
        # Root file = no slash in remaining path
        if "/" not in rel:
            root_files.add(rel)
    return root_files


class TestToolsRootGuard:
    """mu/tools/ root must only contain allowlisted files."""

    def test_no_unallowed_root_files(self):
        root_files = _get_root_files("tools")
        violations = sorted(root_files - TOOLS_ROOT_ALLOWED)
        if violations:
            pytest.fail(
                f"Unallowed files at mu/tools/ root:\n"
                + "\n".join(f"  - {f}" for f in violations)
                + "\n\nMove to a subdirectory (audits/, hooks/, runners/, "
                + "analysis/, util/, docs/, checks/) or add to TOOLS_ROOT_ALLOWED "
                + "with rationale in test_subtree_root_guard.py"
            )

    def test_ratchet_ceiling(self):
        root_files = _get_root_files("tools")
        allowed_present = root_files & TOOLS_ROOT_ALLOWED
        count = len(allowed_present)
        assert count <= TOOLS_RATCHET_CEILING, (
            f"mu/tools/ root file count ({count}) exceeds ratchet ceiling "
            f"({TOOLS_RATCHET_CEILING}). Remove files before adding new ones."
        )


class TestTestsRootGuard:
    """mu/tests/ root must only contain allowlisted files."""

    def test_no_unallowed_root_files(self):
        root_files = _get_root_files("tests")
        violations = sorted(root_files - TESTS_ROOT_ALLOWED)
        if violations:
            pytest.fail(
                f"Unallowed files at mu/tests/ root:\n"
                + "\n".join(f"  - {f}" for f in violations)
                + "\n\nMove to a subdirectory (parity/, structural/, tools/, "
                + "docs/, stress/, fixtures/) or add to TESTS_ROOT_ALLOWED "
                + "with rationale in test_subtree_root_guard.py"
            )

    def test_ratchet_ceiling(self):
        root_files = _get_root_files("tests")
        allowed_present = root_files & TESTS_ROOT_ALLOWED
        count = len(allowed_present)
        assert count <= TESTS_RATCHET_CEILING, (
            f"mu/tests/ root file count ({count}) exceeds ratchet ceiling "
            f"({TESTS_RATCHET_CEILING}). Remove files before adding new ones."
        )


class TestScriptsRootGuard:
    """mu/scripts/ root must only contain allowlisted files."""

    def test_no_unallowed_root_files(self):
        root_files = _get_root_files("scripts")
        violations = sorted(root_files - SCRIPTS_ROOT_ALLOWED)
        if violations:
            pytest.fail(
                f"Unallowed files at mu/scripts/ root:\n"
                + "\n".join(f"  - {f}" for f in violations)
                + "\n\nMove to a subdirectory or add to SCRIPTS_ROOT_ALLOWED "
                + "with rationale in test_subtree_root_guard.py"
            )

    def test_ratchet_ceiling(self):
        root_files = _get_root_files("scripts")
        allowed_present = root_files & SCRIPTS_ROOT_ALLOWED
        count = len(allowed_present)
        assert count <= SCRIPTS_RATCHET_CEILING, (
            f"mu/scripts/ root file count ({count}) exceeds ratchet ceiling "
            f"({SCRIPTS_RATCHET_CEILING}). Remove files before adding new ones."
        )


class TestRatchetMeta:
    """Verify ratchet ceilings match current allowlist sizes."""

    def test_tools_ceiling_matches_allowlist(self):
        assert TOOLS_RATCHET_CEILING == len(TOOLS_ROOT_ALLOWED), (
            f"TOOLS_RATCHET_CEILING ({TOOLS_RATCHET_CEILING}) must equal "
            f"TOOLS_ROOT_ALLOWED size ({len(TOOLS_ROOT_ALLOWED)}). "
            f"Update ceiling when allowlist changes."
        )

    def test_tests_ceiling_matches_allowlist(self):
        assert TESTS_RATCHET_CEILING == len(TESTS_ROOT_ALLOWED), (
            f"TESTS_RATCHET_CEILING ({TESTS_RATCHET_CEILING}) must equal "
            f"TESTS_ROOT_ALLOWED size ({len(TESTS_ROOT_ALLOWED)}). "
            f"Update ceiling when allowlist changes."
        )

    def test_scripts_ceiling_matches_allowlist(self):
        assert SCRIPTS_RATCHET_CEILING == len(SCRIPTS_ROOT_ALLOWED), (
            f"SCRIPTS_RATCHET_CEILING ({SCRIPTS_RATCHET_CEILING}) must equal "
            f"SCRIPTS_ROOT_ALLOWED size ({len(SCRIPTS_ROOT_ALLOWED)}). "
            f"Update ceiling when allowlist changes."
        )
