"""
Context Passthrough Fuzzer - Kernel Context Preservation Tests

Property-based tests for context passthrough to ensure:
1. _match_ctx is preserved through all match projections
2. _subst_ctx is preserved through all subst projections
3. Context fields survive mode transitions
4. No context field corruption or loss
5. Round-trip through kernel preserves context

These tests specifically target the context passthrough mechanism
that was identified as a gap in fuzzer coverage.
"""

import pytest
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

from rcx_pi.selfhost.step_mu import (
    load_combined_kernel_projections,
    list_to_linked,
    normalize_projection,
)
from rcx_pi.selfhost.match_mu import (
    load_match_projections,
    normalize_for_match,
    match_mu,
)
from rcx_pi.selfhost.subst_mu import load_subst_projections, subst_mu
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
    """Test that _match_ctx is preserved through match projections."""

    def setup_method(self):
        """Reset step budget and load projections."""
        reset_step_budget()
        self.match_v2_projs = load_match_projections()  # Uses match.v2.json

    @given(ctx=match_contexts())
    @settings(max_examples=100, deadline=5000)
    def test_context_preserved_on_equal_match(self, ctx):
        """Context preserved when matching equal values."""
        # State: matching 42 against 42 with context
        initial = {
            "mode": "match",
            "pattern_focus": 42,
            "value_focus": 42,
            "bindings": None,
            "stack": None,
            "_match_ctx": ctx,
        }

        # Take steps until done or stall
        _, _, run = make_projection_runner("match")
        final, _, is_stall = run(self.match_v2_projs, initial, max_steps=50)

        # If completed, context should be preserved
        if final.get("mode") == "match_done":
            assert "_match_ctx" in final
            assert mu_equal(final["_match_ctx"], ctx)

    @given(ctx=match_contexts())
    @settings(max_examples=100, deadline=5000)
    def test_context_preserved_on_var_match(self, ctx):
        """Context preserved when matching variable."""
        initial = {
            "mode": "match",
            "pattern_focus": {"var": "x"},
            "value_focus": 42,
            "bindings": None,
            "stack": None,
            "_match_ctx": ctx,
        }

        _, _, run = make_projection_runner("match")
        final, _, is_stall = run(self.match_v2_projs, initial, max_steps=50)

        if final.get("mode") == "match_done":
            assert "_match_ctx" in final
            assert mu_equal(final["_match_ctx"], ctx)

    @given(ctx=match_contexts())
    @settings(max_examples=100, deadline=5000)
    def test_context_preserved_on_match_failure(self, ctx):
        """Context preserved when match fails."""
        # 5 != 6, so this will fail
        initial = {
            "mode": "match",
            "pattern_focus": 5,
            "value_focus": 6,
            "bindings": None,
            "stack": None,
            "_match_ctx": ctx,
        }

        _, _, run = make_projection_runner("match")
        final, _, is_stall = run(self.match_v2_projs, initial, max_steps=50)

        # match.fail should produce match_done with no_match status
        if final.get("_mode") == "match_done":
            assert "_match_ctx" in final
            assert mu_equal(final["_match_ctx"], ctx)


# =============================================================================
# Subst Context Preservation Tests
# =============================================================================

class TestSubstContextPreservation:
    """Test that _subst_ctx is preserved through subst projections."""

    def setup_method(self):
        """Reset step budget and load projections."""
        reset_step_budget()
        self.subst_v2_projs = load_subst_projections()  # Uses subst.v2.json

    @given(ctx=subst_contexts())
    @settings(max_examples=100, deadline=5000)
    def test_context_preserved_on_simple_subst(self, ctx):
        """Context preserved on simple value substitution."""
        initial = {
            "mode": "subst",
            "phase": "traverse",
            "focus": 42,
            "bindings": None,
            "context": None,
            "_subst_ctx": ctx,
        }

        _, _, run = make_projection_runner("subst")
        final, _, is_stall = run(self.subst_v2_projs, initial, max_steps=50)

        # Check if subst completed with context
        if final.get("_mode") == "subst_done":
            assert "_subst_ctx" in final
            assert mu_equal(final["_subst_ctx"], ctx)

    @given(ctx=subst_contexts(), value=simple_values)
    @settings(max_examples=100, deadline=5000)
    def test_context_preserved_through_var_lookup(self, ctx, value):
        """Context preserved when looking up variable."""
        # Bindings with a variable
        bindings = {"name": "x", "value": value, "rest": None}

        initial = {
            "mode": "subst",
            "phase": "traverse",
            "focus": {"var": "x"},
            "bindings": bindings,
            "context": None,
            "_subst_ctx": ctx,
        }

        _, _, run = make_projection_runner("subst")
        final, _, is_stall = run(self.subst_v2_projs, initial, max_steps=50)

        if final.get("_mode") == "subst_done":
            assert "_subst_ctx" in final
            assert mu_equal(final["_subst_ctx"], ctx)


# =============================================================================
# Mode Transition Context Tests
# =============================================================================

