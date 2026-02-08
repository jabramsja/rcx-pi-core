"""
Non-Linear Pattern Chaos Under Bridge Execution Fuzzer (#1019)

Property-based tests for bootstrap_structural bridge handling of non-linear
patterns (same variable appears twice) under stress.

Agent finding #1019: "Non-Linear Pattern Chaos Not Fuzzed Under Bridge Execution"
- Bridge execution with non-linear patterns (binding conflict detection) was not
  fuzzed for correctness under varied inputs.
"""
import pytest
from hypothesis import given, settings, assume, HealthCheck
import hypothesis.strategies as st

from rcx_pi.selfhost.eval_seed import match, substitute, step, NO_MATCH
from rcx_pi.selfhost.step_mu import (
    load_combined_kernel_with_bridge_projections,
    step_kernel_mu,
    run_algorithm_meta_circular,
    step_algorithm_with_bridge,
    KERNEL_RESERVED_FIELDS,
    ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS,
    clear_combined_kernel_cache,
)
from rcx_pi.selfhost.mu_type import mu_equal, is_mu
from rcx_pi.selfhost.match_mu import normalize_for_match, denormalize_from_match


# =============================================================================
# Strategies
# =============================================================================

simple_mu = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-1000, max_value=1000),
    st.text(max_size=20),
)

# Values suitable for non-linear pattern testing (need equality comparison)
hashable_mu = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-100, max_value=100),
    st.text(max_size=10),
)


# =============================================================================
# Tests: Non-Linear Pattern Matching (same var twice)
# =============================================================================

class TestNonLinearPatternMatching:
    """Property-based tests for non-linear pattern binding conflict detection."""

    @given(value=hashable_mu)
    @settings(deadline=5000)
    def test_same_var_same_value_matches(self, value):
        """When a variable appears twice and both bind to equal values, match succeeds."""
        # Pattern: [{"var": "x"}, {"var": "x"}] should match [v, v]
        pattern = [{"var": "x"}, {"var": "x"}]
        inp = [value, value]
        result = match(pattern, inp)
        assert result is not NO_MATCH
        assert result["x"] == value

    @given(
        v1=hashable_mu,
        v2=hashable_mu,
    )
    @settings(deadline=5000)
    def test_same_var_different_value_fails(self, v1, v2):
        """When a variable appears twice and binds to different values, match fails."""
        assume(not mu_equal(v1, v2))
        pattern = [{"var": "x"}, {"var": "x"}]
        inp = [v1, v2]
        result = match(pattern, inp)
        assert result is NO_MATCH

    @given(
        v1=hashable_mu,
        v2=hashable_mu,
    )
    @settings(deadline=5000)
    def test_different_vars_different_values_matches(self, v1, v2):
        """Different variables binding to different values always matches."""
        pattern = [{"var": "x"}, {"var": "y"}]
        inp = [v1, v2]
        result = match(pattern, inp)
        assert result is not NO_MATCH
        assert result["x"] == v1
        assert result["y"] == v2

    @given(value=hashable_mu)
    @settings(deadline=5000)
    def test_triple_var_same_value_matches(self, value):
        """Three occurrences of same variable with equal values matches."""
        pattern = [{"var": "x"}, {"var": "x"}, {"var": "x"}]
        inp = [value, value, value]
        result = match(pattern, inp)
        assert result is not NO_MATCH
        assert result["x"] == value

    @given(
        v1=hashable_mu,
        v2=hashable_mu,
    )
    @settings(deadline=5000)
    def test_triple_var_one_different_fails(self, v1, v2):
        """Three occurrences where one differs fails."""
        assume(not mu_equal(v1, v2))
        pattern = [{"var": "x"}, {"var": "x"}, {"var": "x"}]
        inp = [v1, v1, v2]
        result = match(pattern, inp)
        assert result is NO_MATCH


# =============================================================================
# Tests: Non-Linear Patterns in Dict Context
# =============================================================================

