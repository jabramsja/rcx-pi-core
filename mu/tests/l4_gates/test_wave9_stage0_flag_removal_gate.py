"""
L4 gate test: Wave 9 — Stage 0 pilot flag removal (JS parity with Python).

Proves that JavaScript bootstrap_core.js no longer uses _stage0Pilot conditional
routing, matching Python where the flag was removed in Wave 4.
"""
from tests.repo_root import REPO_ROOT


def test_js_no_stage0_pilot_flag():
    """bootstrap_core.js must not declare a _stage0Pilot variable."""
    source = (REPO_ROOT / "mu" / "host" / "js" / "core" / "bootstrap_core.js").read_text()
    # Flag declaration: "let _stage0Pilot" or "var _stage0Pilot" or "const _stage0Pilot"
    assert "let _stage0Pilot" not in source, (
        "bootstrap_core.js still declares _stage0Pilot. "
        "Stage 0 is the sole production path — flag should be removed."
    )
    assert "var _stage0Pilot" not in source
    assert "const _stage0Pilot" not in source


def test_js_no_conditional_stage0_routing():
    """bootstrap_core.js must not conditionally route via _stage0Pilot."""
    source = (REPO_ROOT / "mu" / "host" / "js" / "core" / "bootstrap_core.js").read_text()
    assert "_stage0Pilot" not in source, (
        "bootstrap_core.js still references _stage0Pilot. "
        "All conditional routing should be removed — stage0Match/stage0Substitute are unconditional."
    )


def test_js_no_set_stage0_pilot_export():
    """bootstrap_core.js must not export setStage0Pilot."""
    source = (REPO_ROOT / "mu" / "host" / "js" / "core" / "bootstrap_core.js").read_text()
    assert "setStage0Pilot" not in source, (
        "bootstrap_core.js still exports setStage0Pilot. "
        "Flag and setter should be removed — Stage 0 is permanent."
    )


def test_python_no_stage0_pilot_flag():
    """eval_seed.py must not declare a _stage0_pilot variable (removed Wave 4)."""
    source = (REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "eval_seed.py").read_text()
    # Should not have an active flag — only comments about removal are OK
    lines = source.split("\n")
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        # Skip comment lines
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'"):
            continue
        assert "_stage0_pilot" not in line.lower() or "stage0_pilot" not in line, (
            f"eval_seed.py line {i} appears to have an active _stage0_pilot reference: {line.strip()}"
        )
