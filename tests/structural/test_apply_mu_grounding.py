"""
Structural grounding tests for Phase 4d apply_mu integration.

These tests verify that the integration of match_mu + subst_mu
operates at the Mu-structural level, not just Python behavioral level.

All tests must:
1. Use actual Mu terms (JSON-compatible dicts)
2. Call step() or run_*_projections() directly where possible
3. Assert structural expectations with assert_mu()
4. Verify determinism with mu_equal()

Phase 4d: Grounding tests for structural verification.

Test Infrastructure Note:
    This file uses Python host builtins (isinstance, len, etc.) for test
    assertion logic. These are TEST HARNESS operations, not Mu operations
    under test. The actual Mu implementations being validated operate on
    pure Mu structures via projections.
"""

import pytest

from rcx_pi.eval_seed import step, NO_MATCH, apply_projection
from rcx_pi.mu_type import assert_mu, mu_equal, is_mu
from rcx_pi.match_mu import (
    load_match_projections,
    normalize_for_match,
    denormalize_from_match,
    run_match_projections,
    match_mu,
)
from rcx_pi.subst_mu import (
    load_subst_projections,
    run_subst_projections,
    subst_mu,
)


# =============================================================================
# Test: Direct Projection Execution
# =============================================================================

class TestStructuralMatchExecution:
    """Verify match projections execute as pure Mu structures."""

    def test_match_var_projection_direct(self):
        """Verify match.var projection captures variable binding."""
        projections = load_match_projections()

        # State for matching {"var": "x"} against 42
        state = {
            "mode": "match",
            "pattern_focus": {"var": "x"},
            "value_focus": 42,
            "bindings": None,
            "stack": None
        }

        # Execute one step
        result = step(projections, state)

        # Assert structural expectation
        assert_mu(result, "match.var result")
        assert result["mode"] == "match"
        assert result["pattern_focus"] is None
        assert result["value_focus"] is None
        # Binding should be created
        assert result["bindings"] is not None
        assert result["bindings"]["name"] == "x"
        assert result["bindings"]["value"] == 42
        assert result["bindings"]["rest"] is None

    def test_match_equal_projection_direct(self):
        """Verify match.equal projection for literal matching."""
        projections = load_match_projections()

        state = {
            "mode": "match",
            "pattern_focus": 42,
            "value_focus": 42,
            "bindings": None,
            "stack": None
        }

        result = step(projections, state)

        assert_mu(result, "match.equal result")
        assert result["mode"] == "match"
        assert result["pattern_focus"] is None
        assert result["value_focus"] is None
        # No new bindings for literal match
        assert result["bindings"] is None
        assert result["stack"] is None

    def test_match_stalls_on_mismatch(self):
        """Verify match stalls when literals don't match.

        Note: Match failure is detected via stall (no projection fires),
        not via an explicit "no_match" status in the state.
        """
        projections = load_match_projections()

        state = {
            "mode": "match",
            "pattern_focus": 42,
            "value_focus": 99,
            "bindings": None,
            "stack": None
        }

        # Run to completion
        final, steps, is_stall = run_match_projections(projections, state, max_steps=10)

        # Should stall (no projection matches this case)
        assert is_stall is True
        # State should be unchanged
        assert mu_equal(final, state)

    def test_match_done_projection_direct(self):
        """Verify match.done projection completes correctly."""
        projections = load_match_projections()

        bindings = {"name": "x", "value": 42, "rest": None}
        state = {
            "mode": "match",
            "pattern_focus": None,
            "value_focus": None,
            "bindings": bindings,
            "stack": None
        }

        result = step(projections, state)

        assert_mu(result, "match.done result")
        assert result["mode"] == "match_done"
        assert result["status"] == "success"
        assert result["bindings"] == bindings


class TestStructuralSubstExecution:
    """Verify substitute projections execute as pure Mu structures."""

    def test_subst_var_projection_direct(self):
        """Verify subst.var projection marks lookup."""
        projections = load_subst_projections()

        bindings = {"name": "x", "value": 42, "rest": None}
        state = {
            "mode": "subst",
            "phase": "traverse",
            "focus": {"var": "x"},
            "bindings": bindings,
            "context": None
        }

        result = step(projections, state)

        assert_mu(result, "subst.var result")
        assert result["mode"] == "subst"
        # Should transition to lookup or result phase
        assert result["phase"] in ("result", "lookup")

    def test_subst_primitive_projection_direct(self):
        """Verify subst.primitive projection handles literals."""
        projections = load_subst_projections()

        state = {
            "mode": "subst",
            "phase": "traverse",
            "focus": 42,
            "bindings": None,
            "context": None
        }

        result = step(projections, state)

        assert_mu(result, "subst.primitive result")
        assert result["mode"] == "subst"
        # Primitive should go directly to result
        assert result["phase"] == "result"
        assert result["focus"] == 42


