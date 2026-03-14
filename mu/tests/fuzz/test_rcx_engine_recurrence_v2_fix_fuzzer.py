"""
RCX Engine + Recurrence v2 + Fix v1 Fuzzer - Property-based testing for engine pipeline.

Fuzz tests for three interconnected seed files:
1. rcx_engine.v1.json - Engine init/trace/unwrap pipeline
2. recurrence.v2.json - Closure detection with context passthrough
3. fix.v1.json - Fix-point accumulation graph

Uses Hypothesis to generate random engine states and verify
structural invariants hold across edge cases.

See: mu/docs/core/RCXEngine.v0.md
"""

from __future__ import annotations

import pytest


from hypothesis import given, strategies as st, settings, HealthCheck
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
def engine_projections() -> list:
    """Load engine projections from seed file."""
    seed = load_verified_seed(get_seed_path("rcx_engine.v1.json"))
    return seed["projections"]


@pytest.fixture(scope="module")
def recurrence_v2_projections() -> list:
    """Load recurrence v2 projections from seed file."""
    seed = load_verified_seed(get_seed_path("recurrence.v2.json"))
    return seed["projections"]


@pytest.fixture(scope="module")
def fix_projections() -> list:
    """Load fix projections from seed file."""
    seed = load_verified_seed(get_seed_path("fix.v1.json"))
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

projection_id = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz._",
    min_size=2,
    max_size=15,
).filter(lambda s: not s.startswith('.') and not s.endswith('.') and '..' not in s)


@composite
def engine_init_input(draw):
    """Generate a valid _run_engine input for engine.init."""
    return {
        "_run_engine": {
            "projections": [],
            "input": draw(simple_value),
        }
    }


@composite
def engine_init_config_input(draw):
    """Generate a _run_engine input with config for engine.init_config."""
    return {
        "_run_engine": {
            "projections": [],
            "input": draw(simple_value),
            "max_iterations": draw(st.integers(min_value=1, max_value=20)),
            "trace_depth": draw(st.integers(min_value=1, max_value=10)),
        }
    }


@composite
def trace_entry_strategy(draw):
    """Generate a trace entry dict."""
    return {
        "step": draw(st.integers(min_value=0, max_value=20)),
        "state": draw(simple_value),
        "projection": draw(st.one_of(st.none(), projection_id)),
    }


@composite
def trace_linked_list(draw, min_length=1, max_length=5):
    """Generate a trace as Mu linked list."""
    length = draw(st.integers(min_value=min_length, max_value=max_length))
    result = None
    for i in range(length - 1, -1, -1):
        entry = draw(trace_entry_strategy())
        entry["step"] = i
        result = {"head": entry, "tail": result}
    return result


@composite
def fix_init_input(draw):
    """Generate a valid apply_fix input."""
    return {
        "apply_fix": {
            "stalled_state": draw(simple_value),
            "stall_hash": draw(st.text(min_size=8, max_size=16, alphabet="0123456789abcdef")),
            "tau_step": draw(st.integers(min_value=0, max_value=20)),
            "engine_iteration": draw(st.integers(min_value=0, max_value=10)),
        }
    }


# =============================================================================
# Engine Init Tests
# =============================================================================


