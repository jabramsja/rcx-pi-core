"""
Tests for EVAL_SEED v0.

Tests the core operations: match, substitute, apply, step.
See docs/EVAL_SEED.v0.md for specification.
"""

import pytest

from rcx_pi.eval_seed import (
    NO_MATCH,
    is_var,
    get_var_name,
    match,
    substitute,
    apply_projection,
    step,
    deep_step,
    create_step_handler,
    create_deep_step_handler,
    create_stall_handler,
    create_eval_seed,
    register_eval_seed,
    assert_not_lambda_calculus,
)
from rcx_pi.kernel import create_kernel


# =============================================================================
# is_var tests
# =============================================================================


class TestIsVar:
    """Tests for is_var()."""

    def test_var_site(self):
        """{"var": "x"} is a variable site."""
        assert is_var({"var": "x"}) is True

    def test_var_with_longer_name(self):
        """{"var": "foo_bar"} is a variable site."""
        assert is_var({"var": "foo_bar"}) is True

    def test_empty_dict_not_var(self):
        """{} is not a variable site."""
        assert is_var({}) is False

    def test_dict_with_other_key_not_var(self):
        """{"foo": "x"} is not a variable site."""
        assert is_var({"foo": "x"}) is False

    def test_dict_with_extra_keys_not_var(self):
        """{"var": "x", "extra": 1} is not a variable site."""
        assert is_var({"var": "x", "extra": 1}) is False

    def test_var_with_non_string_not_var(self):
        """{"var": 123} is not a variable site."""
        assert is_var({"var": 123}) is False

    def test_primitives_not_var(self):
        """Primitives are not variable sites."""
        assert is_var(None) is False
        assert is_var(True) is False
        assert is_var(42) is False
        assert is_var("x") is False
        assert is_var([]) is False


# =============================================================================
# match tests
# =============================================================================


class TestMatchPrimitives:
    """Tests for match() with primitive values."""

    def test_match_null(self):
        """null matches null."""
        assert match(None, None) == {}

    def test_match_null_not_other(self):
        """null doesn't match other types."""
        assert match(None, 0) is NO_MATCH
        assert match(None, False) is NO_MATCH
        assert match(None, "") is NO_MATCH

    def test_match_true(self):
        """true matches true."""
        assert match(True, True) == {}

    def test_match_false(self):
        """false matches false."""
        assert match(False, False) == {}

    def test_match_bool_not_cross(self):
        """true doesn't match false."""
        assert match(True, False) is NO_MATCH
        assert match(False, True) is NO_MATCH

    def test_match_bool_not_int(self):
        """true doesn't match 1, false doesn't match 0."""
        assert match(True, 1) is NO_MATCH
        assert match(False, 0) is NO_MATCH
        assert match(1, True) is NO_MATCH
        assert match(0, False) is NO_MATCH

    def test_match_int(self):
        """Integers match equal integers."""
        assert match(42, 42) == {}
        assert match(0, 0) == {}
        assert match(-1, -1) == {}

    def test_match_int_not_different(self):
        """Integers don't match different integers."""
        assert match(42, 43) is NO_MATCH

    def test_match_float(self):
        """Floats match equal floats."""
        assert match(3.14, 3.14) == {}

    def test_match_float_not_int(self):
        """Float 1.0 doesn't match int 1."""
        assert match(1.0, 1) is NO_MATCH
        assert match(1, 1.0) is NO_MATCH

    def test_match_string(self):
        """Strings match equal strings."""
        assert match("hello", "hello") == {}
        assert match("", "") == {}

    def test_match_string_not_different(self):
        """Strings don't match different strings."""
        assert match("hello", "world") is NO_MATCH


class TestMatchVar:
    """Tests for match() with variable sites."""

    def test_var_matches_null(self):
        """Variable matches null."""
        assert match({"var": "x"}, None) == {"x": None}

    def test_var_matches_bool(self):
        """Variable matches bool."""
        assert match({"var": "x"}, True) == {"x": True}

    def test_var_matches_int(self):
        """Variable matches int."""
        assert match({"var": "x"}, 42) == {"x": 42}

    def test_var_matches_string(self):
        """Variable matches string."""
        assert match({"var": "x"}, "hello") == {"x": "hello"}

    def test_var_matches_list(self):
        """Variable matches list."""
        assert match({"var": "x"}, [1, 2, 3]) == {"x": [1, 2, 3]}

    def test_var_matches_dict(self):
        """Variable matches dict."""
        assert match({"var": "x"}, {"a": 1}) == {"x": {"a": 1}}


