#!/usr/bin/env python3
"""
RCX-π interactive REPL.

Tiny structural playground on top of:

    - μ, VOID, UNIT
    - PureEvaluator
    - num / motif_to_int
    - local motif_to_pair / motif_to_triple
    - high-level closures (swap, dup, rot, swapends)
    - meta classifier + pretty printer
"""

from __future__ import annotations

import sys
from typing import Optional

from rcx_pi import (
    μ,
    VOID,
    UNIT,
    PureEvaluator,
    num,
    motif_to_int,
)

from rcx_pi.core.motif import Motif

from rcx_pi.programs import (
    swap_xy_closure,
    dup_x_closure,
    rotate_xyz_closure,
    swap_ends_xyz_closure,
    activate,
)

from rcx_pi.meta import classify_motif
from rcx_pi.pretty import pretty_motif


# ---------------------------------------------------------------------
# Local helpers (mirroring tests/examples)
# ---------------------------------------------------------------------


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


def parse_nat(token: str) -> Optional[int]:
    """Parse a non-negative integer from a token, else None."""
    try:
        n = int(token)
    except ValueError:
        return None
    if n < 0:
        return None
    return n


def print_header() -> None:
    print("=== RCX-π REPL ===")
    print("Type 'help' for commands, 'quit' to exit.")


def print_help() -> None:
    print(
        """
Commands:

  help
    Show this help.

  quit | exit
    Leave the REPL.

  num N
    Build Peano number N.
      e.g. num 5

  pair A B
    Build a pair (A, B).
      e.g. pair 2 5

  triple A B C
    Build a triple (A, B, C).
      e.g. triple 2 5 7

  swap A B
    Use swap_xy_closure on (A, B) -> (B, A).

  dup A B
    Use dup_x_closure on (A, B) -> (A, A).

  rot A B C
    Use rotate_xyz_closure on (A, B, C) -> (B, C, A).

  swapends A B C
    Use swap_ends_xyz_closure on (A, B, C) -> (C, B, A).

  classify num N
  classify pair A B
  classify triple A B C
    Tag the motif structurally and print the meta label and pretty form.

Notes:
  • All numbers are Peano-encoded μ-terms internally.
  • pretty_motif() shows short tuple-style views when it can.
"""
    )


# ---------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------


def cmd_num(args, ev: PureEvaluator) -> None:
    if len(args) != 1:
        print("usage: num N")
        return
    n = parse_nat(args[0])
    if n is None:
        print("error: N must be a non-negative integer")
        return
    m = num(n)
    print("motif:", m)
    print("int:  ", motif_to_int(m))


def cmd_pair(args, ev: PureEvaluator) -> None:
    if len(args) != 2:
        print("usage: pair A B")
        return
    a = parse_nat(args[0])
    b = parse_nat(args[1])
    if a is None or b is None:
        print("error: A and B must be non-negative integers")
        return
    m = μ(num(a), num(b))
    print("motif:", m)
    print("pair: ", motif_to_pair(m))


def cmd_triple(args, ev: PureEvaluator) -> None:
    if len(args) != 3:
        print("usage: triple A B C")
        return
    ns = [parse_nat(t) for t in args]
    if any(n is None for n in ns):
        print("error: A, B, C must be non-negative integers")
        return
    a, b, c = ns  # type: ignore[misc]
    m = μ(num(a), num(b), num(c))
    print("motif:", m)
    print("triple:", motif_to_triple(m))


def _binary_closure(
    name: str,
    args,
    ev: PureEvaluator,
    closure_factory,
) -> None:
    if len(args) != 2:
        print(f"usage: {name} A B")
        return
    a = parse_nat(args[0])
    b = parse_nat(args[1])
    if a is None or b is None:
        print("error: A and B must be non-negative integers")
        return

    pair = μ(num(a), num(b))
    print("pair motif:    ", pair, " => ", motif_to_pair(pair))

    cl = closure_factory()
    expr = activate(cl, pair)
    print("activation raw:", expr)

    res = ev.reduce(expr)
    print("reduced:       ", res, " => ", motif_to_pair(res))


