# rcx_pi/api.py
"""
High-level RCX-π API helpers.

This module provides a small, stable surface for working with
named programs and Peano-encoded lists:

    - ints_to_peano_list(xs)  : [int] -> Motif list of Peano numbers
    - peano_list_to_ints(m)   : Motif list -> [int]
    - run_named_list_program  : look up a named program and run it
"""

from __future__ import annotations

from typing import List

from .core.motif import Motif
from rcx_pi.core.numbers import num, motif_to_int
from rcx_pi.listutils import list_from_py, py_from_list
from rcx_pi.engine.evaluator_pure import PureEvaluator
from .program_registry import get_program


def ints_to_peano_list(xs: List[int]) -> Motif:
    """
    Encode a Python list of ints as a motif list of Peano numbers.
    """
    return list_from_py([num(int(x)) for x in xs])  # AST_OK: infra


def peano_list_to_ints(m: Motif) -> List[int]:
    """
    Decode a motif list of Peano numbers back to Python ints.

    This is tolerant of two internal representations:

      - Elements that are still Motif Peano chains.
      - Elements that py_from_list has already simplified to Python ints.

    Raises TypeError if any element cannot be interpreted as a Peano int.
    """
    py = py_from_list(m)
    if py is None:
        raise TypeError("peano_list_to_ints expects a motif list")

    out: List[int] = []
    for elem in py:
        # If it's still a Motif, decode via motif_to_int.
        if isinstance(elem, Motif):
            v = motif_to_int(elem)
            if v is None:
                raise TypeError(f"Element is not a Peano number: {elem!r}")
            out.append(v)
        else:
            # py_from_list may already have converted Peano motifs to ints.
            # In that case we just trust and coerce to int.
            out.append(int(elem))

    return out


def run_named_list_program(name: str, xs: List[int]) -> List[int]:
    """
    Look up a named RCX-π program and run it on a list of Python ints.

    Args:
        name: Registered program name (e.g. "succ-list").
        xs:   Input list of integers.

    Returns:
        A new list of integers, decoded from the program's Peano output.

    Raises:
        KeyError   if no such program is registered.
        TypeError  if the program output is not a Peano-number list.
    """
    prog = get_program(name)
    if prog is None:
        raise KeyError(f"No program named {name!r} is registered")

    ev = PureEvaluator()
    arg_motif = ints_to_peano_list(xs)
    result_motif = ev.run(prog, arg_motif)
    return peano_list_to_ints(result_motif)
