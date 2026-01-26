"""
Tests for Mu Type validation.

A Mu is a JSON-compatible value: the portable, host-independent data type
for all RCX values. These tests ensure the validation functions correctly
identify valid and invalid Mu values.

See docs/core/MuType.v0.md for the specification.
"""

import json
import math
import pytest

from rcx_pi.mu_type import (
    is_mu, validate_mu, assert_mu, mu_type_name,
    has_callable, find_callable_path, assert_no_callables,
    assert_seed_pure, assert_handler_pure, validate_kernel_boundary,
    mu_equal, mu_hash, mark_bootstrap, get_bootstrap_registry,
    assert_no_bootstrap_in_production, BOOTSTRAP_REGISTRY
)


class TestIsMu:
    """Tests for is_mu() function."""

    # --- Valid Mu values ---
    def test_none_is_mu(self):
        """None (JSON null) is a valid Mu."""
        assert is_mu(None) is True

    def test_bool_true_is_mu(self):
        """True is a valid Mu."""
        assert is_mu(True) is True

    def test_bool_false_is_mu(self):
        """False is a valid Mu."""
        assert is_mu(False) is True

    def test_int_positive_is_mu(self):
        """Positive integers are valid Mu."""
        assert is_mu(42) is True

    def test_int_negative_is_mu(self):
        """Negative integers are valid Mu."""
        assert is_mu(-1) is True

    def test_int_zero_is_mu(self):
        """Zero is a valid Mu."""
        assert is_mu(0) is True

    def test_int_large_is_mu(self):
        """Large integers are valid Mu."""
        assert is_mu(10**100) is True

    def test_float_positive_is_mu(self):
        """Positive floats are valid Mu."""
        assert is_mu(3.14) is True

    def test_float_negative_is_mu(self):
        """Negative floats are valid Mu."""
        assert is_mu(-0.5) is True

    def test_float_zero_is_mu(self):
        """0.0 is a valid Mu."""
        assert is_mu(0.0) is True

    def test_str_nonempty_is_mu(self):
        """Non-empty strings are valid Mu."""
        assert is_mu("hello") is True

    def test_str_empty_is_mu(self):
        """Empty string is a valid Mu."""
        assert is_mu("") is True

    def test_str_unicode_is_mu(self):
        """Unicode strings are valid Mu."""
        assert is_mu("hello \u4e16\u754c") is True

    def test_list_empty_is_mu(self):
        """Empty list is a valid Mu."""
        assert is_mu([]) is True

    def test_list_of_primitives_is_mu(self):
        """List of primitives is a valid Mu."""
        assert is_mu([1, 2, 3]) is True

    def test_list_mixed_types_is_mu(self):
        """List with mixed valid types is a valid Mu."""
        assert is_mu([1, "hello", True, None, 3.14]) is True

    def test_dict_empty_is_mu(self):
        """Empty dict is a valid Mu."""
        assert is_mu({}) is True

    def test_dict_str_keys_is_mu(self):
        """Dict with string keys and valid values is a valid Mu."""
        assert is_mu({"a": 1, "b": 2}) is True

    def test_nested_structure_is_mu(self):
        """Nested structures are valid Mu."""
        assert is_mu({"x": [1, {"y": 2}]}) is True

    def test_deeply_nested_is_mu(self):
        """Deeply nested structures are valid Mu."""
        value = {"a": [{"b": [{"c": 1}]}]}
        assert is_mu(value) is True

    # --- Invalid Mu values ---
    def test_float_nan_not_mu(self):
        """NaN is not a valid Mu (not JSON-compatible)."""
        assert is_mu(float('nan')) is False

    def test_float_inf_not_mu(self):
        """Infinity is not a valid Mu (not JSON-compatible)."""
        assert is_mu(float('inf')) is False

    def test_float_neg_inf_not_mu(self):
        """Negative infinity is not a valid Mu (not JSON-compatible)."""
        assert is_mu(float('-inf')) is False

    def test_function_not_mu(self):
        """Functions are not valid Mu."""
        assert is_mu(lambda x: x) is False

    def test_class_not_mu(self):
        """Classes are not valid Mu."""
        class Foo:
            pass
        assert is_mu(Foo) is False

    def test_object_not_mu(self):
        """Arbitrary objects are not valid Mu."""
        class Foo:
            pass
        assert is_mu(Foo()) is False

    def test_bytes_not_mu(self):
        """Bytes are not valid Mu."""
        assert is_mu(b"hello") is False

    def test_set_not_mu(self):
        """Sets are not valid Mu."""
        assert is_mu({1, 2, 3}) is False

    def test_tuple_not_mu(self):
        """Tuples are not valid Mu (JSON has arrays, not tuples)."""
        assert is_mu((1, 2)) is False

    def test_complex_not_mu(self):
        """Complex numbers are not valid Mu."""
        assert is_mu(3+4j) is False

    def test_dict_with_int_key_not_mu(self):
        """Dict with non-string keys is not a valid Mu."""
        assert is_mu({1: "a"}) is False

    def test_list_containing_invalid_not_mu(self):
        """List containing invalid type is not a valid Mu."""
        assert is_mu([1, 2, lambda x: x]) is False

    def test_dict_containing_invalid_not_mu(self):
        """Dict containing invalid value is not a valid Mu."""
        assert is_mu({"a": lambda x: x}) is False

    # --- Circular reference detection ---
    def test_circular_list_not_mu(self):
        """Circular list reference is not a valid Mu (prevents stack overflow)."""
        circular_list = [1, 2]
        circular_list.append(circular_list)  # Creates cycle
        assert is_mu(circular_list) is False

    def test_circular_dict_not_mu(self):
        """Circular dict reference is not a valid Mu (prevents stack overflow)."""
        circular_dict = {"a": 1}
        circular_dict["self"] = circular_dict  # Creates cycle
        assert is_mu(circular_dict) is False

    def test_deeply_nested_circular_not_mu(self):
        """Deeply nested circular reference is detected."""
        inner = {"value": 1}
        middle = {"inner": inner}
        outer = {"middle": middle}
        inner["parent"] = outer  # Creates cycle: outer -> middle -> inner -> outer
        assert is_mu(outer) is False

    def test_mutual_circular_not_mu(self):
        """Mutually circular structures are detected."""
        a = {"name": "a"}
        b = {"name": "b"}
        a["other"] = b
        b["other"] = a  # a -> b -> a cycle
        assert is_mu(a) is False
        assert is_mu(b) is False


