# demo_rcx_pi.py
"""
RCX-π DEMO

End-to-end structural demo:
  1) Peano numbers
  2) Pairs and closures (swap, dup, rotate)
  3) Meta classification
"""

from rcx_pi import μ, VOID, UNIT, PureEvaluator
from rcx_pi.core.motif import Motif
from rcx_pi.programs import (
    swap_xy_closure,
    dup_x_closure,
    rotate_xyz_closure,
    activate,
)
from rcx_pi.meta import classify_motif, classification_label


# ---------- helpers ----------

def motif_to_int(m: Motif):
    """Convert Peano motif to Python int (if pure Peano)."""
    if not isinstance(m, Motif):
        return None

    if m.is_zero_pure():
        return 0

    count = 0
    cur = m
    while cur.is_successor_pure():
        count += 1
        cur = cur.head()

    if cur.is_zero_pure():
        return count
    return None


def num(n: int) -> Motif:
    """Build Peano n as nested successors over VOID."""
    m = VOID
    for _ in range(n):
        m = m.succ()
    return m


def motif_to_pair(m: Motif):
    """Assume motif is μ(a, b); decode each as int."""
    if not isinstance(m, Motif) or len(m.structure) != 2:
        return None
    a, b = m.structure
    return motif_to_int(a), motif_to_int(b)


def motif_to_triple(m: Motif):
    """Assume motif is μ(a, b, c); decode each as int."""
    if not isinstance(m, Motif) or len(m.structure) != 3:
        return None
    a, b, c = m.structure
    return motif_to_int(a), motif_to_int(b), motif_to_int(c)


# ---------- main demo ----------

if __name__ == "__main__":
    ev = PureEvaluator()

    print("=== RCX-π DEMO ===\n")

    # 1) Pure Peano numbers
    n2 = num(2)
    n5 = num(5)

    print("1) Pure Peano numbers")
    print("  2 as motif: ", n2, "=>", motif_to_int(n2))
    print("  5 as motif: ", n5, "=>", motif_to_int(n5))
    print()

    # 2) Pairs and swap closure
    print("2) Pairs and swap closure")
    pair = μ(n2, n5)
    print("  Original pair motif: ", pair, " => ", motif_to_pair(pair))

    swap_cl = swap_xy_closure()
    act_swap = activate(swap_cl, pair)
    print("  Activation motif:    ", act_swap)
    r_swap = ev.reduce(act_swap)
    print("  Reduced motif:       ", r_swap, " => ", motif_to_pair(r_swap))
    print()

    # 3) Duplicate-X closure: (2,5) -> (2,2)
    print("3) Duplicate-X closure: (2,5) -> (2,2)")
    dup_cl = dup_x_closure()
    act_dup = activate(dup_cl, pair)
    print("  Activation motif:    ", act_dup)
    r_dup = ev.reduce(act_dup)
    print("  Reduced motif:       ", r_dup, " => ", motif_to_pair(r_dup))
    print()

    # 4) Rotate triple: (2,5,7) -> (5,7,2)
    print("4) Rotate triple: (2,5,7) -> (5,7,2)")
    n7 = num(7)
    triple = μ(n2, n5, n7)
    print("  Original triple:     ", triple, " => ", motif_to_triple(triple))

    rot_cl = rotate_xyz_closure()
    act_rot = activate(rot_cl, triple)
    print("  Activation motif:    ", act_rot)
    r_rot = ev.reduce(act_rot)
    print("  Reduced motif:       ", r_rot, " => ", motif_to_triple(r_rot))
    print()

    # 5) Meta classification
    print("5) Meta classification (external, structural)")

    # classify(5)
    tagged_5 = classify_motif(n5)
    print("  classify(5):")
    print("    tagged:", tagged_5)
    print("    label: ", classification_label(tagged_5))
    print()

    # classify(swap_closure)
    tagged_swap = classify_motif(swap_cl)
    print("  classify(swap_closure):")
    print("    tagged:", tagged_swap)
    print("    label: ", classification_label(tagged_swap))
    print()

    # classify(activate(swap, pair))
    act_swap_again = activate(swap_cl, pair)
    tagged_act = classify_motif(act_swap_again)
    print("  classify(activation(swap, pair)):")
    print("    tagged:", tagged_act)
    print("    label: ", classification_label(tagged_act))
    print()

    print("=== end demo ===")