"""
Classify as Mu Projections - Phase 6b Self-Hosting

This module implements linked list classification using Mu projections.
It determines whether a head/tail linked list encodes a dict (all elements
are kv-pairs) or a list (general elements).

See docs/core/SelfHosting.v0.md for design.

Pre-condition: Dict keys are strings (JSON constraint). The classification
patterns check structural shape but cannot verify Python types.
"""

from __future__ import annotations

from typing import Literal

from .mu_type import Mu, mu_equal
from .eval_seed import step
from .kernel import get_step_budget
from .seed_integrity import load_verified_seed, get_seeds_dir


# =============================================================================
# Projection Loading
# =============================================================================

_CLASSIFY_PROJECTIONS: list[Mu] | None = None


def load_classify_projections() -> list[Mu]:
    """Load classify projections from seeds/classify.v1.json with integrity verification."""
    global _CLASSIFY_PROJECTIONS
    if _CLASSIFY_PROJECTIONS is not None:
        return _CLASSIFY_PROJECTIONS

    seed_path = get_seeds_dir() / "classify.v1.json"
    seed = load_verified_seed(seed_path)

    _CLASSIFY_PROJECTIONS = seed["projections"]
    return _CLASSIFY_PROJECTIONS


def clear_projection_cache() -> None:
    """Clear cached projections (for testing)."""
    global _CLASSIFY_PROJECTIONS
    _CLASSIFY_PROJECTIONS = None


# =============================================================================
# Classify Runner
# =============================================================================


def is_classify_done(state: Mu) -> bool:
    """Check if state is a completed classification result."""
    return (
        isinstance(state, dict)
        and state.get("mode") == "classify_done"
    )


def is_classify_state(state: Mu) -> bool:
    """Check if state is an in-progress classify state."""
    return (
        isinstance(state, dict)
        and state.get("mode") == "classify"
    )


def run_classify_projections(
    projections: list[Mu],
    initial_state: Mu,
    max_steps: int = 1000
) -> tuple[Mu, int, bool]:
    """
    Run classify projections until done or stall.

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
        if is_classify_done(state):
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


def classify_linked_list(value: Mu) -> Literal["dict", "list"]:
    """
    Classify a head/tail linked list as dict-encoding or list-encoding.

    For type-tagged structures (Phase 6c), simply returns the _type value.
    For legacy structures without _type, uses projection-based classification.

    Args:
        value: A head/tail linked list (or null for empty), optionally type-tagged.

    Returns:
        "dict" if type-tagged as dict or all elements are kv-pairs with string keys.
        "list" otherwise (including empty list, primitives, circular).
    """
    # Non-dict structures are not dict-encoded
    if not isinstance(value, dict):
        return "list"

    keys = set(value.keys())

    # Phase 6c: Type-tagged structures - use the _type directly
    if keys == {"_type", "head", "tail"}:
        _type = value.get("_type")
        # Security: Only accept string type tags from the whitelist
        # Non-string or unknown types are treated as invalid (return "list")
        if not isinstance(_type, str):
            return "list"
        if _type == "dict":
            return "dict"
        elif _type == "list":
            return "list"
        # Unknown string type - invalid, treat as list
        return "list"

    # Legacy: head/tail without type tag - use projection-based classification
    if keys != {"head", "tail"}:
        return "list"

    # Walk the list to check:
    # 1. No circular references (projections can't handle these)
    # 2. All kv-pair keys are strings (projections can't verify Python types)
    visited: set[int] = set()
    current = value
    while current is not None:
        if not isinstance(current, dict):
            break
        node_id = id(current)
        if node_id in visited:
            # Circular structure - not a valid dict encoding
            return "list"
        visited.add(node_id)
        if set(current.keys()) != {"head", "tail"}:
            break

        # Check if this element is a valid kv-pair with string key
        # This is the type check that projections cannot do
        #
        # KNOWN LIMITATION: A list like [[s, x]] normalizes identically to {s: x}
        # We cannot distinguish them after normalization. We favor dict interpretation
        # because dicts with None values are more common than lists of 2-element sublists.
        # See docs/core/DebtCategories.v0.md for documentation of this design decision.
        head = current.get("head")
        if isinstance(head, dict):
            # Could be a kv-pair: {"head": key, "tail": {"head": val, "tail": null}}
            if set(head.keys()) == {"head", "tail"}:
                key = head.get("head")
                if not isinstance(key, str):
                    # Key is not a string - not a valid dict encoding
                    return "list"
        # If head is not a dict, the projections will catch it as not-kv

        current = current.get("tail")

    # Load projections for structural validation
    projections = load_classify_projections()

    # Wrap input in classify request format
    initial = {"classify": {"list": value}}

    # Run projections
    final_state, steps, is_stall = run_classify_projections(projections, initial)

    # Extract result
    if is_stall:
        # Stall means no projection matched = treat as list
        return "list"

    if is_classify_done(final_state):
        result_type = final_state.get("type")
        if result_type == "dict":
            return "dict"

    return "list"
