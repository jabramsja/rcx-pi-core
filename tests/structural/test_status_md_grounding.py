"""
Grounding tests for STATUS.md claims.

These tests verify that claims in STATUS.md match actual project state.
If a test fails, either the code changed or STATUS.md needs updating.

See: docs/agents/AgentRig.v0.md (grounding agent)
"""

import re
import subprocess
from pathlib import Path

import pytest

# Project root
ROOT = Path(__file__).parent.parent.parent


def read_status_md() -> str:
    """Read STATUS.md content."""
    return (ROOT / "STATUS.md").read_text()


def parse_status_debt() -> dict:
    """Parse debt section from STATUS.md."""
    content = read_status_md()

    # Find THRESHOLD and CURRENT lines
    threshold_match = re.search(r"THRESHOLD:\s*(\d+)", content)
    current_match = re.search(r"CURRENT:\s*(\d+)", content)

    return {
        "threshold": int(threshold_match.group(1)) if threshold_match else None,
        "current": int(current_match.group(1)) if current_match else None,
    }


def run_debt_dashboard() -> int:
    """Run debt_dashboard.sh and parse total semantic debt."""
    result = subprocess.run(
        ["./tools/debt_dashboard.sh"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    # Parse "Total Semantic: N" from output
    match = re.search(r"Total Semantic:\s*(\d+)", result.stdout)
    if match:
        return int(match.group(1))

    pytest.fail(f"Could not parse debt from dashboard output:\n{result.stdout}")


class TestDebtRatchet:
    """Verify debt ratchet policy: actual debt <= threshold."""

    def test_debt_count_matches_status_md(self):
        """STATUS.md debt count must match debt_dashboard.sh output."""
        status = parse_status_debt()
        actual = run_debt_dashboard()

        assert status["current"] == actual, (
            f"STATUS.md claims CURRENT: {status['current']} "
            f"but debt_dashboard.sh reports: {actual}\n"
            f"Update STATUS.md if debt changed."
        )

    def test_debt_does_not_exceed_threshold(self):
        """Actual debt must not exceed STATUS.md threshold (ratchet policy)."""
        status = parse_status_debt()
        actual = run_debt_dashboard()

        assert actual <= status["threshold"], (
            f"DEBT RATCHET VIOLATION: {actual} > {status['threshold']}\n"
            f"Debt can only decrease, never increase.\n"
            f"See TASKS.md 'RATCHET debt policy'"
        )


class TestSelfHostingLevelClaims:
    """Verify L1/L2/L3 claims match implementation state."""

    def test_l1_match_mu_has_no_host_recursion(self):
        """L1 claim: match_mu uses projections, not Python recursion."""
        match_mu_path = ROOT / "rcx_pi" / "selfhost" / "match_mu.py"
        content = match_mu_path.read_text()

        # Should NOT have @host_recursion on match_mu function itself
        # (helper functions may have it, but the main algorithm shouldn't)
        lines = content.split("\n")
        in_match_mu_func = False

        for i, line in enumerate(lines):
            if "def match_mu(" in line:
                in_match_mu_func = True
            elif in_match_mu_func and line.startswith("def "):
                in_match_mu_func = False

            if in_match_mu_func and "@host_recursion" in line:
                pytest.fail(
                    f"match_mu.py line {i+1}: @host_recursion found in match_mu function\n"
                    f"L1 claim requires match algorithm to use projections"
                )

    def test_l1_subst_mu_has_no_host_recursion(self):
        """L1 claim: subst_mu uses projections, not Python recursion."""
        subst_mu_path = ROOT / "rcx_pi" / "selfhost" / "subst_mu.py"
        content = subst_mu_path.read_text()

        lines = content.split("\n")
        in_subst_mu_func = False

        for i, line in enumerate(lines):
            if "def subst_mu(" in line:
                in_subst_mu_func = True
            elif in_subst_mu_func and line.startswith("def "):
                in_subst_mu_func = False

            if in_subst_mu_func and "@host_recursion" in line:
                pytest.fail(
                    f"subst_mu.py line {i+1}: @host_recursion found in subst_mu function\n"
                    f"L1 claim requires subst algorithm to use projections"
                )

    def test_l2_kernel_loop_is_still_python(self):
        """L2 DESIGN: kernel loop should still be Python (not yet structural)."""
        step_mu_path = ROOT / "rcx_pi" / "selfhost" / "step_mu.py"
        content = step_mu_path.read_text()

        # Should have Python for-loop (scaffolding debt)
        assert "for proj in projections" in content, (
            "step_mu.py should have Python for-loop (L2 is DESIGN, not DONE)\n"
            "If kernel loop is now structural, update STATUS.md to L2 DONE"
        )


class TestKeyFilesExist:
    """Verify files referenced in STATUS.md exist."""

    @pytest.mark.parametrize("path", [
        "docs/core/MetaCircularKernel.v0.md",
        "rcx_pi/selfhost/match_mu.py",
        "rcx_pi/selfhost/subst_mu.py",
        "rcx_pi/selfhost/step_mu.py",
        "seeds/match.v1.json",
        "seeds/subst.v1.json",
        "seeds/classify.v1.json",
        "TASKS.md",
    ])
    def test_key_file_exists(self, path):
        """STATUS.md references this file - it must exist."""
        full_path = ROOT / path
        assert full_path.exists(), (
            f"STATUS.md references {path} but file does not exist"
        )


class TestPhaseStatus:
    """Verify phase claims are consistent."""

    def test_phase_7_is_design_only(self):
        """Phase 7 should be VECTOR status (design-only, no implementation)."""
        kernel_doc = ROOT / "docs" / "core" / "MetaCircularKernel.v0.md"
        content = kernel_doc.read_text()

        # Should have VECTOR status
        assert "VECTOR" in content, (
            "MetaCircularKernel.v0.md should have VECTOR status\n"
            "If Phase 7 is implemented, update STATUS.md"
        )

        # Should NOT have kernel loop implementation
        kernel_loop_impl = ROOT / "rcx_pi" / "selfhost" / "kernel_loop_mu.py"
        assert not kernel_loop_impl.exists(), (
            "kernel_loop_mu.py exists but STATUS.md says L2 is DESIGN\n"
            "Update STATUS.md if kernel loop is now structural"
        )
