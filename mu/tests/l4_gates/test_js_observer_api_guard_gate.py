"""
L4 Gate: JS observer API guard — strict observer type validation through JSON API.

Proves the L4_STRUCTURAL semantic shift: JS JSON API now supports an opt-in
`observer_strict` field that passes the value directly to runtime functions,
exercising the Array.isArray guard added in Wave 10. Legacy `observer: true/false`
behavior is unchanged.

Covers:
- observer_strict with invalid types rejected via runtime guard (pipeline, routing, meta)
- observer_strict with valid types accepted ([], null)
- Legacy observer: true/false/omitted unchanged
- Meta API delta-count lock for pre-populated strict arrays
- Response-shape lock: invalid strict value never echoed as observer_events
- Source lock: all 3 handlers contain observer_strict branch
- Cross-substrate parity: Python and JS both reject invalid observer types

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_js_observer_api_guard_gate.py -v
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(REPO_ROOT))

from rcx_pi.selfhost.step_mu import run_engine_pipeline
from rcx_pi.selfhost.kernel import reset_step_budget

pytestmark = [pytest.mark.slow]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _js_request(action, **kwargs):
    """Send a JSON API request and return the parsed response."""
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


_PIPELINE_BASE = dict(
    input="api_guard_test",
    projections=[],
    maxSteps=10,
    maxEngineIterations=20,
    maxAlgorithmIterations=50,
)


# =============================================================================
# Pipeline API: observer_strict rejection
# =============================================================================

class TestPipelineStrictObserverRejection:
    """run_engine_pipeline API rejects invalid observer_strict types."""

    def test_rejects_string_observer_strict(self):
        """observer_strict: 'bad' -> error with observer.invalid_type."""
        resp = _js_request("run_engine_pipeline", observer_strict="bad", **_PIPELINE_BASE)
        assert not resp["success"]
        assert resp["error_code"] == "observer.invalid_type"

    def test_rejects_dict_observer_strict(self):
        """observer_strict: {} -> error with observer.invalid_type."""
        resp = _js_request("run_engine_pipeline", observer_strict={}, **_PIPELINE_BASE)
        assert not resp["success"]
        assert resp["error_code"] == "observer.invalid_type"

    def test_rejects_int_observer_strict(self):
        """observer_strict: 42 -> error with observer.invalid_type."""
        resp = _js_request("run_engine_pipeline", observer_strict=42, **_PIPELINE_BASE)
        assert not resp["success"]
        assert resp["error_code"] == "observer.invalid_type"


# =============================================================================
# Pipeline API: observer_strict acceptance
# =============================================================================

class TestPipelineStrictObserverAcceptance:
    """run_engine_pipeline API accepts valid observer_strict types."""

    def test_accepts_array_observer_strict(self):
        """observer_strict: [] -> success with observer_events."""
        resp = _js_request("run_engine_pipeline", observer_strict=[], **_PIPELINE_BASE)
        assert resp["success"]
        assert "observer_events" in resp
        assert isinstance(resp["observer_events"], list)

    def test_accepts_null_observer_strict(self):
        """observer_strict: null -> success, no observer_events."""
        resp = _js_request("run_engine_pipeline", observer_strict=None, **_PIPELINE_BASE)
        assert resp["success"]
        assert "observer_events" not in resp


# =============================================================================
# Backward compatibility: legacy observer unchanged
# =============================================================================

class TestLegacyObserverBackwardCompat:
    """Legacy observer: true/false/omitted behavior is unchanged."""

    def test_observer_true_still_works(self):
        """observer: true -> success with observer_events (legacy path)."""
        resp = _js_request("run_engine_pipeline", observer=True, **_PIPELINE_BASE)
        assert resp["success"]
        assert "observer_events" in resp
        assert isinstance(resp["observer_events"], list)
        assert len(resp["observer_events"]) > 0

    def test_observer_omitted_no_events(self):
        """observer omitted -> success, no observer_events."""
        resp = _js_request("run_engine_pipeline", **_PIPELINE_BASE)
        assert resp["success"]
        assert "observer_events" not in resp


# =============================================================================
# Routing API: observer_strict rejection
# =============================================================================

class TestRoutingStrictObserverRejection:
    """run_engine_with_routing API rejects invalid observer_strict."""

    def test_routing_rejects_string_observer_strict(self):
        """observer_strict: 'bad' through routing -> observer.invalid_type."""
        resp = _js_request(
            "run_engine_with_routing",
            observer_strict="bad",
            input="routing_guard_test",
            projections=[],
            maxSteps=10,
            maxEngineIterations=20,
            maxAlgorithmIterations=50,
        )
        assert not resp["success"]
        assert resp["error_code"] == "observer.invalid_type"


# =============================================================================
# Meta API: observer_strict rejection + delta-count lock
# =============================================================================

class TestMetaStrictObserverGuard:
    """run_engine_pipeline_meta API rejects invalid and handles delta counts."""

    def test_meta_rejects_string_observer_strict(self):
        """observer_strict: 'bad' through meta API -> observer.invalid_type."""
        resp = _js_request(
            "run_engine_pipeline_meta",
            observer_strict="bad",
            input="meta_guard_test",
            projections=[],
            maxSteps=10,
            maxEngineIterations=20,
            maxAlgorithmIterations=50,
        )
        assert not resp["success"]
        assert resp["error_code"] == "observer.invalid_type"

    def test_meta_delta_count_with_prepopulated_strict_array(self):
        """Pre-populated strict array does not inflate engine_iterations_used."""
        # Pre-populate with 3 fake step_boundary events
        prior_events = [
            {"event_name": "step_boundary", "step": i, "state_hash": None,
             "error_code": None, "substrate": "js", "timestamp": i}
            for i in range(3)
        ]
        resp = _js_request(
            "run_engine_pipeline_meta",
            observer_strict=prior_events,
            input="delta_test",
            projections=[],
            maxSteps=10,
            maxEngineIterations=20,
            maxAlgorithmIterations=50,
        )
        assert resp["success"]
        iters = resp["result"]["engine_iterations_used"]
        # Must NOT include the 3 pre-populated events
        assert iters > 0, f"engine_iterations_used must be > 0, got {iters}"
        # A fresh run produces the same count
        resp_fresh = _js_request(
            "run_engine_pipeline_meta",
            observer_strict=[],
            input="delta_test",
            projections=[],
            maxSteps=10,
            maxEngineIterations=20,
            maxAlgorithmIterations=50,
        )
        assert resp_fresh["success"]
        assert resp_fresh["result"]["engine_iterations_used"] == iters, (
            f"Delta mismatch: pre-populated={iters}, "
            f"fresh={resp_fresh['result']['engine_iterations_used']}"
        )


# =============================================================================
# Response-shape lock: invalid strict value never echoed
# =============================================================================

class TestResponseShapeLock:
    """Invalid observer_strict must never appear as observer_events."""

    def test_invalid_strict_not_echoed_as_observer_events(self):
        """String observer_strict must not leak into response as observer_events."""
        resp = _js_request("run_engine_pipeline", observer_strict="bad_string", **_PIPELINE_BASE)
        assert not resp["success"]
        assert "observer_events" not in resp, (
            f"Invalid observer_strict leaked into response: {resp.get('observer_events')}"
        )


# =============================================================================
# Source lock: all 3 handlers contain observer_strict branch
# =============================================================================

class TestSourceLock:
    """JS source must contain observer_strict in all 3 API handlers."""

    def test_source_contains_three_observer_strict_branches(self):
        """eval_step.js has observer_strict in all 3 API handlers (2 refs each)."""
        js_path = REPO_ROOT / "mu" / "host" / "js" / "eval_step.js"
        source = js_path.read_text()
        count = source.count("request.observer_strict")
        # 3 handlers × 2 references each (conditional + value) = 6
        assert count == 6, (
            f"Expected 6 request.observer_strict references (3 handlers × 2), got {count}"
        )


# =============================================================================
# Cross-substrate parity: both reject invalid observer with same error code
# =============================================================================

class TestCrossSubstrateParity:
    """Python and JS both reject invalid observer types with matching semantics."""

    def test_python_and_js_both_reject_invalid_observer(self):
        """Python TypeError and JS RcxError both reference observer.invalid_type."""
        # Python path
        reset_step_budget()
        with pytest.raises(TypeError, match="observer.invalid_type"):
            run_engine_pipeline(
                [], "parity_test",
                max_steps=10, max_engine_iterations=20,
                max_algorithm_iterations=50,
                observer="bad",
            )

        # JS path (via strict API)
        resp = _js_request(
            "run_engine_pipeline",
            observer_strict="bad",
            **_PIPELINE_BASE,
        )
        assert not resp["success"]
        assert resp["error_code"] == "observer.invalid_type", (
            f"JS error_code mismatch: {resp['error_code']}"
        )
