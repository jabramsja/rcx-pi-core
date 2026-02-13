"""
Deep Fuzzer Stress Tests - Comprehensive Edge Case Coverage

These tests probe deep nesting and wide structures that are too slow
for regular CI but important for thorough validation.

Run separately:
    pytest tests/stress/ -v --timeout=300

These tests are EXCLUDED from:
- audit_fast.sh (fast iteration)
- pre-commit hooks

They ARE included in:
- audit_all.sh (full validation)
- CI deep test job (if configured)

See docs/TESTING_PERFORMANCE_ISSUE.md for context.
"""

import pytest
import time

# Skip if hypothesis not installed
hypothesis = pytest.importorskip("hypothesis", reason="hypothesis required")

from hypothesis import given, strategies as st, settings, assume, HealthCheck
from hypothesis.strategies import composite

from rcx_pi.selfhost.mu_type import (
    is_mu,
    mu_equal,
    mu_hash,
    MAX_MU_DEPTH,
)
from rcx_pi.selfhost.step_mu import run_mu
from rcx_pi.selfhost.match_mu import normalize_for_match, denormalize_from_match


# =============================================================================
# Deep Value Generators
# =============================================================================

mu_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**31), max_value=2**31),
    st.text(max_size=20),
)


@composite
def deep_mu_values(draw, max_depth=5):
    """Generate deeper Mu values for stress testing.

    Unlike the regular mu_values(max_depth=3), this generates structures
    up to depth 5, which after normalization can reach depth 10+.
    """
    if max_depth <= 0:
        return draw(mu_primitives)

    return draw(st.one_of(
        mu_primitives,
        st.lists(
            st.deferred(lambda: deep_mu_values(max_depth=max_depth-1)),
            max_size=3
        ),
        st.dictionaries(
            st.text(min_size=1, max_size=5),
            st.deferred(lambda: deep_mu_values(max_depth=max_depth-1)),
            max_size=3
        ),
    ))


def build_nested_list(depth: int, leaf=42):
    """Build a list nested to specified depth."""
    result = leaf
    for _ in range(depth):
        result = [result]
    return result


def build_nested_dict(depth: int, leaf=42):
    """Build a dict nested to specified depth."""
    result = leaf
    for _ in range(depth):
        result = {"nested": result}
    return result


# =============================================================================
# Stress Tests: Normalization Roundtrip
# =============================================================================

