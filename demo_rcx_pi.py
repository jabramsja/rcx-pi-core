# demo_rcx_pi.py
#
# One-stop RCX-π demo:
#   - Peano numbers
#   - arithmetic via patterns
#   - projection/closures
#   - tiny "programs" library
#   - meta classification
#

from rcx_pi import μ, VOID, UNIT, PureEvaluator
from rcx_pi.programs import (
    num,
    make_pair,
    swap_xy_closure,
    dup_x_closure,
    rotate_xyz_closure,
)
from rcx_pi.meta import classify_motif, classification_label
from rcx_pi.reduction.pattern_matching import ACTIVATION


# ---------- helpers ----------

def motif_to_int(m):
    """Convert Peano motif to Python int, or None if not pure."""
    # Zero
    if m.is_zero_pure():
        return 0

    count = 0
    cur = m
    while cur.is_successor_pure():
        count += 1
        cur = cur.head()

    return count if cur.is_zero_pure() else None


def pair_to_ints(p):
    """Assume μ(x, y) where x, y are Peano; return (int, int) or (None, None)."""
    if not isinstance(p, type(VOID)) or len(p.structure) != 2:
        return (None, None)
    a, b = p.structure
    return motif_to_int(a), motif_to_int(b)


def triple_to_ints(t):
    """Assume μ(x, y, z) where x,y,z are Peano."""
    if not isinstance(t, type(VOID)) or len(t.structure) != 3:
        return (None, None, None)
    a, b, c = t.structure
    return motif_to_int(a), motif_to_int(b), motif_to_int(c)


# ---------- main demo ----------

if __name__ == "__main__":
    # Turn on tracing so we can watch reductions
    ev = PureEvaluator(trace=True)

    print("=== RCX-π DEMO ===\n")

    # 1) Pure numbers
    print("1) Pure Peano numbers")
    n2 = num(2)
    n5 = num(5)
    print("  2 as motif:", n2, "=>", motif_to_int(n2))
    print("  5 as motif:", n5, "=>", motif_to_int(n5))

    # 2) A pair and projection-based swap
    print("\n2) Pairs and swap closure")
    pair = make_pair(num(2), num(5))
    print("  Original pair motif: ", pair, " => ", pair_to_ints(pair))

    swap_cl = swap_xy_closure()
    act_swap = μ(ACTIVATION, swap_cl, pair)
    print("  Activation motif:    ", act_swap)

    result_swap = ev.reduce(act_swap)
    print("  Reduced motif:       ", result_swap, " => ", pair_to_ints(result_swap))

    # 3) Duplicate-X closure
    print("\n3) Duplicate-X closure: (2,5) -> (2,2)")
    dup_cl = dup_x_closure()
    act_dup = μ(ACTIVATION, dup_cl, pair)
    print("  Activation motif:    ", act_dup)
    result_dup = ev.reduce(act_dup)
    print("  Reduced motif:       ", result_dup, " => ", pair_to_ints(result_dup))

    # 4) Rotate triple
    print("\n4) Rotate triple: (2,5,7) -> (5,7,2)")
    triple = μ(num(2), num(5), num(7))
    print("  Original triple:     ", triple, " => ", triple_to_ints(triple))

    rot_cl = rotate_xyz_closure()
    act_rot = μ(ACTIVATION, rot_cl, triple)
    print("  Activation motif:    ", act_rot)
    result_rot = ev.reduce(act_rot)
    print("  Reduced motif:       ", result_rot, " => ", triple_to_ints(result_rot))

    # 5) Meta classification
    print("\n5) Meta classification (external, but structural)")

    tagged_val = classify_motif(n5)
    tagged_prog = classify_motif(swap_cl)
    tagged_mix = classify_motif(act_swap)

    print("  classify(5):")
    print("    tagged:", tagged_val)
    print("    label: ", classification_label(tagged_val))

    print("\n  classify(swap_closure):")
    print("    tagged:", tagged_prog)
    print("    label: ", classification_label(tagged_prog))

    print("\n  classify(activation(swap, pair)):")
    print("    tagged:", tagged_mix)
    print("    label: ", classification_label(tagged_mix))

    print("\n=== end demo ===")