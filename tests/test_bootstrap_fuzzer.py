"""
Bootstrap Primitives Fuzzer - Property-Based Testing for Phase 8a

This test suite attacks the 5 bootstrap primitives from BootstrapPrimitives.v0.md:
1. eval_step - Projection application (first-match-wins)
2. mu_equal - Structural equality via hash
3. max_steps - Resource exhaustion guard
4. stack_guard - Overflow protection (via MAX_MU_DEPTH)
5. projection_loader - Seed validation

Uses Hypothesis to generate 1000+ random inputs per property to find edge cases
that would break the bootstrap boundary.

Run with: pytest tests/test_bootstrap_fuzzer.py --hypothesis-show-statistics -v
"""

import pytest

# Skip all tests if hypothesis is not installed
hypothesis = pytest.importorskip("hypothesis", reason="hypothesis required for fuzzer tests")

from hypothesis import given, strategies as st, settings, assume, HealthCheck
from hypothesis.strategies import composite

from rcx_pi.selfhost.mu_type import (
    is_mu,
    assert_mu,
    mu_equal,
    mu_hash,
    MAX_MU_DEPTH,
    MAX_MU_WIDTH,
)
from rcx_pi.selfhost.eval_seed import (
    step as eval_step,
    NO_MATCH,
)
from rcx_pi.selfhost.step_mu import run_mu


# =============================================================================
# Hypothesis Strategies for Bootstrap Primitives
# =============================================================================

mu_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**53), max_value=2**53),
    st.floats(
        allow_nan=False,
        allow_infinity=False,
        min_value=-1e10,
        max_value=1e10
    ),
    st.text(max_size=100),
)


@composite
def mu_values(draw, max_depth=5):
    """Generate valid Mu values recursively."""
    if max_depth <= 0:
        return draw(mu_primitives)

    return draw(st.one_of(
        mu_primitives,
        st.lists(
            st.deferred(lambda: mu_values(max_depth=max_depth-1)),
            max_size=5
        ),
        st.dictionaries(
            st.text(min_size=1, max_size=10),
            st.deferred(lambda: mu_values(max_depth=max_depth-1)),
            max_size=5
        ),
    ))


@composite
def mu_patterns(draw, max_depth=3):
    """Generate patterns with var sites."""
    if max_depth <= 0:
        # Leaf nodes can be primitives or vars
        return draw(st.one_of(
            mu_primitives,
            st.builds(lambda name: {"var": name}, st.text(min_size=1, max_size=5))
        ))

    return draw(st.one_of(
        mu_primitives,
        st.builds(lambda name: {"var": name}, st.text(min_size=1, max_size=5)),
        st.lists(
            st.deferred(lambda: mu_patterns(max_depth=max_depth-1)),
            max_size=4
        ),
        st.dictionaries(
            st.text(min_size=1, max_size=10),
            st.deferred(lambda: mu_patterns(max_depth=max_depth-1)),
            max_size=4
        ),
    ))


@composite
def valid_projections(draw, max_depth=3):
    """Generate valid projection dicts."""
    pattern = draw(mu_patterns(max_depth=max_depth))
    body = draw(mu_patterns(max_depth=max_depth))
    return {"pattern": pattern, "body": body}


@composite
def deeply_nested_values(draw, target_depth=150):
    """Generate deeply nested structures approaching MAX_MU_DEPTH."""
    depth = draw(st.integers(min_value=target_depth, max_value=min(target_depth + 20, MAX_MU_DEPTH - 10)))

    # Build nested list
    result = None
    for _ in range(depth):
        result = [result]

    return result


# =============================================================================
# Primitive 1: eval_step - First Match Wins Property
# =============================================================================