class TestNormalizationDeepStress:
    """Stress tests for normalization with deep structures."""

    @given(deep_mu_values(max_depth=5))
    @settings(
        max_examples=50,
        deadline=30000,  # 30 seconds per example
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_deep_normalization_roundtrip(self, value):
        """Normalization roundtrip works for deep structures."""
        assume(is_mu(value))

        normalized = normalize_for_match(value)
        assert is_mu(normalized), "Normalized value must be valid Mu"

        denormalized = denormalize_from_match(normalized)
        assert mu_equal(value, denormalized), "Roundtrip must preserve value"

    @given(st.integers(min_value=50, max_value=MAX_MU_DEPTH - 20))
    @settings(
        max_examples=20,
        deadline=60000,  # 60 seconds per example
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_near_max_depth_list(self, depth):
        """Normalization handles lists near MAX_MU_DEPTH."""
        value = build_nested_list(depth)

        normalized = normalize_for_match(value)
        denormalized = denormalize_from_match(normalized)

        assert mu_equal(value, denormalized), f"Roundtrip failed at depth {depth}"

    @given(st.integers(min_value=30, max_value=80))
    @settings(
        max_examples=20,
        deadline=60000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_near_max_depth_dict(self, depth):
        """Normalization handles dicts near MAX_MU_DEPTH.

        Note: Dicts roughly double depth after normalization (linked list of pairs).
        So depth=80 becomes ~160 after normalization.
        """
        value = build_nested_dict(depth)

        normalized = normalize_for_match(value)
        denormalized = denormalize_from_match(normalized)

        assert mu_equal(value, denormalized), f"Roundtrip failed at depth {depth}"


# =============================================================================
# Stress Tests: run_mu with Pathological Projections
# =============================================================================

class TestRunMuDeepStress:
    """Stress tests for run_mu with deep nesting projections."""

    @given(st.integers(min_value=30, max_value=80))
    @settings(
        max_examples=20,
        deadline=60000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_double_projection_deep(self, max_steps):
        """The "double" projection that wraps deeper each step.

        This is the pathological case that caused fuzzer hangs.
        We test it here with higher limits to ensure it completes.
        """
        double = {"pattern": {"var": "x"}, "body": {"doubled": {"var": "x"}}}

        start = time.time()
        result, trace, is_stall = run_mu([double], 100, max_steps=max_steps)
        elapsed = time.time() - start

        # Should complete (not stall - keeps wrapping)
        assert not is_stall, "Double projection should not stall"
        assert len(trace) == max_steps + 1, f"Should run exactly {max_steps} steps"

        # Result should be deeply nested
        assert is_mu(result), "Result must be valid Mu"

    @given(st.integers(min_value=100, max_value=500))
    @settings(
        max_examples=10,
        deadline=120000,  # 2 minutes
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_oscillation_max_steps(self, max_steps):
        """Oscillation (A->B->A) hits max_steps correctly.

        Known limitation: oscillation is not detected as stall.
        This test verifies it completes via max_steps.
        """
        toggle = [
            {"pattern": 0, "body": 1},
            {"pattern": 1, "body": 0},
        ]

        result, trace, is_stall = run_mu(toggle, 0, max_steps=max_steps)

        # Should NOT stall (oscillates forever)
        assert not is_stall, "Oscillation should not be detected as stall"
        assert len(trace) == max_steps + 1


# =============================================================================
# Perf Regression: match() validate-once optimization
# =============================================================================

class TestMatchValidateOnceRegression:
    """Perf regression gate for the match() validate-once refactor.

    Before the refactor, run_mu with 60 steps of the "double" projection
    took >120s due to O(N²) assert_mu calls inside match().
    After: <20s. This test enforces the perf bound.
    """

    def test_double_projection_60_steps_under_20s(self):
        """Deterministic perf gate: 60 steps of double projection in <20s."""
        double = {"pattern": {"var": "x"}, "body": {"doubled": {"var": "x"}}}

        start = time.time()
        result, trace, is_stall = run_mu([double], 100, max_steps=60)
        elapsed = time.time() - start

        assert not is_stall
        assert len(trace) == 61
        assert is_mu(result)
        assert elapsed < 20.0, (
            f"run_mu(double, max_steps=60) took {elapsed:.1f}s (limit: 20s). "
            f"match() validate-once optimization may have regressed."
        )


class TestMatchBoundaryValidation:
    """Correctness: match() still rejects invalid Mu at the public boundary."""

    def test_match_rejects_non_mu_pattern(self):
        """match() raises TypeError for non-Mu pattern."""
        from rcx_pi.selfhost.eval_seed import match
        with pytest.raises(TypeError, match="match.pattern"):
            match(set(), "hello")

    def test_match_rejects_non_mu_input(self):
        """match() raises TypeError for non-Mu input."""
        from rcx_pi.selfhost.eval_seed import match
        with pytest.raises(TypeError, match="match.input"):
            match("hello", set())

    def test_match_still_works_for_valid_mu(self):
        """match() correctly matches valid Mu after refactor."""
        from rcx_pi.selfhost.eval_seed import match, NO_MATCH

        # Variable match
        result = match({"var": "x"}, 42)
        assert result == {"x": 42}

        # Literal match
        result = match(42, 42)
        assert result == {}

        # Literal mismatch
        result = match(42, 99)
        assert result is NO_MATCH

        # Dict match
        result = match({"a": {"var": "x"}}, {"a": 1})
        assert result == {"x": 1}

        # List match
        result = match([{"var": "x"}, {"var": "y"}], [1, 2])
        assert result == {"x": 1, "y": 2}


class TestHybridMatchPerimeter:
    """Perimeter tests for the Hybrid trust architecture.

    Verifies:
    - Public match() is ALWAYS strict (never weakened)
    - apply_projection() and step() reject forged kernel-like non-Mu inputs
    - Known kernel modes + shallow type check make forgery fail-closed
    - Legitimate kernel states still use the fast path
    """

    # -- match() always strict --

    def test_match_validates_crafted_domain_with_mode_key(self):
        """match() still validates even if domain value has _mode key."""
        from rcx_pi.selfhost.eval_seed import match
        crafted = {"_mode": "kernel", "bad": set()}
        with pytest.raises(TypeError, match="match.input"):
            match({"var": "x"}, crafted)

    def test_match_validates_unknown_mode(self):
        """match() validates dicts with unknown _mode values."""
        from rcx_pi.selfhost.eval_seed import match
        crafted = {"_mode": "evil", "payload": set()}
        with pytest.raises(TypeError, match="match.input"):
            match({"var": "x"}, crafted)

    # -- Forged kernel-like inputs fail closed in apply_projection --

    def test_apply_projection_rejects_forged_kernel_with_non_mu(self):
        """CRITICAL: forged kernel-like dict with non-Mu payload must fail closed.

        Regression guard: a dict with _mode="kernel" but set() value must NOT
        bypass assert_mu validation. The caller-trust model ensures public
        API always validates via assert_mu.
        """
        from rcx_pi.selfhost.eval_seed import apply_projection
        projection = {"id": "t", "pattern": {"var": "x"}, "body": {"var": "x"}}
        forged = {"_mode": "kernel", "payload": set()}  # set() not Mu
        with pytest.raises(TypeError, match="apply.input"):
            apply_projection(projection, forged)

    def test_apply_projection_rejects_unknown_mode_with_non_mu(self):
        """Unknown mode string with non-Mu is rejected (not a known kernel mode)."""
        from rcx_pi.selfhost.eval_seed import apply_projection
        projection = {"id": "t", "pattern": {"var": "x"}, "body": {"var": "x"}}
        forged = {"_mode": "evil_mode", "payload": set()}
        with pytest.raises(TypeError, match="apply.input"):
            apply_projection(projection, forged)

    # -- Forged inputs fail closed in step() --

    def test_step_rejects_forged_kernel_with_non_mu(self):
        """step() rejects forged kernel-like dict with non-Mu payload."""
        from rcx_pi.selfhost.eval_seed import step
        projs = [{"id": "t", "pattern": {"var": "x"}, "body": {"var": "x"}}]
        forged = {"_mode": "kernel", "payload": set()}
        with pytest.raises(TypeError, match="step.input"):
            step(projs, forged)

    # -- Public API always validates (caller-trust model) --

    def test_apply_projection_validates_kernel_looking_state(self):
        """apply_projection() validates even kernel-shaped dicts (caller-trust model).

        Kernel states are valid Mu, so validation passes — but it always runs.
        Trust is explicit via _apply_projection_trusted(), not shape-inferred.
        """
        from rcx_pi.selfhost.eval_seed import apply_projection, NO_MATCH
        projection = {
            "id": "test",
            "pattern": {"_mode": "kernel", "value": {"var": "v"}},
            "body": {"var": "v"},
        }
        # Valid Mu kernel state — passes validation, then matches
        kernel_state = {"_mode": "kernel", "value": 42}
        assert apply_projection(projection, kernel_state) == 42

        kernel_state_miss = {"_mode": "done", "value": 42}
        assert apply_projection(projection, kernel_state_miss) is NO_MATCH

    def test_apply_projection_rejects_non_mu_always(self):
        """Non-Mu values always rejected by apply_projection (no shape bypass)."""
        from rcx_pi.selfhost.eval_seed import apply_projection
        projection = {"id": "t", "pattern": {"var": "x"}, "body": {"var": "x"}}
        with pytest.raises(TypeError, match="apply.input"):
            apply_projection(projection, set())

    # -- Behavioral tests through public API --
    # (Tests assert observable behavior through public API)

    def test_apply_projection_rejects_non_dict_input(self):
        """Non-dict non-Mu values are always rejected by apply_projection."""
        from rcx_pi.selfhost.eval_seed import apply_projection
        projection = {"id": "t", "pattern": {"var": "x"}, "body": {"var": "x"}}
        with pytest.raises(TypeError):
            apply_projection(projection, set())

    def test_apply_projection_rejects_unknown_mode_cleanly(self):
        """Dict with unknown _mode and valid Mu values goes through strict path."""
        from rcx_pi.selfhost.eval_seed import apply_projection, NO_MATCH
        projection = {"id": "t", "pattern": {"_mode": "evil", "x": {"var": "v"}}, "body": {"var": "v"}}
        # Unknown mode — goes through strict match(), which validates. Dict IS valid Mu, so
        # it should match (or not) without error, just won't use fast path.
        result = apply_projection(projection, {"_mode": "evil", "x": 42})
        assert result == 42  # match succeeds through strict path

    def test_step_processes_match_subst_context_states(self):
        """States with _match_ctx/_subst_ctx context keys are accepted by step."""
        from rcx_pi.selfhost.eval_seed import step
        projs = [{"id": "t", "pattern": {"_match_ctx": {"var": "c"}}, "body": {"var": "c"}}]
        match_state = {"_match_ctx": {"saved": "data"}}
        result = step(projs, match_state)
        assert result == {"saved": "data"}

    def test_forged_context_key_with_non_mu_rejected(self):
        """Forged dict with _match_ctx but non-Mu payload is rejected."""
        from rcx_pi.selfhost.eval_seed import apply_projection
        projection = {"id": "t", "pattern": {"var": "x"}, "body": {"var": "x"}}
        forged = {"_match_ctx": {}, "bad": set()}
        with pytest.raises(TypeError):
            apply_projection(projection, forged)

    def test_nested_non_mu_in_kernel_shape_rejected(self):
        """CRITICAL: nested non-Mu in kernel-shaped dict rejected by step().

        Regression test for the trust-bypass gap: {"_mode":"kernel","bad":[{1,2}]}
        has valid Mu types at the top level (list is Mu) but contains set() nested
        inside. With caller-trust model, step() always validates — catches this.
        """
        from rcx_pi.selfhost.eval_seed import step
        projs = [{"id": "t", "pattern": {"var": "x"}, "body": {"var": "x"}}]
        forged = {"_mode": "kernel", "bad": [{1, 2}]}
        with pytest.raises(TypeError, match="step.input"):
            step(projs, forged)


# =============================================================================
# Stress Tests: mu_equal Performance
# =============================================================================

class TestMuEqualDeepStress:
    """Stress tests for mu_equal on deep structures."""

    @given(st.integers(min_value=50, max_value=150))
    @settings(
        max_examples=30,
        deadline=30000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_mu_equal_deep_identical(self, depth):
        """mu_equal handles deep identical structures."""
        value = build_nested_list(depth)

        assert mu_equal(value, value), "Value should equal itself"

    @given(st.integers(min_value=50, max_value=150))
    @settings(
        max_examples=30,
        deadline=30000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_mu_equal_deep_different(self, depth):
        """mu_equal correctly distinguishes deep structures."""
        value1 = build_nested_list(depth, leaf=1)
        value2 = build_nested_list(depth, leaf=2)

        assert not mu_equal(value1, value2), "Different leaves should not be equal"

    @given(st.integers(min_value=50, max_value=150))
    @settings(
        max_examples=30,
        deadline=30000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_mu_hash_deep_consistent(self, depth):
        """mu_hash is consistent for deep structures."""
        value = build_nested_list(depth)

        hash1 = mu_hash(value)
        hash2 = mu_hash(value)

        assert hash1 == hash2, "Hash must be deterministic"


# =============================================================================
# Stress Tests: Wide Structures
# =============================================================================

class TestWideStructureStress:
    """Stress tests for wide (many keys/elements) structures."""

    @given(st.integers(min_value=100, max_value=500))
    @settings(
        max_examples=20,
        deadline=60000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_wide_list_normalization(self, width):
        """Normalization handles wide lists."""
        value = list(range(width))

        normalized = normalize_for_match(value)
        denormalized = denormalize_from_match(normalized)

        assert mu_equal(value, denormalized), f"Roundtrip failed at width {width}"

    @given(st.integers(min_value=50, max_value=200))
    @settings(
        max_examples=20,
        deadline=60000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_wide_dict_normalization(self, width):
        """Normalization handles wide dicts."""
        value = {f"key_{i}": i for i in range(width)}

        normalized = normalize_for_match(value)
        denormalized = denormalize_from_match(normalized)

        assert mu_equal(value, denormalized), f"Roundtrip failed at width {width}"
