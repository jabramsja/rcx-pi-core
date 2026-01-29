"""
Lambda Calculus Guardrail Tests - NORTH STAR Invariant Enforcement

These tests prove that RCX is NOT lambda calculus. They enforce the invariant:
"Lambda calculus MUST NOT emerge - no closures, no self-application"

Migrated from test_eval_seed_v0.py during kernel.py cleanup (2026-01-29).
These tests are CRITICAL for security - they prevent higher-order pattern
matching that could enable lambda calculus smuggling.

See docs/core/StructuralPurity.v0.md for the security rationale.
"""

import pytest

from rcx_pi.eval_seed import (
    apply_projection,
    assert_not_lambda_calculus,
)


# =============================================================================
# NOT Lambda Calculus Tests
# =============================================================================


class TestNotLambdaCalculus:
    """Tests proving this is NOT lambda calculus.

    These tests verify the NORTH STAR invariant:
    "Lambda calculus MUST NOT emerge - no closures, no self-application"
    """

    def test_var_is_hole_not_binder(self):
        """{"var": "x"} is a hole marker, not a lambda binder.

        In lambda calc: λx.x is a function
        Here: {"var": "x"} is just a marker that gets filled in
        """
        proj = {"pattern": {"var": "x"}, "body": {"var": "x"}}
        result = apply_projection(proj, 42)
        # Result is 42, not a "function that returns its argument"
        assert result == 42
        assert not callable(result)

    def test_no_closures(self):
        """Variables don't capture environment (no closures).

        In lambda calc: (λx.λy.x)(1)(2) = 1 (x captured)
        Here: each projection is independent, no captured state
        """
        proj1 = {"pattern": {"var": "x"}, "body": {"captured": {"var": "x"}}}
        result1 = apply_projection(proj1, "outer")
        assert result1 == {"captured": "outer"}

        # Second projection doesn't see "outer"
        proj2 = {"pattern": {"var": "y"}, "body": {"var": "y"}}
        result2 = apply_projection(proj2, "inner")
        assert result2 == "inner"
        # No way for result2 to access "outer"

    def test_no_self_application(self):
        """Can't apply a projection to itself (no (x x)).

        In lambda calc: (λx.x x)(λx.x x) is infinite loop
        Here: projections are DATA, not functions to be called
        """
        # A projection that "looks like" it references itself
        proj = {
            "pattern": {"var": "f"},
            "body": {"var": "f"}  # Just returns the input
        }

        # When we apply it to a "projection-like" structure, we just get that structure back
        # We don't "execute" it
        fake_proj = {"pattern": 1, "body": 2}
        result = apply_projection(proj, fake_proj)
        assert result == fake_proj  # It's just data, not executed

    def test_no_higher_order_matching(self):
        """Can't match on projection structures (first-order only).

        A pattern that tries to match {"pattern": ..., "body": ...}
        with specific structure (not just variables) is suspicious.
        """
        suspicious_proj = {
            "pattern": {"pattern": 1, "body": {"var": "b"}},  # Matching projection structure!
            "body": {"var": "b"}
        }

        with pytest.raises(ValueError) as exc_info:
            apply_projection(suspicious_proj, {"pattern": 1, "body": 2})
        assert "lambda calculus" in str(exc_info.value).lower()

    def test_matching_any_dict_is_ok(self):
        """Matching any dict with all-variable values is OK.

        This is NOT higher-order because it's not specific to projection structure.
        """
        proj = {
            "pattern": {"pattern": {"var": "p"}, "body": {"var": "b"}},
            "body": [{"var": "p"}, {"var": "b"}]
        }
        # This should work - it's just matching a dict with those keys
        result = apply_projection(proj, {"pattern": "x", "body": "y"})
        assert result == ["x", "y"]

    def test_y_combinator_impossible(self):
        """Y combinator cannot be expressed (no self-referential evaluation).

        Y = λf.(λx.f(x x))(λx.f(x x))
        This requires:
        1. Functions as first-class values (we have projections as data, but can't "call" them)
        2. Self-application (x x) - impossible, projections aren't callable
        3. Delayed evaluation - we don't have this
        """
        # Attempt to express something Y-like:
        # "A projection that takes a projection and applies it to itself"
        # This CANNOT work because:

        # 1. We can match a projection-like structure
        proj_matcher = {
            "pattern": {"var": "f"},  # Match anything
            "body": {"var": "f"}       # Return it (can't "call" it)
        }

        # 2. The result is just data, not a "function call"
        some_proj = {"pattern": "a", "body": "b"}
        result = apply_projection(proj_matcher, some_proj)

        # Result is just the projection as data, not "executed"
        assert result == some_proj
        assert result == {"pattern": "a", "body": "b"}

        # There's no way to "execute" result - it's inert data
        # In lambda calc, we could do (result arg), but here we can't

    def test_substitution_is_immediate(self):
        """Substitution happens immediately, no delayed evaluation.

        In lazy lambda calc: (λx.expensive)(unused) doesn't eval expensive
        Here: substitution happens when projection is applied
        """
        proj = {
            "pattern": {"var": "x"},
            "body": [{"var": "x"}, {"var": "x"}, {"var": "x"}]
        }

        # The value is copied 3 times immediately
        big_value = {"data": [1, 2, 3, 4, 5]}
        result = apply_projection(proj, big_value)

        # All three copies are the same (no "thunks" or delayed computation)
        assert result == [big_value, big_value, big_value]
        assert result[0] == result[1] == result[2]


# =============================================================================
# Guardrail Function Tests
# =============================================================================


class TestGuardrailFunction:
    """Tests for assert_not_lambda_calculus guardrail.

    This guardrail is the enforcement mechanism for the "no lambda calculus"
    invariant. It rejects patterns that could enable higher-order matching.
    """

    def test_normal_projection_ok(self):
        """Normal projections pass guardrail."""
        proj = {"pattern": {"var": "x"}, "body": {"var": "x"}}
        assert_not_lambda_calculus(proj)  # Should not raise

    def test_non_dict_ok(self):
        """Non-dict values pass guardrail."""
        assert_not_lambda_calculus(42)  # Should not raise
        assert_not_lambda_calculus("string")
        assert_not_lambda_calculus([1, 2, 3])

    def test_dict_without_pattern_body_ok(self):
        """Dicts without pattern/body pass guardrail."""
        assert_not_lambda_calculus({"a": 1, "b": 2})  # Should not raise

    def test_higher_order_pattern_rejected(self):
        """Higher-order patterns (matching projections) are rejected."""
        suspicious = {
            "pattern": {"pattern": "literal", "body": {"var": "b"}},
            "body": {"var": "b"}
        }
        with pytest.raises(ValueError):
            assert_not_lambda_calculus(suspicious)
