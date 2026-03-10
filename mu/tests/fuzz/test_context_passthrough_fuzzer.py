"""
Context Passthrough Fuzzer - Kernel Context Preservation Tests

Property-based tests for context passthrough to ensure:
1. _match_ctx is preserved through kernel match projections
2. _subst_ctx is preserved through kernel subst projections
3. Context fields survive mode transitions
4. No context field corruption or loss
5. Round-trip through kernel preserves context

Context passthrough is a KERNEL-level concern: combined kernel projections
include _match_ctx/_subst_ctx in their patterns. Standalone match/subst
projections do NOT handle context — they have 5/6-key patterns without
context fields. Tests must use load_combined_kernel_projections().
"""

import pytest
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

from rcx_pi.selfhost.step_mu import (
    load_combined_kernel_projections,
    list_to_linked,
    normalize_projection,
)
from rcx_pi.selfhost.projection_runner import make_projection_runner
from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.selfhost.kernel import reset_step_budget
from rcx_pi.selfhost.eval_seed import step


# =============================================================================
# Strategies for generating test inputs
# =============================================================================

# Context values (things that might be in _match_ctx or _subst_ctx)
context_values = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-100, max_value=100),
        st.text(max_size=10),
    ),
    lambda children: st.one_of(
        st.lists(children, max_size=2),
        st.dictionaries(st.text(max_size=5), children, max_size=2),
    ),
    max_leaves=5,
)


@st.composite
def match_contexts(draw):
    """Generate a valid _match_ctx structure."""
    return {
        "_input": draw(context_values),
        "_body": draw(context_values),
        "_remaining": draw(st.one_of(st.none(), context_values)),
    }


@st.composite
def subst_contexts(draw):
    """Generate a valid _subst_ctx structure."""
    return {
        "_input": draw(context_values),
        "_remaining": draw(st.one_of(st.none(), context_values)),
    }


# Simple patterns and values for matching
simple_values = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-100, max_value=100),
    st.text(max_size=10),
)


# =============================================================================
# Match Context Preservation Tests
# =============================================================================

class TestMatchContextPreservation:
    """Test that _match_ctx is preserved through kernel match projections.

    Uses kernel dispatch format: {match: {pattern: P, value: V}, _match_ctx: ctx}
    which triggers kernel projection 14 → match stepping → match_done with ctx.
    """

    def setup_method(self):
        """Reset step budget and load combined kernel projections."""
        reset_step_budget()
        self.kernel_projs = load_combined_kernel_projections()

    @given(ctx=match_contexts())
    @settings(deadline=5000)
    def test_context_preserved_on_equal_match(self, ctx):
        """Context preserved when matching equal values."""
        initial = {
            "match": {"pattern": 42, "value": 42},
            "_match_ctx": ctx,
        }

        _, _, run = make_projection_runner("match", terminal_field="_mode")
        final, steps, is_stall = run(self.kernel_projs, initial, max_steps=200)

        assert not is_stall, f"stalled at step {steps}"
        assert final.get("_mode") == "match_done"
        assert final.get("_status") == "success"
        assert "_match_ctx" in final
        assert mu_equal(final["_match_ctx"], ctx)

    @given(ctx=match_contexts())
    @settings(deadline=5000)
    def test_context_preserved_on_var_match(self, ctx):
        """Context preserved when matching variable."""
        initial = {
            "match": {"pattern": {"var": "x"}, "value": 42},
            "_match_ctx": ctx,
        }

        _, _, run = make_projection_runner("match", terminal_field="_mode")
        final, steps, is_stall = run(self.kernel_projs, initial, max_steps=200)

        assert not is_stall, f"stalled at step {steps}"
        assert final.get("_mode") == "match_done"
        assert final.get("_status") == "success"
        assert "_match_ctx" in final
        assert mu_equal(final["_match_ctx"], ctx)

    @given(ctx=match_contexts())
    @settings(deadline=5000)
    def test_context_preserved_on_match_failure(self, ctx):
        """Context preserved when match fails (5 != 6)."""
        initial = {
            "match": {"pattern": 5, "value": 6},
            "_match_ctx": ctx,
        }

        _, _, run = make_projection_runner("match", terminal_field="_mode")
        final, steps, is_stall = run(self.kernel_projs, initial, max_steps=200)

        assert not is_stall, f"stalled at step {steps}"
        assert final.get("_mode") == "match_done"
        assert final.get("_status") == "no_match"
        assert "_match_ctx" in final
        assert mu_equal(final["_match_ctx"], ctx)