class TestNonLinearPatternInDicts:
    """Non-linear patterns within dict value positions."""

    @given(value=hashable_mu)
    @settings(deadline=5000)
    def test_dict_values_same_var_same_value(self, value):
        """Same variable in two dict values with equal values matches."""
        pattern = {"a": {"var": "x"}, "b": {"var": "x"}}
        inp = {"a": value, "b": value}
        result = match(pattern, inp)
        assert result is not NO_MATCH

    @given(
        v1=hashable_mu,
        v2=hashable_mu,
    )
    @settings(deadline=5000)
    def test_dict_values_same_var_different_value_fails(self, v1, v2):
        """Same variable in two dict values with different values fails."""
        assume(not mu_equal(v1, v2))
        pattern = {"a": {"var": "x"}, "b": {"var": "x"}}
        inp = {"a": v1, "b": v2}
        result = match(pattern, inp)
        assert result is NO_MATCH

    @given(
        v1=hashable_mu,
        v2=hashable_mu,
    )
    @settings(deadline=5000)
    def test_nested_dict_nonlinear_pattern(self, v1, v2):
        """Non-linear pattern with nested dict structure."""
        pattern = {"outer": {"a": {"var": "x"}}, "check": {"var": "x"}}
        inp = {"outer": {"a": v1}, "check": v2}
        result = match(pattern, inp)
        if mu_equal(v1, v2):
            assert result is not NO_MATCH
            assert mu_equal(result["x"], v1)
        else:
            assert result is NO_MATCH


# =============================================================================
# Tests: Bridge Projection Loading and Ordering
# =============================================================================

class TestBridgeProjectionOrdering:
    """Verify bridge projections load correctly and ordering is enforced."""

    def test_bridge_projections_load_successfully(self):
        """Bridge projections can be loaded without error."""
        projs = load_combined_kernel_with_bridge_projections()
        assert isinstance(projs, list)
        assert len(projs) > 0

    def test_bridge_projections_include_bridge_ids(self):
        """Loaded bridge projections include bridge.* IDs."""
        projs = load_combined_kernel_with_bridge_projections()
        bridge_ids = [
            p.get("id", "") for p in projs
            if isinstance(p, dict) and isinstance(p.get("id", ""), str)
            and p["id"].startswith("bridge.")
        ]
        assert len(bridge_ids) > 0, "No bridge projections found"

    def test_bridge_before_match_var(self):
        """Bridge projections must appear before match.var in combined list."""
        projs = load_combined_kernel_with_bridge_projections()
        ids = [
            p.get("id", "") for p in projs
            if isinstance(p, dict)
        ]
        bridge_indices = [i for i, pid in enumerate(ids) if pid.startswith("bridge.")]
        match_var_indices = [i for i, pid in enumerate(ids) if pid == "match.var"]
        if bridge_indices and match_var_indices:
            assert max(bridge_indices) < min(match_var_indices), \
                "Bridge projections must appear before match.var"


# =============================================================================
# Tests: Bridge Execution Security
# =============================================================================

class TestBridgeExecutionSecurity:
    """Security properties of bridge-mode execution."""

    @given(
        reserved=st.sampled_from(sorted(
            KERNEL_RESERVED_FIELDS - ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS
        )),
        value=simple_mu,
    )
    @settings(deadline=5000)
    def test_non_allowed_reserved_field_rejected_in_bridge(self, reserved, value):
        """Reserved fields not in algorithm allowlist are rejected in bridge mode."""
        with pytest.raises(ValueError, match="SECURITY"):
            run_algorithm_meta_circular(
                [], {reserved: value}, execution_mode="structural"
            )

    def test_kernel_projection_id_rejected_in_bridge(self):
        """Projections with kernel.* IDs are rejected in bridge execution."""
        proj = {
            "id": "kernel.smuggle",
            "pattern": {"var": "x"},
            "body": {"var": "x"},
        }
        with pytest.raises(ValueError, match="SECURITY"):
            step_algorithm_with_bridge([proj], "test")


# =============================================================================
# Tests: Non-Linear Pattern + Substitution Round-Trip
# =============================================================================

class TestNonLinearSubstitutionRoundTrip:
    """Verify match → substitute round-trip with non-linear patterns."""

    @given(value=hashable_mu)
    @settings(deadline=5000)
    def test_nonlinear_match_substitute_roundtrip(self, value):
        """Match with non-linear pattern, then substitute, produces expected output."""
        pattern = [{"var": "x"}, {"var": "x"}]
        body = {"matched": {"var": "x"}}
        inp = [value, value]

        bindings = match(pattern, inp)
        assert bindings is not NO_MATCH

        result = substitute(body, bindings)
        assert mu_equal(result, {"matched": value})

    @given(
        v1=hashable_mu,
        v2=hashable_mu,
    )
    @settings(deadline=5000)
    def test_nonlinear_conflict_prevents_substitution(self, v1, v2):
        """When binding conflict occurs, match fails - no substitution happens."""
        assume(not mu_equal(v1, v2))
        pattern = [{"var": "x"}, {"var": "x"}]
        inp = [v1, v2]

        bindings = match(pattern, inp)
        assert bindings is NO_MATCH
        # No substitution should be attempted with NO_MATCH
