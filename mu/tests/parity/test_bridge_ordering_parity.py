"""
Cross-substrate bridge ordering validation parity.

Verifies that both Python and JavaScript substrates validate bridge
projection ordering with identical semantics. This is a security
invariant — bridge projections MUST come before match.var to ensure
non-linear pattern binding conflict detection runs first.

What this checker PROVES:
- JS has validateCombinedBridgeOrdering (parity with Python).
- Both substrates reject missing bridge projections.
- Both substrates reject bridge-after-match.var ordering.
- Both substrates accept the canonical valid ordering.

What this checker does NOT prove:
- That the validation cannot be bypassed via other load paths.
- Semantic correctness of bridge pattern matching itself.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
from rcx_pi.selfhost.step_mu import (
    _validate_combined_bridge_ordering,  # ANTICHEAT_OK: grounding test for bridge ordering parity
    load_combined_kernel_with_bridge_projections,
)

# ── Locate JS source ────────────────────────────────────────────────────

_REPO = Path(__file__).resolve().parents[3]
_JS_DIR = _REPO / "mu" / "host" / "js"
_JS_PATH = _JS_DIR / "eval_step.js"  # CLI entrypoint (shim)


def _js_source() -> str:
    """Read all JS module files concatenated (monolith was split into modules)."""
    parts = []
    for f in sorted(_JS_DIR.rglob("*.js")):
        parts.append(f.read_text())
    return "\n".join(parts)


# ── JS function existence ────────────────────────────────────────────────


class TestJsBridgeValidationExists:
    """JS must have validateCombinedBridgeOrdering matching Python."""

    def test_js_has_validation_function(self):
        """validateCombinedBridgeOrdering must be defined in JS."""
        source = _js_source()
        assert "function validateCombinedBridgeOrdering" in source, (
            "JS missing validateCombinedBridgeOrdering function"
        )

    def test_js_validates_all_bridge_arrays(self):
        """All 3 bridge-containing combined arrays must be validated."""
        source = _js_source()
        expected_calls = [
            "validateCombinedBridgeOrdering(allProjectionsWithBridge)",
            "validateCombinedBridgeOrdering(allProjectionsWithRecurrenceAndBridge)",
            "validateCombinedBridgeOrdering(allProjectionsWithExhaustionAndBridge)",
        ]
        for call in expected_calls:
            assert call in source, f"JS missing validation call: {call}"

    def test_js_checks_required_bridge_ids(self):
        """JS must check all 5 required bridge projection IDs."""
        source = _js_source()
        required = [
            "bridge.var.check_existing",
            "bridge.lookup.found_same",
            "bridge.lookup.found_different",
            "bridge.lookup.not_found_yet",
            "bridge.lookup.not_found",
        ]
        for bridge_id in required:
            assert f"'{bridge_id}'" in source, (
                f"JS missing required bridge ID check: {bridge_id}"
            )

    def test_js_checks_match_var_ordering(self):
        """JS must verify bridge projections come before match.var."""
        source = _js_source()
        assert "must be before match.var" in source, (
            "JS missing match.var ordering check"
        )

    def test_js_checks_found_same_before_found_different(self):
        """JS must verify found_same precedes found_different."""
        source = _js_source()
        assert "bridge.lookup.found_same must precede bridge.lookup.found_different" in source, (
            "JS missing found_same/found_different ordering check"
        )


# ── Python validation behavior ──────────────────────────────────────────


class TestPythonBridgeValidation:
    """Python _validate_combined_bridge_ordering behaves correctly."""

    def test_valid_ordering_passes(self):
        """Canonical bridge ordering passes validation."""
        projs = load_combined_kernel_with_bridge_projections()
        # Should not raise
        _validate_combined_bridge_ordering(projs)

    def test_missing_bridge_fails(self):
        """Removing all bridge projections must raise ValueError."""
        projs = load_combined_kernel_with_bridge_projections()
        # Remove bridge projections
        filtered = [p for p in projs if not p.get("id", "").startswith("bridge.")]
        with pytest.raises(ValueError, match="missing bridge projections"):
            _validate_combined_bridge_ordering(filtered)

    def test_bridge_after_match_var_fails(self):
        """Moving bridge after match.var must raise ValueError."""
        projs = load_combined_kernel_with_bridge_projections()
        # Separate bridge and non-bridge, put bridge after match
        bridge = [p for p in projs if p.get("id", "").startswith("bridge.")]
        non_bridge = [p for p in projs if not p.get("id", "").startswith("bridge.")]
        reordered = non_bridge + bridge  # bridge after match.var
        with pytest.raises(ValueError, match="must be before match.var"):
            _validate_combined_bridge_ordering(reordered)

    def test_non_dict_projection_rejected(self):
        """Non-dict entries in projection list must raise ValueError (D-04 fail-closed)."""
        projs = load_combined_kernel_with_bridge_projections()
        # Inject a non-dict element
        poisoned = list(projs) + [None]
        with pytest.raises(ValueError, match="Non-dict projection"):
            _validate_combined_bridge_ordering(poisoned)

    def test_non_dict_projection_types_rejected(self):
        """Various non-dict types are all rejected fail-closed."""
        projs = load_combined_kernel_with_bridge_projections()
        for bad_value in [None, [1, 2], "not_a_dict", 42, True]:
            poisoned = list(projs) + [bad_value]
            with pytest.raises(ValueError, match="Non-dict projection"):
                _validate_combined_bridge_ordering(poisoned)


# ── Cross-substrate parity (via JS inline tests) ────────────────────────


class TestCrossSubstrateBridgeValidation:
    """JS inline tests for bridge validation must pass."""

    def test_js_bridge_validation_inline_tests_pass(self):
        """Run JS and verify bridge validation tests pass."""
        result = subprocess.run(
            ["node", str(_JS_PATH)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"JS tests failed:\nstdout: {result.stdout[-500:]}\nstderr: {result.stderr[-500:]}"
        )
        assert "PASS bridge ordering validation: true" in result.stdout, (
            "JS bridge validation tests did not pass"
        )
