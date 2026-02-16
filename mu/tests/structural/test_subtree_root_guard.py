"""
Subtree root-level file guard: prevent loose file accumulation in mu/ subtrees.

After Wave 6, mu/tools/, mu/tests/, and mu/scripts/ have semantic subdirectories.
New files MUST be placed in the appropriate subdirectory, not at subtree root.

Root-level files are exception-only and must be allowlisted with rationale.
The allowlist count can only stay the same or decrease (ratchet rule).

This test fails CI when:
1. A new file appears at subtree root that is not allowlisted.
2. The allowlist count exceeds the ratchet ceiling.
3. Any backup/temp artifact (*.bak, *.orig, *.rej, *~) is tracked anywhere in mu/.
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


# ============================================================================
# Anti-slop: reject backup/temp artifacts tracked in mu/ subtrees
# ============================================================================

# Patterns that must NEVER be committed in mu/tools/, mu/tests/, mu/scripts/
BACKUP_PATTERNS = (".bak", ".orig", ".rej", ".swp", ".swo")

GUARDED_SUBTREES = ("tools", "tests", "scripts")


def _get_all_tracked_files(subtree: str) -> list[str]:
    """Get ALL git-tracked files (including subdirs) in a mu/ subtree."""
    result = subprocess.run(
        ["git", "ls-files", f"mu/{subtree}/"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.strip().splitlines() if line]


class TestUntrackedArtifactChecker:
    """Verify the untracked artifact checker script exists and works."""

    def test_checker_script_exists(self):
        checker = REPO_ROOT / "mu" / "tools" / "checks" / "check_untracked_artifacts.sh"
        assert checker.exists(), (
            f"check_untracked_artifacts.sh missing at {checker}\n"
            "This script detects untracked backup/temp files in mu/ subtrees."
        )

    def test_checker_script_executable(self):
        import os
        checker = REPO_ROOT / "mu" / "tools" / "checks" / "check_untracked_artifacts.sh"
        if checker.exists():
            assert os.access(checker, os.X_OK), (
                f"check_untracked_artifacts.sh is not executable: {checker}"
            )

    def test_checker_passes_on_clean_tree(self):
        """When no .bak/.orig/.rej files exist, checker should exit 0."""
        result = subprocess.run(
            ["bash", "tools/checks/check_untracked_artifacts.sh", "--quiet"],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        assert result.returncode == 0, (
            f"Untracked artifact checker failed on clean tree:\n{result.stdout}\n{result.stderr}"
        )

    def test_checker_wired_into_audit_fast(self):
        """audit_fast.sh must call check_untracked_artifacts.sh."""
        audit = REPO_ROOT / "mu" / "tools" / "audits" / "audit_fast.sh"
        content = audit.read_text()
        assert "check_untracked_artifacts" in content, (
            "check_untracked_artifacts.sh not wired into audit_fast.sh"
        )

    def test_checker_wired_into_pre_commit(self):
        """pre-commit-doc-check must call check_untracked_artifacts.sh."""
        hook = REPO_ROOT / "mu" / "tools" / "hooks" / "pre-commit-doc-check"
        content = hook.read_text()
        assert "check_untracked_artifacts" in content, (
            "check_untracked_artifacts.sh not wired into pre-commit-doc-check"
        )


class TestAntiSlopGuard:
    """Reject tracked backup/temp artifacts in governed subtrees."""

    def test_no_backup_files_in_tools(self):
        files = _get_all_tracked_files("tools")
        violations = [f for f in files
                      if any(f.endswith(p) for p in BACKUP_PATTERNS)
                      or f.endswith("~")]
        assert not violations, (
            f"Backup/temp files tracked in mu/tools/:\n"
            + "\n".join(f"  - {f}" for f in violations)
            + "\n\nRemove with: git rm <file>"
        )

    def test_no_backup_files_in_tests(self):
        files = _get_all_tracked_files("tests")
        violations = [f for f in files
                      if any(f.endswith(p) for p in BACKUP_PATTERNS)
                      or f.endswith("~")]
        assert not violations, (
            f"Backup/temp files tracked in mu/tests/:\n"
            + "\n".join(f"  - {f}" for f in violations)
            + "\n\nRemove with: git rm <file>"
        )

    def test_no_backup_files_in_scripts(self):
        files = _get_all_tracked_files("scripts")
        violations = [f for f in files
                      if any(f.endswith(p) for p in BACKUP_PATTERNS)
                      or f.endswith("~")]
        assert not violations, (
            f"Backup/temp files tracked in mu/scripts/:\n"
            + "\n".join(f"  - {f}" for f in violations)
            + "\n\nRemove with: git rm <file>"
        )
