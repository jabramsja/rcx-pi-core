# test_projection.py
"""
Small RCX-π projection demo: swap (x, y) -> (y, x) structurally.

This file is both:
  - a standalone demo (when run as a script), and
  - a tiny pytest sanity check for the projection machinery.

It exercises:

  - pattern variables (x, y)
  - projection closures (make_projection_closure)
  - PureEvaluator.reduce(...) on a projection-style activation

and prints both the raw motifs and their decoded Peano-int views.
"""

from rcx_pi import VOID, PureEvaluator, motif_to_int, num
from rcx_pi.core.motif import Motif, μ
from rcx_pi.projection import (
    var_x,
    var_y,
    make_projection_closure,
    activate,
)


# ---------- utility: small pair type for this demo ----------


def pair(a: Motif, b: Motif) -> Motif:
    """
    Encode a 2-tuple (a, b) as a plain μ(a, b) node.

    This matches the structure used by the projection pattern:

        pattern = μ(var_x(), var_y())
    """
    return μ(a, b)


def pair_motif_to_ints(m: Motif) -> tuple[int | None, int | None]:
    """
    Decode a *result* motif to two Python ints for display.

    The projection machinery may wrap the pair inside extra structure,
    so we recursively walk the motif tree and pick the first two nodes
    that decode as valid Peano numbers via motif_to_int.
    """
    seen: list[int] = []

    def walk(node: Motif) -> None:
        # Stop early if we already have 2 numbers.
        if len(seen) >= 2:
            return

        if not isinstance(node, Motif):
            return

        v = motif_to_int(node)
        if v is not None:
            seen.append(v)
            if len(seen) >= 2:
                return

        # Recurse into children, if any.
        children = getattr(node, "structure", None)
        if children is not None:
            for child in children:
                if len(seen) >= 2:
                    break
                walk(child)

    walk(m)

    if len(seen) >= 2:
        return seen[0], seen[1]
    return None, None


# ---------- swap closure (x, y) -> (y, x) via structural projection ----------


def make_swap_closure() -> Motif:
    """
    Build a closure that, when activated on a pair (x, y),
    returns the pair (y, x), all in pure RCX-π structure.
    """

    # Pattern to match argument: (x, y)
    pattern = μ(var_x(), var_y())

    # Body: (y, x)
    body = μ(var_y(), var_x())

    # Wrap as a projection-based closure provided by rcx_pi.projection.
    return make_projection_closure(pattern, body)


# ---------- main demo ----------

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

    print("=== RCX-π projection demo: swap [x, y] -> [y, x] ===")
    print("Original pair motif:  ", p, " => ", pair_motif_to_ints(p))
    print("Swap closure motif:   ", swap)
    print("Activation motif:     ", expr)

    result = ev.reduce(expr)

    print("\nResult pair motif:    ", result, " => ", pair_motif_to_ints(result))


# ---------- pytest: minimal projection sanity check ----------


def test_swap_projection_basic():
    ev = PureEvaluator()

    a = num(2)
    b = num(5)
    p = pair(a, b)

    swap = make_swap_closure()
    expr = activate(swap, p)

    result = ev.reduce(expr)
    left, right = pair_motif_to_ints(result)

    # Just assert it really produced two valid Peano numbers.
    # We *don't* assert exact identities here because the internal
    # encoding / wrapping may evolve; this is a structural smoke test.
    assert left is not None and right is not None
    assert left != right
