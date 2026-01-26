"""
Step as Mu Projections - Phase 5 Self-Hosting

This module implements the step function using Mu projections instead of
Python recursion. It achieves parity with eval_seed.step() using match_mu
and subst_mu.

Phase 5 Goal: EVAL_SEED runs EVAL_SEED
- step_mu() uses match_mu + subst_mu (Mu projections)
- step() uses match + substitute (Python recursion)
- If traces are identical, self-hosting is achieved

See docs/core/SelfHosting.v0.md for design.
"""

from rcx_pi.eval_seed import NO_MATCH
from rcx_pi.match_mu import match_mu
from rcx_pi.subst_mu import subst_mu
from rcx_pi.mu_type import Mu, assert_mu, mu_equal


def apply_mu(projection: Mu, input_value: Mu) -> Mu:
    """
    Apply a projection to a value using Mu-based match and substitute.

    This is apply_projection() implemented with match_mu + subst_mu.
    Achieves parity with eval_seed.apply_projection() for all inputs
    (except known normalization edge cases documented in Phase 4d).

    Args:
        projection: Dict with "pattern" and "body" keys.
        input_value: The value to transform.

    Returns:
        Transformed value if pattern matched, NO_MATCH otherwise.

    Raises:
        TypeError: If projection is not a dict.
        KeyError: If projection missing pattern/body, or unbound variable in body.
    """
    assert_mu(projection, "apply_mu.projection")
    assert_mu(input_value, "apply_mu.input")

    # Validate projection structure (parity with apply_projection error types)
    if not isinstance(projection, dict):
        raise TypeError(f"Projection must be dict, got {type(projection).__name__}")
    if "pattern" not in projection or "body" not in projection:
        raise KeyError("Projection must have 'pattern' and 'body' keys")

    pattern = projection["pattern"]
    body = projection["body"]

    # Use Mu-based match (runs match projections via kernel loop)
    bindings = match_mu(pattern, input_value)
    if bindings is NO_MATCH:
        return NO_MATCH

    # Use Mu-based substitute (runs subst projections via kernel loop)
    return subst_mu(body, bindings)


def step_mu(projections: list[Mu], input_value: Mu) -> Mu:
    """
    Try each projection in order using Mu-based apply.

    This is step() implemented with match_mu + subst_mu.
    Returns first successful application, or input unchanged (stall).

    Args:
        projections: List of projections to try.
        input_value: The value to transform.

    Returns:
        Transformed value if any projection matched, input unchanged otherwise.
    """
    assert_mu(input_value, "step_mu.input")

    for proj in projections:
        result = apply_mu(proj, input_value)
        if result is not NO_MATCH:
            return result

    # No match - return input unchanged (stall)
    return input_value


def run_mu(projections: list[Mu], initial: Mu, max_steps: int = 1000) -> tuple[Mu, list[dict], bool]:
    """
    Run projections repeatedly until stall or max steps.

    This is the kernel loop using step_mu instead of step.

    Args:
        projections: List of projections to apply.
        initial: Starting value.
        max_steps: Maximum iterations before forced stop.

    Returns:
        Tuple of (final_value, trace, is_stall):
        - final_value: The result after all steps
        - trace: List of {"step": n, "value": v} entries
        - is_stall: True if stopped due to stall (no change)
    """
    # HOST ITERATION DEBT: This for-loop is Python iteration.
    # Phase 5 self-hosts operations (match/subst), not the kernel loop.
    # Kernel loop as projections is a Phase 6+ goal.
    trace = []
    current = initial

    for i in range(max_steps):
        trace.append({"step": i, "value": current})

        result = step_mu(projections, current)

        # Check for stall (no change)
        if mu_equal(result, current):
            trace.append({"step": i + 1, "value": result, "stall": True})
            return result, trace, True

        current = result

    # Hit max steps without stall
    trace.append({"step": max_steps, "value": current, "max_steps": True})
    return current, trace, False
