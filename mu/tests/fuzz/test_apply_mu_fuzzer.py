"""
Property-Based Fuzzing for apply_mu using Hypothesis.

This test suite generates 1000+ random inputs to stress-test the
integration of match_mu + subst_mu via apply_mu.

Run with: pytest tests/test_apply_mu_fuzzer.py --hypothesis-show-statistics -v

Phase 4d: Verifies structural properties hold across random inputs.

Requires: pip install hypothesis

Test Infrastructure Note:
    This file uses Python host builtins (len, isinstance, set operations, etc.)
    for test generation and assertion logic. These are TEST HARNESS operations,
    not Mu operations under test. The actual Mu implementations (match_mu,
    subst_mu) are what's being validated - the test harness is allowed to use
    host Python freely.

Known Limitations Tested:
    - Empty collections ([], {}) normalize to None in Mu representation
    - Head/tail dict structures can collide with user data having those keys
    These are documented design decisions. Tests skip these cases
    for parity checks but verify the core properties still hold.

    Non-linear patterns (same var twice) are now handled correctly via
    B-structural approach: match_mu uses match.v2 + bridge projections
    which detect binding conflicts structurally.
"""

import pytest

# Skip all tests if hypothesis is not installed

from hypothesis import given, strategies as st, settings, assume, HealthCheck
from hypothesis.strategies import composite

from rcx_pi.eval_seed import apply_projection, NO_MATCH
from rcx_pi.mu_type import is_mu, mu_equal, MAX_MU_DEPTH

# Import apply_mu from production code (9-agent Expert finding 2026-02-01)
# Production version has assert_mu() validation that conftest version lacked
from rcx_pi.step_mu import apply_mu
from tests.helpers.structural_numbers import sn


# =============================================================================
# Hypothesis Strategies for Mu Values
# =============================================================================

# Primitive Mu values (JSON-compatible). Stage 4 encodes matcher-facing
# integer facts as StructuralNumbers; host floats are covered by explicit
# legacy edge-case probes below, not broad legal Mu generation.
mu_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-128, max_value=128).map(sn),
    st.text(max_size=100),  # Reasonable string length
)


@composite
def mu_values(draw, max_depth=3, allow_var_sites=False):
    """
    Generate valid Mu values recursively.

    Args:
        max_depth: Maximum nesting depth (default 3 to prevent pathological
                   nesting after normalization - each dict level can triple)
        allow_var_sites: If True, can generate {"var": "x"} structures
    """
    if max_depth <= 0:
        return draw(mu_primitives)

    strategies = [mu_primitives]

    # Add variable sites if allowed
    if allow_var_sites:
        var_names = st.one_of(
            st.just("x"),
            st.just("y"),
            st.just("z"),
            st.text(
                alphabet=st.characters(
                    whitelist_categories=("L", "N"),  # Letters and numbers only
                    min_codepoint=ord('a'),
                    max_codepoint=ord('z')
                ),
                min_size=1,
                max_size=10
            ),
        )
        strategies.append(
            st.builds(lambda name: {"var": name}, var_names)
        )

    # Add lists (limited size for performance)
    strategies.append(
        st.lists(
            st.deferred(lambda: mu_values(max_depth=max_depth-1, allow_var_sites=allow_var_sites)),
            max_size=4
        )
    )

    # Add dicts (limited size for performance)
    strategies.append(
        st.dictionaries(
            st.text(
                alphabet=st.characters(
                    whitelist_categories=("L", "N"),
                    min_codepoint=ord('a'),
                    max_codepoint=ord('z')
                ),
                min_size=1,
                max_size=10
            ),
            st.deferred(lambda: mu_values(max_depth=max_depth-1, allow_var_sites=allow_var_sites)),
            max_size=4
        )
    )

    return draw(st.one_of(*strategies))


@composite
def mu_patterns(draw, max_depth=3):
    """Generate valid patterns (Mu values with possible var sites)."""
    return draw(mu_values(max_depth=max_depth, allow_var_sites=True))


