# test_combinators.py
#
# RCX-π combinator sanity checks:
#   I n   -> n
#   K a b -> a
#
# Assumes package layout:
#   WorkingRCX/
#       test_numbers.py
#       test_combinators.py
#       rcx_pi/
#           __init__.py
#           core/motif.py
#           engine/evaluator_pure.py
#           reduction/rules_pure.py
#           utils/compression.py
#           ...

from rcx_pi import μ, VOID, UNIT, PureEvaluator

# ---------- helpers (same style as test_numbers.py) ----------


def motif_to_int(m):
    """Convert Peano motif to Python int for readable output."""
    if not hasattr(m, "is_zero_pure"):
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


def num(n: int):
    """Build Peano number n as nested successors over VOID."""
    m = VOID
    for _ in range(n):
        m = m.succ()
    return m


# ---------- RCX-π markers (must match rules_pure / pattern_matching) ----

# These encodings mirror the versions in your uploaded RCX-π rules /
# pattern matcher.

# Structural markers
CLOSURE_MARKER = μ(μ(μ(μ(μ()))))              # 4-deep in that file
ACTIVATION_MARKER = μ(μ(μ(μ(μ(μ())))))          # 5-deep
PROJECTION_MARKER = μ(μ(μ(μ(μ(μ(μ()))))))       # 6/7-deep as used there

# Pattern-variable marker (used to tag "x", "y", etc. as bindable)
PATTERN_VAR_MARKER = μ(μ(μ(μ(μ(μ(μ(μ())))))))    # 7/8-deep in that file


def var_x():
    """Pattern variable 'x' structurally."""
    # In the big RCX-π version: pattern vars are μ(PATTERN_VAR_MARKER, <id>)
    return μ(PATTERN_VAR_MARKER, VOID)


def var_y():
    """Pattern variable 'y' structurally."""
    # y is just a different structural id; use UNIT to distinguish
    return μ(PATTERN_VAR_MARKER, UNIT)


# ---------- Combinator encodings (copied from your RCX-π spec) ----------

def make_I():
    """
    Identity combinator I:

    In the big PureRuleEngine:
        var_x = μ(VOID)
        proj  = μ(PROJECTION_MARKER, var_x, var_x)
        I     = μ(CLOSURE_MARKER, proj)

    We reproduce that here structurally.
    """
    x = var_x()
    proj = μ(PROJECTION_MARKER, x, x)
    return μ(CLOSURE_MARKER, proj)


def make_K():
    """
    Constant combinator K:

    In the big PureRuleEngine:
        var_x = μ(VOID)
        var_y = μ(μ(VOID))
        inner_proj = μ(PROJECTION_MARKER, var_y, var_x)
        inner      = μ(CLOSURE_MARKER, inner_proj)
        outer_proj = μ(PROJECTION_MARKER, var_x, inner)
        K          = μ(CLOSURE_MARKER, outer_proj)

    Structurally: K takes two args and returns the first.
    """
    x = var_x()
    y = var_y()
    inner_proj = μ(PROJECTION_MARKER, y, x)
    inner_closure = μ(CLOSURE_MARKER, inner_proj)
    outer_proj = μ(PROJECTION_MARKER, x, inner_closure)
    return μ(CLOSURE_MARKER, outer_proj)


def activate(func, arg):
    """RCX-π activation node: (func * arg)."""
    return μ(ACTIVATION_MARKER, func, arg)


# ---------- main tests ----------

if __name__ == "__main__":
    ev = PureEvaluator()

    # ----- 1. Identity combinator I -----
    print("=== Identity combinator I ===")
    I = make_I()
    n = num(4)

    expr_I = activate(I, n)
    print("Raw I:", I)
    print("Arg n:", n, " => ", motif_to_int(n))

    reduced_I = ev.reduce(expr_I)
    print("I n raw:", expr_I)
    print("I n reduced:", reduced_I, " => ", motif_to_int(reduced_I))
    print()

    # ----- 2. Constant combinator K -----
    print("=== Constant combinator K ===")
    K = make_K()
    a = num(2)
    b = num(9)

    print("Raw K:", K)
    print("a:", a, " => ", motif_to_int(a))
    print("b:", b, " => ", motif_to_int(b))

    # First application: K a
    Ka = ev.reduce(activate(K, a))
    print("\nAfter first application (K a):")
    print("Raw:", activate(K, a))
    print("Reduced:", Ka)

    # Second application: (K a) b
    Kab = ev.reduce(activate(Ka, b))
    print("\nSecond application (K a) b:")
    print("Raw:", activate(Ka, b))
    print("Reduced:", Kab, " => ", motif_to_int(Kab))

    print("\nExpectation:")
    print("  I n   should behave like n  (4)")
    print("  K a b should behave like a  (2)")
