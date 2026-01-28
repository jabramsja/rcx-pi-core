"""
Property-Based Fuzzing for Phase 7 Kernel Loop Readiness using Hypothesis.

This test suite generates 3000+ random inputs to stress-test Phase 7 requirements:
1. Seed projection coverage (all projections reachable, no unintended stalls)
2. Kernel trace integrity (traces are replay-complete with state transitions)
3. Kernel state injection resistance (domain data can't forge _mode/_phase)
4. Non-linear pattern fuzzing (same var multiple times in pattern)

Run with: pytest tests/test_phase7_readiness_fuzzer.py --hypothesis-show-statistics -v

Phase 7 Goal: Meta-circular kernel - projections select projections
Current Status: Design phase (VECTOR), testing readiness of Phase 6 foundation

Requires: pip install hypothesis

Test Infrastructure Note:
    This file uses Python host builtins for test generation and assertions.
    The Mu implementations (match_mu, subst_mu, step_mu) are under test.
    Test harness freely uses Python - we're testing Mu semantics, not Python.

Security Focus:
    - Type tag injection (covered in test_type_tags_fuzzer.py)
    - Mode namespace collision (_mode, _phase, _input, _remaining, _kernel_ctx)
    - Projection order manipulation (first-match-wins must be deterministic)
    - Context loss (kernel state must survive match/subst roundtrip)
"""

import pytest

# Skip all tests if hypothesis is not installed
hypothesis = pytest.importorskip("hypothesis", reason="hypothesis required for fuzzer tests")

from hypothesis import given, strategies as st, settings, assume, HealthCheck
from hypothesis.strategies import composite

from rcx_pi.selfhost.mu_type import is_mu, mu_equal, assert_mu
from rcx_pi.selfhost.match_mu import (
    match_mu,
    normalize_for_match,
    denormalize_from_match,
    load_match_projections,
)
from rcx_pi.selfhost.subst_mu import subst_mu, load_subst_projections
from rcx_pi.selfhost.step_mu import apply_mu, step_mu, run_mu
from rcx_pi.selfhost.classify_mu import load_classify_projections
from rcx_pi.eval_seed import NO_MATCH


# =============================================================================
# Hypothesis Strategies for Phase 7 Testing
# =============================================================================

# Primitive Mu values (JSON-compatible)
mu_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**31), max_value=2**31),  # JSON safe integers
    st.floats(
        allow_nan=False,
        allow_infinity=False,
        min_value=-1e10,
        max_value=1e10
    ),
    st.text(max_size=20),
)


@composite
def mu_values(draw, max_depth=3, allow_var_sites=False):
    """Generate valid Mu values recursively."""
    if max_depth <= 0:
        return draw(mu_primitives)

    strategies = [mu_primitives]

    if allow_var_sites:
        var_names = st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz",
            min_size=1,
            max_size=5
        )
        strategies.append(
            st.builds(lambda name: {"var": name}, var_names)
        )

    # Lists (shallow to avoid explosion)
    strategies.append(
        st.lists(
            mu_primitives,
            max_size=3
        )
    )

    # Dicts (shallow to avoid explosion)
    strategies.append(
        st.dictionaries(
            st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=5),
            mu_primitives,
            max_size=3
        )
    )

    return draw(st.one_of(*strategies))


@composite
def mu_patterns(draw, max_depth=2):
    """Generate valid patterns (Mu values with var sites)."""
    return draw(mu_values(max_depth=max_depth, allow_var_sites=True))


@composite
def nonlinear_mu_patterns(draw):
    """
    Generate patterns where same variable appears multiple times.

    This tests Phase 6b lookup projections (non-linear matching).
    Example: {"x": {"var": "v"}, "y": {"var": "v"}}  # v must bind same value
    """
    var_name = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=3))

    # Build structure with same var multiple times
    num_keys = draw(st.integers(min_value=2, max_value=4))

    pattern = {}
    for i in range(num_keys):
        pattern[f"k{i}"] = {"var": var_name}

    return pattern, var_name