class TestValidateMu:
    """Tests for validate_mu() - JSON round-trip validation."""

    def test_simple_values_roundtrip(self):
        """Simple values pass round-trip validation."""
        assert validate_mu(None) is True
        assert validate_mu(True) is True
        assert validate_mu(42) is True
        assert validate_mu(3.14) is True
        assert validate_mu("hello") is True

    def test_nested_structure_roundtrip(self):
        """Nested structures pass round-trip validation."""
        value = {"x": [1, {"y": [2, 3]}], "z": None}
        assert validate_mu(value) is True

    def test_invalid_type_fails_roundtrip(self):
        """Invalid types fail round-trip validation."""
        assert validate_mu(lambda x: x) is False
        assert validate_mu(b"bytes") is False

    def test_nan_fails_roundtrip(self):
        """NaN fails round-trip (JSON.dumps raises)."""
        assert validate_mu(float('nan')) is False

    def test_infinity_fails_roundtrip(self):
        """Infinity fails round-trip (JSON.dumps raises)."""
        assert validate_mu(float('inf')) is False


class TestAssertMu:
    """Tests for assert_mu() - raises TypeError on invalid."""

    def test_valid_mu_no_raise(self):
        """Valid Mu values don't raise."""
        assert_mu(42)
        assert_mu([1, 2, 3])
        assert_mu({"a": 1})

    def test_invalid_mu_raises_typeerror(self):
        """Invalid Mu raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            assert_mu(lambda x: x)
        assert "Mu" in str(exc_info.value)
        assert "JSON-compatible" in str(exc_info.value)

    def test_context_in_error_message(self):
        """Context string appears in error message."""
        with pytest.raises(TypeError) as exc_info:
            assert_mu(b"bytes", context="R0 register")
        assert "R0 register" in str(exc_info.value)


class TestMuTypeName:
    """Tests for mu_type_name() helper."""

    def test_null_type_name(self):
        assert mu_type_name(None) == "null"

    def test_bool_type_name(self):
        assert mu_type_name(True) == "bool"
        assert mu_type_name(False) == "bool"

    def test_int_type_name(self):
        assert mu_type_name(42) == "int"

    def test_float_type_name(self):
        assert mu_type_name(3.14) == "float"

    def test_str_type_name(self):
        assert mu_type_name("hello") == "str"

    def test_list_type_name(self):
        assert mu_type_name([1, 2, 3]) == "list"

    def test_dict_type_name(self):
        assert mu_type_name({"a": 1}) == "dict"

    def test_invalid_type_name(self):
        assert mu_type_name(lambda x: x) == "INVALID"
        assert mu_type_name(b"bytes") == "INVALID"


class TestBoolIntDistinction:
    """Tests for bool/int distinction (bool is subclass of int in Python)."""

    def test_bool_is_mu_not_int(self):
        """Bools should be recognized as bool, not int."""
        # True is int in Python (isinstance(True, int) is True)
        # But Mu type should distinguish them
        assert mu_type_name(True) == "bool"
        assert mu_type_name(1) == "int"

    def test_bool_roundtrips_as_bool(self):
        """Bools roundtrip through JSON as bools."""
        assert json.loads(json.dumps(True)) is True
        assert json.loads(json.dumps(False)) is False


class TestRuleMotifCompatibility:
    """Tests that rule motif structures are valid Mu."""

    def test_variable_site_is_mu(self):
        """Variable site {"var": "<name>"} is a valid Mu."""
        assert is_mu({"var": "x"}) is True
        assert is_mu({"var": "my_variable"}) is True

    def test_simple_rule_motif_is_mu(self):
        """Simple rule motif structure is a valid Mu."""
        rule = {
            "rule": {
                "id": "add.zero",
                "pattern": {"add": [{"var": "x"}, 0]},
                "body": {"var": "x"}
            }
        }
        assert is_mu(rule) is True

    def test_rule_with_constants_is_mu(self):
        """Rule motif with constants is a valid Mu."""
        rule = {
            "rule": {
                "id": "const.example",
                "pattern": {"op": [{"var": "a"}, {"var": "b"}]},
                "body": {"result": [1, 2, 3, True, None]}
            }
        }
        assert is_mu(rule) is True


class TestTracePayloadCompatibility:
    """Tests that trace mu payloads are valid Mu."""

    def test_simple_mu_payload(self):
        """Simple mu payloads are valid Mu."""
        payload = {"foo": "bar", "count": 42}
        assert is_mu(payload) is True

    def test_nested_mu_payload(self):
        """Nested mu payloads are valid Mu."""
        payload = {"step": {"value": [1, 2, {"nested": True}]}}
        assert is_mu(payload) is True

    def test_execution_stall_payload(self):
        """Execution stall mu payload is valid Mu."""
        payload = {
            "execution": {
                "stall": {
                    "value_hash": "abc123",
                    "pattern_id": "test.pattern"
                }
            }
        }
        assert is_mu(payload) is True


# =============================================================================
# Structural Purity Guardrail Tests
# =============================================================================
# These tests ensure we program IN RCX (using Mu) rather than ABOUT RCX.
# See docs/core/StructuralPurity.v0.md for rationale.
# =============================================================================


class TestHasCallable:
    """Tests for has_callable() - detects functions/lambdas in structures."""

    def test_lambda_detected(self):
        """Lambda is detected as callable."""
        assert has_callable(lambda x: x) is True

    def test_function_detected(self):
        """Function is detected as callable."""
        def my_func():
            pass
        assert has_callable(my_func) is True

    def test_builtin_detected(self):
        """Built-in function is detected as callable."""
        assert has_callable(len) is True

    def test_lambda_in_dict_detected(self):
        """Lambda nested in dict is detected."""
        value = {"handler": lambda x: x}
        assert has_callable(value) is True

    def test_lambda_in_list_detected(self):
        """Lambda nested in list is detected."""
        value = [1, 2, lambda x: x]
        assert has_callable(value) is True

    def test_deeply_nested_callable_detected(self):
        """Callable deeply nested is detected."""
        value = {"a": [{"b": {"c": lambda x: x}}]}
        assert has_callable(value) is True

    def test_pure_mu_no_callable(self):
        """Pure Mu has no callable."""
        assert has_callable(42) is False
        assert has_callable("hello") is False
        assert has_callable([1, 2, 3]) is False
        assert has_callable({"a": 1}) is False
        assert has_callable({"a": [1, {"b": 2}]}) is False

    def test_circular_list_no_callable(self):
        """Circular list without callable handled safely (no stack overflow)."""
        circular_list = [1, 2]
        circular_list.append(circular_list)  # Creates cycle
        assert has_callable(circular_list) is False

    def test_circular_dict_no_callable(self):
        """Circular dict without callable handled safely (no stack overflow)."""
        circular_dict = {"a": 1}
        circular_dict["self"] = circular_dict  # Creates cycle
        assert has_callable(circular_dict) is False


class TestFindCallablePath:
    """Tests for find_callable_path() - locates callables for error messages."""

    def test_root_callable_path(self):
        """Root-level callable returns '(root)'."""
        path = find_callable_path(lambda x: x)
        assert path == "(root)"

    def test_dict_callable_path(self):
        """Callable in dict returns key path."""
        path = find_callable_path({"handler": lambda x: x})
        assert path == "handler"

    def test_nested_dict_path(self):
        """Nested callable returns full path."""
        path = find_callable_path({"config": {"handler": lambda x: x}})
        assert path == "config.handler"

    def test_list_callable_path(self):
        """Callable in list returns index path."""
        path = find_callable_path([1, 2, lambda x: x])
        assert path == "[2]"

    def test_complex_path(self):
        """Complex nesting returns full path."""
        path = find_callable_path({"items": [{"fn": lambda x: x}]})
        assert path == "items[0].fn"

    def test_no_callable_returns_none(self):
        """No callable returns None."""
        assert find_callable_path({"a": 1}) is None
        assert find_callable_path([1, 2, 3]) is None


class TestAssertNoCallables:
    """Tests for assert_no_callables() - fail-loud on host contamination."""

    def test_pure_mu_passes(self):
        """Pure Mu passes without raising."""
        assert_no_callables({"a": [1, 2, {"b": 3}]})  # Should not raise

    def test_lambda_raises(self):
        """Lambda raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            assert_no_callables({"handler": lambda x: x}, context="seed")
        assert "seed" in str(exc_info.value)
        assert "handler" in str(exc_info.value)
        assert "callable" in str(exc_info.value)

    def test_function_raises(self):
        """Function reference raises TypeError."""
        def my_func():
            pass
        with pytest.raises(TypeError) as exc_info:
            assert_no_callables(my_func)
        assert "callable" in str(exc_info.value)


