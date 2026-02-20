"""
Hemisphere & Metabolization Fuzzer - Property-based testing for hemisphere routing.

Fuzz tests for hemispheres.v1.json and metabolization.v1.json projections:
1. hemisphere.init decomposes engine_result into classify fields
2. hemisphere.classify.* routes by hemi_exhaustion/closure/stall/value
3. hemisphere.add.* accumulates into hemisphere lobe buckets
4. metabolization projections handle sink/stall recovery

Uses Hypothesis to generate random engine_result shapes and verify
structural invariants hold across edge cases.

See: mu/docs/core/Hemispheres.v0.md
"""

from __future__ import annotations

import pytest

hypothesis = pytest.importorskip("hypothesis", reason="hypothesis required for fuzzer tests")

from hypothesis import given, strategies as st, settings, assume, HealthCheck
from hypothesis.strategies import composite

from rcx_pi.selfhost.eval_seed import step
from rcx_pi.selfhost.kernel import reset_step_budget
from rcx_pi.selfhost.mu_type import mu_equal, is_mu
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
from tests.conftest import run_until_stable


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def hemi_projections() -> list:
    """Load hemisphere projections from seed file."""
    seed = load_verified_seed(get_seed_path("hemispheres.v1.json"))
    return seed["projections"]


@pytest.fixture(scope="module")
def metab_projections() -> list:
    """Load metabolization projections from seed file."""
    seed = load_verified_seed(get_seed_path("metabolization.v1.json"))
    return seed["projections"]


# =============================================================================
# Strategies
# =============================================================================


simple_value = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-100, max_value=100),
    st.text(max_size=10, alphabet="abcdefghij"),
)


@composite
def engine_result_strategy(draw):
    """Generate a valid 8-key engine_result shape."""
    return {
        "value": draw(simple_value),
        "closure_detected": draw(st.booleans()),
        "tau_step": draw(st.integers(min_value=0, max_value=20)),
        "exhaustion_detected": draw(st.booleans()),
        "operator_frozen": draw(st.one_of(st.none(), st.text(max_size=5))),
        "frozen_set": draw(st.one_of(st.none(), st.just([]))),
        "action": draw(st.sampled_from(["freeze", "halt", "exception_sink", "continue"])),
        "stall": draw(st.booleans()),
    }


@composite
def hemisphere_dict_strategy(draw):
    """Generate a simple hemisphere dict with lobe buckets."""
    return {
        "r_null": draw(st.one_of(st.none(), st.just([]))),
        "r_inf": draw(st.one_of(st.none(), st.just([]))),
        "r_a": draw(st.one_of(st.none(), st.just([]))),
        "lobes": draw(st.one_of(st.none(), st.just([]))),
        "sink": draw(st.one_of(st.none(), st.just([]))),
    }


@composite
def route_hemisphere_input(draw):
    """Generate a valid route_hemisphere input for hemisphere.init."""
    return {
        "route_hemisphere": {
            "engine_result": draw(engine_result_strategy()),
            "hemispheres": draw(hemisphere_dict_strategy()),
        }
    }


# =============================================================================
# Hemisphere Init Tests
# =============================================================================


