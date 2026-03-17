"""
Wave 3D-A gate test: stage0_vm_run_bounded shared helper.

Verifies the three-outcome contract (terminal/stall/exhaustion) and
parity with projection_runner semantics. This helper is a Python-only
boundary helper, NOT a JS parity target.
"""

from __future__ import annotations

import json

import pytest

from rcx_pi.selfhost.stage0_vm import (
    stage0_vm_run_bounded,  # ANTICHEAT_OK: test-only — gate test for bounded helper
    stage0_vm_step,
    validate_bundle,
    Stage0VMError,
)


# ---------------------------------------------------------------------------
# Fixtures: minimal bundles for testing
# ---------------------------------------------------------------------------

def _make_counter_bundle(steps_to_terminal: int):
    """Build a bundle that counts down to terminal via a 'remaining' field.

    Each step decrements 'remaining'. When remaining == 0, transitions to
    mode=test_done (terminal). This gives deterministic step counts.
    """
    programs = []
    program_order = []

    # Program 1: remaining > 0 → decrement (for each specific value)
    # We create one program per remaining value to avoid needing arithmetic opcodes.
    for i in range(steps_to_terminal, 0, -1):
        pid = f"count.step_{i}"
        programs.append({
            "id": pid,
            "ops": [
                {"op": "assert_focus_kind", "path": ["focus", "root"], "kind": "dict"},
                {"op": "assert_key_profile", "path": ["focus", "root"],
                 "required": ["remaining", "mode"]},
                {"op": "check_equal", "path": ["focus", "root", "remaining"], "value": i},
                {"op": "check_equal", "path": ["focus", "root", "mode"], "value": "running"},
                {"op": "write_path", "template": {
                    "kind": "object",
                    "fields": {
                        "mode": {"kind": "literal", "value": "running"},
                        "remaining": {"kind": "literal", "value": i - 1},
                    },
                }},
                {"op": "return_projection_success"},
            ],
        })
        program_order.append(pid)

    # Program 2: remaining == 0 → terminal
    pid_done = "count.done"
    programs.append({
        "id": pid_done,
        "ops": [
            {"op": "assert_focus_kind", "path": ["focus", "root"], "kind": "dict"},
            {"op": "check_equal", "path": ["focus", "root", "remaining"], "value": 0},
            {"op": "check_equal", "path": ["focus", "root", "mode"], "value": "running"},
            {"op": "write_path", "template": {
                "kind": "object",
                "fields": {
                    "mode": {"kind": "literal", "value": "test_done"},
                    "remaining": {"kind": "literal", "value": 0},
                },
            }},
            {"op": "return_projection_success"},
        ],
    })
    program_order.append(pid_done)

    return {
        "stage0_ir_version": 1,
        "bundle_id": f"test_counter_{steps_to_terminal}",
        "source_seed": "test",
        "machine_profile": "rcx.stage0.v1",
        "program_order": program_order,
        "programs": programs,
        "hand_authored": True,
    }


