"""
Test-only bounded projection stepper.

Replaces make_projection_runner's run() for test callers after
projection_runner.py retirement (Wave 3F). Same stepping semantics:
loop eval_seed.step(), hash-based stall detection, terminal-field check.

Does NOT consume the global step budget — test callers manage their own
budget context if needed.

Import: from tests.helpers.projection_stepper import run_projections
"""

from __future__ import annotations

from rcx_pi.selfhost.mu_type import Mu, mu_hash_control_cached
from rcx_pi.selfhost.eval_seed import step


def run_projections(
    projections: list[Mu],
    initial_state: Mu,
    *,
    max_steps: int = 200,
    terminal_field: str = "mode",
    terminal_value: str | None = None,
) -> tuple[Mu, int, bool]:
    """Run projections until terminal, stall, or max_steps.

    Args:
        projections: List of projection dicts.
        initial_state: Starting Mu state.
        max_steps: Maximum dispatch cycles.
        terminal_field: Dict key for terminal detection (default "mode").
        terminal_value: Value indicating terminal. If None, terminal
            detection is disabled (run to stall or max_steps).
            Callers should always pass this explicitly.

    Returns:
        (final_state, steps_taken, is_stall)

    Stall distinguishability:
        is_stall=True, steps < max_steps  → genuine stall (unchanged state)
        is_stall=True, steps == max_steps → exhaustion (budget ran out)
        is_stall=False                    → terminal reached
    """
    def _is_terminal(state):
        if terminal_value is None:
            return False
        return (
            isinstance(state, dict)  # AST_OK: test helper — type guard
            and state.get(terminal_field) == terminal_value
        )

    state = initial_state
    state_hash = mu_hash_control_cached(initial_state, "test_stepper")

    for i in range(max_steps):
        if _is_terminal(state):
            return state, i, False

        next_state = step(projections, state)
        next_hash = mu_hash_control_cached(next_state, "test_stepper.stall")

        if next_hash == state_hash:
            return state, i, True

        state = next_state
        state_hash = next_hash

    # Post-loop terminal check (terminal-on-last-step)
    if _is_terminal(state):
        return state, max_steps, False

    return state, max_steps, True