class TestMatchList:
    """Tests for match() with lists."""

    def test_match_empty_list(self):
        """Empty list matches empty list."""
        assert match([], []) == {}

    def test_match_list_same_elements(self):
        """List matches list with same elements."""
        assert match([1, 2, 3], [1, 2, 3]) == {}

    def test_match_list_different_length(self):
        """Lists of different length don't match."""
        assert match([1], [1, 2]) is NO_MATCH
        assert match([1, 2], [1]) is NO_MATCH

    def test_match_list_different_elements(self):
        """Lists with different elements don't match."""
        assert match([1, 2], [1, 3]) is NO_MATCH

    def test_match_list_with_var(self):
        """List with variable matches and binds."""
        assert match([{"var": "x"}, 2], [1, 2]) == {"x": 1}

    def test_match_list_multiple_vars(self):
        """List with multiple variables matches and binds all."""
        assert match([{"var": "x"}, {"var": "y"}], [1, 2]) == {"x": 1, "y": 2}

    def test_match_list_nested(self):
        """Nested list matches."""
        assert match([[1, 2], [3]], [[1, 2], [3]]) == {}

    def test_match_list_nested_var(self):
        """Variable in nested list binds."""
        assert match([[{"var": "x"}]], [[42]]) == {"x": 42}


class TestMatchDict:
    """Tests for match() with dicts."""

    def test_match_empty_dict(self):
        """Empty dict matches empty dict."""
        assert match({}, {}) == {}

    def test_match_dict_same_keys(self):
        """Dict matches dict with same keys and values."""
        assert match({"a": 1, "b": 2}, {"a": 1, "b": 2}) == {}

    def test_match_dict_different_keys(self):
        """Dict doesn't match dict with different keys."""
        assert match({"a": 1}, {"b": 1}) is NO_MATCH

    def test_match_dict_extra_key(self):
        """Dict doesn't match dict with extra key."""
        assert match({"a": 1}, {"a": 1, "b": 2}) is NO_MATCH
        assert match({"a": 1, "b": 2}, {"a": 1}) is NO_MATCH

    def test_match_dict_different_value(self):
        """Dict doesn't match dict with different value."""
        assert match({"a": 1}, {"a": 2}) is NO_MATCH

    def test_match_dict_with_var(self):
        """Dict with variable value matches and binds."""
        assert match({"a": {"var": "x"}}, {"a": 42}) == {"x": 42}

    def test_match_dict_nested(self):
        """Nested dict matches."""
        assert match({"a": {"b": 1}}, {"a": {"b": 1}}) == {}

    def test_match_dict_nested_var(self):
        """Variable in nested dict binds."""
        assert match({"a": {"b": {"var": "x"}}}, {"a": {"b": 99}}) == {"x": 99}


class TestMatchSameVarTwice:
    """Tests for match() when same variable appears twice."""

    def test_same_var_same_value(self):
        """Same variable with same value succeeds."""
        result = match([{"var": "x"}, {"var": "x"}], [1, 1])
        assert result == {"x": 1}

    def test_same_var_different_value(self):
        """Same variable with different value fails."""
        result = match([{"var": "x"}, {"var": "x"}], [1, 2])
        assert result is NO_MATCH


# =============================================================================
# substitute tests
# =============================================================================


class TestSubstitute:
    """Tests for substitute()."""

    def test_sub_no_vars(self):
        """Value without vars unchanged."""
        assert substitute({"a": 1}, {}) == {"a": 1}

    def test_sub_primitive(self):
        """Primitives unchanged."""
        assert substitute(None, {}) is None
        assert substitute(True, {}) is True
        assert substitute(42, {}) == 42
        assert substitute("hello", {}) == "hello"

    def test_sub_single_var(self):
        """Single variable substituted."""
        assert substitute({"var": "x"}, {"x": 42}) == 42

    def test_sub_var_to_complex(self):
        """Variable can be substituted with complex value."""
        assert substitute({"var": "x"}, {"x": [1, 2, 3]}) == [1, 2, 3]

    def test_sub_nested_var(self):
        """Nested variable substituted."""
        assert substitute([1, {"var": "x"}], {"x": 2}) == [1, 2]

    def test_sub_multiple_vars(self):
        """Multiple variables substituted."""
        result = substitute(
            [{"var": "x"}, {"var": "y"}],
            {"x": 1, "y": 2}
        )
        assert result == [1, 2]

    def test_sub_dict_values(self):
        """Variables in dict values substituted."""
        result = substitute(
            {"a": {"var": "x"}, "b": {"var": "y"}},
            {"x": 1, "y": 2}
        )
        assert result == {"a": 1, "b": 2}

    def test_sub_unbound_raises(self):
        """Unbound variable raises KeyError."""
        with pytest.raises(KeyError) as exc_info:
            substitute({"var": "x"}, {})
        assert "x" in str(exc_info.value)


