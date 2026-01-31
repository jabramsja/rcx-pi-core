"""
Property-Based Bindings Roundtrip Fuzzer

Uses Hypothesis to verify the bindings conversion functions:
- dict_to_bindings: Python dict -> Mu linked list
- bindings_to_dict: Mu linked list -> Python dict

Critical property: bindings_to_dict(dict_to_bindings(d)) == d

9-agent review (Fuzzer finding): Bindings conversion is a kernel boundary
function. Bugs here would corrupt variable bindings in pattern matching.
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from rcx_pi.selfhost.match_mu import (
    dict_to_bindings,
    bindings_to_dict,
)
from rcx_pi.selfhost.mu_type import is_mu


# =============================================================================
# Mu Value Generators for Binding Values
# =============================================================================

@st.composite
def mu_primitives(draw):
    """Generate primitive Mu values for binding values."""
    return draw(st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-10**9, max_value=10**9),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(max_size=50),
    ))


@st.composite
def mu_binding_values(draw, max_depth=2):
    """Generate Mu values suitable for binding values."""
    return draw(mu_binding_values_strategy(max_depth))


def mu_binding_values_strategy(max_depth=2):
    """Return a strategy for Mu binding values at given depth."""
    if max_depth <= 0:
        return mu_primitives()

    inner = st.deferred(lambda: mu_binding_values_strategy(max_depth - 1))

    return st.one_of(
        mu_primitives(),
        st.lists(inner, max_size=5),
        st.dictionaries(
            st.text(min_size=1, max_size=10),
            inner,
            max_size=5
        ),
    )


@st.composite
def variable_names(draw):
    """Generate valid variable names (non-empty strings)."""
    # Variable names should be non-empty strings
    # Avoid special characters that might cause issues
    return draw(st.text(
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789"),
        min_size=1,
        max_size=20
    ))


@st.composite
def bindings_dicts(draw, max_size=10):
    """Generate bindings dictionaries (var name -> value)."""
    return draw(st.dictionaries(
        variable_names(),
        mu_binding_values(max_depth=2),
        min_size=0,
        max_size=max_size
    ))


# =============================================================================
# Core Roundtrip Property Tests
# =============================================================================

class TestBindingsRoundtripFuzzer:
    """Property-based tests for bindings conversion roundtrip."""

    @given(bindings_dicts())
    @settings(max_examples=500, deadline=5000)
    def test_roundtrip_property(self, bindings):
        """Property: bindings_to_dict(dict_to_bindings(d)) == d."""
        # Convert to linked list
        linked = dict_to_bindings(bindings)

        # Convert back
        result = bindings_to_dict(linked)

        assert result == bindings, (
            f"Roundtrip failed:\n"
            f"  Original: {bindings}\n"
            f"  Linked: {linked}\n"
            f"  Result: {result}"
        )

    @given(bindings_dicts())
    @settings(max_examples=500, deadline=5000)
    def test_all_keys_preserved(self, bindings):
        """Property: all keys are preserved in roundtrip."""
        linked = dict_to_bindings(bindings)
        result = bindings_to_dict(linked)

        assert set(result.keys()) == set(bindings.keys()), (
            f"Keys differ:\n"
            f"  Original: {set(bindings.keys())}\n"
            f"  Result: {set(result.keys())}"
        )

    @given(bindings_dicts())
    @settings(max_examples=500, deadline=5000)
    def test_all_values_preserved(self, bindings):
        """Property: all values are preserved in roundtrip."""
        linked = dict_to_bindings(bindings)
        result = bindings_to_dict(linked)

        for key in bindings:
            assert result[key] == bindings[key], (
                f"Value changed for key '{key}':\n"
                f"  Original: {bindings[key]}\n"
                f"  Result: {result[key]}"
            )


class TestLinkedListFormatFuzzer:
    """Property-based tests for linked list format validity."""

    @given(bindings_dicts())
    @settings(max_examples=500, deadline=5000)
    def test_linked_list_is_mu(self, bindings):
        """Property: dict_to_bindings produces valid Mu."""
        linked = dict_to_bindings(bindings)

        assert is_mu(linked), (
            f"Linked list is not valid Mu: {linked}"
        )

    @given(bindings_dicts())
    @settings(max_examples=500, deadline=5000)
    def test_linked_list_structure(self, bindings):
        """Property: linked list has correct structure."""
        linked = dict_to_bindings(bindings)

        # Empty bindings -> null
        if len(bindings) == 0:
            assert linked is None
            return

        # Non-empty -> linked list structure
        assert isinstance(linked, dict)

        # Walk the linked list and count entries
        count = 0
        current = linked
        while current is not None:
            assert isinstance(current, dict), f"Node is not dict: {current}"
            assert "name" in current, f"Node missing 'name': {current}"
            assert "value" in current, f"Node missing 'value': {current}"
            assert "rest" in current, f"Node missing 'rest': {current}"
            count += 1
            current = current.get("rest")

        assert count == len(bindings), (
            f"Linked list has {count} nodes but dict has {len(bindings)} entries"
        )


class TestDeterminismFuzzer:
    """Property-based tests for deterministic conversion."""

    @given(bindings_dicts())
    @settings(max_examples=300, deadline=5000)
    def test_deterministic_conversion(self, bindings):
        """Property: same dict produces same linked list."""
        linked1 = dict_to_bindings(bindings)
        linked2 = dict_to_bindings(bindings)

        # Both should be identical (deterministic)
        import json
        assert json.dumps(linked1, sort_keys=True) == json.dumps(linked2, sort_keys=True), (
            f"Non-deterministic:\n"
            f"  First: {linked1}\n"
            f"  Second: {linked2}"
        )

    @given(st.data())
    @settings(max_examples=100, deadline=5000)
    def test_key_order_invariance(self, data):
        """Property: dict key insertion order doesn't affect linked list content."""
        # Generate keys and values
        keys = data.draw(st.lists(variable_names(), min_size=2, max_size=5, unique=True))
        values = [data.draw(mu_primitives()) for _ in keys]

        # Create dicts with different insertion orders
        d1 = dict(zip(keys, values))
        d2 = dict(zip(reversed(keys), reversed(values)))

        linked1 = dict_to_bindings(d1)
        linked2 = dict_to_bindings(d2)

        result1 = bindings_to_dict(linked1)
        result2 = bindings_to_dict(linked2)

        # Both should produce same dict
        assert result1 == result2, (
            f"Key order affected result:\n"
            f"  d1: {d1}\n"
            f"  d2: {d2}\n"
            f"  result1: {result1}\n"
            f"  result2: {result2}"
        )


