"""
EVAL_SEED v0 - Foundational Seed for RCX

This module implements the core operations needed to evaluate projections:
1. match(pattern, input) - structural pattern matching
2. substitute(body, bindings) - variable substitution
3. apply(projection, input) - match + substitute
4. step(projections, input) - select and apply first matching projection

The only special form is {"var": "<name>"} which matches anything and binds.

See docs/EVAL_SEED.v0.md for specification.
"""

from __future__ import annotations

from typing import Any

from rcx_pi.mu_type import Mu, assert_mu, is_mu


# Sentinel for no match (not a valid Mu, so unambiguous)
class _NoMatch:
    """Sentinel indicating pattern did not match."""
    __slots__ = ()

    def __repr__(self) -> str:
        return "NO_MATCH"


NO_MATCH = _NoMatch()


# =============================================================================
# Core Operations
# =============================================================================


def is_var(mu: Mu) -> bool:
    """Check if mu is a variable site {"var": "<name>"}."""
    return (
        isinstance(mu, dict)
        and len(mu) == 1
        and "var" in mu
        and isinstance(mu["var"], str)
    )


def get_var_name(mu: Mu) -> str:
    """Extract variable name from {"var": "<name>"}."""
    if not is_var(mu):
        raise ValueError(f"Not a variable site: {mu}")
    return mu["var"]


def match(pattern: Mu, input_value: Mu) -> dict[str, Mu] | _NoMatch:
    """
    Match pattern against input, returning bindings or NO_MATCH.

    Rules:
    - {"var": "x"} matches anything, binds to x
    - Literals match if equal (null, bool, int, float, str)
    - Lists match if same length and all elements match
    - Dicts match if same keys and all values match

    Args:
        pattern: The pattern to match (Mu with possible var sites).
        input_value: The value to match against (Mu).

    Returns:
        Dict of bindings {"var_name": value} if match, NO_MATCH otherwise.
    """
    # Guardrails
    assert_mu(pattern, "match.pattern")
    assert_mu(input_value, "match.input")

    # Variable site - matches anything
    if is_var(pattern):
        name = get_var_name(pattern)
        return {name: input_value}

    # None
    if pattern is None:
        return {} if input_value is None else NO_MATCH

    # Bool (must check before int because bool is subclass of int in Python)
    if isinstance(pattern, bool):
        if isinstance(input_value, bool) and pattern == input_value:
            return {}
        return NO_MATCH

    # Int
    if isinstance(pattern, int):
        if isinstance(input_value, int) and not isinstance(input_value, bool):
            if pattern == input_value:
                return {}
        return NO_MATCH

    # Float
    if isinstance(pattern, float):
        if isinstance(input_value, float) and pattern == input_value:
            return {}
        return NO_MATCH

    # String
    if isinstance(pattern, str):
        if isinstance(input_value, str) and pattern == input_value:
            return {}
        return NO_MATCH

    # List
    if isinstance(pattern, list):
        if not isinstance(input_value, list):
            return NO_MATCH
        if len(pattern) != len(input_value):
            return NO_MATCH
        bindings: dict[str, Mu] = {}
        for p_elem, i_elem in zip(pattern, input_value):
            sub_bindings = match(p_elem, i_elem)
            if sub_bindings is NO_MATCH:
                return NO_MATCH
            # Merge bindings (check for conflicts)
            for k, v in sub_bindings.items():
                if k in bindings:
                    # Same variable bound twice - must be same value
                    # Use JSON comparison for structural equality
                    import json
                    if json.dumps(bindings[k], sort_keys=True) != json.dumps(v, sort_keys=True):
                        return NO_MATCH
                bindings[k] = v
        return bindings

    # Dict
    if isinstance(pattern, dict):
        if not isinstance(input_value, dict):
            return NO_MATCH
        if set(pattern.keys()) != set(input_value.keys()):
            return NO_MATCH
        bindings = {}
        for key in pattern:
            sub_bindings = match(pattern[key], input_value[key])
            if sub_bindings is NO_MATCH:
                return NO_MATCH
            # Merge bindings
            for k, v in sub_bindings.items():
                if k in bindings:
                    import json
                    if json.dumps(bindings[k], sort_keys=True) != json.dumps(v, sort_keys=True):
                        return NO_MATCH
                bindings[k] = v
        return bindings

    # Should not reach here if input is valid Mu
    return NO_MATCH


