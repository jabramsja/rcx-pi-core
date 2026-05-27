"""
L4 Gate: Boot1 default for direct engine pipeline.

Proves the L4_STRUCTURAL semantic shift: run_engine_pipeline defaults
to Boot1 recursive path when caller omits the flag, in BOTH substrates.

Anti-theater: observer events prove actual route selection.
Boot1 path emits events with boot1_depth field; trampoline does not.

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_boot1_default_pipeline_gate.py -v
"""

from __future__ import annotations

import pytest

from tests.l4_gates.engine_evidence_cache import (
    cached_js_request,
    cached_python_pipeline,
    uncached_js_request,
)

from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _js_request(action, **kwargs):
    """Send a JSON API request to eval_step.js and return the parsed response."""
    return cached_js_request(action, **kwargs)


def _js_request_uncached(action, **kwargs):
    """Send a JSON API request without evidence caching."""
    return uncached_js_request(action, **kwargs)


def _python_pipeline(boot1_mode: str, *, observer_enabled=False):
    """Return cached Python pipeline evidence for the fixed default-route case."""
    return cached_python_pipeline(
        input_value={"test": True},
        boot1_mode=boot1_mode,
        observer_enabled=observer_enabled,
    )


# =============================================================================
# Python: omitted flag defaults to Boot1 (observer route proof)
# =============================================================================

@pytest.mark.slow
class TestPythonPipelineBoot1Default:
    """Python run_engine_pipeline defaults to Boot1 recursive path.

    Anti-theater: observer events prove boot1_depth presence/absence.
    """

    def test_omitted_flag_routes_boot1(self):
        """Omitting use_boot1_recursive routes Boot1 — boot1_depth in events."""
        observer = _python_pipeline("omitted", observer_enabled=True)["observer"]
        assert len(observer) > 0, "must emit at least one observer event"
        assert all("boot1_depth" in e for e in observer), (
            "Default route must use Boot1 path (all events should have boot1_depth)"
        )

    def test_explicit_true_routes_boot1(self):
        """Explicit use_boot1_recursive=True routes Boot1 — boot1_depth in events."""
        observer = _python_pipeline("true", observer_enabled=True)["observer"]
        assert len(observer) > 0, "must emit at least one observer event"
        assert all("boot1_depth" in e for e in observer), (
            "Explicit true must use Boot1 path (all events should have boot1_depth)"
        )

    def test_explicit_false_routes_trampoline(self):
        """Explicit use_boot1_recursive=False routes trampoline — no boot1_depth."""
        observer = _python_pipeline("false", observer_enabled=True)["observer"]
        assert len(observer) > 0, "must emit at least one observer event"
        assert all("boot1_depth" not in e for e in observer), (
            "Explicit false must use trampoline path (no boot1_depth in events)"
        )

    def test_omitted_matches_explicit_true(self):
        """Omitted and explicit true produce identical results."""
        result_omit = _python_pipeline("omitted")["result"]
        result_true = _python_pipeline("true")["result"]
        assert result_omit == result_true

    def test_non_bool_flag_fails_typed(self):
        """Non-bool use_boot1_recursive raises TypeError (fail-closed)."""
        with pytest.raises(TypeError, match="use_boot1_recursive must be bool"):
            run_engine_pipeline([], {"test": True}, use_boot1_recursive="true")


# =============================================================================
# JS: omitted flag defaults to Boot1 (observer route proof)
# =============================================================================

@pytest.mark.slow
class TestJsPipelineBoot1Default:
    """JS run_engine_pipeline defaults to Boot1 recursive path.

    Anti-theater: observer events prove boot1_depth presence/absence.
    """

    def test_omitted_flag_routes_boot1_with_observer(self):
        """Omitting boot1LoopMode routes Boot1 — boot1_depth in observer events."""
        resp = _js_request(
            "run_engine_pipeline",
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
        """Explicit boot1LoopMode=true routes Boot1 — boot1_depth in events."""
        resp = _js_request(
            "run_engine_pipeline",
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
        """Explicit boot1LoopMode=false routes trampoline — no boot1_depth."""
        resp = _js_request(
            "run_engine_pipeline",
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
            "run_engine_pipeline",
            projections=[], input={"test": True},
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
        )
        resp_true = _js_request(
            "run_engine_pipeline",
            projections=[], input={"test": True},
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
            boot1LoopMode=True,
        )
        assert resp_omit["success"], f"Omitted failed: {resp_omit.get('error')}"
        assert resp_true["success"], f"Explicit true failed: {resp_true.get('error')}"
        assert resp_omit["result"] == resp_true["result"]

    def test_non_bool_flag_fails_typed(self):
        """Non-boolean boot1LoopMode returns type_error."""
        resp = _js_request_uncached(
            "run_engine_pipeline",
            projections=[], input={"test": True},
            maxSteps=5, boot1LoopMode="true",
        )
        assert not resp["success"]
        assert resp["error_code"] == "type_error"


def _has_slow_mark(obj):
    marks = getattr(obj, "pytestmark", [])
    if not isinstance(marks, (list, tuple)):
        marks = [marks]
    return any(getattr(mark, "name", None) == "slow" for mark in marks)


def test_boot1_default_pipeline_expensive_classes_remain_slow_marked():
    """Lock default pipeline Boot1 evidence into the owned slow gate lane."""
    expensive_classes = (
        TestPythonPipelineBoot1Default,
        TestJsPipelineBoot1Default,
    )
    missing = [cls.__name__ for cls in expensive_classes if not _has_slow_mark(cls)]
    assert not missing, f"Default pipeline Boot1 classes must stay @pytest.mark.slow: {missing}"
