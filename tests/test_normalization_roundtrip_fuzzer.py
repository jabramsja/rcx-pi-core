"""
Property-Based Normalization Roundtrip Fuzzer

Uses Hypothesis to generate 1000+ random Mu values and verify:
1. denormalize(normalize(x)) == x for all valid Mu
2. normalize(normalize(x)) == normalize(x) (idempotency)
3. type(denormalize(normalize(x))) == type(x) (type preservation)

9-agent review (Fuzzer finding): Manual roundtrip tests existed but
property-based testing was missing. This catches edge cases that
manual tests miss.
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from rcx_pi.selfhost.match_mu import (
    normalize_for_match,
    denormalize_from_match,
)
from rcx_pi.selfhost.mu_type import is_mu, mu_equal


# =============================================================================
# Mu Value Generators (Hypothesis Strategies)
# =============================================================================

@st.composite
def mu_primitives(draw):
    """Generate primitive Mu values."""
    return draw(st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-10**9, max_value=10**9),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(max_size=50),
    ))


@st.composite
def mu_values(draw, max_depth=3):
    """Generate arbitrary Mu values with controlled depth."""
    if max_depth <= 0:
        return draw(mu_primitives())

    # Use recursive strategy for depth control
    inner = st.deferred(lambda: mu_values_strategy(max_depth - 1))

    return draw(st.one_of(
        mu_primitives(),
        st.lists(inner, max_size=5),
        st.dictionaries(
            st.text(min_size=1, max_size=10).filter(lambda s: s not in ["var"]),
            inner,
            max_size=5
        ),
    ))


def mu_values_strategy(max_depth=3):
    """Return a strategy for Mu values at given depth."""
    if max_depth <= 0:
        return mu_primitives()

    inner = st.deferred(lambda: mu_values_strategy(max_depth - 1))

    return st.one_of(
        mu_primitives(),
        st.lists(inner, max_size=5),
        st.dictionaries(
            st.text(min_size=1, max_size=10).filter(lambda s: s not in ["var"]),
            inner,
            max_size=5
        ),
    )


@st.composite
def mu_values_with_empties(draw, max_depth=3):
    """Generate Mu values with emphasis on empty containers (edge cases)."""
    return draw(mu_values_with_empties_strategy(max_depth))


def mu_values_with_empties_strategy(max_depth=3):
    """Return a strategy for Mu values with empties at given depth."""
    if max_depth <= 0:
        return st.one_of(
            mu_primitives(),
            st.just([]),  # Empty list
            st.just({}),  # Empty dict
        )

    inner = st.deferred(lambda: mu_values_with_empties_strategy(max_depth - 1))

    return st.one_of(
        mu_primitives(),
        st.just([]),
        st.just({}),
        st.lists(inner, max_size=5),
        st.dictionaries(
            st.text(min_size=1, max_size=10).filter(lambda s: s not in ["var"]),
            inner,
            max_size=5
        ),
    )


# =============================================================================
# Core Roundtrip Property Tests
# =============================================================================

class TestNormalizationRoundtripFuzzer:
    """Property-based tests for normalize/denormalize roundtrip."""

    @given(mu_values(max_depth=3))
    @settings(max_examples=500, deadline=5000)
    def test_roundtrip_property(self, value):
        """Property: denormalize(normalize(x)) == x for all valid Mu."""
        assume(is_mu(value))

        normalized = normalize_for_match(value)
        denormalized = denormalize_from_match(normalized)

        assert denormalized == value, (
            f"Roundtrip failed:\n"
            f"  Original: {value}\n"
            f"  Normalized: {normalized}\n"
            f"  Denormalized: {denormalized}"
        )

    @given(mu_values_with_empties(max_depth=3))
    @settings(max_examples=500, deadline=5000)
    def test_roundtrip_with_empties(self, value):
        """Property: roundtrip works for values with empty containers."""
        assume(is_mu(value))

        normalized = normalize_for_match(value)
        denormalized = denormalize_from_match(normalized)

        assert denormalized == value, (
            f"Roundtrip with empties failed:\n"
            f"  Original: {value}\n"
            f"  Denormalized: {denormalized}"
        )


class TestNormalizationIdempotencyFuzzer:
    """Property-based tests for normalization idempotency."""

    @given(mu_values(max_depth=3))
    @settings(max_examples=500, deadline=5000)
    def test_idempotency_property(self, value):
        """Property: normalize(normalize(x)) == normalize(x)."""
        assume(is_mu(value))

        once = normalize_for_match(value)
        twice = normalize_for_match(once)

        assert mu_equal(once, twice), (
            f"Not idempotent:\n"
            f"  Once: {once}\n"
            f"  Twice: {twice}"
        )

    @given(mu_values_with_empties(max_depth=3))
    @settings(max_examples=500, deadline=5000)
    def test_idempotency_with_empties(self, value):
        """Property: idempotency holds for values with empty containers."""
        assume(is_mu(value))

        once = normalize_for_match(value)
        twice = normalize_for_match(once)

        assert mu_equal(once, twice), (
            f"Not idempotent (with empties):\n"
            f"  Once: {once}\n"
            f"  Twice: {twice}"
        )


class TestTypePreservationFuzzer:
    """Property-based tests for type preservation through roundtrip."""

    @given(st.lists(mu_values(max_depth=2), max_size=5))
    @settings(max_examples=300, deadline=5000)
    def test_list_type_preserved(self, value):
        """Property: lists remain lists after roundtrip."""
        assume(is_mu(value))

        result = denormalize_from_match(normalize_for_match(value))

        assert isinstance(result, list), (
            f"List became {type(result).__name__}: {value} -> {result}"
        )
        assert result == value

    @given(st.dictionaries(
        st.text(min_size=1, max_size=10).filter(lambda s: s not in ["var"]),
        mu_values(max_depth=2),
        max_size=5
    ))
    @settings(max_examples=300, deadline=5000)
    def test_dict_type_preserved(self, value):
        """Property: dicts remain dicts after roundtrip."""
        assume(is_mu(value))

        result = denormalize_from_match(normalize_for_match(value))

        assert isinstance(result, dict), (
            f"Dict became {type(result).__name__}: {value} -> {result}"
        )
        assert result == value


class TestNormalizedOutputValidityFuzzer:
    """Property-based tests that normalized output is valid Mu."""

    @given(mu_values(max_depth=3))
    @settings(max_examples=500, deadline=5000)
    def test_normalized_is_mu(self, value):
        """Property: normalize produces valid Mu."""
        assume(is_mu(value))

        normalized = normalize_for_match(value)

        assert is_mu(normalized), (
            f"Normalized is not Mu: {value} -> {normalized}"
        )

    @given(mu_values(max_depth=3))
    @settings(max_examples=500, deadline=5000)
    def test_denormalized_is_mu(self, value):
        """Property: denormalize produces valid Mu."""
        assume(is_mu(value))

        normalized = normalize_for_match(value)
        denormalized = denormalize_from_match(normalized)

        assert is_mu(denormalized), (
            f"Denormalized is not Mu: {value} -> {denormalized}"
        )


class TestEdgeCaseFuzzer:
    """Property-based tests for edge cases."""

    @given(st.lists(st.just([]), min_size=1, max_size=5))
    @settings(max_examples=100, deadline=5000)
    def test_nested_empty_lists(self, value):
        """Property: nested empty lists roundtrip correctly."""
        result = denormalize_from_match(normalize_for_match(value))
        assert result == value
        for item in result:
            assert isinstance(item, list)
            assert item == []

    @given(st.lists(st.just({}), min_size=1, max_size=5))
    @settings(max_examples=100, deadline=5000)
    def test_nested_empty_dicts(self, value):
        """Property: nested empty dicts roundtrip correctly."""
        result = denormalize_from_match(normalize_for_match(value))
        assert result == value
        for item in result:
            assert isinstance(item, dict)
            assert item == {}

    @given(st.dictionaries(
        st.text(min_size=1, max_size=10),
        st.just([]),
        min_size=1,
        max_size=5
    ))
    @settings(max_examples=100, deadline=5000)
    def test_dict_with_empty_list_values(self, value):
        """Property: dicts with empty list values roundtrip correctly."""
        result = denormalize_from_match(normalize_for_match(value))
        assert result == value
        for v in result.values():
            assert isinstance(v, list)
            assert v == []

    @given(st.dictionaries(
        st.text(min_size=1, max_size=10),
        st.just({}),
        min_size=1,
        max_size=5
    ))
    @settings(max_examples=100, deadline=5000)
    def test_dict_with_empty_dict_values(self, value):
        """Property: dicts with empty dict values roundtrip correctly."""
        result = denormalize_from_match(normalize_for_match(value))
        assert result == value
        for v in result.values():
            assert isinstance(v, dict)
            assert v == {}
