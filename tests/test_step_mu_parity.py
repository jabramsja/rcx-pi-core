"""
Phase 5: step_mu parity tests

Verifies step_mu() produces identical results to step() for all cases.
This is the foundation for self-hosting - if step_mu == step, then
Mu projections can replace Python functions.

See docs/core/SelfHosting.v0.md for design.
"""

import pytest

from rcx_pi.eval_seed import step, apply_projection, NO_MATCH
from rcx_pi.step_mu import step_mu, apply_mu


class TestApplyMuParityWithApplyProjection:
    """Verify apply_mu matches apply_projection."""

    def test_literal_match(self):
        """Literal pattern matches literal value."""
        proj = {"pattern": 42, "body": "matched"}

        py_result = apply_projection(proj, 42)
        mu_result = apply_mu(proj, 42)

        assert py_result == mu_result == "matched"

    def test_literal_no_match(self):
        """Literal pattern doesn't match different value."""
        proj = {"pattern": 42, "body": "matched"}

        py_result = apply_projection(proj, 99)
        mu_result = apply_mu(proj, 99)

        assert py_result is NO_MATCH
        assert mu_result is NO_MATCH

    def test_variable_binding(self):
        """Variable pattern captures value."""
        proj = {"pattern": {"var": "x"}, "body": {"result": {"var": "x"}}}

        py_result = apply_projection(proj, 42)
        mu_result = apply_mu(proj, 42)

        assert py_result == mu_result == {"result": 42}

    def test_nested_pattern(self):
        """Nested pattern with multiple variables."""
        proj = {
            "pattern": {"a": {"var": "x"}, "b": {"var": "y"}},
            "body": {"first": {"var": "x"}, "second": {"var": "y"}}
        }
        value = {"a": 1, "b": 2}

        py_result = apply_projection(proj, value)
        mu_result = apply_mu(proj, value)

        assert py_result == mu_result == {"first": 1, "second": 2}

    def test_list_pattern(self):
        """List pattern captures elements."""
        proj = {
            "pattern": [{"var": "head"}, {"var": "tail"}],
            "body": {"h": {"var": "head"}, "t": {"var": "tail"}}
        }
        value = [1, 2]

        py_result = apply_projection(proj, value)
        mu_result = apply_mu(proj, value)

        assert py_result == mu_result == {"h": 1, "t": 2}


class TestStepMuParityWithStep:
    """Verify step_mu matches step for projection selection."""

    def test_first_projection_matches(self):
        """First projection matches, should apply it."""
        projections = [
            {"pattern": 42, "body": "first"},
            {"pattern": {"var": "x"}, "body": "second"}
        ]

        py_result = step(projections, 42)
        mu_result = step_mu(projections, 42)

        assert py_result == mu_result == "first"

    def test_second_projection_matches(self):
        """First doesn't match, second does."""
        projections = [
            {"pattern": 99, "body": "first"},
            {"pattern": {"var": "x"}, "body": "second"}
        ]

        py_result = step(projections, 42)
        mu_result = step_mu(projections, 42)

        assert py_result == mu_result == "second"

    def test_no_projection_matches(self):
        """None match, returns input (stall)."""
        projections = [
            {"pattern": 99, "body": "first"},
            {"pattern": 100, "body": "second"}
        ]

        py_result = step(projections, 42)
        mu_result = step_mu(projections, 42)

        # Stall: return input unchanged
        assert py_result == mu_result == 42

    def test_empty_projections(self):
        """Empty projections list returns input (stall)."""
        projections = []

        py_result = step(projections, 42)
        mu_result = step_mu(projections, 42)

        assert py_result == mu_result == 42

    def test_variable_substitution(self):
        """Variable captured and substituted correctly."""
        projections = [
            {"pattern": {"op": "inc", "val": {"var": "n"}},
             "body": {"op": "result", "val": {"var": "n"}}}
        ]
        value = {"op": "inc", "val": 5}

        py_result = step(projections, value)
        mu_result = step_mu(projections, value)

        assert py_result == mu_result == {"op": "result", "val": 5}


