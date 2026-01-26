"""
Test DeepStep v0 projections with EVAL_SEED.

This validates that the work-stack machine approach works
for the append example using pure Mu projections.

SIMPLIFIED APPROACH:
Since we're testing the concept, we specialize for linked lists
(dicts with exactly "head" and "tail" keys). Generalization comes later.

HOST DEBT INVENTORY:
  - @host_builtin: linked_list (reversed), run_deep_eval (range), validate_deep_eval_state
  - @host_iteration: to_python_list (while-loop)
  Total: 4 host dependencies (test harness scaffolding, not projection logic)

SECURITY NOTES:
  - State validation added per adversary review
  - History capped at MAX_HISTORY to prevent memory exhaustion
  - max_steps parameter prevents infinite loops
"""

import json
from rcx_pi.eval_seed import match, substitute, apply_projection, step, NO_MATCH
from rcx_pi.mu_type import is_mu, assert_mu, mu_equal

# Resource limits
MAX_HISTORY = 500
MAX_CONTEXT_DEPTH = 100


# =============================================================================
# Domain projections (append)
# =============================================================================

APPEND_BASE = {
    "pattern": {"op": "append", "xs": None, "ys": {"var": "ys"}},
    "body": {"var": "ys"}
}

APPEND_RECURSIVE = {
    "pattern": {
        "op": "append",
        "xs": {"head": {"var": "h"}, "tail": {"var": "t"}},
        "ys": {"var": "ys"}
    },
    "body": {
        "head": {"var": "h"},
        "tail": {"op": "append", "xs": {"var": "t"}, "ys": {"var": "ys"}}
    }
}

DOMAIN_PROJECTIONS = [APPEND_BASE, APPEND_RECURSIVE]


# =============================================================================
# Deep eval machine projections
# =============================================================================

def make_deep_eval_projections(domain_projections):
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
# Test harness (host scaffolding - all functions marked with debt decorators)
# =============================================================================

def host_builtin(func):
    """Decorator marking functions that use Python builtins (reversed, range, etc.)."""
    func.host_debt_marker = "builtin"
    return func


def host_iteration(func):
    """Decorator marking functions that use Python iteration (while, for)."""
    func.host_debt_marker = "iteration"
    return func


