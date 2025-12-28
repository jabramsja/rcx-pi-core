# rcx_pi/programs.py
"""
RCX-π programs layer — closure based, minimal, test-oriented.

Implements:
✔ swap_xy_closure
✔ dup_x_closure
✔ rotate_xyz_closure
✔ swap_ends_xyz_closure
✔ activate(closure,arg)

+ Adds features required by test_programs.py:
✔ PROGRAM_TAG, SEQ_TAG
✔ wrap_program(fn)
✔ is_program_block()
✔ seq(a,b,...)  -> sequential composition A∘B∘...

Evaluation rule:
    ev.run(program,arg) executes program.meta["fn"](ev,arg)
"""

from __future__ import annotations
from typing import Callable, List

from rcx_pi.core.motif import Motif, μ
from rcx_pi.listutils import list_from_py, py_from_list, is_list_motif

# =========================================================
# Tags recognized by tests
# =========================================================
PROGRAM_TAG = "PROGRAM"
SEQ_TAG = "SEQ"


# =========================================================
# -- Internal closure builder
# =========================================================
def _make_closure(fn: Callable, tag: str = PROGRAM_TAG) -> Motif:
    m = μ()                     # payload irrelevant, meta drives execution
    meta = {}
    meta["fn"] = fn
    meta["tag"] = tag
    setattr(m, "meta", meta)
    return m


# =========================================================
# Program block detection
# =========================================================
def is_program_block(m: Motif) -> bool:
    meta = getattr(m, "meta", None)
    return isinstance(meta, dict) and meta.get("tag") in {PROGRAM_TAG, SEQ_TAG}


# =========================================================
# Sequential composition — seq(a,b) runs b(a(x))
# =========================================================
def seq(*programs: Motif) -> Motif:
    """Compose program closures sequentially."""
    for p in programs:
        if not is_program_block(p):
            raise TypeError("seq() only accepts program closures")

    def _run(ev, arg):
        out = arg
        for p in programs:
            fn = p.meta["fn"]
            out = fn(ev, out)
        return out

    return _make_closure(_run, tag=SEQ_TAG)


def wrap_program(fn: Callable) -> Motif:
    """Convert a python function(ev,arg) into a runnable closure."""
    return _make_closure(fn, tag=PROGRAM_TAG)


# =========================================================
# Core transformation closures
# =========================================================
def _swap_xy_fn(ev, arg):
    lst = ev.ensure_list(arg)
    py = py_from_list(lst)
    if py is None or len(py) < 2:
        return lst
    py[0], py[1] = py[1], py[0]
    return list_from_py(py)


def _dup_x_fn(ev, arg):
    lst = ev.ensure_list(arg)
    py = py_from_list(lst)
    if not py:
        return lst
    return list_from_py([py[0], py[0]])


def _rotate_xyz_fn(ev, arg):
    lst = ev.ensure_list(arg)
    py = py_from_list(lst)
    return lst if len(py) <= 1 else list_from_py(py[1:]+[py[0]])


def _swap_ends_fn(ev, arg):
    lst = ev.ensure_list(arg)
    py = py_from_list(lst)
    if len(py) < 2:
        return lst
    py[0], py[-1] = py[-1], py[0]
    return list_from_py(py)


# =========================================================
# Public constructors used in tests
# =========================================================
def swap_xy_closure(): return wrap_program(_swap_xy_fn)
def dup_x_closure(): return wrap_program(_dup_x_fn)
def rotate_xyz_closure(): return wrap_program(_rotate_xyz_fn)
def swap_ends_xyz_closure(): return wrap_program(_swap_ends_fn)

def activate(closure, arg): return μ(closure, arg)   # structural only for now