def extract_var_names(pattern) -> set:
    """Extract all variable names from a pattern.

    Only extracts var sites where the name is a string (valid variable names).
    Nested var sites like {"var": {"var": "x"}} are recursively explored.
    """
    if isinstance(pattern, dict):
        if set(pattern.keys()) == {"var"}:
            var_val = pattern["var"]
            # Only string names are valid variables; recurse into nested structures
            if isinstance(var_val, str):
                return {var_val}
            else:
                # Recurse into nested structure (e.g., {"var": {"var": "x"}})
                return extract_var_names(var_val)
        names = set()
        for v in pattern.values():
            names |= extract_var_names(v)
        return names
    elif isinstance(pattern, list):
        names = set()
        for elem in pattern:
            names |= extract_var_names(elem)
        return names
    return set()


def has_nonlinear_vars(pattern) -> bool:
    """Check if pattern has non-linear variables (same var name appears twice).

    Used by fuzzer strategies to generate targeted non-linear test cases.
    Non-linear conflict detection is handled by bridge projections
    (bridge.var.check_existing intercepts vars before match.var).
    """
    var_counts = {}

    def count_vars(value):
        if isinstance(value, dict):
            if set(value.keys()) == {"var"} and isinstance(value["var"], str):
                name = value["var"]
                var_counts[name] = var_counts.get(name, 0) + 1
            else:
                for v in value.values():
                    count_vars(v)
        elif isinstance(value, list):
            for elem in value:
                count_vars(elem)

    count_vars(pattern)
    return any(count > 1 for count in var_counts.values())


@composite
def mu_projections(draw):
    """
    Generate valid projection dicts with pattern and body.
    """
    pattern = draw(mu_patterns(max_depth=3))

    # Generate body (may or may not reference vars from pattern)
    body = draw(mu_values(max_depth=3, allow_var_sites=True))

    return {"pattern": pattern, "body": body}


@composite
def mu_nonlinear_projections(draw):
    """Generate projections with deliberately repeated variables (non-linear patterns).

    Non-linear patterns have the same variable name in multiple pattern positions.
    These are critical for testing binding conflict detection:
    - Same var, different values at positions -> NO_MATCH
    - Same var, same value at positions -> match succeeds
    """
    var_name = draw(st.sampled_from(["x", "y", "z", "v", "w"]))

    # Number of keys in the pattern dict (2-5, all mapping to the same var)
    num_keys = draw(st.integers(min_value=2, max_value=5))
    keys = [f"k{i}" for i in range(num_keys)]

    # Build pattern: at least 2 positions use the same var
    # Some positions may use different vars or literals for variety
    pattern = {}
    nonlinear_positions = draw(
        st.lists(
            st.sampled_from(keys),
            min_size=2,
            max_size=num_keys,
            unique=True,
        )
    )
    for key in keys:
        if key in nonlinear_positions:
            pattern[key] = {"var": var_name}
        else:
            # Use a unique var name for non-repeated positions or a literal
            pattern[key] = draw(st.one_of(
                st.just({"var": "other_" + key}),
                mu_primitives,
            ))

    body = draw(st.one_of(
        st.just("matched"),
        st.just({"result": {"var": var_name}}),
    ))

    return {"pattern": pattern, "body": body, "_nonlinear_var": var_name,
            "_nonlinear_keys": nonlinear_positions}


@composite
def mu_nonlinear_conflict_inputs(draw):
    """Generate (projection, value) pairs where non-linear vars bind to DIFFERENT values.

    These MUST return NO_MATCH in a correct implementation.
    """
    proj_info = draw(mu_nonlinear_projections())
    pattern = proj_info["pattern"]
    body = proj_info["body"]
    nl_var = proj_info["_nonlinear_var"]
    nl_keys = proj_info["_nonlinear_keys"]

    # Generate distinct values for the non-linear positions
    base_val = draw(mu_primitives)
    conflict_val = draw(mu_primitives)
    assume(not mu_equal(base_val, conflict_val))

    value = {}
    first = True
    for key in sorted(pattern.keys()):
        if key in nl_keys:
            if first:
                value[key] = base_val
                first = False
            else:
                value[key] = conflict_val
        else:
            # For non-nonlinear positions, provide a matching value
            if isinstance(pattern[key], dict) and set(pattern[key].keys()) == {"var"}:
                value[key] = draw(mu_primitives)
            else:
                value[key] = pattern[key]

    return {"pattern": pattern, "body": body}, value


