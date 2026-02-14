# test_numbers.py

from rcx_pi import μ, VOID, UNIT, PureEvaluator

# ---------- helpers ----------


def motif_to_int(m):
    """Convert Peano motif to Python int for readable output."""
    # Zero = VOID = μ()
    if m.is_zero_pure():
        return 0

    count = 0
    cur = m
    while cur.is_successor_pure():
        count += 1
        cur = cur.head()

    # If it bottoms out cleanly at zero, return the count
    if cur.is_zero_pure():
        return count

    # Otherwise it's not a pure number
    return None


def num(n: int):
    """Build Peano number n as nested successors over VOID."""
    m = VOID
    for _ in range(n):
        m = m.succ()
    return m


# Markers must match what rules_pure expects structurally
ADD_MARKER = μ(μ(), μ())  # two voids
MULT_MARKER = μ(μ(), μ(), μ())  # three voids


def add_pattern(a, b):
    """Encode a + b as RCX-π add pattern."""
    return μ(ADD_MARKER, a, b)


def mult_pattern(a, b):
    """Encode a * b as RCX-π mult pattern."""
    return μ(MULT_MARKER, a, b)


def fact_peano(n: int):
    """Compute n! as a pure Peano motif (no RCX-π markers)."""
    if n == 0:
        return num(1)
    result = num(1)
    for k in range(1, n + 1):
        result = result.mult(num(k))
    return result


# ---------- main tests ----------

if __name__ == "__main__":
    ev = PureEvaluator()

    # ----- 1. pred(succ(0)) -----
    print("=== pred(succ(0)) (direct) ===")
    expr1 = num(0).succ().pred()
    print("Raw:       ", expr1)
    red1 = ev.reduce(expr1)
    print("Reduced:   ", red1, " => ", motif_to_int(red1))

    # ----- 2. 2 + 3 using Motif.add (direct structural) -----
    print("\n=== 2 + 3 (direct Motif.add) ===")
    expr2 = num(2).add(num(3))
    print("Raw:       ", expr2)
    red2 = ev.reduce(expr2)
    print("Reduced:   ", red2, " => ", motif_to_int(red2))

    # ----- 3. 2 + 3 via RCX-π add-pattern -----
    print("\n=== 2 + 3 via RCX-π add-pattern ===")
    a = num(2)
    b = num(3)
    expr3 = add_pattern(a, b)
    print("Raw pattern:", expr3)
    red3 = ev.reduce(expr3)
    print("Reduced:    ", red3, " => ", motif_to_int(red3))

    # ----- 4. 2 * 3 via RCX-π mult-pattern -----
    print("\n=== 2 * 3 via RCX-π mult-pattern ===")
    expr4 = mult_pattern(a, b)
    print("Raw pattern:", expr4)
    red4 = ev.reduce(expr4)
    print("Reduced:    ", red4, " => ", motif_to_int(red4))

    # ----- 5. 4! via nested RCX-π mult-patterns (structural) -----
    print("\n=== 4! via nested RCX-π mult-patterns (RCX-π structural) ===")
    n1 = num(1)
    n2 = num(2)
    n3 = num(3)
    n4 = num(4)

    # 4! = 4 * 3 * 2 * 1, encoded as nested mult-patterns
    fact4_rcx = mult_pattern(n4, mult_pattern(n3, mult_pattern(n2, n1)))

    print("Raw factorial motif:")
    print("   ", fact4_rcx)

    fact4_rcx_reduced = ev.reduce(fact4_rcx)
    print("Reduced motif (RCX-π form):")
    print("   ", fact4_rcx_reduced)
    print("motif_to_int:", motif_to_int(fact4_rcx_reduced))

    # ----- 6. 4! via pure Peano arithmetic -----
    print("\n=== 4! via pure Peano arithmetic ===")
    fact4_peano = fact_peano(4)
    print("Raw Peano motif:   ", fact4_peano)
    fact4_peano_red = ev.reduce(fact4_peano)
    print("Reduced Peano:     ", fact4_peano_red, " => ", motif_to_int(fact4_peano_red))
