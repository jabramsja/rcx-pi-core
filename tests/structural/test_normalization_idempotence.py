"""Phase 8b grounding: Verify normalization idempotence and roundtrip.

These tests were specified by the Grounding agent during L2 review.
They ground the claim that normalization is idempotent.
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from rcx_pi.selfhost.match_mu import normalize_for_match, denormalize_from_match
from rcx_pi.selfhost.mu_type import mu_equal, is_mu


# Mu value generators (consistent with test_selfhost_fuzzer.py)
mu_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**53), max_value=2**53),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=50),
)


@st.composite
def mu_values(draw, max_depth=3):
    """Recursive Mu generator with depth control."""
    if max_depth <= 0:
        return draw(mu_primitives)

    # Safe keys (no var, head, tail collisions)
    safe_keys = st.text(min_size=1, max_size=10).filter(
        lambda k: k not in ("var", "head", "tail", "_type", "_mode", "_phase")
    )

    return draw(st.one_of(
        mu_primitives,
        st.lists(st.deferred(lambda: mu_values(max_depth=max_depth-1)), max_size=4),
        st.dictionaries(safe_keys, st.deferred(lambda: mu_values(max_depth=max_depth-1)), max_size=4),
    ))


class TestNormalizationIdempotence:
    """Normalization must be idempotent: normalize(normalize(x)) == normalize(x)."""

    @given(mu_values(max_depth=3))
    @settings(deadline=5000)
    def test_normalize_idempotent(self, value):
        """normalize(normalize(x)) == normalize(x) for all Mu."""
        assume(is_mu(value))

        once = normalize_for_match(value)
        twice = normalize_for_match(once)

        assert mu_equal(once, twice), \
            f"Normalization not idempotent: {value} → {once} → {twice}"

    @given(mu_values(max_depth=3))
    @settings(deadline=5000)
    def test_denormalize_inverse(self, value):
        """denormalize(normalize(x)) produces equivalent result."""
        assume(is_mu(value))

        normalized = normalize_for_match(value)
        result = denormalize_from_match(normalized)

        # Result should be valid Mu
        assert is_mu(result), f"Denormalized result is not valid Mu: {result}"

        # For non-empty containers, should be equivalent
        if value not in (None, [], {}):
            assert mu_equal(result, value), \
                f"Round-trip failed: {value} → {normalized} → {result}"


class TestEmptyContainerPreservation:
    """Phase 8b fix: empty containers preserve type through normalization."""

    def test_empty_list_roundtrip(self):
        """[] → normalize → denormalize → []"""
        empty_list = []

        normalized = normalize_for_match(empty_list)
        assert normalized == {"_type": "list"}, \
            f"Empty list should normalize to typed sentinel, got {normalized}"

        result = denormalize_from_match(normalized)
        assert result == [], f"Expected [], got {result}"

    def test_empty_dict_roundtrip(self):
        """{} → normalize → denormalize → {}"""
        empty_dict = {}

        normalized = normalize_for_match(empty_dict)
        assert normalized == {"_type": "dict"}, \
            f"Empty dict should normalize to typed sentinel, got {normalized}"

        result = denormalize_from_match(normalized)
        assert result == {}, f"Expected {{}}, got {result}"

    def test_nested_empty_containers(self):
        """Nested empty containers preserve type."""
        nested = {"outer": [], "inner": {}}

        normalized = normalize_for_match(nested)
        result = denormalize_from_match(normalized)

        assert result == {"outer": [], "inner": {}}, \
            f"Nested empty containers failed roundtrip: {result}"

    def test_list_containing_empty_dict(self):
        """List containing empty dict preserves structure."""
        value = [1, {}, 3]

        normalized = normalize_for_match(value)
        result = denormalize_from_match(normalized)

        assert result == [1, {}, 3], f"Expected [1, {{}}, 3], got {result}"

    def test_dict_containing_empty_list(self):
        """Dict containing empty list preserves structure."""
        value = {"items": [], "count": 0}

        normalized = normalize_for_match(value)
        result = denormalize_from_match(normalized)

        assert result == {"items": [], "count": 0}, f"Got {result}"


class TestNormalizationDeterminism:
    """Normalization must be deterministic."""

    @given(mu_values(max_depth=3))
    @settings(deadline=5000)
    def test_normalize_deterministic(self, value):
        """Same input always produces same normalized output."""
        assume(is_mu(value))

        result1 = normalize_for_match(value)
        result2 = normalize_for_match(value)

        assert mu_equal(result1, result2), \
            f"Normalization not deterministic: {value} → {result1} vs {result2}"

    @given(mu_values(max_depth=3))
    @settings(deadline=5000)
    def test_denormalize_deterministic(self, value):
        """Same normalized input always produces same denormalized output."""
        assume(is_mu(value))

        normalized = normalize_for_match(value)

        result1 = denormalize_from_match(normalized)
        result2 = denormalize_from_match(normalized)

        assert mu_equal(result1, result2), \
            f"Denormalization not deterministic: {normalized} → {result1} vs {result2}"
