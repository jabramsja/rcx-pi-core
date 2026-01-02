# rcx_pi/__init__.py
"""
RCX-π public API surface — minimal, test-proof, docs-aligned.

This module exposes a small, coherent core:

    - Motif primitives: Motif, μ, VOID, UNIT
    - Evaluator: PureEvaluator, new_evaluator()
    - Numbers: num, succ, pred, motif_to_int, add, zero
    - Lists: list_from_py, py_from_list, NIL, CONS, is_list_motif, head, tail
    - Pretty / meta: pretty_motif, classify_motif
    - Programs: swap_xy_closure, dup_x_closure, rotate_xyz_closure,
                swap_ends_xyz_closure, reverse_list_closure,
                append_lists_closure, activate, bytecode helpers
    - High-level API: ints_to_peano_list, peano_list_to_ints,
                      run_named_list_program
"""

from __future__ import annotations
from .api import (
    ints_to_peano_list,
    peano_list_to_ints,
    run_named_list_program,
)
from .programs import (
    swap_xy_closure,
    dup_x_closure,
    rotate_xyz_closure,
    swap_ends_xyz_closure,
    reverse_list_closure,
    append_lists_closure,
    activate,
    OP_PUSH_CONST,
    OP_ADD,
    OP_HALT,
    make_instr,
    bytecode_closure,
)
from .pretty import pretty_motif
from .meta import classify_motif

# ---------------------------------------------------------------------------
# Core motif + numbers
# ---------------------------------------------------------------------------

from .core.motif import Motif, μ, VOID, UNIT
from .core.numbers import num, succ, pred, motif_to_int, add, zero

# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------

from .listutils import (
    list_from_py,
    py_from_list,
    NIL,
    CONS,
    is_list_motif,
    head,
    tail,
)

# ---------------------------------------------------------------------------
# Evaluator selection
# ---------------------------------------------------------------------------

try:
    from .engine.evaluator_pure import PureEvaluator

    _DefaultEvaluator = PureEvaluator
except ImportError:
    try:
        from .evaluator import Evaluator as _DefaultEvaluator  # legacy fallback

        PureEvaluator = _DefaultEvaluator
    except ImportError:
        _DefaultEvaluator = None
        PureEvaluator = None  # type: ignore


def new_evaluator():
    """Return a fresh evaluator instance for running RCX-π programs."""
    if _DefaultEvaluator is None:
        raise RuntimeError("No evaluator found in rcx_pi.")
    return _DefaultEvaluator()


# ---------------------------------------------------------------------------
# Pretty / Meta
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Programs: hosted closures operating on lists and motifs
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# High-level API (from api.py, no circular imports)
# ---------------------------------------------------------------------------


__all__ = [
    # core
    "Motif",
    "μ",
    "VOID",
    "UNIT",
    # evaluator
    "PureEvaluator",
    "new_evaluator",
    # numbers
    "num",
    "succ",
    "pred",
    "add",
    "motif_to_int",
    "zero",
    # lists
    "list_from_py",
    "py_from_list",
    "NIL",
    "CONS",
    "is_list_motif",
    "head",
    "tail",
    # pretty
    "pretty_motif",
    # meta
    "classify_motif",
    # programs
    "swap_xy_closure",
    "dup_x_closure",
    "rotate_xyz_closure",
    "swap_ends_xyz_closure",
    "reverse_list_closure",
    "append_lists_closure",
    "activate",
    "OP_PUSH_CONST",
    "OP_ADD",
    "OP_HALT",
    "make_instr",
    "bytecode_closure",
    # high-level API
    "ints_to_peano_list",
    "peano_list_to_ints",
    "run_named_list_program",
]