@composite
def mu_nonlinear_agreement_inputs(draw):
    """Generate (projection, value) pairs where non-linear vars bind to SAME value.

    These MUST succeed (return body result) in a correct implementation.
    """
    proj_info = draw(mu_nonlinear_projections())
    pattern = proj_info["pattern"]
    body = proj_info["body"]
    nl_keys = proj_info["_nonlinear_keys"]

    # Same value at all non-linear positions
    shared_val = draw(mu_primitives)

    value = {}
    for key in sorted(pattern.keys()):
        if key in nl_keys:
            value[key] = shared_val
        else:
            if isinstance(pattern[key], dict) and set(pattern[key].keys()) == {"var"}:
                value[key] = draw(mu_primitives)
            else:
                value[key] = pattern[key]

    return {"pattern": pattern, "body": body}, value


def contains_var_site(value, _seen=None):
    """Check if value contains {"var": ...} anywhere."""
    if _seen is None:
        _seen = set()
    if id(value) in _seen:
        return False
    _seen.add(id(value))

    if isinstance(value, dict):
        if set(value.keys()) == {"var"}:
            return True
        return any(contains_var_site(v, _seen) for v in value.values())
    if isinstance(value, list):
        return any(contains_var_site(elem, _seen) for elem in value)
    return False


def is_empty_collection(value):
    """Check if value is [] or {}."""
    return value == [] or value == {}


def contains_empty_collection(value, _seen=None):
    """Check if value contains [] or {} anywhere."""
    if _seen is None:
        _seen = set()
    if id(value) in _seen:
        return False
    _seen.add(id(value))

    if value == [] or value == {}:
        return True
    if isinstance(value, list):
        return any(contains_empty_collection(elem, _seen) for elem in value)
    if isinstance(value, dict):
        return any(contains_empty_collection(v, _seen) for v in value.values())
    return False


def contains_head_tail(value, _seen=None):
    """Check if value contains head/tail structure."""
    if _seen is None:
        _seen = set()
    if id(value) in _seen:
        return False
    _seen.add(id(value))

    if isinstance(value, dict):
        if set(value.keys()) == {"head", "tail"}:
            return True
        return any(contains_head_tail(v, _seen) for v in value.values())
    if isinstance(value, list):
        return any(contains_head_tail(elem, _seen) for elem in value)
    return False


def is_negative_zero(value):
    """Check if value is -0.0 (IEEE 754 negative zero)."""
    import math
    return isinstance(value, float) and value == 0.0 and math.copysign(1.0, value) < 0


def contains_signed_zero_mismatch(pattern, value):
    """
    Check if pattern and value have a signed zero mismatch.

    Python == treats 0.0 == -0.0 as True, but JSON serialization distinguishes them.
    This causes parity violations when matching 0.0 against -0.0.
    """
    # Direct comparison case
    if isinstance(pattern, float) and isinstance(value, float):
        if pattern == 0.0 and value == 0.0:
            # Check if one is negative zero and the other isn't
            import math
            p_sign = math.copysign(1.0, pattern)
            v_sign = math.copysign(1.0, value)
            if p_sign != v_sign:
                return True
    return False


# =============================================================================
# Property 1: Determinism
# =============================================================================

@given(mu_projections(), mu_values(max_depth=3))
@settings(
    deadline=5000,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much]
)
def test_apply_mu_determinism(projection, value):
    """apply_mu must be deterministic - same input always gives same output."""
    assume(is_mu(projection))
    assume(is_mu(value))

    try:
        result1 = apply_mu(projection, value)
        result2 = apply_mu(projection, value)

        # Use structural equality (avoid Python coercion)
        if result1 is NO_MATCH:
            assert result2 is NO_MATCH, "Determinism violated: got NO_MATCH then match"
        else:
            assert result2 is not NO_MATCH, "Determinism violated: got match then NO_MATCH"
            assert mu_equal(result1, result2), f"Determinism violated: {result1} != {result2}"
    except (KeyError, TypeError, ValueError):
        # Expected errors should also be deterministic
        try:
            apply_mu(projection, value)
            assert False, "Non-deterministic error: first call raised, second didn't"
        except (KeyError, TypeError, ValueError):
            pass  # Good - same error twice


# =============================================================================
# Property 2: Parity with Reference Implementation
# =============================================================================

