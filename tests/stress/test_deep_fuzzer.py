"""
Deep Fuzzer Stress Tests - Comprehensive Edge Case Coverage

These tests probe deep nesting and wide structures that are too slow
for regular CI but important for thorough validation.

Run separately:
    pytest tests/stress/ -v --timeout=300

These tests are EXCLUDED from:
- audit_fast.sh (fast iteration)
- pre-commit hooks

They ARE included in:
- audit_all.sh (full validation)
- CI deep test job (if configured)

See docs/TESTING_PERFORMANCE_ISSUE.md for context.
"""

import pytest
import time

# Skip if hypothesis not installed
hypothesis = pytest.importorskip("hypothesis", reason="hypothesis required")

from hypothesis import given, strategies as st, settings, assume, HealthCheck
from hypothesis.strategies import composite

from rcx_pi.selfhost.mu_type import (
    is_mu,
    mu_equal,
    mu_hash,
    MAX_MU_DEPTH,
)
from rcx_pi.selfhost.step_mu import run_mu
from rcx_pi.selfhost.match_mu import normalize_for_match, denormalize_from_match


# =============================================================================
# Deep Value Generators
# =============================================================================

mu_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**31), max_value=2**31),
    st.text(max_size=20),
)


@composite
def deep_mu_values(draw, max_depth=5):
    """Generate deeper Mu values for stress testing.

    Unlike the regular mu_values(max_depth=3), this generates structures
    up to depth 5, which after normalization can reach depth 10+.
    """
    if max_depth <= 0:
        return draw(mu_primitives)

    return draw(st.one_of(
        mu_primitives,
        st.lists(
            st.deferred(lambda: deep_mu_values(max_depth=max_depth-1)),
            max_size=3
        ),
        st.dictionaries(
            st.text(min_size=1, max_size=5),
            st.deferred(lambda: deep_mu_values(max_depth=max_depth-1)),
            max_size=3
        ),
    ))


def build_nested_list(depth: int, leaf=42):
    """Build a list nested to specified depth."""
    result = leaf
    for _ in range(depth):
        result = [result]
    return result


def build_nested_dict(depth: int, leaf=42):
    """Build a dict nested to specified depth."""
    result = leaf
    for _ in range(depth):
        result = {"nested": result}
    return result


# =============================================================================
# Stress Tests: Normalization Roundtrip
# =============================================================================