class TestAssertSeedPure:
    """Tests for assert_seed_pure() - comprehensive seed validation."""

    def test_valid_seed_passes(self):
        """Valid pure Mu seed passes."""
        seed = {
            "seed": {
                "id": "test.v1",
                "projections": [
                    {"pattern": {"add": [1, 0]}, "body": 1},
                    {"pattern": {"add": [0, 1]}, "body": 1}
                ],
                "config": {"acyclic": True}
            }
        }
        assert_seed_pure(seed)  # Should not raise

    def test_simple_seed_passes(self):
        """Minimal seed structure passes."""
        seed = {"id": "minimal", "projections": []}
        assert_seed_pure(seed)  # Should not raise

    def test_lambda_in_seed_raises(self):
        """Lambda in seed raises TypeError."""
        seed = {"handler": lambda x: x}
        with pytest.raises(TypeError) as exc_info:
            assert_seed_pure(seed)
        # Lambda is caught by assert_mu (not valid Mu) - either message is fine
        assert "Mu" in str(exc_info.value) or "callable" in str(exc_info.value)

    def test_function_in_projection_raises(self):
        """Function in projection raises TypeError."""
        def my_apply(x):
            return x
        seed = {
            "seed": {
                "projections": [
                    {"pattern": 1, "body": my_apply}
                ]
            }
        }
        with pytest.raises(TypeError):
            assert_seed_pure(seed)

    def test_missing_pattern_raises(self):
        """Projection without pattern raises ValueError."""
        seed = {
            "seed": {
                "projections": [
                    {"body": 1}  # Missing pattern
                ]
            }
        }
        with pytest.raises(ValueError) as exc_info:
            assert_seed_pure(seed)
        assert "pattern" in str(exc_info.value)

    def test_missing_body_raises(self):
        """Projection without body raises ValueError."""
        seed = {
            "seed": {
                "projections": [
                    {"pattern": 1}  # Missing body
                ]
            }
        }
        with pytest.raises(ValueError) as exc_info:
            assert_seed_pure(seed)
        assert "body" in str(exc_info.value)

    def test_tuple_in_seed_raises(self):
        """Tuple in seed raises TypeError (not Mu)."""
        seed = {"pair": (1, 2)}
        with pytest.raises(TypeError):
            assert_seed_pure(seed)

    def test_bytes_in_seed_raises(self):
        """Bytes in seed raises TypeError (not Mu)."""
        seed = {"data": b"hello"}
        with pytest.raises(TypeError):
            assert_seed_pure(seed)


