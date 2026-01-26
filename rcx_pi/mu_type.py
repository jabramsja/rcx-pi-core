"""
Mu Type Definition and Validation.

A Mu is a JSON-compatible value: the portable, host-independent data type
for all RCX values. This module provides validation to ensure no Python-specific
types leak into the VM.

See docs/MuType.v0.md for the full specification.
"""

from __future__ import annotations

import json
from typing import Any


# Type alias for documentation (Python's type system can't express recursive JSON)
Mu = Any  # Actually: None | bool | int | float | str | List[Mu] | Dict[str, Mu]

# Maximum nesting depth for Mu validation (prevents RecursionError attacks)
# Set conservatively below Python's default recursion limit (~1000)
# to account for stack frames used by comprehensions
MAX_MU_DEPTH = 200


def is_mu(value: Any, _seen: set[int] | None = None, _depth: int = 0) -> bool:
    """
    Check if a value is a valid Mu (JSON-compatible).

    A Mu is recursively composed of:
    - None (JSON null)
    - bool (JSON true/false)
    - int, float (JSON number)
    - str (JSON string)
    - list of Mu (JSON array)
    - dict with str keys and Mu values (JSON object)

    Args:
        value: The value to check.
        _seen: Internal parameter for cycle detection. Do not pass.
        _depth: Internal parameter for depth tracking. Do not pass.

    Returns:
        True if value is a valid Mu, False otherwise.

    Note:
        Circular references are detected and rejected (return False).
        Deep nesting beyond MAX_MU_DEPTH is rejected (return False).
        This prevents infinite recursion/stack overflow attacks.
    """
    # Depth limit check (prevents RecursionError attacks)
    if _depth > MAX_MU_DEPTH:
        return False

    if value is None:
        return True
    # Check bool before int (bool is subclass of int in Python)
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        # Reject special float values that aren't JSON-compatible
        if isinstance(value, float) and (value != value or value == float('inf') or value == float('-inf')):
            return False  # NaN or Infinity
        return True
    if isinstance(value, str):
        return True

    # For compound types (list, dict), check for circular references
    if isinstance(value, (list, dict)):
        if _seen is None:
            _seen = set()
        value_id = id(value)
        if value_id in _seen:
            # Circular reference detected - not valid Mu
            return False
        _seen = _seen | {value_id}  # Create new set to avoid mutation issues

    if isinstance(value, list):
        return all(is_mu(item, _seen, _depth + 1) for item in value)
    if isinstance(value, dict):
        return (
            all(isinstance(k, str) for k in value.keys()) and
            all(is_mu(v, _seen, _depth + 1) for v in value.values())
        )
    # Anything else (function, class, object, bytes, set, tuple, etc.) is not a Mu
    return False


def validate_mu(value: Any) -> bool:
    """
    Validate that a value is a portable Mu via JSON round-trip.

    This is stricter than is_mu() - it actually serializes and deserializes
    to catch edge cases. Uses allow_nan=False to reject NaN/Infinity.

    Returns:
        True if value round-trips through JSON correctly.
    """
    try:
        # allow_nan=False ensures NaN/Infinity raise ValueError
        serialized = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
        deserialized = json.loads(serialized)
        reserialized = json.dumps(deserialized, sort_keys=True, ensure_ascii=False, allow_nan=False)
        return serialized == reserialized
    except (TypeError, ValueError, OverflowError):
        return False


def assert_mu(value: Any, context: str = "value") -> None:
    """
    Assert that a value is a valid Mu, raising TypeError if not.

    Args:
        value: The value to check.
        context: Description for error message (e.g., "R0 register").

    Raises:
        TypeError: If value is not a valid Mu.
    """
    if not is_mu(value):
        raise TypeError(
            f"{context} must be a Mu (JSON-compatible value), got {type(value).__name__}: {value!r}"
        )


