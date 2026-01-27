"""
Substitute as Mu Projections - Phase 4b Self-Hosting

This module implements variable substitution using Mu projections instead of
Python recursion. It achieves parity with eval_seed.substitute() but uses
the kernel loop for iteration.

See docs/core/SelfHosting.v0.md for design.
"""

from __future__ import annotations

from .mu_type import Mu, assert_mu, mu_equal
from .eval_seed import step
from .kernel import get_step_budget
from .seed_integrity import load_verified_seed, get_seeds_dir
from .match_mu import (
    normalize_for_match,
    denormalize_from_match,
    dict_to_bindings,
    bindings_to_dict,
    _check_empty_var_names,
)


# =============================================================================
# Projection Loading
# =============================================================================

_SUBST_PROJECTIONS: list[Mu] | None = None


def load_subst_projections() -> list[Mu]:
    """Load substitute projections from seeds/subst.v1.json with integrity verification."""
    global _SUBST_PROJECTIONS
    if _SUBST_PROJECTIONS is not None:
        return _SUBST_PROJECTIONS

    seed_path = get_seeds_dir() / "subst.v1.json"
    seed = load_verified_seed(seed_path)

    _SUBST_PROJECTIONS = seed["projections"]
    return _SUBST_PROJECTIONS


def clear_projection_cache() -> None:
    """Clear cached projections (for testing)."""
    global _SUBST_PROJECTIONS
    _SUBST_PROJECTIONS = None


# =============================================================================
# Substitute Runner
# =============================================================================


def is_subst_done(state: Mu) -> bool:
    """Check if state is a completed substitute result."""
    return (
        isinstance(state, dict)
        and state.get("mode") == "subst_done"
    )


def is_subst_state(state: Mu) -> bool:
    """Check if state is an in-progress substitute state."""
    return (
        isinstance(state, dict)
        and state.get("mode") == "subst"
    )


def run_subst_projections(
    projections: list[Mu],
    initial_state: Mu,
    max_steps: int = 1000
) -> tuple[Mu, int, bool]:
    """
    Run substitute projections until done or stall.

    Reports steps to the global step budget for cross-call resource accounting.

    As of Phase 6a, lookup is handled structurally by subst.lookup.found and
    subst.lookup.next projections - bindings are embedded in initial_state.

    Returns:
        (final_state, steps_taken, is_stall)

    Raises:
        RuntimeError: If global step budget exceeded.
    """
    budget = get_step_budget()
    state = initial_state
    for i in range(max_steps):
        # Check if done
        if is_subst_done(state):
            # Report steps consumed to global budget
            budget.consume(i)
            return state, i, False

        # Take a step (lookup is now handled by subst.lookup.* projections)
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


def is_head_tail_structure(value: Mu) -> bool:
    """Check if value is a head/tail dict (not a normalized list/dict)."""
    return (
        isinstance(value, dict)
        and set(value.keys()) == {"head", "tail"}
    )


def subst_mu(body: Mu, bindings: dict[str, Mu]) -> Mu:
    """
    Substitute variables in body with bound values using Mu projections.

    This is the parity function for eval_seed.substitute().

    Args:
        body: The body with possible {"var": "x"} sites.
        bindings: Dict mapping variable names to values.

    Returns:
        Body with variables replaced by their bound values.

    Raises:
        KeyError: If a variable in body is not in bindings.
    """
    assert_mu(body, "subst_mu.body")

    # Validate no empty variable names (parity with eval_seed.py)
    _check_empty_var_names(body, "body")

    # Check if body is already in head/tail form (structural dict)
    # If so, we shouldn't denormalize it back to a list
    body_was_head_tail = is_head_tail_structure(body)

    # Normalize body to head/tail structure
    norm_body = normalize_for_match(body)

    # Convert bindings dict to linked list
    linked_bindings = dict_to_bindings(bindings)

    # Load projections
    projections = load_subst_projections()

    # Wrap input in subst request format
    initial = {"subst": {"body": norm_body, "bindings": linked_bindings}}

    # Run projections (bindings are embedded in initial state)
    final_state, steps, is_stall = run_subst_projections(projections, initial)

    # Extract result
    if is_stall:
        # Check if we stalled on a lookup (unbound variable)
        # Phase 6a: lookup stalls when lookup_bindings is null
        if is_subst_state(final_state):
            phase = final_state.get("phase")
            if phase == "lookup":
                # Stalled in lookup phase = unbound variable
                name = final_state.get("lookup_name")
                raise KeyError(f"Unbound variable: {name}")
            # Legacy check for old lookup marker format (shouldn't happen now)
            focus = final_state.get("focus")
            if isinstance(focus, dict) and "lookup" in focus:
                name = focus["lookup"]
                raise KeyError(f"Unbound variable: {name}")
        raise RuntimeError(f"Substitute stalled unexpectedly: {final_state}")

    if is_subst_done(final_state):
        result = final_state.get("result")
        # Denormalize back to regular Python structures
        # But if the original body was head/tail, keep it as head/tail
        if body_was_head_tail:
            return result
        return denormalize_from_match(result)

    raise RuntimeError(f"Unexpected substitute state: {final_state}")