class TestAssertHandlerPure:
    """Tests for assert_handler_pure() - handler wrapper for Mu boundaries."""

    def test_valid_handler_wrapped(self):
        """Valid handler that returns Mu works."""
        def my_handler(ctx):
            return {"result": ctx.get("input", 0) + 1}

        wrapped = assert_handler_pure(my_handler, "test_handler")
        result = wrapped({"input": 5})
        assert result == {"result": 6}

    def test_handler_name_preserved(self):
        """Wrapped handler has descriptive name."""
        def my_handler(ctx):
            return ctx

        wrapped = assert_handler_pure(my_handler, "my_handler")
        assert "pure_my_handler" in wrapped.__name__

    def test_non_callable_raises(self):
        """Non-callable handler raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            assert_handler_pure("not a function", "bad_handler")
        assert "callable" in str(exc_info.value)

    def test_handler_with_invalid_input_raises(self):
        """Handler receiving non-Mu input raises."""
        def my_handler(ctx):
            return ctx

        wrapped = assert_handler_pure(my_handler, "test")
        with pytest.raises(TypeError) as exc_info:
            wrapped(lambda x: x)  # Lambda is not Mu
        assert "input" in str(exc_info.value)

    def test_handler_returning_non_mu_raises(self):
        """Handler returning non-Mu raises."""
        def bad_handler(ctx):
            return lambda x: x  # Returns non-Mu

        wrapped = assert_handler_pure(bad_handler, "bad")
        with pytest.raises(TypeError) as exc_info:
            wrapped({"input": 1})
        assert "output" in str(exc_info.value)


class TestValidateKernelBoundary:
    """Tests for validate_kernel_boundary() - kernel primitive validation."""

    def test_valid_boundary_passes(self):
        """Valid Mu inputs and output pass."""
        validate_kernel_boundary(
            "compute_identity",
            inputs={"mu": {"a": 1}},
            output="abc123"
        )  # Should not raise

    def test_invalid_input_raises(self):
        """Non-Mu input raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            validate_kernel_boundary(
                "compute_identity",
                inputs={"mu": lambda x: x},
                output="abc123"
            )
        assert "compute_identity" in str(exc_info.value)
        assert "mu" in str(exc_info.value)

    def test_invalid_output_raises(self):
        """Non-Mu output raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            validate_kernel_boundary(
                "gate_dispatch",
                inputs={"context": {"a": 1}},
                output=lambda x: x
            )
        assert "output" in str(exc_info.value)

    def test_none_output_allowed(self):
        """None output (no Mu output) is allowed."""
        validate_kernel_boundary(
            "record_trace",
            inputs={"entry": {"hash": "abc"}},
            output=None
        )  # Should not raise


# =============================================================================
# Structural Equality Tests (Anti-Python-Coercion)
# =============================================================================


class TestMuEqual:
    """Tests for mu_equal() - structural equality via JSON."""

    def test_identical_values(self):
        """Identical values are equal."""
        assert mu_equal({"a": 1}, {"a": 1}) is True
        assert mu_equal([1, 2, 3], [1, 2, 3]) is True
        assert mu_equal("hello", "hello") is True

    def test_different_values(self):
        """Different values are not equal."""
        assert mu_equal({"a": 1}, {"a": 2}) is False
        assert mu_equal([1, 2], [1, 2, 3]) is False

    def test_dict_key_order_irrelevant(self):
        """Dict key order doesn't affect equality (sorted keys)."""
        # Python dicts preserve insertion order, but mu_equal uses sorted keys
        a = {"z": 1, "a": 2}
        b = {"a": 2, "z": 1}
        assert mu_equal(a, b) is True

    def test_true_not_equal_to_one(self):
        """True is NOT equal to 1 (anti-Python-coercion)."""
        # In Python: True == 1 is True
        # In Mu: they are structurally different
        assert mu_equal(True, 1) is False

    def test_false_not_equal_to_zero(self):
        """False is NOT equal to 0 (anti-Python-coercion)."""
        # In Python: False == 0 is True
        # In Mu: they are structurally different
        assert mu_equal(False, 0) is False

    def test_none_not_equal_to_empty(self):
        """None is NOT equal to empty dict/list."""
        assert mu_equal(None, {}) is False
        assert mu_equal(None, []) is False

    def test_nested_structures(self):
        """Nested structures compare correctly."""
        a = {"x": [1, {"y": True}]}
        b = {"x": [1, {"y": True}]}
        c = {"x": [1, {"y": 1}]}  # True vs 1
        assert mu_equal(a, b) is True
        assert mu_equal(a, c) is False  # True != 1

    def test_non_mu_raises(self):
        """Non-Mu values raise TypeError."""
        with pytest.raises(TypeError):
            mu_equal(lambda x: x, {"a": 1})
        with pytest.raises(TypeError):
            mu_equal({"a": 1}, lambda x: x)


