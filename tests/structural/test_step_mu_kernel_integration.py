"""
Grounding tests for step_mu → kernel projection integration.

These tests prove that step_mu actually uses kernel.v1.json projections,
not just loads them. They are executable proofs of the Phase 7d-1 claim:
"step_mu() delegates to step_kernel_mu() which uses kernel projections for selection."

Critical gaps addressed:
1. Verify step_mu uses kernel projections (not just loads them)
2. Verify projection order is enforced at runtime
3. Verify kernel stall path is complete (kernel.stall → kernel.unwrap)
4. Verify KERNEL_RESERVED_FIELDS boundary validation works
"""

import pytest
from unittest.mock import patch, MagicMock

from rcx_pi.selfhost.step_mu import (
    step_mu,
    step_kernel_mu,
    load_combined_kernel_projections,
    validate_no_kernel_reserved_fields,
    KERNEL_RESERVED_FIELDS,
)
from rcx_pi.selfhost.eval_seed import step as eval_step
from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.selfhost.kernel import reset_step_budget


# =============================================================================
# Test: step_mu Uses Kernel Projections
# =============================================================================

class TestStepMuUsesKernelProjections:
    """Verify step_mu execution path includes kernel projections."""

    def setup_method(self):
        """Reset step budget before each test."""
        reset_step_budget()

    def test_step_mu_calls_step_kernel_mu(self):
        """step_mu delegates to step_kernel_mu for execution."""
        with patch('rcx_pi.selfhost.step_mu.step_kernel_mu') as mock_kernel:
            mock_kernel.return_value = 42

            result = step_mu([{"pattern": {"var": "x"}, "body": {"result": {"var": "x"}}}], 100)

            # step_kernel_mu should have been called
            assert mock_kernel.called
            # Result should be what step_kernel_mu returned
            assert result == 42

    def test_step_kernel_mu_loads_combined_projections(self):
        """step_kernel_mu loads kernel + match.v2 + subst.v2 projections."""
        with patch('rcx_pi.selfhost.step_mu.load_combined_kernel_projections') as mock_load:
            # Return minimal valid projections
            mock_load.return_value = []

            # This will stall immediately with empty projections
            try:
                step_kernel_mu([], 42)
            except Exception:
                pass  # May fail, but we just want to verify load was called

            assert mock_load.called

    def test_step_kernel_mu_calls_eval_step_with_kernel_projs(self):
        """step_kernel_mu uses eval_step with kernel projections."""
        kernel_projs = load_combined_kernel_projections()

        calls = []
        original_eval_step = eval_step

        def tracking_eval_step(projs, state):
            calls.append({"projs_count": len(projs), "state_keys": set(state.keys()) if isinstance(state, dict) else None})
            return original_eval_step(projs, state)

        with patch('rcx_pi.selfhost.step_mu.eval_step', side_effect=tracking_eval_step):
            # Simple projection that matches
            result = step_kernel_mu([{"pattern": {"var": "x"}, "body": {"result": {"var": "x"}}}], 42)

        # Should have made calls to eval_step
        assert len(calls) > 0
        # First call should be with kernel entry state (has _step and _projs)
        assert calls[0]["state_keys"] == {"_step", "_projs"}

    def test_kernel_wrap_projection_fires(self):
        """Verify kernel.wrap projection transforms entry state."""
        kernel_projs = load_combined_kernel_projections()

        # Manual test: kernel entry state
        entry_state = {"_step": 42, "_projs": None}

        # First step should be kernel.wrap
        result = eval_step(kernel_projs, entry_state)

        # After kernel.wrap, state should have _mode: "kernel"
        assert isinstance(result, dict)
        assert result.get("_mode") == "kernel"
        assert result.get("_phase") == "try"

    def test_kernel_stall_projection_fires(self):
        """Verify kernel.stall projection fires when projections exhausted."""
        kernel_projs = load_combined_kernel_projections()

        # State after kernel.wrap with null _remaining (no projections)
        stall_state = {
            "_mode": "kernel",
            "_phase": "try",
            "_input": 42,
            "_remaining": None
        }

        # kernel.stall should match this
        result = eval_step(kernel_projs, stall_state)

        assert isinstance(result, dict)
        assert result.get("_mode") == "done"
        assert result.get("_stall") is True
        assert result.get("_result") == 42

    def test_kernel_unwrap_projection_fires(self):
        """Verify kernel.unwrap projection extracts final result."""
        kernel_projs = load_combined_kernel_projections()

        # Done state ready for unwrap
        done_state = {
            "_mode": "done",
            "_result": {"answer": 42},
            "_stall": False
        }

        # kernel.unwrap should extract result
        result = eval_step(kernel_projs, done_state)

        assert result == {"answer": 42}


