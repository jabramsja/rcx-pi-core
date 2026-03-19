"""
Wave 5A gate test: Boot1 observer step monotonicity normalization.

Verifies (at boot1_depth=0, no re-entry):
1. All observer step values are monotonically non-decreasing
2. All events within the same engine iteration share the same step value
   (per-iteration adjacency, not set membership)
3. Exhaustion emits the last zero-based step index, not a count
4. Both Python and JS Boot1 paths satisfy these invariants

Note: These tests run at boot1_depth=0 and do not exercise actual re-entry
(boot1_depth > 0). Re-entry coverage is tracked as a deferred non-blocker:
reports/deferred/non_blocking/w5a_reentry_gate_coverage.md
"""

from __future__ import annotations

import json
import subprocess

import pytest

from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline
from tests.repo_root import REPO_ROOT

pytestmark = [pytest.mark.slow]

# User projections that produce multiple engine steps without triggering
# boundary effects or reserved-field validation issues. Each step transforms
# the key, producing a chain: a→b→c→d→e→f→(closure).
_CHAIN_PROJECTIONS = [
    {"pattern": {"a": {"var": "n"}}, "body": {"b": {"var": "n"}}},
    {"pattern": {"b": {"var": "n"}}, "body": {"c": {"var": "n"}}},
    {"pattern": {"c": {"var": "n"}}, "body": {"d": {"var": "n"}}},
    {"pattern": {"d": {"var": "n"}}, "body": {"e": {"var": "n"}}},
    {"pattern": {"e": {"var": "n"}}, "body": {"f": {"var": "n"}}},
]


def _run_js_json_api(request_dict: dict) -> dict:
    """Run a JSON API request against the JS substrate."""
    result = subprocess.run(
        ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request_dict)],
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=120
    )
    for line in result.stdout.split('\n'):
        if line.startswith('JSON_API_RESPONSE:'):
            return json.loads(line[len('JSON_API_RESPONSE:'):])
    raise RuntimeError(
        f"No JSON_API_RESPONSE in stdout.\n"
        f"returncode: {result.returncode}\n"
        f"stdout: {result.stdout[:500]}\n"
        f"stderr: {result.stderr[:500]}"
    )


def _extract_steps(events: list[dict]) -> list[int]:
    """Extract step values from observer events that carry a step field."""
    return [e["step"] for e in events if "step" in e]


def _assert_monotonic(steps: list[int], label: str):
    """Assert step values are monotonically non-decreasing."""
    for i in range(1, len(steps)):
        assert steps[i] >= steps[i - 1], (
            f"{label}: step regression at index {i}: "
            f"step[{i-1}]={steps[i-1]} > step[{i}]={steps[i]}. "
            f"Full sequence: {steps}"
        )


def _assert_same_step_grouping(events: list[dict], label: str):
    """Assert all events between consecutive step_boundary events share step values.

    Events emitted within the same engine iteration must share the same step
    index. This catches off-by-one bugs where step_boundary uses pre-increment
    but terminal events use post-increment.

    Validates per-iteration adjacency: each non-boundary event must match the
    step of the immediately preceding step_boundary, not just any boundary.
    """
    current_step = None
    for e in events:
        if e.get("event_name") == "step_boundary":
            current_step = e.get("step")
        elif "step" in e and current_step is not None:
            assert e["step"] == current_step, (
                f"{label}: event '{e.get('event_name')}' has step={e['step']} "
                f"but preceding step_boundary had step={current_step}. "
                f"Events within the same engine iteration must share step values."
            )