# =============================================================================
# Subst Context Preservation Tests
# =============================================================================

class TestSubstContextPreservation:
    """Test that _subst_ctx is preserved through kernel subst projections.

    Uses kernel dispatch format: {subst: {body: B, bindings: binds}, _subst_ctx: ctx}
    which triggers kernel projection 26 → subst stepping → subst_done with ctx.
    """

    def setup_method(self):
        """Reset step budget and load combined kernel projections."""
        reset_step_budget()
        self.kernel_projs = load_combined_kernel_projections()

    @given(ctx=subst_contexts())
    @settings(deadline=5000)
    def test_context_preserved_on_simple_subst(self, ctx):
        """Context preserved on simple value substitution."""
        initial = {
            "subst": {"body": 42, "bindings": None},
            "_subst_ctx": ctx,
        }

        _, _, run = make_projection_runner("subst", terminal_field="_mode")
        final, steps, is_stall = run(self.kernel_projs, initial, max_steps=200)

        assert not is_stall, f"stalled at step {steps}"
        assert final.get("_mode") == "subst_done"
        assert "_subst_ctx" in final
        assert mu_equal(final["_subst_ctx"], ctx)

    @given(ctx=subst_contexts(), value=simple_values)
    @settings(deadline=5000)
    def test_context_preserved_through_var_lookup(self, ctx, value):
        """Context preserved when looking up variable."""
        bindings = {"name": "x", "value": value, "rest": None}

        initial = {
            "subst": {"body": {"var": "x"}, "bindings": bindings},
            "_subst_ctx": ctx,
        }

        _, _, run = make_projection_runner("subst", terminal_field="_mode")
        final, steps, is_stall = run(self.kernel_projs, initial, max_steps=200)

        assert not is_stall, f"stalled at step {steps}"
        assert final.get("_mode") == "subst_done"
        assert "_subst_ctx" in final
        assert mu_equal(final["_subst_ctx"], ctx)


# =============================================================================
# Mode Transition Context Tests
# =============================================================================

class TestModeTransitionContext:
    """Test context survives mode transitions at the kernel level.

    match_done → step: kernel extracts _match_ctx fields and threads them
    into _subst_ctx for the next phase. subst_done → step: kernel produces
    done state (context consumed — no _subst_ctx in output).
    """

    def setup_method(self):
        """Reset step budget."""
        reset_step_budget()
        self.kernel_projs = load_combined_kernel_projections()

    @given(input_val=simple_values, body=simple_values, remaining=st.one_of(st.none(), simple_values))
    @settings(deadline=5000)
    def test_match_to_kernel_transition(self, input_val, body, remaining):
        """match_done → step threads _match_ctx into _subst_ctx."""
        match_done_state = {
            "_mode": "match_done",
            "_status": "success",
            "_bindings": None,
            "_match_ctx": {
                "_input": input_val,
                "_body": body,
                "_remaining": remaining,
            }
        }

        result = step(self.kernel_projs, match_done_state)

        # Kernel should produce subst dispatch with _subst_ctx threaded from _match_ctx
        assert isinstance(result, dict), f"expected dict, got {type(result)}"
        assert "subst" in result, f"expected subst dispatch, got keys {list(result.keys())}"
        assert "_subst_ctx" in result, "kernel dropped _subst_ctx during match→subst transition"
        assert mu_equal(result["_subst_ctx"]["_input"], input_val)
        assert mu_equal(result["_subst_ctx"]["_remaining"], remaining)

    @given(input_val=simple_values, remaining=st.one_of(st.none(), simple_values))
    @settings(deadline=5000)
    def test_subst_to_kernel_transition(self, input_val, remaining):
        """subst_done → step produces done state (context consumed)."""
        subst_done_state = {
            "_mode": "subst_done",
            "_result": 42,
            "_subst_ctx": {
                "_input": input_val,
                "_remaining": remaining,
            }
        }

        result = step(self.kernel_projs, subst_done_state)

        # Kernel produces done mode — _subst_ctx is consumed (not threaded further)
        assert isinstance(result, dict), f"expected dict, got {type(result)}"
        assert result.get("_mode") == "done", f"expected done mode, got {result.get('_mode')}"
        assert mu_equal(result.get("_result"), 42)


# =============================================================================
# Context Field Integrity Tests
# =============================================================================

