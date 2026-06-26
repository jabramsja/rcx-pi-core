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

ONE = {"_num": {"xH": None}}
TWO = {"_num": {"xO": {"xH": None}}}
THREE = {"_num": {"xI": {"xH": None}}}


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

            test_projs = [{"pattern": {"var": "x"}, "body": {"result": {"var": "x"}}}]
            result = step_mu(test_projs, 100)

            # step_kernel_mu should have been called with the projections and input
            assert mock_kernel.called, "step_kernel_mu was not called"
            call_args = mock_kernel.call_args
            assert call_args is not None, "No call arguments captured"
            # Verify projections were passed (first positional arg)
            assert call_args[0][0] == test_projs, f"Wrong projections passed: {call_args[0][0]}"
            # Result should be what step_kernel_mu returned
            assert result == 42

    def test_step_kernel_mu_loads_combined_projections(self):
        """step_kernel_mu loads kernel + match.v2 + subst.v2 projections via private shared helper."""
        import rcx_pi.selfhost.step_mu as _step_mu_mod
        # Disable P7-d shadow — monkeypatching loader makes shadow meaningless
        orig_shadow = _step_mu_mod._STAGE0_SHADOW_ENABLED  # ANTICHEAT_OK: save shadow flag for monkeypatch test
        _step_mu_mod._STAGE0_SHADOW_ENABLED = False  # ANTICHEAT_OK: disable shadow for monkeypatch test
        try:
            with patch('rcx_pi.selfhost.step_mu._load_combined_kernel_projections_shared') as mock_load:  # ANTICHEAT_OK: F-39 internal path proof
                # Return minimal valid projections
                mock_load.return_value = []

                # This will stall immediately with empty projections
                try:
                    step_kernel_mu([], 42)
                except (ValueError, TypeError, KeyError):
                    pass  # Expected validation errors
                except Exception as e:
                    raise AssertionError(f"Unexpected exception in step_kernel_mu: {type(e).__name__}: {e}")

                assert mock_load.called
        finally:
            _step_mu_mod._STAGE0_SHADOW_ENABLED = orig_shadow  # ANTICHEAT_OK: restore shadow flag

    def test_step_kernel_mu_calls_eval_step_with_kernel_projs(self):
        """step_kernel_mu uses eval_step with kernel projections.

        Proves this through public API:
        1. return_meta=True confirms the kernel path is taken
        2. Manual eval_step on kernel entry state confirms kernel projections
           transform it (kernel.wrap fires)
        """
        kernel_projs = load_combined_kernel_projections()

        # 1. step_kernel_mu with return_meta proves kernel processes input
        meta = step_kernel_mu(
            [{"pattern": {"var": "x"}, "body": {"result": {"var": "x"}}}],
            ONE,
            return_meta=True,
        )
        assert isinstance(meta, dict)
        assert "output" in meta and "stall" in meta
        assert meta["stall"] is False
        assert meta["output"] == {"result": ONE}

        # 2. Manually verify kernel entry state is processed by kernel projections
        entry_state = {"_step": 42, "_projs": None}
        result = eval_step(kernel_projs, entry_state)
        assert isinstance(result, dict)
        assert result.get("_mode") == "kernel"  # kernel.wrap fired

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
        result = step_kernel_mu(domain_projs, ONE)
        # Should match and transform
        assert result == {"doubled": ONE}


# =============================================================================
# Test: Kernel Stall Path Complete
# =============================================================================