def mu_type_name(value: Any) -> str:
    """
    Return the Mu type name for a value.

    Returns one of: "null", "bool", "int", "float", "str", "list", "dict", or "INVALID".
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return "INVALID"


# =============================================================================
# Structural Purity Guardrails
# =============================================================================
# These functions ensure we program IN RCX (using Mu) rather than ABOUT RCX
# (using Python constructs). See docs/StructuralPurity.v0.md for rationale.
# =============================================================================


def has_callable(value: Any, _seen: set[int] | None = None) -> bool:
    """
    Check if a value contains any callable (function, lambda, method).

    This is a structural purity check - callables cannot be Mu because
    they cannot be serialized to JSON. They represent host (Python) logic
    leaking into the Mu world.

    Args:
        value: The value to check.
        _seen: Internal parameter for cycle detection. Do not pass.

    Returns:
        True if value contains a callable anywhere in its structure.

    Note:
        Circular references are handled safely (return False, no callable found
        in the cycle since we already checked the node).
    """
    if callable(value):
        return True

    # For compound types, check for circular references
    if isinstance(value, (list, dict)):
        if _seen is None:
            _seen = set()
        value_id = id(value)
        if value_id in _seen:
            # Already visited - no callable found on this path
            return False
        _seen = _seen | {value_id}

    if isinstance(value, list):
        return any(has_callable(item, _seen) for item in value)
    if isinstance(value, dict):
        return any(has_callable(v, _seen) for v in value.values())
    return False


def find_callable_path(value: Any, path: str = "", _seen: set[int] | None = None) -> str | None:
    """
    Find the path to the first callable in a value.

    Args:
        value: The value to search.
        path: Current path (internal, builds up during recursion).
        _seen: Internal parameter for cycle detection. Do not pass.

    Returns:
        Path string like "projections[0].handler" or None if no callable found.

    Note:
        Circular references are handled safely.
    """
    if callable(value):
        return path or "(root)"

    # For compound types, check for circular references
    if isinstance(value, (list, dict)):
        if _seen is None:
            _seen = set()
        value_id = id(value)
        if value_id in _seen:
            return None
        _seen = _seen | {value_id}

    if isinstance(value, list):
        for i, item in enumerate(value):
            result = find_callable_path(item, f"{path}[{i}]", _seen)
            if result:
                return result
    if isinstance(value, dict):
        for k, v in value.items():
            result = find_callable_path(v, f"{path}.{k}" if path else k, _seen)
            if result:
                return result
    return None


def assert_no_callables(value: Any, context: str = "value") -> None:
    """
    Assert that a value contains no callables, raising TypeError if it does.

    This prevents Python functions/lambdas from leaking into Mu structures.

    Args:
        value: The value to check.
        context: Description for error message.

    Raises:
        TypeError: If value contains a callable.
    """
    path = find_callable_path(value)
    if path:
        raise TypeError(
            f"{context} contains callable at {path}. "
            f"Seeds must be pure Mu (no functions, lambdas, or methods)."
        )


def assert_seed_pure(seed: Any, context: str = "seed") -> None:
    """
    Verify a seed is pure Mu with no host contamination.

    Checks:
    1. Seed is valid Mu (JSON-compatible)
    2. No callable values anywhere in structure
    3. If seed has projections, each has pattern and body, both Mu

    Args:
        seed: The seed structure to validate.
        context: Description for error message.

    Raises:
        TypeError: If seed is not pure Mu.
        ValueError: If seed structure is invalid.
    """
    # Check 1: Must be valid Mu
    assert_mu(seed, context)

    # Check 2: No callables (redundant with is_mu, but explicit)
    assert_no_callables(seed, context)

    # Check 3: Validate projection structure if present
    if isinstance(seed, dict):
        seed_data = seed.get("seed", seed)
        if isinstance(seed_data, dict):
            projections = seed_data.get("projections", [])
            if isinstance(projections, list):
                for i, proj in enumerate(projections):
                    proj_ctx = f"{context}.projections[{i}]"
                    if not isinstance(proj, dict):
                        raise ValueError(f"{proj_ctx} must be a dict, got {type(proj).__name__}")
                    if "pattern" not in proj:
                        raise ValueError(f"{proj_ctx} missing 'pattern' field")
                    if "body" not in proj:
                        raise ValueError(f"{proj_ctx} missing 'body' field")
                    assert_mu(proj["pattern"], f"{proj_ctx}.pattern")
                    assert_mu(proj["body"], f"{proj_ctx}.body")


def assert_handler_pure(handler: Any, name: str) -> Any:
    """
    Wrap a handler function to verify Mu in, Mu out.

    This is a BOOTSTRAP guardrail. During Phase 1, handlers are Python
    functions. This wrapper ensures they respect Mu boundaries.

    Args:
        handler: The handler function to wrap.
        name: Name for error messages.

    Returns:
        Wrapped handler that validates input/output are Mu.

    Note:
        The handler itself is a Python callable (allowed during bootstrap).
        What's validated is that it receives Mu and returns Mu.
    """
    if not callable(handler):
        raise TypeError(f"Handler '{name}' must be callable, got {type(handler).__name__}")

    def wrapped(context: Mu) -> Mu:
        # Validate input is Mu
        assert_mu(context, f"{name} input")
        # Call original handler
        result = handler(context)
        # Validate output is Mu
        assert_mu(result, f"{name} output")
        return result

    # Preserve original function name for debugging
    wrapped.__name__ = f"pure_{name}"
    wrapped.__doc__ = f"Mu-pure wrapper for {name}"

    return wrapped


def validate_kernel_boundary(func_name: str, inputs: dict[str, Any], output: Any) -> None:
    """
    Validate that a kernel primitive respects Mu boundaries.

    Called by kernel primitives to ensure:
    - All Mu inputs are valid Mu
    - Output is valid Mu (if applicable)

    Args:
        func_name: Name of the kernel primitive.
        inputs: Dict of input name -> value for Mu inputs.
        output: The output value (or None if no Mu output).

    Raises:
        TypeError: If any boundary violation detected.
    """
    for input_name, value in inputs.items():
        assert_mu(value, f"{func_name} {input_name}")
    if output is not None:
        assert_mu(output, f"{func_name} output")


# =============================================================================
# Structural Equality (Anti-Python-Coercion)
# =============================================================================
# Python's == has type coercion (True == 1). We need structural equality
# that compares via canonical JSON serialization.
# =============================================================================


def mu_equal(a: Any, b: Any) -> bool:
    """
    Compare two Mu values for structural equality.

    Uses canonical JSON serialization to avoid Python's type coercion.
    This ensures True != 1 and other edge cases are handled correctly.

    Args:
        a: First Mu value.
        b: Second Mu value.

    Returns:
        True if values are structurally identical.

    Raises:
        TypeError: If either value is not a valid Mu.
    """
    assert_mu(a, "mu_equal.a")
    assert_mu(b, "mu_equal.b")
    return (
        json.dumps(a, sort_keys=True, ensure_ascii=False) ==
        json.dumps(b, sort_keys=True, ensure_ascii=False)
    )


def mu_hash(value: Any) -> str:
    """
    Compute deterministic hash of a Mu value.

    Uses SHA-256 of canonical JSON serialization.

    Args:
        value: A Mu value.

    Returns:
        Hex string of SHA-256 hash.

    Raises:
        TypeError: If value is not a valid Mu.
    """
    import hashlib
    assert_mu(value, "mu_hash")
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


# =============================================================================
# Bootstrap Markers
# =============================================================================
# Functions for marking Python code that will be replaced by seeds.
# =============================================================================


BOOTSTRAP_REGISTRY: list[str] = []


def mark_bootstrap(name: str, reason: str) -> None:
    """
    Mark a function/code section as bootstrap-only.

    Bootstrap code is Python that will be replaced by EVAL_SEED.
    This registry tracks what needs to be removed for true self-hosting.

    Args:
        name: Identifier for the bootstrap code.
        reason: Why this is bootstrap (what seed will replace it).
    """
    entry = f"{name}: {reason}"
    if entry not in BOOTSTRAP_REGISTRY:
        BOOTSTRAP_REGISTRY.append(entry)


def get_bootstrap_registry() -> list[str]:
    """Return list of all registered bootstrap code."""
    return list(BOOTSTRAP_REGISTRY)


def assert_no_bootstrap_in_production() -> None:
    """
    Assert that no bootstrap code is registered.

    Call this in Phase 3+ to verify all Python matching is removed.

    Raises:
        RuntimeError: If bootstrap code is still registered.
    """
    if BOOTSTRAP_REGISTRY:
        raise RuntimeError(
            f"Bootstrap code still present (should be replaced by seeds): "
            f"{BOOTSTRAP_REGISTRY}"
        )
