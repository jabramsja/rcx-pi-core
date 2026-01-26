"""
Normalization Roundtrip Tests

These tests verify that normalize_for_match and denormalize_from_match
are proper inverses (with documented exceptions).

Critical property: denormalize(normalize(x)) == x for most Mu values.

Known exceptions:
- Empty lists [] normalize to None
- Empty dicts {} normalize to None
- Existing head/tail structures denormalize to lists

These tests were added to address grounding gaps identified by the
grounding agent.
"""

import pytest
from rcx_pi.match_mu import (
    normalize_for_match,
    denormalize_from_match,
    is_dict_linked_list,
    is_kv_pair_linked,
)
from rcx_pi.mu_type import is_mu, mu_equal


class TestNormalizationRoundtrip:
    """Tests for normalize -> denormalize roundtrip property."""

    # --- Primitives roundtrip correctly ---

    def test_none_roundtrips(self):
        """None roundtrips correctly."""
        assert denormalize_from_match(normalize_for_match(None)) is None

    def test_bool_roundtrips(self):
        """Booleans roundtrip correctly."""
        assert denormalize_from_match(normalize_for_match(True)) is True
        assert denormalize_from_match(normalize_for_match(False)) is False

    def test_int_roundtrips(self):
        """Integers roundtrip correctly."""
        for value in [0, 1, -1, 42, 10**10]:
            assert denormalize_from_match(normalize_for_match(value)) == value

    def test_float_roundtrips(self):
        """Floats roundtrip correctly."""
        for value in [0.0, 3.14, -2.5, 1e10]:
            assert denormalize_from_match(normalize_for_match(value)) == value

    def test_string_roundtrips(self):
        """Strings roundtrip correctly."""
        for value in ["", "hello", "unicode: \u4e16\u754c", "with\nnewline"]:
            assert denormalize_from_match(normalize_for_match(value)) == value

    # --- Non-empty collections roundtrip correctly ---

    def test_nonempty_list_roundtrips(self):
        """Non-empty lists roundtrip correctly."""
        values = [
            [1],
            [1, 2, 3],
            ["a", "b", "c"],
            [1, "mixed", True, None],
        ]
        for value in values:
            result = denormalize_from_match(normalize_for_match(value))
            assert result == value, f"List roundtrip failed: {value} -> {result}"

    def test_nonempty_dict_roundtrips(self):
        """Non-empty dicts roundtrip correctly."""
        values = [
            {"a": 1},
            {"a": 1, "b": 2},
            {"key": "value", "count": 42},
        ]
        for value in values:
            result = denormalize_from_match(normalize_for_match(value))
            assert result == value, f"Dict roundtrip failed: {value} -> {result}"

    def test_nested_list_roundtrips(self):
        """Nested lists roundtrip correctly."""
        values = [
            [[1, 2], [3, 4]],
            [1, [2, [3, [4]]]],
            [[], [1], [1, 2]],  # Note: inner [] becomes None
        ]
        for value in values:
            result = denormalize_from_match(normalize_for_match(value))
            # Inner empty lists become None
            expected = _replace_empty_with_none(value)
            assert result == expected, f"Nested list roundtrip: {value} -> {result}"

    def test_nested_dict_roundtrips(self):
        """Nested dicts roundtrip correctly."""
        values = [
            {"a": {"b": 1}},
            {"outer": {"inner": {"deep": "value"}}},
            {"x": {"y": 1}, "z": {"w": 2}},
        ]
        for value in values:
            result = denormalize_from_match(normalize_for_match(value))
            assert result == value, f"Nested dict roundtrip: {value} -> {result}"

    def test_mixed_nesting_roundtrips(self):
        """Mixed list/dict nesting roundtrips correctly."""
        values = [
            {"items": [1, 2, 3]},
            [{"a": 1}, {"b": 2}],
            {"data": [{"nested": "value"}]},
        ]
        for value in values:
            result = denormalize_from_match(normalize_for_match(value))
            assert result == value, f"Mixed nesting roundtrip: {value} -> {result}"

    # --- Known exceptions (empty collections) ---

    def test_empty_list_normalizes_to_none(self):
        """Empty list [] normalizes to None (known limitation)."""
        assert normalize_for_match([]) is None
        # Denormalizing None gives None, not []
        assert denormalize_from_match(None) is None

    def test_empty_dict_normalizes_to_none(self):
        """Empty dict {} normalizes to None (known limitation)."""
        assert normalize_for_match({}) is None
        # Denormalizing None gives None, not {}
        assert denormalize_from_match(None) is None

    # --- Variable sites preserved ---

    def test_var_site_preserved(self):
        """Variable sites {"var": "x"} are preserved, not normalized."""
        var = {"var": "x"}
        assert normalize_for_match(var) == var
        assert denormalize_from_match(var) == var

    def test_var_site_in_pattern_preserved(self):
        """Variable sites in nested structures are preserved."""
        pattern = {"a": {"var": "x"}, "b": {"var": "y"}}
        normalized = normalize_for_match(pattern)
        denormalized = denormalize_from_match(normalized)
        assert denormalized == pattern

    def test_var_site_in_list_preserved(self):
        """Variable sites in lists are preserved."""
        pattern = [{"var": "a"}, {"var": "b"}]
        normalized = normalize_for_match(pattern)
        denormalized = denormalize_from_match(normalized)
        assert denormalized == pattern