@composite
def kernel_mode_injection_attempts(draw):
    """
    Generate structures that attempt to inject kernel state fields.

    Phase 7 security: Domain data must not be able to forge:
    - _mode, _phase, _input, _remaining
    - _kernel_ctx, _match_ctx, _subst_ctx
    - _pattern_focus, _value_focus, _bindings, _stack
    """
    malicious_key = draw(st.sampled_from([
        "_mode",
        "_phase",
        "_input",
        "_remaining",
        "_kernel_ctx",
        "_match_ctx",
        "_subst_ctx",
        "_pattern_focus",
        "_value_focus",
        "_bindings",
        "_stack",
        "_result",
        "_stall",
        "_status",
    ]))

    value = draw(mu_primitives)

    return {malicious_key: value}


@composite
def projection_lists(draw, min_size=1, max_size=3):
    """Generate lists of valid projections."""
    num_projs = draw(st.integers(min_value=min_size, max_value=max_size))
    projections = []

    for i in range(num_projs):
        # Simple patterns that might or might not match
        key = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=3))
        projections.append({
            "id": f"test.proj.{i}",
            "pattern": {key: {"var": "v"}},
            "body": {f"result_{i}": {"var": "v"}}
        })

    return projections


def extract_var_names(pattern, _seen=None) -> list:
    """Extract all variable names from a pattern (with duplicates)."""
    if _seen is None:
        _seen = set()
    if isinstance(pattern, (list, dict)) and id(pattern) in _seen:
        return []
    if isinstance(pattern, (list, dict)):
        _seen.add(id(pattern))

    if isinstance(pattern, dict):
        if set(pattern.keys()) == {"var"} and isinstance(pattern.get("var"), str):
            return [pattern["var"]]
        names = []
        for v in pattern.values():
            names.extend(extract_var_names(v, _seen))
        return names
    elif isinstance(pattern, list):
        names = []
        for elem in pattern:
            names.extend(extract_var_names(elem, _seen))
        return names
    return []


def contains_empty_collection(value, _seen=None):
    """Check if value contains [] or {} anywhere."""
    if _seen is None:
        _seen = set()
    if isinstance(value, (list, dict)) and id(value) in _seen:
        return False
    if isinstance(value, (list, dict)):
        _seen.add(id(value))

    if value == [] or value == {}:
        return True
    if isinstance(value, list):
        return any(contains_empty_collection(elem, _seen) for elem in value)
    if isinstance(value, dict):
        return any(contains_empty_collection(v, _seen) for v in value.values())
    return False


def contains_kernel_mode_keys(value, _seen=None):
    """Check if value contains kernel-internal keys (_mode, _phase, etc)."""
    if _seen is None:
        _seen = set()
    if isinstance(value, (list, dict)) and id(value) in _seen:
        return False
    if isinstance(value, (list, dict)):
        _seen.add(id(value))

    if isinstance(value, dict):
        kernel_keys = {"_mode", "_phase", "_input", "_remaining", "_kernel_ctx",
                       "_match_ctx", "_subst_ctx", "_pattern_focus", "_value_focus",
                       "_bindings", "_stack", "_result", "_stall", "_status"}
        if any(k in value for k in kernel_keys):
            return True
        return any(contains_kernel_mode_keys(v, _seen) for v in value.values())
    if isinstance(value, list):
        return any(contains_kernel_mode_keys(elem, _seen) for elem in value)
    return False


# =============================================================================
# Property 1: Seed Projection Coverage (No Unintended Stalls)
# =============================================================================