# =============================================================================
# apply_projection tests
# =============================================================================


class TestApplyProjection:
    """Tests for apply_projection()."""

    def test_apply_match(self):
        """Pattern matches, body returned."""
        proj = {"pattern": 1, "body": 2}
        assert apply_projection(proj, 1) == 2

    def test_apply_no_match(self):
        """Pattern doesn't match, NO_MATCH returned."""
        proj = {"pattern": 1, "body": 2}
        assert apply_projection(proj, 3) is NO_MATCH

    def test_apply_with_var(self):
        """Variable in pattern binds, substituted in body."""
        proj = {
            "pattern": {"var": "x"},
            "body": [{"var": "x"}, {"var": "x"}]
        }
        assert apply_projection(proj, 5) == [5, 5]

    def test_apply_complex(self):
        """Complex pattern with substitution."""
        proj = {
            "pattern": {"a": {"var": "x"}, "b": {"var": "y"}},
            "body": [{"var": "y"}, {"var": "x"}]
        }
        result = apply_projection(proj, {"a": 1, "b": 2})
        assert result == [2, 1]

    def test_apply_missing_pattern_key(self):
        """Missing pattern key raises."""
        with pytest.raises(KeyError):
            apply_projection({"body": 1}, 1)

    def test_apply_missing_body_key(self):
        """Missing body key raises."""
        with pytest.raises(KeyError):
            apply_projection({"pattern": 1}, 1)


# =============================================================================
# step tests
# =============================================================================


class TestStep:
    """Tests for step()."""

    def test_step_first_match(self):
        """First matching projection applied."""
        projections = [
            {"pattern": 1, "body": "one"},
            {"pattern": 2, "body": "two"},
        ]
        assert step(projections, 1) == "one"

    def test_step_second_match(self):
        """Second projection matches if first doesn't."""
        projections = [
            {"pattern": 1, "body": "one"},
            {"pattern": 2, "body": "two"},
        ]
        assert step(projections, 2) == "two"

    def test_step_no_match_returns_input(self):
        """No match returns input (stall)."""
        projections = [
            {"pattern": 1, "body": "one"},
        ]
        assert step(projections, 99) == 99

    def test_step_empty_projections(self):
        """Empty projections returns input (stall)."""
        assert step([], 42) == 42

    def test_step_first_match_wins(self):
        """First matching projection wins even if others match."""
        projections = [
            {"pattern": {"var": "x"}, "body": "first"},
            {"pattern": {"var": "y"}, "body": "second"},
        ]
        assert step(projections, 1) == "first"


# =============================================================================
# deep_step tests
# =============================================================================


class TestDeepStep:
    """Tests for deep_step() - recursive descent matching."""

    def test_deep_step_root_match(self):
        """deep_step matches at root just like step."""
        projections = [{"pattern": 1, "body": 2}]
        assert deep_step(projections, 1) == 2

    def test_deep_step_no_match_returns_input(self):
        """No match returns input unchanged."""
        projections = [{"pattern": 1, "body": 2}]
        assert deep_step(projections, 99) == 99

    def test_deep_step_nested_dict(self):
        """deep_step finds match inside nested dict."""
        projections = [{"pattern": {"op": "inc"}, "body": "found"}]
        nested = {"a": {"b": {"op": "inc"}}}
        result = deep_step(projections, nested)
        assert result == {"a": {"b": "found"}}

    def test_deep_step_nested_list(self):
        """deep_step finds match inside nested list."""
        projections = [{"pattern": {"op": "inc"}, "body": "found"}]
        nested = [1, [2, {"op": "inc"}, 3], 4]
        result = deep_step(projections, nested)
        assert result == [1, [2, "found", 3], 4]

    def test_deep_step_linked_list_append(self):
        """deep_step enables linked list append."""
        append_projections = [
            # Base: append(null, ys) = ys
            {
                "pattern": {"op": "append", "xs": None, "ys": {"var": "ys"}},
                "body": {"var": "ys"}
            },
            # Recursive: append({head:h, tail:t}, ys) = {head:h, tail:append(t, ys)}
            {
                "pattern": {
                    "op": "append",
                    "xs": {"head": {"var": "h"}, "tail": {"var": "t"}},
                    "ys": {"var": "ys"}
                },
                "body": {
                    "head": {"var": "h"},
                    "tail": {"op": "append", "xs": {"var": "t"}, "ys": {"var": "ys"}}
                }
            }
        ]

        # append([1], [2]) should become [1, 2]
        input_val = {
            "op": "append",
            "xs": {"head": 1, "tail": None},
            "ys": {"head": 2, "tail": None}
        }

        # Run until stall
        value = input_val
        for _ in range(10):
            next_val = deep_step(append_projections, value)
            if next_val == value:
                break
            value = next_val

        expected = {"head": 1, "tail": {"head": 2, "tail": None}}
        assert value == expected

    def test_deep_step_first_match_only(self):
        """deep_step reduces only the first matching sub-expression."""
        projections = [{"pattern": {"op": "x"}, "body": "replaced"}]
        # Two matches at same level - only first should be replaced
        nested = {"a": {"op": "x"}, "b": {"op": "x"}}
        result = deep_step(projections, nested)
        # Note: dict iteration order is preserved in Python 3.7+
        # First key 'a' should be processed first
        assert result == {"a": "replaced", "b": {"op": "x"}}


