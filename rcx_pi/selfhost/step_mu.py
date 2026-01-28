"""
Step as Mu Projections - Phase 7d Self-Hosting

This module implements the step function using Mu projections instead of
Python recursion. It achieves parity with eval_seed.step() using match_mu
and subst_mu.

Phase 7d: Meta-circular kernel
- step_mu() now uses structural kernel projections (kernel.v1 + match.v2 + subst.v2)
- The Python for-loop is replaced with kernel projections that iterate structurally
- Iteration uses linked-list cursor, not arithmetic

SECURITY: Projection order is security-critical. When combining kernel
projections with domain projections (Phase 7+), kernel projections MUST
run first to prevent domain data from forging kernel state.

See docs/core/SelfHosting.v0.md for design.
See docs/core/MetaCircularKernel.v0.md for kernel design.
"""

from __future__ import annotations

from .eval_seed import NO_MATCH, host_iteration, step as eval_step
from .match_mu import match_mu, normalize_for_match, denormalize_from_match
from .subst_mu import subst_mu
from .mu_type import Mu, assert_mu, mu_equal
from .seed_integrity import get_seeds_dir, load_verified_seed


# =============================================================================
# Projection Order Security (Phase 7+)
# =============================================================================

def is_kernel_projection(projection: Mu) -> bool:
    """
    Check if a projection is a kernel projection (matches _mode prefix).

    Kernel projections have patterns that match on _mode field, which is
    the kernel namespace. Domain projections should not use _mode patterns.

    Args:
        projection: A projection dict with pattern and body.

    Returns:
        True if projection ID starts with "kernel." or pattern has _mode key.
    """
    if not isinstance(projection, dict):
        return False

    # Check by ID (fast path)
    proj_id = projection.get("id", "")
    if isinstance(proj_id, str) and proj_id.startswith("kernel."):
        return True

    # Check by pattern structure (fallback)
    pattern = projection.get("pattern", {})
    if isinstance(pattern, dict) and "_mode" in pattern:
        return True

    return False


def validate_kernel_projections_first(projections: list[Mu]) -> None:
    """
    Validate that kernel projections appear before domain projections.

    SECURITY: This is critical for Phase 7+ when kernel and domain projections
    are combined. If domain projections run first, they could forge kernel state
    by matching patterns like {"_step": ..., "_projs": ...} before kernel.wrap.

    Args:
        projections: List of projections to validate.

    Raises:
        ValueError: If domain projection appears before kernel projection.
    """
    seen_domain = False
    first_domain_id = None

    for proj in projections:
        is_kernel = is_kernel_projection(proj)

        if is_kernel and seen_domain:
            proj_id = proj.get("id", "<unknown>") if isinstance(proj, dict) else "<invalid>"
            raise ValueError(
                f"SECURITY: Kernel projection '{proj_id}' appears after domain projection "
                f"'{first_domain_id}'. Kernel projections MUST be first to prevent "
                f"domain data from forging kernel state."
            )

        if not is_kernel and not seen_domain:
            seen_domain = True
            first_domain_id = proj.get("id", "<unknown>") if isinstance(proj, dict) else "<invalid>"


# =============================================================================
# Structural Kernel Helpers (Phase 7d)
# =============================================================================

# Module-level cache for combined kernel projections
_combined_kernel_cache: list[Mu] | None = None


def list_to_linked(items: list[Mu]) -> Mu:
    """
    Convert Python list to Mu linked-list format.

    [a, b, c] -> {head: a, tail: {head: b, tail: {head: c, tail: null}}}
    [] -> null

    Required for structural kernel iteration (no arithmetic in pure Mu).
    Uses iterative construction for performance.

    Args:
        items: Python list of Mu values.

    Returns:
        Mu linked-list (dict with head/tail) or None for empty list.
    """
    if not items:
        return None
    result: Mu = None
    for item in reversed(items):
        result = {"head": item, "tail": result}
    return result


def normalize_projection(proj: dict) -> dict:
    """
    Normalize a projection's pattern and body for kernel use.

    Both pattern and body are converted to head/tail format so they can
    be structurally matched and substituted by the Mu projections.

    Args:
        proj: Projection dict with "pattern" and "body" keys.

    Returns:
        Dict with normalized pattern and body.
    """
    return {
        "pattern": normalize_for_match(proj["pattern"]),
        "body": normalize_for_match(proj["body"])
    }