class TestNormalizationDeepStress:
    """Stress tests for normalization with deep structures."""

    @given(deep_mu_values(max_depth=5))
    @settings(
        max_examples=50,
        deadline=30000,  # 30 seconds per example
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_deep_normalization_roundtrip(self, value):
        """Normalization roundtrip works for deep structures."""
        assume(is_mu(value))

        normalized = normalize_for_match(value)
        assert is_mu(normalized), "Normalized value must be valid Mu"

        denormalized = denormalize_from_match(normalized)
        assert mu_equal(value, denormalized), "Roundtrip must preserve value"

    @given(st.integers(min_value=50, max_value=MAX_MU_DEPTH - 20))
    @settings(
        max_examples=20,
        deadline=60000,  # 60 seconds per example
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_near_max_depth_list(self, depth):
        """Normalization handles lists near MAX_MU_DEPTH."""
        value = build_nested_list(depth)

        normalized = normalize_for_match(value)
        denormalized = denormalize_from_match(normalized)

        assert mu_equal(value, denormalized), f"Roundtrip failed at depth {depth}"

    @given(st.integers(min_value=30, max_value=80))
    @settings(
        max_examples=20,
        deadline=60000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_near_max_depth_dict(self, depth):
        """Normalization handles dicts near MAX_MU_DEPTH.

        Note: Dicts roughly double depth after normalization (linked list of pairs).
        So depth=80 becomes ~160 after normalization.
        """
        value = build_nested_dict(depth)

        normalized = normalize_for_match(value)
        denormalized = denormalize_from_match(normalized)

        assert mu_equal(value, denormalized), f"Roundtrip failed at depth {depth}"


# =============================================================================
# Stress Tests: run_mu with Pathological Projections
# =============================================================================

class TestRunMuDeepStress:
    """Stress tests for run_mu with deep nesting projections."""

    @given(st.integers(min_value=30, max_value=80))
    @settings(
        max_examples=20,
        deadline=60000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_double_projection_deep(self, max_steps):
        """The "double" projection that wraps deeper each step.

        This is the pathological case that caused fuzzer hangs.
        We test it here with higher limits to ensure it completes.
        """
        double = {"pattern": {"var": "x"}, "body": {"doubled": {"var": "x"}}}

        start = time.time()
        result, trace, is_stall = run_mu([double], 100, max_steps=max_steps)
        elapsed = time.time() - start

        # Should complete (not stall - keeps wrapping)
        assert not is_stall, "Double projection should not stall"
        assert len(trace) == max_steps + 1, f"Should run exactly {max_steps} steps"

        # Result should be deeply nested
        assert is_mu(result), "Result must be valid Mu"

    @given(st.integers(min_value=100, max_value=500))
    @settings(
        max_examples=10,
        deadline=120000,  # 2 minutes
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_oscillation_max_steps(self, max_steps):
        """Oscillation (A->B->A) hits max_steps correctly.

        Known limitation: oscillation is not detected as stall.
        This test verifies it completes via max_steps.
        """
        toggle = [
            {"pattern": 0, "body": 1},
            {"pattern": 1, "body": 0},
        ]

        result, trace, is_stall = run_mu(toggle, 0, max_steps=max_steps)

        # Should NOT stall (oscillates forever)
        assert not is_stall, "Oscillation should not be detected as stall"
        assert len(trace) == max_steps + 1


# =============================================================================
# Stress Tests: mu_equal Performance
# =============================================================================

class TestMuEqualDeepStress:
    """Stress tests for mu_equal on deep structures."""

    @given(st.integers(min_value=50, max_value=150))
    @settings(
        max_examples=30,
        deadline=30000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_mu_equal_deep_identical(self, depth):
        """mu_equal handles deep identical structures."""
        value = build_nested_list(depth)

        assert mu_equal(value, value), "Value should equal itself"

    @given(st.integers(min_value=50, max_value=150))
    @settings(
        max_examples=30,
        deadline=30000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_mu_equal_deep_different(self, depth):
        """mu_equal correctly distinguishes deep structures."""
        value1 = build_nested_list(depth, leaf=1)
        value2 = build_nested_list(depth, leaf=2)

        assert not mu_equal(value1, value2), "Different leaves should not be equal"

    @given(st.integers(min_value=50, max_value=150))
    @settings(
        max_examples=30,
        deadline=30000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_mu_hash_deep_consistent(self, depth):
        """mu_hash is consistent for deep structures."""
        value = build_nested_list(depth)

        hash1 = mu_hash(value)
        hash2 = mu_hash(value)

        assert hash1 == hash2, "Hash must be deterministic"


# =============================================================================
# Stress Tests: Wide Structures
# =============================================================================

class TestWideStructureStress:
    """Stress tests for wide (many keys/elements) structures."""

    @given(st.integers(min_value=100, max_value=500))
    @settings(
        max_examples=20,
        deadline=60000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_wide_list_normalization(self, width):
        """Normalization handles wide lists."""
        value = list(range(width))

        normalized = normalize_for_match(value)
        denormalized = denormalize_from_match(normalized)

        assert mu_equal(value, denormalized), f"Roundtrip failed at width {width}"

    @given(st.integers(min_value=50, max_value=200))
    @settings(
        max_examples=20,
        deadline=60000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_wide_dict_normalization(self, width):
        """Normalization handles wide dicts."""
        value = {f"key_{i}": i for i in range(width)}

        normalized = normalize_for_match(value)
        denormalized = denormalize_from_match(normalized)

        assert mu_equal(value, denormalized), f"Roundtrip failed at width {width}"
