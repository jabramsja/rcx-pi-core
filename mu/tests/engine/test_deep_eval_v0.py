"""
Tests for deep_eval v0 (work-stack machine).

Tests the production deep_eval module from rcx_pi/deep_eval.py.

HOST DEBT INVENTORY (test scaffolding):
  - @host_builtin: linked_list (reversed), to_python_list (while-loop)
  Total: 2 host dependencies (test helpers only, not production code)
"""

import pytest

from rcx_pi.deep_eval import (
    make_deep_eval_projections,
    validate_deep_eval_state,
    run_deep_eval,
    deep_eval,
    MAX_HISTORY,
    MAX_CONTEXT_DEPTH,
)
from rcx_pi.mu_type import assert_mu, mu_equal


# =============================================================================
# Test Helpers (host scaffolding)
# =============================================================================

def host_builtin(func):
    """Decorator marking functions that use Python builtins."""
    func.host_debt_marker = "builtin"
    return func


def host_iteration(func):
    """Decorator marking functions that use Python iteration."""
    func.host_debt_marker = "iteration"
    return func


@host_builtin
def linked_list(*elements):
    """
    Create linked list from elements.

    @host_builtin: Uses reversed() builtin
    """
    result = None
    for elem in reversed(elements):
        assert_mu(elem)
        result = {"head": elem, "tail": result}
    return result


@host_iteration
def to_python_list(linked):
    """
    Convert linked list back to Python list.

    @host_iteration: Uses while-loop
    """
    result = []
    while linked is not None:
        result.append(linked["head"])
        linked = linked["tail"]
    return result


# =============================================================================
# Domain Projections (append)
# =============================================================================

APPEND_BASE = {
    "id": "append.base",
    "pattern": {"op": "append", "xs": None, "ys": {"var": "ys"}},
    "body": {"var": "ys"}
}

APPEND_RECURSIVE = {
    "id": "append.recursive",
    "pattern": {
        "op": "append",
        "xs": {"head": {"var": "h"}, "tail": {"var": "t"}},
        "ys": {"var": "ys"}
    },
    "body": {
        "head": {"var": "h"},
        "tail": {"op": "append", "xs": {"var": "t"}, "ys": {"var": "ys"}}
    }
}

DOMAIN_PROJECTIONS = [APPEND_BASE, APPEND_RECURSIVE]


# =============================================================================
# Core Functionality Tests
# =============================================================================

class TestWrapUnwrap:
    """Test that values wrap and unwrap correctly."""

    def test_simple_value(self):
        """Simple value wraps and unwraps unchanged."""
        projections = make_deep_eval_projections([])
        value = {"head": 1, "tail": None}

        result, history = run_deep_eval(projections, value)

        assert mu_equal(result, value)

    def test_null_value(self):
        """
        Null value gets wrapped but doesn't complete.

        NOTE: Current deep_eval is specialized for linked lists (head/tail dicts).
        Primitive values without structure stall in wrapped state.
        This is a known limitation; future work may add primitive handling.
        """
        projections = make_deep_eval_projections([])
        value = None

        result, history = run_deep_eval(projections, value, max_steps=10)

        # Currently stalls in wrapped state (known limitation)
        # Future: add projections to handle primitive values
        assert isinstance(result, dict)
        assert result.get("mode") == "deep_eval"

    def test_nested_value(self):
        """Nested structure without reductions."""
        projections = make_deep_eval_projections([])
        value = {"head": {"head": 1, "tail": None}, "tail": {"head": 2, "tail": None}}

        result, history = run_deep_eval(projections, value)

        assert mu_equal(result, value)


class TestSingleReduction:
    """Test single reduction at root level."""

    def test_append_empty_xs(self):
        """append([], [1]) = [1]"""
        projections = make_deep_eval_projections(DOMAIN_PROJECTIONS)

        value = {"op": "append", "xs": None, "ys": linked_list(1)}
        result, history = run_deep_eval(projections, value)

        expected = linked_list(1)
        assert mu_equal(result, expected)

    def test_append_empty_ys(self):
        """append([1,2], None) = [1,2] - edge case with empty ys."""
        projections = make_deep_eval_projections(DOMAIN_PROJECTIONS)

        value = {"op": "append", "xs": linked_list(1, 2), "ys": None}
        result, history = run_deep_eval(projections, value)

        expected = linked_list(1, 2)
        assert mu_equal(result, expected), f"Expected [1,2], got {to_python_list(result)}"


