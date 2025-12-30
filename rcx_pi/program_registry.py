# rcx_pi/program_registry.py
"""
Simple in-memory registry for named RCX-π programs.

This is a tiny helper layer so higher-level APIs can talk in terms of
string-named programs like "succ-list" instead of passing closures around.

Design:

- Registry is just a dict[str, Motif].
- We provide basic CRUD-ish helpers:
    * register_program(name, program)
    * get_program(name)
    * has_program(name)
    * clear_registry()
    * list_programs() / list_program_names()

- We also lazily seed a default program "succ-list" so that:
    * list_program_names() includes "succ-list"
    * get_program("succ-list") returns the succ-list closure

  This lazy seeding avoids brittle import-order issues.
"""

from __future__ import annotations

from typing import Dict

from .core.motif import Motif

# Internal registry mapping string names -> Motif closures.
_REGISTRY: Dict[str, Motif] = {}


# ---------------------------------------------------------------------------
# Core registry operations
# ---------------------------------------------------------------------------

def register_program(name: str, program: Motif) -> None:
    """
    Register (or overwrite) a named RCX-π program.

    Args:
        name: Human-readable / API-facing program name.
        program: Motif closure with meta["fn"] = (ev, arg) -> Motif.
    """
    _REGISTRY[name] = program


def get_program(name: str) -> Motif | None:
    """
    Look up a named program by string name.

    Returns:
        Motif closure if present, or None if not registered.
    """
    _ensure_defaults()
    return _REGISTRY.get(name)


def has_program(name: str) -> bool:
    """
    Return True if a program with this name is registered.
    """
    _ensure_defaults()
    return name in _REGISTRY


def clear_registry() -> None:
    """
    Remove all registered programs.

    Used by tests and callers that want a clean slate.
    """
    _REGISTRY.clear()


def list_programs() -> list[str]:
    """
    Return all registered program names, sorted for stability.
    """
    _ensure_defaults()
    return sorted(_REGISTRY.keys())


def list_program_names() -> list[str]:
    """
    Backwards-compatible alias expected by tests.

    Returns:
        List of registered program names, sorted.
    """
    return list_programs()


# ---------------------------------------------------------------------------
# Default / built-in programs
# ---------------------------------------------------------------------------

def _ensure_defaults() -> None:
    """
    Lazily seed built-in named programs into the registry.

    Currently this ensures that "succ-list" is always available.
    """
    if "succ-list" not in _REGISTRY:
        # Local import avoids circular import at module import time.
        from .programs import succ_list_program

        register_program("succ-list", succ_list_program())