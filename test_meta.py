# test_meta.py

from rcx_pi import μ, VOID, UNIT, PureEvaluator, classify_motif, classification_label
from rcx_pi.programs import (
    swap_xy_closure,
    dup_x_closure,
    rotate_xyz_closure,
)


# ---------- helpers copied from test_numbers ----------

def motif_to_int(m):
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


def num(n: int):
    m = VOID
    for _ in range(n):
        m = m.succ()
    return m


def pair(a, b):
    return μ(a, b)


def triple(a, b, c):
    return μ(a, b, c)


if __name__ == "__main__":
    ev = PureEvaluator()

    # 1) Pure value lobe: a plain Peano number
    print("=== classify pure value (number) ===")
    n5 = num(5)
    tagged_n5 = classify_motif(n5)
    print("Motif:", n5, " => ", motif_to_int(n5))
    print("Tagged:", tagged_n5)
    print("Label:", classification_label(tagged_n5))
    print()

    # 2) Pure program lobe: a closure (swap_xy)
    print("=== classify pure program (closure) ===")
    swap_cl = swap_xy_closure()
    tagged_swap = classify_motif(swap_cl)
    print("Swap closure motif:", swap_cl)
    print("Tagged:", tagged_swap)
    print("Label:", classification_label(tagged_swap))
    print()

    # 3) Mixed lobe: program + embedded numbers
    print("=== classify mixed motif: activated program on numeric pair ===")
    p = pair(num(2), num(5))
    act = μ(  # activation: APPLY swap_xy_closure to pair(2,5)
        # ACTIVATION marker is built inside the programs module,
        # but we can just reuse the closure and pair structurally:
        # μ(ACTIVATION_MARKER, closure, arg)
        # we don't import the marker directly here, we let programs build it.
        # So instead: use the same construction programs.py uses:
        #   from rcx_pi.programs import apply_closure
        # but to keep this file minimal, we'll just treat the *result*.
        #
        # Simpler: just use swap_xy_closure() applied via the engine in programs.py
        # and classify that result as "value".
        #
        # For a clearly mixed motif, we *wrap* the closure + pair:
        swap_cl,
        p,
    )
    # This "act" isn't a valid ACTIVATION form by itself, so classification
    # will just see a structure that contains both a closure and numbers.
    tagged_mixed = classify_motif(act)
    print("Mixed raw motif:", act)
    print("Tagged:", tagged_mixed)
    print("Label:", classification_label(tagged_mixed))
    print()

    # 4) Generic structural: some random nested motif that is neither a number nor program
    print("=== classify generic structural motif ===")
    s = μ(μ(VOID, UNIT), μ(UNIT, VOID))
    tagged_s = classify_motif(s)
    print("Struct motif:", s)
    print("Tagged:", tagged_s)
    print("Label:", classification_label(tagged_s))