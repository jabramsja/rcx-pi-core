# test_projection.py
"""
Tiny RCX-π demo: swap a pair (x, y) -> (y, x) using the *current* closure-based core.

This is not a pytest test; it's a standalone demo that you can run with:

    python3 test_projection.py
"""

from rcx_pi import num, motif_to_int
from rcx_pi.engine.evaluator_pure import PureEvaluator
from rcx_pi.programs import swap_xy_closure, activate
from rcx_pi.listutils import list_from_py, py_from_list
from rcx_pi.core.motif import Motif


def pair_motif_to_ints(m: Motif) -> tuple[int, int]:
    """
    Decode a pair [a, b] where a and b are Peano-number motifs OR already
    decoded Python ints (as produced by py_from_list).
    """
    xs = py_from_list(m)
    if not isinstance(xs, list) or len(xs) != 2:
        raise TypeError(f"Expected motif list [left, right], got {xs!r}")

    left_v, right_v = xs

    def to_int(v):
        # Case 1: py_from_list already gave us a Python int
        if isinstance(v, int):
            return v

        # Case 2: still a Motif → interpret as Peano
        if isinstance(v, Motif):
            n = motif_to_int(v)
            if n is None:
                raise TypeError(f"Element {v!r} is not a Peano number")
            return n

        # Anything else is a bug in caller / encoding
        raise TypeError(f"Unsupported element type {type(v)}: {v!r}")

    return to_int(left_v), to_int(right_v)

if __name__ == "__main__":
    ev = PureEvaluator()

    # Build Peano numbers 2 and 5
    a = num(2)
    b = num(5)

    # Build pair [2, 5] as a list motif
    pair = list_from_py([a, b])

    # Build swap-XY closure and run it on the pair
    swap = swap_xy_closure()
    result = activate(ev, swap, pair)

    print("=== RCX-π projection demo: swap [x, y] -> [y, x] ===")
    print("Original pair motif:  ", pair, " => ", pair_motif_to_ints(pair))
    print("Result pair motif:    ", result, " => ", pair_motif_to_ints(result))