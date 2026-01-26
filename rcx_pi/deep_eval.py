"""
Deep Evaluation for RCX (Work-Stack Machine)

This module implements deep evaluation using a work-stack machine approach.
Unlike step() which only matches at the root level, deep_eval traverses
the entire tree to find and reduce nested expressions.

The key insight is that tree traversal is expressed as explicit Mu state
(focus + context stack + phase), with no host recursion - the kernel loop
provides the iteration.

See docs/execution/DeepStep.v0.md for the design.

HOST DEBT INVENTORY:
  - @host_builtin: run_deep_eval (range for iteration loop)
  - @host_builtin: validate_deep_eval_state (isinstance, set operations)
  Total: 2 host dependencies (runner scaffolding, not projection logic)

The projections themselves are pure structural - no host debt.
"""

from __future__ import annotations

from typing import Any

from rcx_pi.eval_seed import step, NO_MATCH, host_builtin, host_mutation
from rcx_pi.mu_type import Mu, assert_mu, mu_equal


# =============================================================================
# Resource Limits (defense against adversary attacks)
# =============================================================================

MAX_HISTORY = 500        # Cap history to prevent memory exhaustion (Attack 17)
MAX_CONTEXT_DEPTH = 100  # Cap context depth to prevent stack-like overflow (Attack 7)

# Internal marker for done wrapper - prevents spoofing by domain projections
# This value is checked by the runner to verify authentic completion
DONE_MARKER = "__deep_eval_internal_done__"


# =============================================================================
# Deep Eval State Machine Projections
# =============================================================================

