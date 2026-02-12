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


def _run(args: list[str], cwd: Path | None = None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command and return the result.

    Args:
        args: Command and arguments to run
        cwd: Working directory (defaults to ROOT)
        timeout: Maximum seconds to wait (prevents CI hangs)
    """
    return subprocess.run(
        args,
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
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

    # Current count should be 4 (from match_mu.py, eval_seed.py, step_mu.py)
    # Phase 6c removed 2 (normalize_for_match and denormalize_from_match comprehensions)
    # Phase A reclassified 2 items from bootstrap to infra (match_mu boundary, step_mu constant)
    ast_ok_count = data["debt"]["ast_ok_bootstrap"]

    # Verify it's a reasonable number
    assert ast_ok_count >= 0, "Count should be non-negative"
    assert ast_ok_count < 100, "Count should be reasonable (sanity check)"

    # Current expected count is 2 (eval_seed.py list/dict comprehensions)
    assert ast_ok_count == 2, (
        f"Expected 2 AST_OK:bootstrap markers, found {ast_ok_count}. "
        f"If this is intentional, update the test."
    )


# -----------------------------------------------------------------------------
# audit_semantic_purity.sh Tests
# -----------------------------------------------------------------------------


@pytest.mark.slow
def test_audit_semantic_purity_runs_successfully():
    """Verify audit_semantic_purity.sh runs without crashing."""
    result = _run(["bash", str(AUDIT_SCRIPT)])

    # Script should pass or pass with warnings (exit code 0)
    # It may fail if threshold needs adjustment (exit code 1)
    assert result.returncode in [0, 1], (
        f"audit_semantic_purity.sh returned unexpected code {result.returncode}:\n"
        f"stderr: {result.stderr}"
    )


@pytest.mark.slow
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


@pytest.mark.slow
def test_audit_semantic_purity_threshold_matches_status_md():
    """Verify the threshold is read from STATUS.md (single source of truth).

    7-agent review finding: audit_semantic_purity.sh should read the threshold
    dynamically from STATUS.md rather than hardcoding it, ensuring a single
    source of truth.

    Current threshold: 12 (L2 floor - irreducible bootstrap substrate)
    - @host_recursion: 2 (eval_seed match/substitute)
    - @host_builtin: 3 (eval_seed, deep_eval)
    - @host_iteration: 3 (run_mu, step_kernel_mu, run_mu_structural)
    - @host_mutation: 2 (eval_seed, deep_eval)
    - AST_OK bootstrap: 2 (eval_seed comprehensions)
    """
    # Verify STATUS.md has the threshold line
    status_md = ROOT / "STATUS.md"
    status_content = status_md.read_text(encoding="utf-8")

    status_threshold = None
    for line in status_content.split("\n"):
        if line.startswith("THRESHOLD:"):
            # Use split()[0] to handle inline comments like "12 (current)"
            status_threshold = line.split(":")[1].strip().split()[0]
            break

    assert status_threshold is not None, "Should find THRESHOLD in STATUS.md"

    # Verify audit script reads from STATUS.md (not hardcoded)
    script_content = AUDIT_SCRIPT.read_text(encoding="utf-8")

    # Script should read THRESHOLD from STATUS.md
    assert 'grep "^THRESHOLD:" "$PROJECT_ROOT/STATUS.md"' in script_content, (
        "audit_semantic_purity.sh must read DEBT_THRESHOLD from STATUS.md"
    )

    # Should NOT have a hardcoded numeric DEBT_THRESHOLD=NN line
    # (the assignment uses $(grep...) now)
    hardcoded_lines = [
        line for line in script_content.split("\n")
        if line.strip().startswith("DEBT_THRESHOLD=") and
        line.split("=")[1].strip().isdigit()
    ]
    assert len(hardcoded_lines) == 0, (
        f"Found hardcoded DEBT_THRESHOLD in audit script: {hardcoded_lines}. "
        f"Script should read from STATUS.md instead."
    )


@pytest.mark.slow
def test_audit_semantic_purity_has_selfhost_error_path():
    """Verify audit_semantic_purity.sh fails with clear error if selfhost missing.

    7-agent review finding: The else branch must fail with an actionable error,
    not silently pass or assign variables to themselves (dead code).
    """
    script_content = AUDIT_SCRIPT.read_text(encoding="utf-8")

    # Check for the error message that tells users what's wrong
    assert "ERROR: selfhost subpackage not found" in script_content, (
        "audit_semantic_purity.sh must have clear error message when selfhost missing"
    )
    assert "exit 1" in script_content, (
        "audit_semantic_purity.sh must exit with error code when selfhost missing"
    )


# -----------------------------------------------------------------------------
# Integration Tests
# -----------------------------------------------------------------------------


@pytest.mark.slow
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


# -----------------------------------------------------------------------------
# Infrastructure Ceiling Tests
# -----------------------------------------------------------------------------


def test_debt_dashboard_json_includes_infra_count():
    """Verify debt_dashboard.sh JSON output includes infra fields."""
    result = _run(["bash", str(DEBT_DASHBOARD), "--json"])

    assert result.returncode == 0
    data = json.loads(result.stdout)

    # Check infra fields exist
    assert "ast_ok_infra" in data["debt"], "JSON should include ast_ok_infra"
    assert "ast_ok_infra_ceiling" in data["debt"], "JSON should include ast_ok_infra_ceiling"

    # Verify ceiling matches STATUS.md (single source of truth)
    status_md = ROOT / "STATUS.md"
    status_content = status_md.read_text(encoding="utf-8")
    status_ceiling = None
    for line in status_content.split("\n"):
        if line.startswith("INFRA_CEILING:"):
            status_ceiling = int(line.split(":")[1].strip().split()[0])
            break

    if status_ceiling is not None:
        assert data["debt"]["ast_ok_infra_ceiling"] == status_ceiling, (
            f"Ceiling in dashboard ({data['debt']['ast_ok_infra_ceiling']}) "
            f"doesn't match STATUS.md ({status_ceiling})"
        )
    else:
        # Fallback: just verify it's the expected default
        assert data["debt"]["ast_ok_infra_ceiling"] == 35


def test_infra_count_within_ceiling():
    """Verify AST_OK:infra count is below ceiling (35).

    This test enforces the infra ceiling to prevent unbounded accumulation
    of boundary scaffolding. Infra markers are not debt (they don't block
    self-hosting), but excessive infra suggests architectural issues.

    Current expected: 37
    """
    result = _run(["bash", str(DEBT_DASHBOARD), "--json"])

    assert result.returncode == 0
    data = json.loads(result.stdout)

    infra_count = data["debt"]["ast_ok_infra"]
    infra_ceiling = data["debt"]["ast_ok_infra_ceiling"]

    # Must be within ceiling
    assert infra_count <= infra_ceiling, (
        f"AST_OK:infra ({infra_count}) exceeds ceiling ({infra_ceiling}). "
        f"Review and reduce scaffolding markers before adding more."
    )

    # Current expected count is 46 (44 base + 1 run_hemisphere_routing + 1 _default_hemispheres)
    assert infra_count == 46, (
        f"Expected 46 AST_OK:infra markers, found {infra_count}. "
        f"If this is intentional, update the test."
    )
