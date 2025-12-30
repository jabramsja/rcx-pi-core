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

from .core.motif import Motif, μ, VOID, UNIT

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
# Numbers: Peano representation and helpers
# ---------------------------------------------------------------------------

def num(n: int) -> Motif:
    """Build Peano number n as a pure successor chain."""
    if n < 0:
        raise ValueError("num only supports n>=0")
    m = VOID
    for _ in range(n):
        m = m.succ()
    return m


def succ(m: Motif) -> Motif:
    """Successor of a Peano motif."""
    return m.succ()


def pred(m: Motif):
    """Predecessor of a Peano motif, or None for zero / non-successor."""
    return m.head() if m.is_successor_pure() else None


def motif_to_int(m: Motif) -> int | None:
    """
    Interpret a Motif as a Peano integer.

    Returns:
        int  if the motif is a pure successor chain
        None otherwise
    """
    if not isinstance(m, Motif):
        return None
    if m.is_zero_pure():
        return 0
    n = 0
    cur = m
    while cur.is_successor_pure():
        n += 1
        cur = cur.head()
    return n if cur.is_zero_pure() else None


def add(a: Motif, b: Motif) -> Motif:
    """Peano addition via integer view + reconstruction."""
    va = motif_to_int(a)
    vb = motif_to_int(b)
    if va is None or vb is None:
        raise TypeError("add expects Peano numbers")
    return num(va + vb)


# Canonical zero alias used in tests and examples.
def zero() -> Motif:
    return VOID


# ---------------------------------------------------------------------------
# Lists: structural encoding and helpers
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
# Pretty / Meta
# ---------------------------------------------------------------------------

from .pretty import pretty_motif
from .meta import classify_motif


# ---------------------------------------------------------------------------
# Programs: hosted closures operating on lists and motifs
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# High-level API
# ---------------------------------------------------------------------------

from .api import (
    ints_to_peano_list,
    peano_list_to_ints,
    run_named_list_program,
)


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