# =============================================================================
# Handler tests
# =============================================================================


class TestHandlers:
    """Tests for kernel handlers."""

    def test_step_handler(self):
        """step_handler extracts mu and applies projections."""
        projections = [{"pattern": 1, "body": 2}]
        handler = create_step_handler(projections)
        result = handler({"mu": 1, "hash": "abc"})
        assert result == 2

    def test_step_handler_stall(self):
        """step_handler returns mu if no match."""
        projections = [{"pattern": 1, "body": 2}]
        handler = create_step_handler(projections)
        result = handler({"mu": 99, "hash": "abc"})
        assert result == 99

    def test_deep_step_handler(self):
        """deep_step_handler extracts mu and applies projections deeply."""
        projections = [{"pattern": {"op": "inc"}, "body": "found"}]
        handler = create_deep_step_handler(projections)
        nested = {"mu": {"a": {"op": "inc"}}, "hash": "abc"}
        result = handler(nested)
        assert result == {"a": "found"}

    def test_deep_step_handler_stall(self):
        """deep_step_handler returns mu if no match anywhere."""
        projections = [{"pattern": {"op": "inc"}, "body": "found"}]
        handler = create_deep_step_handler(projections)
        result = handler({"mu": {"a": {"op": "dec"}}, "hash": "abc"})
        assert result == {"a": {"op": "dec"}}

    def test_stall_handler(self):
        """stall_handler returns stalled value."""
        handler = create_stall_handler()
        result = handler({"mu": 42, "trace": []})
        assert result == 42


# =============================================================================
# Integration tests
# =============================================================================


class TestKernelIntegration:
    """Integration tests with kernel."""

    def test_countdown_peano(self):
        """Countdown using Peano numerals."""
        # 0 = "zero", 1 = {"succ": "zero"}, 2 = {"succ": {"succ": "zero"}}
        projections = [
            # Base case: zero stalls (pattern = body)
            {"pattern": "zero", "body": "zero"},
            # Recursive case: unwrap succ
            {"pattern": {"succ": {"var": "n"}}, "body": {"var": "n"}},
        ]

        kernel = create_kernel()
        register_eval_seed(kernel, projections)

        # Start with 3 = {"succ": {"succ": {"succ": "zero"}}}
        three = {"succ": {"succ": {"succ": "zero"}}}
        final, trace, reason = kernel.run(three, max_steps=100)

        assert reason == "stall"
        assert final == "zero"
        assert len(trace) == 4  # 3 decrements + 1 stall

    def test_identity_projection(self):
        """Identity projection causes immediate stall."""
        projections = [
            {"pattern": {"var": "x"}, "body": {"var": "x"}}
        ]

        kernel = create_kernel()
        register_eval_seed(kernel, projections)

        final, trace, reason = kernel.run({"value": 42}, max_steps=100)

        assert reason == "stall"
        assert final == {"value": 42}
        assert len(trace) == 1

    def test_swap_pair(self):
        """Projection that swaps pair elements."""
        projections = [
            {
                "pattern": {"first": {"var": "a"}, "second": {"var": "b"}},
                "body": {"first": {"var": "b"}, "second": {"var": "a"}}
            }
        ]

        kernel = create_kernel()
        register_eval_seed(kernel, projections)

        # This will oscillate: {1,2} -> {2,1} -> {1,2} -> ...
        # Until max_steps
        final, trace, reason = kernel.run(
            {"first": 1, "second": 2},
            max_steps=10
        )

        assert reason == "max_steps"
        assert len(trace) == 10

    def test_list_head(self):
        """Extract head of list."""
        projections = [
            # Non-empty list: extract head
            {
                "pattern": [{"var": "head"}, {"var": "tail"}],
                "body": {"var": "head"}
            },
            # Anything else stalls
            {
                "pattern": {"var": "x"},
                "body": {"var": "x"}
            }
        ]

        kernel = create_kernel()
        register_eval_seed(kernel, projections)

        # [1, 2] matches the 2-element pattern, not the var
        # Wait, [1, 2] has 2 elements, pattern [head, tail] has 2 elements
        # So it matches: head=1, tail=2
        final, trace, reason = kernel.run([1, 2], max_steps=100)

        assert reason == "stall"
        assert final == 1


