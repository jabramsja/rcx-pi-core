# example_rcx.py

"""
Example usage of RCX-π structural programs:
  - swap_xy_closure:      (x, y)   -> (y, x)
  - dup_x_closure:        (x, y)   -> (x, x)
  - rotate_xyz_closure:   (x, y, z)-> (y, z, x)
  - swap_ends_xyz_closure:(x, y, z)-> (z, y, x)
"""

from rcx_pi import μ, VOID, PureEvaluator
from rcx_pi.core.motif import Motif
from rcx_pi.programs import (
    swap_xy_closure,
    dup_x_closure,
    rotate_xyz_closure,
    swap_ends_xyz_closure,
    activate,
)

def motif_to_int(m: Motif):
    if not isinstance(m, Motif):
        return None
    if m.is_zero_pure():
        return 0
    count = 0
    cur = m
    while cur.is_successor_pure():
        count += 1
        cur = cur.head()
    return count if cur.is_zero_pure() else None

def num(n: int) -> Motif:
    m = VOID
    for _ in range(n):
        m = m.succ()
    return m

def motif_to_pair(m: Motif):
    if not isinstance(m, Motif) or len(m.structure) != 2:
        return None
    a, b = m.structure
    return motif_to_int(a), motif_to_int(b)

def motif_to_triple(m: Motif):
    if not isinstance(m, Motif) or len(m.structure) != 3:
        return None
    a, b, c = m.structure
    return motif_to_int(a), motif_to_int(b), motif_to_int(c)


if __name__ == "__main__":
    ev = PureEvaluator()

    n2 = num(2)
    n5 = num(5)
    n7 = num(7)

    # 1) swap (x, y) -> (y, x)
    print("=== swap_xy_closure: (2, 5) -> (5, 2) ===")
    pair = μ(n2, n5)
    print("Original pair motif:  ", pair, " =>  ", motif_to_pair(pair))
    swap_cl = swap_xy_closure()
    expr = activate(swap_cl, pair)
    print("Activation motif:      ", expr)
    res = ev.reduce(expr)
    print("Reduced motif:         ", res, " =>  ", motif_to_pair(res))
    print()

    # 2) dup_x: (x, y) -> (x, x)
    print("=== dup_x_closure: (2, 5) -> (2, 2) ===")
    pair2 = μ(n2, n5)
    print("Original pair motif:  ", pair2, " =>  ", motif_to_pair(pair2))
    dup_cl = dup_x_closure()
    expr2 = activate(dup_cl, pair2)
    print("Activation motif:      ", expr2)
    res2 = ev.reduce(expr2)
    print("Reduced motif:         ", res2, " =>  ", motif_to_pair(res2))
    print()

    # 3) rotate (x, y, z) -> (y, z, x)
    print("=== rotate_xyz_closure: (2, 5, 7) -> (5, 7, 2) ===")
    triple = μ(n2, n5, n7)
    print("Original triple:       ", triple, " =>  ", motif_to_triple(triple))
    rot_cl = rotate_xyz_closure()
    expr3 = activate(rot_cl, triple)
    print("Activation motif:      ", expr3)
    res3 = ev.reduce(expr3)
    print("Reduced motif:         ", res3, " =>  ", motif_to_triple(res3))
    print()

    # 4) swap ends (x, y, z) -> (z, y, x)
    print("=== swap_ends_xyz_closure: (2, 5, 7) -> (7, 5, 2) ===")
    triple2 = μ(n2, n5, n7)
    print("Original triple:       ", triple2, " =>  ", motif_to_triple(triple2))
    swap_ends_cl = swap_ends_xyz_closure()
    expr4 = activate(swap_ends_cl, triple2)
    print("Activation motif:      ", expr4)
    res4 = ev.reduce(expr4)
    print("Reduced motif:         ", res4, " =>  ", motif_to_triple(res4))