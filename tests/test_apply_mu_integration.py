"""
Phase 4d: Integration tests for match_mu + subst_mu.

Verifies that the Mu-based match and substitute work together
as a complete replacement for apply_projection.

This file validates parity between:
- apply_projection (Python reference, uses match/substitute)
- apply_mu (Mu integration, uses match_mu + subst_mu)

Phase 4d goal: Ensure Mu-based match + substitute work correctly together.
(This is integration testing, not apply as pure Mu projections.)

KNOWN LIMITATIONS due to normalization/denormalization:
- Empty collections ([], {}) normalize to None
- Existing head/tail structures denormalize to Python lists
These are acceptable because RCX projections work on normalized structures.

See docs/core/SelfHosting.v0.md for design.
"""

import pytest

from rcx_pi.eval_seed import apply_projection, match, substitute, NO_MATCH

# Import shared apply_mu from conftest (avoids duplication)
from conftest import apply_mu


class TestApplyMuParitySimple:
    """Test apply_mu matches apply_projection for simple cases."""

    def test_literal_match_no_vars(self):
        """Literal pattern with no variables."""
        proj = {"pattern": 42, "body": "matched"}

        py_result = apply_projection(proj, 42)
        mu_result = apply_mu(proj, 42)

        assert py_result == mu_result == "matched"

    def test_literal_no_match(self):
        """Literal pattern that doesn't match."""
        proj = {"pattern": 42, "body": "matched"}

        py_result = apply_projection(proj, 99)
        mu_result = apply_mu(proj, 99)

        assert py_result is NO_MATCH
        assert mu_result is NO_MATCH

    def test_single_variable(self):
        """Single variable captures value."""
        proj = {"pattern": {"var": "x"}, "body": {"var": "x"}}

        py_result = apply_projection(proj, 42)
        mu_result = apply_mu(proj, 42)

        assert py_result == mu_result == 42

    def test_variable_in_body(self):
        """Variable substituted into body structure."""
        proj = {
            "pattern": {"var": "x"},
            "body": {"result": {"var": "x"}}
        }

        py_result = apply_projection(proj, "hello")
        mu_result = apply_mu(proj, "hello")

        assert py_result == mu_result == {"result": "hello"}


class TestApplyMuParityStructures:
    """Test apply_mu matches apply_projection for structured data."""

    def test_dict_pattern_extraction(self):
        """Extract values from dict pattern."""
        proj = {
            "pattern": {"name": {"var": "n"}, "age": {"var": "a"}},
            "body": {"person": {"var": "n"}, "years": {"var": "a"}}
        }
        input_val = {"name": "Alice", "age": 30}

        py_result = apply_projection(proj, input_val)
        mu_result = apply_mu(proj, input_val)

        assert py_result == mu_result == {"person": "Alice", "years": 30}

    def test_list_pattern_extraction(self):
        """Extract values from list pattern."""
        proj = {
            "pattern": [{"var": "first"}, {"var": "second"}],
            "body": {"a": {"var": "first"}, "b": {"var": "second"}}
        }
        input_val = [1, 2]

        py_result = apply_projection(proj, input_val)
        mu_result = apply_mu(proj, input_val)

        assert py_result == mu_result == {"a": 1, "b": 2}

    def test_nested_structure(self):
        """Deeply nested pattern and body."""
        proj = {
            "pattern": {"outer": {"inner": {"var": "val"}}},
            "body": {"result": {"nested": {"var": "val"}}}
        }
        input_val = {"outer": {"inner": "deep"}}

        py_result = apply_projection(proj, input_val)
        mu_result = apply_mu(proj, input_val)

        assert py_result == mu_result == {"result": {"nested": "deep"}}

    def test_mixed_literals_and_vars(self):
        """Pattern with both literals and variables."""
        proj = {
            "pattern": {"type": "user", "data": {"var": "d"}},
            "body": {"user_data": {"var": "d"}}
        }
        input_val = {"type": "user", "data": {"name": "Bob"}}

        py_result = apply_projection(proj, input_val)
        mu_result = apply_mu(proj, input_val)

        assert py_result == mu_result == {"user_data": {"name": "Bob"}}

    def test_literal_mismatch_in_structure(self):
        """Literal part of pattern doesn't match."""
        proj = {
            "pattern": {"type": "user", "data": {"var": "d"}},
            "body": {"user_data": {"var": "d"}}
        }
        input_val = {"type": "admin", "data": {"name": "Bob"}}

        py_result = apply_projection(proj, input_val)
        mu_result = apply_mu(proj, input_val)

        assert py_result is NO_MATCH
        assert mu_result is NO_MATCH