class TestMuHash:
    """Tests for mu_hash() - deterministic hashing."""

    def test_deterministic(self):
        """Same value always produces same hash."""
        value = {"a": [1, 2, {"b": 3}]}
        h1 = mu_hash(value)
        h2 = mu_hash(value)
        assert h1 == h2

    def test_different_values_different_hash(self):
        """Different values produce different hashes."""
        h1 = mu_hash({"a": 1})
        h2 = mu_hash({"a": 2})
        assert h1 != h2

    def test_dict_order_irrelevant(self):
        """Dict key order doesn't affect hash."""
        h1 = mu_hash({"z": 1, "a": 2})
        h2 = mu_hash({"a": 2, "z": 1})
        assert h1 == h2

    def test_true_vs_one_different_hash(self):
        """True and 1 produce different hashes."""
        h1 = mu_hash(True)
        h2 = mu_hash(1)
        assert h1 != h2

    def test_returns_hex_string(self):
        """Hash is a hex string (SHA-256 = 64 chars)."""
        h = mu_hash({"test": "value"})
        assert isinstance(h, str)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_non_mu_raises(self):
        """Non-Mu value raises TypeError."""
        with pytest.raises(TypeError):
            mu_hash(lambda x: x)


# =============================================================================
# Bootstrap Registry Tests
# =============================================================================