class TestContextFieldIntegrity:
    """Test that individual context fields are not corrupted through kernel."""

    def setup_method(self):
        """Reset step budget and load kernel projections."""
        reset_step_budget()
        self.kernel_projs = load_combined_kernel_projections()

    @given(
        input_val=context_values,
        body_val=context_values,
        remaining_val=st.one_of(st.none(), context_values)
    )
    @settings(deadline=5000)
    def test_match_ctx_fields_unchanged(self, input_val, body_val, remaining_val):
        """Individual _match_ctx fields remain unchanged through match."""
        ctx = {
            "_input": input_val,
            "_body": body_val,
            "_remaining": remaining_val,
        }

        initial = {
            "match": {"pattern": {"var": "x"}, "value": 42},
            "_match_ctx": ctx,
        }

        _, _, run = make_projection_runner("match", terminal_field="_mode")
        final, steps, is_stall = run(self.kernel_projs, initial, max_steps=200)

        assert not is_stall, f"stalled at step {steps}"
        assert final.get("_mode") == "match_done"
        assert "_match_ctx" in final
        final_ctx = final["_match_ctx"]
        assert mu_equal(final_ctx.get("_input"), input_val)
        assert mu_equal(final_ctx.get("_body"), body_val)
        assert mu_equal(final_ctx.get("_remaining"), remaining_val)

    @given(
        input_val=context_values,
        remaining_val=st.one_of(st.none(), context_values)
    )
    @settings(deadline=5000)
    def test_subst_ctx_fields_unchanged(self, input_val, remaining_val):
        """Individual _subst_ctx fields remain unchanged through subst."""
        ctx = {
            "_input": input_val,
            "_remaining": remaining_val,
        }

        initial = {
            "subst": {"body": 42, "bindings": None},
            "_subst_ctx": ctx,
        }

        _, _, run = make_projection_runner("subst", terminal_field="_mode")
        final, steps, is_stall = run(self.kernel_projs, initial, max_steps=200)

        assert not is_stall, f"stalled at step {steps}"
        assert final.get("_mode") == "subst_done"
        assert "_subst_ctx" in final
        final_ctx = final["_subst_ctx"]
        assert mu_equal(final_ctx.get("_input"), input_val)
        assert mu_equal(final_ctx.get("_remaining"), remaining_val)


# =============================================================================
# Adversarial Context Tests
# =============================================================================

class TestAdversarialContexts:
    """Test with adversarial context values through kernel projections."""

    def setup_method(self):
        """Reset step budget and load kernel projections."""
        reset_step_budget()
        self.kernel_projs = load_combined_kernel_projections()

    def test_empty_context(self):
        """Empty context dict is preserved through match."""
        ctx = {}

        initial = {
            "match": {"pattern": 42, "value": 42},
            "_match_ctx": ctx,
        }

        _, _, run = make_projection_runner("match", terminal_field="_mode")
        final, steps, is_stall = run(self.kernel_projs, initial, max_steps=200)

        assert not is_stall, f"stalled at step {steps}"
        assert final.get("_mode") == "match_done"
        assert "_match_ctx" in final
        assert final["_match_ctx"] == {}

    def test_deeply_nested_context(self):
        """Deeply nested context is preserved through match."""
        nested = {"level": 1}
        for i in range(2, 6):
            nested = {"level": i, "inner": nested}

        ctx = {"_input": nested, "_body": None, "_remaining": None}

        initial = {
            "match": {"pattern": 42, "value": 42},
            "_match_ctx": ctx,
        }

        _, _, run = make_projection_runner("match", terminal_field="_mode")
        final, steps, is_stall = run(self.kernel_projs, initial, max_steps=200)

        assert not is_stall, f"stalled at step {steps}"
        assert final.get("_mode") == "match_done"
        assert "_match_ctx" in final
        assert mu_equal(final["_match_ctx"]["_input"], nested)

    def test_context_with_special_keys(self):
        """Context with special key names is preserved through match."""
        ctx = {
            "_input": {"_mode": "fake", "_phase": "also_fake"},
            "_body": {"var": "x"},
            "_remaining": None,
        }

        initial = {
            "match": {"pattern": 42, "value": 42},
            "_match_ctx": ctx,
        }

        _, _, run = make_projection_runner("match", terminal_field="_mode")
        final, steps, is_stall = run(self.kernel_projs, initial, max_steps=200)

        assert not is_stall, f"stalled at step {steps}"
        assert final.get("_mode") == "match_done"
        assert "_match_ctx" in final
        assert final["_match_ctx"]["_input"]["_mode"] == "fake"
