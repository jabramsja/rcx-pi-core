# rcx_pi/engine/evaluator_pure.py
"""
Pure structural evaluator for RCX-π.

This version intentionally supports only the primitives needed for
list programs like swap_xy_closure, rotate_xyz_closure, etc.

Execution model:
----------------
Programs are motifs of shape μ(f, x) where f is a function motif
produced by *_closure constructors in rcx_pi.programs.

We interpret these closures structurally by applying substitution rules.
Eventually this should evolve into a meta-rewrite engine, but
right now we support:

    run(program, arg) -> motif result

And functions created in programs.py know how to deconstruct lists
and rebuild them using CONS/NIL.
"""

from __future__ import annotations
from typing import Callable

from rcx_pi.core.motif import Motif, μ
from rcx_pi.listutils import (
    CONS, NIL, head, tail, is_list_motif,
    list_from_py, py_from_list,
)


class PureEvaluator:
    """Tiny evaluator executing closures as Python callables."""

    # ----------------------------------------------------------------------
    # Core API used by tests
    # ----------------------------------------------------------------------
    def run(self, program: Motif, arg: Motif) -> Motif:
        """
        Executable entry — programs are motifs carrying Python functions.

        program.structure must be (fn_callable, environment)
        where closure constructors attach a callable in .meta field.
        """

        fn = self._extract_func(program)
        if not callable(fn):
            raise TypeError(f"Program is not runnable: {program}")

        return fn(self, arg)


    # ----------------------------------------------------------------------
    # Closure extraction
    # ----------------------------------------------------------------------
    def _extract_func(self, program: Motif) -> Callable:
        """
        program must have .payload containing Python function.

        Programs created by swap_xy_closure etc store Python functions
        directly in program.meta['fn'].
        """
        meta = getattr(program, "meta", None)
        if not isinstance(meta, dict) or "fn" not in meta:
            raise TypeError("Motif is not a function closure")

        return meta["fn"]


    # ----------------------------------------------------------------------
    # Helpers used by functions inside programs.py
    # ----------------------------------------------------------------------
    def cons(self, h: Motif, t: Motif) -> Motif:
        return CONS(h, t)

    def nil(self) -> Motif:
        return NIL()

    def ensure_list(self, m: Motif) -> Motif:
        if not is_list_motif(m):
            raise TypeError("Expected list-like motif")
        return m

    def head(self, m: Motif) -> Motif:
        return head(m)

    def tail(self, m: Motif) -> Motif:
        return tail(m)
    # ----------------------------------------------------------------------
    # Legacy compatibility shims for old tests/benchmarks
    # ----------------------------------------------------------------------
    def reduce(self, expr):
        """
        Temporary stub so old benchmark/test code can call ev.reduce().
        Currently aliases to run(), assuming expr is a closure expecting arg.
        If expr is just data (not a closure), returns expr unchanged.

        Later this becomes the real rewrite reducer.
        """
        try:
            fn = self._extract_func(expr)
            # treat as nullary program taking UNIT/NIL
            return fn(self, None)   # modify if benchmarks need argument passing
        except Exception:
            return expr  # not executable → return motif as-is

    def reduce_full(self, expr, max_steps=10000):
        """
        Compatibility wrapper.
        Calls reduce repeatedly until expression stops changing.
        Later replaced by structural rewrite loop.
        """
        prev = None
        cur  = expr
        steps = 0
        while cur != prev and steps < max_steps:
            prev = cur
            cur = self.reduce(cur)
            steps += 1
        return cur