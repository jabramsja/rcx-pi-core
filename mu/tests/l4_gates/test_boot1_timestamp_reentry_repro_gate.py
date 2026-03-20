"""Boot1 timestamp reset behavioral reproduction gate test.

This reproduces the issue documented in:
  reports/deferred/non_blocking/boot1_observer_timestamp_reentry_regression.md

Current behavior (BUG):
- timestamp (obs_ts) RESETS on re-entry (non-monotonic across passes)
- step (step_index from total_iterations) does NOT reset (monotonic across passes)

Per ObserverEventContract.v0.md lines 64-67:
- Step is PRIMARY sort key (ascending)
- Timestamp is TIE-BREAKER for same-step events

Since same-step events never span re-entry depths, the timestamp reset does not
cause actual ordering violations. This test documents the current behavior as a
deferred non-blocker.

Run: PYTHONHASHSEED=0 pytest mu/tests/l4_gates/test_boot1_timestamp_reentry_repro_gate.py -v -s
"""
import json
import subprocess
import pytest
from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline
from rcx_pi.selfhost.kernel import reset_step_budget
from tests.repo_root import REPO_ROOT


pytestmark = [pytest.mark.slow]


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


# Same-ID cycling projections: trigger closure -> exhaustion freeze -> re-entry
_CYCLE_PROJECTIONS = [
    {"id": "cycle.loop", "pattern": {"state": "A"}, "body": {"state": "B"}},
    {"id": "cycle.loop", "pattern": {"state": "B"}, "body": {"state": "A"}},
]
_CYCLE_INPUT = {"state": "A"}


def _find_reentry_boundary(step_events):
    """Find the index of the first event after re-entry (boot1_depth > 0)."""
    for i, e in enumerate(step_events):
        if e['boot1_depth'] > 0 and (i == 0 or step_events[i-1]['boot1_depth'] == 0):
            return i
    return None


class TestBoot1TimestampReentryReproduction:
    """Reproduce and document Boot1 timestamp reset behavior across re-entry.

    These tests assert the CURRENT (buggy) behavior to ensure it is documented
    and any fix will cause these tests to fail (requiring update).
    """

    def test_python_timestamp_reset_on_real_reentry(self):
        """Python real re-entry via cycling projections - timestamp resets."""
        reset_step_budget()
        observer = []
        run_engine_pipeline(
            _CYCLE_PROJECTIONS, _CYCLE_INPUT,
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=100, observer=observer,
        )

        step_events = [e for e in observer if e["event_name"] == "step_boundary"]
        assert len(step_events) >= 2, "Expected multiple step events"

        reentry_idx = _find_reentry_boundary(step_events)
        assert reentry_idx is not None, "Expected re-entry to occur (boot1_depth > 0)"

        before = step_events[reentry_idx - 1]
        after = step_events[reentry_idx]

        # Document current behavior: timestamp resets, step stays monotonic
        ts_reset = after['timestamp'] < before['timestamp']
        step_monotonic = after['step'] > before['step']

        assert ts_reset, (
            f"Expected timestamp to reset on re-entry (current behavior). "
            f"Before: {before['timestamp']}, After: {after['timestamp']}"
        )
        assert step_monotonic, (
            f"Expected step to remain monotonic. "
            f"Before: {before['step']}, After: {after['step']}"
        )

    def test_js_timestamp_reset_on_real_reentry(self):
        """JS real re-entry via cycling projections - timestamp resets."""
        resp = _js_request(
            "run_engine_pipeline",
            projections=_CYCLE_PROJECTIONS, input=_CYCLE_INPUT,
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=100,
            observer=True,
        )
        assert resp["success"], f"JS request must succeed: {resp.get('error')}"

        step_events = [e for e in resp["observer_events"] if e.get("event_name") == "step_boundary"]
        assert len(step_events) >= 2, "Expected multiple step events"

        reentry_idx = _find_reentry_boundary(step_events)
        assert reentry_idx is not None, "Expected re-entry to occur (boot1_depth > 0)"

        before = step_events[reentry_idx - 1]
        after = step_events[reentry_idx]

        # Document current behavior: timestamp resets, step stays monotonic
        ts_reset = after['timestamp'] < before['timestamp']
        step_monotonic = after['step'] > before['step']

        assert ts_reset, (
            f"Expected timestamp to reset on re-entry (current behavior). "
            f"Before: {before['timestamp']}, After: {after['timestamp']}"
        )
        assert step_monotonic, (
            f"Expected step to remain monotonic. "
            f"Before: {before['step']}, After: {after['step']}"
        )

    def test_cross_substrate_parity(self):
        """Python and JS have identical timestamp reset behavior."""
        # Python
        reset_step_budget()
        py_observer = []
        run_engine_pipeline(
            _CYCLE_PROJECTIONS, _CYCLE_INPUT,
            max_steps=10, max_engine_iterations=20,
            max_algorithm_iterations=100, observer=py_observer,
        )
        py_steps = [e for e in py_observer if e["event_name"] == "step_boundary"]

        # JS
        resp = _js_request(
            "run_engine_pipeline",
            projections=_CYCLE_PROJECTIONS, input=_CYCLE_INPUT,
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=100,
            observer=True,
        )
        js_steps = [e for e in resp["observer_events"] if e.get("event_name") == "step_boundary"]

        # Same number of events
        assert len(py_steps) == len(js_steps), (
            f"Event count mismatch: Python={len(py_steps)}, JS={len(js_steps)}"
        )

        # Same timestamp and step patterns
        for i, (py_e, js_e) in enumerate(zip(py_steps, js_steps)):
            assert py_e['timestamp'] == js_e['timestamp'], (
                f"Timestamp mismatch at index {i}: Python={py_e['timestamp']}, JS={js_e['timestamp']}"
            )
            assert py_e['step'] == js_e['step'], (
                f"Step mismatch at index {i}: Python={py_e['step']}, JS={js_e['step']}"
            )
            assert py_e['boot1_depth'] == js_e['boot1_depth'], (
                f"Depth mismatch at index {i}: Python={py_e['boot1_depth']}, JS={js_e['boot1_depth']}"
            )
