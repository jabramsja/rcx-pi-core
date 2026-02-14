# example_numbers.py
#
# Tiny, focused demo of RCX-π Peano numbers + arithmetic.

from rcx_pi import μ, VOID, UNIT, PureEvaluator


# ---------- helpers ----------


def motif_to_int(m):
    """Convert Peano motif to Python int for readable output."""
    if m.is_zero_pure():
        return 0

    count = 0
    cur = m
    while cur.is_successor_pure():
        count += 1
        cur = cur.head()

    if cur.is_zero_pure():
        return count
    return None  # not a pure Peano number


def num(n: int):
    """Build Peano number n as nested successors over VOID."""
    m = VOID
    for _ in range(n):
        m = m.succ()
    return m


# ---------- main demo ----------

if __name__ == "__main__":
    ev = PureEvaluator()

    # 1) Show 2 and 5 as motifs
    two = num(2)
    five = num(5)

    print("=== RCX-π Peano numbers ===")
    print("2 as motif:  ", two, " => ", motif_to_int(two))
    print("5 as motif:  ", five, " => ", motif_to_int(five))

    # 2) pred(succ(0)) -> 0
    print("\n=== pred(succ(0)) ===")
    expr1 = num(0).succ().pred()
    print("Raw:      ", expr1)
    red1 = ev.reduce(expr1)
    print("Reduced:  ", red1, " => ", motif_to_int(red1))

    # 3) 2 + 3 using structural Motif.add
    print("\n=== 2 + 3 (structural add) ===")
    expr2 = two.add(num(3))
    print("Raw:      ", expr2)
    red2 = ev.reduce(expr2)
    print("Reduced:  ", red2, " => ", motif_to_int(red2))

    # 4) 2 * 3 using structural Motif.mult
    print("\n=== 2 * 3 (structural mult) ===")
    expr3 = two.mult(num(3))
    print("Raw:      ", expr3)
    red3 = ev.reduce(expr3)
    print("Reduced:  ", red3, " => ", motif_to_int(red3))