# =============================================================================
# Test: Projection Order Enforced at Runtime
# =============================================================================

class TestProjectionOrderEnforcedAtRuntime:
    """Verify projection order validation happens during execution."""

    def setup_method(self):
        """Reset step budget before each test."""
        reset_step_budget()

    def test_step_kernel_mu_rejects_bad_order_at_runtime(self):
        """step_kernel_mu raises error if domain projection before kernel."""
        # Create a malicious domain projection that mimics kernel entry
        malicious_proj = {
            "id": "attack.intercept",
            "pattern": {"_step": {"var": "x"}, "_projs": {"var": "p"}},
            "body": {"pwned": True}
        }

        # This has kernel-like pattern (_step) but isn't a kernel projection
        # The validation should catch this as a domain projection with kernel pattern
        # Actually, this tests that validate_kernel_projections_first is called

        # Create a bad order: domain-like first, then something that looks kernel-ish
        bad_order = [
            {"id": "domain.first", "pattern": {"x": 1}, "body": {"y": 2}},
            {"id": "kernel.fake", "pattern": {"_mode": "kernel"}, "body": {}},
        ]

        with pytest.raises(ValueError, match="SECURITY"):
            step_kernel_mu(bad_order, 42)

    def test_step_kernel_mu_accepts_empty_projections(self):
        """Empty projection list is valid (stalls immediately)."""
        result = step_kernel_mu([], 42)
        assert result == 42  # Returns original on stall

    def test_step_kernel_mu_accepts_domain_only_projections(self):
        """Domain-only projections are valid (no kernel projections in list)."""
        domain_projs = [
            {"id": "double", "pattern": {"var": "x"}, "body": {"doubled": {"var": "x"}}}
        ]
        result = step_kernel_mu(domain_projs, 42)
        # Should match and transform
        assert result == {"doubled": 42}


# =============================================================================
# Test: Kernel Stall Path Complete
# =============================================================================

class TestKernelStallPathComplete:
    """Verify the full stall path: kernel.stall → kernel.unwrap → original input."""

    def setup_method(self):
        """Reset step budget before each test."""
        reset_step_budget()

    def test_empty_projections_full_stall_path(self):
        """Empty projections go through kernel.wrap → kernel.stall → kernel.unwrap."""
        kernel_projs = load_combined_kernel_projections()

        # Track state transitions by recording both input and output of eval_step
        transitions = []
        original_eval_step = eval_step

        def tracking_step(projs, state):
            result = original_eval_step(projs, state)
            input_mode = state.get("_mode") if isinstance(state, dict) else None
            output_mode = result.get("_mode") if isinstance(result, dict) else None
            transitions.append({"input_mode": input_mode, "output_mode": output_mode})
            return result

        with patch('rcx_pi.selfhost.step_mu.eval_step', side_effect=tracking_step):
            result = step_kernel_mu([], 42)

        # Should return original input
        assert result == 42

        # Extract modes from transitions
        input_modes = [t["input_mode"] for t in transitions]
        output_modes = [t["output_mode"] for t in transitions]

        # Should have transitioned through:
        # None (entry) → kernel (after wrap) → done (after stall) → unwrapped
        assert None in input_modes  # Entry state has no _mode
        assert "kernel" in output_modes  # kernel.wrap produces _mode: kernel
        assert "done" in output_modes  # kernel.stall produces _mode: done

    def test_no_match_projections_stall(self):
        """Projections that don't match cause stall."""
        never_match = [
            {"id": "never", "pattern": {"impossible": "match"}, "body": {"never": "reached"}}
        ]

        result = step_kernel_mu(never_match, 42)

        # Should stall and return original
        assert result == 42

    def test_stall_preserves_complex_input(self):
        """Stall correctly preserves complex input structures."""
        complex_input = {
            "nested": {"deep": {"value": [1, 2, 3]}},
            "list": [{"a": 1}, {"b": 2}]
        }

        result = step_kernel_mu([], complex_input)

        # Should return original unchanged
        assert mu_equal(result, complex_input)

    def test_stall_after_partial_matching(self):
        """Stall after some projections tried but none match."""
        projections = [
            {"id": "match.1", "pattern": {"x": 1}, "body": {"result": "one"}},
            {"id": "match.2", "pattern": {"x": 2}, "body": {"result": "two"}},
            {"id": "match.3", "pattern": {"x": 3}, "body": {"result": "three"}},
        ]

        # Input matches none
        result = step_kernel_mu(projections, {"x": 999})

        # Should stall
        assert mu_equal(result, {"x": 999})


