"""
Parity tests for match_mu vs match.

These tests verify that match_mu (Mu projections) produces identical
results to match (Python implementation) for all test cases.

Phase 4a scope: Linear patterns only (no conflict detection).
"""

import pytest

from rcx_pi.eval_seed import match, NO_MATCH
from rcx_pi.match_mu import (
    match_mu,
    load_match_projections,
    clear_projection_cache,
    bindings_to_dict,
    dict_to_bindings,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset projection cache before each test."""
    clear_projection_cache()
    yield
    clear_projection_cache()


# =============================================================================
# Helper: Parity Assertion
# =============================================================================


def assert_parity(pattern, value):
    """Assert that match_mu and match produce identical results."""
    py_result = match(pattern, value)
    mu_result = match_mu(pattern, value)

    if py_result is NO_MATCH:
        assert mu_result is NO_MATCH, (
            f"Parity failure: Python returned NO_MATCH, "
            f"but Mu returned {mu_result}"
        )
    else:
        assert mu_result is not NO_MATCH, (
            f"Parity failure: Python returned {py_result}, "
            f"but Mu returned NO_MATCH"
        )
        assert py_result == mu_result, (
            f"Parity failure: Python returned {py_result}, "
            f"but Mu returned {mu_result}"
        )


# =============================================================================
# Test: Seed Loading
# =============================================================================


class TestSeedLoading:
    """Test that match seed loads correctly."""

    def test_load_projections(self):
        """Projections load from JSON."""
        projections = load_match_projections()
        assert isinstance(projections, list)
        assert len(projections) >= 5  # At least 5 core projections

    def test_projection_ids(self):
        """All projections have IDs."""
        projections = load_match_projections()
        ids = [p.get("id") for p in projections]
        assert "match.var" in ids
        assert "match.dict.descend" in ids
        assert "match.sibling" in ids
        assert "match.done" in ids
        assert "match.wrap" in ids

    def test_wrap_is_last(self):
        """Wrap projection must be last (catch-all)."""
        projections = load_match_projections()
        assert projections[-1].get("id") == "match.wrap"


# =============================================================================
# Test: Bindings Conversion
# =============================================================================


class TestBindingsConversion:
    """Test bindings linked list <-> dict conversion."""

    def test_empty_bindings(self):
        """Null converts to empty dict."""
        assert bindings_to_dict(None) == {}

    def test_single_binding(self):
        """Single binding converts correctly."""
        linked = {"name": "x", "value": 42, "rest": None}
        assert bindings_to_dict(linked) == {"x": 42}

    def test_multiple_bindings(self):
        """Multiple bindings convert correctly."""
        linked = {
            "name": "x",
            "value": 42,
            "rest": {
                "name": "y",
                "value": "hello",
                "rest": None
            }
        }
        assert bindings_to_dict(linked) == {"x": 42, "y": "hello"}

    def test_dict_to_bindings_empty(self):
        """Empty dict converts to null."""
        assert dict_to_bindings({}) is None

    def test_dict_to_bindings_roundtrip(self):
        """Dict -> linked -> dict roundtrip."""
        original = {"a": 1, "b": 2, "c": 3}
        linked = dict_to_bindings(original)
        restored = bindings_to_dict(linked)
        assert restored == original


# =============================================================================
# Test: Variable Matching (Parity)
# =============================================================================


class TestMatchParityVariables:
    """Test variable binding parity."""

    def test_var_matches_null(self):
        """Variable matches null."""
        assert_parity({"var": "x"}, None)

    def test_var_matches_int(self):
        """Variable matches integer."""
        assert_parity({"var": "x"}, 42)

    def test_var_matches_string(self):
        """Variable matches string."""
        assert_parity({"var": "x"}, "hello")

    def test_var_matches_bool(self):
        """Variable matches boolean."""
        assert_parity({"var": "x"}, True)

    def test_var_matches_list(self):
        """Variable matches list."""
        assert_parity({"var": "x"}, [1, 2, 3])

    def test_var_matches_dict(self):
        """Variable matches dict."""
        assert_parity({"var": "x"}, {"a": 1, "b": 2})

    def test_var_matches_nested(self):
        """Variable matches nested structure."""
        assert_parity({"var": "x"}, {"a": [1, {"b": 2}]})


# =============================================================================
# Test: Dict Structure Matching (Parity)
# =============================================================================


class TestMatchParityDicts:
    """Test dict structure matching parity."""

    def test_empty_dict_matches_empty(self):
        """Empty dict matches empty dict."""
        assert_parity({}, {})

    def test_dict_same_keys_values(self):
        """Dict with same keys and values matches."""
        assert_parity({"a": 1, "b": 2}, {"a": 1, "b": 2})

    def test_dict_with_var(self):
        """Dict with variable in value."""
        assert_parity({"a": {"var": "x"}}, {"a": 42})

    def test_dict_nested(self):
        """Nested dict structure."""
        assert_parity(
            {"a": {"b": {"var": "x"}}},
            {"a": {"b": 42}}
        )

    def test_dict_multiple_vars(self):
        """Dict with multiple variables."""
        assert_parity(
            {"a": {"var": "x"}, "b": {"var": "y"}},
            {"a": 1, "b": 2}
        )

    def test_dict_different_keys_fails(self):
        """Dict with different keys fails."""
        assert_parity({"a": 1}, {"b": 1})

    def test_dict_extra_key_fails(self):
        """Dict with extra key fails."""
        assert_parity({"a": 1}, {"a": 1, "b": 2})

    def test_dict_missing_key_fails(self):
        """Dict with missing key fails."""
        assert_parity({"a": 1, "b": 2}, {"a": 1})


# =============================================================================
# Test: Primitive Matching (Parity)
# =============================================================================


class TestMatchParityPrimitives:
    """Test primitive value matching parity."""

    def test_null_matches_null(self):
        """Null matches null."""
        assert_parity(None, None)

    def test_null_not_matches_zero(self):
        """Null doesn't match zero."""
        assert_parity(None, 0)

    def test_true_matches_true(self):
        """True matches true."""
        assert_parity(True, True)

    def test_false_matches_false(self):
        """False matches false."""
        assert_parity(False, False)

    def test_true_not_matches_false(self):
        """True doesn't match false."""
        assert_parity(True, False)

    def test_int_matches_same(self):
        """Int matches same int."""
        assert_parity(42, 42)

    def test_int_not_matches_different(self):
        """Int doesn't match different int."""
        assert_parity(42, 43)

    def test_string_matches_same(self):
        """String matches same string."""
        assert_parity("hello", "hello")

    def test_string_not_matches_different(self):
        """String doesn't match different string."""
        assert_parity("hello", "world")

    def test_bool_not_matches_int(self):
        """Bool doesn't match equivalent int (type matters)."""
        assert_parity(True, 1)

    def test_int_not_matches_bool(self):
        """Int doesn't match equivalent bool (type matters)."""
        assert_parity(1, True)


# =============================================================================
# Test: List Matching (Parity)
# =============================================================================


class TestMatchParityLists:
    """Test list structure matching parity."""

    def test_empty_list_matches_empty(self):
        """Empty list matches empty list."""
        assert_parity([], [])

    def test_list_same_elements(self):
        """List with same elements matches."""
        assert_parity([1, 2, 3], [1, 2, 3])

    def test_list_different_length_fails(self):
        """List with different length fails."""
        assert_parity([1, 2], [1, 2, 3])

    def test_list_different_element_fails(self):
        """List with different element fails."""
        assert_parity([1, 2, 3], [1, 2, 4])

    def test_list_with_var(self):
        """List with variable."""
        assert_parity([{"var": "x"}, 2], [1, 2])

    def test_list_nested(self):
        """Nested list."""
        assert_parity([[1, 2]], [[1, 2]])


# =============================================================================
# Test: Complex Structures (Parity)
# =============================================================================


class TestMatchParityComplex:
    """Test complex/mixed structure matching parity."""

    def test_mixed_dict_list(self):
        """Dict containing list."""
        assert_parity(
            {"items": [1, 2, 3]},
            {"items": [1, 2, 3]}
        )

    def test_list_of_dicts(self):
        """List containing dicts."""
        assert_parity(
            [{"a": 1}, {"b": 2}],
            [{"a": 1}, {"b": 2}]
        )

    def test_deeply_nested(self):
        """Deeply nested structure."""
        pattern = {"a": {"b": {"c": {"var": "x"}}}}
        value = {"a": {"b": {"c": 42}}}
        assert_parity(pattern, value)

    def test_multiple_vars_complex(self):
        """Multiple variables in complex structure."""
        pattern = {
            "name": {"var": "n"},
            "items": [{"var": "first"}, {"var": "second"}]
        }
        value = {
            "name": "test",
            "items": [1, 2]
        }
        assert_parity(pattern, value)


# =============================================================================
# Test: Head/Tail Structures (Key for Mu)
# =============================================================================


class TestMatchParityHeadTail:
    """Test head/tail (linked list) structure matching.

    This is critical because Mu uses head/tail for dict representation.
    """

    def test_head_tail_basic(self):
        """Basic head/tail structure."""
        pattern = {"head": {"var": "h"}, "tail": {"var": "t"}}
        value = {"head": 1, "tail": None}
        assert_parity(pattern, value)

    def test_head_tail_nested(self):
        """Nested head/tail (linked list)."""
        pattern = {
            "head": {"var": "first"},
            "tail": {
                "head": {"var": "second"},
                "tail": None
            }
        }
        value = {
            "head": 1,
            "tail": {
                "head": 2,
                "tail": None
            }
        }
        assert_parity(pattern, value)

    def test_head_tail_deep(self):
        """Deep head/tail chain."""
        # 3-element linked list
        pattern = {
            "head": {"var": "a"},
            "tail": {
                "head": {"var": "b"},
                "tail": {
                    "head": {"var": "c"},
                    "tail": None
                }
            }
        }
        value = {
            "head": 1,
            "tail": {
                "head": 2,
                "tail": {
                    "head": 3,
                    "tail": None
                }
            }
        }
        assert_parity(pattern, value)


# =============================================================================
# Test: Type Mismatches (Failure Cases)
# =============================================================================


class TestMatchParityFailures:
    """Test that type mismatches properly fail."""

    def test_dict_vs_list(self):
        """Dict pattern doesn't match list value."""
        assert_parity({"a": 1}, [1])

    def test_list_vs_dict(self):
        """List pattern doesn't match dict value."""
        assert_parity([1], {"a": 1})

    def test_dict_vs_primitive(self):
        """Dict pattern doesn't match primitive."""
        assert_parity({"a": 1}, 42)

    def test_list_vs_primitive(self):
        """List pattern doesn't match primitive."""
        assert_parity([1, 2], 42)

    def test_primitive_vs_dict(self):
        """Primitive pattern doesn't match dict."""
        assert_parity(42, {"a": 1})

    def test_primitive_vs_list(self):
        """Primitive pattern doesn't match list."""
        assert_parity(42, [1, 2])


# =============================================================================
# Test: Head/Tail Collision (Adversary Finding V2)
# =============================================================================


class TestMatchParityHeadTailCollision:
    """Test that dicts with head/tail keys are NOT misclassified as linked lists.

    This addresses adversary finding V2: user data containing 'head' and 'tail'
    keys should not be confused with the internal linked list encoding.
    """

    def test_dict_with_head_tail_keys_string_tail(self):
        """Dict with head/tail keys where tail is a string (not a node)."""
        # This is user data, not a linked list node
        pattern = {"head": {"var": "h"}, "tail": {"var": "t"}}
        value = {"head": "x", "tail": "y"}  # tail is string, not node
        assert_parity(pattern, value)

    def test_dict_with_head_tail_keys_int_tail(self):
        """Dict with head/tail keys where tail is an int (not a node)."""
        pattern = {"head": {"var": "h"}, "tail": {"var": "t"}}
        value = {"head": 1, "tail": 2}
        assert_parity(pattern, value)

    def test_dict_with_head_tail_keys_list_tail(self):
        """Dict with head/tail keys where tail is a list (not a node)."""
        pattern = {"head": {"var": "h"}, "tail": {"var": "t"}}
        value = {"head": "x", "tail": [1, 2, 3]}
        assert_parity(pattern, value)

    def test_dict_with_head_tail_keys_dict_wrong_shape(self):
        """Dict with head/tail keys where tail is a dict but wrong shape."""
        pattern = {"head": {"var": "h"}, "tail": {"var": "t"}}
        value = {"head": "x", "tail": {"a": 1, "b": 2}}  # Not head/tail shape
        assert_parity(pattern, value)

    def test_nested_head_tail_collision(self):
        """Nested structure with head/tail keys at multiple levels."""
        pattern = {
            "data": {"var": "d"},
            "meta": {"head": {"var": "h"}, "tail": {"var": "t"}}
        }
        value = {
            "data": [1, 2, 3],
            "meta": {"head": "first", "tail": "last"}
        }
        assert_parity(pattern, value)


# =============================================================================
# Test: Empty Collection Normalization (Adversary Finding V1)
# =============================================================================


class TestMatchParityEmptyCollections:
    """Test empty collection normalization behavior.

    This documents adversary finding V1: {} and [] both normalize to null
    (empty linked list). This creates a KNOWN DIFFERENCE between Python and Mu:

    - Python match: {} and [] are different types, don't match each other
    - Mu match: {} and [] both normalize to null, match the same patterns

    These tests document this intentional difference rather than assert parity.
    """

    def test_empty_dict_vs_empty_list_now_matches_python(self):
        """Phase 8b fix: {} vs [] is now NO_MATCH in both Python and Mu.

        With typed sentinels, {} becomes {"_type": "dict"} and [] becomes
        {"_type": "list"}, so they no longer match (correct behavior).
        """
        from rcx_pi.eval_seed import match
        from rcx_pi.match_mu import match_mu

        # Python treats these as different types
        assert match({}, []) is NO_MATCH
        assert match([], {}) is NO_MATCH

        # Mu now also distinguishes them (Phase 8b fix)
        assert match_mu({}, []) is NO_MATCH
        assert match_mu([], {}) is NO_MATCH

    def test_var_matches_empty_dict_preserves_type(self):
        """Phase 8b fix: Variable binding of {} now preserved in Mu.

        With typed sentinel, {} roundtrips correctly.
        """
        from rcx_pi.eval_seed import match
        from rcx_pi.match_mu import match_mu

        # Python preserves the original structure
        assert match({"var": "x"}, {}) == {"x": {}}

        # Mu now also preserves {} via typed sentinel (Phase 8b fix)
        assert match_mu({"var": "x"}, {}) == {"x": {}}

    def test_var_matches_empty_list_preserves_type(self):
        """Phase 8b fix: Variable binding of [] now preserved in Mu.

        With typed sentinel, [] roundtrips correctly.
        """
        from rcx_pi.eval_seed import match
        from rcx_pi.match_mu import match_mu

        # Python preserves the original structure
        assert match({"var": "x"}, []) == {"x": []}

        # Mu now also preserves [] via typed sentinel (Phase 8b fix)
        assert match_mu({"var": "x"}, []) == {"x": []}

    def test_dict_with_empty_value(self):
        """Dict with empty list value - parity maintained for nested empties."""
        assert_parity({"items": []}, {"items": []})

    def test_dict_with_empty_dict_value(self):
        """Dict with empty dict value - parity maintained for nested empties."""
        assert_parity({"config": {}}, {"config": {}})


# =============================================================================
# Shared References (DAG) Tests - Phase 6c
# =============================================================================


class TestSharedReferencesAllowed:
    """Tests that shared references (DAGs) are allowed, not flagged as cycles.

    Phase 6c introduced path-based cycle detection that distinguishes:
    - Cycles (back-edges): Same node on current traversal path → reject
    - Shared refs (DAGs): Same node via different paths → allow

    These tests verify the fix works correctly.
    """

    def test_shared_list_in_normalize(self):
        """Shared list reference should not trigger cycle detection."""
        from rcx_pi.match_mu import normalize_for_match

        shared = [1, 2, 3]
        dag = [shared, shared]  # Same object twice

        # Should NOT raise ValueError
        result = normalize_for_match(dag)
        assert result is not None

    def test_shared_dict_in_normalize(self):
        """Shared dict reference should not trigger cycle detection."""
        from rcx_pi.match_mu import normalize_for_match

        shared = {"x": 42}
        dag = {"a": shared, "b": shared}  # Same object twice

        # Should NOT raise ValueError
        result = normalize_for_match(dag)
        assert result is not None

    def test_shared_empty_list_in_normalize(self):
        """Shared empty list reference - the original bug case."""
        from rcx_pi.match_mu import normalize_for_match

        shared = []
        dag = [shared, shared, "literal"]

        # Should NOT raise ValueError (this was the bug!)
        result = normalize_for_match(dag)
        assert result is not None

    def test_diamond_dag_in_normalize(self):
        """Diamond DAG pattern - shared node at multiple depths."""
        from rcx_pi.match_mu import normalize_for_match

        leaf = {"value": 1}
        left = {"child": leaf}
        right = {"child": leaf}
        root = {"left": left, "right": right}

        # Should NOT raise ValueError
        result = normalize_for_match(root)
        assert result is not None

    def test_shared_reference_in_denormalize(self):
        """Shared reference in denormalize_from_match."""
        from rcx_pi.match_mu import denormalize_from_match

        # Manually construct a normalized structure with shared refs
        shared = {"head": 1, "tail": {"head": 2, "tail": None}}
        dag = {"head": shared, "tail": {"head": shared, "tail": None}}

        # Should NOT raise ValueError
        result = denormalize_from_match(dag)
        assert result is not None

    def test_true_cycle_still_detected_normalize(self):
        """True cycles should still be detected in normalize."""
        from rcx_pi.match_mu import normalize_for_match

        cycle = {}
        cycle["self"] = cycle

        with pytest.raises(ValueError, match="Circular reference"):
            normalize_for_match(cycle)

    def test_true_cycle_still_detected_denormalize(self):
        """True cycles should still be detected in denormalize."""
        from rcx_pi.match_mu import denormalize_from_match

        cycle = {"head": 1, "tail": None}
        cycle["tail"] = cycle

        with pytest.raises(ValueError, match="Circular reference"):
            denormalize_from_match(cycle)

    def test_shared_ref_roundtrip(self):
        """Shared references should survive normalize/denormalize roundtrip."""
        from rcx_pi.match_mu import normalize_for_match, denormalize_from_match

        shared = [1, 2, 3]
        original = [shared, shared]

        normalized = normalize_for_match(original)
        denormalized = denormalize_from_match(normalized)

        # Structure should be preserved (though shared refs become copies)
        assert denormalized == [[1, 2, 3], [1, 2, 3]]


# =============================================================================
# Empty Variable Name Rejection Tests (Phase 6d - Iterative Implementation)
# =============================================================================


class TestEmptyVarNameRejection:
    """
    Test that empty variable names are rejected by the iterative
    _check_empty_var_names implementation (Phase 6d).

    The function uses an explicit stack instead of recursion, so these
    tests verify the iterative traversal works correctly at various depths.
    """

    def test_match_mu_rejects_shallow_empty_var(self):
        """match_mu raises ValueError for {"var": ""} at top level."""
        with pytest.raises(ValueError, match="Variable name cannot be empty"):
            match_mu({"var": ""}, 42)

    def test_match_mu_rejects_empty_var_in_dict(self):
        """match_mu rejects empty var name nested in dict."""
        pattern = {"a": {"var": ""}}
        with pytest.raises(ValueError, match="Variable name cannot be empty"):
            match_mu(pattern, {"a": 1})

    def test_match_mu_rejects_empty_var_deeply_nested(self):
        """match_mu rejects deeply nested empty var names."""
        pattern = {"a": {"b": {"c": {"d": {"var": ""}}}}}
        with pytest.raises(ValueError, match="Variable name cannot be empty"):
            match_mu(pattern, {"a": {"b": {"c": {"d": 1}}}})

    def test_match_mu_rejects_empty_var_in_list(self):
        """match_mu rejects empty var in list."""
        pattern = [{"var": ""}, {"var": "x"}]
        with pytest.raises(ValueError, match="Variable name cannot be empty"):
            match_mu(pattern, [1, 2])

    def test_match_mu_rejects_empty_var_in_nested_list(self):
        """match_mu rejects empty var in nested list."""
        pattern = [[[[{"var": ""}]]]]
        with pytest.raises(ValueError, match="Variable name cannot be empty"):
            match_mu(pattern, [[[[1]]]])

    def test_match_mu_rejects_empty_var_in_mixed_structure(self):
        """match_mu rejects empty var in mixed list/dict structure."""
        pattern = {"items": [{"key": {"var": ""}}]}
        with pytest.raises(ValueError, match="Variable name cannot be empty"):
            match_mu(pattern, {"items": [{"key": "value"}]})

    def test_match_mu_accepts_valid_var_names(self):
        """match_mu accepts non-empty variable names."""
        # Single char
        result = match_mu({"var": "x"}, 42)
        assert result == {"x": 42}

        # Longer name
        result = match_mu({"var": "my_variable"}, "hello")
        assert result == {"my_variable": "hello"}

        # Unicode
        result = match_mu({"var": "变量"}, 123)
        assert result == {"变量": 123}

    def test_match_mu_accepts_deeply_nested_valid_vars(self):
        """match_mu accepts valid vars at any depth."""
        pattern = {"a": {"b": {"c": {"var": "deep"}}}}
        value = {"a": {"b": {"c": "found"}}}
        result = match_mu(pattern, value)
        assert result == {"deep": "found"}

    def test_iterative_handles_wide_structure(self):
        """Iterative check handles wide structures (many keys)."""
        # Build pattern with many keys, one has empty var
        pattern = {f"key_{i}": i for i in range(50)}
        pattern["bad_key"] = {"var": ""}

        with pytest.raises(ValueError, match="Variable name cannot be empty"):
            match_mu(pattern, {f"key_{i}": i for i in range(51)})

    def test_iterative_handles_wide_list(self):
        """Iterative check handles wide lists (many elements)."""
        # Build list with many elements, one has empty var
        pattern = list(range(50)) + [{"var": ""}]

        with pytest.raises(ValueError, match="Variable name cannot be empty"):
            match_mu(pattern, list(range(51)))