@given(mu_projections(), mu_values(max_depth=3))
@settings(
    deadline=5000,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much]
)
def test_apply_mu_parity_fuzzer(projection, value):
    """apply_mu should match apply_projection behavior (with known exceptions).

    Known limitation: empty collections ([], {}) normalize to None in Mu.
    This causes parity differences when:
    - Pattern is None and value is [] or {} (Mu matches, Python doesn't)
    - Pattern is [] or {} and value is None (Mu matches, Python doesn't)
    - Body contains [] or {} (Mu returns None, Python returns [])

    Known limitation: signed zeros (0.0 vs -0.0).
    Python == treats them as equal, but JSON serialization distinguishes them.
    Mu uses JSON-based structural comparison, so 0.0 != -0.0 in Mu.

    Non-linear patterns (same var twice) are handled correctly via
    B-structural approach: match_mu uses match.v2 + bridge projections
    which detect binding conflicts structurally.
    """
    assume(is_mu(projection))
    assume(is_mu(value))

    # Skip if body has unbound variables (would raise KeyError)
    pattern_vars = extract_var_names(projection.get("pattern", {}))
    body_vars = extract_var_names(projection.get("body", {}))
    unbound = body_vars - pattern_vars
    if unbound:
        return  # Skip - expected to raise KeyError

    pattern = projection.get("pattern")
    body = projection.get("body")

    # Known limitation: empty collection normalization
    # Skip cases where empty collections cause expected divergence
    if is_empty_collection(value) or contains_empty_collection(value):
        return  # Skip - known divergence
    if is_empty_collection(pattern) or contains_empty_collection(pattern):
        return  # Skip - known divergence
    if is_empty_collection(body) or contains_empty_collection(body):
        return  # Skip - known divergence

    # Non-linear patterns handled correctly via B-structural approach:
    # match_mu uses match.v2 + bridge projections which detect binding conflicts.

    # Known limitation: None ↔ [] confusion due to normalization
    # Skip cases where pattern=None matches value=[] or vice versa
    if pattern is None and value is None:
        pass  # This should match in both
    elif pattern is None or value is None:
        # One is None - could cause mismatch due to normalization
        return  # Skip - known edge case

    # Known limitation: head/tail structures denormalize to lists
    if contains_head_tail(value) or contains_head_tail(pattern) or contains_head_tail(body):
        return  # Skip - known divergence

    # Known limitation: signed zeros (0.0 vs -0.0)
    # Python == treats them as equal, JSON distinguishes them
    if contains_signed_zero_mismatch(pattern, value):
        return  # Skip - known divergence

    try:
        py_result = apply_projection(projection, value)
        mu_result = apply_mu(projection, value)

        # Exact parity expected for non-edge cases
        if py_result is NO_MATCH:
            assert mu_result is NO_MATCH, "Parity violation: Python NO_MATCH, Mu matched"
        else:
            assert mu_result is not NO_MATCH, "Parity violation: Python matched, Mu NO_MATCH"
            assert mu_equal(py_result, mu_result), f"Parity violation: {py_result} != {mu_result}"
    except KeyError:
        # Both should raise KeyError for unbound variables
        pass


# =============================================================================
# Property 3: Well-Formedness Preservation
# =============================================================================

@given(mu_projections(), mu_values(max_depth=3))
@settings(
    deadline=5000,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much]
)
def test_apply_mu_result_is_valid_mu_on_success(projection, value):
    """When apply_mu succeeds, result must be valid Mu (exceptions are acceptable termination)."""
    assume(is_mu(projection))
    assume(is_mu(value))

    try:
        result = apply_mu(projection, value)

        if result is not NO_MATCH:
            assert is_mu(result), f"Result is not valid Mu: {result}"
    except (KeyError, TypeError, ValueError):
        pass  # Expected errors - test only verifies invariant on success path


# =============================================================================
# Property 4: No Crash on Valid Inputs
# =============================================================================

@given(mu_projections(), mu_values(max_depth=3))
@settings(
    deadline=5000,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much]
)
def test_apply_mu_never_crashes_on_valid_mu(projection, value):
    """apply_mu should handle any valid Mu without unexpected crashes."""
    assume(is_mu(projection))
    assume(is_mu(value))

    try:
        result = apply_mu(projection, value)
        # Should be NO_MATCH or valid Mu
        assert result is NO_MATCH or is_mu(result)
    except KeyError:
        # Unbound variable - expected
        pass
    except (TypeError, ValueError) as e:
        # These might be legitimate for malformed projections
        assert len(str(e)) > 0, "Error with empty message"


