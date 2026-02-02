"""
Parity tests for exhaust.v1.json (Rule 3.1 Operator Exhaustion).

These tests verify that the structural exhaustion detection projections
produce correct results for various scenarios.

See: docs/core/OperatorExhaustion.v0.md
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rcx_pi.selfhost.eval_seed import step
from rcx_pi.selfhost.kernel import reset_step_budget
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seeds_dir

import subprocess

# JSON null -> Python None alias for readability
null = None

# Root directory of the project
ROOT = Path(__file__).parent.parent


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def exhaust_projections() -> list:
    """Load exhaustion projections from seed file."""
    seed_path = get_seeds_dir() / "exhaust.v1.json"
    seed = load_verified_seed(seed_path)
    return seed["projections"]


@pytest.fixture
def exhaustion_vectors() -> list:
    """Load test vectors from JSON fixture."""
    vectors_path = Path(__file__).parent / "fixtures" / "exhaustion_vectors.json"
    with open(vectors_path) as f:
        data = json.load(f)
    return data["vectors"]


def run_until_stable(projections: list, value: dict, max_steps: int = 100) -> dict:
    """Run projections until stall (no change) or max_steps."""
    reset_step_budget()
    current = value
    for _ in range(max_steps):
        result = step(projections, current)
        if result == current:
            return result
        current = result
    return current


# =============================================================================
# Parity Tests
# =============================================================================


class TestExhaustionParity:
    """Test exhaustion detection against expected vectors."""

    def test_no_tau_continues(self, exhaust_projections, exhaustion_vectors):
        """No tau_step (null) means no exhaustion possible."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.no_tau")
        result = run_until_stable(exhaust_projections, vector["input"])
        assert result == vector["expected"], f"Expected {vector['expected']}, got {result}"

    def test_single_op_exhausted(self, exhaust_projections, exhaustion_vectors):
        """Same operator since tau_step should be frozen."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.single_op_exhausted")
        result = run_until_stable(exhaust_projections, vector["input"])
        assert result == vector["expected"], f"Expected {vector['expected']}, got {result}"

    def test_different_op_not_exhausted(self, exhaust_projections, exhaustion_vectors):
        """Different operator after tau_step means not exhausted."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.different_op")
        result = run_until_stable(exhaust_projections, vector["input"])
        assert result == vector["expected"], f"Expected {vector['expected']}, got {result}"

    def test_already_frozen_skipped(self, exhaust_projections, exhaustion_vectors):
        """Operator already in frozen list should be skipped."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.already_frozen")
        result = run_until_stable(exhaust_projections, vector["input"])
        assert result == vector["expected"], f"Expected {vector['expected']}, got {result}"

    def test_tau_not_found(self, exhaust_projections, exhaustion_vectors):
        """tau_step not found in trace should continue."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.tau_not_found")
        result = run_until_stable(exhaust_projections, vector["input"])
        assert result == vector["expected"], f"Expected {vector['expected']}, got {result}"

    def test_tau_at_end(self, exhaust_projections, exhaustion_vectors):
        """tau_step at end of trace (no subsequent entries) should freeze."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.tau_at_end")
        result = run_until_stable(exhaust_projections, vector["input"])
        assert result == vector["expected"], f"Expected {vector['expected']}, got {result}"


class TestExhaustionStructure:
    """Test that exhaustion detection is structural."""

    def test_projections_are_valid_mu(self, exhaust_projections):
        """All projections must be valid Mu (JSON-compatible)."""
        # If we got here, seed loaded and validated
        assert len(exhaust_projections) == 11, f"Expected 11 projections, got {len(exhaust_projections)}"

    def test_no_python_sets_in_frozen(self, exhaust_projections, exhaustion_vectors):
        """Frozen list must be Mu linked-list, not Python set."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.single_op_exhausted")
        result = run_until_stable(exhaust_projections, vector["input"])

        # Frozen should be a linked list structure
        frozen = result.get("frozen")
        assert frozen is not None, "Expected frozen list"
        assert isinstance(frozen, dict), "Frozen must be dict (linked list)"
        assert "head" in frozen, "Frozen must have head"
        assert "tail" in frozen, "Frozen must have tail"

    def test_projection_order_matters(self, exhaust_projections):
        """Verify first-match-wins ordering for non-linear patterns."""
        # exhaust.scan_same (non-linear) must come before exhaust.scan_different
        ids = [p["id"] for p in exhaust_projections]
        same_idx = ids.index("exhaust.scan_same")
        diff_idx = ids.index("exhaust.scan_different")
        assert same_idx < diff_idx, "scan_same must come before scan_different"

        # exhaust.frozen_found (non-linear) must come before exhaust.frozen_check_tail
        found_idx = ids.index("exhaust.frozen_found")
        check_idx = ids.index("exhaust.frozen_check_tail")
        assert found_idx < check_idx, "frozen_found must come before frozen_check_tail"