def _triple_closure(
    name: str,
    args,
    ev: PureEvaluator,
    closure_factory,
) -> None:
    if len(args) != 3:
        print(f"usage: {name} A B C")
        return
    ns = [parse_nat(t) for t in args]
    if any(n is None for n in ns):
        print("error: A, B, C must be non-negative integers")
        return
    a, b, c = ns  # type: ignore[misc]

    triple = μ(num(a), num(b), num(c))
    print("triple motif:  ", triple, " => ", motif_to_triple(triple))

    cl = closure_factory()
    expr = activate(cl, triple)
    print("activation raw:", expr)

    res = ev.reduce(expr)
    print("reduced:       ", res, " => ", motif_to_triple(res))


def cmd_swap(args, ev: PureEvaluator) -> None:
    _binary_closure("swap", args, ev, swap_xy_closure)


def cmd_dup(args, ev: PureEvaluator) -> None:
    _binary_closure("dup", args, ev, dup_x_closure)


def cmd_rot(args, ev: PureEvaluator) -> None:
    _triple_closure("rot", args, ev, rotate_xyz_closure)


def cmd_swapends(args, ev: PureEvaluator) -> None:
    _triple_closure("swapends", args, ev, swap_ends_xyz_closure)


def _build_motif_for_classify(kind: str, args) -> Optional[Motif]:
    """Support: classify num N / pair A B / triple A B C."""
    if kind == "num":
        if len(args) != 1:
            print("usage: classify num N")
            return None
        n = parse_nat(args[0])
        if n is None:
            print("error: N must be a non-negative integer")
            return None
        return num(n)

    if kind == "pair":
        if len(args) != 2:
            print("usage: classify pair A B")
            return None
        a = parse_nat(args[0])
        b = parse_nat(args[1])
        if a is None or b is None:
            print("error: A and B must be non-negative integers")
            return None
        return μ(num(a), num(b))

    if kind == "triple":
        if len(args) != 3:
            print("usage: classify triple A B C")
            return None
        ns = [parse_nat(t) for t in args]
        if any(n is None for n in ns):
            print("error: A, B, C must be non-negative integers")
            return None
        a, b, c = ns  # type: ignore[misc]
        return μ(num(a), num(b), num(c))

    print("usage: classify [num|pair|triple] ...")
    return None


def cmd_classify(args, ev: PureEvaluator) -> None:
    if not args:
        print("usage: classify [num|pair|triple] ...")
        return

    kind = args[0]
    motif = _build_motif_for_classify(kind, args[1:])
    if motif is None:
        return

    print("motif:   ", motif)

    tagged = classify_motif(motif)
    print("tagged:  ", tagged)
    print("pretty:  ", pretty_motif(tagged))


# ---------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------


def main(argv=None) -> int:
    ev = PureEvaluator()
    print_header()

    while True:
        try:
            line = input("rcx> ")
        except EOFError:
            print()
            break

        line = line.strip()
        if not line:
            continue

        if line in ("quit", "exit"):
            break

        if line == "help":
            print_help()
            continue

        parts = line.split()
        cmd, args = parts[0], parts[1:]

        if cmd == "num":
            cmd_num(args, ev)
        elif cmd == "pair":
            cmd_pair(args, ev)
        elif cmd == "triple":
            cmd_triple(args, ev)
        elif cmd == "swap":
            cmd_swap(args, ev)
        elif cmd == "dup":
            cmd_dup(args, ev)
        elif cmd == "rot":
            cmd_rot(args, ev)
        elif cmd == "swapends":
            cmd_swapends(args, ev)
        elif cmd == "classify":
            cmd_classify(args, ev)
        else:
            print(f"unknown command: {cmd!r} (try 'help')")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())