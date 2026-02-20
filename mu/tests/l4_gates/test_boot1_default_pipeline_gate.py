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

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(REPO_ROOT))

from rcx_pi.selfhost.step_mu import run_engine_pipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
# Python: omitted flag defaults to Boot1 (observer route proof)
# =============================================================================

@pytest.mark.slow
class TestPythonPipelineBoot1Default:
    """Python run_engine_pipeline defaults to Boot1 recursive path.

    Anti-theater: observer events prove boot1_depth presence/absence.
    """

    def test_omitted_flag_routes_boot1(self):
        """Omitting use_boot1_recursive routes Boot1 — boot1_depth in events."""
        from rcx_pi.selfhost.kernel import reset_step_budget
        reset_step_budget()

        observer = []
        run_engine_pipeline(
            [], {"test": True},
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=50, observer=observer,
        )
        assert len(observer) > 0, "must emit at least one observer event"
        assert all("boot1_depth" in e for e in observer), (
            "Default route must use Boot1 path (all events should have boot1_depth)"
        )

    def test_explicit_true_routes_boot1(self):
        """Explicit use_boot1_recursive=True routes Boot1 — boot1_depth in events."""
        from rcx_pi.selfhost.kernel import reset_step_budget
        reset_step_budget()

        observer = []
        run_engine_pipeline(
            [], {"test": True},
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=50, observer=observer,
            use_boot1_recursive=True,
        )
        assert len(observer) > 0, "must emit at least one observer event"
        assert all("boot1_depth" in e for e in observer), (
            "Explicit true must use Boot1 path (all events should have boot1_depth)"
        )

    def test_explicit_false_routes_trampoline(self):
        """Explicit use_boot1_recursive=False routes trampoline — no boot1_depth."""
        from rcx_pi.selfhost.kernel import reset_step_budget
        reset_step_budget()

        observer = []
        run_engine_pipeline(
            [], {"test": True},
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=50, observer=observer,
            use_boot1_recursive=False,
        )
        assert len(observer) > 0, "must emit at least one observer event"
        assert all("boot1_depth" not in e for e in observer), (
            "Explicit false must use trampoline path (no boot1_depth in events)"
        )

    def test_omitted_matches_explicit_true(self):
        """Omitted and explicit true produce identical results."""
        from rcx_pi.selfhost.kernel import reset_step_budget

        reset_step_budget()
        result_omit = run_engine_pipeline(
            [], {"test": True},
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=50,
        )
        reset_step_budget()
        result_true = run_engine_pipeline(
            [], {"test": True},
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=50, use_boot1_recursive=True,
        )
        assert result_omit == result_true

    def test_non_bool_flag_fails_typed(self):
        """Non-bool use_boot1_recursive raises TypeError (fail-closed)."""
        with pytest.raises(TypeError, match="use_boot1_recursive must be bool"):
            run_engine_pipeline([], {"test": True}, use_boot1_recursive="true")


# =============================================================================
# JS: omitted flag defaults to Boot1 (observer route proof)
# =============================================================================

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
        resp = _js_request(
            "run_engine_pipeline",
            projections=[], input={"test": True},
            maxSteps=5, boot1LoopMode="true",
        )
        assert not resp["success"]
        assert resp["error_code"] == "type_error"