class TestAppend:
    """Test append operation with various inputs."""

    def test_append_basic(self):
        """append([1], [2]) = [1, 2]"""
        projections = make_deep_eval_projections(DOMAIN_PROJECTIONS)

        value = {
            "op": "append",
            "xs": linked_list(1),
            "ys": linked_list(2)
        }
        result, history = run_deep_eval(projections, value)

        expected = linked_list(1, 2)
        assert mu_equal(result, expected), f"Expected [1,2], got {to_python_list(result)}"

    def test_append_longer(self):
        """append([1,2], [3,4]) = [1,2,3,4]"""
        projections = make_deep_eval_projections(DOMAIN_PROJECTIONS)

        value = {
            "op": "append",
            "xs": linked_list(1, 2),
            "ys": linked_list(3, 4)
        }
        result, history = run_deep_eval(projections, value)

        expected = linked_list(1, 2, 3, 4)
        assert mu_equal(result, expected)

    def test_append_three_elements(self):
        """append([1,2,3], [4,5]) = [1,2,3,4,5]"""
        projections = make_deep_eval_projections(DOMAIN_PROJECTIONS)

        value = {
            "op": "append",
            "xs": linked_list(1, 2, 3),
            "ys": linked_list(4, 5)
        }
        result, history = run_deep_eval(projections, value)

        expected = linked_list(1, 2, 3, 4, 5)
        assert mu_equal(result, expected)


class TestConvenienceFunction:
    """Test the deep_eval convenience function."""

    def test_deep_eval_basic(self):
        """deep_eval convenience function works."""
        value = {"op": "append", "xs": linked_list(1), "ys": linked_list(2)}
        result = deep_eval(DOMAIN_PROJECTIONS, value)

        expected = linked_list(1, 2)
        assert mu_equal(result, expected)


# =============================================================================
# State Validation Tests
# =============================================================================

class TestValidation:
    """Test state validation."""

    def test_valid_state(self):
        """Valid deep_eval state passes validation."""
        state = {
            "mode": "deep_eval",
            "phase": "traverse",
            "focus": 1,
            "context": [],
            "changed": False
        }
        is_valid, error = validate_deep_eval_state(state)
        assert is_valid
        assert error is None

    def test_invalid_phase(self):
        """Invalid phase is rejected."""
        state = {
            "mode": "deep_eval",
            "phase": "INVALID",
            "focus": 1,
            "context": [],
            "changed": False
        }
        is_valid, error = validate_deep_eval_state(state)
        assert not is_valid
        assert "phase" in error.lower()

    def test_non_boolean_changed(self):
        """Non-boolean changed is rejected."""
        state = {
            "mode": "deep_eval",
            "phase": "traverse",
            "focus": 1,
            "context": [],
            "changed": "true"  # String, not boolean
        }
        is_valid, error = validate_deep_eval_state(state)
        assert not is_valid
        assert "boolean" in error.lower()

    def test_missing_fields(self):
        """Missing required fields are rejected."""
        state = {
            "mode": "deep_eval",
            "phase": "traverse",
            "focus": 1,
            # missing: context, changed
        }
        is_valid, error = validate_deep_eval_state(state)
        assert not is_valid
        assert "missing" in error.lower()

    def test_non_deep_eval_passes(self):
        """Non-deep_eval values pass validation."""
        state = {"foo": "bar"}
        is_valid, error = validate_deep_eval_state(state)
        assert is_valid

    def test_root_check_with_context_rejected(self):
        """root_check phase with non-empty context is rejected."""
        state = {
            "mode": "deep_eval",
            "phase": "root_check",
            "focus": 1,
            "context": [{"type": "dict_tail", "head_result": 0}, []],
            "changed": False
        }
        is_valid, error = validate_deep_eval_state(state)
        assert not is_valid
        assert "root_check" in error.lower() or "context" in error.lower()


# =============================================================================
# Adversary Attack Tests
# =============================================================================

