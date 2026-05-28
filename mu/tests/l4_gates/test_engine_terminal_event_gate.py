"""
L4 Gate: Engine terminal observer event parity.

Proves the L4_STRUCTURAL semantic shift: both engine paths (trampoline + Boot1)
in Python and JS emit exactly one `engine_terminal` observer event on successful
terminal return, carrying engine_exit_reason and engine_iterations_used.

Error paths (engine.exhausted, engine.stalled_non_terminal) emit zero
engine_terminal events.

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_engine_terminal_event_gate.py -v
"""

from __future__ import annotations

import pytest

from tests.repo_root import REPO_ROOT
from tests.l4_gates.engine_evidence_cache import (
    cached_js_request,
    cached_python_pipeline,
    uncached_js_request,
)

from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline, ENGINE_EXIT_REASONS

from rcx_pi.selfhost.kernel import reset_step_budget

pytestmark = [pytest.mark.slow]

_CANONICAL_ENGINE_INPUT = "test_input"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_terminal_events(observer):
    """Return all engine_terminal events from an observer list."""
    return [e for e in observer if e.get("event_name") == "engine_terminal"]


def _python_observer(input_value, *, use_boot1_recursive=False):
    """Return cached Python engine observer evidence for deterministic cases."""
    return cached_python_pipeline(
        input_value=input_value,
        boot1_mode="true" if use_boot1_recursive else "false",
        observer_enabled=True,
    )["observer"]


def _js_request(action, **kwargs):
    """Send a JSON API request to eval_step.js and return the parsed response."""
    return cached_js_request(action, **kwargs)


def _js_request_with_observer(action, **kwargs):
    """Send a JSON API request with observer enabled."""
    return cached_js_request(action, observer=True, **kwargs)


def _js_request_with_observer_uncached(action, **kwargs):
    """Send a JSON API request with observer enabled and no evidence caching."""
    return uncached_js_request(action, observer=True, **kwargs)


# =============================================================================
# Python: engine_terminal event
# =============================================================================

class TestPythonEngineTerminalEvent:
    """Python engine paths emit exactly one engine_terminal on success."""

    def test_closure_emits_engine_terminal(self):
        """Successful closure run emits exactly one engine_terminal event."""
        observer = _python_observer(_CANONICAL_ENGINE_INPUT, use_boot1_recursive=False)
        terminals = _collect_terminal_events(observer)
        assert len(terminals) == 1, (
            f"Expected exactly 1 engine_terminal, got {len(terminals)}"
        )
        assert terminals[0]["engine_exit_reason"] == "closure"
        assert terminals[0]["engine_iterations_used"] > 0

    def test_exactly_one_terminal_event(self):
        """Count of engine_terminal events is always exactly 1 on success."""
        observer = _python_observer(_CANONICAL_ENGINE_INPUT, use_boot1_recursive=False)
        terminals = _collect_terminal_events(observer)
        assert len(terminals) == 1

    def test_no_engine_terminal_on_exhausted_error(self):
        """engine.exhausted raises RuntimeError, observer has 0 engine_terminal."""
        reset_step_budget()
        observer = []
        with pytest.raises(RuntimeError, match="exhausted"):
            run_engine_pipeline(
                [], _CANONICAL_ENGINE_INPUT,
                max_steps=10, max_engine_iterations=1,
                max_algorithm_iterations=50, observer=observer,
                use_boot1_recursive=False,
            )
        terminals = _collect_terminal_events(observer)
        assert len(terminals) == 0, (
            f"Error path should emit 0 engine_terminal, got {len(terminals)}"
        )

    def test_terminal_event_has_required_fields(self):
        """engine_terminal event has base 6 fields + engine_exit_reason + engine_iterations_used."""
        observer = _python_observer(_CANONICAL_ENGINE_INPUT, use_boot1_recursive=False)
        terminals = _collect_terminal_events(observer)
        assert len(terminals) == 1
        event = terminals[0]
        base_fields = {"event_name", "step", "state_hash", "error_code", "substrate", "timestamp"}
        extra_fields = {"engine_exit_reason", "engine_iterations_used"}
        assert base_fields.issubset(set(event.keys())), (
            f"Missing base fields: {base_fields - set(event.keys())}"
        )
        assert extra_fields.issubset(set(event.keys())), (
            f"Missing extra fields: {extra_fields - set(event.keys())}"
        )
        assert event["error_code"] is None
        assert event["engine_exit_reason"] in ENGINE_EXIT_REASONS
        assert isinstance(event["engine_iterations_used"], int)
        assert event["engine_iterations_used"] > 0

    def test_boot1_emits_engine_terminal(self):
        """Boot1 path also emits exactly one engine_terminal."""
        observer = _python_observer(_CANONICAL_ENGINE_INPUT, use_boot1_recursive=True)
        terminals = _collect_terminal_events(observer)
        assert len(terminals) == 1
        assert terminals[0]["engine_exit_reason"] == "closure"
        assert terminals[0]["engine_iterations_used"] > 0

    def test_boot1_and_trampoline_terminal_parity(self):
        """Both engine paths emit engine_terminal with same reason and iteration count."""
        obs_tramp = _python_observer(_CANONICAL_ENGINE_INPUT, use_boot1_recursive=False)
        obs_boot1 = _python_observer(_CANONICAL_ENGINE_INPUT, use_boot1_recursive=True)
        tramp_terms = _collect_terminal_events(obs_tramp)
        boot1_terms = _collect_terminal_events(obs_boot1)
        assert len(tramp_terms) == 1
        assert len(boot1_terms) == 1
        assert tramp_terms[0]["engine_exit_reason"] == boot1_terms[0]["engine_exit_reason"]
        assert tramp_terms[0]["engine_iterations_used"] == boot1_terms[0]["engine_iterations_used"]


