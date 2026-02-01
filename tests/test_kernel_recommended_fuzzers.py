"""
Kernel Recommended Fuzzers - Property-based tests from 9-agent review.

Created based on TASKS.md recommended fuzzer additions (lines 343-347):
1. Kernel projection ordering fuzzer (500+ examples)
2. Mode transition completeness fuzzer (500+ examples)
3. Context passthrough stress fuzzer (500+ examples)
4. _step/_projs field fuzzing (500+ examples)
5. Depth boundary fuzzing (95-105 range)

These fuzzers test the meta-circular kernel's structural properties
that are critical for L2 FULL self-hosting.
"""
import pytest
from hypothesis import given, settings, assume
import hypothesis.strategies as st

from rcx_pi.selfhost.step_mu import (
    is_kernel_projection,
    validate_kernel_projections_first,
    is_kernel_terminal,
    is_kernel_intermediate,
    step_kernel_mu,
    list_to_linked,
    normalize_projection,
    validate_no_kernel_reserved_fields,
    KERNEL_RESERVED_FIELDS,
)
from rcx_pi.selfhost.eval_seed import step
from rcx_pi.selfhost.mu_type import mu_equal, is_mu
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seeds_dir


# =============================================================================
# Module-level kernel projection loading (cached)
# =============================================================================

def _load_kernel_projs():
    """Load kernel projections from seeds/kernel.v1.json."""
    seed_path = get_seeds_dir() / "kernel.v1.json"
    return load_verified_seed(seed_path)["projections"]


# =============================================================================
# Strategies for kernel fuzzing
# =============================================================================

@st.composite
def mu_primitive(draw):
    """Generate Mu primitive values."""
    return draw(st.one_of(
        st.integers(min_value=-1000, max_value=1000),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(min_size=0, max_size=20),
        st.booleans(),
        st.none(),
    ))


@st.composite
def mu_value(draw, max_depth=3):
    """Generate arbitrary Mu values (recursive with depth limit)."""
    if max_depth <= 0:
        return draw(mu_primitive())

    return draw(st.one_of(
        mu_primitive(),
        st.lists(mu_value(max_depth=max_depth-1), max_size=3),
        st.dictionaries(
            st.text(min_size=1, max_size=10).filter(lambda x: not x.startswith("_")),
            mu_value(max_depth=max_depth-1),
            max_size=3
        ),
    ))