class TestExhaustionEdgeCases:
    """Edge case tests for exhaustion detection."""

    def test_empty_trace(self, exhaust_projections):
        """Empty trace with tau_step should not crash."""
        reset_step_budget()
        input_data = {
            "_detect_exhaustion": {
                "trace": null,
                "frozen": null,
                "tau_step": 0,
                "operator_ids": null
            }
        }
        # Should not crash - will stall or return continue
        result = run_until_stable(exhaust_projections, input_data)
        # Empty trace means tau_step won't be found → action should be "continue"
        # If stalled at intermediate, must be valid exhaust mode (not random)
        if "action" in result:
            assert result["action"] == "continue", f"Empty trace should continue, got {result}"
        else:
            # Intermediate state must be valid exhaust mode
            assert result.get("_mode") in ("exhaust", "exhaust_find", "exhaust_scan"), \
                f"Invalid intermediate state: {result}"

    def test_multiple_frozen_operators(self, exhaust_projections):
        """Test with multiple operators already frozen."""
        reset_step_budget()
        input_data = {
            "_detect_exhaustion": {
                "trace": {
                    "head": {"step": 0, "state": "A", "projection": "op2"},
                    "tail": {
                        "head": {"step": 1, "state": "B", "projection": "op2"},
                        "tail": null
                    }
                },
                "frozen": {
                    "head": "op1",
                    "tail": {"head": "op3", "tail": null}
                },
                "tau_step": 0,
                "operator_ids": {
                    "head": "op1",
                    "tail": {"head": "op2", "tail": {"head": "op3", "tail": null}}
                }
            }
        }
        result = run_until_stable(exhaust_projections, input_data)
        # op2 is not in frozen list, should be frozen
        assert result.get("exhaustion_detected") is True
        assert result.get("operator_to_freeze") == "op2"
        assert result.get("action") == "freeze"


# =============================================================================
# Cross-Substrate Parity Tests (Python vs JavaScript)
# =============================================================================