# =============================================================================
# Test: KERNEL_RESERVED_FIELDS Boundary Validation
# =============================================================================

class TestKernelReservedFieldsValidation:
    """Verify domain inputs with kernel-reserved fields are rejected."""

    def setup_method(self):
        """Reset step budget before each test."""
        reset_step_budget()

    def test_reserved_fields_constant_complete(self):
        """KERNEL_RESERVED_FIELDS contains all expected fields."""
        expected = {
            "_mode", "_phase", "_input", "_remaining",
            "_match_ctx", "_subst_ctx", "_kernel_ctx",
            "_status", "_result", "_stall",
            "_step", "_projs"  # Kernel entry format fields (Phase 8b)
        }
        assert KERNEL_RESERVED_FIELDS == expected

    def test_validate_rejects_step_field(self):
        """Input with _step field is rejected (kernel entry format forgery)."""
        malicious = {"_step": 42, "_projs": None}

        with pytest.raises(ValueError, match="SECURITY.*_step"):
            validate_no_kernel_reserved_fields(malicious, "test")

    def test_validate_rejects_projs_field(self):
        """Input with _projs field is rejected (kernel entry format forgery)."""
        malicious = {"data": 1, "_projs": [{"pattern": 1, "body": 2}]}

        with pytest.raises(ValueError, match="SECURITY.*_projs"):
            validate_no_kernel_reserved_fields(malicious, "test")

    def test_validate_no_kernel_reserved_fields_rejects_mode(self):
        """Input with _mode field is rejected."""
        malicious = {"_mode": "done", "_result": "pwned", "_stall": False}

        with pytest.raises(ValueError, match="SECURITY.*_mode"):
            validate_no_kernel_reserved_fields(malicious, "test")

    def test_validate_no_kernel_reserved_fields_rejects_match_ctx(self):
        """Input with _match_ctx field is rejected."""
        malicious = {"data": 1, "_match_ctx": {"forged": True}}

        with pytest.raises(ValueError, match="SECURITY.*_match_ctx"):
            validate_no_kernel_reserved_fields(malicious, "test")

    def test_validate_no_kernel_reserved_fields_allows_clean_input(self):
        """Input without reserved fields is accepted."""
        clean = {"x": 1, "y": {"nested": True}, "list": [1, 2, 3]}

        # Should not raise
        validate_no_kernel_reserved_fields(clean, "test")

    def test_validate_no_kernel_reserved_fields_allows_primitives(self):
        """Primitive inputs are always accepted."""
        validate_no_kernel_reserved_fields(42, "test")
        validate_no_kernel_reserved_fields("hello", "test")
        validate_no_kernel_reserved_fields(None, "test")
        validate_no_kernel_reserved_fields(True, "test")

    def test_step_kernel_mu_rejects_reserved_fields_in_input(self):
        """step_kernel_mu rejects inputs with kernel-reserved fields."""
        malicious_input = {"_mode": "done", "_result": "attack"}

        with pytest.raises(ValueError, match="SECURITY"):
            step_kernel_mu([], malicious_input)

    def test_step_kernel_mu_accepts_underscore_prefixed_non_reserved(self):
        """step_kernel_mu accepts underscore-prefixed fields not in reserved set."""
        # _custom is not in KERNEL_RESERVED_FIELDS
        input_with_custom = {"_custom": "value", "data": 42}

        result = step_kernel_mu([], input_with_custom)
        # Should stall (no projections) but not reject
        assert mu_equal(result, input_with_custom)

    # =========================================================================
    # Deep Validation Tests (Phase 8b - Adversary Review Fix)
    # =========================================================================

    def test_validate_rejects_nested_reserved_fields(self):
        """CRITICAL: Nested reserved fields are rejected (not just top-level)."""
        # Attack vector from adversary review
        nested_attack = {"outer": {"_mode": "done", "_result": "pwned"}}

        with pytest.raises(ValueError, match="SECURITY.*_mode"):
            validate_no_kernel_reserved_fields(nested_attack, "test")

    def test_validate_rejects_deeply_nested_reserved_fields(self):
        """Deep nesting doesn't bypass validation."""
        deep_attack = {
            "level1": {
                "level2": {
                    "level3": {"_stall": True}
                }
            }
        }

        with pytest.raises(ValueError, match="SECURITY.*_stall"):
            validate_no_kernel_reserved_fields(deep_attack, "test")

    def test_validate_rejects_reserved_fields_in_list(self):
        """Reserved fields inside list elements are rejected."""
        list_attack = {"data": [{"_mode": "kernel"}, {"clean": True}]}

        with pytest.raises(ValueError, match="SECURITY.*_mode"):
            validate_no_kernel_reserved_fields(list_attack, "test")

    def test_validate_rejects_reserved_fields_in_nested_list(self):
        """Reserved fields in deeply nested lists are rejected."""
        nested_list_attack = {
            "items": [
                [{"_match_ctx": {"forged": True}}]
            ]
        }

        with pytest.raises(ValueError, match="SECURITY.*_match_ctx"):
            validate_no_kernel_reserved_fields(nested_list_attack, "test")

    def test_step_kernel_mu_rejects_nested_attack(self):
        """step_kernel_mu rejects nested reserved field attacks."""
        nested_attack = {"wrapper": {"_mode": "done", "_result": "attack"}}

        with pytest.raises(ValueError, match="SECURITY"):
            step_kernel_mu([], nested_attack)

    def test_validate_allows_clean_deep_structure(self):
        """Clean deeply nested structures pass validation."""
        clean_deep = {
            "a": {"b": {"c": {"d": {"e": 42}}}},
            "list": [{"x": 1}, {"y": [{"z": 2}]}]
        }

        # Should not raise
        validate_no_kernel_reserved_fields(clean_deep, "test")

    # =========================================================================
    # Depth Boundary Tests (Phase 8b - Expert Review Fix)
    # =========================================================================

    def test_validate_rejects_excessive_depth(self):
        """CRITICAL: Structures deeper than 100 are rejected (fail closed)."""
        # Build structure with 101 levels of nesting
        deep = {"data": 42}
        for _ in range(101):
            deep = {"level": deep}

        # Should raise - depth exceeded (fail CLOSED, not open)
        with pytest.raises(ValueError, match="exceeded maximum validation depth"):
            validate_no_kernel_reserved_fields(deep, "test")

    def test_validate_accepts_depth_100(self):
        """Structures exactly at depth 100 are accepted."""
        # Build structure with exactly 100 levels
        deep = {"data": 42}
        for _ in range(99):  # 99 wraps + initial = 100 total
            deep = {"level": deep}

        # Should not raise - within limit
        validate_no_kernel_reserved_fields(deep, "test")

    def test_step_kernel_mu_rejects_excessive_depth_attack(self):
        """step_kernel_mu rejects excessively deep structures."""
        # Build structure with 101 levels of nesting
        deep = {"data": 42}
        for _ in range(101):
            deep = {"level": deep}

        with pytest.raises(ValueError, match="exceeded maximum validation depth"):
            step_kernel_mu([], deep)


