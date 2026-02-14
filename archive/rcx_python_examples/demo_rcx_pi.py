#!/usr/bin/env python3
"""
demo_rcx_pi.py

Tiny, friendly walkthrough of the current RCX-π core:

- Peano numbers (num, add, motif_to_int, zero)
- Lists (list_from_py, py_from_list)
- List program (swap_ends_xyz_closure via PureEvaluator.run)
- Pretty-print + classification

Run with:
    python3 demo_rcx_pi.py
"""

from rcx_pi import num, add, motif_to_int
from rcx_pi.core.motif import Motif
from rcx_pi.listutils import list_from_py, py_from_list, is_list_motif
from rcx_pi.programs import swap_ends_xyz_closure, succ_list_program
from rcx_pi import PureEvaluator

import rcx_pi


def demo_numbers() -> None:
    print("=== Numbers ===")
    n3 = rcx_pi.num(3)
    n5 = rcx_pi.num(5)
    s = rcx_pi.add(n3, n5)

    print("n3 motif:", n3)
    print("n5 motif:", n5)
    print("3 + 5 motif:", s)
    print("back to int:", rcx_pi.motif_to_int(s))

    tagged = rcx_pi.classify_motif(n5)
    print("classified motif (pretty):", rcx_pi.pretty_motif(tagged))
    print()


def demo_lists() -> None:
    print("=== Lists ===")
    xs = [1, 2, 3, 4]
    mlist = rcx_pi.list_from_py(xs)
    print("python list:", xs)
    print("motif list:", mlist)
    print("back to python:", rcx_pi.py_from_list(mlist))
    print("is_list_motif:", rcx_pi.is_list_motif(mlist))
    print()


def demo_swap_ends() -> None:
    print("=== swap_ends_xyz_closure ===")
    xs = [1, 2, 3, 4]
    mlist = rcx_pi.list_from_py(xs)

    ev = rcx_pi.new_evaluator()
    prog = rcx_pi.swap_ends_xyz_closure()

    out = ev.run(prog, mlist)
    out_py = rcx_pi.py_from_list(out)

    print("input list motif: ", mlist)
    print("output list motif:", out)
    print("output as python: ", out_py)
    print()

    # === succ_list_program (map +1 over a list of Peano numbers) ===
    print("\n=== succ_list_program (RCX-π named program) ===")

    ev = PureEvaluator()
    prog = succ_list_program()

    xs = list_from_py([num(0), num(1), num(2), num(3)])
    out = ev.run(prog, xs)

    print("input Peano list motif: ", xs)
    print("output Peano list motif:", out)

    # py_from_list now decodes Peano motifs to ints, so this should be [1, 2,
    # 3, 4]
    out_ints = py_from_list(out)
    print("output as Python ints:  ", out_ints)


def main() -> None:
    print("RCX-π demo (current core)\n")
    demo_numbers()
    demo_lists()
    demo_swap_ends()


if __name__ == "__main__":
    main()
