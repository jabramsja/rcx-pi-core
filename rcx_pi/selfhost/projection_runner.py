"""
Projection Runner Factory - Phase 6d Consolidation

This module provides a factory for creating projection runners.
It consolidates the duplicated runner pattern from match_mu.py, subst_mu.py,
and classify_mu.py.

See docs/core/SelfHosting.v0.md for design.
"""

from __future__ import annotations

from typing import Callable

from .mu_type import Mu, mu_equal
from .eval_seed import step
from .kernel import get_step_budget


def make_projection_runner(mode_name: str) -> tuple[
    Callable[[Mu], bool],
    Callable[[Mu], bool],
    Callable[[list[Mu], Mu, int], tuple[Mu, int, bool]]
]:
    """
    Create a projection runner for a specific mode.

    Returns a (is_done_fn, is_state_fn, run_fn) tuple:
    - is_done_fn: Check if state is completed (mode == "{mode_name}_done")
    - is_state_fn: Check if state is in progress (mode == "{mode_name}")
    - run_fn: Run projections until done or stall

    This consolidates the runner pattern used by match/subst/classify.

    HOST ITERATION DEBT: The returned run() function contains a for-loop that
    iterates projections. This is semantic debt that Phase 7d will eliminate
    when the meta-circular kernel handles match/subst internally. Cannot use
    decorator on nested function, so documented here instead.

    # @host_iteration - nested function debt (counted by debt_dashboard.sh)

    Args:
        mode_name: The mode name (e.g., "match", "subst", "classify")

    Returns:
        Tuple of (is_done, is_state, run_projections) functions

    Example:
        is_match_done, is_match_state, run_match_projections = make_projection_runner("match")
        result, steps, is_stall = run_match_projections(projections, initial_state)
    """
    done_mode = f"{mode_name}_done"

    def is_done(state: Mu) -> bool:
        """Check if state is a completed result."""
        return (
            isinstance(state, dict)
            and state.get("mode") == done_mode
        )

    def is_state(state: Mu) -> bool:
        """Check if state is in-progress."""
        return (
            isinstance(state, dict)
            and state.get("mode") == mode_name
        )

    def run(
        projections: list[Mu],
        initial_state: Mu,
        max_steps: int = 1000
    ) -> tuple[Mu, int, bool]:
        """
        Run projections until done or stall.

        Reports steps to the global step budget for cross-call resource accounting.

        Returns:
            (final_state, steps_taken, is_stall)

        Raises:
            RuntimeError: If global step budget exceeded.
        """
        budget = get_step_budget()
        state = initial_state
        for i in range(max_steps):
            # Check if done
            if is_done(state):
                # Report steps consumed to global budget
                budget.consume(i)
                return state, i, False

            # Take a step
            next_state = step(projections, state)

            # Check for stall (no change) - use mu_equal to avoid Python type coercion
            if mu_equal(next_state, state):
                # Report steps consumed to global budget
                budget.consume(i)
                return state, i, True

            state = next_state

        # Max steps exceeded - treat as stall
        # Report steps consumed to global budget
        budget.consume(max_steps)
        return state, max_steps, True

    return is_done, is_state, run
