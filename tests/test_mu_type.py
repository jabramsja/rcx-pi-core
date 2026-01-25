"""
Tests for Mu Type validation.

A Mu is a JSON-compatible value: the portable, host-independent data type
for all RCX values. These tests ensure the validation functions correctly
identify valid and invalid Mu values.

See docs/MuType.v0.md for the specification.
"""

import json
import math
import pytest

from rcx_pi.mu_type import is_mu, validate_mu, assert_mu, mu_type_name


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
