"""
Test suite for host debt enforcement changes.

Verifies:
1. debt_dashboard.sh correctly counts and displays AST_OK:bootstrap markers
2. audit_semantic_purity.sh includes AST_OK:bootstrap in DEBT_THRESHOLD
3. Threshold enforcement works as expected (ratchet behavior)
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DEBT_DASHBOARD = ROOT / "tools" / "debt_dashboard.sh"
AUDIT_SCRIPT = ROOT / "tools" / "audit_semantic_purity.sh"


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command and return the result."""
    return subprocess.run(
        args,
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


# -----------------------------------------------------------------------------
# debt_dashboard.sh Tests
# -----------------------------------------------------------------------------


def test_debt_dashboard_includes_ast_ok_bootstrap_line():
    """Verify debt_dashboard.sh outputs the AST_OK:bootstrap count line."""
    result = _run(["bash", str(DEBT_DASHBOARD)])

    assert result.returncode == 0, (
        f"debt_dashboard.sh failed:\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    # Check for the specific output line
    assert "# AST_OK: bootstrap:" in result.stdout, (
        f"Expected '# AST_OK: bootstrap:' line in output.\n"
        f"stdout:\n{result.stdout}"
    )


def test_debt_dashboard_includes_total_semantic_line():
    """Verify debt_dashboard.sh outputs the Total Semantic count line."""
    result = _run(["bash", str(DEBT_DASHBOARD)])

    assert result.returncode == 0
    assert "Total Semantic:" in result.stdout, (
        f"Expected 'Total Semantic:' line in output.\n"
        f"stdout:\n{result.stdout}"
    )


def test_debt_dashboard_json_format():
    """Verify debt_dashboard.sh JSON output includes new fields."""
    result = _run(["bash", str(DEBT_DASHBOARD), "--json"])

    assert result.returncode == 0, (
        f"debt_dashboard.sh --json failed:\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    # Parse JSON output
    data = json.loads(result.stdout)

    # Verify structure
    assert "debt" in data, "JSON should have 'debt' field"
    debt = data["debt"]

    # Check new fields
    assert "ast_ok_bootstrap" in debt, "JSON debt should include ast_ok_bootstrap"
    assert "total_semantic" in debt, "JSON debt should include total_semantic"

    # Verify values are integers
    assert isinstance(debt["ast_ok_bootstrap"], int)
    assert isinstance(debt["total_semantic"], int)

    # Verify calculation: total_semantic = total_tracked + ast_ok_bootstrap
    assert debt["total_semantic"] == debt["total_tracked"] + debt["ast_ok_bootstrap"]


def test_debt_dashboard_counts_ast_ok_bootstrap_correctly():
    """Verify debt_dashboard.sh counts AST_OK:bootstrap markers correctly."""
    result = _run(["bash", str(DEBT_DASHBOARD), "--json"])

    assert result.returncode == 0
    data = json.loads(result.stdout)

    # Current count should be 5 (from match_mu.py and eval_seed.py)
    ast_ok_count = data["debt"]["ast_ok_bootstrap"]

    # Verify it's a reasonable number
    assert ast_ok_count >= 0, "Count should be non-negative"
    assert ast_ok_count < 100, "Count should be reasonable (sanity check)"

    # Current expected count is 5
    assert ast_ok_count == 5, (
        f"Expected 5 AST_OK:bootstrap markers, found {ast_ok_count}. "
        f"If this is intentional, update the test."
    )


# -----------------------------------------------------------------------------
# audit_semantic_purity.sh Tests
# -----------------------------------------------------------------------------


def test_audit_semantic_purity_runs_successfully():
    """Verify audit_semantic_purity.sh runs without crashing."""
    result = _run(["bash", str(AUDIT_SCRIPT)])

    # Script should pass or pass with warnings (exit code 0)
    # It may fail if threshold needs adjustment (exit code 1)
    assert result.returncode in [0, 1], (
        f"audit_semantic_purity.sh returned unexpected code {result.returncode}:\n"
        f"stderr: {result.stderr}"
    )


def test_audit_semantic_purity_includes_ast_ok_bootstrap_in_debt():
    """Verify audit includes AST_OK:bootstrap in total debt calculation."""
    result = _run(["bash", str(AUDIT_SCRIPT)])

    # Look for section 19 (Host Debt: Threshold Check)
    assert "== 19. Host Debt: Threshold Check ==" in result.stdout

    # Should show AST_OK: bootstrap count
    assert "# AST_OK: bootstrap:" in result.stdout, (
        f"Expected AST_OK:bootstrap count in debt section.\n"
        f"stdout:\n{result.stdout}"
    )

    # Should show TOTAL SEMANTIC DEBT calculation
    assert "TOTAL SEMANTIC DEBT:" in result.stdout


def test_audit_semantic_purity_threshold_is_21():
    """Verify the threshold is set to 21 as documented.

    Threshold history:
    - 14: Original (7 tracked + 5 AST_OK + 2 headroom)
    - 23: After marking ~289 LOC of previously unmarked semantic debt
          (17 tracked + 5 AST_OK + 1 review = 23)
    - 21: Phase 6a lookup as Mu projections (removed 2 @host_builtin)
          (15 tracked + 5 AST_OK + 1 review = 21)
    """
    script_content = AUDIT_SCRIPT.read_text(encoding="utf-8")

    # Find the DEBT_THRESHOLD line
    threshold_lines = [
        line for line in script_content.split("\n")
        if "DEBT_THRESHOLD=" in line and not line.strip().startswith("#")
    ]

    assert len(threshold_lines) >= 1, "Should find DEBT_THRESHOLD assignment"

    # Extract value - format: DEBT_THRESHOLD=21
    line = threshold_lines[0]
    value = line.split("=")[1].split()[0]

    assert value == "21", (
        f"Expected DEBT_THRESHOLD=21, found {value}. "
        f"If this changed, update test to match current threshold."
    )


# -----------------------------------------------------------------------------
# Integration Tests
# -----------------------------------------------------------------------------


def test_dashboard_and_audit_agree_on_ast_ok_count():
    """Verify dashboard and audit count AST_OK:bootstrap identically."""
    # Run dashboard
    dash_result = _run(["bash", str(DEBT_DASHBOARD), "--json"])
    assert dash_result.returncode == 0
    dash_data = json.loads(dash_result.stdout)
    dash_count = dash_data["debt"]["ast_ok_bootstrap"]

    # Run audit and extract count
    audit_result = _run(["bash", str(AUDIT_SCRIPT)])

    # Extract AST_OK count from audit output
    # Format: "    # AST_OK: bootstrap: 5"
    lines = audit_result.stdout.split("\n")
    ast_ok_lines = [l for l in lines if "# AST_OK: bootstrap:" in l]

    assert len(ast_ok_lines) >= 1, "Should find AST_OK:bootstrap count in audit"

    # Extract number - it's the last number on the line before any text
    ast_ok_line = ast_ok_lines[0]
    # Split by colon and get the number
    parts = ast_ok_line.split(":")
    if len(parts) >= 3:
        num_str = parts[-1].strip().split()[0]
        audit_count = int(num_str)

        assert audit_count == dash_count, (
            f"Audit count ({audit_count}) should match dashboard count ({dash_count})"
        )


def test_ast_ok_pattern_catches_spacing_variations():
    """Verify the AST_OK pattern catches variations like AST_OK:bootstrap."""
    # The pattern should use [[:space:]]* to catch spacing variations
    script_content = DEBT_DASHBOARD.read_text(encoding="utf-8")

    # Check that the pattern includes flexibility for spacing
    assert "[[:space:]]*bootstrap" in script_content or "\\s*bootstrap" in script_content, (
        "AST_OK pattern should handle spacing variations"
    )