# =============================================================================
# JS: engine_terminal event
# =============================================================================

class TestJsEngineTerminalEvent:
    """JS engine paths emit exactly one engine_terminal on success."""

    def test_js_closure_emits_engine_terminal(self):
        """JS successful closure run emits exactly one engine_terminal event."""
        resp = _js_request_with_observer(
            "run_engine_pipeline",
            input=_CANONICAL_ENGINE_INPUT,
            projections=[],
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
            boot1LoopMode=False,
        )
        assert resp["success"], f"JS failed: {resp.get('error')}"
        events = resp.get("observer_events", [])
        terminals = [e for e in events if e.get("event_name") == "engine_terminal"]
        assert len(terminals) == 1, (
            f"Expected exactly 1 engine_terminal in JS, got {len(terminals)}"
        )
        assert terminals[0]["engine_exit_reason"] == "closure"
        assert terminals[0]["engine_iterations_used"] > 0

    def test_js_no_engine_terminal_on_error(self):
        """JS engine.exhausted returns error, observer has 0 engine_terminal."""
        resp = _js_request_with_observer_uncached(
            "run_engine_pipeline",
            input=_CANONICAL_ENGINE_INPUT,
            projections=[],
            maxSteps=10, maxEngineIterations=1, maxAlgorithmIterations=50,
            boot1LoopMode=False,
        )
        assert not resp["success"], "Should fail with engine.exhausted"
        events = resp.get("observer_events", [])
        terminals = [e for e in events if e.get("event_name") == "engine_terminal"]
        assert len(terminals) == 0

    def test_js_exactly_one_terminal_event(self):
        """JS count of engine_terminal is always exactly 1 on success."""
        resp = _js_request_with_observer(
            "run_engine_pipeline",
            input=_CANONICAL_ENGINE_INPUT,
            projections=[],
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
            boot1LoopMode=False,
        )
        assert resp["success"]
        events = resp.get("observer_events", [])
        terminals = [e for e in events if e.get("event_name") == "engine_terminal"]
        assert len(terminals) == 1


# =============================================================================
# Cross-substrate parity
# =============================================================================

class TestCrossSubstrateTerminalEventParity:
    """Python and JS emit matching engine_terminal events for same inputs."""

    def test_closure_terminal_parity(self):
        """Both substrates emit engine_terminal with same reason for closure input."""
        py_observer = _python_observer(_CANONICAL_ENGINE_INPUT, use_boot1_recursive=False)
        js_resp = _js_request_with_observer(
            "run_engine_pipeline",
            input=_CANONICAL_ENGINE_INPUT,
            projections=[],
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
            boot1LoopMode=False,
        )
        assert js_resp["success"]

        py_terms = _collect_terminal_events(py_observer)
        js_terms = [e for e in js_resp.get("observer_events", [])
                     if e.get("event_name") == "engine_terminal"]

        assert len(py_terms) == 1
        assert len(js_terms) == 1
        assert py_terms[0]["engine_exit_reason"] == js_terms[0]["engine_exit_reason"], (
            f"Reason mismatch: Python={py_terms[0]['engine_exit_reason']!r}, "
            f"JS={js_terms[0]['engine_exit_reason']!r}"
        )
        assert py_terms[0]["engine_iterations_used"] == js_terms[0]["engine_iterations_used"], (
            f"Iterations mismatch: Python={py_terms[0]['engine_iterations_used']}, "
            f"JS={js_terms[0]['engine_iterations_used']}"
        )


# =============================================================================
# Source lock: engine_terminal string in both substrates
# =============================================================================

class TestEngineTerminalSourceLock:
    """Verify engine_terminal string exists in both substrate source files."""

    def test_python_source_contains_engine_terminal(self):
        """Python step_mu.py contains 'engine_terminal' string."""
        py_path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
        source = py_path.read_text()
        assert '"engine_terminal"' in source, "Python source missing 'engine_terminal'"

    def test_js_source_contains_engine_terminal(self):
        """JS source contains 'engine_terminal' string."""
        js_dir = REPO_ROOT / "mu" / "host" / "js"
        source = "\n".join(f.read_text() for f in sorted(js_dir.rglob("*.js")))
        assert "'engine_terminal'" in source, "JS source missing 'engine_terminal'"
