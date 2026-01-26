"""
Match as Mu Projections - Phase 4a Self-Hosting

This module implements pattern matching using Mu projections instead of
Python recursion. It achieves parity with eval_seed.match() but uses
the kernel loop for iteration.

See docs/core/SelfHosting.v0.md for design.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rcx_pi.mu_type import Mu, assert_mu, mu_equal
from rcx_pi.eval_seed import NO_MATCH, _NoMatch, step


# =============================================================================
# Projection Loading
# =============================================================================

_MATCH_PROJECTIONS: list[Mu] | None = None


def load_match_projections() -> list[Mu]:
    """Load match projections from seeds/match.v1.json."""
    global _MATCH_PROJECTIONS
    if _MATCH_PROJECTIONS is not None:
        return _MATCH_PROJECTIONS

    seed_path = Path(__file__).parent.parent / "seeds" / "match.v1.json"
    with open(seed_path) as f:
        seed = json.load(f)

    _MATCH_PROJECTIONS = seed["projections"]
    return _MATCH_PROJECTIONS


def clear_projection_cache() -> None:
    """Clear cached projections (for testing)."""
    global _MATCH_PROJECTIONS
    _MATCH_PROJECTIONS = None


# =============================================================================
# Dict Normalization
# =============================================================================


def normalize_for_match(value: Mu) -> Mu:
    """
    Normalize a Mu value for structural matching.

    Converts dicts and lists to head/tail linked lists so they can be
    matched structurally via head/tail patterns.

    Dict: {"a": 1, "b": 2} -> linked list of [key, value] pairs
    List: [1, 2, 3] -> {"head": 1, "tail": {"head": 2, "tail": {...}}}
    KV-pair: ["a", 1] -> {"head": "a", "tail": {"head": 1, "tail": null}}
    """
    if value is None:
        return None

    if isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, list):
        # Convert Python list to linked list
        result: Mu = None
        for elem in reversed(value):
            result = {"head": normalize_for_match(elem), "tail": result}
        return result

    if isinstance(value, dict):
        # Check if already normalized (has head/tail structure only)
        if set(value.keys()) == {"head", "tail"}:
            return {
                "head": normalize_for_match(value["head"]),
                "tail": normalize_for_match(value["tail"])
            }

        # Check for variable site - don't normalize
        if set(value.keys()) == {"var"} and isinstance(value.get("var"), str):
            return value

        # Convert dict to sorted key-value linked list
        # Each kv-pair becomes {"head": key, "tail": {"head": value, "tail": null}}
        result: Mu = None
        for key in sorted(value.keys(), reverse=True):
            # Key-value pair as linked list: [key, value]
            kv_pair: Mu = {
                "head": key,
                "tail": {"head": normalize_for_match(value[key]), "tail": None}
            }
            result = {"head": kv_pair, "tail": result}
        return result

    return value


def is_kv_pair_linked(value: Mu) -> bool:
    """
    Check if value is a key-value pair in linked list format.

    KV-pair format: {"head": key_string, "tail": {"head": value, "tail": null}}
    """
    if not isinstance(value, dict):
        return False
    if set(value.keys()) != {"head", "tail"}:
        return False
    head = value.get("head")
    tail = value.get("tail")
    if not isinstance(head, str):
        return False
    if not isinstance(tail, dict):
        return False
    if set(tail.keys()) != {"head", "tail"}:
        return False
    if tail.get("tail") is not None:
        return False
    return True


def denormalize_from_match(value: Mu) -> Mu:
    """
    Convert normalized Mu back to regular Python structures.

    Reverses the normalization done by normalize_for_match.
    """
    if value is None:
        return None

    if isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, list):
        return [denormalize_from_match(elem) for elem in value]  # AST_OK: bootstrap - denormalization

    if isinstance(value, dict):
        # Check if it's a linked list (head/tail structure)
        if set(value.keys()) == {"head", "tail"}:
            head = value["head"]

            # Check if head is a key-value pair (dict encoding)
            if is_kv_pair_linked(head):
                # It's a dict encoded as linked list of kv-pairs
                result = {}
                current = value
                while current is not None:
                    kv = current["head"]
                    key = kv["head"]
                    val = kv["tail"]["head"]
                    result[key] = denormalize_from_match(val)
                    current = current["tail"]
                return result
            else:
                # It's a regular linked list (Python list encoding)
                result = []
                current = value
                while current is not None:
                    result.append(denormalize_from_match(current["head"]))
                    current = current["tail"]
                return result

        # Variable site - return as-is
        if set(value.keys()) == {"var"}:
            return value

        # Regular dict (shouldn't happen after normalization)
        return {k: denormalize_from_match(v) for k, v in value.items()}  # AST_OK: bootstrap

    return value


# =============================================================================
# Bindings Conversion
# =============================================================================


def bindings_to_dict(linked: Mu) -> dict[str, Mu]:
    """
    Convert linked list bindings to Python dict.

    Linked format: {"name": "x", "value": 42, "rest": {...}} or null
    Dict format: {"x": 42, ...}
    """
    result: dict[str, Mu] = {}
    current = linked
    while current is not None:
        if not isinstance(current, dict):
            raise ValueError(f"Invalid bindings structure: {current}")
        name = current.get("name")
        value = current.get("value")
        if name is None:
            raise ValueError(f"Binding missing 'name': {current}")
        result[name] = value
        current = current.get("rest")
    return result


def dict_to_bindings(d: dict[str, Mu]) -> Mu:
    """
    Convert Python dict to linked list bindings.

    Dict format: {"x": 42, ...}
    Linked format: {"name": "x", "value": 42, "rest": {...}} or null
    """
    result: Mu = None
    # Use sorted keys for determinism
    for name in sorted(d.keys(), reverse=True):
        result = {"name": name, "value": d[name], "rest": result}
    return result


# =============================================================================
# Match Runner
# =============================================================================


def is_match_done(state: Mu) -> bool:
    """Check if state is a completed match result."""
    return (
        isinstance(state, dict)
        and state.get("mode") == "match_done"
    )


def is_match_state(state: Mu) -> bool:
    """Check if state is an in-progress match state."""
    return (
        isinstance(state, dict)
        and state.get("mode") == "match"
    )


def run_match_projections(
    projections: list[Mu],
    initial_state: Mu,
    max_steps: int = 1000
) -> tuple[Mu, int, bool]:
    """
    Run match projections until done or stall.

    Returns:
        (final_state, steps_taken, is_stall)
    """
    state = initial_state
    for i in range(max_steps):
        # Check if done
        if is_match_done(state):
            return state, i, False

        # Take a step
        next_state = step(projections, state)

        # Check for stall (no change) - use mu_equal to avoid Python type coercion
        if mu_equal(next_state, state):
            return state, i, True

        state = next_state

    # Max steps exceeded - treat as stall
    return state, max_steps, True


def match_mu(pattern: Mu, value: Mu) -> dict[str, Mu] | _NoMatch:
    """
    Match pattern against value using Mu projections.

    This is the parity function for eval_seed.match().

    Args:
        pattern: The pattern to match (Mu with possible var sites).
        value: The value to match against (Mu).

    Returns:
        Dict of bindings {"var_name": value} if match, NO_MATCH otherwise.
    """
    assert_mu(pattern, "match_mu.pattern")
    assert_mu(value, "match_mu.value")

    # Normalize inputs to head/tail structures
    norm_pattern = normalize_for_match(pattern)
    norm_value = normalize_for_match(value)

    # Load projections
    projections = load_match_projections()

    # Wrap input in match request format
    initial = {"match": {"pattern": norm_pattern, "value": norm_value}}

    # Run projections
    final_state, steps, is_stall = run_match_projections(projections, initial)

    # Extract result
    if is_stall:
        # Stall means no projection matched = pattern didn't match
        return NO_MATCH

    if is_match_done(final_state):
        status = final_state.get("status")
        if status == "success":
            bindings = final_state.get("bindings")
            raw_dict = bindings_to_dict(bindings)
            # Denormalize the bound values back to regular Python structures
            return {k: denormalize_from_match(v) for k, v in raw_dict.items()}  # AST_OK: bootstrap
        else:
            # Explicit failure status
            return NO_MATCH

    # Unexpected state
    return NO_MATCH