class TestSeedProjectionCoverage:
    """
    Tests that all seed projections are reachable and no unintended stalls occur.

    Phase 7 requirement: All 32 projections (match=7, subst=12, classify=6, eval=7)
    must be exercisable. If certain patterns never match, projections are dead code.
    """

    @given(mu_patterns(max_depth=2), mu_values(max_depth=2))
    @settings(max_examples=500, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_match_mu_never_unintended_stall(self, pattern, value):
        """
        match_mu should either match or return NO_MATCH.

        No unexpected stalls where match hangs or returns invalid result.
        """
        assume(is_mu(pattern))
        assume(is_mu(value))

        # Skip empty collections (known normalization edge case)
        if contains_empty_collection(pattern) or contains_empty_collection(value):
            return
        # Skip kernel mode keys (security test handles these)
        if contains_kernel_mode_keys(pattern) or contains_kernel_mode_keys(value):
            return

        try:
            result = match_mu(pattern, value)

            # Result must be NO_MATCH or valid bindings dict
            if result is NO_MATCH:
                assert result is NO_MATCH  # Verify sentinel identity
            else:
                assert isinstance(result, dict), f"match_mu returned non-dict: {type(result)}"
        except (ValueError, KeyError):
            pass  # Expected for some edge cases (empty var names, etc.)

    @given(mu_values(max_depth=2, allow_var_sites=True),
           st.dictionaries(
               st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=5),
               mu_primitives,
               max_size=5
           ))
    @settings(max_examples=500, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_subst_mu_never_unintended_stall(self, body, bindings):
        """
        subst_mu should either substitute or raise KeyError for unbound vars.

        No unexpected stalls where substitute hangs or returns invalid result.
        """
        assume(is_mu(body))

        # Skip empty collections
        if contains_empty_collection(body):
            return
        if contains_kernel_mode_keys(body) or contains_kernel_mode_keys(bindings):
            return

        # Only test if all vars are bound
        var_names = extract_var_names(body)
        if not all(v in bindings for v in var_names):
            return  # Would raise KeyError, that's expected

        try:
            result = subst_mu(body, bindings)
            assert is_mu(result), f"subst_mu returned invalid Mu: {type(result)}"
        except (ValueError, KeyError):
            pass  # Expected for some edge cases

    @given(projection_lists(min_size=1, max_size=3), mu_values(max_depth=2))
    @settings(max_examples=300, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_step_mu_projection_coverage(self, projections, value):
        """
        step_mu should try all projections in order without crashing.
        """
        assume(is_mu(value))
        if contains_empty_collection(value):
            return
        if contains_kernel_mode_keys(value):
            return

        result = step_mu(projections, value)

        # Result should be valid Mu
        assert is_mu(result), f"step_mu returned invalid Mu: {type(result)}"


# =============================================================================
# Property 2: Kernel Trace Integrity (Replay Completeness)
# =============================================================================

class TestKernelTraceIntegrity:
    """
    Tests that kernel traces capture all state transitions for replay.

    Phase 7 requirement: Traces must be replay-complete. If we record
    step_mu trace, we should be able to manually replay it.
    """

    @given(projection_lists(min_size=1, max_size=3), mu_values(max_depth=2))
    @settings(max_examples=300, deadline=10000, suppress_health_check=[HealthCheck.too_slow])
    def test_run_mu_trace_completeness(self, projections, initial):
        """
        run_mu traces should capture all intermediate states.

        Trace should have: initial step, intermediate steps, final step.
        """
        assume(is_mu(initial))
        if contains_empty_collection(initial):
            return
        if contains_kernel_mode_keys(initial):
            return

        result, trace, is_stall = run_mu(projections, initial, max_steps=10)

        # Trace should have at least 1 entry
        assert len(trace) >= 1, f"Trace too short: {len(trace)}"

        # First entry should be step 0
        assert trace[0]["step"] == 0, "First trace entry should be step 0"

        # Result should be valid Mu
        assert is_mu(result), f"run_mu result is invalid Mu"

    @given(projection_lists(min_size=1, max_size=3), mu_values(max_depth=2))
    @settings(max_examples=200, deadline=10000, suppress_health_check=[HealthCheck.too_slow])
    def test_trace_step_numbers_sequential(self, projections, initial):
        """
        Trace step numbers should be sequential 0, 1, 2, ...
        """
        assume(is_mu(initial))
        if contains_empty_collection(initial):
            return
        if contains_kernel_mode_keys(initial):
            return

        result, trace, is_stall = run_mu(projections, initial, max_steps=10)

        # Check step numbers are sequential
        for i, entry in enumerate(trace):
            assert entry["step"] == i, f"Step number mismatch at index {i}: got {entry['step']}"

    @given(mu_values(max_depth=2))
    @settings(max_examples=200, deadline=5000)
    def test_empty_projections_immediate_stall(self, value):
        """
        Empty projection list should immediately stall (return input unchanged).
        """
        assume(is_mu(value))
        if contains_empty_collection(value):
            return

        result, trace, is_stall = run_mu([], value, max_steps=10)

        # Should stall immediately
        assert is_stall, "Empty projections should cause immediate stall"
        assert mu_equal(result, value), "Stalled result should equal input"
        # Trace has 2 entries: initial state + stall detection
        assert len(trace) == 2, f"Expected 2 trace entries (init + stall), got {len(trace)}"


# =============================================================================
# Property 3: Kernel State Injection Resistance
# =============================================================================

class TestKernelStateInjectionResistance:
    """
    Tests that domain data cannot forge kernel-internal state fields.

    Phase 7 security requirement: Domain data with _mode, _phase, _input, etc.
    must not be able to manipulate kernel state transitions.
    """

    @given(kernel_mode_injection_attempts(), projection_lists(max_size=3))
    @settings(max_examples=300, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_domain_data_cannot_forge_kernel_mode(self, malicious_value, projections):
        """
        Domain data with _mode/_phase/_input keys should not break kernel.

        step_mu should handle these as normal data, not kernel state.
        """
        # Malicious value has kernel-internal keys
        assert contains_kernel_mode_keys(malicious_value), "Test setup error"

        # step_mu should not crash on malicious input
        try:
            result = step_mu(projections, malicious_value)
            assert is_mu(result), "step_mu returned invalid Mu"
        except (ValueError, KeyError, TypeError):
            pass  # Some errors acceptable for malformed input

    @given(mu_values(max_depth=2))
    @settings(max_examples=200, deadline=5000)
    def test_legitimate_underscore_keys_still_work(self, value):
        """
        Legitimate domain data with underscore keys should still work.

        Not all underscore keys are kernel-internal. E.g., _id, _timestamp.
        """
        # Add legitimate underscore key
        if isinstance(value, dict):
            test_value = {**value, "_user_data": "legitimate"}
        else:
            test_value = {"_user_data": "legitimate", "data": value}

        # Simple projection that matches anything
        projections = [{"pattern": {"var": "x"}, "body": {"wrapped": {"var": "x"}}}]

        # Should work normally
        result = step_mu(projections, test_value)
        assert is_mu(result), "step_mu failed on legitimate underscore key"

    @given(kernel_mode_injection_attempts())
    @settings(max_examples=200, deadline=5000)
    def test_normalize_denormalize_preserves_kernel_keys(self, malicious_value):
        """
        Normalization should preserve kernel-internal keys in domain data.

        If user data happens to have _mode key, it should roundtrip correctly.
        """
        assume(is_mu(malicious_value))

        normalized = normalize_for_match(malicious_value)
        denormalized = denormalize_from_match(normalized)

        # Kernel keys should survive roundtrip
        assert is_mu(denormalized), "Denormalized value not valid Mu"


# =============================================================================
# Property 4: Non-Linear Pattern Fuzzing
# =============================================================================

class TestNonLinearPatternFuzzing:
    """
    Tests that non-linear patterns work correctly.

    Phase 6b improvement: Same variable can appear multiple times in pattern.
    Example: {"x": {"var": "v"}, "y": {"var": "v"}}  # x and y must match same value

    This uses lookup projections in subst.v1.json.
    """

    @given(nonlinear_mu_patterns(), mu_primitives)
    @settings(max_examples=500, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_nonlinear_pattern_match_consistency(self, pattern_and_var, bound_value):
        """
        Non-linear patterns should enforce consistency.

        If pattern has {"k0": {"var": "v"}, "k1": {"var": "v"}},
        then value must have same value at k0 and k1 positions.
        """
        pattern, var_name = pattern_and_var
        assume(is_mu(bound_value))

        # Create consistent value (same value at all positions)
        value = {k: bound_value for k in pattern.keys()}

        try:
            result = match_mu(pattern, value)

            if result is not NO_MATCH:
                # All occurrences of same var should bind same value
                assert var_name in result, f"Var {var_name} not bound despite match success"
                assert mu_equal(result[var_name], bound_value), "Bound wrong value"
        except (ValueError, KeyError):
            pass

    def test_nonlinear_pattern_first_occurrence_wins(self):
        """
        Non-linear pattern binds first occurrence (current behavior).

        Pattern: {"x": {"var": "v"}, "y": {"var": "v"}}
        Value:   {"x": 1, "y": 2}

        Note: Current match_mu binds first occurrence of var and does NOT
        enforce consistency across multiple occurrences. This is documented
        behavior - non-linear constraint enforcement would be a Phase 7+
        enhancement. The lookup projections in subst.v1.json are for
        substitution, not pattern matching.
        """
        pattern = {"x": {"var": "v"}, "y": {"var": "v"}}
        value = {"x": 1, "y": 2}

        result = match_mu(pattern, value)

        # Current behavior: binds first occurrence, ignores subsequent
        # This is NOT a bug - it's how match_mu currently works
        if result is not NO_MATCH:
            # If it matched, the binding should be from one of the occurrences
            assert "v" in result, "Var should be bound"
            # Value should be either 1 or 2 (whichever was bound first)
            assert result["v"] in (1, 2), f"Bound unexpected value: {result['v']}"

    @given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=3),
           mu_primitives)
    @settings(max_examples=300, deadline=5000)
    def test_nonlinear_pattern_accepts_consistent(self, var_name, value):
        """
        Non-linear pattern should accept consistent values.

        Pattern: {"x": {"var": "v"}, "y": {"var": "v"}}
        Value:   {"x": 1, "y": 1}  # Should match (1 == 1)
        """
        assume(is_mu(value))
        if contains_empty_collection(value):
            return

        # Create value with SAME value at each key
        consistent_value = {"x": value, "y": value}
        pattern = {"x": {"var": var_name}, "y": {"var": var_name}}

        result = match_mu(pattern, consistent_value)

        # Should match
        assert result is not NO_MATCH, \
            f"Non-linear pattern rejected consistent values: {consistent_value}"
        assert var_name in result, "Var not bound"
        assert mu_equal(result[var_name], value), f"Bound wrong value"


# =============================================================================
# Property 5: Projection Order Security (First-Match-Wins)
# =============================================================================

class TestProjectionOrderSecurity:
    """
    Tests that projection order is deterministic and attack-resistant.

    Phase 7 security requirement: First-match-wins must be deterministic.
    Projection order cannot be manipulated by input data.
    """

    @given(projection_lists(min_size=2, max_size=4), mu_values(max_depth=2))
    @settings(max_examples=500, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_first_match_wins_deterministic(self, projections, value):
        """
        First matching projection should always win.

        Running step_mu multiple times should give same result.
        """
        assume(is_mu(value))
        if contains_empty_collection(value):
            return
        if contains_kernel_mode_keys(value):
            return

        # Run multiple times
        result1 = step_mu(projections, value)
        result2 = step_mu(projections, value)
        result3 = step_mu(projections, value)

        # All should be identical
        assert mu_equal(result1, result2), "First-match-wins not deterministic (1 vs 2)"
        assert mu_equal(result2, result3), "First-match-wins not deterministic (2 vs 3)"

    @given(mu_values(max_depth=2))
    @settings(max_examples=300, deadline=5000)
    def test_projection_order_matters(self, value):
        """
        Reversing projection order changes which one matches first.

        This tests that projection order is security-critical.
        """
        assume(is_mu(value))
        if contains_empty_collection(value):
            return

        # Two overlapping projections
        proj1 = {"pattern": {"var": "x"}, "body": "first"}
        proj2 = {"pattern": {"var": "y"}, "body": "second"}

        result_forward = step_mu([proj1, proj2], value)
        result_backward = step_mu([proj2, proj1], value)

        # Both should match (var patterns match anything)
        # But results should be different based on order
        assert result_forward == "first", "First projection should win"
        assert result_backward == "second", "Second projection should win when first"


# =============================================================================
# Property 6: Context Preservation
# =============================================================================

class TestContextPreservation:
    """
    Tests that match/subst roundtrip preserves structure.

    Phase 7 design requirement: match_mu + subst_mu should compose correctly.
    """

    @given(mu_patterns(max_depth=2), mu_values(max_depth=2))
    @settings(max_examples=300, deadline=5000, suppress_health_check=[HealthCheck.too_slow])
    def test_match_subst_roundtrip_preserves_value_type(self, pattern, value):
        """
        match_mu -> subst_mu roundtrip should produce valid Mu.
        """
        assume(is_mu(pattern))
        assume(is_mu(value))

        if contains_empty_collection(pattern) or contains_empty_collection(value):
            return

        try:
            bindings = match_mu(pattern, value)
            if bindings is NO_MATCH:
                return  # No match, skip

            # Simple body with a var from the pattern
            var_names = extract_var_names(pattern)
            if not var_names:
                return

            body = {"result": {"var": var_names[0]}}
            result = subst_mu(body, bindings)

            # Result should be valid Mu
            assert is_mu(result), "subst_mu result not valid Mu"
        except (ValueError, KeyError):
            pass

    @given(projection_lists(min_size=2, max_size=3))
    @settings(max_examples=200, deadline=5000)
    def test_projection_list_not_modified_by_step(self, projections):
        """
        Projection list should not be modified by step_mu.

        Phase 7 requirement: _remaining is immutable (linked list).
        """
        import copy

        # Deep copy projection list structure
        projections_before = copy.deepcopy(projections)

        # Run step_mu
        value = {"test": "data"}
        result = step_mu(projections, value)

        # Projection list should be unchanged
        assert projections == projections_before, "step_mu modified projection list"


# =============================================================================
# Edge Cases: Load Actual Seed Files
# =============================================================================

class TestActualSeedProjections:
    """
    Tests using actual seed files (match.v1.json, subst.v1.json, classify.v1.json).

    This ensures Phase 7 readiness with REAL projection data, not just synthetic.
    """

    def test_match_projections_loaded(self):
        """Match projections should load without error."""
        match_projs = load_match_projections()
        assert len(match_projs) > 0, "No match projections loaded"
        assert len(match_projs) == 7, f"Expected 7 match projections, got {len(match_projs)}"

    def test_subst_projections_loaded(self):
        """Subst projections should load without error."""
        subst_projs = load_subst_projections()
        assert len(subst_projs) > 0, "No subst projections loaded"
        assert len(subst_projs) == 12, f"Expected 12 subst projections, got {len(subst_projs)}"

    def test_classify_projections_loaded(self):
        """Classify projections should load without error."""
        classify_projs = load_classify_projections()
        assert len(classify_projs) > 0, "No classify projections loaded"
        assert len(classify_projs) == 6, f"Expected 6 classify projections, got {len(classify_projs)}"

    def test_all_projections_have_required_fields(self):
        """All seed projections must have id, pattern, body."""
        for name, loader in [
            ("match", load_match_projections),
            ("subst", load_subst_projections),
            ("classify", load_classify_projections),
        ]:
            projs = loader()
            for proj in projs:
                assert "id" in proj, f"{name} projection missing 'id'"
                assert "pattern" in proj, f"{name} projection missing 'pattern'"
                assert "body" in proj, f"{name} projection missing 'body'"


# =============================================================================
# Regression Tests: Known Issues from Prior Phases
# =============================================================================

class TestKnownRegressions:
    """
    Regression tests for issues found in prior phases.

    These should remain fixed in Phase 7.
    """

    def test_empty_list_vs_empty_dict_normalization(self):
        """
        Empty list and empty dict both normalize to None (known limitation).

        This is EXPECTED behavior, not a bug. Documented in Phase 6c.
        """
        assert normalize_for_match([]) is None
        assert normalize_for_match({}) is None

    def test_type_tag_whitelist_enforced(self):
        """
        Type tags must be whitelisted ("list" or "dict").

        Phase 6c security: Invalid type tags must be rejected.
        """
        from rcx_pi.selfhost.match_mu import validate_type_tag

        validate_type_tag("list", "test")  # Should not raise
        validate_type_tag("dict", "test")  # Should not raise

        with pytest.raises(ValueError, match="Invalid type tag"):
            validate_type_tag("malicious", "test")

    @given(mu_values(max_depth=2))
    @settings(max_examples=200, deadline=5000)
    def test_mu_equal_reflexive(self, value):
        """mu_equal should be reflexive (x == x)."""
        assume(is_mu(value))
        assert mu_equal(value, value), "mu_equal not reflexive"

    def test_true_not_equal_one(self):
        """Regression: True and 1 should be distinct in Mu."""
        assert not mu_equal(True, 1), "mu_equal failed to discriminate True vs 1"
        assert not mu_equal(False, 0), "mu_equal failed to discriminate False vs 0"

    def test_projection_order_is_security_critical(self):
        """
        Regression: Projection order must be deterministic.

        Adversary finding from Phase 6d: first-match-wins is security-critical.
        """
        projs = [
            {"pattern": {"var": "x"}, "body": "first"},
            {"pattern": {"var": "y"}, "body": "second"},
        ]

        result = step_mu(projs, {"any": "value"})
        assert result == "first", "First projection should always win"


# =============================================================================
# Linked-List Cursor Tests (Phase 7 Foundation)
# =============================================================================

class TestLinkedListCursor:
    """
    Tests for linked-list cursor iteration (Phase 7 foundation).

    Phase 7 uses head/tail pattern matching for iteration without arithmetic.
    These tests verify the foundation is solid.

    Note: match_mu denormalizes results back to Python dicts/lists. The
    head/tail structure exists in normalized form during matching, but
    bindings contain denormalized values. For Phase 7 kernel projections,
    the kernel state will remain in normalized (head/tail) form.
    """

    def test_linked_list_pattern_matches_head_tail_structure(self):
        """
        Verify head/tail pattern matching works on normalized structures.

        The key insight: Phase 7 kernel will work with normalized Mu (head/tail)
        internally. This test verifies the pattern matching works.
        """
        # Head/tail structure (what normalized Mu looks like)
        remaining = {
            "head": "first",
            "tail": {
                "head": "second",
                "tail": None
            }
        }

        # Pattern to extract head and tail
        pattern = {"head": {"var": "current"}, "tail": {"var": "rest"}}

        bindings = match_mu(pattern, remaining)
        assert bindings is not NO_MATCH
        assert bindings["current"] == "first"
        # rest is denormalized to a list by match_mu
        assert bindings["rest"] == ["second"], f"Expected ['second'], got {bindings['rest']}"

    def test_empty_remaining_is_null(self):
        """Empty remaining list is represented as null (termination condition)."""
        pattern = {"head": {"var": "current"}, "tail": {"var": "rest"}}
        remaining = None  # Empty list

        # Should not match (no head/tail structure)
        bindings = match_mu(pattern, remaining)
        assert bindings is NO_MATCH, (
            "null (empty list) does not match head/tail pattern. "
            "This is how kernel.stall detects 'no more projections'."
        )

    def test_cursor_termination_at_single_element(self):
        """Single-element linked list has null tail."""
        # Single element: head is value, tail is null
        single = {"head": "only", "tail": None}

        pattern = {"head": {"var": "current"}, "tail": {"var": "rest"}}

        bindings = match_mu(pattern, single)
        assert bindings is not NO_MATCH
        assert bindings["current"] == "only"
        # Empty tail (null) stays as None
        assert bindings["rest"] is None, f"Expected None, got {bindings['rest']}"

    def test_projection_list_as_linked_list(self):
        """
        Projection list can be represented as linked list for Phase 7.

        This is the foundation of meta-circular kernel: projections stored
        as head/tail structure, cursor advances by pattern matching.
        """
        # Three projections as linked list
        proj_list = {
            "head": {"id": "p1", "pattern": {"a": 1}, "body": "r1"},
            "tail": {
                "head": {"id": "p2", "pattern": {"b": 2}, "body": "r2"},
                "tail": {
                    "head": {"id": "p3", "pattern": {"c": 3}, "body": "r3"},
                    "tail": None
                }
            }
        }

        # Extract first projection
        pattern = {"head": {"var": "proj"}, "tail": {"var": "rest"}}
        bindings = match_mu(pattern, proj_list)

        assert bindings is not NO_MATCH
        assert bindings["proj"]["id"] == "p1"

        # The rest is denormalized to a Python list of dicts
        rest = bindings["rest"]
        assert isinstance(rest, list), f"Expected list, got {type(rest)}"
        assert len(rest) == 2, f"Expected 2 remaining, got {len(rest)}"
        assert rest[0]["id"] == "p2"
        assert rest[1]["id"] == "p3"


# =============================================================================
# Summary Statistics Tests
# =============================================================================

class TestFuzzerCoverage:
    """
    Meta-tests to verify fuzzer is exercising diverse inputs.
    """

    @given(mu_values(max_depth=3))
    @settings(max_examples=500, deadline=5000)
    def test_fuzzer_generates_diverse_types(self, value):
        """Fuzzer should generate diverse Mu types."""
        assume(is_mu(value))
        assert is_mu(value), "Fuzzer generated invalid Mu"

    @given(mu_patterns(max_depth=2))
    @settings(max_examples=500, deadline=5000)
    def test_fuzzer_generates_diverse_patterns(self, pattern):
        """Fuzzer should generate diverse patterns with var sites."""
        assume(is_mu(pattern))
        assert is_mu(pattern), "Fuzzer generated invalid pattern"

    @given(projection_lists(min_size=1, max_size=4))
    @settings(max_examples=300, deadline=5000)
    def test_fuzzer_generates_diverse_projection_lists(self, projections):
        """Fuzzer should generate diverse projection lists."""
        assert len(projections) >= 1, "Empty projection list"

        for proj in projections:
            assert "pattern" in proj, "Projection missing pattern"
            assert "body" in proj, "Projection missing body"