class TestBootstrapRegistry:
    """Tests for bootstrap marking functions."""

    def setup_method(self):
        """Clear registry before each test."""
        BOOTSTRAP_REGISTRY.clear()

    def teardown_method(self):
        """Clear registry after each test."""
        BOOTSTRAP_REGISTRY.clear()

    def test_mark_bootstrap_adds_entry(self):
        """mark_bootstrap adds to registry."""
        mark_bootstrap("python_match", "Will be replaced by EVAL_SEED")
        assert "python_match: Will be replaced by EVAL_SEED" in get_bootstrap_registry()

    def test_get_bootstrap_registry_returns_copy(self):
        """get_bootstrap_registry returns a copy."""
        mark_bootstrap("test", "reason")
        registry = get_bootstrap_registry()
        registry.append("should not affect original")
        assert "should not affect original" not in get_bootstrap_registry()

    def test_duplicate_mark_idempotent(self):
        """Marking same thing twice doesn't duplicate."""
        mark_bootstrap("test", "reason")
        mark_bootstrap("test", "reason")
        assert len(get_bootstrap_registry()) == 1

    def test_assert_no_bootstrap_passes_when_empty(self):
        """assert_no_bootstrap_in_production passes with empty registry."""
        assert_no_bootstrap_in_production()  # Should not raise

    def test_assert_no_bootstrap_fails_when_present(self):
        """assert_no_bootstrap_in_production fails when bootstrap present."""
        mark_bootstrap("leftover", "should be removed")
        with pytest.raises(RuntimeError) as exc_info:
            assert_no_bootstrap_in_production()
        assert "leftover" in str(exc_info.value)


# =============================================================================
# Meta-Tests (Prevent False Positives)
# =============================================================================


class TestNoGuardrailMocking:
    """
    Meta-tests to ensure no tests mock guardrail functions.

    Mocking guardrails creates false positives where tests pass
    but actual violations would be missed.
    """

    def test_this_file_has_no_mock_patches_on_guardrails(self):
        """
        This test file should not mock any guardrail functions.

        We check for actual @patch decorator usage, not just string mentions.
        """
        import inspect
        import re
        source = inspect.getsource(__import__('tests.test_mu_type', fromlist=['']))

        # Look for actual decorator usage: @patch(...) at start of line (with indent)
        # This excludes string literals like the ones in this test
        decorator_pattern = r'^\s*@patch\([\'"]rcx_pi\.mu_type\.(assert_mu|is_mu|validate_mu|assert_seed_pure|assert_no_callables|mu_equal)'

        matches = re.findall(decorator_pattern, source, re.MULTILINE)
        assert len(matches) == 0, (
            f"Found mock decorators for guardrail functions: {matches}. "
            f"Do not mock guardrail functions in tests."
        )
