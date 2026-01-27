"""
Parity tests for subst_mu vs substitute.

These tests verify that subst_mu (Mu projections) produces identical
results to substitute (Python implementation) for all test cases.

Phase 4b: Substitute as Mu projections.
"""

import pytest

from rcx_pi.eval_seed import substitute
from rcx_pi.subst_mu import (
    subst_mu,
    load_subst_projections,
    clear_projection_cache,
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


def assert_parity(body, bindings):
    """Assert that subst_mu and substitute produce identical results."""
    py_result = substitute(body, bindings)
    mu_result = subst_mu(body, bindings)
    assert py_result == mu_result, (
        f"Parity failure:\n"
        f"  body: {body}\n"
        f"  bindings: {bindings}\n"
        f"  Python: {py_result}\n"
        f"  Mu: {mu_result}"
    )


# =============================================================================
# Test: Seed Loading
# =============================================================================


class TestSeedLoading:
    """Test that subst seed loads correctly."""

    def test_load_projections(self):
        """Projections load from JSON."""
        projections = load_subst_projections()
        assert isinstance(projections, list)
        assert len(projections) >= 5  # At least 5 core projections

    def test_projection_ids(self):
        """All projections have IDs."""
        projections = load_subst_projections()
        ids = [p.get("id") for p in projections]
        assert "subst.var" in ids
        assert "subst.descend" in ids
        assert "subst.sibling" in ids
        assert "subst.ascend" in ids
        assert "subst.done" in ids
        assert "subst.wrap" in ids

    def test_wrap_is_last(self):
        """Wrap projection must be last (catch-all)."""
        projections = load_subst_projections()
        assert projections[-1].get("id") == "subst.wrap"


# =============================================================================
# Test: Primitive Passthrough (Parity)
# =============================================================================
# NOTE: TestBindingLookup removed - lookup_binding() was deleted in Phase 6d
# as lookup is now handled structurally by subst.lookup.* projections (Phase 6a)


class TestSubstParityPrimitives:
    """Test that primitives pass through unchanged."""

    def test_null_passthrough(self):
        """Null passes through."""
        assert_parity(None, {})

    def test_bool_true_passthrough(self):
        """True passes through."""
        assert_parity(True, {})

    def test_bool_false_passthrough(self):
        """False passes through."""
        assert_parity(False, {})

    def test_int_passthrough(self):
        """Integer passes through."""
        assert_parity(42, {})

    def test_float_passthrough(self):
        """Float passes through."""
        assert_parity(3.14, {})

    def test_string_passthrough(self):
        """String passes through."""
        assert_parity("hello", {})


# =============================================================================
# Test: Variable Substitution (Parity)
# =============================================================================


class TestSubstParityVariables:
    """Test variable substitution parity."""

    def test_single_var(self):
        """Single variable substitution."""
        assert_parity({"var": "x"}, {"x": 42})

    def test_var_to_null(self):
        """Variable substitutes to null."""
        assert_parity({"var": "x"}, {"x": None})

    def test_var_to_string(self):
        """Variable substitutes to string."""
        assert_parity({"var": "x"}, {"x": "hello"})

    def test_var_to_list(self):
        """Variable substitutes to list."""
        assert_parity({"var": "x"}, {"x": [1, 2, 3]})

    def test_var_to_dict(self):
        """Variable substitutes to dict."""
        assert_parity({"var": "x"}, {"x": {"a": 1}})

    def test_multiple_vars(self):
        """Multiple different variables."""
        body = [{"var": "x"}, {"var": "y"}]
        bindings = {"x": 1, "y": 2}
        assert_parity(body, bindings)

    def test_same_var_twice(self):
        """Same variable used twice."""
        body = [{"var": "x"}, {"var": "x"}]
        bindings = {"x": 42}
        assert_parity(body, bindings)


# =============================================================================
# Test: Structure Substitution (Parity)
# =============================================================================


class TestSubstParityStructures:
    """Test substitution in nested structures."""

    def test_list_no_vars(self):
        """List with no variables."""
        assert_parity([1, 2, 3], {})

    def test_list_with_var(self):
        """List containing variable."""
        assert_parity([1, {"var": "x"}, 3], {"x": 2})

    def test_dict_no_vars(self):
        """Dict with no variables."""
        assert_parity({"a": 1, "b": 2}, {})

    def test_dict_with_var(self):
        """Dict containing variable."""
        assert_parity({"a": {"var": "x"}}, {"x": 42})

    def test_nested_dict(self):
        """Nested dict with variable."""
        assert_parity(
            {"a": {"b": {"var": "x"}}},
            {"x": 42}
        )

    def test_nested_list(self):
        """Nested list with variable."""
        assert_parity(
            [[{"var": "x"}]],
            {"x": 42}
        )

    def test_mixed_dict_list(self):
        """Dict containing list with variable."""
        assert_parity(
            {"items": [1, {"var": "x"}, 3]},
            {"x": 2}
        )

    def test_list_of_dicts(self):
        """List of dicts with variables."""
        assert_parity(
            [{"a": {"var": "x"}}, {"b": {"var": "y"}}],
            {"x": 1, "y": 2}
        )


# =============================================================================
# Test: Complex Cases (Parity)
# =============================================================================


class TestSubstParityComplex:
    """Test complex substitution cases."""

    def test_deeply_nested(self):
        """Deeply nested structure."""
        body = {"a": {"b": {"c": {"d": {"var": "x"}}}}}
        assert_parity(body, {"x": "deep"})

    def test_many_vars(self):
        """Many variables in one structure."""
        body = {
            "a": {"var": "v1"},
            "b": {"var": "v2"},
            "c": [{"var": "v3"}, {"var": "v4"}]
        }
        bindings = {"v1": 1, "v2": 2, "v3": 3, "v4": 4}
        assert_parity(body, bindings)

    def test_var_to_complex(self):
        """Variable substitutes to complex structure."""
        body = {"result": {"var": "data"}}
        bindings = {"data": {"nested": [1, 2, {"deep": True}]}}
        assert_parity(body, bindings)

    def test_projection_like_body(self):
        """Body that looks like a projection."""
        body = {
            "pattern": {"var": "p"},
            "body": {"var": "b"}
        }
        bindings = {
            "p": {"mode": "test"},
            "b": {"result": 42}
        }
        assert_parity(body, bindings)


# =============================================================================
# Test: Head/Tail Structures (Parity)
# =============================================================================


class TestSubstParityHeadTail:
    """Test head/tail structure substitution."""

    def test_head_tail_with_var(self):
        """Head/tail with variable in head."""
        body = {"head": {"var": "x"}, "tail": None}
        assert_parity(body, {"x": 42})

    def test_head_tail_both_vars(self):
        """Head/tail with variables in both."""
        body = {"head": {"var": "h"}, "tail": {"var": "t"}}
        bindings = {"h": 1, "t": 2}
        assert_parity(body, bindings)

    def test_linked_list_vars(self):
        """Linked list with variables."""
        body = {
            "head": {"var": "a"},
            "tail": {
                "head": {"var": "b"},
                "tail": None
            }
        }
        bindings = {"a": 1, "b": 2}
        assert_parity(body, bindings)


# =============================================================================
# Test: Error Cases
# =============================================================================


class TestSubstErrors:
    """Test error handling."""

    def test_unbound_variable(self):
        """Unbound variable raises KeyError."""
        with pytest.raises(KeyError, match="Unbound variable: x"):
            subst_mu({"var": "x"}, {})

    def test_unbound_in_nested(self):
        """Unbound variable in nested structure."""
        with pytest.raises(KeyError, match="Unbound variable: missing"):
            subst_mu({"a": {"var": "missing"}}, {})


# =============================================================================
# Test: Empty Variable Name Rejection (Phase 6d - Iterative Implementation)
# =============================================================================


class TestSubstEmptyVarNameRejection:
    """
    Test that empty variable names are rejected by subst_mu.

    The _check_empty_var_names function uses an explicit stack instead
    of recursion (Phase 6d), so these tests verify the iterative
    traversal works correctly.
    """

    def test_subst_mu_rejects_shallow_empty_var(self):
        """subst_mu raises ValueError for {"var": ""} at top level."""
        with pytest.raises(ValueError, match="Variable name cannot be empty"):
            subst_mu({"var": ""}, {"x": 1})

    def test_subst_mu_rejects_empty_var_in_dict(self):
        """subst_mu rejects empty var name nested in dict."""
        body = {"a": {"var": ""}}
        with pytest.raises(ValueError, match="Variable name cannot be empty"):
            subst_mu(body, {"x": 1})

    def test_subst_mu_rejects_empty_var_deeply_nested(self):
        """subst_mu rejects deeply nested empty var names."""
        body = {"a": {"b": {"c": {"d": {"var": ""}}}}}
        with pytest.raises(ValueError, match="Variable name cannot be empty"):
            subst_mu(body, {"x": 1})

    def test_subst_mu_rejects_empty_var_in_list(self):
        """subst_mu rejects empty var in list."""
        body = [{"var": ""}, {"var": "x"}]
        with pytest.raises(ValueError, match="Variable name cannot be empty"):
            subst_mu(body, {"x": 1})

    def test_subst_mu_rejects_empty_var_in_nested_list(self):
        """subst_mu rejects empty var in nested list (parity with match_mu tests)."""
        body = [[[[{"var": ""}]]]]
        with pytest.raises(ValueError, match="Variable name cannot be empty"):
            subst_mu(body, {"x": 1})

    def test_subst_mu_rejects_empty_var_in_mixed_structure(self):
        """subst_mu rejects empty var in mixed list/dict structure."""
        body = {"items": [{"key": {"var": ""}}]}
        with pytest.raises(ValueError, match="Variable name cannot be empty"):
            subst_mu(body, {"x": 1})

    def test_subst_mu_iterative_handles_wide_structure(self):
        """Iterative check handles wide structures (many keys)."""
        body = {f"key_{i}": i for i in range(50)}
        body["bad_key"] = {"var": ""}
        with pytest.raises(ValueError, match="Variable name cannot be empty"):
            subst_mu(body, {"x": 1})

    def test_subst_mu_accepts_valid_var_names(self):
        """subst_mu accepts non-empty variable names."""
        # Single char
        result = subst_mu({"var": "x"}, {"x": 42})
        assert result == 42

        # Longer name
        result = subst_mu({"var": "my_variable"}, {"my_variable": "hello"})
        assert result == "hello"

        # Unicode
        result = subst_mu({"var": "变量"}, {"变量": 123})
        assert result == 123
