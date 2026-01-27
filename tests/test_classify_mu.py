"""
Tests for classify_mu - Phase 6b classification as Mu projections.

These tests verify that:
1. Dict-encoded linked lists are correctly classified as "dict"
2. List-encoded linked lists are correctly classified as "list"
3. Edge cases (empty, primitives, mixed) are handled correctly
4. Classification produces same results as the Python is_dict_linked_list()
"""

import pytest

from rcx_pi.selfhost.classify_mu import (
    classify_linked_list,
    load_classify_projections,
    clear_projection_cache,
)
from rcx_pi.selfhost.match_mu import (
    normalize_for_match,
    is_dict_linked_list,
    is_kv_pair_linked,
)


# =============================================================================
# Test: Basic Classification
# =============================================================================


class TestBasicClassification:
    """Test basic dict vs list classification."""

    def test_empty_list_is_list(self):
        """Empty list (null) is classified as list."""
        assert classify_linked_list(None) == "list"

    def test_simple_list_is_list(self):
        """Simple list [1, 2, 3] is classified as list."""
        # Normalized: {"head": 1, "tail": {"head": 2, "tail": {"head": 3, "tail": null}}}
        normalized = normalize_for_match([1, 2, 3])
        assert classify_linked_list(normalized) == "list"

    def test_simple_dict_is_dict(self):
        """Simple dict {"a": 1} is classified as dict."""
        # Normalized: {"head": {"head": "a", "tail": {"head": 1, "tail": null}}, "tail": null}
        normalized = normalize_for_match({"a": 1})
        assert classify_linked_list(normalized) == "dict"

    def test_multi_key_dict_is_dict(self):
        """Multi-key dict {"a": 1, "b": 2} is classified as dict."""
        normalized = normalize_for_match({"a": 1, "b": 2})
        assert classify_linked_list(normalized) == "dict"

    def test_nested_dict_is_dict(self):
        """Nested dict {"outer": {"inner": 1}} is classified as dict."""
        normalized = normalize_for_match({"outer": {"inner": 1}})
        assert classify_linked_list(normalized) == "dict"


# =============================================================================
# Test: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and tricky inputs."""

    def test_list_of_strings_is_list(self):
        """List of strings ["a", "b"] is list, not dict."""
        normalized = normalize_for_match(["a", "b"])
        assert classify_linked_list(normalized) == "list"

    def test_list_of_lists_is_list(self):
        """List of lists [[1], [2]] is list."""
        normalized = normalize_for_match([[1], [2]])
        assert classify_linked_list(normalized) == "list"

    def test_list_with_kv_first_but_non_kv_later_is_list(self):
        """List where first element looks like kv-pair but later one doesn't."""
        # [["a", 1], "not-a-pair"] - first is kv-pair shaped, second isn't
        normalized = normalize_for_match([["a", 1], "not-a-pair"])
        # The Python function would return False (not all elements are kv-pairs)
        assert classify_linked_list(normalized) == "list"

    def test_dict_with_null_value_is_dict(self):
        """Dict with null value {"a": null} is still a dict."""
        normalized = normalize_for_match({"a": None})
        assert classify_linked_list(normalized) == "dict"

    def test_dict_with_empty_string_key_is_dict(self):
        """Dict with empty string key {"": 1} is still a dict."""
        normalized = normalize_for_match({"": 1})
        assert classify_linked_list(normalized) == "dict"


class TestTypeTaggedStructures:
    """Test that type tags resolve list/dict ambiguity (Phase 6c).

    PREVIOUSLY: A list of 2-element sublists where the first element is a
    string normalized identically to a dict. For example:
    - [[s, x]] normalized the same as {s: x}

    NOW (Phase 6c): Type tags distinguish lists from dicts:
    - [[s, x]] normalizes to {"_type": "list", ...}
    - {s: x} normalizes to {"_type": "dict", ...}
    """

    def test_type_tags_resolve_ambiguity(self):
        """Type tags distinguish previously-ambiguous structures."""
        # This list would have been ambiguous with a dict
        list_form = [['a', 1]]
        dict_form = {'a': 1}

        list_norm = normalize_for_match(list_form)
        dict_norm = normalize_for_match(dict_form)

        # With type tags, they are now DIFFERENT
        assert list_norm != dict_norm

        # Type tags correctly identify each
        assert list_norm.get("_type") == "list"
        assert dict_norm.get("_type") == "dict"

        # Classification uses type tags
        assert classify_linked_list(list_norm) == "list"
        assert classify_linked_list(dict_norm) == "dict"

    def test_unambiguous_list_classified_correctly(self):
        """Lists that don't look like dicts are classified as lists."""
        # 3-element sublist - not a kv-pair
        assert classify_linked_list(normalize_for_match([[1, 2, 3]])) == "list"

        # Non-string first element - not a kv-pair key
        assert classify_linked_list(normalize_for_match([[1, 2]])) == "list"

        # Single element (not a kv-pair)
        assert classify_linked_list(normalize_for_match([1, 2, 3])) == "list"

    def test_primitive_is_list(self):
        """Primitive values are classified as list (not head/tail)."""
        assert classify_linked_list(42) == "list"
        assert classify_linked_list("string") == "list"
        assert classify_linked_list(True) == "list"

    def test_non_head_tail_dict_is_list(self):
        """Dict without head/tail keys is classified as list."""
        assert classify_linked_list({"other": "keys"}) == "list"

    def test_list_containing_dict_is_list(self):
        """List containing a dict [{"a": 1}] is list, not dict.

        This is the key edge case: a dict's kv-pair structure has a string
        as the key, but a list containing a normalized dict has a dict
        (the kv-pair itself) in the key position.
        """
        normalized = normalize_for_match([{"a": 1}])
        assert classify_linked_list(normalized) == "list"

    def test_list_containing_multiple_dicts_is_list(self):
        """List containing multiple dicts [{"a": 1}, {"b": 2}] is list."""
        normalized = normalize_for_match([{"a": 1}, {"b": 2}])
        assert classify_linked_list(normalized) == "list"