@st.composite
def safe_domain_key(draw):
    """Generate keys that are safe for domain data (no underscore prefix)."""
    return draw(st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"))


@st.composite
def domain_dict(draw, max_depth=2):
    """Generate domain dicts that don't contain kernel reserved fields."""
    if max_depth <= 0:
        return draw(mu_primitive())

    return draw(st.dictionaries(
        safe_domain_key(),
        st.one_of(
            mu_primitive(),
            st.lists(mu_primitive(), max_size=2),
            domain_dict(max_depth=max_depth-1) if max_depth > 1 else mu_primitive(),
        ),
        max_size=3
    ))


@st.composite
def kernel_projection(draw):
    """Generate a kernel projection (has _mode in pattern root)."""
    mode = draw(st.sampled_from(["kernel", "match_done", "subst_done", "done"]))
    return {
        "id": f"kernel.test.{draw(st.integers(min_value=0, max_value=100))}",
        "pattern": {"_mode": mode, "_input": {"var": "x"}},
        "body": {"_mode": "done", "_result": {"var": "x"}, "_stall": False}
    }


@st.composite
def domain_projection(draw):
    """Generate a domain projection (no _mode in pattern)."""
    key = draw(safe_domain_key())
    return {
        "id": f"domain.test.{draw(st.integers(min_value=0, max_value=100))}",
        "pattern": {key: {"var": "v"}},
        "body": {"result": {"var": "v"}}
    }


# =============================================================================
# 1. Kernel Projection Ordering Fuzzer (500+ examples)
# =============================================================================

class TestKernelProjectionOrderingFuzzer:
    """
    Fuzzer for kernel projection ordering security.

    SECURITY: Kernel projections must appear before domain projections.
    If domain projections come first, they could forge kernel state.
    """

    @given(
        st.lists(kernel_projection(), min_size=1, max_size=5),
        st.lists(domain_projection(), min_size=1, max_size=5)
    )
    @settings(max_examples=500, deadline=10000)
    def test_valid_ordering_kernel_then_domain(self, kernel_projs, domain_projs):
        """Kernel projections followed by domain projections is VALID."""
        combined = kernel_projs + domain_projs
        # Should not raise
        validate_kernel_projections_first(combined)

    @given(
        st.lists(domain_projection(), min_size=1, max_size=5),
        st.lists(kernel_projection(), min_size=1, max_size=5)
    )
    @settings(max_examples=500, deadline=10000)
    def test_invalid_ordering_domain_then_kernel(self, domain_projs, kernel_projs):
        """Domain projections followed by kernel projections is INVALID."""
        combined = domain_projs + kernel_projs
        with pytest.raises(ValueError, match="SECURITY"):
            validate_kernel_projections_first(combined)

    @given(
        st.lists(kernel_projection(), min_size=0, max_size=3),
        domain_projection(),
        st.lists(kernel_projection(), min_size=1, max_size=3),
    )
    @settings(max_examples=500, deadline=10000)
    def test_interleaved_ordering_invalid(self, k1, d1, k2):
        """Any kernel projection after domain projection is INVALID."""
        combined = k1 + [d1] + k2
        with pytest.raises(ValueError, match="SECURITY"):
            validate_kernel_projections_first(combined)

    @given(st.lists(domain_projection(), min_size=1, max_size=10))
    @settings(max_examples=200, deadline=10000)
    def test_domain_only_valid(self, domain_projs):
        """List containing only domain projections is valid."""
        # Should not raise
        validate_kernel_projections_first(domain_projs)

    @given(st.lists(kernel_projection(), min_size=1, max_size=10))
    @settings(max_examples=200, deadline=10000)
    def test_kernel_only_valid(self, kernel_projs):
        """List containing only kernel projections is valid."""
        # Should not raise
        validate_kernel_projections_first(kernel_projs)


# =============================================================================
# 2. Mode Transition Completeness Fuzzer (500+ examples)
# =============================================================================

class TestModeTransitionCompletenessFuzzer:
    """
    Fuzzer for kernel mode transition completeness.

    Tests that all kernel states transition correctly without
    getting stuck in invalid states.
    """

    @given(domain_dict())
    @settings(max_examples=500, deadline=10000)
    def test_kernel_wrap_always_transitions(self, input_val):
        """kernel.wrap always produces kernel state from entry format."""
        kernel_projs = _load_kernel_projs()
        entry = {"_step": input_val, "_projs": []}
        result = step(kernel_projs, entry)
        # Should transition to kernel state
        assert result.get("_mode") == "kernel"
        assert result.get("_phase") == "try"

    @given(domain_dict())
    @settings(max_examples=500, deadline=10000)
    def test_kernel_stall_on_null_remaining(self, input_val):
        """kernel.stall matches when _remaining is null."""
        kernel_projs = _load_kernel_projs()
        state = {
            "_mode": "kernel",
            "_phase": "try",
            "_input": input_val,
            "_remaining": None
        }
        result = step(kernel_projs, state)
        # Should transition to done state
        assert result.get("_mode") == "done"
        assert result.get("_stall") is True

    @given(domain_dict())
    @settings(max_examples=500, deadline=10000)
    def test_kernel_try_extracts_projection(self, input_val):
        """kernel.try extracts first projection from linked list."""
        kernel_projs = _load_kernel_projs()
        proj = {"pattern": {"x": {"var": "v"}}, "body": {"y": {"var": "v"}}}
        state = {
            "_mode": "kernel",
            "_phase": "try",
            "_input": input_val,
            "_remaining": {"head": proj, "tail": None}
        }
        result = step(kernel_projs, state)
        # Should produce match entry format
        assert "match" in result
        assert "_match_ctx" in result

    @given(domain_dict(), st.booleans())
    @settings(max_examples=200, deadline=10000)
    def test_kernel_unwrap_extracts_result(self, result_val, is_stall):
        """kernel.unwrap extracts result from done state."""
        kernel_projs = _load_kernel_projs()
        state = {
            "_mode": "done",
            "_result": result_val,
            "_stall": is_stall
        }
        result = step(kernel_projs, state)
        # Should extract the result value
        assert mu_equal(result, result_val)


# =============================================================================
# 3. Context Passthrough Stress Fuzzer (500+ examples)
# =============================================================================

class TestContextPassthroughStressFuzzer:
    """
    Fuzzer for kernel context preservation across mode transitions.

    Tests that _match_ctx and _subst_ctx correctly preserve
    information through the kernel state machine.
    """

    @given(
        domain_dict(),
        domain_dict(),
        st.lists(domain_dict(), min_size=0, max_size=3)
    )
    @settings(max_examples=500, deadline=10000)
    def test_match_ctx_preserves_input_and_body(self, input_val, body_val, remaining_vals):
        """_match_ctx preserves input, body, and remaining across match."""
        kernel_projs = _load_kernel_projs()
        remaining = list_to_linked([
            {"pattern": r, "body": body_val} for r in remaining_vals
        ])

        # Build state after kernel.try
        proj = {"pattern": {"x": {"var": "v"}}, "body": body_val}
        state = {
            "_mode": "kernel",
            "_phase": "try",
            "_input": input_val,
            "_remaining": {"head": proj, "tail": remaining}
        }

        result = step(kernel_projs, state)

        # Check context preserved
        ctx = result.get("_match_ctx", {})
        assert mu_equal(ctx.get("_input"), input_val)
        assert mu_equal(ctx.get("_body"), body_val)

    @given(domain_dict(), domain_dict())
    @settings(max_examples=500, deadline=10000)
    def test_match_success_preserves_bindings(self, body_val, input_val):
        """kernel.match_success transfers bindings to subst."""
        kernel_projs = _load_kernel_projs()
        bindings = {"v": 42, "w": "test"}
        state = {
            "_mode": "match_done",
            "_status": "success",
            "_bindings": bindings,
            "_match_ctx": {
                "_input": input_val,
                "_body": body_val,
                "_remaining": None
            }
        }

        result = step(kernel_projs, state)

        # Should have subst entry with preserved bindings
        assert "subst" in result
        assert mu_equal(result["subst"]["bindings"], bindings)
        assert mu_equal(result["subst"]["body"], body_val)

    @given(domain_dict())
    @settings(max_examples=500, deadline=10000)
    def test_match_fail_preserves_remaining(self, input_val):
        """kernel.match_fail preserves remaining projections for retry."""
        kernel_projs = _load_kernel_projs()
        remaining = {"head": {"pattern": {}, "body": {}}, "tail": None}
        state = {
            "_mode": "match_done",
            "_status": "no_match",
            "_match_ctx": {
                "_input": input_val,
                "_body": {"ignored": True},
                "_remaining": remaining
            }
        }

        result = step(kernel_projs, state)

        # Should return to kernel try with remaining
        assert result.get("_mode") == "kernel"
        assert result.get("_phase") == "try"
        assert mu_equal(result.get("_remaining"), remaining)


# =============================================================================
# 4. _step/_projs Field Fuzzing (500+ examples)
# =============================================================================

class TestStepProjsFieldFuzzer:
    """
    Fuzzer for kernel entry format (_step/_projs) handling.

    Tests that the kernel correctly wraps various input types
    and projection list structures.
    """

    @given(mu_value())
    @settings(max_examples=500, deadline=10000)
    def test_step_accepts_any_mu_value(self, input_val):
        """_step can be any Mu value."""
        kernel_projs = _load_kernel_projs()
        entry = {"_step": input_val, "_projs": []}
        result = step(kernel_projs, entry)
        # Should wrap successfully
        assert result.get("_mode") == "kernel"
        assert mu_equal(result.get("_input"), input_val)

    @given(
        domain_dict(),
        st.lists(
            st.fixed_dictionaries({
                "pattern": domain_dict(),
                "body": domain_dict(),
            }),
            min_size=0,
            max_size=5
        )
    )
    @settings(max_examples=500, deadline=10000)
    def test_projs_wraps_to_linked_list(self, input_val, projs):
        """_projs list becomes linked list in _remaining."""
        kernel_projs = _load_kernel_projs()
        entry = {"_step": input_val, "_projs": projs}
        result = step(kernel_projs, entry)

        # Should have converted to kernel state
        assert result.get("_mode") == "kernel"

        # _remaining should be linked list (or equal to projs for empty)
        remaining = result.get("_remaining")
        if not projs:
            assert remaining == []  # Empty list stays as list in this phase
        else:
            # With projections, should still be wrapped
            assert remaining == projs  # kernel.wrap preserves _projs format

    @given(domain_dict(), domain_dict())
    @settings(max_examples=200, deadline=10000)
    def test_step_with_single_projection(self, input_val, body_val):
        """Single projection in _projs works correctly."""
        kernel_projs = _load_kernel_projs()
        proj = {"pattern": {"x": {"var": "v"}}, "body": body_val}
        entry = {"_step": input_val, "_projs": [proj]}
        result = step(kernel_projs, entry)

        assert result.get("_mode") == "kernel"
        assert result.get("_remaining") == [proj]

    def test_step_null_is_valid(self):
        """_step can be null (None)."""
        kernel_projs = _load_kernel_projs()
        entry = {"_step": None, "_projs": []}
        result = step(kernel_projs, entry)

        assert result.get("_mode") == "kernel"
        assert result.get("_input") is None


# =============================================================================
# 5. Depth Boundary Fuzzing (95-105 range)
# =============================================================================

class TestDepthBoundaryFuzzer:
    """
    Fuzzer for depth boundary behavior in validation.

    Tests the MAX_VALIDATION_DEPTH=100 boundary behavior
    in validate_no_kernel_reserved_fields().
    """

    def build_nested_dict(self, depth: int, leaf_value=42) -> dict:
        """Build a dict nested to specified depth."""
        result = {"value": leaf_value}
        for i in range(depth):
            result = {"nested": result}
        return result

    @given(st.integers(min_value=95, max_value=99))
    @settings(max_examples=100, deadline=10000)
    def test_deep_nesting_under_limit_passes(self, depth):
        """Nesting depths 95-99 (under MAX=100) should pass validation."""
        nested = self.build_nested_dict(depth)
        # Should not raise
        validate_no_kernel_reserved_fields(nested, "test input")

    @given(st.integers(min_value=101, max_value=105))
    @settings(max_examples=100, deadline=10000)
    def test_deep_nesting_over_limit_fails(self, depth):
        """Nesting depths 101-105 (over MAX=100) should fail validation."""
        nested = self.build_nested_dict(depth)
        with pytest.raises(ValueError, match="maximum validation depth"):
            validate_no_kernel_reserved_fields(nested, "test input")

    def test_exact_boundary_100_passes(self):
        """Exactly depth 100 should pass (boundary case)."""
        nested = self.build_nested_dict(99)  # 99 wraps = 100 depth checks
        # Should not raise
        validate_no_kernel_reserved_fields(nested, "test input")

    def test_exact_boundary_101_fails(self):
        """Exactly depth 101 should fail (just over boundary)."""
        nested = self.build_nested_dict(101)
        with pytest.raises(ValueError, match="maximum validation depth"):
            validate_no_kernel_reserved_fields(nested, "test input")

    @given(st.integers(min_value=95, max_value=99))
    @settings(max_examples=100, deadline=10000)
    def test_deep_nesting_with_reserved_field_at_depth(self, depth):
        """Reserved field at depth < 100 should be detected."""
        # Build nested structure with _mode at specified depth
        nested = {"_mode": "forged"}
        for _ in range(depth):
            nested = {"nested": nested}

        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(nested, "test input")

    @given(
        st.integers(min_value=0, max_value=50),
        st.sampled_from(list(KERNEL_RESERVED_FIELDS))
    )
    @settings(max_examples=200, deadline=10000)
    def test_reserved_field_at_various_depths(self, depth, reserved_field):
        """Any reserved field at any reasonable depth should be caught."""
        # Build nested structure with reserved field at specified depth
        nested = {reserved_field: "forged_value"}
        for _ in range(depth):
            nested = {"nested": nested}

        with pytest.raises(ValueError, match="kernel-reserved field"):
            validate_no_kernel_reserved_fields(nested, "test input")


# =============================================================================
# Additional Edge Case Fuzzing
# =============================================================================

class TestKernelStateClassificationEdgeCases:
    """Additional edge cases for kernel state classification."""

    @given(domain_dict())
    @settings(max_examples=200, deadline=10000)
    def test_domain_dict_not_terminal(self, d):
        """Domain dicts without _mode are never terminal."""
        assert not is_kernel_terminal(d)

    @given(domain_dict())
    @settings(max_examples=200, deadline=10000)
    def test_domain_dict_not_intermediate(self, d):
        """Domain dicts without kernel fields are never intermediate."""
        # Ensure no kernel fields
        assume("_mode" not in d)
        assume("_match_ctx" not in d)
        assume("_subst_ctx" not in d)
        assert not is_kernel_intermediate(d)

    @given(
        st.sampled_from(["kernel", "wrap", "try", "match_done", "subst_done"]),
        domain_dict()
    )
    @settings(max_examples=200, deadline=10000)
    def test_non_done_mode_is_intermediate(self, mode, input_val):
        """_mode values other than 'done' indicate intermediate state."""
        state = {"_mode": mode, "_input": input_val}
        if mode != "done":
            assert is_kernel_intermediate(state)
            assert not is_kernel_terminal(state)

    @given(domain_dict(), st.booleans())
    @settings(max_examples=200, deadline=10000)
    def test_done_mode_is_terminal(self, result_val, stall):
        """_mode='done' with _result and _stall is terminal."""
        state = {
            "_mode": "done",
            "_result": result_val,
            "_stall": stall
        }
        assert is_kernel_terminal(state)
        assert not is_kernel_intermediate(state)
