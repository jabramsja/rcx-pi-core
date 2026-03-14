"""
Grounding tests for STATUS.md claims.

These tests verify that claims in STATUS.md match actual project state.
If a test fails, either the code changed or STATUS.md needs updating.

See: mu/docs/agents/AgentRig.v0.md (grounding agent)
"""

import ast
import re
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

# Project root
ROOT = REPO_ROOT


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


def get_function_decorators(file_path: Path, function_name: str) -> list[str]:
    """Use AST to find decorators on a specific function.

    Returns list of decorator names (e.g., ['host_recursion', 'staticmethod']).
    """
    content = file_path.read_text()
    tree = ast.parse(content)

    decorators = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name):
                    decorators.append(decorator.id)
                elif isinstance(decorator, ast.Attribute):
                    decorators.append(decorator.attr)
                elif isinstance(decorator, ast.Call):
                    if isinstance(decorator.func, ast.Name):
                        decorators.append(decorator.func.id)
                    elif isinstance(decorator.func, ast.Attribute):
                        decorators.append(decorator.func.attr)

    return decorators


class TestDebtRatchet:
    """Verify debt ratchet policy: actual debt <= threshold."""

    def test_debt_count_matches_status_md(self):
        """STATUS.md debt count must match host_semantics_baseline.json total (canonical)."""
        import json as _json
        status = parse_status_debt()
        baseline_path = REPO_ROOT / "mu" / "tools" / "checks" / "host_semantics_baseline.json"
        baseline = _json.loads(baseline_path.read_text())
        actual = baseline["total"]

        assert status["current"] == actual, (
            f"STATUS.md claims CURRENT: {status['current']} "
            f"but host_semantics_baseline.json total: {actual}\n"
            f"Update STATUS.md or the baseline."
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
    """Verify L1/L2/L3 claims match implementation state using AST parsing."""

    def test_l1_match_mu_has_no_host_recursion(self):
        """L1 claim: match_mu function has no @host_recursion decorator.

        Uses AST parsing for robustness (not text matching).
        """
        match_mu_path = ROOT / "rcx_pi" / "selfhost" / "match_mu.py"
        decorators = get_function_decorators(match_mu_path, "match_mu")

        assert "host_recursion" not in decorators, (
            f"match_mu function has @host_recursion decorator: {decorators}\n"
            f"L1 claim requires match algorithm to use projections, not Python recursion"
        )

    def test_l1_subst_mu_has_no_host_recursion(self):
        """L1 claim: subst_mu function has no @host_recursion decorator."""
        subst_mu_path = ROOT / "rcx_pi" / "selfhost" / "subst_mu.py"
        decorators = get_function_decorators(subst_mu_path, "subst_mu")

        assert "host_recursion" not in decorators, (
            f"subst_mu function has @host_recursion decorator: {decorators}\n"
            f"L1 claim requires subst algorithm to use projections, not Python recursion"
        )

    def test_l1_step_mu_has_no_host_recursion(self):
        """L1 claim: step_mu function has no @host_recursion decorator."""
        step_mu_path = ROOT / "rcx_pi" / "selfhost" / "step_mu.py"
        decorators = get_function_decorators(step_mu_path, "step_mu")

        assert "host_recursion" not in decorators, (
            f"step_mu function has @host_recursion decorator: {decorators}\n"
            f"L1 claim requires step algorithm to use projections"
        )

    def test_l2_kernel_loop_is_still_python(self):
        """L2 FULL: kernel loop uses Python for-loop (accepted as bootstrap primitive)."""
        step_mu_path = ROOT / "rcx_pi" / "selfhost" / "step_mu.py"
        content = step_mu_path.read_text()

        # Python for-loop is accepted as irreducible bootstrap primitive (L2 FULL)
        assert "for proj in projections" in content, (
            "step_mu.py should have Python for-loop (bootstrap primitive, L2 FULL)\n"
            "The for-loop is accepted as irreducible — see Phase 8 decision"
        )


class TestKeyFilesExist:
    """Verify files referenced in STATUS.md exist."""

    @pytest.mark.parametrize("path", [
        "mu/docs/core/MetaCircularKernel.v0.md",
        "rcx_pi/selfhost/match_mu.py",
        "rcx_pi/selfhost/subst_mu.py",
        "rcx_pi/selfhost/step_mu.py",
        "rcx_pi/selfhost/classify_mu.py",
        "mu/substrate/match.v1.json",
        "mu/substrate/subst.v1.json",
        "mu/utilities/classify.v1.json",
        "mu/utilities/eval.v1.json",
        "TASKS.md",
        "STATUS.md",
        "CLAUDE.md",
    ])
    def test_key_file_exists(self, path):
        """STATUS.md references this file - it must exist."""
        full_path = ROOT / path
        assert full_path.exists(), (
            f"STATUS.md references {path} but file does not exist"
        )


class TestPhaseStatus:
    """Verify phase claims are consistent."""

    def test_phase_7_is_complete(self):
        """Phase 7 should be DONE status (L2 FULL achieved via explicit acceptance)."""
        kernel_doc = ROOT / "mu" / "docs" / "core" / "MetaCircularKernel.v0.md"
        content = kernel_doc.read_text()

        # Should have DONE status (Phase 8 decision: accept for-loop as bootstrap primitive)
        assert "DONE" in content, (
            "MetaCircularKernel.v0.md should have DONE status\n"
            "Phase 7 is complete - L2 FULL achieved via explicit acceptance of for-loop as bootstrap"
        )

        # L2 FULL achieved - for-loop is accepted as bootstrap primitive
        assert "L2 FULL" in content, (
            "MetaCircularKernel.v0.md should mention L2 FULL\n"
            "Phase 8 decision: accept for-loop as irreducible bootstrap primitive"
        )


class TestToolsExist:
    """Verify enforcement tools exist and are executable."""

    @pytest.mark.parametrize("tool", [
        "tools/debt_dashboard.sh",
        "tools/checks/check_docs_consistency.sh",
        "tools/pre-commit-doc-check",
        "tools/audit_semantic_purity.sh",
    ])
    def test_tool_exists(self, tool):
        """Enforcement tool must exist."""
        tool_path = ROOT / tool
        assert tool_path.exists(), f"Tool not found: {tool}"

    def test_debt_dashboard_produces_output(self):
        """debt_dashboard.sh should produce parseable output."""
        result = subprocess.run(
            ["./tools/debt_dashboard.sh"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

        assert result.returncode == 0, (
            f"debt_dashboard.sh failed with code {result.returncode}\n"
            f"stderr: {result.stderr}"
        )

        assert "Total Semantic:" in result.stdout, (
            f"debt_dashboard.sh output missing 'Total Semantic:'\n"
            f"stdout: {result.stdout}"
        )