# =============================================================================
# Test: Integration - Full Pipeline
# =============================================================================

class TestFullPipelineIntegration:
    """End-to-end tests of the step_mu → kernel pipeline."""

    def setup_method(self):
        """Reset step budget before each test."""
        reset_step_budget()

    def test_simple_transformation_through_kernel(self):
        """Simple projection transformation uses full kernel pipeline."""
        projections = [
            {"pattern": {"var": "x"}, "body": {"wrapped": {"var": "x"}}}
        ]

        result = step_mu(projections, 42)

        assert result == {"wrapped": 42}

    def test_first_match_wins_through_kernel(self):
        """First matching projection wins (kernel selection is correct)."""
        projections = [
            {"pattern": 1, "body": "first"},
            {"pattern": 1, "body": "second"},  # Same pattern, should never match
            {"pattern": 2, "body": "third"},
        ]

        result = step_mu(projections, 1)
        assert result == "first"

        result = step_mu(projections, 2)
        assert result == "third"

    def test_variable_binding_through_kernel(self):
        """Variable binding works through kernel pipeline."""
        projections = [
            {
                "pattern": {"x": {"var": "a"}, "y": {"var": "b"}},
                "body": {"sum_desc": {"first": {"var": "a"}, "second": {"var": "b"}}}
            }
        ]

        result = step_mu(projections, {"x": 10, "y": 20})

        assert result == {"sum_desc": {"first": 10, "second": 20}}

    def test_nested_structure_transformation(self):
        """Nested structures transform correctly through kernel."""
        projections = [
            {
                "pattern": {"data": {"var": "d"}},
                "body": {"result": {"data": {"var": "d"}, "processed": True}}
            }
        ]

        input_val = {"data": {"nested": {"deep": [1, 2, 3]}}}
        result = step_mu(projections, input_val)

        assert result == {
            "result": {
                "data": {"nested": {"deep": [1, 2, 3]}},
                "processed": True
            }
        }
