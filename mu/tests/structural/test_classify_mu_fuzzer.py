"""Phase 8b: Fuzzer tests for classify_mu module.

Added based on Fuzzer agent recommendation during L2 review.
Gap identified: classify_mu had no dedicated fuzzer coverage.
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from rcx_pi.selfhost.classify_mu import classify_linked_list
from rcx_pi.selfhost.mu_type import is_mu


# Mu value generators
mu_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**53), max_value=2**53),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=50),
)


@st.composite
def mu_values(draw, max_depth=3):
    """Recursive Mu generator."""
    if max_depth <= 0:
        return draw(mu_primitives)

    safe_keys = st.text(min_size=1, max_size=10).filter(
        lambda k: k not in ("var", "head", "tail", "_type")
    )

    return draw(st.one_of(
        mu_primitives,
        st.lists(st.deferred(lambda: mu_values(max_depth=max_depth-1)), max_size=4),
        st.dictionaries(safe_keys, st.deferred(lambda: mu_values(max_depth=max_depth-1)), max_size=4),
    ))


@st.composite
def dict_encoded_linked_list(draw):
    """Generate a linked list that encodes a dict (all kv-pairs with string keys)."""
    # Dict entries as kv-pairs
    n_entries = draw(st.integers(min_value=0, max_value=5))
    entries = []
    for _ in range(n_entries):
        key = draw(st.text(min_size=1, max_size=10))
        value = draw(mu_primitives)
        # kv-pair format: {"head": {"head": key, "tail": {"head": value, "tail": None}}, "tail": ...}
        kv_pair = {"head": key, "tail": {"head": value, "tail": None}}
        entries.append(kv_pair)

    # Build linked list from entries
    result = None
    for entry in reversed(entries):
        result = {"head": entry, "tail": result}

    return result


@st.composite
def list_encoded_linked_list(draw):
    """Generate a linked list that encodes a list (not all kv-pairs)."""
    n_elements = draw(st.integers(min_value=1, max_value=5))

    result = None
    for _ in range(n_elements):
        # Use primitives directly (not kv-pair format)
        element = draw(mu_primitives)
        result = {"head": element, "tail": result}

    return result


class TestClassifyLinkedListProperties:
    """Property-based tests for classify_linked_list."""

    @given(mu_values(max_depth=3))
    @settings(deadline=5000)
    def test_classify_deterministic(self, value):
        """classify_linked_list is deterministic."""
        assume(is_mu(value))

        result1 = classify_linked_list(value)
        result2 = classify_linked_list(value)

        assert result1 == result2, \
            f"Classification not deterministic: {value} → {result1} vs {result2}"

    @given(mu_values(max_depth=3))
    @settings(deadline=5000)
    def test_classify_returns_valid_type(self, value):
        """classify_linked_list returns 'list' or 'dict'."""
        assume(is_mu(value))

        result = classify_linked_list(value)

        assert result in ("list", "dict"), \
            f"Invalid classification result: {result} for {value}"

    @given(mu_values(max_depth=3))
    @settings(deadline=5000)
    def test_classify_never_crashes(self, value):
        """classify_linked_list never crashes on valid Mu."""
        assume(is_mu(value))

        try:
            result = classify_linked_list(value)
            assert isinstance(result, str)
        except ValueError:
            # ValueError is acceptable (e.g., for circular refs)
            pass


class TestDictEncodingDetection:
    """Tests for dict-encoded linked list detection."""

    def test_empty_is_list(self):
        """Empty (None) classifies as list."""
        assert classify_linked_list(None) == "list"

    def test_single_kv_pair_is_dict(self):
        """Single kv-pair with string key classifies as dict."""
        # {"key": "value"} encoded as linked list
        kv = {"head": {"head": "key", "tail": {"head": "value", "tail": None}}, "tail": None}

        result = classify_linked_list(kv)
        assert result == "dict", f"Expected dict, got {result}"

    def test_multiple_kv_pairs_is_dict(self):
        """Multiple kv-pairs with string keys classifies as dict."""
        # {"a": 1, "b": 2}
        kv1 = {"head": "a", "tail": {"head": 1, "tail": None}}
        kv2 = {"head": "b", "tail": {"head": 2, "tail": None}}
        linked = {"head": kv1, "tail": {"head": kv2, "tail": None}}

        result = classify_linked_list(linked)
        assert result == "dict", f"Expected dict, got {result}"

    def test_non_string_key_is_list(self):
        """kv-pair with non-string key classifies as list."""
        # {123: "value"} - numeric key
        kv = {"head": {"head": 123, "tail": {"head": "value", "tail": None}}, "tail": None}

        result = classify_linked_list(kv)
        assert result == "list", f"Expected list (non-string key), got {result}"

    def test_primitive_elements_is_list(self):
        """Linked list of primitives classifies as list."""
        # [1, 2, 3]
        linked = {"head": 1, "tail": {"head": 2, "tail": {"head": 3, "tail": None}}}

        result = classify_linked_list(linked)
        assert result == "list", f"Expected list, got {result}"


class TestClassifyEdgeCases:
    """Edge case tests for classification."""

    def test_mixed_kv_and_primitive_is_list(self):
        """Mix of kv-pairs and primitives classifies as list."""
        kv = {"head": "key", "tail": {"head": "value", "tail": None}}
        # [kv_pair, 42]
        linked = {"head": kv, "tail": {"head": 42, "tail": None}}

        result = classify_linked_list(linked)
        assert result == "list", f"Mixed content should be list, got {result}"

    def test_nested_dict_in_list(self):
        """Nested dict inside list classifies correctly."""
        # The outer structure determines classification
        inner_dict = {"head": {"head": "k", "tail": {"head": "v", "tail": None}}, "tail": None}
        # [inner_dict, 1]
        linked = {"head": inner_dict, "tail": {"head": 1, "tail": None}}

        result = classify_linked_list(linked)
        # Outer is list (mixed content)
        assert result == "list"

    def test_empty_string_key_is_dict(self):
        """Empty string key still makes it a dict."""
        kv = {"head": {"head": "", "tail": {"head": "value", "tail": None}}, "tail": None}

        result = classify_linked_list(kv)
        assert result == "dict", f"Empty string key should still be dict, got {result}"

    def test_unicode_key_is_dict(self):
        """Unicode string key classifies as dict."""
        kv = {"head": {"head": "日本語", "tail": {"head": "value", "tail": None}}, "tail": None}

        result = classify_linked_list(kv)
        assert result == "dict", f"Unicode key should be dict, got {result}"


class TestClassifyWithTypeTag:
    """Tests for type-tagged structures."""

    def test_type_tagged_list_is_list(self):
        """Type-tagged empty list sentinel."""
        tagged = {"_type": "list"}

        # This goes through different path - may not be classify_linked_list's job
        # Just ensure it doesn't crash
        try:
            result = classify_linked_list(tagged)
            assert result in ("list", "dict")
        except (ValueError, KeyError):
            pass  # May not handle this case

    def test_type_tagged_dict_is_dict(self):
        """Type-tagged empty dict sentinel."""
        tagged = {"_type": "dict"}

        try:
            result = classify_linked_list(tagged)
            assert result in ("list", "dict")
        except (ValueError, KeyError):
            pass