# =============================================================================
# Test: Normalization Round-Trips
# =============================================================================

class TestNormalizationRoundTrips:
    """Verify normalization preserves RCX-valid structures."""

    def test_roundtrip_list_nonempty(self):
        """Non-empty lists survive normalization round-trip."""
        original = [1, 2, 3]
        normalized = normalize_for_match(original)
        denormalized = denormalize_from_match(normalized)

        assert denormalized == original

    def test_roundtrip_dict_nonempty(self):
        """Non-empty dicts survive normalization round-trip."""
        original = {"a": 1, "b": 2}
        normalized = normalize_for_match(original)
        denormalized = denormalize_from_match(normalized)

        assert denormalized == original

    def test_roundtrip_nested_structure(self):
        """Deeply nested structures survive round-trip."""
        original = {
            "users": [
                {"name": "Alice", "scores": [1, 2, 3]},
                {"name": "Bob", "scores": [4, 5, 6]}
            ]
        }
        normalized = normalize_for_match(original)
        denormalized = denormalize_from_match(normalized)

        assert denormalized == original

    def test_normalization_determinism(self):
        """Normalization is deterministic (dict key ordering)."""
        value = {"z": 1, "a": 2, "m": 3}

        norm1 = normalize_for_match(value)
        norm2 = normalize_for_match(value)

        assert mu_equal(norm1, norm2)

    def test_roundtrip_primitives(self):
        """Primitives survive normalization."""
        for value in [None, True, False, 0, 1, -1, 3.14, "", "hello"]:
            normalized = normalize_for_match(value)
            denormalized = denormalize_from_match(normalized)
            assert denormalized == value, f"Failed for {value}"


# =============================================================================
# Test: Structural Equality
# =============================================================================

class TestStructuralEquality:
    """Verify structural equality vs Python equality."""

    def test_mu_equal_for_results(self):
        """Use mu_equal for structural comparison."""
        pattern = {"var": "x"}
        value = 42

        bindings1 = match_mu(pattern, value)
        bindings2 = match_mu(pattern, value)

        # Both should be structurally equal
        assert mu_equal(bindings1, bindings2)

    def test_result_validity_check(self):
        """All results must be valid Mu."""
        # Match produces Mu
        bindings = match_mu({"var": "x"}, [1, 2, 3])
        assert_mu(bindings, "match_mu bindings")

        # Subst produces Mu
        body = {"result": {"var": "x"}}
        result = subst_mu(body, bindings)
        assert_mu(result, "subst_mu result")

    def test_mu_equal_catches_type_coercion(self):
        """mu_equal should distinguish True from 1."""
        # Python: True == 1 is True
        # mu_equal: should distinguish via JSON serialization
        assert True == 1  # Python coercion
        assert not mu_equal(True, 1)  # Structural distinction


# =============================================================================
# Test: Trace Determinism
# =============================================================================

class TestTraceDeterminism:
    """Verify execution traces are deterministic."""

    def test_match_trace_deterministic(self):
        """Match produces identical trace on repeated runs."""
        pattern = {"a": {"var": "x"}, "b": {"var": "y"}}
        value = {"a": 1, "b": 2}

        norm_pattern = normalize_for_match(pattern)
        norm_value = normalize_for_match(value)

        initial = {
            "mode": "match",
            "pattern_focus": norm_pattern,
            "value_focus": norm_value,
            "bindings": None,
            "stack": None
        }

        projections = load_match_projections()

        # Capture trace 1
        trace1 = [initial]
        state = initial
        for _ in range(100):
            next_state = step(projections, state)
            trace1.append(next_state)
            if mu_equal(next_state, state):
                break
            state = next_state

        # Capture trace 2
        trace2 = [initial]
        state = initial
        for _ in range(100):
            next_state = step(projections, state)
            trace2.append(next_state)
            if mu_equal(next_state, state):
                break
            state = next_state

        # Traces must be identical
        assert len(trace1) == len(trace2), "Trace lengths differ"
        for i, (t1, t2) in enumerate(zip(trace1, trace2)):
            assert mu_equal(t1, t2), f"Trace diverged at step {i}"


# =============================================================================
# Test: Stall Conditions
# =============================================================================

class TestStallConditions:
    """Verify stall behavior for invalid states."""

    def test_match_stalls_on_unknown_mode(self):
        """Match stalls if mode is not 'match'."""
        projections = load_match_projections()

        # State with unexpected mode
        invalid_state = {"mode": "unknown_mode", "data": "test"}

        final, steps, is_stall = run_match_projections(projections, invalid_state, max_steps=10)

        assert is_stall is True
        assert mu_equal(final, invalid_state)

    def test_subst_raises_on_unbound_variable(self):
        """subst_mu raises KeyError for unbound variable."""
        body = {"result": {"var": "unbound"}}
        bindings = {"other": 42}

        with pytest.raises(KeyError, match="unbound"):
            subst_mu(body, bindings)