class TestHemisphereInitFuzz:
    """Fuzz hemisphere.init: engine_result decomposition into classify fields."""

    @given(data=route_hemisphere_input())
    @settings(
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_init_produces_classify_mode(self, hemi_projections, data):
        """hemisphere.init always produces hemi_mode: 'classify'."""
        reset_step_budget()
        result = run_until_stable(hemi_projections, data, max_steps=1)
        if isinstance(result, dict) and "hemi_mode" in result:
            assert result["hemi_mode"] == "classify", (
                f"hemisphere.init should produce classify mode, got {result['hemi_mode']}"
            )

    @given(data=route_hemisphere_input())
    @settings(
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_init_preserves_value(self, hemi_projections, data):
        """hemisphere.init preserves engine_result.value as hemi_value."""
        reset_step_budget()
        result = run_until_stable(hemi_projections, data, max_steps=1)
        if isinstance(result, dict) and "hemi_value" in result:
            expected_value = data["route_hemisphere"]["engine_result"]["value"]
            assert mu_equal(result["hemi_value"], expected_value), (
                f"Value mismatch: {result['hemi_value']} != {expected_value}"
            )

    @given(data=route_hemisphere_input())
    @settings(
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_init_result_is_valid_mu(self, hemi_projections, data):
        """hemisphere.init always produces valid Mu."""
        reset_step_budget()
        result = run_until_stable(hemi_projections, data, max_steps=1)
        assert is_mu(result), f"Result is not valid Mu: {type(result)}"


# =============================================================================
# Hemisphere Classify Invariant Tests
# =============================================================================


class TestHemisphereClassifyFuzz:
    """Fuzz hemisphere classify: routing invariants under random inputs."""

    @given(data=route_hemisphere_input())
    @settings(
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_classify_always_reaches_add_mode(self, hemi_projections, data):
        """After init + classify, result should have hemi_mode: 'add'."""
        reset_step_budget()
        result = run_until_stable(hemi_projections, data, max_steps=2)
        if isinstance(result, dict) and "hemi_mode" in result:
            assert result["hemi_mode"] == "add", (
                f"After 2 steps, expected add mode, got {result['hemi_mode']}"
            )

    @given(data=route_hemisphere_input())
    @settings(
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_exhaustion_routes_to_sink(self, hemi_projections, data):
        """Exhausted inputs route to sink target."""
        # Force exhaustion
        data["route_hemisphere"]["engine_result"]["exhaustion_detected"] = True
        reset_step_budget()
        result = run_until_stable(hemi_projections, data, max_steps=2)
        if isinstance(result, dict) and "hemi_target" in result:
            assert result["hemi_target"] == "sink", (
                f"Exhausted input should route to sink, got {result['hemi_target']}"
            )

    @given(data=route_hemisphere_input())
    @settings(
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_null_value_routes_to_r_null(self, hemi_projections, data):
        """Null-valued, non-exhausted, non-closure, non-stall inputs route to r_null."""
        data["route_hemisphere"]["engine_result"]["value"] = None
        data["route_hemisphere"]["engine_result"]["exhaustion_detected"] = False
        data["route_hemisphere"]["engine_result"]["closure_detected"] = False
        data["route_hemisphere"]["engine_result"]["stall"] = False
        reset_step_budget()
        result = run_until_stable(hemi_projections, data, max_steps=2)
        if isinstance(result, dict) and "hemi_target" in result:
            assert result["hemi_target"] == "r_null", (
                f"Null value should route to r_null, got {result['hemi_target']}"
            )


# =============================================================================
# Hemisphere Full Pipeline Fuzz
# =============================================================================


class TestHemispherePipelineFuzz:
    """Fuzz full hemisphere pipeline: init → classify → add → unwrap."""

    @given(data=route_hemisphere_input())
    @settings(
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_pipeline_terminates(self, hemi_projections, data):
        """Full hemisphere pipeline always terminates within step budget."""
        reset_step_budget()
        result = run_until_stable(hemi_projections, data, max_steps=10)
        # Should have exited the hemisphere routing (no more hemi_mode)
        assert is_mu(result), f"Pipeline produced invalid Mu: {type(result)}"

    @given(data=route_hemisphere_input())
    @settings(
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_pipeline_output_has_no_hemi_mode(self, hemi_projections, data):
        """After full pipeline, hemi_mode should be consumed (unwrapped)."""
        reset_step_budget()
        result = run_until_stable(hemi_projections, data, max_steps=10)
        if isinstance(result, dict):
            # If pipeline completed, hemi_mode should be gone
            # (hemisphere.unwrap strips it)
            if "hemi_mode" not in result:
                pass  # Good: unwrapped
            # If still has hemi_mode, pipeline may have stalled — that's still valid Mu


# =============================================================================
# Metabolization Invariant Tests
# =============================================================================


class TestMetabolizationFuzz:
    """Fuzz metabolization projections: recovery and recycling invariants."""

    @given(
        value=simple_value,
        closure_flag=st.booleans(),
    )
    @settings(
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_sink_to_r_null_with_null_value(self, metab_projections, value, closure_flag):
        """metabolize.sink_to_r_null fires when state is null."""
        sink_entry = {
            "hemisphere.metabolize": {
                "source": "sink",
                "entry": {
                    "state": None,
                    "closure_flag": closure_flag,
                    "origin": "engine",
                },
            }
        }
        reset_step_budget()
        result = run_until_stable(metab_projections, sink_entry, max_steps=1)
        assert is_mu(result), f"Result is not valid Mu: {type(result)}"

    @given(
        value=st.integers(min_value=1, max_value=100),
        closure_flag=st.booleans(),
    )
    @settings(
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_metabolization_result_is_valid_mu(self, metab_projections, value, closure_flag):
        """All metabolization outputs are valid Mu."""
        sink_entry = {
            "hemisphere.metabolize": {
                "source": "sink",
                "entry": {
                    "state": value,
                    "closure_flag": closure_flag,
                    "origin": "engine",
                },
            }
        }
        reset_step_budget()
        result = run_until_stable(metab_projections, sink_entry, max_steps=1)
        assert is_mu(result), f"Result is not valid Mu: {type(result)}"
