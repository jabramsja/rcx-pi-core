# rcx_pi/program_registry.py
"""
Tiny RCX-π program registry.

Maps human-facing RCX program names to factory functions that
construct the corresponding program closures.

This is intentionally minimal; higher layers (RCX-Diamond, etc.)
can wrap this with richer metadata, versions, etc.
"""

from __future__ import annotations

from typing import Callable, Dict

from rcx_pi.core.motif import Motif
from rcx_pi.programs import succ_list_program

# The registry maps names -> zero-arg factories returning Motif programs.
_PROGRAM_FACTORIES: Dict[str, Callable[[], Motif]] = {
    "succ-list": succ_list_program,
}


def list_program_names() -> list[str]:
    """Return all registered RCX-π program names."""
    return sorted(_PROGRAM_FACTORIES.keys())


def has_program(name: str) -> bool:
    """Check if a program name is registered."""
    return name in _PROGRAM_FACTORIES


def get_program(name: str) -> Motif:
    """
    Look up a program by RCX name and construct a fresh closure.

        get_program("succ-list") -> Motif closure

    Raises KeyError if the name is unknown.
    """
    factory = _PROGRAM_FACTORIES.get(name)
    if factory is None:
        raise KeyError(f"Unknown RCX-π program: {name!r}")
    return factory()