class TestPythonBoot1StepMonotonicity:
    """Prove Python Boot1 observer steps are monotonic."""

    def test_multi_step_monotonic_and_grouped(self):
        """Boot1 multi-step produces monotonic, consistently-grouped step values."""
        events = []
        # Chain projections produce multiple engine steps ending in closure
        run_engine_pipeline(
            _CHAIN_PROJECTIONS, {"a": 1},
            use_boot1_recursive=True,
            max_engine_iterations=20,
            observer=events,
        )
        steps = _extract_steps(events)
        assert len(steps) >= 2, f"Expected >=2 step events, got {len(steps)}"
        _assert_monotonic(steps, "Python Boot1 multi-step")
        _assert_same_step_grouping(events, "Python Boot1 multi-step")

    def test_exhaustion_step_anchoring(self):
        """Boot1 exhaustion emits last zero-based step index, not count."""
        events = []
        max_iters = 3
        # Chain projections with low budget — exhausts before reaching terminal
        try:
            run_engine_pipeline(
                _CHAIN_PROJECTIONS, {"a": 1},
                use_boot1_recursive=True,
                max_engine_iterations=max_iters,
                observer=events,
            )
        except Exception:
            pass  # Expected — exhaustion raises

        # Must have collected events (not a trivial pass)
        assert len(events) >= 2, f"Expected >=2 events, got {len(events)}"

        # Find the fail_closed exhaustion event
        exhaustion_events = [
            e for e in events
            if e.get("event_name") == "fail_closed"
            and e.get("error_code") == "engine.exhausted"
        ]
        assert exhaustion_events, (
            f"Expected engine.exhausted fail_closed event. "
            f"Events: {[e.get('event_name') for e in events]}"
        )

        exhaust_step = exhaustion_events[-1]["step"]
        # Last zero-based step index = max_engine_iterations - 1
        assert exhaust_step == max_iters - 1, (
            f"Exhaustion step ({exhaust_step}) should equal "
            f"max_engine_iterations - 1 ({max_iters - 1})"
        )

        # Exhaustion step must match last step_boundary step
        step_boundaries = [e for e in events if e.get("event_name") == "step_boundary"]
        assert step_boundaries, "Expected at least one step_boundary event"
        last_boundary_step = step_boundaries[-1]["step"]
        assert exhaust_step == last_boundary_step, (
            f"Exhaustion step ({exhaust_step}) should equal last "
            f"step_boundary step ({last_boundary_step})"
        )


class TestJsBoot1StepMonotonicity:
    """Prove JS Boot1 observer steps are monotonic."""

    def test_multi_step_monotonic_and_grouped(self):
        """JS Boot1 multi-step produces monotonic, consistently-grouped step values."""
        resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "input": {"value": 42},
            "boot1LoopMode": True,
            "maxEngineIterations": 20,
            "observer": True,
        })
        assert resp.get("success"), f"JS engine failed: {resp.get('error')}"
        events = resp.get("observer_events", [])
        steps = _extract_steps(events)
        assert len(steps) >= 2, f"Expected >=2 step events, got {len(steps)}"
        _assert_monotonic(steps, "JS Boot1 multi-step")
        _assert_same_step_grouping(events, "JS Boot1 multi-step")

    def test_exhaustion_step_anchoring(self):
        """JS Boot1 exhaustion emits last zero-based step index, not count."""
        # Use chain projections with low budget to force exhaustion
        # (avoids reserved-field rejection that _run_engine input triggers)
        chain_projs = [
            {"pattern": {"a": {"var": "n"}}, "body": {"b": {"var": "n"}}},
            {"pattern": {"b": {"var": "n"}}, "body": {"c": {"var": "n"}}},
            {"pattern": {"c": {"var": "n"}}, "body": {"d": {"var": "n"}}},
            {"pattern": {"d": {"var": "n"}}, "body": {"e": {"var": "n"}}},
            {"pattern": {"e": {"var": "n"}}, "body": {"f": {"var": "n"}}},
        ]
        max_iters = 3
        resp = _run_js_json_api({
            "action": "run_engine_pipeline",
            "projections": chain_projs,
            "input": {"a": 1},
            "boot1LoopMode": True,
            "maxEngineIterations": max_iters,
            "observer": True,
        })
        # Exhaustion should cause failure
        events = resp.get("observer_events", [])

        # Must have collected events (not a trivial pass)
        assert len(events) >= 2, f"Expected >=2 events, got {len(events)}"

        exhaustion_events = [
            e for e in events
            if e.get("event_name") == "fail_closed"
            and e.get("error_code") == "engine.exhausted"
        ]
        assert exhaustion_events, (
            f"Expected engine.exhausted fail_closed event. "
            f"Events: {[e.get('event_name') for e in events]}"
        )

        exhaust_step = exhaustion_events[-1]["step"]
        # Last zero-based step index = max_engine_iterations - 1
        assert exhaust_step == max_iters - 1, (
            f"JS exhaustion step ({exhaust_step}) should equal "
            f"max_engine_iterations - 1 ({max_iters - 1})"
        )

        # Exhaustion step must match last step_boundary step
        step_boundaries = [e for e in events if e.get("event_name") == "step_boundary"]
        assert step_boundaries, "Expected at least one step_boundary event"
        last_boundary_step = step_boundaries[-1]["step"]
        assert exhaust_step == last_boundary_step, (
            f"JS exhaustion step ({exhaust_step}) should equal last "
            f"step_boundary step ({last_boundary_step})"
        )