def make_deep_eval_projections(domain_projections: list[Mu]) -> list[Mu]:
    """
    Create the full projection list for deep_eval.

    Uses phase state to prevent infinite loops:
    - phase="traverse": actively traversing tree, DESCEND can fire
    - phase="ascending": going up the tree, DESCEND blocked
    - phase="root_check": at root, deciding restart vs unwrap

    Returns projections in correct order:
    1. Root check (restart or unwrap)
    2. Reduce (wrapped domain projections)
    3. Descend (phase=traverse only - prevents re-descent after ascend)
    4. Sibling (any phase, sets phase=traverse for new subtree)
    5. Ascend (any phase, sets phase=ascending to block re-descent)
    6. Wrap (entry point, last)

    Args:
        domain_projections: List of domain-specific projections (e.g., append).

    Returns:
        Complete projection list for deep evaluation.
    """
    projections = []

    # 1. ROOT_CHECK with changes -> RESTART
    projections.append({
        "id": "restart",
        "pattern": {
            "mode": "deep_eval",
            "phase": "root_check",
            "focus": {"var": "f"},
            "context": [],
            "changed": True
        },
        "body": {
            "mode": "deep_eval",
            "phase": "traverse",
            "focus": {"var": "f"},
            "context": [],
            "changed": False
        }
    })

    # 2. ROOT_CHECK without changes -> UNWRAP (done!)
    # Return a "done" wrapper that no projection matches (causes stall)
    # SECURITY: Include internal marker to prevent spoofing by domain projections
    projections.append({
        "id": "unwrap",
        "pattern": {
            "mode": "deep_eval",
            "phase": "root_check",
            "focus": {"var": "result"},
            "context": [],
            "changed": False
        },
        "body": {
            "mode": "deep_eval_done",
            "_marker": DONE_MARKER,  # Internal marker - runner checks this
            "result": {"var": "result"}
        }
    })

    # 3. REDUCE: Wrap each domain projection (only in traverse phase)
    for dp in domain_projections:
        projections.append({
            "id": f"reduce.{dp.get('id', 'domain')}",
            "pattern": {
                "mode": "deep_eval",
                "phase": "traverse",
                "focus": dp["pattern"],
                "context": {"var": "ctx"},
                "changed": {"var": "_c"}
            },
            "body": {
                "mode": "deep_eval",
                "phase": "traverse",
                "focus": dp["body"],
                "context": {"var": "ctx"},
                "changed": True
            }
        })

    # 4. DESCEND into dict with head/tail
    # CRITICAL: Only matches phase="traverse" - prevents re-descent after ascend
    # Must come BEFORE sibling/ascend so we descend into nested dicts
    projections.append({
        "id": "descend.dict",
        "pattern": {
            "mode": "deep_eval",
            "phase": "traverse",
            "focus": {"head": {"var": "h"}, "tail": {"var": "t"}},
            "context": {"var": "ctx"},
            "changed": {"var": "c"}
        },
        "body": {
            "mode": "deep_eval",
            "phase": "traverse",
            "focus": {"var": "h"},
            "context": [
                {
                    "type": "dict_head",
                    "head_val": {"var": "h"},
                    "tail_val": {"var": "t"}
                },
                {"var": "ctx"}
            ],
            "changed": {"var": "c"}
        }
    })

    # 5. SIBLING: After processing head, move to tail
    # Matches any phase (traverse or ascending), sets phase=traverse
    # This allows DESCEND to fire on the tail value if it's a dict
    projections.append({
        "id": "sibling.to_tail",
        "pattern": {
            "mode": "deep_eval",
            "phase": {"var": "_phase"},  # matches any phase
            "focus": {"var": "head_result"},
            "context": [
                {
                    "type": "dict_head",
                    "head_val": {"var": "_h"},
                    "tail_val": {"var": "t"}
                },
                {"var": "outer"}
            ],
            "changed": {"var": "c"}
        },
        "body": {
            "mode": "deep_eval",
            "phase": "traverse",  # reset to traverse for new subtree
            "focus": {"var": "t"},
            "context": [
                {
                    "type": "dict_tail",
                    "head_result": {"var": "head_result"}
                },
                {"var": "outer"}
            ],
            "changed": {"var": "c"}
        }
    })

    # 6. ASCEND to non-empty outer context
    # Matches any phase, sets phase=ascending to prevent re-descent
    projections.append({
        "id": "ascend.to_context",
        "pattern": {
            "mode": "deep_eval",
            "phase": {"var": "_phase"},  # matches any phase
            "focus": {"var": "tail_result"},
            "context": [
                {
                    "type": "dict_tail",
                    "head_result": {"var": "h_res"}
                },
                [{"var": "first_outer"}, {"var": "rest_outer"}]
            ],
            "changed": {"var": "c"}
        },
        "body": {
            "mode": "deep_eval",
            "phase": "ascending",  # block re-descent into rebuilt dict
            "focus": {"head": {"var": "h_res"}, "tail": {"var": "tail_result"}},
            "context": [{"var": "first_outer"}, {"var": "rest_outer"}],
            "changed": {"var": "c"}
        }
    })

    # 7. ASCEND to root (empty outer context) -> set phase to root_check
    projections.append({
        "id": "ascend.to_root",
        "pattern": {
            "mode": "deep_eval",
            "phase": {"var": "_phase"},  # matches any phase
            "focus": {"var": "tail_result"},
            "context": [
                {
                    "type": "dict_tail",
                    "head_result": {"var": "h_res"}
                },
                []
            ],
            "changed": {"var": "c"}
        },
        "body": {
            "mode": "deep_eval",
            "phase": "root_check",
            "focus": {"head": {"var": "h_res"}, "tail": {"var": "tail_result"}},
            "context": [],
            "changed": {"var": "c"}
        }
    })

    # 8. WRAP: Entry point (must be last)
    projections.append({
        "id": "wrap",
        "pattern": {"var": "input"},
        "body": {
            "mode": "deep_eval",
            "phase": "traverse",
            "focus": {"var": "input"},
            "context": [],
            "changed": False
        }
    })

    return projections


# =============================================================================
# State Validation (defense against adversary attacks)
# =============================================================================