def _normalize_for_cross_substrate(value):
    """Normalize Python values for cross-substrate comparison with JS.

    JavaScript doesn't distinguish int/float (all numbers are float64).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [_normalize_for_cross_substrate(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_for_cross_substrate(v) for k, v in value.items()}
    return value


def _run_js_exhaustion(input_data: dict) -> dict:
    """Run exhaustion detection via JS JSON API."""
    request = {"action": "run_exhaustion", "input": input_data}
    result = subprocess.run(
        ["node", "substrates/js/eval_step.js", "--json-api", json.dumps(request)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=60
    )

    for line in result.stdout.split('\n'):
        if line.startswith('JSON_API_RESPONSE:'):
            response = json.loads(line[len('JSON_API_RESPONSE:'):])
            if response.get("success"):
                return response["result"]
            raise RuntimeError(f"JS API error: {response.get('error')}")

    raise RuntimeError(f"No JSON_API_RESPONSE found: {result.stdout[:500]}")


class TestCrossSubstrateExhaustion:
    """Verify Python and JavaScript produce identical exhaustion results."""

    def test_js_loads_exhaust_seed(self):
        """Verify JS loads exhaust.v1.json correctly."""
        request = {"action": "get_constants"}
        result = subprocess.run(
            ["node", "substrates/js/eval_step.js", "--json-api", json.dumps(request)],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60
        )

        for line in result.stdout.split('\n'):
            if line.startswith('JSON_API_RESPONSE:'):
                response = json.loads(line[len('JSON_API_RESPONSE:'):])
                assert response.get("success"), f"API failed: {response}"
                assert response.get("exhaust_projection_count") == 11, \
                    f"Expected 11 exhaust projections, got {response.get('exhaust_projection_count')}"
                return

        pytest.fail("No JSON_API_RESPONSE found")

    def test_cross_substrate_no_tau(self, exhaust_projections, exhaustion_vectors):
        """Cross-substrate: no tau_step produces same result."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.no_tau")

        # Python result
        py_result = run_until_stable(exhaust_projections, vector["input"])

        # JS result
        js_result = _run_js_exhaustion(vector["input"])

        # Normalize and compare
        py_norm = _normalize_for_cross_substrate(py_result)
        js_norm = _normalize_for_cross_substrate(js_result)

        assert json.dumps(py_norm, sort_keys=True) == json.dumps(js_norm, sort_keys=True), \
            f"Cross-substrate mismatch:\nPython: {py_result}\nJS: {js_result}"

    def test_cross_substrate_exhaustion_detected(self, exhaust_projections, exhaustion_vectors):
        """Cross-substrate: exhaustion detection produces same result."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.single_op_exhausted")

        py_result = run_until_stable(exhaust_projections, vector["input"])
        js_result = _run_js_exhaustion(vector["input"])

        py_norm = _normalize_for_cross_substrate(py_result)
        js_norm = _normalize_for_cross_substrate(js_result)

        assert json.dumps(py_norm, sort_keys=True) == json.dumps(js_norm, sort_keys=True), \
            f"Cross-substrate mismatch:\nPython: {py_result}\nJS: {js_result}"

    def test_cross_substrate_different_op(self, exhaust_projections, exhaustion_vectors):
        """Cross-substrate: different operator produces same result."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.different_op")

        py_result = run_until_stable(exhaust_projections, vector["input"])
        js_result = _run_js_exhaustion(vector["input"])

        py_norm = _normalize_for_cross_substrate(py_result)
        js_norm = _normalize_for_cross_substrate(js_result)

        assert json.dumps(py_norm, sort_keys=True) == json.dumps(js_norm, sort_keys=True), \
            f"Cross-substrate mismatch:\nPython: {py_result}\nJS: {js_result}"

    def test_cross_substrate_already_frozen(self, exhaust_projections, exhaustion_vectors):
        """Cross-substrate: already frozen produces same result."""
        vector = next(v for v in exhaustion_vectors if v["id"] == "exhaust.already_frozen")

        py_result = run_until_stable(exhaust_projections, vector["input"])
        js_result = _run_js_exhaustion(vector["input"])

        py_norm = _normalize_for_cross_substrate(py_result)
        js_norm = _normalize_for_cross_substrate(js_result)

        assert json.dumps(py_norm, sort_keys=True) == json.dumps(js_norm, sort_keys=True), \
            f"Cross-substrate mismatch:\nPython: {py_result}\nJS: {js_result}"

    def test_cross_substrate_all_vectors(self, exhaust_projections, exhaustion_vectors):
        """Cross-substrate: all exhaustion vectors produce same results."""
        mismatches = []

        for vector in exhaustion_vectors:
            py_result = run_until_stable(exhaust_projections, vector["input"])
            try:
                js_result = _run_js_exhaustion(vector["input"])
            except Exception as e:
                mismatches.append(f"{vector['id']}: JS error - {e}")
                continue

            py_norm = _normalize_for_cross_substrate(py_result)
            js_norm = _normalize_for_cross_substrate(js_result)

            if json.dumps(py_norm, sort_keys=True) != json.dumps(js_norm, sort_keys=True):
                mismatches.append(f"{vector['id']}: Python={py_result}, JS={js_result}")

        assert not mismatches, f"Cross-substrate mismatches:\n" + "\n".join(mismatches)