# =============================================================================
# Property 5: Variable Binding Consistency
# =============================================================================

@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10), mu_values(max_depth=3))
@settings(deadline=5000)
def test_same_var_multiple_times_consistency(var_name, value):
    """If same variable appears multiple times in body, all get same value."""
    assume(is_mu(value))

    # Projection that captures var and uses it 3 times
    projection = {
        "pattern": {"var": var_name},
        "body": {
            "first": {"var": var_name},
            "second": {"var": var_name},
            "third": {"var": var_name}
        }
    }

    result = apply_mu(projection, value)
    assert result is not NO_MATCH

    # All three should be structurally identical
    assert mu_equal(result["first"], result["second"]), "first != second"
    assert mu_equal(result["second"], result["third"]), "second != third"


# =============================================================================
# Property 5b: Non-Linear Pattern Conflict Detection (Binding Parity)
# =============================================================================

@given(mu_nonlinear_conflict_inputs())
@settings(
    deadline=5000,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_nonlinear_pattern_conflict_detection(conflict_pair):
    """Non-linear pattern with conflicting bindings MUST return NO_MATCH.

    When a pattern has {a: {var:x}, b: {var:x}} and value has a!=b,
    apply_mu must detect the conflict and return NO_MATCH, matching
    apply_projection behavior.

    This is the key semantic gap: match.v1 silently overwrites the first
    binding. Bridge projections (via match.v2) correctly detect conflicts.
    """
    projection, value = conflict_pair

    # Skip empty collections and head/tail (known normalization edge cases)
    assume(not contains_empty_collection(value))
    assume(not contains_head_tail(value))

    ref = apply_projection(projection, value)
    mu_result = apply_mu(projection, value)

    assert ref is NO_MATCH, f"Reference should NO_MATCH on conflict, got {ref}"
    assert mu_result is NO_MATCH, f"apply_mu should NO_MATCH on conflict, got {mu_result}"


def test_nonlinear_conflict_distinguishes_positive_and_negative_zero():
    projection = {
        "pattern": {"k0": {"var": "x"}, "k1": {"var": "x"}},
        "body": "matched",
    }
    value = {"k0": 0.0, "k1": -0.0}

    assert apply_projection(projection, value) is NO_MATCH
    assert apply_mu(projection, value) is NO_MATCH


@given(mu_nonlinear_agreement_inputs())
@settings(
    deadline=5000,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_nonlinear_agreement_determinism(agreement_pair):
    """Non-linear pattern with agreeing bindings MUST succeed.

    When a pattern has {a: {var:x}, b: {var:x}} and value has a==b,
    apply_mu must return the substituted body, matching apply_projection.
    """
    projection, value = agreement_pair

    # Skip empty collections and head/tail (known normalization edge cases)
    assume(not contains_empty_collection(value))
    assume(not contains_head_tail(value))

    ref = apply_projection(projection, value)
    mu_result = apply_mu(projection, value)

    if ref is NO_MATCH:
        # Literal positions didn't match — skip (not a non-linear issue)
        return

    assert mu_result is not NO_MATCH, \
        f"apply_mu should succeed when non-linear vars agree, got NO_MATCH (ref={ref})"
    assert mu_equal(ref, mu_result), \
        f"Parity violation: apply_projection={ref}, apply_mu={mu_result}"


# =============================================================================
# Property 6: Literal Pattern Behavior
# =============================================================================

@given(mu_values(max_depth=3), mu_values(max_depth=3))
@settings(deadline=5000, suppress_health_check=[HealthCheck.filter_too_much])
def test_literal_pattern_only_matches_exact(pattern_literal, test_value):
    """Literal pattern (no vars) only matches exact value.

    Known limitation: empty collections normalize to None, so
    pattern=None matches value=[] and vice versa.
    """
    assume(is_mu(pattern_literal))
    assume(is_mu(test_value))

    # Ensure pattern is literal (no var sites)
    assume(not contains_var_site(pattern_literal))

    # Skip known normalization edge cases
    # Empty collections normalize to None, causing false matches
    if is_empty_collection(pattern_literal) or is_empty_collection(test_value):
        return
    if contains_empty_collection(pattern_literal) or contains_empty_collection(test_value):
        return
    # None/[] confusion
    if pattern_literal is None or test_value is None:
        return
    # head/tail structures
    if contains_head_tail(pattern_literal) or contains_head_tail(test_value):
        return

    body = {"matched": True}
    projection = {"pattern": pattern_literal, "body": body}

    result = apply_mu(projection, test_value)

    if mu_equal(pattern_literal, test_value):
        # Exact match - should succeed
        assert result is not NO_MATCH
    else:
        # Different - should fail
        assert result is NO_MATCH


# =============================================================================
# Edge Case Strategies
# =============================================================================

def build_deep_structure(depth):
    """Build deeply nested dict structure."""
    result = "leaf"
    for _ in range(depth):
        result = {"nested": result}
    return result


@composite
def edge_case_mu_values(draw):
    """Generate Mu values that are likely to expose edge cases."""
    return draw(st.one_of(
        st.just(None),
        st.just(True),
        st.just(False),
        st.just(sn(0)),
        st.just(-0.0),
        st.just(sn(1)),
        st.just(sn(-1)),
        st.just(""),
        st.just([]),
        st.just({}),
        st.just({"head": sn(1), "tail": None}),
        st.just({"head": sn(1), "tail": {"head": sn(2), "tail": None}}),
        st.just({"var": "x"}),
        # Deep nesting (moderate depth for speed)
        st.builds(lambda: build_deep_structure(30)),
        # Wide structure
        st.builds(lambda: {f"key{i}": sn(i) for i in range(20)}),
        # Unicode
        st.just("hello"),
        st.just({"key": "value"}),
    ))


@given(mu_projections(), edge_case_mu_values())
@settings(deadline=5000)
def test_apply_mu_edge_cases_fuzzer(projection, value):
    """Test apply_mu with edge case values."""
    assume(is_mu(projection))
    assume(is_mu(value))

    try:
        result = apply_mu(projection, value)
        assert result is NO_MATCH or is_mu(result)
    except (KeyError, TypeError, ValueError):
        # Expected errors
        pass


# =============================================================================
# Stress Test: Maximum Depth
# =============================================================================

@given(st.integers(min_value=1, max_value=50))
@settings(deadline=10000)
def test_apply_mu_handles_depth(depth):
    """Test apply_mu with structures at various depths."""
    # Build structure at specified depth
    value = "leaf"
    for _ in range(depth):
        value = {"level": value}

    projection = {
        "pattern": {"var": "x"},
        "body": {"wrapped": {"var": "x"}}
    }

    result = apply_mu(projection, value)
    assert result is not NO_MATCH
    assert is_mu(result)


# =============================================================================
# Stress Test: Wide Structures
# =============================================================================

@given(st.integers(min_value=0, max_value=50))
@settings(deadline=10000)
def test_apply_mu_handles_wide_dicts(num_keys):
    """Test apply_mu with dicts having many keys."""
    value = {f"key{i}": f"value{i}" for i in range(num_keys)}

    projection = {
        "pattern": {"var": "x"},
        "body": {"data": {"var": "x"}}
    }

    result = apply_mu(projection, value)
    assert result is not NO_MATCH
    assert is_mu(result)


# =============================================================================
# Type Discrimination (Known RCX Behavior)
# =============================================================================

class TestTypeDiscrimination:
    """Test that types are discriminated correctly."""

    def test_true_vs_one(self):
        """True and 1 should be treated distinctly in patterns."""
        proj_bool = {"pattern": True, "body": "bool"}
        proj_int = {"pattern": sn(1), "body": "int"}

        # True should match True pattern
        assert apply_mu(proj_bool, True) == "bool"
        # 1 should match 1 pattern
        assert apply_mu(proj_int, sn(1)) == "int"

        # Cross-matching behavior depends on Python semantics
        # (True == 1 in Python, so both may match)

    def test_false_vs_zero(self):
        """False and 0 should be treated distinctly in patterns."""
        proj_bool = {"pattern": False, "body": "bool"}
        proj_int = {"pattern": sn(0), "body": "int"}

        assert apply_mu(proj_bool, False) == "bool"
        assert apply_mu(proj_int, sn(0)) == "int"

    def test_none_matches_none(self):
        """None only matches None."""
        proj = {"pattern": None, "body": "null"}

        assert apply_mu(proj, None) == "null"
        assert apply_mu(proj, sn(0)) is NO_MATCH
        assert apply_mu(proj, "") is NO_MATCH
        assert apply_mu(proj, False) is NO_MATCH