@host_builtin("isinstance, set operations for type checking")
def validate_deep_eval_state(state: Mu) -> tuple[bool, str | None]:
    """
    Validate deep_eval state is well-formed.

    Defends against adversary attacks:
    - Attack 14: Phase state injection (inconsistent phase/context)
    - Attack 15: Changed flag manipulation
    - Attack 7: Deep context overflow

    Args:
        state: The state to validate.

    Returns:
        (is_valid, error_message) tuple.
        If valid, error_message is None.
    """
    if not isinstance(state, dict):
        return True, None  # Not a deep_eval state, pass through

    if state.get("mode") != "deep_eval":
        return True, None  # Not a deep_eval state

    # Validate required fields
    required = {"mode", "phase", "focus", "context", "changed"}
    if not required.issubset(state.keys()):
        return False, f"Missing required fields: {required - set(state.keys())}"

    # Validate phase values
    valid_phases = {"traverse", "ascending", "root_check"}
    if state["phase"] not in valid_phases:
        return False, f"Invalid phase: {state['phase']}"

    # Validate changed is boolean
    if not isinstance(state["changed"], bool):
        return False, f"changed must be boolean, got: {type(state['changed'])}"

    # Validate context is a list
    if not isinstance(state["context"], list):
        return False, f"context must be list, got: {type(state['context'])}"

    # Validate context structure - must be properly nested [frame, outer_context]
    # Empty context is valid; non-empty must be [frame_dict, list]
    ctx = state["context"]
    depth = 0
    while ctx:
        if not isinstance(ctx, list):
            return False, f"Context at depth {depth} is not a list"
        if len(ctx) == 0:
            break  # Empty context, done
        if len(ctx) != 2:
            return False, f"Context at depth {depth} must be [frame, outer], got length {len(ctx)}"

        frame, outer = ctx
        if not isinstance(frame, dict):
            return False, f"Context frame at depth {depth} is not a dict"
        if "type" not in frame:
            return False, f"Context frame at depth {depth} missing 'type' field"

        valid_frame_types = {"dict_head", "dict_tail"}
        if frame["type"] not in valid_frame_types:
            return False, f"Invalid frame type at depth {depth}: {frame['type']}"

        ctx = outer
        depth += 1

        if depth > MAX_CONTEXT_DEPTH:
            return False, f"Context depth {depth} exceeds max {MAX_CONTEXT_DEPTH}"

    # Validate phase/context consistency
    # root_check phase should only have empty context
    if state["phase"] == "root_check" and state["context"]:
        return False, f"root_check phase requires empty context, got depth {depth}"

    return True, None


# =============================================================================
# Deep Eval Runner
# =============================================================================

@host_builtin("range() for iteration loop")
@host_mutation("history.append() to record steps")
def run_deep_eval(
    projections: list[Mu],
    value: Mu,
    max_steps: int = 100,
    debug: bool = False,
    validate: bool = True
) -> tuple[Mu, list[dict[str, Any]]]:
    """
    Run projections until stall or done, with deep traversal.

    This is the main entry point for deep evaluation. It wraps the input
    in deep_eval state and runs until completion.

    Args:
        projections: Complete projection list from make_deep_eval_projections().
        value: The initial value to evaluate.
        max_steps: Maximum steps before forced termination.
        debug: If True, print each step.
        validate: If True, validate state at each step.

    Returns:
        (result, history) tuple where:
        - result is the final evaluated value
        - history is list of {step, before, after} dicts

    Raises:
        ValueError: If state validation fails (when validate=True).
    """
    import json

    # Validate input is Mu
    assert_mu(value)

    current = value
    history: list[dict[str, Any]] = []

    for i in range(max_steps):
        # Validate state if it's a deep_eval state
        if validate:
            is_valid, error = validate_deep_eval_state(current)
            if not is_valid:
                raise ValueError(f"Invalid deep_eval state at step {i+1}: {error}")

        if debug:
            print(f"\n=== Step {i+1} ===")
            print(f"Current: {json.dumps(current, indent=2)}")

        next_val = step(projections, current)

        # Cap history to prevent memory exhaustion (Attack 17)
        if len(history) < MAX_HISTORY:
            history.append({"step": i + 1, "before": current, "after": next_val})

        if debug:
            if mu_equal(current, next_val):
                print("STALL")
            else:
                print(f"Result: {json.dumps(next_val, indent=2)}")

        # Check for done wrapper with internal marker (prevents spoofing)
        if (isinstance(next_val, dict) and
            next_val.get("mode") == "deep_eval_done" and
            next_val.get("_marker") == DONE_MARKER):
            if debug:
                print("DONE!")
            return next_val["result"], history

        if mu_equal(current, next_val):
            break
        current = next_val

    # If we stalled without done wrapper, extract result if possible
    # Check for internal marker to prevent spoofing
    if (isinstance(current, dict) and
        current.get("mode") == "deep_eval_done" and
        current.get("_marker") == DONE_MARKER):
        return current["result"], history

    return current, history


# =============================================================================
# Convenience Functions
# =============================================================================

def deep_eval(domain_projections: list[Mu], value: Mu, **kwargs) -> Mu:
    """
    Convenience wrapper for deep evaluation.

    Creates deep_eval projections from domain projections and runs evaluation.

    Args:
        domain_projections: List of domain-specific projections.
        value: The value to evaluate.
        **kwargs: Passed to run_deep_eval (max_steps, debug, validate).

    Returns:
        The final evaluated value.
    """
    projections = make_deep_eval_projections(domain_projections)
    result, _ = run_deep_eval(projections, value, **kwargs)
    return result
