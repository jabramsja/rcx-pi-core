"""
Test DeepStep v0 projections with EVAL_SEED.

This validates that the work-stack machine approach works
for the append example using pure Mu projections.

SIMPLIFIED APPROACH:
Since we're testing the concept, we specialize for linked lists
(dicts with exactly "head" and "tail" keys). Generalization comes later.
"""

import json
from rcx_pi.eval_seed import match, substitute, apply_projection, step, NO_MATCH
from rcx_pi.mu_type import is_mu, mu_equal


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
# Test harness
# =============================================================================

def run_deep_eval(projections, value, max_steps=100, debug=False):
    """Run projections until stall or done."""
    current = value
    history = []

    for i in range(max_steps):
        if debug:
            print(f"\n=== Step {i+1} ===")
            print(f"Current: {json.dumps(current, indent=2)}")

        next_val = step(projections, current)
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


def linked_list(*elements):
    """Create linked list from elements."""
    result = None
    for elem in reversed(elements):
        result = {"head": elem, "tail": result}
    return result


def to_python_list(linked):
    """Convert linked list back to Python list."""
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


if __name__ == "__main__":
    print("=" * 60)
    print("DeepStep v0 Prototype Tests")
    print("=" * 60)

    test_wrap_unwrap()
    print()

    test_single_reduction()
    print()

    test_append_basic()
    print()

    test_append_longer()
    print()

    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