class TestKernelStallPathComplete:
    """Verify the full stall path: kernel.stall → kernel.unwrap → original input."""

    def setup_method(self):
        """Reset step budget before each test."""
        reset_step_budget()

    def test_empty_projections_full_stall_path(self):
        """Empty projections go through kernel.wrap → kernel.stall → kernel.unwrap.

        Traces the kernel state machine through the public eval_step function
        to prove mode transitions without patching private internals.
        """
        kernel_projs = load_combined_kernel_projections()

        # Manually step through the kernel state machine via public eval_step
        entry_state = {"_step": 42, "_projs": None}
        modes_seen = []

        state = entry_state
        for _ in range(20):
            result = eval_step(kernel_projs, state)
            out_mode = result.get("_mode") if isinstance(result, dict) else None
            modes_seen.append(out_mode)
            if result == state:
                break  # fixpoint
            state = result

        # Should have transitioned through:
        # kernel.wrap → _mode: kernel (try phase)
        # kernel.stall → _mode: done (all projections exhausted)
        # kernel.unwrap → no _mode (unwrapped to domain value)
        assert "kernel" in modes_seen, f"kernel.wrap did not fire: {modes_seen}"
        assert "done" in modes_seen, f"kernel.stall did not fire: {modes_seen}"

        # Also verify through the public API
        meta = step_kernel_mu([], 42, return_meta=True)
        assert meta["stall"] is True
        assert meta["output"] == 42

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
        """KERNEL_RESERVED_FIELDS contains all expected fields.

        Gate 3 (2026-02-04): Entry point keys (_detect_closure, _detect_exhaustion)
        moved to ALGORITHM_ENTRYPOINT_KEYS. Now 24 reserved fields.
        """
        # Note: 'subst' and 'match' are NOT reserved - they're too generic.
        # Domain data with these keys cannot forge kernel state.
        expected = {
            "_mode", "_phase", "_input", "_remaining",
            "_match_ctx", "_subst_ctx", "_kernel_ctx",
            "_status", "_result", "_stall",
            "_step", "_projs",  # Kernel entry format fields (Phase 8b)
            # Recurrence closure detection fields (9-agent review, 2026-02-02)
            "_seen", "_current", "_check_list",
            # Operator Exhaustion fields (Step 6 preparation, 2026-02-02)
            "_frozen", "_tau_step", "_operator_ids",
            # Bootstrap-Structural Bridge lookup phase fields (9-agent review, 2026-02-02)
            "_lookup_name", "_lookup_value", "_lookup_bindings", "_original_bindings",
            # Engine pipeline dispatch field (Boot1 P2 hardening, 2026-02-14)
            "_run_engine",
            # Boot1 recursive loop contract field (Boot1 P3 hardening, 2026-02-14)
            "_tail_call",
            # Boundary effect dispatch field (adversary hardening, 2026-02-24)
            "_boundary_request"
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

    def test_validate_allows_subst_field(self):
        """Input with subst field is allowed (too generic to reserve)."""
        # 'subst' is a common domain key (e.g., text substitution)
        clean = {"data": 1, "subst": {"pattern": 1, "body": 2}}
        validate_no_kernel_reserved_fields(clean, "test")  # Should not raise

    def test_validate_allows_match_field(self):
        """Input with match field is allowed (too generic to reserve)."""
        # 'match' is a common domain key (e.g., pattern matching result)
        clean = {"data": 1, "match": {"pattern_focus": 42}}
        validate_no_kernel_reserved_fields(clean, "test")  # Should not raise

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
        """CRITICAL: Structures deeper than MAX_MU_DEPTH (300) are rejected (fail closed)."""
        # Build structure with 301 levels of nesting (exceeds MAX_MU_DEPTH=300)
        deep = {"data": 42}
        for _ in range(301):
            deep = {"level": deep}

        # Should raise - depth exceeded (fail CLOSED, not open)
        with pytest.raises(ValueError, match="exceeded maximum validation depth"):
            validate_no_kernel_reserved_fields(deep, "test")

    def test_validate_accepts_depth_at_limit(self):
        """Structures exactly at MAX_MU_DEPTH (300) are accepted."""
        # Build structure with exactly 300 levels
        deep = {"data": 42}
        for _ in range(299):  # 299 wraps + initial = 300 total
            deep = {"level": deep}

        # Should not raise - within limit
        validate_no_kernel_reserved_fields(deep, "test")

    def test_step_kernel_mu_rejects_excessive_depth_attack(self):
        """step_kernel_mu rejects excessively deep structures.

        Structures exceeding MAX_MU_DEPTH (300) fail at assert_mu boundary
        (TypeError) before reaching _walk_and_validate. Both limits are 300,
        so assert_mu is the first defense line.
        """
        # Build structure with 301 levels of nesting (exceeds MAX_MU_DEPTH=300)
        deep = {"data": 42}
        for _ in range(301):
            deep = {"level": deep}

        with pytest.raises(TypeError, match="must be a Mu"):
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

        result = step_mu(projections, ONE)

        assert result == {"wrapped": ONE}

    def test_first_match_wins_through_kernel(self):
        """First matching projection wins (kernel selection is correct)."""
        projections = [
            {"pattern": ONE, "body": "first"},
            {"pattern": ONE, "body": "second"},  # Same pattern, should never match
            {"pattern": TWO, "body": "third"},
        ]

        result = step_mu(projections, ONE)
        assert result == "first"

        result = step_mu(projections, TWO)
        assert result == "third"

    def test_variable_binding_through_kernel(self):
        """Variable binding works through kernel pipeline."""
        projections = [
            {
                "pattern": {"x": {"var": "a"}, "y": {"var": "b"}},
                "body": {"sum_desc": {"first": {"var": "a"}, "second": {"var": "b"}}}
            }
        ]

        result = step_mu(projections, {"x": ONE, "y": TWO})

        assert result == {"sum_desc": {"first": ONE, "second": TWO}}

    def test_nested_structure_transformation(self):
        """Nested structures transform correctly through kernel."""
        projections = [
            {
                "pattern": {"data": {"var": "d"}},
                "body": {"result": {"data": {"var": "d"}, "processed": True}}
            }
        ]

        input_val = {"data": {"nested": {"deep": [ONE, TWO, THREE]}}}
        result = step_mu(projections, input_val)

        assert result == {
            "result": {
                "data": {"nested": {"deep": [ONE, TWO, THREE]}},
                "processed": True
            }
        }