class TestPeanoArithmetic:
    """Tests for Peano numeral operations."""

    def test_is_zero(self):
        """Detect zero."""
        projections = [
            {"pattern": "zero", "body": True},
            {"pattern": {"succ": {"var": "n"}}, "body": False},
        ]

        # Test zero
        result = step(projections, "zero")
        assert result is True

        # Test non-zero
        result = step(projections, {"succ": "zero"})
        assert result is False

    def test_predecessor(self):
        """Get predecessor (n-1)."""
        projections = [
            {"pattern": "zero", "body": "zero"},  # pred(0) = 0
            {"pattern": {"succ": {"var": "n"}}, "body": {"var": "n"}},
        ]

        # pred(0) = 0
        assert step(projections, "zero") == "zero"

        # pred(1) = 0
        assert step(projections, {"succ": "zero"}) == "zero"

        # pred(2) = 1
        two = {"succ": {"succ": "zero"}}
        one = {"succ": "zero"}
        assert step(projections, two) == one


# =============================================================================
# NOT Lambda Calculus Tests
# =============================================================================


class TestNotLambdaCalculus:
    """Tests proving this is NOT lambda calculus."""

    def test_var_is_hole_not_binder(self):
        """{"var": "x"} is a hole marker, not a lambda binder."""
        # In lambda calc: λx.x is a function
        # Here: {"var": "x"} is just a marker that gets filled in
        proj = {"pattern": {"var": "x"}, "body": {"var": "x"}}
        result = apply_projection(proj, 42)
        # Result is 42, not a "function that returns its argument"
        assert result == 42
        assert not callable(result)

    def test_no_closures(self):
        """Variables don't capture environment (no closures)."""
        # In lambda calc: (λx.λy.x)(1)(2) = 1 (x captured)
        # Here: each projection is independent, no captured state
        proj1 = {"pattern": {"var": "x"}, "body": {"captured": {"var": "x"}}}
        result1 = apply_projection(proj1, "outer")
        assert result1 == {"captured": "outer"}

        # Second projection doesn't see "outer"
        proj2 = {"pattern": {"var": "y"}, "body": {"var": "y"}}
        result2 = apply_projection(proj2, "inner")
        assert result2 == "inner"
        # No way for result2 to access "outer"

    def test_no_self_application(self):
        """Can't apply a projection to itself (no (x x))."""
        # In lambda calc: (λx.x x)(λx.x x) is infinite loop
        # Here: projections are DATA, not functions to be called

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
        """Can't match on projection structures (first-order only)."""
        # A pattern that tries to match {"pattern": ..., "body": ...}
        # with specific structure (not just variables) is suspicious
        suspicious_proj = {
            "pattern": {"pattern": 1, "body": {"var": "b"}},  # Matching projection structure!
            "body": {"var": "b"}
        }

        with pytest.raises(ValueError) as exc_info:
            apply_projection(suspicious_proj, {"pattern": 1, "body": 2})
        assert "lambda calculus" in str(exc_info.value).lower()

    def test_matching_any_dict_is_ok(self):
        """Matching any dict with all-variable values is OK."""
        # This is NOT higher-order because it's not specific to projection structure
        proj = {
            "pattern": {"pattern": {"var": "p"}, "body": {"var": "b"}},
            "body": [{"var": "p"}, {"var": "b"}]
        }
        # This should work - it's just matching a dict with those keys
        result = apply_projection(proj, {"pattern": "x", "body": "y"})
        assert result == ["x", "y"]

    def test_y_combinator_impossible(self):
        """Y combinator cannot be expressed (no self-referential evaluation)."""
        # Y = λf.(λx.f(x x))(λx.f(x x))
        # This requires:
        # 1. Functions as first-class values (we have projections as data, but can't "call" them)
        # 2. Self-application (x x) - impossible, projections aren't callable
        # 3. Delayed evaluation - we don't have this

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
        """Substitution happens immediately, no delayed evaluation."""
        # In lazy lambda calc: (λx.expensive)(unused) doesn't eval expensive
        # Here: substitution happens when projection is applied

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


class TestGuardrailFunction:
    """Tests for assert_not_lambda_calculus guardrail."""

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
