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
)


# Local fixtures (constraint #5: no underscored imports from rcx_pi)
HEMISPHERE_KEYS = frozenset({"r_null", "r_inf", "r_a", "lobes", "sink"})


def _local_default_hemispheres():
    return {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None}


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

            # Pipeline called with projections, input, default Boot1 recursive, and kwargs
            mock_pipeline.assert_called_once_with(
                ["proj1"], "input_val", use_boot1_recursive=True, max_steps=5
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


class TestKwargCollisionRegression:
    """Regression: use_boot1_recursive must not cause kwarg collision (P1 red-team)."""

    def test_explicit_false_no_collision(self):
        """Passing use_boot1_recursive=False explicitly must not raise TypeError."""
        fake_engine_result = {
            "value": "x", "closure_detected": False, "tau_step": 0,
            "exhaustion_detected": False, "operator_frozen": False,
            "frozen_set": None, "action": "continue", "stall": True,
        }
        fake_hemispheres = _local_default_hemispheres()

        with patch("rcx_pi.selfhost.step_mu.run_engine_pipeline") as mock_pipeline, \
             patch("rcx_pi.selfhost.step_mu.run_hemisphere_routing") as mock_routing:
            mock_pipeline.return_value = fake_engine_result
            mock_routing.return_value = fake_hemispheres

            # This used to raise TypeError: got multiple values for 'use_boot1_recursive'
            result = run_engine_with_routing(
                ["proj1"], "input_val", use_boot1_recursive=False, max_steps=5
            )

            mock_pipeline.assert_called_once_with(
                ["proj1"], "input_val", use_boot1_recursive=False, max_steps=5
            )
            assert "engine_result" in result

    def test_explicit_true_no_collision(self):
        """Passing use_boot1_recursive=True explicitly must not raise TypeError."""
        fake_engine_result = {
            "value": "x", "closure_detected": False, "tau_step": 0,
            "exhaustion_detected": False, "operator_frozen": False,
            "frozen_set": None, "action": "continue", "stall": True,
        }
        fake_hemispheres = _local_default_hemispheres()

        with patch("rcx_pi.selfhost.step_mu.run_engine_pipeline") as mock_pipeline, \
             patch("rcx_pi.selfhost.step_mu.run_hemisphere_routing") as mock_routing:
            mock_pipeline.return_value = fake_engine_result
            mock_routing.return_value = fake_hemispheres

            result = run_engine_with_routing(
                ["proj1"], "input_val", use_boot1_recursive=True, max_steps=5
            )

            mock_pipeline.assert_called_once_with(
                ["proj1"], "input_val", use_boot1_recursive=True, max_steps=5
            )
            assert "engine_result" in result

    def test_default_is_boot1(self):
        """Without explicit kwarg, use_boot1_recursive defaults to True (boot1 path)."""
        fake_engine_result = {
            "value": "x", "closure_detected": False, "tau_step": 0,
            "exhaustion_detected": False, "operator_frozen": False,
            "frozen_set": None, "action": "continue", "stall": True,
        }
        fake_hemispheres = _local_default_hemispheres()

        with patch("rcx_pi.selfhost.step_mu.run_engine_pipeline") as mock_pipeline, \
             patch("rcx_pi.selfhost.step_mu.run_hemisphere_routing") as mock_routing:
            mock_pipeline.return_value = fake_engine_result
            mock_routing.return_value = fake_hemispheres

            run_engine_with_routing(["proj1"], "input_val")

            mock_pipeline.assert_called_once_with(
                ["proj1"], "input_val", use_boot1_recursive=True
            )


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


class TestExactShapeValidation:
    """Exact-shape validation rejects extra keys (Phase 4 / P3a)."""

    def test_routing_rejects_extra_keys(self):
        """run_hemisphere_routing rejects result with extra keys."""
        from rcx_pi.selfhost.step_mu import run_hemisphere_routing

        # Craft an engine_result that, when routed, would produce 5 correct keys.
        # We can't easily make run_mu return extra keys, so we test the wrapper's
        # output validation in run_engine_with_routing instead.
        fake_engine_result = {
            "value": "x", "closure_detected": False, "tau_step": 0,
            "exhaustion_detected": False, "operator_frozen": False,
            "frozen_set": None, "action": "continue", "stall": True,
        }
        # Patch run_hemisphere_routing to return a dict with extra key
        with patch("rcx_pi.selfhost.step_mu.run_hemisphere_routing") as mock_routing:
            mock_routing.return_value = {
                "r_null": None, "r_inf": None, "r_a": None,
                "lobes": None, "sink": None, "extra_key": "bad",
            }
            with patch("rcx_pi.selfhost.step_mu.run_engine_pipeline") as mock_pipeline:
                mock_pipeline.return_value = fake_engine_result
                with pytest.raises(RuntimeError, match="unexpected shape"):
                    run_engine_with_routing([], "input")


class TestDefaultConsistency:
    """Guard against drift between constant and helper."""

    def test_default_keys_match_constant(self):
        """_local_default_hemispheres() keys exactly match HEMISPHERE_KEYS."""
        defaults = _local_default_hemispheres()
        assert set(defaults.keys()) == HEMISPHERE_KEYS
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


class TestRoutingPriorityRegression:
    """Regression tests for P1 merge blocker: stall must NOT swallow closure/null."""

    def test_closure_not_swallowed_by_stall(self):
        """closure=True + stall=True → r_a (not r_inf). P1 regression."""
        crafted_engine_result = {
            "value": "has_value", "closure_detected": True, "tau_step": 0,
            "exhaustion_detected": False, "operator_frozen": False,
            "frozen_set": None, "action": "continue", "stall": True,
        }
        with patch("rcx_pi.selfhost.step_mu.run_engine_pipeline") as mock_pipeline:
            mock_pipeline.return_value = crafted_engine_result
            result = run_engine_with_routing([], "ignored_input")

        h = result["hemispheres"]
        assert h["r_a"] is not None, "closure+stall should route to r_a"
        assert h["r_inf"] is None, "closure+stall must NOT route to r_inf"

    def test_null_not_swallowed_by_stall(self):
        """value=None + stall=True → r_null (not r_inf). P1 regression."""
        crafted_engine_result = {
            "value": None, "closure_detected": False, "tau_step": 0,
            "exhaustion_detected": False, "operator_frozen": False,
            "frozen_set": None, "action": "continue", "stall": True,
        }
        with patch("rcx_pi.selfhost.step_mu.run_engine_pipeline") as mock_pipeline:
            mock_pipeline.return_value = crafted_engine_result
            result = run_engine_with_routing([], "ignored_input")

        h = result["hemispheres"]
        assert h["r_null"] is not None, "null+stall should route to r_null"
        assert h["r_inf"] is None, "null+stall must NOT route to r_inf"


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

    # Manual chain (use_boot1_recursive=True matches wrapper's Boot1 default)
    engine_result = run_engine_pipeline(cycle_projs, initial, use_boot1_recursive=True, **engine_kwargs)
    hemispheres = _local_default_hemispheres()
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
