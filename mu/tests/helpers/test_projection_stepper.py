"""
Semantic-lock tests for the test-only projection stepper.

Wave 3F: proves the helper preserves the bounded-run contract that
parity/fuzz callers depend on. These 4 behaviors were previously proven
by test_projection_runner.py::TestStallDistinguishability — that file
is deleted as part of projection_runner retirement.
"""

import pytest

from tests.helpers.projection_stepper import run_projections


class TestProjectionStepperContract:
    """Prove the 4 behavioral properties callers depend on."""

    def test_immediate_stall(self):
        """Empty projections → is_stall=True, steps=0."""
        state, steps, is_stall = run_projections(
            [], {"mode": "test", "data": 42},
            max_steps=10,
            terminal_value="test_done",
        )
        assert is_stall is True
        assert steps == 0

    def test_max_steps_exhaustion(self):
        """Flip-flop projections exhaust max_steps: is_stall=True, steps==max_steps."""
        projections = [
            {"id": "flip.a", "pattern": {"mode": "test", "val": "a"},
             "body": {"mode": "test", "val": "b"}},
            {"id": "flip.b", "pattern": {"mode": "test", "val": "b"},
             "body": {"mode": "test", "val": "a"}},
        ]
        state, steps, is_stall = run_projections(
            projections, {"mode": "test", "val": "a"},
            max_steps=6,
            terminal_value="test_done",
        )
        assert is_stall is True
        assert steps == 6, f"Expected steps==max_steps==6, got {steps}"

    def test_terminal_on_last_step(self):
        """Terminal state on exactly max_steps=1 → is_stall=False."""
        projections = [
            {"id": "finish", "pattern": {"mode": "test", "val": "start"},
             "body": {"mode": "test_done", "val": "end"}},
        ]
        state, steps, is_stall = run_projections(
            projections, {"mode": "test", "val": "start"},
            max_steps=1,
            terminal_value="test_done",
        )
        assert state.get("mode") == "test_done"
        assert is_stall is False, "Terminal on last step should be done, not exhaustion"

    def test_terminal_field_override(self):
        """terminal_field='_mode' detects _mode terminal, rejects mode terminal."""
        # _mode terminal should be detected
        projections = [
            {"id": "finish", "pattern": {"mode": "test", "val": "start"},
             "body": {"_mode": "test_done", "val": "end"}},
        ]
        state, steps, is_stall = run_projections(
            projections, {"mode": "test", "val": "start"},
            max_steps=10,
            terminal_field="_mode",
            terminal_value="test_done",
        )
        assert state.get("_mode") == "test_done"
        assert is_stall is False

        # mode terminal should NOT be detected when checking _mode
        projections_v1 = [
            {"id": "finish_v1", "pattern": {"mode": "test", "val": "go"},
             "body": {"mode": "test_done", "val": "end"}},
        ]
        state2, steps2, is_stall2 = run_projections(
            projections_v1, {"mode": "test", "val": "go"},
            max_steps=10,
            terminal_field="_mode",
            terminal_value="test_done",
        )
        # The body has mode="test_done" but we check _mode — should stall
        assert is_stall2 is True, "mode terminal should not match _mode check"