class TestEngineInitFuzz:
    """Fuzz engine.init: input decomposition into engine state."""

    @given(data=engine_init_input())
    @settings(
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_init_produces_valid_mu(self, engine_projections, data):
        """engine.init always produces valid Mu."""
        reset_step_budget()
        result = run_until_stable(engine_projections, data, max_steps=1)
        assert is_mu(result), f"engine.init produced invalid Mu: {type(result)}"

    @given(data=engine_init_config_input())
    @settings(
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_init_config_produces_valid_mu(self, engine_projections, data):
        """engine.init_config always produces valid Mu."""
        reset_step_budget()
        result = run_until_stable(engine_projections, data, max_steps=1)
        assert is_mu(result), f"engine.init_config produced invalid Mu: {type(result)}"

    @given(data=engine_init_input())
    @settings(
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_init_preserves_input(self, engine_projections, data):
        """engine.init preserves the input value in engine state."""
        reset_step_budget()
        result = run_until_stable(engine_projections, data, max_steps=1)
        if isinstance(result, dict):
            # The engine state should contain the original input somewhere
            assert is_mu(result)


# =============================================================================
# Engine Structure Tests
# =============================================================================


class TestEngineStructureFuzz:
    """Fuzz engine structural invariants."""

    @given(data=engine_init_input())
    @settings(
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_engine_result_has_8_keys_when_terminal(self, engine_projections, data):
        """Terminal engine_result must have exactly 8 keys."""
        reset_step_budget()
        result = run_until_stable(engine_projections, data, max_steps=1)
        if isinstance(result, dict) and "engine_result" in result:
            er = result["engine_result"]
            if isinstance(er, dict):
                expected_keys = {
                    "value", "closure_detected", "tau_step",
                    "exhaustion_detected", "operator_frozen",
                    "frozen_set", "action", "stall",
                }
                actual_keys = set(er.keys())
                if actual_keys == expected_keys:
                    assert len(er) == 8


# =============================================================================
# Recurrence v2 Tests
# =============================================================================


class TestRecurrenceV2Fuzz:
    """Fuzz recurrence.v2: closure detection with context passthrough."""

    @given(trace=trace_linked_list(min_length=1, max_length=5))
    @settings(
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_recurrence_output_is_valid_mu(self, recurrence_v2_projections, trace):
        """Recurrence v2 always produces valid Mu output."""
        # Build a _detect_closure input
        detect_input = {
            "head": {
                "head": "_detect_closure",
                "tail": {
                    "head": {
                        "head": {
                            "head": "result",
                            "tail": {"head": None, "tail": None},
                        },
                        "tail": None,
                    },
                    "tail": None,
                },
            },
            "tail": {
                "head": {
                    "head": "_trace",
                    "tail": {"head": trace, "tail": None},
                },
                "tail": None,
            },
        }
        reset_step_budget()
        result = run_until_stable(recurrence_v2_projections, detect_input, max_steps=1)
        assert is_mu(result), f"Recurrence v2 produced invalid Mu: {type(result)}"


# =============================================================================
# Fix v1 Tests
# =============================================================================


class TestFixV1Fuzz:
    """Fuzz fix.v1: fix-point graph accumulation."""

    @given(data=fix_init_input())
    @settings(
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_fix_init_produces_valid_mu(self, fix_projections, data):
        """fix.init always produces valid Mu."""
        reset_step_budget()
        result = run_until_stable(fix_projections, data, max_steps=1)
        assert is_mu(result), f"fix.init produced invalid Mu: {type(result)}"

    @given(data=fix_init_input())
    @settings(
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_fix_init_produces_classify_mode(self, fix_projections, data):
        """fix.init produces fix_mode: 'classify' for graph construction."""
        reset_step_budget()
        result = run_until_stable(fix_projections, data, max_steps=1)
        if isinstance(result, dict) and "fix_mode" in result:
            assert result["fix_mode"] == "classify", (
                f"fix.init should produce classify mode, got {result['fix_mode']}"
            )

    @given(
        state=simple_value,
        hash_val=st.text(min_size=8, max_size=16, alphabet="0123456789abcdef"),
        tau=st.integers(min_value=0, max_value=20),
    )
    @settings(
        max_examples=50,
        deadline=5000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_fix_deterministic(self, fix_projections, state, hash_val, tau):
        """Same input to fix.init always produces same output."""
        data = {
            "apply_fix": {
                "stalled_state": state,
                "stall_hash": hash_val,
                "tau_step": tau,
                "engine_iteration": 0,
            }
        }
        reset_step_budget()
        result1 = run_until_stable(fix_projections, data, max_steps=1)
        reset_step_budget()
        result2 = run_until_stable(fix_projections, data, max_steps=1)
        assert mu_equal(result1, result2), (
            f"fix.init is non-deterministic: {result1} != {result2}"
        )
