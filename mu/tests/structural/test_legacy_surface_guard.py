"""
Structural guard: prevent new test/script files from coupling to ARCHIVE-bound surfaces.

rcx_pi_rust and rcx_omega are ARCHIVE-bound (LegacySurfaceDecisionRecord.v0.md).
Existing references are grandfathered and tracked. New test files must NOT add
hard imports from rcx_omega or hard path references to rcx_pi_rust.

This guard prevents re-coupling after the Round 21B/21C decoupling pass.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

# Files that are grandfathered (existing before this guard was added).
# Do NOT add new entries here without a governance reason documented in
# LegacySurfaceDecisionRecord.v0.md.
#
# Round 21C: Cleared GRANDFATHERED_RCX_PI_RUST_PATHS — all 4 test files
# repointed to mu/mu_programs/.
# Round 21D: Cleared GRANDFATHERED_RCX_OMEGA_IMPORTS — both test files
# archived to archive/tests/legacy/ (moved from mu/tests/archive/ in wave15).
GRANDFATHERED_RCX_OMEGA_IMPORTS: frozenset[str] = frozenset()

# Round 23A: Guardrail infrastructure files reference rcx_pi_rust/ as regex
# patterns to prevent re-coupling — these are not hard path dependencies.
GRANDFATHERED_RCX_PI_RUST_PATHS: frozenset[str] = frozenset({
    "tests/docs/test_doc_freshness.py",   # ForbiddenPattern regex
    "tests/docs/test_doc_governance.py",   # EXEMPT_PATTERNS regex
})

# Patterns that indicate coupling to legacy surfaces
RCX_OMEGA_IMPORT = re.compile(
    r"^\s*(from\s+rcx_omega[\s.]|import\s+rcx_omega)\b", re.MULTILINE
)
RCX_PI_RUST_PATH = re.compile(
    r"""(?:["'/])rcx_pi_rust[/"']""", re.MULTILINE
)


class TestNoNewLegacySurfaceCoupling:
    """Prevent new test/script files from coupling to legacy surfaces."""

    def test_no_new_rcx_omega_imports_in_tests(self):
        """No new test files should import from rcx_omega."""
        violations = []
        tests_dir = REPO_ROOT / "tests"
        for py_file in sorted(tests_dir.rglob("*.py")):
            if "archive" in py_file.parts:
                continue
            rel = str(py_file.relative_to(REPO_ROOT))
            if rel in GRANDFATHERED_RCX_OMEGA_IMPORTS:
                continue
            content = py_file.read_text(encoding="utf-8")
            if RCX_OMEGA_IMPORT.search(content):
                violations.append(f"  {rel}")

        assert not violations, (
            "New test files must NOT import from rcx_omega "
            "(ARCHIVE-bound, LegacySurfaceDecisionRecord.v0.md).\n"
            "Use local fixtures or public rcx_pi API instead.\n"
            "Violations:\n" + "\n".join(violations)
        )

    def test_no_new_rcx_pi_rust_paths_in_tests(self):
        """No new test files should hard-reference rcx_pi_rust paths."""
        violations = []
        for search_dir in [REPO_ROOT / "tests", REPO_ROOT / "scripts" / "tests"]:
            if not search_dir.exists():
                continue
            for py_file in sorted(search_dir.rglob("*.py")):
                if "archive" in py_file.parts:
                    continue
                rel = str(py_file.relative_to(REPO_ROOT))
                if rel in GRANDFATHERED_RCX_PI_RUST_PATHS:
                    continue
                content = py_file.read_text(encoding="utf-8")
                if RCX_PI_RUST_PATH.search(content):
                    violations.append(f"  {rel}")

        assert not violations, (
            "New test files must NOT hard-reference rcx_pi_rust paths "
            "(ARCHIVE-bound, LegacySurfaceDecisionRecord.v0.md).\n"
            "Use mu/mu_programs/ or local fixtures instead.\n"
            "Violations:\n" + "\n".join(violations)
        )

    def test_no_rcx_pi_rust_in_new_scripts(self):
        """Non-exempt scripts must not hard-reference rcx_pi_rust paths.

        Exempt: files with DEPRECATED or LEGACY_GUARDED in the first 500 chars.
        """
        violations = []
        scripts_dir = REPO_ROOT / "scripts"
        if not scripts_dir.exists():
            return
        for sh_file in sorted(scripts_dir.rglob("*.sh")):
            content = sh_file.read_text(encoding="utf-8", errors="replace")
            header = content[:500]
            # Files with DEPRECATED or LEGACY_GUARDED are exempt
            if "DEPRECATED" in header or "LEGACY_GUARDED" in content:
                continue
            rel = str(sh_file.relative_to(REPO_ROOT))
            if RCX_PI_RUST_PATH.search(content):
                violations.append(f"  {rel}")

        assert not violations, (
            "Non-exempt scripts must NOT hard-reference rcx_pi_rust paths "
            "(ARCHIVE-bound, LegacySurfaceDecisionRecord.v0.md).\n"
            "Use mu/mu_programs/, add DEPRECATED header, or mark LEGACY_GUARDED.\n"
            "Violations:\n" + "\n".join(violations)
        )

    def test_grandfathered_files_still_exist(self):
        """Ensure grandfathered allowlist doesn't go stale."""
        all_grandfathered = GRANDFATHERED_RCX_OMEGA_IMPORTS | GRANDFATHERED_RCX_PI_RUST_PATHS
        for rel in sorted(all_grandfathered):
            p = REPO_ROOT / rel
            assert p.exists(), (
                f"Grandfathered file no longer exists: {rel}\n"
                "Remove it from the allowlist in test_legacy_surface_guard.py."
            )
