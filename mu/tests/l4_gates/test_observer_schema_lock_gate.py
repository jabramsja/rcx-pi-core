"""
L4 Gate: Observer event schema source-lock and parity hardening.

Proves the L4_ENABLER semantic shift: observer event schema is locked against
drift between doc, code constants, and actual runtime emission in both Python
and JS. No runtime changes — tests enforce existing behavior.

Covers:
- All emitted event_names are in VALID_EVENT_NAMES (Python+JS, trampoline+Boot1)
- Source-lock: all 5 event name strings exist in both substrate source files
- JS engine_terminal extras validated for value correctness
- Cross-substrate parity validates both equality and independent correctness
- boot1_depth presence/absence discipline

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_observer_schema_lock_gate.py -v
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

from rcx_pi.selfhost.step_mu import run_engine_pipeline, ENGINE_EXIT_REASONS
from rcx_pi.selfhost.kernel import reset_step_budget

pytestmark = [pytest.mark.slow]

# Canonical event name set (must match tests/structural/test_observer_events.py)
VALID_EVENT_NAMES = frozenset({
    "step_boundary",
    "stall_detected",
    "closure_detected",
    "fail_closed",
    "engine_terminal",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _js_request_with_observer(action, **kwargs):
    """Send a JSON API request with observer enabled."""
    request = {"action": action, "observer": True, **kwargs}
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
# Event name enforcement: all emitted names must be in VALID_EVENT_NAMES
# =============================================================================

class TestEmittedEventNameEnforcement:
    """Every event_name emitted by real engine runs must be registered."""

    def test_python_trampoline_event_names_valid(self):
        """All Python trampoline event names are in VALID_EVENT_NAMES."""
        reset_step_budget()
        observer = []
        run_engine_pipeline(
            [], "schema_lock_test",
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=50, observer=observer,
            use_boot1_recursive=False,
        )
        for event in observer:
            assert event["event_name"] in VALID_EVENT_NAMES, (
                f"Python trampoline emitted unregistered event: {event['event_name']!r}"
            )

    def test_python_boot1_event_names_valid(self):
        """All Python Boot1 event names are in VALID_EVENT_NAMES."""
        reset_step_budget()
        observer = []
        run_engine_pipeline(
            [], "schema_lock_test",
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=50, observer=observer,
            use_boot1_recursive=True,
        )
        for event in observer:
            assert event["event_name"] in VALID_EVENT_NAMES, (
                f"Python Boot1 emitted unregistered event: {event['event_name']!r}"
            )

    def test_js_trampoline_event_names_valid(self):
        """All JS trampoline event names are in VALID_EVENT_NAMES."""
        resp = _js_request_with_observer(
            "run_engine_pipeline",
            input="schema_lock_test",
            projections=[],
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
            boot1LoopMode=False,
        )
        assert resp["success"]
        for event in resp.get("observer_events", []):
            assert event["event_name"] in VALID_EVENT_NAMES, (
                f"JS trampoline emitted unregistered event: {event['event_name']!r}"
            )

    def test_js_boot1_event_names_valid(self):
        """All JS Boot1 event names are in VALID_EVENT_NAMES."""
        resp = _js_request_with_observer(
            "run_engine_pipeline",
            input="schema_lock_test",
            projections=[],
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
            boot1LoopMode=True,
        )
        assert resp["success"]
        for event in resp.get("observer_events", []):
            assert event["event_name"] in VALID_EVENT_NAMES, (
                f"JS Boot1 emitted unregistered event: {event['event_name']!r}"
            )


# =============================================================================
# Source lock: all 5 event name strings in both substrate files
# =============================================================================

class TestEventNameSourceLock:
    """All registered event names must appear as strings in both substrates."""

    def test_all_event_names_in_python_source(self):
        """Python step_mu.py contains all 5 event name strings."""
        py_path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
        source = py_path.read_text()
        for name in VALID_EVENT_NAMES:
            assert f'"{name}"' in source, (
                f"Python source missing event name string: {name!r}"
            )

    def test_all_event_names_in_js_source(self):
        """JS eval_step.js contains all 5 event name strings."""
        js_path = REPO_ROOT / "mu" / "host" / "js" / "eval_step.js"
        source = js_path.read_text()
        for name in VALID_EVENT_NAMES:
            assert f"'{name}'" in source, (
                f"JS source missing event name string: {name!r}"
            )

    def test_valid_event_names_count_is_five(self):
        """VALID_EVENT_NAMES has exactly 5 members."""
        assert len(VALID_EVENT_NAMES) == 5, (
            f"Expected 5 event names, got {len(VALID_EVENT_NAMES)}: {VALID_EVENT_NAMES}"
        )

    def test_engine_exit_reasons_count_is_four(self):
        """ENGINE_EXIT_REASONS has exactly 4 members."""
        assert len(ENGINE_EXIT_REASONS) == 4, (
            f"Expected 4 exit reasons, got {len(ENGINE_EXIT_REASONS)}: {ENGINE_EXIT_REASONS}"
        )


# =============================================================================
# JS engine_terminal value validation
# =============================================================================

class TestJsTerminalExtrasValueValidation:
    """JS engine_terminal extras must have valid values, not just presence."""

    def test_js_engine_terminal_reason_is_valid(self):
        """JS engine_exit_reason must be one of the known exit reasons."""
        resp = _js_request_with_observer(
            "run_engine_pipeline",
            input="test_input",
            projections=[],
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
            boot1LoopMode=False,
        )
        assert resp["success"]
        terminals = [e for e in resp.get("observer_events", [])
                     if e.get("event_name") == "engine_terminal"]
        assert len(terminals) == 1
        reason = terminals[0]["engine_exit_reason"]
        assert reason in ENGINE_EXIT_REASONS, (
            f"JS engine_exit_reason {reason!r} not in ENGINE_EXIT_REASONS"
        )

    def test_js_engine_terminal_iterations_positive(self):
        """JS engine_iterations_used must be int > 0."""
        resp = _js_request_with_observer(
            "run_engine_pipeline",
            input="test_input",
            projections=[],
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
            boot1LoopMode=False,
        )
        assert resp["success"]
        terminals = [e for e in resp.get("observer_events", [])
                     if e.get("event_name") == "engine_terminal"]
        assert len(terminals) == 1
        iters = terminals[0]["engine_iterations_used"]
        assert isinstance(iters, int), f"engine_iterations_used must be int, got {type(iters)}"
        assert iters > 0, f"engine_iterations_used must be > 0, got {iters}"


# =============================================================================
# Cross-substrate parity: independent correctness AND equality
# =============================================================================

class TestTerminalExtrasCrossSubstrateParity:
    """Both substrates must produce independently valid AND equal terminal extras."""

    def test_terminal_extras_independently_valid_and_equal(self):
        """Python and JS engine_terminal extras are both valid and match."""
        reset_step_budget()
        py_observer = []
        run_engine_pipeline(
            [], "parity_lock_test",
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=50, observer=py_observer,
            use_boot1_recursive=False,
        )
        js_resp = _js_request_with_observer(
            "run_engine_pipeline",
            input="parity_lock_test",
            projections=[],
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
            boot1LoopMode=False,
        )
        assert js_resp["success"]

        py_terms = [e for e in py_observer if e.get("event_name") == "engine_terminal"]
        js_terms = [e for e in js_resp.get("observer_events", [])
                     if e.get("event_name") == "engine_terminal"]

        assert len(py_terms) == 1, f"Python should emit 1 engine_terminal, got {len(py_terms)}"
        assert len(js_terms) == 1, f"JS should emit 1 engine_terminal, got {len(js_terms)}"

        py_t, js_t = py_terms[0], js_terms[0]

        # Independent validity
        assert py_t["engine_exit_reason"] in ENGINE_EXIT_REASONS
        assert js_t["engine_exit_reason"] in ENGINE_EXIT_REASONS
        assert isinstance(py_t["engine_iterations_used"], int) and py_t["engine_iterations_used"] > 0
        assert isinstance(js_t["engine_iterations_used"], int) and js_t["engine_iterations_used"] > 0

        # Cross-substrate equality
        assert py_t["engine_exit_reason"] == js_t["engine_exit_reason"], (
            f"Reason mismatch: Python={py_t['engine_exit_reason']!r}, "
            f"JS={js_t['engine_exit_reason']!r}"
        )
        assert py_t["engine_iterations_used"] == js_t["engine_iterations_used"], (
            f"Iterations mismatch: Python={py_t['engine_iterations_used']}, "
            f"JS={js_t['engine_iterations_used']}"
        )


# =============================================================================
# boot1_depth presence/absence discipline
# =============================================================================

class TestBoot1DepthDiscipline:
    """boot1_depth must appear on Boot1 events and be absent on trampoline events."""

    def test_python_trampoline_no_boot1_depth(self):
        """Python trampoline events must NOT have boot1_depth field."""
        reset_step_budget()
        observer = []
        run_engine_pipeline(
            [], "depth_test",
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=50, observer=observer,
            use_boot1_recursive=False,
        )
        for event in observer:
            assert "boot1_depth" not in event, (
                f"Trampoline event should not have boot1_depth: {event['event_name']}"
            )

    def test_python_boot1_has_boot1_depth(self):
        """Python Boot1 events must have boot1_depth field."""
        reset_step_budget()
        observer = []
        run_engine_pipeline(
            [], "depth_test",
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=50, observer=observer,
            use_boot1_recursive=True,
        )
        for event in observer:
            assert "boot1_depth" in event, (
                f"Boot1 event missing boot1_depth: {event['event_name']}"
            )
            assert isinstance(event["boot1_depth"], int)
            assert event["boot1_depth"] >= 0

    def test_js_trampoline_no_boot1_depth(self):
        """JS trampoline events must NOT have boot1_depth field."""
        resp = _js_request_with_observer(
            "run_engine_pipeline",
            input="depth_test",
            projections=[],
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
            boot1LoopMode=False,
        )
        assert resp["success"]
        for event in resp.get("observer_events", []):
            assert "boot1_depth" not in event, (
                f"JS trampoline event should not have boot1_depth: {event['event_name']}"
            )

    def test_js_boot1_has_boot1_depth(self):
        """JS Boot1 events must have boot1_depth field."""
        resp = _js_request_with_observer(
            "run_engine_pipeline",
            input="depth_test",
            projections=[],
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
            boot1LoopMode=True,
        )
        assert resp["success"]
        for event in resp.get("observer_events", []):
            assert "boot1_depth" in event, (
                f"JS Boot1 event missing boot1_depth: {event['event_name']}"
            )
            assert isinstance(event["boot1_depth"], int)
            assert event["boot1_depth"] >= 0


# =============================================================================
# Doc grounding: ObserverEventContract.v0.md lists all event names
# =============================================================================

class TestDocEventNameGrounding:
    """ObserverEventContract.v0.md must list all registered event names."""

    def test_doc_lists_all_event_names(self):
        """Every VALID_EVENT_NAME must appear in the contract doc."""
        doc_path = REPO_ROOT / "mu" / "docs" / "core" / "ObserverEventContract.v0.md"
        content = doc_path.read_text()
        for name in VALID_EVENT_NAMES:
            assert f"`{name}`" in content, (
                f"ObserverEventContract.v0.md missing event name: {name!r}"
            )
