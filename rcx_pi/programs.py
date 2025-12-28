# rcx_pi/programs.py
"""
Core RCX-π "library" programs for the minimal stack.

This module provides two layers:

1. Runnable *closures* for the current minimal evaluator:
   - swap_xy_closure
   - dup_x_closure
   - rotate_xyz_closure
   - swap_ends_xyz_closure
   - reverse_list_closure
   - activate

2. Simple "program block" scaffolding used by legacy tests:
   - PROGRAM_TAG, SEQ_TAG
   - wrap_program(body)
   - is_program_block(m)
   - seq(*stmts)

The evaluator only cares about closures (motifs with meta["fn"] = callable).
The program-block helpers are lightweight structural wrappers that tests can
inspect without changing evaluator behaviour.
"""

from __future__ import annotations
from typing import Callable

from rcx_pi.core.motif import Motif, μ
from rcx_pi.listutils import list_from_py, py_from_list


# ---------------------------------------------------------------------------
# Closure construction helper
# ---------------------------------------------------------------------------

def _make_closure(fn: Callable) -> Motif:
    """
    Wrap a Python function as a runnable motif closure.

    The returned motif has no children (μ()) and carries fn in ``meta["fn"]``.
    """
    m = μ()
    meta = getattr(m, "meta", None)
    if not isinstance(meta, dict):
        meta = {}
        setattr(m, "meta", meta)
    meta["fn"] = fn
    return m


# ---------------------------------------------------------------------------
# Tuple-style combinators (x,y,z)  — small, but useful for demos
# ---------------------------------------------------------------------------

def _swap_xy_fn(ev, pair: Motif) -> Motif:
    """
    Swap a pair: (x, y) -> (y, x).
    """
    if not isinstance(pair, Motif) or len(pair.structure) != 2:
        raise TypeError("swap_xy_closure expects μ(x, y)")
    x, y = pair.structure
    return μ(y, x)


def swap_xy_closure() -> Motif:
    return _make_closure(_swap_xy_fn)


def _dup_x_fn(ev, x: Motif) -> Motif:
    """
    Duplicate a value: x -> (x, x).
    """
    return μ(x, x)


def dup_x_closure() -> Motif:
    return _make_closure(_dup_x_fn)


def _rotate_xyz_fn(ev, triple: Motif) -> Motif:
    """
    Rotate a triple left: (x, y, z) -> (y, z, x).
    """
    if not isinstance(triple, Motif) or len(triple.structure) != 3:
        raise TypeError("rotate_xyz_closure expects μ(x, y, z)")
    x, y, z = triple.structure
    return μ(y, z, x)


def rotate_xyz_closure() -> Motif:
    return _make_closure(_rotate_xyz_fn)


# ---------------------------------------------------------------------------
# List programs
# ---------------------------------------------------------------------------

def _swap_ends_fn(ev, xs: Motif) -> Motif:
    """
    Swap the first and last elements of a list.

        [a, b, c, d] -> [d, b, c, a]

    Lists are encoded as CONS/NIL motifs. We round-trip through Python lists
    for clarity; the structural encoding is preserved by listutils.
    """
    xs = ev.ensure_list(xs)
    py = py_from_list(xs)
    if py is None:
        raise TypeError("swap_ends_xyz_closure: not a pure list motif")

    if len(py) <= 1:
        # Nothing to swap
        return xs

    py[0], py[-1] = py[-1], py[0]
    return list_from_py(py)


def swap_ends_xyz_closure() -> Motif:
    """
    Return a closure that, when run, swaps the ends of a list.
    """
    return _make_closure(_swap_ends_fn)


def _reverse_list_fn(ev, xs: Motif) -> Motif:
    """
    Reverse a list structurally.

        []          -> []
        [1]         -> [1]
        [1, 2, 3]   -> [3, 2, 1]
    """
    xs = ev.ensure_list(xs)
    py = py_from_list(xs)
    if py is None:
        raise TypeError("reverse_list_closure: not a pure list motif")

    py.reverse()
    return list_from_py(py)


def reverse_list_closure() -> Motif:
    """
    Return a closure that reverses a list when run by the evaluator.
    """
    return _make_closure(_reverse_list_fn)


# ---------------------------------------------------------------------------
# Generic "activate" stub
# ---------------------------------------------------------------------------

def _activate_fn(ev, arg: Motif) -> Motif:
    """
    Placeholder "activate" program.

    For now this is just the identity function on motifs. It gives us a hook
    for future meta / projection logic without breaking demos.
    """
    return arg


def activate() -> Motif:
    return _make_closure(_activate_fn)


# ---------------------------------------------------------------------------
# Program-block scaffolding (for legacy tests)
# ---------------------------------------------------------------------------

# Simple structural tags. They only need to be consistent, not magical.
PROGRAM_TAG: Motif = μ()          # "this motif is a program block"
SEQ_TAG: Motif = μ(μ())           # "this motif encodes a sequence"


def wrap_program(body: Motif) -> Motif:
    """
    Wrap an arbitrary motif *body* as a "program block":

        body  ->  μ(PROGRAM_TAG, body)

    Tests can use this to check that something is recognised as a program.
    """
    return μ(PROGRAM_TAG, body)


def is_program_block(m: Motif) -> bool:
    """
    Return True iff *m* is structurally a program block.

    Current convention: μ(PROGRAM_TAG, body).
    """
    if not isinstance(m, Motif):
        return False
    if len(m.structure) != 2:
        return False
    tag, _ = m.structure
    return tag == PROGRAM_TAG


def seq(*stmts: Motif) -> Motif:
    """
    Build a "sequence" node out of one or more statements.

        seq(a, b, c)  =>  μ(SEQ_TAG, list_of_stmts)

    where list_of_stmts is the list-encoding produced by list_from_py.
    """
    stmts_list = list_from_py(list(stmts))
    return μ(SEQ_TAG, stmts_list)