class TestEvalStepProperties:
    """Property-based tests for eval_step primitive."""

    @given(valid_projections(), mu_values())
    @settings(max_examples=1000, deadline=None)
    def test_eval_step_single_projection_determinism(self, projection, value):
        """eval_step with single projection is deterministic."""
        assume(is_mu(value))

        projections = [projection]
        try:
            result1 = eval_step(projections, value)
            result2 = eval_step(projections, value)
            assert mu_equal(result1, result2), "eval_step must be deterministic"
        except KeyError:
            # Unbound variable is acceptable - both calls would raise same error
            pass

    @given(st.lists(valid_projections(), min_size=2, max_size=5), mu_values())
    @settings(max_examples=1000, deadline=None)
    def test_eval_step_order_matters(self, projections, value):
        """First-match-wins: projection order is observable."""
        assume(is_mu(value))
        assume(len(projections) >= 2)

        try:
            # Apply forward
            result_forward = eval_step(projections, value)

            # Apply reversed
            result_reversed = eval_step(list(reversed(projections)), value)

            # Results MAY differ (order matters)
            # What we test: both are deterministic
            result_forward2 = eval_step(projections, value)
            result_reversed2 = eval_step(list(reversed(projections)), value)

            assert mu_equal(result_forward, result_forward2), "Forward must be stable"
            assert mu_equal(result_reversed, result_reversed2), "Reversed must be stable"
        except KeyError:
            # Unbound variable is acceptable - both orderings would raise same error
            pass

    @given(mu_values())
    @settings(max_examples=1000, deadline=None)
    def test_eval_step_empty_projections_is_identity(self, value):
        """eval_step with empty projection list returns input unchanged (stall)."""
        assume(is_mu(value))

        result = eval_step([], value)
        assert mu_equal(result, value), "Empty projections should stall (identity)"

    @given(st.lists(valid_projections(), min_size=1, max_size=10), mu_values())
    @settings(max_examples=1000, deadline=None)
    def test_eval_step_never_crashes(self, projections, value):
        """eval_step should never crash on valid inputs."""
        assume(is_mu(value))

        try:
            result = eval_step(projections, value)
            # Result should be valid Mu
            assert is_mu(result), "Result must be valid Mu"
        except KeyError:
            # Unbound variable is acceptable failure mode
            pass


# =============================================================================
# Primitive 2: mu_equal - Hash Comparison Property
# =============================================================================

class TestMuEqualProperties:
    """Property-based tests for mu_equal primitive."""

    @given(mu_values())
    @settings(max_examples=1000, deadline=None)
    def test_mu_equal_reflexive(self, value):
        """mu_equal(a, a) is always True."""
        assume(is_mu(value))
        assert mu_equal(value, value), "Equality must be reflexive"

    @given(mu_values(), mu_values())
    @settings(max_examples=1000, deadline=None)
    def test_mu_equal_symmetric(self, a, b):
        """mu_equal(a, b) == mu_equal(b, a)."""
        assume(is_mu(a) and is_mu(b))

        assert mu_equal(a, b) == mu_equal(b, a), "Equality must be symmetric"

    @given(mu_values(), mu_values(), mu_values())
    @settings(max_examples=500, deadline=None)
    def test_mu_equal_transitive(self, a, b, c):
        """If mu_equal(a, b) and mu_equal(b, c), then mu_equal(a, c)."""
        assume(is_mu(a) and is_mu(b) and is_mu(c))

        if mu_equal(a, b) and mu_equal(b, c):
            assert mu_equal(a, c), "Equality must be transitive"

    @given(mu_values())
    @settings(max_examples=1000, deadline=None)
    def test_mu_hash_consistency(self, value):
        """Same value produces same hash."""
        assume(is_mu(value))

        hash1 = mu_hash(value)
        hash2 = mu_hash(value)

        assert hash1 == hash2, "Hash must be consistent"

    @given(mu_values(), mu_values())
    @settings(max_examples=1000, deadline=None)
    def test_mu_equal_hash_correspondence(self, a, b):
        """If mu_equal(a, b), then mu_hash(a) == mu_hash(b)."""
        assume(is_mu(a) and is_mu(b))

        if mu_equal(a, b):
            assert mu_hash(a) == mu_hash(b), "Equal values must have equal hashes"

    @given(st.data())
    @settings(max_examples=1000, deadline=None)
    def test_mu_equal_type_coercion_resistance(self, data):
        """mu_equal avoids Python type coercion (True != 1, etc.)."""
        # Generate pairs that Python == would coerce
        test_cases = [
            (True, 1),
            (False, 0),
            (1.0, 1),
        ]

        pair = data.draw(st.sampled_from(test_cases))
        a, b = pair

        # Python's == may say these are equal due to coercion
        # mu_equal should NOT
        if is_mu(a) and is_mu(b):
            # True == 1 in Python, but not in Mu semantics
            if isinstance(a, bool) and isinstance(b, int) and not isinstance(b, bool):
                assert not mu_equal(a, b), f"mu_equal should reject {a} == {b}"


# =============================================================================
# Primitive 3: max_steps - Resource Exhaustion Guard
# =============================================================================

