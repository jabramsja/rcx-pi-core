import pytest

pytest.skip(
    "Legacy projection API (.structure + pair_motif_to_ints) "
    "not wired to current RCX-π core yet.",
    allow_module_level=True,
)

# test_projection.py

from rcx_pi import μ, VOID, UNIT, PureEvaluator

# ---------- shared helpers (copied from test_numbers) ----------

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
    return None


def num(n: int):
    """Build Peano number n as nested successors over VOID."""
    m = VOID
    for _ in range(n):
        m = m.succ()
    return m


# ---------- RCX-π markers (must match rules/pattern matcher) ----------

# These depths mirror what you're already using in rules_pure / pattern_matching
CLOSURE_MARKER     = μ(μ(μ(μ(μ()))))                # 4-deep
ACTIVATION_MARKER  = μ(μ(μ(μ(μ(μ())))))             # 5-deep
PROJECTION_MARKER  = μ(μ(μ(μ(μ(μ(μ()))))))          # 6-deep
PATTERN_VAR_MARKER = μ(μ(μ(μ(μ(μ(μ(μ())))))))       # 7-deep


def var_x():
    """Pattern variable x (ID = VOID)."""
    return μ(PATTERN_VAR_MARKER, VOID)


def var_y():
    """Pattern variable y (ID = succ(VOID))."""
    return μ(PATTERN_VAR_MARKER, μ(VOID))


# ---------- swap closure (x, y) -> (y, x) ----------

def make_swap_closure():
    """
    Build a closure that, when activated on a pair (x, y),
    returns the pair (y, x), all in pure RCX-π structure.
    """

    # Pattern to match argument: (x, y)
    pattern = μ(var_x(), var_y())

    # Body: (y, x)
    body = μ(var_y(), var_x())

    # Projection: PROJECTION_MARKER, pattern, body
    projection = μ(PROJECTION_MARKER, pattern, body)

    # Closure: CLOSURE_MARKER, projection
    swap_closure = μ(CLOSURE_MARKER, projection)
    return swap_closure


def activate(func, arg):
    """Structural activation wrapper."""
    return μ(ACTIVATION_MARKER, func, arg)


def pair(a, b):
    """Just a 2-tuple as a motif."""
    return μ(a, b)


def pair_motif_to_ints(m):
    """Decode a pair of Peano motifs to Python ints (for display)."""
    left, right = m.structure
    return motif_to_int(left), motif_to_int(right)


# ---------- main test ----------

if __name__ == "__main__":
    ev = PureEvaluator()

    # Build Peano numbers
    a = num(2)
    b = num(5)

    # Build pair (2, 5)
    p = pair(a, b)

    # Build swap closure and activation
    swap = make_swap_closure()
    expr = activate(swap, p)

    print("=== RCX-π projection demo: swap (x, y) -> (y, x) ===")
    print("Original pair motif:  ", p, " => ", pair_motif_to_ints(p))
    print("Swap closure motif:   ", swap)
    print("Activation motif:     ", expr)

    result = ev.reduce(expr)

    print("\nReduced motif:        ", result)
    print("As ints (expect 5, 2):", pair_motif_to_ints(result))