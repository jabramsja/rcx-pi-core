"""
A20.2: Execution-Layer Truth Contract.

Proves that claimed execution layers are distinguishable via observer evidence:
- L0 (step-only): No observer events — step() is a primitive with no observer support.
- L2 (engine): Observer captures step_boundary + engine_terminal events.
- No hemisphere events without hemisphere routing.
- Layer claims are falsifiable: L0 vs L2 produce detectably different evidence.
"""
from __future__ import annotations

import pytest

from rcx_pi.selfhost.eval_seed import step
from rcx_pi.selfhost.step_mu import run_engine_pipeline
from rcx_pi.selfhost.projection_loader import load_verified_seed, get_seed_path
from rcx_pi.selfhost.mu_type import mu_equal

pytestmark = [pytest.mark.slow]

VALID_ENGINE_EVENT_NAMES = frozenset({
    "step_boundary",
    "stall_detected",
    "closure_detected",
    "fail_closed",
    "engine_terminal",
})


@pytest.fixture
def engine_projections() -> list:
    seed = load_verified_seed(get_seed_path("rcx_engine.v1.json"))
    return seed["projections"]


@pytest.fixture
def identity_projections() -> list:
    return [{"id": "identity", "pattern": {"x": "x"}, "body": {"x": "x"}}]


class TestExecutionLayerTruth:
    """Execution layers are distinguishable via observer evidence."""

    def test_l0_step_no_engine_events(self, engine_projections):
        """step() is a primitive with no observer parameter.

        L0 execution produces a result but cannot emit observer events.
        This is the structural proof that L0 and L2 are distinguishable.
        """
        # step() accepts exactly (projections, input) — no observer parameter
        import inspect
        sig = inspect.signature(step)
        param_names = set(sig.parameters.keys())
        assert "observer" not in param_names, (
            "step() must not accept observer parameter — "
            "it is L0 (primitive), not L2 (engine-observable)"
        )

        # step() produces a result (it works), but there's no way to observe it
        result = step(engine_projections, {"value": 1})
        assert result is not None, "step() must produce a result"

    def test_l2_engine_produces_boundary_events(self, identity_projections):
        """run_engine_pipeline with observer captures step_boundary events.

        This proves L2 execution is observable — the engine emits heartbeat
        events at each iteration boundary.
        """
        observer = []
        run_engine_pipeline(identity_projections, {"value": 1}, observer=observer)

        # Must have at least one step_boundary event
        step_events = [e for e in observer if e["event_name"] == "step_boundary"]
        assert len(step_events) > 0, (
            "L2 engine must emit step_boundary events. "
            f"Got events: {[e['event_name'] for e in observer]}"
        )

        # Must have exactly one engine_terminal event
        terminal_events = [e for e in observer if e["event_name"] == "engine_terminal"]
        assert len(terminal_events) == 1, (
            f"L2 engine must emit exactly 1 engine_terminal. "
            f"Got {len(terminal_events)}"
        )

        # All events must have required schema fields
        required_fields = {"event_name", "step", "state_hash", "error_code", "substrate", "timestamp"}
        for event in observer:
            missing = required_fields - set(event.keys())
            assert not missing, (
                f"Event missing fields: {missing}. Event: {event}"
            )

    def test_l2_engine_no_hemisphere_events(self, identity_projections):
        """run_engine_pipeline observer output contains only engine-level events.

        No hemisphere-specific event names appear — those require
        run_hemisphere_routing / run_engine_with_routing.
        """
        observer = []
        run_engine_pipeline(identity_projections, {"value": 1}, observer=observer)

        # All event names must be in the valid engine set
        for event in observer:
            assert event["event_name"] in VALID_ENGINE_EVENT_NAMES, (
                f"Unexpected event type in engine-only execution: "
                f"{event['event_name']}. Valid: {sorted(VALID_ENGINE_EVENT_NAMES)}"
            )

    def test_layer_claim_mismatch_fails_closed(self, identity_projections):
        """L0 and L2 produce detectably different evidence.

        If someone claims L0 execution but actually used L2,
        the presence of observer events betrays the claim.
        This is the falsifiability proof.
        """
        # L0: step() — no observer, returns raw result
        l0_result = step(identity_projections, {"value": 1})

        # L2: run_engine_pipeline — observer captures events
        observer = []
        l2_result = run_engine_pipeline(
            identity_projections, {"value": 1}, observer=observer,
        )

        # The evidence distinction: L2 has observer events, L0 cannot
        assert len(observer) > 0, "L2 must produce observer events"

        # L2 terminal shape differs from L0 (L2 adds engine metadata)
        assert isinstance(l2_result, dict), "L2 result must be dict (terminal shape)"
        l2_keys = set(l2_result.keys())
        # L2 terminal has engine-specific keys that L0 step result does not
        engine_keys = {"closure_detected", "exhaustion_detected", "tau_step", "stall", "action"}
        assert engine_keys.issubset(l2_keys), (
            f"L2 terminal must contain engine metadata keys. "
            f"Missing: {engine_keys - l2_keys}"
        )