class TestEdgeCaseFuzzer:
    """Property-based tests for edge cases."""

    def test_empty_bindings(self):
        """Empty dict -> None -> empty dict."""
        linked = dict_to_bindings({})
        assert linked is None
        result = bindings_to_dict(linked)
        assert result == {}

    @given(variable_names(), mu_binding_values(max_depth=2))
    @settings(max_examples=300, deadline=5000)
    def test_single_binding(self, name, value):
        """Single binding roundtrips correctly."""
        bindings = {name: value}
        linked = dict_to_bindings(bindings)
        result = bindings_to_dict(linked)
        assert result == bindings

    @given(st.lists(variable_names(), min_size=5, max_size=10, unique=True))
    @settings(max_examples=100, deadline=5000)
    def test_many_bindings(self, names):
        """Many bindings roundtrip correctly."""
        bindings = {name: i for i, name in enumerate(names)}
        linked = dict_to_bindings(bindings)
        result = bindings_to_dict(linked)
        assert result == bindings

    @given(variable_names())
    @settings(max_examples=100, deadline=5000)
    def test_none_value_binding(self, name):
        """Binding with None value roundtrips correctly."""
        bindings = {name: None}
        linked = dict_to_bindings(bindings)
        result = bindings_to_dict(linked)
        assert result == bindings
        assert result[name] is None

    @given(variable_names())
    @settings(max_examples=100, deadline=5000)
    def test_empty_list_value_binding(self, name):
        """Binding with empty list value roundtrips correctly."""
        bindings = {name: []}
        linked = dict_to_bindings(bindings)
        result = bindings_to_dict(linked)
        assert result == bindings
        assert result[name] == []

    @given(variable_names())
    @settings(max_examples=100, deadline=5000)
    def test_empty_dict_value_binding(self, name):
        """Binding with empty dict value roundtrips correctly."""
        bindings = {name: {}}
        linked = dict_to_bindings(bindings)
        result = bindings_to_dict(linked)
        assert result == bindings
        assert result[name] == {}


class TestUnicodeBindingsFuzzer:
    """Property-based tests for Unicode variable names and values."""

    @given(st.text(min_size=1, max_size=20))
    @settings(max_examples=200, deadline=5000)
    def test_unicode_variable_names(self, name):
        """Unicode variable names roundtrip correctly."""
        assume(name)  # Non-empty
        bindings = {name: 42}
        linked = dict_to_bindings(bindings)
        result = bindings_to_dict(linked)
        assert result == bindings

    @given(st.text(max_size=100))
    @settings(max_examples=200, deadline=5000)
    def test_unicode_string_values(self, value):
        """Unicode string values roundtrip correctly."""
        bindings = {"x": value}
        linked = dict_to_bindings(bindings)
        result = bindings_to_dict(linked)
        assert result == bindings


class TestBindingsErrorHandlingFuzzer:
    """Property-based tests for error handling."""

    def test_malformed_linked_list_missing_name(self):
        """Malformed linked list (missing name) raises ValueError."""
        malformed = {"value": 42, "rest": None}  # Missing "name"
        with pytest.raises(ValueError, match="missing 'name'"):
            bindings_to_dict(malformed)

    def test_malformed_linked_list_non_dict_node(self):
        """Non-dict node in linked list raises ValueError."""
        malformed = {"name": "x", "value": 42, "rest": "not_a_dict_or_none"}
        with pytest.raises(ValueError, match="Invalid bindings structure"):
            bindings_to_dict(malformed)