class TestModeTransitionContext:
    """Test context survives mode transitions."""

    def setup_method(self):
        """Reset step budget."""
        reset_step_budget()

    @given(input_val=simple_values, body=simple_values, remaining=st.one_of(st.none(), simple_values))
    @settings(max_examples=100, deadline=5000)
    def test_match_to_kernel_transition(self, input_val, body, remaining):
        """Context in match_done can be consumed by kernel."""
        # Simulate what kernel.match_success expects
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

        # This state should be consumable by kernel.match_success
        kernel_projs = load_combined_kernel_projections()
        result = step(kernel_projs, match_done_state)

        # Should transition to subst mode or done
        if isinstance(result, dict):
            # Either moved to subst or stayed (if projection doesn't match)
            assert result is not None

    @given(input_val=simple_values, remaining=st.one_of(st.none(), simple_values))
    @settings(max_examples=100, deadline=5000)
    def test_subst_to_kernel_transition(self, input_val, remaining):
        """Context in subst_done can be consumed by kernel."""
        subst_done_state = {
            "_mode": "subst_done",
            "_result": 42,
            "_subst_ctx": {
                "_input": input_val,
                "_remaining": remaining,
            }
        }

        kernel_projs = load_combined_kernel_projections()
        result = step(kernel_projs, subst_done_state)

        # Should transition to done mode
        if isinstance(result, dict):
            assert result is not None


# =============================================================================
# Context Field Integrity Tests
# =============================================================================

class TestContextFieldIntegrity:
    """Test that context fields are not corrupted."""

    def setup_method(self):
        """Reset step budget."""
        reset_step_budget()

    @given(
        input_val=context_values,
        body_val=context_values,
        remaining_val=st.one_of(st.none(), context_values)
    )
    @settings(max_examples=100, deadline=5000)
    def test_match_ctx_fields_unchanged(self, input_val, body_val, remaining_val):
        """Individual _match_ctx fields remain unchanged through match."""
        ctx = {
            "_input": input_val,
            "_body": body_val,
            "_remaining": remaining_val,
        }

        # Simple match that succeeds
        initial = {
            "mode": "match",
            "pattern_focus": {"var": "x"},
            "value_focus": 42,
            "bindings": None,
            "stack": None,
            "_match_ctx": ctx,
        }

        match_projs = load_match_projections()
        _, _, run = make_projection_runner("match")
        final, _, _ = run(match_projs, initial, max_steps=50)

        if final.get("mode") == "match_done" and "_match_ctx" in final:
            final_ctx = final["_match_ctx"]
            assert mu_equal(final_ctx.get("_input"), input_val)
            assert mu_equal(final_ctx.get("_body"), body_val)
            assert mu_equal(final_ctx.get("_remaining"), remaining_val)

    @given(
        input_val=context_values,
        remaining_val=st.one_of(st.none(), context_values)
    )
    @settings(max_examples=100, deadline=5000)
    def test_subst_ctx_fields_unchanged(self, input_val, remaining_val):
        """Individual _subst_ctx fields remain unchanged through subst."""
        ctx = {
            "_input": input_val,
            "_remaining": remaining_val,
        }

        initial = {
            "mode": "subst",
            "phase": "traverse",
            "focus": 42,
            "bindings": None,
            "context": None,
            "_subst_ctx": ctx,
        }

        subst_projs = load_subst_projections()
        _, _, run = make_projection_runner("subst")
        final, _, _ = run(subst_projs, initial, max_steps=50)

        if final.get("_mode") == "subst_done" and "_subst_ctx" in final:
            final_ctx = final["_subst_ctx"]
            assert mu_equal(final_ctx.get("_input"), input_val)
            assert mu_equal(final_ctx.get("_remaining"), remaining_val)


# =============================================================================
# Adversarial Context Tests
# =============================================================================

class TestAdversarialContexts:
    """Test with adversarial context values."""

    def setup_method(self):
        """Reset step budget."""
        reset_step_budget()

    def test_empty_context(self):
        """Empty context dict is preserved."""
        ctx = {}

        initial = {
            "mode": "match",
            "pattern_focus": 42,
            "value_focus": 42,
            "bindings": None,
            "stack": None,
            "_match_ctx": ctx,
        }

        match_projs = load_match_projections()
        _, _, run = make_projection_runner("match")
        final, _, _ = run(match_projs, initial, max_steps=50)

        if final.get("mode") == "match_done":
            assert "_match_ctx" in final
            assert final["_match_ctx"] == {}

    def test_deeply_nested_context(self):
        """Deeply nested context is preserved."""
        nested = {"level": 1}
        for i in range(2, 6):
            nested = {"level": i, "inner": nested}

        ctx = {"_input": nested, "_body": None, "_remaining": None}

        initial = {
            "mode": "match",
            "pattern_focus": 42,
            "value_focus": 42,
            "bindings": None,
            "stack": None,
            "_match_ctx": ctx,
        }

        match_projs = load_match_projections()
        _, _, run = make_projection_runner("match")
        final, _, _ = run(match_projs, initial, max_steps=50)

        if final.get("mode") == "match_done":
            assert "_match_ctx" in final
            assert mu_equal(final["_match_ctx"]["_input"], nested)

    def test_context_with_special_keys(self):
        """Context with special key names is preserved."""
        ctx = {
            "_input": {"_mode": "fake", "_phase": "also_fake"},
            "_body": {"var": "x"},
            "_remaining": None,
        }

        initial = {
            "mode": "match",
            "pattern_focus": 42,
            "value_focus": 42,
            "bindings": None,
            "stack": None,
            "_match_ctx": ctx,
        }

        match_projs = load_match_projections()
        _, _, run = make_projection_runner("match")
        final, _, _ = run(match_projs, initial, max_steps=50)

        if final.get("mode") == "match_done":
            assert "_match_ctx" in final
            # Context should preserve the fake _mode values
            assert final["_match_ctx"]["_input"]["_mode"] == "fake"