def substitute(body: Mu, bindings: dict[str, Mu]) -> Mu:
    """
    Substitute variable sites in body with bound values.

    Args:
        body: The body with possible {"var": "x"} sites.
        bindings: Dict mapping variable names to values.

    Returns:
        Body with variables replaced by their bound values.

    Raises:
        KeyError: If a variable in body is not in bindings.
    """
    assert_mu(body, "substitute.body")

    # Variable site - replace with bound value
    if is_var(body):
        name = get_var_name(body)
        if name not in bindings:
            raise KeyError(f"Unbound variable: {name}")
        return bindings[name]

    # None, bool, int, float, str - return as-is
    if body is None or isinstance(body, (bool, int, float, str)):
        return body

    # List - recursively substitute
    if isinstance(body, list):
        return [substitute(elem, bindings) for elem in body]

    # Dict - recursively substitute values
    if isinstance(body, dict):
        return {k: substitute(v, bindings) for k, v in body.items()}

    # Should not reach here
    raise TypeError(f"Invalid body type: {type(body)}")


def apply_projection(projection: Mu, input_value: Mu) -> Mu | _NoMatch:
    """
    Apply a projection to an input value.

    A projection is {"pattern": P, "body": B}.
    If P matches input, return B with substitutions.
    Otherwise return NO_MATCH.

    Args:
        projection: Dict with "pattern" and "body" keys.
        input_value: The value to transform.

    Returns:
        Transformed value if pattern matched, NO_MATCH otherwise.
    """
    assert_mu(projection, "apply.projection")
    assert_mu(input_value, "apply.input")

    if not isinstance(projection, dict):
        raise TypeError(f"Projection must be dict, got {type(projection)}")
    if "pattern" not in projection or "body" not in projection:
        raise KeyError("Projection must have 'pattern' and 'body' keys")

    pattern = projection["pattern"]
    body = projection["body"]

    bindings = match(pattern, input_value)
    if bindings is NO_MATCH:
        return NO_MATCH

    return substitute(body, bindings)


def step(projections: list[Mu], input_value: Mu) -> Mu:
    """
    Try each projection in order, return first successful application.

    If no projection matches, return input unchanged (this causes a stall).

    Args:
        projections: List of projections to try.
        input_value: The value to transform.

    Returns:
        Transformed value if any projection matched, input unchanged otherwise.
    """
    assert_mu(input_value, "step.input")

    for proj in projections:
        result = apply_projection(proj, input_value)
        if result is not NO_MATCH:
            return result

    # No match - return input unchanged (stall)
    return input_value


# =============================================================================
# Kernel Handlers
# =============================================================================


def create_step_handler(projections: list[Mu]):
    """
    Create a step handler for the kernel with given projections.

    Args:
        projections: List of projections to use.

    Returns:
        Handler function for "step" event.
    """
    def step_handler(context: Mu) -> Mu:
        """Handle step event: apply projections to current value."""
        assert_mu(context, "step_handler.context")
        if not isinstance(context, dict) or "mu" not in context:
            raise KeyError("step_handler context must have 'mu' key")
        return step(projections, context["mu"])

    return step_handler


def create_stall_handler():
    """
    Create a stall handler for the kernel.

    For now, just returns the stalled value. Later versions may
    signal closure, retry with different projections, etc.

    Returns:
        Handler function for "stall" event.
    """
    def stall_handler(context: Mu) -> Mu:
        """Handle stall event: return stalled value."""
        assert_mu(context, "stall_handler.context")
        if not isinstance(context, dict) or "mu" not in context:
            raise KeyError("stall_handler context must have 'mu' key")
        return context["mu"]

    return stall_handler


def create_init_handler():
    """
    Create an init handler for the kernel.

    Returns:
        Handler function for "init" event.
    """
    def init_handler(context: Mu) -> Mu:
        """Handle init event: return initial value."""
        assert_mu(context, "init_handler.context")
        if not isinstance(context, dict) or "mu" not in context:
            raise KeyError("init_handler context must have 'mu' key")
        return context["mu"]

    return init_handler


# =============================================================================
# Seed Configuration
# =============================================================================


def create_eval_seed(projections: list[Mu]) -> dict:
    """
    Create a complete EVAL_SEED configuration.

    Args:
        projections: List of projections for this seed.

    Returns:
        Dict with handlers for kernel registration.
    """
    return {
        "step": create_step_handler(projections),
        "stall": create_stall_handler(),
        "init": create_init_handler(),
    }


def register_eval_seed(kernel, projections: list[Mu]) -> None:
    """
    Register EVAL_SEED handlers with a kernel.

    Args:
        kernel: Kernel instance to register with.
        projections: List of projections for this seed.
    """
    handlers = create_eval_seed(projections)
    for event, handler in handlers.items():
        kernel.register_handler(event, handler)
