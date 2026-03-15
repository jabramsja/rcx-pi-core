"""
Projection Runner Factory - Phase 6d Consolidation

This module provides a factory for creating projection runners.
It consolidates the duplicated runner pattern from match_mu.py, subst_mu.py,
and classify_mu.py.

See mu/docs/core/SelfHosting.v0.md for design.
"""

from __future__ import annotations

from typing import Callable

from .mu_type import Mu, mu_hash_cached, mu_hash_control_cached
from .eval_seed import _step_trusted
from .kernel import get_step_budget


def make_projection_runner(mode_name: str, *, terminal_field: str = "mode") -> tuple[
    Callable[[Mu], bool],
    Callable[[Mu], bool],
    Callable[[list[Mu], Mu, int], tuple[Mu, int, bool]]
]:
    """
    Create a projection runner for a specific mode.

    Returns a (is_done_fn, is_state_fn, run_fn) tuple:
    - is_done_fn: Check if state is completed (terminal_field == "{mode_name}_done")
    - is_state_fn: Check if state is in progress (mode == "{mode_name}")
    - run_fn: Run projections until done or stall

    This consolidates the runner pattern used by match/subst/classify.

    HOST ITERATION DEBT: The returned run() function contains a for-loop that
    iterates projections. This is semantic debt tracked toward L4 elimination
    when the meta-circular kernel handles match/subst internally. Cannot use
    decorator on nested function, so documented here instead.

    # BOUNDARY: iteration debt (off kernel path — used by match_mu/subst_mu/classify_mu, not step_kernel_mu)

    Args:
        mode_name: The mode name (e.g., "match", "subst", "classify")
        terminal_field: The field name to check for terminal state detection.
            Default "mode" (v1 projections). Use "_mode" for v2 projections
            where terminal states use underscore-prefixed fields.

    Returns:
        Tuple of (is_done, is_state, run_projections) functions

    Example:
        is_match_done, _, run_match_projections = make_projection_runner("match")
        result, steps, is_stall = run_match_projections(projections, initial_state)

        # For v2 projections with _mode terminal field:
        is_done_v2, _, run_v2 = make_projection_runner("match", terminal_field="_mode")
    """
    done_mode = f"{mode_name}_done"

    def is_done(state: Mu) -> bool:
        """Check if state is a completed result."""
        return (
            isinstance(state, dict)  # AST_OK: infra — type guard for projection state
            and state.get(terminal_field) == done_mode
        )

    def is_state(state: Mu) -> bool:
        """Check if state is in-progress."""
        return (
            isinstance(state, dict)  # AST_OK: infra — type guard for projection state
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

        Stall distinguishability (D7):
            When is_stall=True, callers can distinguish the cause:
            - steps_taken == max_steps → max-steps exhaustion (budget ran out)
            - steps_taken < max_steps  → genuine stall (state unchanged)

        Raises:
            RuntimeError: If global step budget exceeded.
        """
        budget = get_step_budget()
        state = initial_state
        # INVARIANT: step() is functionally pure — state_hash caching is safe.
        state_hash = mu_hash_control_cached(initial_state, "projection_runner")
        for i in range(max_steps):
            # Check if done
            if is_done(state):
                # Report steps consumed to global budget
                budget.consume(i)
                return state, i, False

            # Take a step — trusted: boundary validated by caller (match_mu, subst_mu)
            next_state = _step_trusted(projections, state)

            # Check for stall (no change) - use mu_hash_control_cached for numeric safety
            next_hash = mu_hash_control_cached(next_state, "projection_runner.stall")
            if next_hash == state_hash:
                # Report steps consumed to global budget.
                # A step was executed before stall detection, so consume i + 1.
                budget.consume(i + 1)
                return state, i, True

            state = next_state
            state_hash = next_hash

        # Final done check: if the last step produced a terminal state,
        # return done (not exhaustion). Without this, terminal-on-last-step
        # would be misclassified as max-steps exhaustion.
        if is_done(state):
            budget.consume(max_steps)
            return state, max_steps, False

        # Max steps exceeded — distinguishable from genuine stall:
        # steps_taken == max_steps (exhaustion) vs steps_taken < max_steps (stall).
        budget.consume(max_steps)
        return state, max_steps, True

    return is_done, is_state, run
