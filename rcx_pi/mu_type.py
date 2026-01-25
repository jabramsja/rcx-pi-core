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


def is_mu(value: Any) -> bool:
    """
    Check if a value is a valid Mu (JSON-compatible).

    A Mu is recursively composed of:
    - None (JSON null)
    - bool (JSON true/false)
    - int, float (JSON number)
    - str (JSON string)
    - list of Mu (JSON array)
    - dict with str keys and Mu values (JSON object)

    Returns:
        True if value is a valid Mu, False otherwise.
    """
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
    if isinstance(value, list):
        return all(is_mu(item) for item in value)
    if isinstance(value, dict):
        return (
            all(isinstance(k, str) for k in value.keys()) and
            all(is_mu(v) for v in value.values())
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