# =============================================================================
# Test: Projection Ordering
# =============================================================================

class TestProjectionOrdering:
    """Verify projection order in seed files."""

    def test_match_wrap_is_last(self):
        """match.wrap must be last projection."""
        projections = load_match_projections()

        # Find wrap projection
        wrap_ids = [p.get("id") for p in projections if p.get("id", "").endswith(".wrap")]
        assert len(wrap_ids) > 0, "No wrap projection found"

        # Last projection should be a wrap
        assert projections[-1].get("id", "").endswith(".wrap")

    def test_subst_wrap_is_last(self):
        """subst.wrap must be last projection."""
        projections = load_subst_projections()

        # Find wrap projection
        wrap_ids = [p.get("id") for p in projections if p.get("id", "").endswith(".wrap")]
        assert len(wrap_ids) > 0, "No wrap projection found"

        # Last projection should be a wrap
        assert projections[-1].get("id", "").endswith(".wrap")


# =============================================================================
# Test: Depth Boundaries
# =============================================================================

class TestDepthBoundaries:
    """Test depth boundary conditions."""

    def test_moderate_nesting_works(self):
        """Structures at 50 levels should work."""
        # Build 50-level deep structure
        deep_value = "leaf"
        for _ in range(50):
            deep_value = {"nested": deep_value}

        normalized = normalize_for_match(deep_value)
        denormalized = denormalize_from_match(normalized)

        # Should succeed without error
        assert is_mu(denormalized)

    def test_deep_matching(self):
        """Deep structures can be matched."""
        # Build 20-level deep structure
        deep_pattern = {"var": "x"}
        deep_value = "leaf"
        for _ in range(20):
            deep_pattern = {"nested": deep_pattern}
            deep_value = {"nested": deep_value}

        bindings = match_mu(deep_pattern, deep_value)
        assert bindings is not NO_MATCH
        assert bindings["x"] == "leaf"


# =============================================================================
# Test: Edge Cases Not in Parity Tests
# =============================================================================

class TestEdgeCasesNotCovered:
    """Additional edge cases from grounding analysis."""

    def test_empty_string_variable_name_rejected(self):
        """Empty string variable name is rejected (security hardening).

        HARDENED: Empty variable names cause confusing error messages.
        They are now rejected with ValueError.
        """
        pattern = {"var": ""}
        value = 42

        with pytest.raises(ValueError, match="cannot be empty"):
            match_mu(pattern, value)

    def test_numeric_string_keys(self):
        """Dict keys that look like numbers."""
        pattern = {"123": {"var": "x"}, "456": {"var": "y"}}
        value = {"123": "one", "456": "two"}

        bindings = match_mu(pattern, value)
        assert bindings is not NO_MATCH
        assert bindings["x"] == "one"
        assert bindings["y"] == "two"

    def test_special_json_strings(self):
        """Strings that are JSON keywords."""
        for special in ["null", "true", "false", "NaN", "Infinity"]:
            pattern = {"var": "x"}
            value = special

            bindings = match_mu(pattern, value)
            assert bindings is not NO_MATCH
            assert bindings["x"] == special

    def test_whitespace_in_values(self):
        """Values with various whitespace."""
        for ws in [" ", "\t", "\n", "  multiple  spaces  "]:
            pattern = {"var": "x"}
            value = ws

            bindings = match_mu(pattern, value)
            assert bindings is not NO_MATCH
            assert bindings["x"] == ws


# =============================================================================
# Test: Integration Grounding
# =============================================================================

class TestIntegrationGrounding:
    """Verify match_mu + subst_mu integration at structural level."""

    def test_apply_produces_valid_mu(self):
        """Full apply cycle produces valid Mu."""
        projection = {
            "pattern": {"a": {"var": "x"}, "b": {"var": "y"}},
            "body": {"result": {"first": {"var": "x"}, "second": {"var": "y"}}}
        }
        value = {"a": 1, "b": 2}

        # Match
        bindings = match_mu(projection["pattern"], value)
        assert_mu(bindings, "match bindings")

        # Substitute
        result = subst_mu(projection["body"], bindings)
        assert_mu(result, "subst result")

        # Verify result
        assert result == {"result": {"first": 1, "second": 2}}

    def test_parity_reference_is_mu(self):
        """Reference apply_projection also produces valid Mu."""
        projection = {
            "pattern": {"var": "x"},
            "body": {"wrapped": {"var": "x"}}
        }
        value = [1, 2, 3]

        result = apply_projection(projection, value)
        assert_mu(result, "apply_projection result")
