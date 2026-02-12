"""
Execution Path Verification Tests.

These tests verify that SPECIFIC projections are actually executed,
not just that behavior is correct. This prevents "test theater" where
tests pass via bootstrap but the claimed meta-circular path is never used.

Problem discovered (2026-02-03): All tests were passing because Python's
eval_seed.match() provides binding conflict detection, but we claimed
bootstrap_structural.v1 projections were providing it. Tests verified
behavior, not execution path.

EVIDENCE TYPES:
1. Trace log - capture which projection IDs fire during execution
2. Unique output - assert output only possible from specific projection
3. Structural marker - projection leaves marker no other projection produces

See: docs/agents/AgentGuardrails.v0.md (Execution Path Verification section)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from rcx_pi.selfhost.eval_seed import step

pytestmark = [pytest.mark.slow]


# =============================================================================
# Test Infrastructure: Projection Tracing
# =============================================================================


def step_with_trace(projections: list[dict], state: dict, trace: list[str]) -> dict:
    """
    Step through projections and record which projection fires.

    This provides EVIDENCE that specific projections are executed,
    not just that behavior is correct.
    """
    from rcx_pi.selfhost.eval_seed import match, substitute, _NoMatch  # ANTICHEAT_OK: execution path verification
    from rcx_pi.selfhost.match_mu import denormalize_from_match

    for proj in projections:
        pattern = proj.get("pattern", {})
        body = proj.get("body", {})
        proj_id = proj.get("id", "unknown")

        # Try to match using the actual step function logic
        result = match(pattern, state)

        # Check if match succeeded (not _NoMatch and not None)
        if result is not None and not isinstance(result, _NoMatch):
            # This projection matched!
            trace.append(proj_id)
            # Apply substitution
            subst_result = substitute(body, result)
            # Gate 3: Denormalize output when body uses normalized dict format
            if isinstance(body, dict) and body.get("_type") == "dict":
                subst_result = denormalize_from_match(subst_result)
            return subst_result

    # No projection matched - stall
    return state


def run_with_trace(projections: list[dict], initial_state: dict, max_steps: int = 100) -> tuple[dict, list[str]]:
    """
    Run projections and return (final_state, trace_of_projection_ids).

    The trace provides PROOF of execution path, not just behavior.
    """
    trace: list[str] = []
    state = initial_state

    for _ in range(max_steps):
        new_state = step_with_trace(projections, state, trace)
        if new_state == state:
            break
        state = new_state
        # Check for terminal state
        if isinstance(state, dict) and state.get("_mode") == "match_done":
            break

    return state, trace


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def bridge_projections():
    """Load bootstrap_structural bridge projections."""
    path = Path(__file__).parent.parent / "mu" / "bridge" / "bootstrap_structural.v1.json"
    with open(path) as f:
        seed = json.load(f)
    return seed["projections"]


@pytest.fixture(scope="module")
def match_v2_projections():
    """Load match.v2 projections."""
    path = Path(__file__).parent.parent / "mu" / "substrate" / "match.v2.json"
    with open(path) as f:
        seed = json.load(f)
    return seed["projections"]


@pytest.fixture(scope="module")
def combined_projections(bridge_projections, match_v2_projections):
    """Combined bridge + match.v2 projections (bridge first for interception)."""
    return bridge_projections + match_v2_projections


# =============================================================================
# Execution Path Verification Tests
# =============================================================================


class TestBridgeProjectionExecution:
    """
    Verify that bridge projections are ACTUALLY EXECUTED.

    These tests fail if the wrong path is used, even if behavior is correct.
    This prevents test theater where bootstrap provides behavior but we
    claim projections are providing it.
    """

    def test_bridge_var_check_existing_fires(self, combined_projections):
        """
        EVIDENCE: bridge.var.check_existing must fire when processing {"var": "x"}.

        This is the entry point for non-linear pattern support.
        If this doesn't fire, the bridge is not being used.
        """
        from rcx_pi.selfhost.match_mu import normalize_for_match

        # Create a match state that should trigger bridge.var.check_existing
        pattern = {"a": {"var": "x"}}
        value = {"a": 1}

        state = {
            "mode": "match",
            "pattern_focus": {"var": {"var": "x"}},  # This is what triggers bridge
            "value_focus": 1,
            "bindings": None,
            "stack": None,
            "_match_ctx": {}
        }

        result, trace = run_with_trace(combined_projections, state)

        # EVIDENCE: bridge.var.check_existing must be in the trace
        assert "bridge.var.check_existing" in trace, (
            f"bridge.var.check_existing was NOT executed!\n"
            f"Trace: {trace}\n"
            f"This means the bridge is not being used for variable binding."
        )

    def test_bridge_lookup_not_found_fires_for_new_binding(self, combined_projections):
        """
        EVIDENCE: bridge.lookup.not_found must fire when variable is not yet bound.

        This projection adds new bindings. If it doesn't fire, we're using
        a different code path (like match.var directly).
        """
        # After bridge.var.check_existing, state enters lookup phase
        state = {
            "mode": "match",
            "_phase": "lookup_binding",
            "_lookup_name": "x",
            "_lookup_value": 1,
            "_lookup_bindings": None,  # Empty bindings
            "_original_bindings": None,
            "stack": None,
            "_match_ctx": {}
        }

        result, trace = run_with_trace(combined_projections, state)

        # EVIDENCE: bridge.lookup.not_found must fire for empty bindings
        assert "bridge.lookup.not_found" in trace, (
            f"bridge.lookup.not_found was NOT executed!\n"
            f"Trace: {trace}\n"
            f"This means new bindings are not being added via bridge projections."
        )

    def test_bridge_lookup_found_same_fires_for_non_linear_match(self, combined_projections):
        """
        EVIDENCE: bridge.lookup.found_same must fire when same var has same value.

        This is the critical non-linear pattern support. If it doesn't fire,
        binding conflict detection is coming from Python, not projections.
        """
        # State after finding existing binding with same value
        state = {
            "mode": "match",
            "_phase": "lookup_binding",
            "_lookup_name": "x",
            "_lookup_value": 1,
            "_lookup_bindings": {
                "name": "x",
                "value": 1,  # Same value!
                "rest": None
            },
            "_original_bindings": {"name": "x", "value": 1, "rest": None},
            "stack": None,
            "_match_ctx": {}
        }

        result, trace = run_with_trace(combined_projections, state)

        # EVIDENCE: bridge.lookup.found_same must fire
        assert "bridge.lookup.found_same" in trace, (
            f"bridge.lookup.found_same was NOT executed!\n"
            f"Trace: {trace}\n"
            f"Non-linear pattern support is NOT coming from bridge projections!"
        )

    def test_bridge_lookup_found_different_fires_for_conflict(self, combined_projections):
        """
        EVIDENCE: bridge.lookup.found_different must fire when same var has different value.

        This is the binding conflict detection. If it doesn't fire,
        we're getting NO_MATCH from Python, not from projections.
        """
        # State with existing binding but different value
        state = {
            "mode": "match",
            "_phase": "lookup_binding",
            "_lookup_name": "x",
            "_lookup_value": 2,  # Different value!
            "_lookup_bindings": {
                "name": "x",
                "value": 1,  # Was bound to 1
                "rest": None
            },
            "_original_bindings": {"name": "x", "value": 1, "rest": None},
            "stack": None,
            "_match_ctx": {}
        }

        result, trace = run_with_trace(combined_projections, state)

        # EVIDENCE: bridge.lookup.found_different must fire
        assert "bridge.lookup.found_different" in trace, (
            f"bridge.lookup.found_different was NOT executed!\n"
            f"Trace: {trace}\n"
            f"Binding conflict detection is NOT coming from bridge projections!"
        )

    def test_bridge_lookup_not_found_yet_fires_for_search(self, combined_projections):
        """
        EVIDENCE: bridge.lookup.not_found_yet must fire when searching through bindings.
        """
        # State with bindings but name not at head
        state = {
            "mode": "match",
            "_phase": "lookup_binding",
            "_lookup_name": "y",  # Looking for y
            "_lookup_value": 2,
            "_lookup_bindings": {
                "name": "x",  # But head is x
                "value": 1,
                "rest": None
            },
            "_original_bindings": {"name": "x", "value": 1, "rest": None},
            "stack": None,
            "_match_ctx": {}
        }

        result, trace = run_with_trace(combined_projections, state)

        # EVIDENCE: bridge.lookup.not_found_yet must fire to continue searching
        assert "bridge.lookup.not_found_yet" in trace, (
            f"bridge.lookup.not_found_yet was NOT executed!\n"
            f"Trace: {trace}\n"
            f"Binding search is NOT using bridge projections!"
        )


class TestExecutionPathIntegrity:
    """
    Integration tests that verify the complete execution path.
    """

    def test_full_non_linear_match_uses_bridge(self, combined_projections):
        """
        Complete test: non-linear pattern match must use bridge projections.

        Input: {"a": {"var": "x"}, "b": {"var": "x"}} vs {"a": 1, "b": 1}
        Expected: Match succeeds, and bridge.lookup.found_same fired
        """
        from rcx_pi.selfhost.match_mu import normalize_for_match

        pattern = normalize_for_match({"a": {"var": "x"}, "b": {"var": "x"}})
        value = normalize_for_match({"a": 1, "b": 1})

        state = {
            "match": {"pattern": pattern, "value": value},
            "_match_ctx": {}
        }

        result, trace = run_with_trace(combined_projections, state, max_steps=200)

        # Check behavior is correct
        assert result.get("_mode") == "match_done"
        assert result.get("_status") == "success"

        # EVIDENCE: Bridge projections must have fired
        bridge_projections_in_trace = [p for p in trace if p.startswith("bridge.")]
        assert len(bridge_projections_in_trace) >= 2, (
            f"Too few bridge projections fired for non-linear match!\n"
            f"Bridge projections: {bridge_projections_in_trace}\n"
            f"Full trace: {trace}\n"
            f"Expected at least bridge.var.check_existing and bridge.lookup.*"
        )

    def test_non_linear_conflict_uses_bridge_for_rejection(self, combined_projections):
        """
        Complete test: non-linear pattern conflict must use bridge.lookup.found_different.

        Input: {"a": {"var": "x"}, "b": {"var": "x"}} vs {"a": 1, "b": 2}
        Expected: NO_MATCH, and bridge.lookup.found_different fired
        """
        from rcx_pi.selfhost.match_mu import normalize_for_match

        pattern = normalize_for_match({"a": {"var": "x"}, "b": {"var": "x"}})
        value = normalize_for_match({"a": 1, "b": 2})

        state = {
            "match": {"pattern": pattern, "value": value},
            "_match_ctx": {}
        }

        result, trace = run_with_trace(combined_projections, state, max_steps=200)

        # Check behavior is correct
        assert result.get("_mode") == "match_done"
        assert result.get("_status") == "no_match"

        # EVIDENCE: bridge.lookup.found_different must have fired
        assert "bridge.lookup.found_different" in trace, (
            f"bridge.lookup.found_different did NOT fire for binding conflict!\n"
            f"Trace: {trace}\n"
            f"The NO_MATCH came from a different code path, not bridge projections."
        )


class TestWiringVerification:
    """
    Verify that code is wired to use the correct paths.
    """

    def test_load_combined_kernel_with_bridge_has_correct_order(self):
        """
        Verify bridge projections come BEFORE match.var in combined kernel.

        This is critical: bridge.var.check_existing must intercept
        before match.var handles variable binding.
        """
        from rcx_pi.selfhost.step_mu import load_combined_kernel_with_bridge_projections

        projs = load_combined_kernel_with_bridge_projections()
        ids = [p.get("id") for p in projs]

        bridge_idx = ids.index("bridge.var.check_existing")
        match_var_idx = ids.index("match.var")

        assert bridge_idx < match_var_idx, (
            f"WIRING ERROR: bridge.var.check_existing (index {bridge_idx}) "
            f"must come BEFORE match.var (index {match_var_idx})!\n"
            f"Current order allows match.var to intercept first, "
            f"bypassing bridge entirely."
        )

    def test_all_bridge_projections_present_in_combined_kernel(self):
        """
        Verify all 5 bridge projections are in combined kernel.
        """
        from rcx_pi.selfhost.step_mu import load_combined_kernel_with_bridge_projections

        projs = load_combined_kernel_with_bridge_projections()
        ids = [p.get("id") for p in projs]

        expected_bridge = [
            "bridge.var.check_existing",
            "bridge.lookup.found_same",
            "bridge.lookup.found_different",
            "bridge.lookup.not_found_yet",
            "bridge.lookup.not_found"
        ]

        for proj_id in expected_bridge:
            assert proj_id in ids, (
                f"WIRING ERROR: {proj_id} is missing from combined kernel!\n"
                f"Bridge projections found: {[p for p in ids if p.startswith('bridge.')]}"
            )

    def test_runtime_bridge_ordering_guard_rejects_invalid_order(self):
        """
        Runtime guard should reject bridge ordering regressions.
        """
        import rcx_pi.selfhost.step_mu as step_mu_module
        validate_ordering = getattr(step_mu_module, "_validate_combined_bridge_ordering")

        invalid = [
            {"id": "kernel.wrap"},
            {"id": "match.var"},
            {"id": "bridge.var.check_existing"},
            {"id": "bridge.lookup.found_same"},
            {"id": "bridge.lookup.found_different"},
            {"id": "bridge.lookup.not_found_yet"},
            {"id": "bridge.lookup.not_found"},
        ]

        with pytest.raises(ValueError, match="Bridge ordering invariant failed"):
            validate_ordering(invalid)


# =============================================================================
# Algorithm Execution Path Verification
# =============================================================================


class TestAlgorithmExecutionPath:
    """
    Verify algorithm (recurrence/exhaustion) execution uses expected path.

    9-agent finding (Fuzzer): Algorithm execution may fall back to bootstrap
    without detection. These tests verify which projections actually fire.

    NOTE (Gate 4): Default algorithm runtime path is structural:
    run_algorithm_meta_circular() -> step_kernel_mu(kernel_mode="bridge").
    Bootstrap execution is explicit fallback only.
    """

    @pytest.fixture
    def recurrence_projections(self):
        """Load recurrence projections."""
        path = Path(__file__).parent.parent / "mu" / "closures" / "recurrence.v1.json"
        with open(path) as f:
            seed = json.load(f)
        return seed["projections"]

    @pytest.fixture
    def exhaustion_projections(self):
        """Load exhaustion projections."""
        path = Path(__file__).parent.parent / "mu" / "closures" / "exhaustion.v1.json"
        with open(path) as f:
            seed = json.load(f)
        return seed["projections"]

    def test_recurrence_closure_projection_fires(self, recurrence_projections):
        """
        EVIDENCE: recurrence.found_in_seen must fire when state repeats.

        This test verifies the non-linear pattern (same var twice for state equality)
        actually executes via the recurrence projections.

        The seen-set stores STATES directly (not {state, step} entries).
        _check_list.head must equal _state for the non-linear pattern to match.
        """
        # Input where state "A" is in the check_list
        # The non-linear pattern requires _check_list.head == _state
        input_data = {
            "_mode": "recurrence",
            "_phase": "check_seen",
            "_state": "A",  # The state we're checking
            "_step": 2,
            "_rest": None,
            "_seen": {"head": "A", "tail": None},  # Seen-set stores states directly
            "_check_list": {"head": "A", "tail": None},  # Must have head == _state
            "_result": "final"
        }

        result, trace = run_with_trace(recurrence_projections, input_data, max_steps=50)

        # EVIDENCE: recurrence.found_in_seen must fire
        assert "recurrence.found_in_seen" in trace, (
            f"recurrence.found_in_seen was NOT executed!\n"
            f"Trace: {trace}\n"
            f"This means closure detection didn't use the non-linear pattern."
        )

        # Should detect closure
        assert result.get("_closure") is True or result.get("closure_detected") is True

    def test_recurrence_not_in_head_projection_fires(self, recurrence_projections):
        """
        EVIDENCE: recurrence.not_in_head must fire when state differs.

        Tests that first-match-wins ordering works (found_in_seen doesn't
        match when states differ).
        """
        # Input where state "B" is not in seen (only "A" is seen)
        # _check_list.head is "A" but _state is "B" - should NOT match found_in_seen
        input_data = {
            "_mode": "recurrence",
            "_phase": "check_seen",
            "_state": "B",  # Different from check_list head
            "_step": 2,
            "_rest": None,
            "_seen": {"head": "A", "tail": None},  # Seen-set stores states directly
            "_check_list": {"head": "A", "tail": None},  # Different from _state
            "_result": "final"
        }

        result, trace = run_with_trace(recurrence_projections, input_data, max_steps=50)

        # EVIDENCE: recurrence.not_in_head must fire (not found_in_seen)
        assert "recurrence.not_in_head" in trace, (
            f"recurrence.not_in_head was NOT executed!\n"
            f"Trace: {trace}\n"
            f"First-match-wins ordering may be broken."
        )

    def test_exhaustion_scan_same_projection_fires(self, exhaustion_projections):
        """
        EVIDENCE: exhaustion.scan_same must fire when operator repeats.

        This test verifies the non-linear pattern (same var for operator equality)
        actually executes via the exhaustion projections.
        """
        # Input in scan phase where operator matches tau_operator
        input_data = {
            "_mode": "exhaustion",
            "_phase": "scan",
            "_trace": {
                "head": {"step": 1, "state": "B", "projection": "op1"},
                "tail": None
            },
            "_tau_step": 0,
            "_tau_operator": "op1",  # Same as trace entry
            "_frozen": None,
            "_operator_ids": {"head": "op1", "tail": None}
        }

        result, trace = run_with_trace(exhaustion_projections, input_data, max_steps=50)

        # EVIDENCE: exhaustion.scan_same must fire
        assert "exhaustion.scan_same" in trace, (
            f"exhaustion.scan_same was NOT executed!\n"
            f"Trace: {trace}\n"
            f"This means operator equality didn't use the non-linear pattern."
        )

    def test_exhaustion_scan_different_projection_fires(self, exhaustion_projections):
        """
        EVIDENCE: exhaustion.scan_different must fire when operator differs.

        Tests that first-match-wins ordering works (scan_same doesn't
        match when operators differ).
        """
        # Input in scan phase where operator differs from tau_operator
        input_data = {
            "_mode": "exhaustion",
            "_phase": "scan",
            "_trace": {
                "head": {"step": 1, "state": "B", "projection": "op2"},  # Different operator
                "tail": None
            },
            "_tau_step": 0,
            "_tau_operator": "op1",  # Different from trace entry
            "_frozen": None,
            "_operator_ids": {"head": "op1", "tail": {"head": "op2", "tail": None}}
        }

        result, trace = run_with_trace(exhaustion_projections, input_data, max_steps=50)

        # EVIDENCE: exhaustion.scan_different must fire (not scan_same)
        assert "exhaustion.scan_different" in trace, (
            f"exhaustion.scan_different was NOT executed!\n"
            f"Trace: {trace}\n"
            f"First-match-wins ordering may be broken."
        )

    def test_exhaustion_frozen_found_projection_fires(self, exhaustion_projections):
        """
        EVIDENCE: exhaustion.frozen_found must fire when operator is in frozen list.

        This tests the non-linear pattern for frozen list membership.
        """
        # Input in check_frozen phase where operator is already frozen
        input_data = {
            "_mode": "exhaustion",
            "_phase": "check_frozen",
            "_operator": "op1",
            "_frozen": {"head": "op1", "tail": None},  # op1 is frozen
            "_frozen_check": {"head": "op1", "tail": None},  # Cursor at op1
            "_operator_ids": {"head": "op1", "tail": None}
        }

        result, trace = run_with_trace(exhaustion_projections, input_data, max_steps=50)

        # EVIDENCE: exhaustion.frozen_found must fire
        assert "exhaustion.frozen_found" in trace, (
            f"exhaustion.frozen_found was NOT executed!\n"
            f"Trace: {trace}\n"
            f"This means frozen membership didn't use the non-linear pattern."
        )

        # Should return already_frozen action
        assert result.get("action") == "already_frozen"

    def test_exhaustion_do_freeze_projection_fires(self, exhaustion_projections):
        """
        EVIDENCE: exhaustion.do_freeze must fire when operator is not frozen.

        Tests that freeze action is taken when operator exhausted but not yet frozen.
        """
        # Input in check_frozen phase where frozen list is empty (null)
        input_data = {
            "_mode": "exhaustion",
            "_phase": "check_frozen",
            "_operator": "op1",
            "_frozen": None,  # Empty frozen list
            "_frozen_check": None,  # Cursor at end (null)
            "_operator_ids": {"head": "op1", "tail": None}
        }

        result, trace = run_with_trace(exhaustion_projections, input_data, max_steps=50)

        # EVIDENCE: exhaustion.do_freeze must fire
        assert "exhaustion.do_freeze" in trace, (
            f"exhaustion.do_freeze was NOT executed!\n"
            f"Trace: {trace}"
        )

        # Should return freeze action
        assert result.get("action") == "freeze"
        assert result.get("exhaustion_detected") is True

    def test_default_runtime_does_not_use_bootstrap_fallback(self, monkeypatch):
        """
        EVIDENCE: run_algorithm_meta_circular() default path must use structural kernel.

        If this regresses to bootstrap fallback silently, Gate 4 cutover is broken.
        """
        from rcx_pi.selfhost.step_mu import run_algorithm_meta_circular

        def fail_bootstrap(*_args, **_kwargs):
            raise AssertionError("bootstrap fallback executed on default path")

        monkeypatch.setattr("rcx_pi.selfhost.step_mu.step_algorithm_with_bridge", fail_bootstrap)

        # Use a patched kernel entry so test is path-focused (not seed semantics-focused).
        monkeypatch.setattr(
            "rcx_pi.selfhost.step_mu.step_kernel_mu",
            lambda *_args, **_kwargs: {"mode": "kernel_path"}
        )

        out = run_algorithm_meta_circular(
            [],
            {"_detect_closure": {"trace": None, "result": "x"}},
        )
        assert out == {"mode": "kernel_path"}
