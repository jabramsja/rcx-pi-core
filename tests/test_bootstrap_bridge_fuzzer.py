"""
Property-Based Fuzzer for Bootstrap-Structural Bridge (Step 7).

Tests non-linear pattern support via binding conflict detection.
Properties tested:
1. LINEAR_PARITY: (match.v2 + bridge) == match.v2 for linear patterns
2. NON_LINEAR_CORRECTNESS: Same var twice requires same value
3. DETERMINISM: Same input → same output
4. NO_CRASH: Valid Mu inputs never crash

See: docs/core/BootstrapStructuralBridge.v0.md
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hypothesis import given, settings, assume, strategies as st, HealthCheck

from rcx_pi.selfhost.eval_seed import step
from rcx_pi.selfhost.match_mu import normalize_for_match, bindings_to_dict
from rcx_pi.selfhost.mu_type import is_mu, mu_equal
from rcx_pi.selfhost.kernel import reset_step_budget


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def match_with_bridge_projections():
    """Load match.v2 + bootstrap_structural projections (combined at runtime)."""
    match_path = Path(__file__).parent.parent / "mu" / "substrate" / "match.v2.json"
    bridge_path = Path(__file__).parent.parent / "mu" / "bridge" / "bootstrap_structural.v1.json"

    with open(match_path) as f:
        match_seed = json.load(f)
    with open(bridge_path) as f:
        bridge_seed = json.load(f)

    # Combine: match.v2 projections + bridge projections
    # Order matters: bridge.var.check_existing must come before match.var
    match_projs = match_seed["projections"]
    bridge_projs = bridge_seed["projections"]

    # Insert bridge projections before match.var (index 0 in match.v2)
    return bridge_projs + match_projs


@pytest.fixture(scope="module")
def match_v2_projections():
    """Load match.v2 projections (baseline for linear parity)."""
    path = Path(__file__).parent.parent / "mu" / "substrate" / "match.v2.json"
    with open(path) as f:
        seed = json.load(f)
    return seed["projections"]


def run_match_structural(projections, pattern, value, max_steps=1000):
    """Run match using projections until terminal state."""
    reset_step_budget()

    norm_pattern = normalize_for_match(pattern)
    norm_value = normalize_for_match(value)

    state = {
        "match": {
            "pattern": norm_pattern,
            "value": norm_value
        },
        "_match_ctx": {}
    }

    for _ in range(max_steps):
        new_state = step(projections, state)
        if new_state == state:
            break
        state = new_state
        if isinstance(state, dict) and state.get("_mode") == "match_done":
            break

    return state


# =============================================================================
# Strategies
# =============================================================================


@st.composite
def mu_primitives(draw):
    """Generate primitive Mu values."""
    return draw(st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-10**6, max_value=10**6),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(max_size=20),
    ))


@st.composite
def mu_values(draw, max_depth=3):
    """Generate valid Mu values."""
    if max_depth <= 0:
        return draw(mu_primitives())

    return draw(st.one_of(
        mu_primitives(),
        st.lists(st.deferred(lambda: mu_values(max_depth - 1)), max_size=3),
        st.dictionaries(
            st.text(min_size=1, max_size=5),
            st.deferred(lambda: mu_values(max_depth - 1)),
            max_size=3
        ),
    ))


@st.composite
def variable_names(draw):
    """Generate valid variable names."""
    return draw(st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz",
        min_size=1,
        max_size=10
    ))


@st.composite
def linear_patterns(draw):
    """Generate linear patterns (each var appears at most once)."""
    return draw(st.one_of(
        # Catch-all
        st.builds(lambda v: {"var": v}, variable_names()),
        # Dict with single var
        st.builds(
            lambda k, v: {k: {"var": v}},
            st.text(min_size=1, max_size=5),
            variable_names()
        ),
    ))


# =============================================================================
# Property 1: LINEAR_PARITY
# =============================================================================


class TestLinearParityFuzzer:
    """Verify match.v2 + bridge preserves match.v2 behavior for linear patterns."""

    @given(pattern=linear_patterns(), value=mu_values(max_depth=2))
    @settings(deadline=5000)
    def test_linear_parity_with_v2(self, match_v2_projections, match_with_bridge_projections, pattern, value):
        """Property: (match.v2 + bridge)(linear_pattern, value) == match.v2(linear_pattern, value)."""
        reset_step_budget()
        result_v2 = run_match_structural(match_v2_projections, pattern, value)

        reset_step_budget()
        result_bridge = run_match_structural(match_with_bridge_projections, pattern, value)

        assert result_v2.get("_status") == result_bridge.get("_status"), (
            f"Linear parity violation:\n"
            f"  Pattern: {pattern}\n"
            f"  Value: {value}\n"
            f"  v2 status: {result_v2.get('_status')}\n"
            f"  bridge status: {result_bridge.get('_status')}"
        )


# =============================================================================
# Property 2: NON_LINEAR_CORRECTNESS
# =============================================================================


class TestNonLinearCorrectnessFuzzer:
    """Verify non-linear patterns enforce binding equality."""

    @given(var=variable_names(), val=mu_values(max_depth=2))
    @settings(deadline=5000)
    def test_same_values_match(self, match_with_bridge_projections, var, val):
        """Property: Non-linear pattern with matching values → success."""
        pattern = {"a": {"var": var}, "b": {"var": var}}
        value = {"a": val, "b": val}

        reset_step_budget()
        result = run_match_structural(match_with_bridge_projections, pattern, value)

        assert result.get("_status") == "success", (
            f"Non-linear match failed with matching values:\n"
            f"  Pattern: {pattern}\n"
            f"  Value: {value}"
        )

    @given(var=variable_names(), val1=mu_values(max_depth=2), val2=mu_values(max_depth=2))
    @settings(deadline=5000)
    def test_different_values_no_match(self, match_with_bridge_projections, var, val1, val2):
        """Property: Non-linear pattern with conflicting values → no_match."""
        assume(not mu_equal(val1, val2))

        pattern = {"a": {"var": var}, "b": {"var": var}}
        value = {"a": val1, "b": val2}

        reset_step_budget()
        result = run_match_structural(match_with_bridge_projections, pattern, value)

        assert result.get("_status") == "no_match", (
            f"Non-linear match succeeded with conflicting values:\n"
            f"  Pattern: {pattern}\n"
            f"  Value: {value}"
        )

    @given(var=variable_names(), val=mu_values(max_depth=2))
    @settings(deadline=5000)
    def test_triple_occurrence_same(self, match_with_bridge_projections, var, val):
        """Property: Same var 3 times with matching values → success."""
        pattern = {"a": {"var": var}, "b": {"var": var}, "c": {"var": var}}
        value = {"a": val, "b": val, "c": val}

        reset_step_budget()
        result = run_match_structural(match_with_bridge_projections, pattern, value)

        assert result.get("_status") == "success"


# =============================================================================
# Property 3: DETERMINISM
# =============================================================================


class TestDeterminismFuzzer:
    """Verify match is deterministic."""

    @given(pattern=mu_values(max_depth=2), value=mu_values(max_depth=2))
    @settings(deadline=5000)
    def test_deterministic_match(self, match_with_bridge_projections, pattern, value):
        """Property: Running twice with same inputs gives same result."""
        reset_step_budget()
        result1 = run_match_structural(match_with_bridge_projections, pattern, value)

        reset_step_budget()
        result2 = run_match_structural(match_with_bridge_projections, pattern, value)

        assert mu_equal(result1, result2), (
            f"Non-deterministic:\n"
            f"  Result 1: {result1}\n"
            f"  Result 2: {result2}"
        )


# =============================================================================
# Property 4: NO_CRASH
# =============================================================================


class TestNoCrashFuzzer:
    """Verify match never crashes on valid Mu inputs."""

    @given(pattern=mu_values(max_depth=2), value=mu_values(max_depth=2))
    @settings(deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_never_crashes(self, match_with_bridge_projections, pattern, value):
        """Property: match never crashes, always returns terminal state or stalls."""
        reset_step_budget()

        try:
            result = run_match_structural(match_with_bridge_projections, pattern, value)
            # Should reach a terminal state or stall
            assert result.get("_mode") == "match_done" or result == pattern or "mode" in result, (
                f"Unexpected result state:\n"
                f"  Pattern: {pattern}\n"
                f"  Value: {value}\n"
                f"  Result: {result}"
            )
        except Exception as e:
            pytest.fail(f"Match crashed on valid input:\n"
                       f"  Pattern: {pattern}\n"
                       f"  Value: {value}\n"
                       f"  Exception: {type(e).__name__}: {e}")


# =============================================================================
# Property 5: EDGE_CASES
# =============================================================================


class TestEdgeCasesFuzzer:
    """Verify edge cases are handled correctly."""

    @given(var=variable_names())
    @settings(deadline=5000)
    def test_null_value_binding(self, match_with_bridge_projections, var):
        """Non-linear with null values should match."""
        pattern = {"a": {"var": var}, "b": {"var": var}}
        value = {"a": None, "b": None}

        reset_step_budget()
        result = run_match_structural(match_with_bridge_projections, pattern, value)

        assert result.get("_status") == "success"

    @given(var=variable_names())
    @settings(deadline=5000)
    def test_empty_list_binding(self, match_with_bridge_projections, var):
        """Non-linear with empty list values should match."""
        pattern = {"a": {"var": var}, "b": {"var": var}}
        value = {"a": [], "b": []}

        reset_step_budget()
        result = run_match_structural(match_with_bridge_projections, pattern, value)

        assert result.get("_status") == "success"

    @given(var=variable_names())
    @settings(deadline=5000)
    def test_empty_dict_binding(self, match_with_bridge_projections, var):
        """Non-linear with empty dict values should match."""
        pattern = {"a": {"var": var}, "b": {"var": var}}
        value = {"a": {}, "b": {}}

        reset_step_budget()
        result = run_match_structural(match_with_bridge_projections, pattern, value)

        assert result.get("_status") == "success"