class TestApplyMuParityMultipleVars:
    """Test apply_mu with multiple variables."""

    def test_three_variables(self):
        """Three variables in pattern and body."""
        proj = {
            "pattern": {"a": {"var": "x"}, "b": {"var": "y"}, "c": {"var": "z"}},
            "body": {"first": {"var": "x"}, "second": {"var": "y"}, "third": {"var": "z"}}
        }
        input_val = {"a": 1, "b": 2, "c": 3}

        py_result = apply_projection(proj, input_val)
        mu_result = apply_mu(proj, input_val)

        assert py_result == mu_result == {"first": 1, "second": 2, "third": 3}

    def test_variable_used_multiple_times(self):
        """Same variable used multiple times in body."""
        proj = {
            "pattern": {"var": "x"},
            "body": {"a": {"var": "x"}, "b": {"var": "x"}, "c": {"var": "x"}}
        }
        input_val = "duplicate"

        py_result = apply_projection(proj, input_val)
        mu_result = apply_mu(proj, input_val)

        assert py_result == mu_result == {"a": "duplicate", "b": "duplicate", "c": "duplicate"}

    def test_variable_not_used_in_body(self):
        """Variable captured but not used in body."""
        proj = {
            "pattern": {"keep": {"var": "k"}, "ignore": {"var": "i"}},
            "body": {"result": {"var": "k"}}
        }
        input_val = {"keep": "important", "ignore": "discarded"}

        py_result = apply_projection(proj, input_val)
        mu_result = apply_mu(proj, input_val)

        assert py_result == mu_result == {"result": "important"}


class TestApplyMuParityEdgeCases:
    """Test apply_mu edge cases."""

    def test_null_value(self):
        """Match and substitute null."""
        proj = {
            "pattern": {"var": "x"},
            "body": {"value": {"var": "x"}}
        }

        py_result = apply_projection(proj, None)
        mu_result = apply_mu(proj, None)

        assert py_result == mu_result == {"value": None}

    def test_boolean_values(self):
        """Match and substitute booleans."""
        proj = {
            "pattern": {"flag": {"var": "f"}},
            "body": {"inverted": {"var": "f"}}
        }

        for val in [True, False]:
            input_val = {"flag": val}
            py_result = apply_projection(proj, input_val)
            mu_result = apply_mu(proj, input_val)
            assert py_result == mu_result == {"inverted": val}

    def test_empty_dict(self):
        """Empty dict as value.

        KNOWN LIMITATION: Empty collections normalize to None in linked-list
        representation. The denormalization can't recover the original type.
        This is acceptable because RCX projections work on normalized structures.
        """
        proj = {
            "pattern": {"var": "x"},
            "body": {"wrapped": {"var": "x"}}
        }

        py_result = apply_projection(proj, {})
        mu_result = apply_mu(proj, {})

        # Python version preserves empty dict
        assert py_result == {"wrapped": {}}
        # Mu version normalizes to None (empty linked list)
        assert mu_result == {"wrapped": None}

    def test_empty_list(self):
        """Empty list as value.

        KNOWN LIMITATION: Empty collections normalize to None in linked-list
        representation. The denormalization can't recover the original type.
        """
        proj = {
            "pattern": {"var": "x"},
            "body": {"items": {"var": "x"}}
        }

        py_result = apply_projection(proj, [])
        mu_result = apply_mu(proj, [])

        # Python version preserves empty list
        assert py_result == {"items": []}
        # Mu version normalizes to None (empty linked list)
        assert mu_result == {"items": None}

    def test_complex_nested_value(self):
        """Complex nested structure as captured value."""
        proj = {
            "pattern": {"data": {"var": "d"}},
            "body": {"result": {"var": "d"}}
        }
        complex_data = {
            "users": [
                {"name": "Alice", "scores": [1, 2, 3]},
                {"name": "Bob", "scores": [4, 5, 6]}
            ],
            "meta": {"count": 2, "active": True}
        }
        input_val = {"data": complex_data}

        py_result = apply_projection(proj, input_val)
        mu_result = apply_mu(proj, input_val)

        assert py_result == mu_result == {"result": complex_data}