# =============================================================================
# Test: Parity with Python Functions
# =============================================================================


class TestParityWithPython:
    """Ensure classify_linked_list produces same results as Python functions."""

    def test_parity_simple_list(self):
        """Parity: simple list."""
        normalized = normalize_for_match([1, 2, 3])
        python_result = is_dict_linked_list(normalized)
        projection_result = classify_linked_list(normalized) == "dict"
        assert python_result == projection_result

    def test_parity_simple_dict(self):
        """Parity: simple dict."""
        normalized = normalize_for_match({"a": 1})
        python_result = is_dict_linked_list(normalized)
        projection_result = classify_linked_list(normalized) == "dict"
        assert python_result == projection_result

    def test_parity_mixed_content(self):
        """Parity: list with kv-pair first element but non-kv later."""
        normalized = normalize_for_match([["a", 1], "not-kv"])
        python_result = is_dict_linked_list(normalized)
        projection_result = classify_linked_list(normalized) == "dict"
        assert python_result == projection_result

    def test_parity_empty(self):
        """Parity: empty (null)."""
        python_result = is_dict_linked_list(None)
        projection_result = classify_linked_list(None) == "dict"
        assert python_result == projection_result

    def test_parity_nested_dicts(self):
        """Parity: nested dicts."""
        normalized = normalize_for_match({"a": {"b": {"c": 1}}})
        python_result = is_dict_linked_list(normalized)
        projection_result = classify_linked_list(normalized) == "dict"
        assert python_result == projection_result


# =============================================================================
# Test: Integration with match_mu
# =============================================================================


class TestIntegrationWithMatch:
    """Test that classification works correctly in denormalization context."""

    def test_denormalize_uses_projection_classification(self):
        """Verify denormalize_from_match uses projection-based classification."""
        from rcx_pi.selfhost.match_mu import denormalize_from_match

        # Dict should denormalize back to dict
        normalized = normalize_for_match({"a": 1, "b": 2})
        result = denormalize_from_match(normalized)
        assert result == {"a": 1, "b": 2}

    def test_denormalize_list_correctly(self):
        """Verify list denormalizes correctly."""
        from rcx_pi.selfhost.match_mu import denormalize_from_match

        normalized = normalize_for_match([1, 2, 3])
        result = denormalize_from_match(normalized)
        assert result == [1, 2, 3]

    def test_match_mu_round_trip_with_dict(self):
        """Full round-trip: pattern match with dict value."""
        from rcx_pi.selfhost.match_mu import match_mu

        pattern = {"key": {"var": "x"}}
        value = {"key": {"nested": "value"}}

        result = match_mu(pattern, value)
        assert result != "NO_MATCH"
        assert result["x"] == {"nested": "value"}


# =============================================================================
# Test: Projection Loading
# =============================================================================


class TestProjectionLoading:
    """Test projection loading and caching."""

    def test_load_classify_projections(self):
        """Load projections successfully."""
        clear_projection_cache()
        projections = load_classify_projections()
        assert len(projections) == 6  # Added classify.nested_not_kv

    def test_projection_ids_correct(self):
        """Projections have expected IDs."""
        clear_projection_cache()
        projections = load_classify_projections()
        ids = [p["id"] for p in projections]
        assert "classify.done" in ids
        assert "classify.nested_not_kv" in ids  # Reject head/tail in key position
        assert "classify.kv_continue" in ids
        assert "classify.not_kv" in ids
        assert "classify.empty" in ids
        assert "classify.wrap" in ids

    def test_wrap_is_last(self):
        """classify.wrap is last projection (catch-all)."""
        clear_projection_cache()
        projections = load_classify_projections()
        assert projections[-1]["id"] == "classify.wrap"

    def test_caching_works(self):
        """Second load returns same cached projections."""
        clear_projection_cache()
        p1 = load_classify_projections()
        p2 = load_classify_projections()
        assert p1 is p2  # Same object (cached)
