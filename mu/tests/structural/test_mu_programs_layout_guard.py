"""
Structural guard: mu/mu_programs/ root must contain only whitelisted entries.

Sandbox-generated files (__sandbox_run_*, __smoke_*) belong in sandbox/.
Canonical .mu world fixtures and README.md live at root.  Any new entry
must be explicitly allowlisted here with a governance reason.

Usage:
    PYTHONHASHSEED=0 pytest tests/structural/test_mu_programs_layout_guard.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

MU_PROGRAMS_DIR = REPO_ROOT / "mu" / "mu_programs"

# Allowlisted entries at mu/mu_programs/ root.
# Add new entries ONLY with a governance reason.
ALLOWED_ROOT_ENTRIES: frozenset[str] = frozenset({
    # Canonical .mu world fixtures
    "rcx_core.mu",
    "pingpong.mu",
    "paradox_1over0.mu",
    "vars_demo.mu",
    # Documentation
    "README.md",
    # Sandbox subfolder (generated files go HERE, not at root)
    "sandbox",
})

# Prefixes that indicate sandbox/generated files misplaced at root.
SANDBOX_PREFIXES = ("__sandbox_run_", "__smoke_")


class TestMuProgramsLayoutGuard:
    """Prevent file sprawl in mu/mu_programs/ root."""

    def test_no_unlisted_entries(self):
        """All entries at mu/mu_programs/ root must be in the allowlist."""
        assert MU_PROGRAMS_DIR.is_dir(), f"mu/mu_programs/ not found at {MU_PROGRAMS_DIR}"
        actual = {e.name for e in MU_PROGRAMS_DIR.iterdir() if not e.name.startswith(".")}
        violations = sorted(actual - ALLOWED_ROOT_ENTRIES)
        assert not violations, (
            "Unlisted entries found in mu/mu_programs/ root.\n"
            "Sandbox files belong in mu/mu_programs/sandbox/.\n"
            "If a new canonical fixture, add it to ALLOWED_ROOT_ENTRIES in\n"
            "tests/structural/test_mu_programs_layout_guard.py.\n"
            f"Violations: {violations}"
        )

    def test_no_sandbox_files_at_root(self):
        """Sandbox-generated files must not exist at mu/mu_programs/ root."""
        assert MU_PROGRAMS_DIR.is_dir()
        misplaced = sorted(
            e.name for e in MU_PROGRAMS_DIR.iterdir()
            if any(e.name.startswith(p) for p in SANDBOX_PREFIXES)
        )
        assert not misplaced, (
            f"Found {len(misplaced)} sandbox-generated file(s) at mu/mu_programs/ root.\n"
            "These must live in mu/mu_programs/sandbox/.\n"
            "Fix the generator or move them: "
            "mv mu/mu_programs/__sandbox_run_* mu/mu_programs/sandbox/\n"
            f"First 5: {misplaced[:5]}"
        )

    def test_sandbox_subfolder_exists(self):
        """mu/mu_programs/sandbox/ must exist (with .gitkeep)."""
        sandbox = MU_PROGRAMS_DIR / "sandbox"
        assert sandbox.is_dir(), (
            "mu/mu_programs/sandbox/ directory missing. "
            "Create it: mkdir -p mu/mu_programs/sandbox && touch mu/mu_programs/sandbox/.gitkeep"
        )
        gitkeep = sandbox / ".gitkeep"
        assert gitkeep.exists(), (
            "mu/mu_programs/sandbox/.gitkeep missing. "
            "Required so git tracks the empty directory."
        )

    def test_allowlist_not_stale(self):
        """Every allowlisted entry must actually exist (no phantoms)."""
        actual = {e.name for e in MU_PROGRAMS_DIR.iterdir() if not e.name.startswith(".")}
        phantoms = sorted(ALLOWED_ROOT_ENTRIES - actual)
        assert not phantoms, (
            "Allowlisted entries no longer exist in mu/mu_programs/.\n"
            "Remove stale entries from ALLOWED_ROOT_ENTRIES in\n"
            "tests/structural/test_mu_programs_layout_guard.py.\n"
            f"Phantom entries: {phantoms}"
        )