class TestApplyMuParityRealProjections:
    """Test apply_mu with realistic projection patterns."""

    def test_increment_projection(self):
        """Projection that extracts a value for increment."""
        # This pattern is used in real RCX seeds
        proj = {
            "pattern": {"op": "get", "key": {"var": "k"}, "from": {"var": "obj"}},
            "body": {"lookup": {"key": {"var": "k"}, "in": {"var": "obj"}}}
        }
        input_val = {"op": "get", "key": "name", "from": {"name": "Alice", "age": 30}}

        py_result = apply_projection(proj, input_val)
        mu_result = apply_mu(proj, input_val)

        assert py_result == mu_result == {
            "lookup": {"key": "name", "in": {"name": "Alice", "age": 30}}
        }

    def test_state_transform_projection(self):
        """Projection that transforms state structure."""
        proj = {
            "pattern": {"state": {"var": "s"}, "event": {"type": "update", "value": {"var": "v"}}},
            "body": {"state": {"var": "v"}, "event": None}
        }
        input_val = {"state": "old", "event": {"type": "update", "value": "new"}}

        py_result = apply_projection(proj, input_val)
        mu_result = apply_mu(proj, input_val)

        assert py_result == mu_result == {"state": "new", "event": None}

    def test_head_tail_linked_list(self):
        """Projection pattern using head/tail (linked list style).

        KNOWN LIMITATION: Existing head/tail structures are treated as linked
        lists by normalization, and denormalized back to Python lists.
        This is by design - RCX internally uses linked lists.
        """
        proj = {
            "pattern": {"head": {"var": "h"}, "tail": {"var": "t"}},
            "body": {"first": {"var": "h"}, "rest": {"var": "t"}}
        }
        input_val = {"head": 1, "tail": {"head": 2, "tail": None}}

        py_result = apply_projection(proj, input_val)
        mu_result = apply_mu(proj, input_val)

        # Python version preserves original structure
        assert py_result == {
            "first": 1,
            "rest": {"head": 2, "tail": None}
        }
        # Mu version denormalizes linked list to Python list
        assert mu_result == {
            "first": 1,
            "rest": [2]
        }


class TestApplyMuAdversarialEdgeCases:
    """Edge cases identified by adversary agent review."""

    def test_deeply_nested_structure(self):
        """Test with moderately deep nesting (within MAX_MU_DEPTH=200)."""
        # Build 50-level deep structure
        deep_value = "leaf"
        for _ in range(50):
            deep_value = {"nested": deep_value}

        proj = {
            "pattern": {"var": "x"},
            "body": {"wrapped": {"var": "x"}}
        }

        py_result = apply_projection(proj, deep_value)
        mu_result = apply_mu(proj, deep_value)

        assert py_result == mu_result == {"wrapped": deep_value}

    def test_empty_string_variable_name(self):
        """Variable name can be empty string (edge case)."""
        proj = {
            "pattern": {"var": ""},
            "body": {"result": {"var": ""}}
        }

        py_result = apply_projection(proj, "value")
        mu_result = apply_mu(proj, "value")

        assert py_result == mu_result == {"result": "value"}

    def test_unicode_variable_name(self):
        """Variable names can be unicode."""
        proj = {
            "pattern": {"var": "変数"},
            "body": {"結果": {"var": "変数"}}
        }

        py_result = apply_projection(proj, "データ")
        mu_result = apply_mu(proj, "データ")

        assert py_result == mu_result == {"結果": "データ"}

    def test_large_bindings_dict(self):
        """Many variables in pattern and body."""
        # Create pattern with 20 variables
        pattern = {f"key{i}": {"var": f"v{i}"} for i in range(20)}
        body = {f"result{i}": {"var": f"v{i}"} for i in range(20)}
        input_val = {f"key{i}": f"value{i}" for i in range(20)}
        expected = {f"result{i}": f"value{i}" for i in range(20)}

        proj = {"pattern": pattern, "body": body}

        py_result = apply_projection(proj, input_val)
        mu_result = apply_mu(proj, input_val)

        assert py_result == mu_result == expected

    def test_numeric_string_keys(self):
        """Dict keys that look like numbers."""
        proj = {
            "pattern": {"123": {"var": "x"}, "456": {"var": "y"}},
            "body": {"a": {"var": "x"}, "b": {"var": "y"}}
        }
        input_val = {"123": "first", "456": "second"}

        py_result = apply_projection(proj, input_val)
        mu_result = apply_mu(proj, input_val)

        assert py_result == mu_result == {"a": "first", "b": "second"}


class TestApplyMuErrors:
    """Test apply_mu error handling matches apply_projection."""

    def test_missing_pattern_key(self):
        """Projection missing pattern key."""
        proj = {"body": "result"}

        with pytest.raises(KeyError):
            apply_projection(proj, 42)

        with pytest.raises(KeyError):
            apply_mu(proj, 42)

    def test_missing_body_key(self):
        """Projection missing body key."""
        proj = {"pattern": {"var": "x"}}

        with pytest.raises(KeyError):
            apply_projection(proj, 42)

        with pytest.raises(KeyError):
            apply_mu(proj, 42)

    def test_non_dict_projection(self):
        """Projection is not a dict."""
        with pytest.raises(TypeError):
            apply_projection("not a dict", 42)

        with pytest.raises(TypeError):
            apply_mu("not a dict", 42)
