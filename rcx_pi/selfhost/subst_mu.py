"""
Substitute as Mu Projections - Phase 4b Self-Hosting

This module implements variable substitution using Mu projections instead of
Python recursion. It achieves parity with eval_seed.substitute() but uses
the kernel loop for iteration.

See docs/core/SelfHosting.v0.md for design.
"""

from __future__ import annotations

from typing import Any

from .mu_type import Mu, assert_mu, mu_equal
from .eval_seed import step, host_builtin
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
# Binding Lookup
# =============================================================================


@host_builtin("Linked list traversal using while - will become projection in L2")
def lookup_binding(name: str, bindings: Mu) -> Mu:
    """
    Look up a variable name in linked list bindings.

    Bindings format: {"name": "x", "value": 42, "rest": {...}} or null

    Args:
        name: Variable name to look up.
        bindings: Linked list of bindings.

    Returns:
        The bound value.

    Raises:
        KeyError: If variable is not bound.
    """
    current = bindings
    while current is not None:
        if not isinstance(current, dict):
            raise ValueError(f"Invalid bindings structure: {current}")
        if current.get("name") == name:
            return current.get("value")
        current = current.get("rest")
    raise KeyError(f"Unbound variable: {name}")


@host_builtin("Marker interpretation using isinstance - will become projection in L2")
def resolve_lookups(state: Mu, bindings: Mu) -> Mu:
    """
    Resolve any lookup markers in the state.

    The subst.var projection creates: {"lookup": name, "in": bindings}
    This function replaces that with the actual looked-up value.
    """
    if not isinstance(state, dict):
        return state

    if state.get("mode") != "subst":
        return state

    focus = state.get("focus")
    if isinstance(focus, dict) and "lookup" in focus and "in" in focus:
        # Resolve the lookup - validate types to prevent type confusion attacks
        name = focus["lookup"]
        lookup_bindings = focus["in"]

        # Type validation (adversary finding: non-string names silently fail)
        if not isinstance(name, str):
            raise TypeError(
                f"Lookup name must be str, got {type(name).__name__}: {name}"
            )
        if lookup_bindings is not None and not isinstance(lookup_bindings, dict):
            raise TypeError(
                f"Lookup bindings must be dict or null, got {type(lookup_bindings).__name__}"
            )

        try:
            value = lookup_binding(name, lookup_bindings)
            return {
                "mode": "subst",
                "phase": state.get("phase"),  # Preserve phase
                "focus": value,
                "bindings": state.get("bindings"),
                "context": state.get("context"),
            }
        except KeyError:
            raise

    return state


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
    bindings: Mu,
    max_steps: int = 1000
) -> tuple[Mu, int, bool]:
    """
    Run substitute projections until done or stall.

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
        if is_subst_done(state):
            # Report steps consumed to global budget
            budget.consume(i)
            return state, i, False

        # Resolve any lookup markers before taking a step
        state = resolve_lookups(state, bindings)

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

    # Run projections
    final_state, steps, is_stall = run_subst_projections(
        projections, initial, linked_bindings
    )

    # Extract result
    if is_stall:
        # Check if we stalled on a lookup (unbound variable)
        if is_subst_state(final_state):
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