def load_combined_kernel_projections() -> list[Mu]:
    """
    Load and cache combined kernel + match.v2 + subst.v2 projections.

    SECURITY: Kernel projections MUST come first to prevent domain
    projections from forging kernel state.

    Returns:
        Combined list of kernel, match, and subst projections.
    """
    global _combined_kernel_cache
    if _combined_kernel_cache is not None:
        return _combined_kernel_cache

    seeds_dir = get_seeds_dir()
    kernel_seed = load_verified_seed(seeds_dir / "kernel.v1.json")
    match_seed = load_verified_seed(seeds_dir / "match.v2.json")
    subst_seed = load_verified_seed(seeds_dir / "subst.v2.json")

    # SECURITY: Kernel projections MUST be first
    _combined_kernel_cache = (
        kernel_seed["projections"] +
        match_seed["projections"] +
        subst_seed["projections"]
    )
    return _combined_kernel_cache


def clear_combined_kernel_cache() -> None:
    """Clear cached kernel projections (for testing)."""
    global _combined_kernel_cache
    _combined_kernel_cache = None


@host_iteration("Kernel execution loop - Phase 8 replaces with recursive kernel projections")
def step_kernel_mu(projections: list[Mu], input_value: Mu) -> Mu:
    """
    Try each projection in order using structural kernel projections.

    This is the structural replacement for the Python for-loop.
    Uses kernel.v1 + match.v2 + subst.v2 projections for iteration.

    The kernel works as a state machine:
    1. kernel.wrap: Wraps input and projections into kernel state
    2. kernel.try: Tries first projection via match.v2
    3. kernel.match_success/fail: On success, substitute via subst.v2; on fail, try next
    4. kernel.stall: All projections tried, no match
    5. kernel.unwrap: Extract final result

    L2 PARTIAL: Projection SELECTION is structural (linked-list cursor).
    Projection EXECUTION still uses Python for-loop (this function).
    True L2 requires recursive kernel projections (Phase 8).

    Args:
        projections: List of domain projections to try.
        input_value: The value to transform.

    Returns:
        Transformed value if any projection matched, input unchanged otherwise.

    Raises:
        ValueError: If kernel projections appear after domain projections (security).
    """
    assert_mu(input_value, "step_kernel_mu.input")

    # SECURITY: Validate projection order
    validate_kernel_projections_first(projections)

    # Load combined kernel projections
    kernel_projs = load_combined_kernel_projections()

    # Normalize domain projections to head/tail format
    normalized_projs = [normalize_projection(p) for p in projections]

    # Normalize input value
    normalized_input = normalize_for_match(input_value)

    # Build kernel entry format: {_step: normalized_input, _projs: linked_list}
    kernel_entry: Mu = {
        "_step": normalized_input,
        "_projs": list_to_linked(normalized_projs)
    }

    # Run kernel until done or stall
    current = kernel_entry
    max_steps = 10000  # Safety limit

    for _ in range(max_steps):
        result = eval_step(kernel_projs, current)

        # Check for stall (no change)
        if mu_equal(result, current):
            # Stall before reaching done - return original input
            return input_value

        # Check for done state BEFORE unwrap
        # Kernel.done state has _mode=done, _result, _stall
        # If _stall=true, return original input (preserves type info for empty containers)
        if isinstance(result, dict) and result.get("_mode") == "done":
            if result.get("_stall") is True:
                # Kernel indicates stall - return original input
                return input_value
            else:
                # Success - get the result and denormalize
                kernel_result = result.get("_result")
                return denormalize_from_match(kernel_result)

        # Check for final unwrapped result (after kernel.unwrap)
        if isinstance(result, dict):
            mode = result.get("_mode")
            # Final result has no _mode and no entry format markers
            if mode is None and "_step" not in result and "match" not in result and "subst" not in result:
                # Check it's not a match/subst internal state either
                if result.get("mode") not in ("match", "subst"):
                    # Unwrapped result - denormalize and return
                    return denormalize_from_match(result)
        else:
            # Primitive result (from kernel.unwrap)
            return result

        current = result

    # Max steps exceeded - return original input (stall)
    return input_value


# =============================================================================
# Projection Application (Phase 5)
# =============================================================================

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
    Try each projection in order using structural kernel.

    Phase 7d-1: This function now uses the meta-circular kernel
    (kernel.v1 + match.v2 + subst.v2 projections) instead of a Python
    for-loop. The kernel provides iteration without host arithmetic
    or control flow.

    Args:
        projections: List of projections to try.
        input_value: The value to transform.

    Returns:
        Transformed value if any projection matched, input unchanged otherwise.

    Raises:
        ValueError: If kernel projections appear after domain projections (security).
    """
    return step_kernel_mu(projections, input_value)


@host_iteration("Kernel run loop - Phase 7d replaces with meta-circular kernel")
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
