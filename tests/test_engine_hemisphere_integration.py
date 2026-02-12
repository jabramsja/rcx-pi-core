"""
Engine → Hemisphere Integration Tests

Tests the handoff contract between run_engine_pipeline() and
run_hemisphere_routing() via the run_engine_with_routing() wrapper.

8 fast tests (green gate) + 2 slow tests (full suite).
No module-level pytestmark — per-test @pytest.mark.slow only.
"""
import pytest
from unittest.mock import patch, MagicMock

from rcx_pi.selfhost.step_mu import (
    run_engine_with_routing,
    hash_trace_for_recurrence,
    _default_hemispheres,
    _HEMISPHERE_KEYS,
)


# --- Fast tests (green gate, no @slow) ---


class TestWiringContract:
    """Verify run_engine_with_routing composes correctly via mocks."""

    def test_wiring_call_order(self):
        """Wrapper calls pipeline then routing with correct args."""
        fake_engine_result = {
            "value": "x", "closure_detected": False, "tau_step": 0,
            "exhaustion_detected": False, "operator_frozen": False,
            "frozen_set": None, "action": "continue", "stall": True,
        }
        fake_hemispheres = {
            "r_null": None, "r_inf": None, "r_a": None,
            "lobes": None, "sink": None,
        }

        with patch("rcx_pi.selfhost.step_mu.run_engine_pipeline") as mock_pipeline, \
             patch("rcx_pi.selfhost.step_mu.run_hemisphere_routing") as mock_routing:
            mock_pipeline.return_value = fake_engine_result
            mock_routing.return_value = fake_hemispheres

            result = run_engine_with_routing(
                ["proj1"], "input_val", max_steps=5
            )

            # Pipeline called with projections, input, and kwargs
            mock_pipeline.assert_called_once_with(
                ["proj1"], "input_val", max_steps=5
            )
            # Routing called with engine result + default hemispheres
            mock_routing.assert_called_once()
            args = mock_routing.call_args[0]
            assert args[0] is fake_engine_result

            # Return shape has both keys
            assert "engine_result" in result
            assert "hemispheres" in result
            assert result["engine_result"] is fake_engine_result
            assert result["hemispheres"] is fake_hemispheres


class TestInputValidation:
    """Fail-closed input validation on hemispheres arg."""

    def test_rejects_non_dict_hemispheres(self):
        """Non-dict hemispheres raises TypeError."""
        with pytest.raises(TypeError, match="hemispheres must be dict"):
            run_engine_with_routing([], "input", hemispheres="bad")

    def test_rejects_missing_hemisphere_keys(self):
        """Dict missing keys raises ValueError with sorted message."""
        incomplete = {"r_null": None, "r_inf": None}
        with pytest.raises(ValueError, match="hemispheres shape mismatch"):
            run_engine_with_routing([], "input", hemispheres=incomplete)

    def test_rejects_extra_hemisphere_keys(self):
        """Dict with extra keys raises ValueError."""
        extra = {
            "r_null": None, "r_inf": None, "r_a": None,
            "lobes": None, "sink": None, "bogus": None,
        }
        with pytest.raises(ValueError, match="hemispheres shape mismatch"):
            run_engine_with_routing([], "input", hemispheres=extra)


class TestOutputValidation:
    """Fail-closed output validation on routing result."""

    def test_bad_routing_output_raises(self):
        """RuntimeError if run_hemisphere_routing returns bad shape."""
        fake_engine_result = {
            "value": "x", "closure_detected": False, "tau_step": 0,
            "exhaustion_detected": False, "operator_frozen": False,
            "frozen_set": None, "action": "continue", "stall": True,
        }

        with patch("rcx_pi.selfhost.step_mu.run_engine_pipeline") as mock_pipeline, \
             patch("rcx_pi.selfhost.step_mu.run_hemisphere_routing") as mock_routing:
            mock_pipeline.return_value = fake_engine_result
            mock_routing.return_value = {"bad": "shape"}  # Wrong keys

            with pytest.raises(RuntimeError, match="unexpected shape"):
                run_engine_with_routing([], "input")


class TestDefaultConsistency:
    """Guard against drift between constant and helper."""

    def test_default_keys_match_constant(self):
        """_default_hemispheres() keys exactly match _HEMISPHERE_KEYS."""
        defaults = _default_hemispheres()
        assert set(defaults.keys()) == _HEMISPHERE_KEYS
        # All values are None
        assert all(v is None for v in defaults.values())


class TestCycleGuard:
    """Fail-closed cycle detection in hash_trace_for_recurrence."""

    def test_cyclic_trace_raises(self):
        """Cyclic linked list raises ValueError."""
        node_a = {"head": {"state": "A", "step": 0}, "tail": None}
        node_b = {"head": {"state": "B", "step": 1}, "tail": node_a}
        node_a["tail"] = node_b  # Create cycle: A → B → A → ...

        with pytest.raises(ValueError, match="cyclic linked list detected"):
            hash_trace_for_recurrence(node_a)

    def test_overcap_trace_raises(self):
        """Trace exceeding max_entries raises ValueError."""
        # Build a 5-entry trace, cap at 3
        trace = None
        for i in range(5):
            trace = {"head": {"state": str(i), "step": i}, "tail": trace}

        with pytest.raises(ValueError, match="exceeds 3 entries"):
            hash_trace_for_recurrence(trace, max_entries=3)


# --- Slow tests (per-test @pytest.mark.slow) ---


@pytest.mark.slow
def test_wrapper_equivalent_to_manual_chain():
    """run_engine_with_routing == manual run_engine_pipeline + run_hemisphere_routing."""
    from rcx_pi.selfhost.step_mu import run_engine_pipeline, run_hemisphere_routing
    from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
    from rcx_pi.selfhost.kernel import reset_step_budget

    reset_step_budget()

    paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
    cycle_projs = paxos_seed["projections"][:4]
    initial = {"paxos_trigger": "start_paxos"}

    engine_kwargs = dict(max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50)

    # Manual chain
    engine_result = run_engine_pipeline(cycle_projs, initial, **engine_kwargs)
    hemispheres = _default_hemispheres()
    manual_hemispheres = run_hemisphere_routing(engine_result, hemispheres)

    # Wrapper
    reset_step_budget()
    wrapper_result = run_engine_with_routing(
        cycle_projs, initial, **engine_kwargs
    )

    # Must be structurally identical
    from rcx_pi.selfhost.mu_type import mu_equal
    assert mu_equal(wrapper_result["engine_result"], engine_result)
    assert mu_equal(wrapper_result["hemispheres"], manual_hemispheres)


@pytest.mark.slow
def test_paxos_closure_routes_to_r_a():
    """Paxos livelock → closure_detected → routes to r_a hemisphere."""
    from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
    from rcx_pi.selfhost.kernel import reset_step_budget

    reset_step_budget()

    paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
    cycle_projs = paxos_seed["projections"][:4]

    result = run_engine_with_routing(
        cycle_projs, {"paxos_trigger": "start_paxos"},
        max_steps=6, max_engine_iterations=20, max_algorithm_iterations=50,
    )

    # Engine should detect closure
    assert result["engine_result"]["closure_detected"] is True

    # Hemisphere routing should route to r_a
    # Note: Mu denormalization converts {"head": x, "tail": None} → [x]
    hemispheres = result["hemispheres"]
    assert hemispheres["r_a"] is not None, "Paxos closure should route to r_a"
    # r_a entry should have closure_flag=True
    entry = hemispheres["r_a"][0]
    assert entry["closure_flag"] is True
    assert entry["origin"] == "engine"