class TestNormalizationFormat:
    """Tests for normalization output format."""

    def test_list_becomes_linked_list(self):
        """Lists become head/tail linked lists."""
        normalized = normalize_for_match([1, 2, 3])
        assert isinstance(normalized, dict)
        assert set(normalized.keys()) == {"head", "tail"}
        assert normalized["head"] == 1

    def test_dict_becomes_kv_linked_list(self):
        """Dicts become linked lists of key-value pairs."""
        normalized = normalize_for_match({"a": 1})
        assert isinstance(normalized, dict)
        assert set(normalized.keys()) == {"head", "tail"}
        # Each element is a kv-pair
        assert is_kv_pair_linked(normalized["head"])

    def test_dict_keys_sorted(self):
        """Dict keys are processed in sorted order (determinism)."""
        d1 = {"z": 1, "a": 2, "m": 3}
        d2 = {"a": 2, "m": 3, "z": 1}

        n1 = normalize_for_match(d1)
        n2 = normalize_for_match(d2)

        # Same normalized form
        assert mu_equal(n1, n2)


class TestDenormalizationDetection:
    """Tests for is_dict_linked_list detection."""

    def test_detects_dict_encoding(self):
        """Correctly detects dict-encoded linked lists."""
        # Manually build dict encoding: {"a": 1, "b": 2}
        kv_a = {"head": "a", "tail": {"head": 1, "tail": None}}
        kv_b = {"head": "b", "tail": {"head": 2, "tail": None}}
        linked = {"head": kv_a, "tail": {"head": kv_b, "tail": None}}

        assert is_dict_linked_list(linked) is True

    def test_detects_non_dict_encoding(self):
        """Correctly detects non-dict linked lists."""
        # Regular list encoding: [1, 2]
        linked = {"head": 1, "tail": {"head": 2, "tail": None}}

        assert is_dict_linked_list(linked) is False

    def test_mixed_list_not_dict_encoding(self):
        """List containing kv-pairs followed by non-kv is not dict encoding."""
        kv = {"head": "a", "tail": {"head": 1, "tail": None}}
        non_kv = 42
        linked = {"head": kv, "tail": {"head": non_kv, "tail": None}}

        # First element looks like kv, but second doesn't
        assert is_dict_linked_list(linked) is False


class TestNormalizationOutputValidity:
    """Tests that normalized output is valid Mu."""

    def test_normalized_primitives_are_mu(self):
        """Normalized primitives are valid Mu."""
        for value in [None, True, False, 42, 3.14, "hello"]:
            normalized = normalize_for_match(value)
            assert is_mu(normalized), f"Normalized {value} is not Mu"

    def test_normalized_lists_are_mu(self):
        """Normalized lists are valid Mu."""
        for value in [[1, 2, 3], ["a", "b"], [1, [2, 3]]]:
            normalized = normalize_for_match(value)
            assert is_mu(normalized), f"Normalized {value} is not Mu"

    def test_normalized_dicts_are_mu(self):
        """Normalized dicts are valid Mu."""
        for value in [{"a": 1}, {"x": {"y": 2}}, {"list": [1, 2]}]:
            normalized = normalize_for_match(value)
            assert is_mu(normalized), f"Normalized {value} is not Mu"


class TestDenormalizationOutputValidity:
    """Tests that denormalized output is valid Mu."""

    def test_denormalized_is_mu(self):
        """Denormalized values are valid Mu."""
        values = [
            None,
            True,
            42,
            "hello",
            [1, 2, 3],
            {"a": 1, "b": 2},
            {"nested": [1, {"deep": "value"}]},
        ]
        for value in values:
            normalized = normalize_for_match(value)
            denormalized = denormalize_from_match(normalized)
            assert is_mu(denormalized), f"Denormalized {value} is not Mu"


# --- Helper functions ---

def _replace_empty_with_none(value):
    """Replace empty lists/dicts with None (to match normalization behavior)."""
    if value == [] or value == {}:
        return None
    if isinstance(value, list):
        return [_replace_empty_with_none(x) for x in value]
    if isinstance(value, dict):
        return {k: _replace_empty_with_none(v) for k, v in value.items()}
    return value