class TestStepMuComplexCases:
    """Complex cases for step_mu parity."""

    def test_peano_successor(self):
        """Peano numeral successor pattern."""
        projections = [
            # succ(zero) -> one
            {"pattern": {"succ": "zero"}, "body": "one"},
            # succ(n) -> succ(succ(n)) for any n
            {"pattern": {"succ": {"var": "n"}}, "body": {"double_succ": {"var": "n"}}}
        ]

        # Test succ(zero)
        py1 = step(projections, {"succ": "zero"})
        mu1 = step_mu(projections, {"succ": "zero"})
        assert py1 == mu1 == "one"

        # Test succ(one)
        py2 = step(projections, {"succ": "one"})
        mu2 = step_mu(projections, {"succ": "one"})
        assert py2 == mu2 == {"double_succ": "one"}

    def test_nested_dict_pattern(self):
        """Deeply nested dict pattern."""
        projections = [
            {
                "pattern": {"level1": {"level2": {"level3": {"var": "x"}}}},
                "body": {"extracted": {"var": "x"}}
            }
        ]
        value = {"level1": {"level2": {"level3": "deep_value"}}}

        py_result = step(projections, value)
        mu_result = step_mu(projections, value)

        assert py_result == mu_result == {"extracted": "deep_value"}

    def test_multiple_vars_same_level(self):
        """Multiple variables at same level."""
        projections = [
            {
                "pattern": {"a": {"var": "x"}, "b": {"var": "y"}, "c": {"var": "z"}},
                "body": {"sum": [{"var": "x"}, {"var": "y"}, {"var": "z"}]}
            }
        ]
        value = {"a": 1, "b": 2, "c": 3}

        py_result = step(projections, value)
        mu_result = step_mu(projections, value)

        assert py_result == mu_result == {"sum": [1, 2, 3]}

    def test_projection_order_matters(self):
        """First matching projection wins."""
        projections = [
            {"pattern": {"var": "x"}, "body": "catch_all"},
            {"pattern": 42, "body": "specific"}  # Never reached
        ]

        py_result = step(projections, 42)
        mu_result = step_mu(projections, 42)

        # First projection (catch-all) wins
        assert py_result == mu_result == "catch_all"


class TestStepMuEdgeCases:
    """Edge cases for step_mu."""

    def test_null_value(self):
        """Null value handling."""
        projections = [
            {"pattern": None, "body": "was_null"},
            {"pattern": {"var": "x"}, "body": "was_something"}
        ]

        py_result = step(projections, None)
        mu_result = step_mu(projections, None)

        assert py_result == mu_result == "was_null"

    def test_boolean_values(self):
        """Boolean value handling."""
        projections = [
            {"pattern": True, "body": "was_true"},
            {"pattern": False, "body": "was_false"}
        ]

        py_true = step(projections, True)
        mu_true = step_mu(projections, True)
        assert py_true == mu_true == "was_true"

        py_false = step(projections, False)
        mu_false = step_mu(projections, False)
        assert py_false == mu_false == "was_false"

    def test_string_values(self):
        """String value handling."""
        projections = [
            {"pattern": "hello", "body": "matched_hello"},
            {"pattern": {"var": "s"}, "body": {"echoed": {"var": "s"}}}
        ]

        py1 = step(projections, "hello")
        mu1 = step_mu(projections, "hello")
        assert py1 == mu1 == "matched_hello"

        py2 = step(projections, "world")
        mu2 = step_mu(projections, "world")
        assert py2 == mu2 == {"echoed": "world"}

    def test_numeric_values(self):
        """Numeric value handling (int and float)."""
        projections = [
            {"pattern": 42, "body": "int_42"},
            {"pattern": 3.14, "body": "pi"},
            {"pattern": {"var": "n"}, "body": {"number": {"var": "n"}}}
        ]

        assert step(projections, 42) == step_mu(projections, 42) == "int_42"
        assert step(projections, 3.14) == step_mu(projections, 3.14) == "pi"
        assert step(projections, 99) == step_mu(projections, 99) == {"number": 99}


class TestStepMuErrors:
    """Error handling parity."""

    def test_invalid_projection_type(self):
        """Non-dict projection raises TypeError."""
        projections = ["not_a_dict"]

        with pytest.raises(TypeError):
            step(projections, 42)

        with pytest.raises(TypeError):
            step_mu(projections, 42)

    def test_missing_pattern_key(self):
        """Missing pattern key raises KeyError."""
        projections = [{"body": "no_pattern"}]

        with pytest.raises(KeyError):
            step(projections, 42)

        with pytest.raises(KeyError):
            step_mu(projections, 42)

    def test_missing_body_key(self):
        """Missing body key raises KeyError."""
        projections = [{"pattern": 42}]

        with pytest.raises(KeyError):
            step(projections, 42)

        with pytest.raises(KeyError):
            step_mu(projections, 42)

    def test_unbound_variable(self):
        """Unbound variable in body: step raises KeyError, step_mu stalls.

        Phase 7d behavioral difference: The structural kernel (step_mu) treats
        unbound variables as a stall condition rather than an error. This is
        more consistent with pure Mu semantics where errors become stalls.

        - step(): Raises KeyError (Python error handling)
        - step_mu(): Returns original input (stall - structural behavior)
        """
        projections = [
            {"pattern": 42, "body": {"result": {"var": "unbound"}}}
        ]

        # Python step still raises KeyError
        with pytest.raises(KeyError):
            step(projections, 42)

        # Structural step_mu stalls instead of raising
        result = step_mu(projections, 42)
        assert result == 42  # Returns original input (stall)
