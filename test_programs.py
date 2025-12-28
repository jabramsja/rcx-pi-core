# test_programs.py

from rcx_pi import μ, VOID, UNIT, PureEvaluator
from rcx_pi.core.motif import Motif
from rcx_pi.reduction.pattern_matching import ACTIVATION
from rcx_pi.programs import (
    swap_xy_closure,
    dup_x_closure,
    rotate_xyz_closure,
)

# ---------- small helper to build activation ----------

def activate(func: Motif, arg: Motif) -> Motif:
    """
    Build a proper RCX-π activation motif:

        activate(f, x) = μ(ACTIVATION, f, x)
    """
    return μ(ACTIVATION, func, arg)


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


# ---------- tests ----------

if __name__ == "__main__":
    ev = PureEvaluator()

    # numbers we'll use
    n2 = num(2)
    n5 = num(5)
    n7 = num(7)

    # 1) swap (x, y) -> (y, x)
    print("=== swap_xy_closure: (2, 5) -> (5, 2) ===")
    pair = μ(n2, n5)
    print("Original pair motif: ", pair, " =>  ", motif_to_pair(pair))

    swap_cl = swap_xy_closure()
    expr = activate(swap_cl, pair)
    print("Activation motif:     ", expr)

    res = ev.reduce(expr)
    print("Reduced motif:        ", res, " =>  ", motif_to_pair(res))
    print()

    # 2) dup_x: (x, y) -> (x, x)
    print("=== dup_x_closure: (2, 5) -> (2, 2) ===")
    pair2 = μ(n2, n5)
    print("Original pair motif: ", pair2, " =>  ", motif_to_pair(pair2))

    dup_cl = dup_x_closure()
    expr2 = activate(dup_cl, pair2)
    print("Activation motif:     ", expr2)

    res2 = ev.reduce(expr2)
    print("Reduced motif:        ", res2, " =>  ", motif_to_pair(res2))
    print()

    # 3) rotate_xyz: (2, 5, 7) -> (5, 7, 2)
    print("=== rotate_xyz_closure: (2, 5, 7) -> (5, 7, 2) ===")
    triple = μ(n2, n5, n7)
    print("Original triple:      ", triple, " =>  ", motif_to_triple(triple))

    rot_cl = rotate_xyz_closure()
    expr3 = activate(rot_cl, triple)
    print("Activation motif:     ", expr3)

    res3 = ev.reduce(expr3)
    print("Reduced motif:        ", res3, " =>  ", motif_to_triple(res3))

from rcx_pi.programs import wrap_program, is_program_block, seq, PROGRAM_TAG, SEQ_TAG

if __name__ == "__main__":
    # ...existing tests...

    print()
    print("=== program block + seq structural sanity ===")
    swap_cl = swap_xy_closure()

    prog_swap = wrap_program(swap_cl)
    print("Program block motif:", prog_swap)
    print("is_program_block:", is_program_block(prog_swap))

    seq_prog = seq(swap_cl, swap_cl)
    print("Sequence motif:", seq_prog)
    # Very shallow structural checks:
    assert isinstance(seq_prog, Motif)
    assert len(seq_prog.structure) == 3
    assert seq_prog.structure[0] == SEQ_TAG

    print("[OK program algebra skeleton]")