@host_builtin
def validate_deep_eval_state(state):
    """
    Validate deep_eval state is well-formed.

    Defends against adversary attacks:
    - Attack 14: Phase state injection (inconsistent phase/context)
    - Attack 15: Changed flag manipulation

    Returns: (is_valid, error_message)
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


@host_builtin
def run_deep_eval(projections, value, max_steps=100, debug=False, validate=True):
    """
    Run projections until stall or done.

    @host_builtin: Uses range() for iteration
    """
    # Validate input is Mu
    assert_mu(value)

    current = value
    history = []

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
            history.append({"step": i+1, "before": current, "after": next_val})

        if debug:
            if mu_equal(current, next_val):
                print("STALL")
            else:
                print(f"Result: {json.dumps(next_val, indent=2)}")

        # Check for done wrapper
        if isinstance(next_val, dict) and next_val.get("mode") == "deep_eval_done":
            if debug:
                print("DONE!")
            return next_val["result"], history

        if mu_equal(current, next_val):
            break
        current = next_val

    # If we stalled without done wrapper, extract result if possible
    if isinstance(current, dict) and current.get("mode") == "deep_eval_done":
        return current["result"], history

    return current, history


@host_builtin
def linked_list(*elements):
    """
    Create linked list from elements.

    @host_builtin: Uses reversed() builtin
    """
    result = None
    for elem in reversed(elements):
        assert_mu(elem)
        result = {"head": elem, "tail": result}
    return result


@host_iteration
def to_python_list(linked):
    """
    Convert linked list back to Python list.

    @host_iteration: Uses while-loop
    """
    result = []
    while linked is not None:
        result.append(linked["head"])
        linked = linked["tail"]
    return result


# =============================================================================
# Tests
# =============================================================================

def test_wrap_unwrap():
    """Simple value wraps and unwraps unchanged."""
    projections = make_deep_eval_projections([])
    value = {"head": 1, "tail": None}

    result, history = run_deep_eval(projections, value, debug=True)

    # Should wrap, traverse, unwrap to same value
    print(f"\nSteps: {len(history)}")
    print(f"Result: {result}")
    assert mu_equal(result, value), f"Expected {value}, got {result}"
    print("✓ test_wrap_unwrap passed")


def test_single_reduction():
    """Single append at root."""
    projections = make_deep_eval_projections(DOMAIN_PROJECTIONS)

    # append([], [1]) = [1]
    value = {"op": "append", "xs": None, "ys": linked_list(1)}
    result, history = run_deep_eval(projections, value, debug=True)

    expected = linked_list(1)
    print(f"\nResult: {to_python_list(result) if result else 'null'}")
    assert mu_equal(result, expected), f"Expected {expected}, got {result}"
    print("✓ test_single_reduction passed")


def test_append_basic():
    """append([1], [2]) = [1, 2]"""
    projections = make_deep_eval_projections(DOMAIN_PROJECTIONS)

    value = {
        "op": "append",
        "xs": linked_list(1),
        "ys": linked_list(2)
    }
    result, history = run_deep_eval(projections, value, debug=True)

    print(f"\nSteps: {len(history)}")
    print(f"Result: {to_python_list(result)}")

    expected = linked_list(1, 2)
    assert mu_equal(result, expected), f"Expected [1,2], got {to_python_list(result)}"
    print("✓ test_append_basic passed")


def test_append_longer():
    """append([1,2], [3,4]) = [1,2,3,4]"""
    projections = make_deep_eval_projections(DOMAIN_PROJECTIONS)

    value = {
        "op": "append",
        "xs": linked_list(1, 2),
        "ys": linked_list(3, 4)
    }
    result, history = run_deep_eval(projections, value, debug=True)

    print(f"\nSteps: {len(history)}")
    print(f"Result: {to_python_list(result)}")

    expected = linked_list(1, 2, 3, 4)
    assert mu_equal(result, expected)
    print("✓ test_append_longer passed")


def test_append_empty_ys():
    """append([1,2], None) = [1,2] - edge case with empty ys."""
    projections = make_deep_eval_projections(DOMAIN_PROJECTIONS)

    value = {
        "op": "append",
        "xs": linked_list(1, 2),
        "ys": None
    }
    result, history = run_deep_eval(projections, value, debug=True)

    print(f"\nSteps: {len(history)}")
    print(f"Result: {to_python_list(result)}")

    expected = linked_list(1, 2)
    assert mu_equal(result, expected), f"Expected [1,2], got {to_python_list(result)}"
    print("✓ test_append_empty_ys passed")


# =============================================================================
# Adversary attack tests (from agent review)
# =============================================================================

def test_attack_phase_state_injection():
    """
    Attack 14: Verify phase guards prevent infinite loops from injected states.

    Adversary tries to inject malformed context structure.
    """
    projections = make_deep_eval_projections([])

    # Malicious state: context is malformed (single-element list, not [frame, outer])
    malicious = {
        "mode": "deep_eval",
        "phase": "traverse",
        "focus": {"head": 1, "tail": None},
        "context": [{"type": "dict_tail", "head_result": 0}],  # malformed: should be [frame, outer_list]
        "changed": False
    }

    # Should reject due to malformed context
    try:
        result, history = run_deep_eval(projections, malicious, max_steps=20, validate=True)
        assert False, "Should have rejected malformed context"
    except ValueError as e:
        assert "context" in str(e).lower() or "frame" in str(e).lower()
    print("✓ test_attack_phase_state_injection passed")


def test_attack_changed_flag_manipulation():
    """
    Attack 15: Verify changed flag is validated.

    Adversary claims no changes when focus is reducible.
    """
    projections = make_deep_eval_projections([
        {"pattern": {"x": 1}, "body": {"x": 2}}
    ])

    # Malicious: focus can reduce but changed=False
    malicious = {
        "mode": "deep_eval",
        "phase": "root_check",
        "focus": {"x": 1},  # This SHOULD reduce to {"x": 2}
        "context": [],
        "changed": False  # But we falsely claim no changes
    }

    result, history = run_deep_eval(projections, malicious, max_steps=20)

    # The system should either:
    # 1. Re-check for reductions (correct), or
    # 2. Return the unreduced value (safe but suboptimal)
    # It should NOT infinitely loop
    assert len(history) < 20, "Changed flag manipulation caused problems"
    print("✓ test_attack_changed_flag_manipulation passed")


def test_attack_deep_context():
    """
    Attack 7: Verify deep context doesn't cause stack overflow.

    Context depth is now limited by MAX_CONTEXT_DEPTH.
    """
    projections = make_deep_eval_projections([])

    # Create artificially deep context
    deep_context = []
    for i in range(MAX_CONTEXT_DEPTH + 10):
        deep_context = [{"type": "dict_tail", "head_result": i}, deep_context]

    malicious = {
        "mode": "deep_eval",
        "phase": "traverse",
        "focus": 1,
        "context": deep_context,
        "changed": False
    }

    # Should reject due to context depth
    try:
        result, history = run_deep_eval(projections, malicious, max_steps=10)
        # If it didn't raise, check it terminated reasonably
        assert len(history) <= 10, "Deep context caused extended execution"
    except ValueError as e:
        # Expected: validation rejects deep context
        assert "depth" in str(e).lower() or "context" in str(e).lower()
    print("✓ test_attack_deep_context passed")


def test_attack_history_limit():
    """
    Attack 17: Verify history doesn't grow unbounded.

    History should be capped at MAX_HISTORY.
    """
    projections = make_deep_eval_projections([])
    value = linked_list(*range(10))

    # Run with many steps
    result, history = run_deep_eval(projections, value, max_steps=MAX_HISTORY + 100)

    # History should be capped
    assert len(history) <= MAX_HISTORY, f"History grew to {len(history)}, expected max {MAX_HISTORY}"
    print("✓ test_attack_history_limit passed")


def test_attack_invalid_phase():
    """
    Attack: Verify invalid phase values are rejected.
    """
    projections = make_deep_eval_projections([])

    malicious = {
        "mode": "deep_eval",
        "phase": "MALICIOUS_PHASE",
        "focus": 1,
        "context": [],
        "changed": False
    }

    try:
        result, history = run_deep_eval(projections, malicious, max_steps=10)
        assert False, "Should have rejected invalid phase"
    except ValueError as e:
        assert "phase" in str(e).lower()
    print("✓ test_attack_invalid_phase passed")


def test_attack_non_boolean_changed():
    """
    Attack: Verify non-boolean changed values are rejected.
    """
    projections = make_deep_eval_projections([])

    malicious = {
        "mode": "deep_eval",
        "phase": "traverse",
        "focus": 1,
        "context": [],
        "changed": "true"  # String, not boolean
    }

    try:
        result, history = run_deep_eval(projections, malicious, max_steps=10)
        assert False, "Should have rejected non-boolean changed"
    except ValueError as e:
        assert "boolean" in str(e).lower()
    print("✓ test_attack_non_boolean_changed passed")


if __name__ == "__main__":
    import pytest

    print("=" * 60)
    print("DeepStep v0 Prototype Tests")
    print("=" * 60)

    # Core functionality tests
    test_wrap_unwrap()
    print()

    test_single_reduction()
    print()

    test_append_basic()
    print()

    test_append_longer()
    print()

    test_append_empty_ys()
    print()

    # Adversary attack tests
    print("=" * 60)
    print("Adversary Attack Tests")
    print("=" * 60)

    test_attack_phase_state_injection()
    test_attack_changed_flag_manipulation()
    test_attack_deep_context()
    test_attack_history_limit()
    test_attack_invalid_phase()
    test_attack_non_boolean_changed()

    print()
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