class TestAdversaryAttacks:
    """Tests for adversary-identified vulnerabilities."""

    def test_attack_phase_state_injection(self):
        """
        Attack 14: Verify phase guards prevent infinite loops from injected states.

        Adversary tries to inject malformed context structure.
        """
        projections = make_deep_eval_projections([])

        # Malicious state: context is malformed (single-element list)
        malicious = {
            "mode": "deep_eval",
            "phase": "traverse",
            "focus": {"head": 1, "tail": None},
            "context": [{"type": "dict_tail", "head_result": 0}],  # malformed
            "changed": False
        }

        with pytest.raises(ValueError) as exc_info:
            run_deep_eval(projections, malicious, max_steps=20, validate=True)

        assert "context" in str(exc_info.value).lower() or "frame" in str(exc_info.value).lower()

    def test_attack_changed_flag_manipulation(self):
        """
        Attack 15: Verify changed flag is validated.

        Adversary claims no changes when focus is reducible.
        """
        projections = make_deep_eval_projections([
            {"pattern": {"x": 1}, "body": {"x": 2}}
        ])

        # Malicious: focus can reduce but changed=False
        malicious = {
            "mode": "deep_eval",
            "phase": "root_check",
            "focus": {"x": 1},  # This SHOULD reduce to {"x": 2}
            "context": [],
            "changed": False  # But we falsely claim no changes
        }

        result, history = run_deep_eval(projections, malicious, max_steps=20)

        # The system should NOT infinitely loop
        assert len(history) < 20, "Changed flag manipulation caused problems"

    def test_attack_deep_context(self):
        """
        Attack 7: Verify deep context doesn't cause stack overflow.

        Context depth is limited by MAX_CONTEXT_DEPTH.
        """
        projections = make_deep_eval_projections([])

        # Create artificially deep context
        deep_context = []
        for i in range(MAX_CONTEXT_DEPTH + 10):
            deep_context = [{"type": "dict_tail", "head_result": i}, deep_context]

        malicious = {
            "mode": "deep_eval",
            "phase": "traverse",
            "focus": 1,
            "context": deep_context,
            "changed": False
        }

        # Should reject due to context depth or terminate reasonably
        try:
            result, history = run_deep_eval(projections, malicious, max_steps=10)
            # If it didn't raise, check it terminated reasonably
            assert len(history) <= 10, "Deep context caused extended execution"
        except ValueError as e:
            # Expected: validation rejects deep context
            assert "depth" in str(e).lower() or "context" in str(e).lower()

    def test_attack_history_limit(self):
        """
        Attack 17: Verify history doesn't grow unbounded.

        History should be capped at MAX_HISTORY.
        """
        projections = make_deep_eval_projections([])
        value = linked_list(*range(10))

        # Run with many steps
        result, history = run_deep_eval(projections, value, max_steps=MAX_HISTORY + 100)

        # History should be capped
        assert len(history) <= MAX_HISTORY, f"History grew to {len(history)}, expected max {MAX_HISTORY}"

    def test_attack_invalid_phase_runtime(self):
        """Verify invalid phase values are rejected at runtime."""
        projections = make_deep_eval_projections([])

        malicious = {
            "mode": "deep_eval",
            "phase": "MALICIOUS_PHASE",
            "focus": 1,
            "context": [],
            "changed": False
        }

        with pytest.raises(ValueError) as exc_info:
            run_deep_eval(projections, malicious, max_steps=10)

        assert "phase" in str(exc_info.value).lower()

    def test_attack_non_boolean_changed_runtime(self):
        """Verify non-boolean changed values are rejected at runtime."""
        projections = make_deep_eval_projections([])

        malicious = {
            "mode": "deep_eval",
            "phase": "traverse",
            "focus": 1,
            "context": [],
            "changed": "true"  # String, not boolean
        }

        with pytest.raises(ValueError) as exc_info:
            run_deep_eval(projections, malicious, max_steps=10)

        assert "boolean" in str(exc_info.value).lower()

    def test_attack_done_wrapper_spoofing(self):
        """
        CRITICAL: Verify domain projections cannot spoof done wrapper.

        A malicious domain projection that returns {"mode": "deep_eval_done", ...}
        should NOT cause early exit - only the authentic unwrap projection can.
        """
        # Malicious projection that tries to inject done wrapper
        malicious_proj = {
            "id": "malicious",
            "pattern": {"trigger": "spoof"},
            "body": {
                "mode": "deep_eval_done",
                "result": "SPOOFED_EARLY_EXIT"
                # Note: no _marker field - this is the attack
            }
        }

        projections = make_deep_eval_projections([malicious_proj])

        # This input matches the malicious projection
        value = {"trigger": "spoof"}
        result, history = run_deep_eval(projections, value, max_steps=50)

        # The spoofed done wrapper should NOT cause early exit
        # Instead, it should stall (no projection matches the spoofed wrapper)
        assert result != "SPOOFED_EARLY_EXIT", "Done wrapper spoofing succeeded - CRITICAL vulnerability!"

        # The result should be the spoofed structure stuck in deep_eval state
        # (because no projection matches the spoofed done wrapper without marker)
        assert isinstance(result, dict)

    def test_attack_deep_mu_nesting(self):
        """
        HIGH: Verify deeply nested Mu values are rejected.

        is_mu() now has MAX_MU_DEPTH limit to prevent RecursionError.
        """
        from rcx_pi.mu_type import is_mu, MAX_MU_DEPTH

        # Create deeply nested structure beyond limit
        deep_value = 1
        for _ in range(MAX_MU_DEPTH + 50):
            deep_value = {"nested": deep_value}

        # Should return False (not valid Mu due to depth)
        assert not is_mu(deep_value), f"Deep nesting ({MAX_MU_DEPTH + 50} levels) should be rejected"

        # Value well within the limit should pass
        ok_value = 1
        for _ in range(MAX_MU_DEPTH - 50):
            ok_value = {"nested": ok_value}

        assert is_mu(ok_value), "Value within depth limit should be valid Mu"


# =============================================================================
# Projection Structure Tests
# =============================================================================

class TestProjectionStructure:
    """Test that projections are generated correctly."""

    def test_projection_count(self):
        """Correct number of projections generated."""
        projections = make_deep_eval_projections([])
        # Without domain projections: restart, unwrap, descend, sibling, ascend.to_context, ascend.to_root, wrap
        assert len(projections) == 7

        projections = make_deep_eval_projections(DOMAIN_PROJECTIONS)
        # With 2 domain projections: 7 + 2 = 9
        assert len(projections) == 9

    def test_projection_ids(self):
        """All projections have IDs."""
        projections = make_deep_eval_projections(DOMAIN_PROJECTIONS)
        for proj in projections:
            assert "id" in proj, f"Projection missing ID: {proj}"

    def test_wrap_is_last(self):
        """Wrap projection is last (catches everything)."""
        projections = make_deep_eval_projections([])
        assert projections[-1]["id"] == "wrap"