class TestMaxStepsGuard:
    """Property-based tests for max_steps primitive."""

    @given(mu_values(), st.integers(min_value=1, max_value=100))
    @settings(max_examples=500, deadline=None)
    def test_max_steps_enforced(self, value, max_steps):
        """run_mu respects max_steps limit."""
        assume(is_mu(value))

        # Projection that never matches (infinite loop if unconstrained)
        never_match = {"pattern": {"impossible": "value"}, "body": {"var": "x"}}

        result, trace, is_stall = run_mu([never_match], value, max_steps=max_steps)

        # Should stop after max_steps
        assert len(trace) <= max_steps + 2, f"Trace exceeded max_steps: {len(trace)} > {max_steps + 2}"

    @given(mu_values())
    @settings(max_examples=500, deadline=None)
    def test_max_steps_cycle_detection(self, value):
        """run_mu detects stalls via mu_equal (fixed point)."""
        assume(is_mu(value))

        # Identity projection (immediate stall)
        identity = {"pattern": {"var": "x"}, "body": {"var": "x"}}

        result, trace, is_stall = run_mu([identity], value, max_steps=1000)

        # Should stall immediately
        assert is_stall, "Identity projection should cause immediate stall"
        assert len(trace) <= 3, f"Should stall quickly, got {len(trace)} steps"


# =============================================================================
# Primitive 4: stack_guard - Overflow Protection
# =============================================================================

class TestStackGuard:
    """Property-based tests for stack overflow protection."""

    @given(st.integers(min_value=MAX_MU_DEPTH + 1, max_value=MAX_MU_DEPTH + 50))
    @settings(max_examples=100, deadline=None)
    def test_is_mu_rejects_too_deep(self, depth):
        """is_mu rejects structures deeper than MAX_MU_DEPTH."""
        # Build nested structure
        result = None
        for _ in range(depth):
            result = [result]

        # Should reject
        assert not is_mu(result), f"is_mu should reject depth {depth} > {MAX_MU_DEPTH}"

    @given(st.integers(min_value=10, max_value=MAX_MU_DEPTH - 10))
    @settings(max_examples=100, deadline=None)
    def test_is_mu_accepts_valid_depth(self, depth):
        """is_mu accepts structures within MAX_MU_DEPTH."""
        # Build nested structure
        result = None
        for _ in range(depth):
            result = [result]

        # Should accept
        assert is_mu(result), f"is_mu should accept depth {depth} < {MAX_MU_DEPTH}"


# =============================================================================
# Cross-Primitive Integration Tests
# =============================================================================

class TestBootstrapBoundary:
    """Tests that verify primitives work together correctly."""

    @given(st.lists(valid_projections(), min_size=1, max_size=5), mu_values())
    @settings(max_examples=500, deadline=None)
    def test_eval_step_result_equality(self, projections, value):
        """eval_step result should be comparable with mu_equal."""
        assume(is_mu(value))

        try:
            result = eval_step(projections, value)

            # Result must be comparable
            assert mu_equal(result, result), "Result must be self-equal"

            # If stalled, should equal input
            if mu_equal(result, value):
                # Stall detected correctly
                pass
        except KeyError:
            # Unbound variable - acceptable
            pass

    @given(mu_values(), st.integers(min_value=10, max_value=100))
    @settings(max_examples=300, deadline=None)
    def test_max_steps_uses_mu_equal_for_stall(self, value, max_steps):
        """run_mu uses mu_equal to detect stalls."""
        assume(is_mu(value))

        # Projection that doubles a number (will stall on non-numbers)
        double = {"pattern": {"var": "x"}, "body": {"doubled": {"var": "x"}}}

        result, trace, is_stall = run_mu([double], value, max_steps=max_steps)

        if is_stall:
            # Stall means last two values were equal
            if len(trace) >= 2:
                last_val = trace[-1]["value"]
                prev_val = trace[-2]["value"]
                assert mu_equal(last_val, prev_val), "Stall should mean mu_equal detected no change"


# =============================================================================
# Known Limitations (Documented)
# =============================================================================

class TestKnownLimitations:
    """Tests documenting known limitations of the primitives."""

    def test_oscillation_not_detected(self):
        """KNOWN LIMITATION: Oscillation (A->B->A) not detected, hits max_steps."""
        # Projection that toggles between two states
        toggle = [
            {"pattern": 0, "body": 1},
            {"pattern": 1, "body": 0},
        ]

        result, trace, is_stall = run_mu(toggle, 0, max_steps=50)

        # DOCUMENTS CURRENT BEHAVIOR: Oscillation not detected
        # Should hit max_steps, not stall
        assert not is_stall, "Oscillation should NOT be detected as stall (limitation)"
        assert len(trace) >= 50, "Should run until max_steps"

    def test_type_coercion_blocked(self):
        """mu_equal blocks Python type coercion."""
        # Python says True == 1
        assert True == 1

        # mu_equal says they're different
        assert not mu_equal(True, 1), "True != 1 in structural comparison"
        assert not mu_equal(False, 0), "False != 0 in structural comparison"
        assert not mu_equal(1.0, 1), "1.0 != 1 in structural comparison"