def _make_stall_bundle():
    """Bundle where no program ever matches — immediate stall."""
    return {
        "stage0_ir_version": 1,
        "bundle_id": "test_stall",
        "source_seed": "test",
        "machine_profile": "rcx.stage0.v1",
        "program_order": ["never_match"],
        "programs": [{
            "id": "never_match",
            "ops": [
                {"op": "check_equal", "path": ["focus", "root"], "value": "__impossible__"},
                {"op": "write_path", "template": {"kind": "literal", "value": None}},
                {"op": "return_projection_success"},
            ],
        }],
        "hand_authored": True,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStage0VmRunBoundedGate:
    """Gate tests for stage0_vm_run_bounded three-outcome contract."""

    def test_terminal_after_n_steps(self):
        """Bundle reaches terminal after 3 steps."""
        bundle = _make_counter_bundle(3)
        initial = {"mode": "running", "remaining": 3}

        outcome = stage0_vm_run_bounded(
            bundle, initial,
            terminal_field="mode",
            terminal_value="test_done",
        )

        assert outcome["status"] == "terminal"
        assert outcome["root"]["mode"] == "test_done"
        assert outcome["root"]["remaining"] == 0
        assert outcome["steps"] == 4  # 3 decrements + 1 done transition

    def test_immediate_terminal(self):
        """Input is already terminal — pre-step fast path catches it."""
        bundle = _make_stall_bundle()  # doesn't matter, won't be called
        initial = {"mode": "test_done", "result": 42}

        outcome = stage0_vm_run_bounded(
            bundle, initial,
            terminal_field="mode",
            terminal_value="test_done",
        )

        assert outcome["status"] == "terminal"
        assert outcome["root"] == initial
        assert outcome["steps"] == 0  # no VM dispatch needed

    def test_genuine_stall(self):
        """State not terminal, no projection matches — genuine stall."""
        bundle = _make_stall_bundle()
        initial = {"mode": "running", "data": "hello"}

        outcome = stage0_vm_run_bounded(
            bundle, initial,
            terminal_field="mode",
            terminal_value="test_done",
        )

        assert outcome["status"] == "stall"
        assert outcome["root"] == initial
        assert outcome["steps"] == 0  # nothing matched
        assert outcome["steps"] < 1000  # distinguishable from exhaustion

    def test_max_step_exhaustion(self):
        """All max_steps consumed without terminal or stall — exhaustion."""
        # Bundle that needs 10 steps but we only allow 5
        bundle = _make_counter_bundle(10)
        initial = {"mode": "running", "remaining": 10}

        outcome = stage0_vm_run_bounded(
            bundle, initial,
            max_steps=5,  # only allow 5 steps
            terminal_field="mode",
            terminal_value="test_done",
        )

        assert outcome["status"] == "exhaustion"
        assert outcome["steps"] == 5  # consumed all allowed steps

    def test_terminal_on_last_step(self):
        """Terminal reached on exactly the last allowed step — returns terminal, not exhaustion."""
        bundle = _make_counter_bundle(3)
        initial = {"mode": "running", "remaining": 3}

        # 4 steps needed (3 decrements + 1 done), allow exactly 4
        outcome = stage0_vm_run_bounded(
            bundle, initial,
            max_steps=4,
            terminal_field="mode",
            terminal_value="test_done",
        )

        # The 4th step produces terminal, then pre-step check catches it
        # OR the loop exits and post-loop terminal check catches it.
        # Either way: terminal, not exhaustion.
        assert outcome["status"] == "terminal"
        assert outcome["root"]["mode"] == "test_done"
        assert outcome["steps"] == 4

    def test_steps_count_matches_successful_matches(self):
        """steps field counts successful projection matches, not loop iterations."""
        bundle = _make_counter_bundle(2)
        initial = {"mode": "running", "remaining": 2}

        outcome = stage0_vm_run_bounded(
            bundle, initial,
            terminal_field="mode",
            terminal_value="test_done",
        )

        assert outcome["status"] == "terminal"
        # 2 decrements + 1 done transition = 3 successful matches
        assert outcome["steps"] == 3

    def test_terminal_value_none_disables_detection(self):
        """terminal_value=None runs until stall or exhaustion — no terminal detection."""
        bundle = _make_counter_bundle(3)
        initial = {"mode": "running", "remaining": 3}

        # Without terminal detection, the done state will stall (no projection matches it)
        outcome = stage0_vm_run_bounded(
            bundle, initial,
            terminal_value=None,
        )

        # The counter reaches done state, then stalls because no projection matches
        assert outcome["status"] == "stall"
        assert outcome["root"]["mode"] == "test_done"
        assert outcome["steps"] == 4  # 3 decrements + 1 done

    def test_does_not_consume_budget(self):
        """Helper does NOT consume global step budget — caller responsibility."""
        from rcx_pi.selfhost.kernel import get_step_budget

        budget = get_step_budget()
        initial_remaining = budget.get_remaining()

        bundle = _make_counter_bundle(2)
        initial = {"mode": "running", "remaining": 2}

        stage0_vm_run_bounded(
            bundle, initial,
            terminal_field="mode",
            terminal_value="test_done",
        )

        # Budget unchanged — helper doesn't touch it
        assert budget.get_remaining() == initial_remaining

    def test_max_steps_one_exhaustion(self):
        """max_steps=1 with non-terminal match → exhaustion with steps=1."""
        bundle = _make_counter_bundle(5)  # needs 5+ steps
        initial = {"mode": "running", "remaining": 5}

        outcome = stage0_vm_run_bounded(
            bundle, initial,
            max_steps=1,
            terminal_field="mode",
            terminal_value="test_done",
        )

        assert outcome["status"] == "exhaustion"
        assert outcome["steps"] == 1  # one match consumed the single allowed step

    def test_vm_fault_propagates(self):
        """Stage0VMError from stage0_vm_step propagates (not caught)."""
        # Create a bundle that will cause an op-limit error
        huge_ops = [{"op": "check_equal", "path": ["focus", "root"], "value": "x"}] * 2000
        huge_ops.append({"op": "return_projection_fail"})
        bundle = {
            "stage0_ir_version": 1,
            "bundle_id": "test_fault",
            "source_seed": "test",
            "machine_profile": "rcx.stage0.v1",
            "program_order": ["huge"],
            "programs": [{"id": "huge", "ops": huge_ops}],
            "hand_authored": True,
        }

        with pytest.raises(Stage0VMError, match="Op limit exceeded"):
            stage0_vm_run_bounded(bundle, "x", terminal_value="done")
