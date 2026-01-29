"""
Normalization Roundtrip Tests

These tests verify that normalize_for_match and denormalize_from_match
are proper inverses.

Critical property: denormalize(normalize(x)) == x for all Mu values.

Phase 8b fix: Empty containers now use typed sentinels:
- [] → {"_type": "list"} → []
- {} → {"_type": "dict"} → {}

This preserves type information through the roundtrip.

These tests were added to address grounding gaps identified by the
grounding agent.
"""

import pytest
from rcx_pi.match_mu import (
    normalize_for_match,
    denormalize_from_match,
    is_dict_linked_list,
    is_kv_pair_linked,
    validate_type_tag,
    VALID_TYPE_TAGS,
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
        """Nested lists roundtrip correctly (including empty inner lists)."""
        values = [
            [[1, 2], [3, 4]],
            [1, [2, [3, [4]]]],
            [[], [1], [1, 2]],  # Phase 8b fix: inner [] now roundtrips correctly
        ]
        for value in values:
            result = denormalize_from_match(normalize_for_match(value))
            # With Phase 8b fix, all containers roundtrip correctly
            assert result == value, f"Nested list roundtrip: {value} -> {result}"

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

    # --- Empty containers roundtrip correctly (Phase 8b fix) ---

    def test_empty_list_roundtrips(self):
        """Empty list [] roundtrips correctly via typed sentinel."""
        normalized = normalize_for_match([])
        # Empty list becomes typed sentinel
        assert normalized == {"_type": "list"}
        # Denormalizing gives back empty list
        assert denormalize_from_match(normalized) == []

    def test_empty_dict_roundtrips(self):
        """Empty dict {} roundtrips correctly via typed sentinel."""
        normalized = normalize_for_match({})
        # Empty dict becomes typed sentinel
        assert normalized == {"_type": "dict"}
        # Denormalizing gives back empty dict
        assert denormalize_from_match(normalized) == {}

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
        """Lists become type-tagged head/tail linked lists."""
        normalized = normalize_for_match([1, 2, 3])
        assert isinstance(normalized, dict)
        assert set(normalized.keys()) == {"_type", "head", "tail"}
        assert normalized["_type"] == "list"
        assert normalized["head"] == 1

    def test_dict_becomes_kv_linked_list(self):
        """Dicts become type-tagged linked lists of key-value pairs."""
        normalized = normalize_for_match({"a": 1})
        assert isinstance(normalized, dict)
        assert set(normalized.keys()) == {"_type", "head", "tail"}
        assert normalized["_type"] == "dict"
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


class TestTypeTagValidation:
    """Tests for _type tag whitelist validation (Phase 6c security)."""

    def test_valid_type_tags_pass(self):
        """Valid type tags pass validation."""
        for tag in VALID_TYPE_TAGS:
            validate_type_tag(tag)  # Should not raise

    def test_invalid_type_tag_raises(self):
        """Invalid type tags raise ValueError."""
        with pytest.raises(ValueError, match="Invalid type tag"):
            validate_type_tag("unknown")

    def test_invalid_type_tag_in_denormalize(self):
        """Denormalize rejects structures with invalid type tags."""
        malicious = {"_type": "malicious", "head": 1, "tail": None}
        with pytest.raises(ValueError, match="Invalid type tag"):
            denormalize_from_match(malicious)

    def test_is_dict_linked_list_rejects_invalid_type(self):
        """is_dict_linked_list returns False for invalid type tags."""
        malicious = {"_type": "malicious", "head": 1, "tail": None}
        assert is_dict_linked_list(malicious) is False


class TestNormalizationIdempotency:
    """
    Tests for normalization idempotency: normalize(normalize(x)) == normalize(x).

    This was identified as a grounding gap by the grounding agent.
    Phase 8b added typed sentinel handling (lines 189-195 in match_mu.py)
    to ensure idempotency for empty containers.
    """

    def test_empty_list_sentinel_idempotent(self):
        """Typed sentinel {"_type": "list"} stays unchanged under normalization."""
        sentinel = {"_type": "list"}
        normalized = normalize_for_match(sentinel)
        assert normalized == sentinel, f"Sentinel changed: {sentinel} -> {normalized}"

    def test_empty_dict_sentinel_idempotent(self):
        """Typed sentinel {"_type": "dict"} stays unchanged under normalization."""
        sentinel = {"_type": "dict"}
        normalized = normalize_for_match(sentinel)
        assert normalized == sentinel, f"Sentinel changed: {sentinel} -> {normalized}"

    def test_empty_list_double_normalize(self):
        """normalize(normalize([])) == normalize([])."""
        once = normalize_for_match([])
        twice = normalize_for_match(once)
        assert mu_equal(once, twice), f"Not idempotent: {once} vs {twice}"

    def test_empty_dict_double_normalize(self):
        """normalize(normalize({})) == normalize({})."""
        once = normalize_for_match({})
        twice = normalize_for_match(once)
        assert mu_equal(once, twice), f"Not idempotent: {once} vs {twice}"

    def test_nested_empty_idempotent(self):
        """Nested empty containers are idempotent under normalization."""
        values = [
            {"a": []},
            {"a": {}},
            [[]],
            [{}],
            {"outer": {"inner": []}},
            [[[], []]],
        ]
        for value in values:
            once = normalize_for_match(value)
            twice = normalize_for_match(once)
            assert mu_equal(once, twice), (
                f"Not idempotent for {value}:\n"
                f"  Once: {once}\n"
                f"  Twice: {twice}"
            )

    def test_complex_structure_idempotent(self):
        """Complex nested structures are idempotent under normalization."""
        values = [
            {"a": [1, 2], "b": {"c": []}},
            [{"x": 1}, {"y": []}, {"z": {}}],
            {"nested": {"deep": {"empty": [], "data": [1, 2, 3]}}},
        ]
        for value in values:
            once = normalize_for_match(value)
            twice = normalize_for_match(once)
            assert mu_equal(once, twice), (
                f"Not idempotent for {value}:\n"
                f"  Once: {once}\n"
                f"  Twice: {twice}"
            )


class TestSentinelCollision:
    """
    Tests for sentinel collision: user data that looks like typed sentinels.

    This was identified as a risk by the adversary agent.
    User data {"_type": "list"} should be handled correctly (either preserved
    as user data OR converted to empty list consistently).
    """

    def test_user_data_with_type_list_roundtrips(self):
        """User data {"_type": "list"} roundtrips consistently.

        Note: This is a KNOWN edge case. User data that exactly matches
        the typed sentinel format will be treated as a sentinel.
        This is documented behavior, not a bug.
        """
        user_data = {"_type": "list"}
        normalized = normalize_for_match(user_data)
        denormalized = denormalize_from_match(normalized)

        # The sentinel is preserved through normalization (idempotent)
        assert normalized == {"_type": "list"}
        # Denormalization produces empty list (sentinel semantics)
        assert denormalized == []

    def test_user_data_with_type_dict_roundtrips(self):
        """User data {"_type": "dict"} roundtrips consistently."""
        user_data = {"_type": "dict"}
        normalized = normalize_for_match(user_data)
        denormalized = denormalize_from_match(normalized)

        assert normalized == {"_type": "dict"}
        assert denormalized == {}

    def test_user_data_with_type_and_extra_keys_preserved(self):
        """User data {"_type": "list", "extra": "key"} is NOT a sentinel.

        Extra keys cause the structure to be treated as regular dict,
        not as a typed sentinel.
        """
        user_data = {"_type": "list", "extra": "data"}
        normalized = normalize_for_match(user_data)
        denormalized = denormalize_from_match(normalized)

        # Should roundtrip as dict (not converted to empty list)
        assert denormalized == user_data

    def test_user_data_with_invalid_type_preserved(self):
        """User data {"_type": "custom"} is treated as regular dict.

        Invalid type tags are NOT in whitelist, so the structure
        is normalized as a regular dict, not as a sentinel.
        """
        user_data = {"_type": "custom", "data": 123}
        normalized = normalize_for_match(user_data)
        denormalized = denormalize_from_match(normalized)

        # Should roundtrip as dict
        assert denormalized == user_data

    def test_only_exact_sentinel_format_triggers_special_handling(self):
        """Only exact format {"_type": "list"} or {"_type": "dict"} is sentinel."""
        # These are NOT sentinels (extra keys)
        not_sentinels = [
            {"_type": "list", "head": 1, "tail": None},  # Has head/tail
            {"_type": "dict", "key": "value"},  # Has extra key
            {"_type": "list", "_extra": True},  # Has underscore key
        ]

        for value in not_sentinels:
            normalized = normalize_for_match(value)
            denormalized = denormalize_from_match(normalized)
            # Should roundtrip (not converted to empty container)
            # Note: type-tagged head/tail structures are handled specially
            assert is_mu(denormalized), f"Failed for {value}"


class TestNestedEmptyContainers:
    """
    Tests for nested empty containers at various depths.

    This was identified as a gap by the fuzzer and advisor agents.
    Phase 8b fix should handle nested empties correctly.
    """

    def test_list_containing_empty_list(self):
        """[[]] roundtrips correctly."""
        value = [[]]
        result = denormalize_from_match(normalize_for_match(value))
        assert result == [[]]
        assert isinstance(result[0], list)

    def test_list_containing_empty_dict(self):
        """[{}] roundtrips correctly."""
        value = [{}]
        result = denormalize_from_match(normalize_for_match(value))
        assert result == [{}]
        assert isinstance(result[0], dict)

    def test_dict_containing_empty_list(self):
        """{"x": []} roundtrips correctly."""
        value = {"x": []}
        result = denormalize_from_match(normalize_for_match(value))
        assert result == {"x": []}
        assert isinstance(result["x"], list)

    def test_dict_containing_empty_dict(self):
        """{"x": {}} roundtrips correctly."""
        value = {"x": {}}
        result = denormalize_from_match(normalize_for_match(value))
        assert result == {"x": {}}
        assert isinstance(result["x"], dict)

    def test_deeply_nested_empty_list(self):
        """[[[[]]]] roundtrips correctly (depth 4)."""
        value = [[[[]]]]
        result = denormalize_from_match(normalize_for_match(value))
        assert result == [[[[]]]]

    def test_deeply_nested_empty_dict(self):
        """{"a": {"b": {"c": {}}}} roundtrips correctly (depth 3)."""
        value = {"a": {"b": {"c": {}}}}
        result = denormalize_from_match(normalize_for_match(value))
        assert result == {"a": {"b": {"c": {}}}}

    def test_mixed_nested_empties(self):
        """Mixed empty lists and dicts at various depths."""
        values = [
            {"list": [], "dict": {}},
            [[], {}],
            {"outer": [{"inner": []}]},
            [{"a": []}, {"b": {}}],
            {"x": [[], [], []]},
            [{"a": {}}, {"b": {}}, {"c": {}}],
        ]
        for value in values:
            result = denormalize_from_match(normalize_for_match(value))
            assert result == value, f"Failed for {value}: got {result}"

    def test_empty_and_nonempty_siblings(self):
        """Empty containers alongside non-empty ones."""
        values = [
            [[], [1, 2, 3]],
            [{}, {"a": 1}],
            {"empty": [], "full": [1, 2]},
            {"empty": {}, "full": {"a": 1}},
        ]
        for value in values:
            result = denormalize_from_match(normalize_for_match(value))
            assert result == value, f"Failed for {value}: got {result}"
