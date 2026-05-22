"""
L4 Gate: Boot1 default routing verification.

Proves the L4_STRUCTURAL semantic shift: run_engine_with_routing defaults
to Boot1 recursive path when caller omits the flag, in BOTH substrates.

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_boot1_default_routing_gate.py -v
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.repo_root import REPO_ROOT

from rcx_pi.selfhost.engine_pipeline import run_engine_with_routing, run_engine_pipeline



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _local_default_hemispheres():
    return {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None}


def _fake_engine_result():
    return {
        "value": "x", "closure_detected": False, "tau_step": 0,
        "exhaustion_detected": False, "operator_frozen": False,
        "frozen_set": None, "action": "continue", "stall": True,
    }


def _js_request(action, **kwargs):
    """Send a JSON API request to eval_step.js and return the parsed response."""
    request = {"action": action, **kwargs}
    js_path = REPO_ROOT / "mu" / "host" / "js" / "eval_step.js"
    result = subprocess.run(
        ["node", str(js_path), "--json-api", json.dumps(request)],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=60,
    )
    for line in result.stdout.split("\n"):
        if line.startswith("JSON_API_RESPONSE:"):
            return json.loads(line[len("JSON_API_RESPONSE:"):])
    pytest.fail(
        f"No JSON_API_RESPONSE in JS output.\n"
        f"returncode: {result.returncode}\n"
        f"stdout: {result.stdout[:500]}\n"
        f"stderr: {result.stderr[:500]}"
    )


# =============================================================================
# Python: omitted flag defaults to Boot1
# =============================================================================

@pytest.mark.slow
class TestPythonBoot1Default:
    """Python run_engine_with_routing defaults to Boot1 recursive path."""

    def test_omitted_flag_routes_boot1(self):
        """Omitting use_boot1_recursive routes to Boot1 (recursive) path."""
        with patch("rcx_pi.selfhost.engine_pipeline.run_engine_pipeline") as mock_pipeline, \
             patch("rcx_pi.selfhost.engine_pipeline.run_hemisphere_routing") as mock_routing:
            mock_pipeline.return_value = _fake_engine_result()
            mock_routing.return_value = _local_default_hemispheres()

            run_engine_with_routing(["proj1"], "input_val")

            mock_pipeline.assert_called_once_with(
                ["proj1"], "input_val", use_boot1_recursive=True
            )

    def test_explicit_false_routes_trampoline(self):
        """Explicit use_boot1_recursive=False routes trampoline path."""
        with patch("rcx_pi.selfhost.engine_pipeline.run_engine_pipeline") as mock_pipeline, \
             patch("rcx_pi.selfhost.engine_pipeline.run_hemisphere_routing") as mock_routing:
            mock_pipeline.return_value = _fake_engine_result()
            mock_routing.return_value = _local_default_hemispheres()

            run_engine_with_routing(["proj1"], "input_val", use_boot1_recursive=False)

            mock_pipeline.assert_called_once_with(
                ["proj1"], "input_val", use_boot1_recursive=False
            )

    def test_explicit_true_matches_default(self):
        """Explicit use_boot1_recursive=True matches omitted-flag behavior."""
        with patch("rcx_pi.selfhost.engine_pipeline.run_engine_pipeline") as mock_pipeline, \
             patch("rcx_pi.selfhost.engine_pipeline.run_hemisphere_routing") as mock_routing:
            mock_pipeline.return_value = _fake_engine_result()
            mock_routing.return_value = _local_default_hemispheres()

            run_engine_with_routing(["proj1"], "input_val", use_boot1_recursive=True)

            mock_pipeline.assert_called_once_with(
                ["proj1"], "input_val", use_boot1_recursive=True
            )

    def test_non_bool_flag_fails_typed(self):
        """Non-bool use_boot1_recursive raises TypeError (fail-closed)."""
        with pytest.raises(TypeError, match="use_boot1_recursive must be bool"):
            run_engine_with_routing(["proj1"], "input_val", use_boot1_recursive="true")


# =============================================================================
# JS: omitted flag defaults to Boot1
# =============================================================================

@pytest.mark.slow
class TestJsBoot1Default:
    """JS run_engine_with_routing defaults to Boot1 recursive path.

    Anti-theater: observer events prove actual route selection.
    Boot1 path emits events with boot1_depth field; trampoline does not.
    """

    def test_omitted_flag_routes_boot1_with_observer(self):
        """Omitting boot1LoopMode routes Boot1 — observer proves boot1_depth present."""
        resp = _js_request(
            "run_engine_with_routing",
            projections=[], input={"test": True},
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
            observer=True,
        )
        assert resp["success"], f"JS request must succeed: {resp.get('error')}"
        assert "observer_events" in resp, "observer must be returned"
        events = resp["observer_events"]
        assert len(events) > 0, "must emit at least one observer event"
        assert all("boot1_depth" in e for e in events), (
            "Default route must use Boot1 path (all events should have boot1_depth)"
        )

    def test_explicit_true_routes_boot1_with_observer(self):
        """Explicit boot1LoopMode=true routes Boot1 — observer proves boot1_depth."""
        resp = _js_request(
            "run_engine_with_routing",
            projections=[], input={"test": True},
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
            boot1LoopMode=True, observer=True,
        )
        assert resp["success"], f"JS request must succeed: {resp.get('error')}"
        assert "observer_events" in resp, "observer must be returned"
        events = resp["observer_events"]
        assert len(events) > 0, "must emit at least one observer event"
        assert all("boot1_depth" in e for e in events), (
            "Explicit true must use Boot1 path (all events should have boot1_depth)"
        )

    def test_explicit_false_routes_trampoline_with_observer(self):
        """Explicit boot1LoopMode=false routes trampoline — no boot1_depth in events."""
        resp = _js_request(
            "run_engine_with_routing",
            projections=[], input={"test": True},
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
            boot1LoopMode=False, observer=True,
        )
        assert resp["success"], f"Trampoline path should work: {resp.get('error')}"
        assert "observer_events" in resp, "observer must be returned"
        events = resp["observer_events"]
        assert len(events) > 0, "must emit at least one observer event"
        assert all("boot1_depth" not in e for e in events), (
            "Explicit false must use trampoline path (no boot1_depth in events)"
        )

    def test_omitted_matches_explicit_true(self):
        """Omitted and explicit true produce identical results."""
        resp_omit = _js_request(
            "run_engine_with_routing",
            projections=[], input={"test": True},
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
        )
        resp_true = _js_request(
            "run_engine_with_routing",
            projections=[], input={"test": True},
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
            boot1LoopMode=True,
        )
        assert resp_omit["success"] == resp_true["success"]
        if resp_omit["success"]:
            assert resp_omit["result"] == resp_true["result"]

    def test_non_bool_flag_fails_typed(self):
        """Non-boolean boot1LoopMode returns type_error."""
        resp = _js_request(
            "run_engine_with_routing",
            projections=[], input={"test": True},
            maxSteps=5, boot1LoopMode="true",
        )
        assert not resp["success"]
        assert resp["error_code"] == "type_error"


# =============================================================================
# Cross-substrate parity: default behavior matches
# =============================================================================

@pytest.mark.slow
class TestCrossSubstrateDefaultParity:
    """Both substrates must produce same result with omitted flag."""

    def test_omitted_flag_parity(self):
        """Python and JS produce same result when boot1 flag is omitted."""
        from rcx_pi.selfhost.kernel import reset_step_budget
        reset_step_budget()

        py_result = run_engine_with_routing(
            [], {"test": True}, max_steps=10,
            max_engine_iterations=20, max_algorithm_iterations=50,
        )
        js_resp = _js_request(
            "run_engine_with_routing",
            projections=[], input={"test": True},
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
        )
        assert js_resp["success"], f"JS failed: {js_resp.get('error')}"
        # Both used Boot1 default — engine_result values should match
        py_val = py_result["engine_result"]["value"]
        js_val = js_resp["result"]["engine_result"]["value"]
        assert py_val == js_val, f"Parity mismatch: Python={py_val}, JS={js_val}"


def _has_slow_mark(obj):
    marks = getattr(obj, "pytestmark", [])
    if not isinstance(marks, (list, tuple)):
        marks = [marks]
    return any(getattr(mark, "name", None) == "slow" for mark in marks)


def test_boot1_default_routing_expensive_classes_remain_slow_marked():
    """Lock default routing Boot1 evidence into the owned slow gate lane."""
    expensive_classes = (
        TestPythonBoot1Default,
        TestJsBoot1Default,
        TestCrossSubstrateDefaultParity,
    )
    missing = [cls.__name__ for cls in expensive_classes if not _has_slow_mark(cls)]
    assert not missing, f"Default routing Boot1 classes must stay @pytest.mark.slow: {missing}"
