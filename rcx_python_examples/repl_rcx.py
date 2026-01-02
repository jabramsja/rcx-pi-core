# repl_rcx.py
"""
Tiny RCX-π REPL on top of the core engine.

Commands (all structural, no cheating):
  num N            -> Peano number N
  pair a b         -> (a, b)
  swap a b         -> swap (a, b) -> (b, a) via closure
  rot a b c        -> rotate (a, b, c) -> (b, c, a)
  classify num N   -> meta-tagged Peano N
  classify pair a b
  pretty num N     -> pretty-print Peano N
  pretty pair a b  -> pretty-print pair with meta tag
  safe num N       -> self-host safety check on a value
  safe pair a b    -> self-host safety check on a structural pair

Type 'help' to see this summary again, 'quit' to exit.
"""

from __future__ import annotations

import sys
from typing import Optional, Tuple

from rcx_pi import (
    μ,
    VOID,
    PureEvaluator,
    num,
    motif_to_int,
    pretty_motif,
    classify_motif,
)
from rcx_pi.core.motif import Motif

from rcx_pi.programs import (
    swap_xy_closure,
    dup_x_closure,
    rotate_xyz_closure,
    activate,
)
from rcx_pi.self_host import (
    is_pure_peano,
    is_structurally_pure,
    is_meta_tagged,
    is_self_host_value,
    is_self_host_safe,
)


# --- small structural helpers ------------------------------------------------


def motif_to_pair(m: Motif) -> Optional[Tuple[int, int]]:
    """Assume μ(a, b) where a, b are Peano; decode to (int, int)."""
    if not isinstance(m, Motif) or len(m.structure) != 2:
        return None
    a, b = m.structure
    return motif_to_int(a), motif_to_int(b)


def motif_to_triple(m: Motif) -> Optional[Tuple[int, int, int]]:
    """Assume μ(a, b, c) where a, b, c are Peano; decode to (int, int, int)."""
    if not isinstance(m, Motif) or len(m.structure) != 3:
        return None
    a, b, c = m.structure
    return motif_to_int(a), motif_to_int(b), motif_to_int(c)


# --- command handlers --------------------------------------------------------


def cmd_num(ev: PureEvaluator, args):
    if len(args) != 1:
        print("usage: num N")
        return
    try:
        n = int(args[0])
    except ValueError:
        print("N must be an int")
        return

    m = num(n)
    print("motif:", m)
    print("int:  ", motif_to_int(m))


def cmd_pair(ev: PureEvaluator, args):
    if len(args) != 2:
        print("usage: pair A B")
        return
    try:
        a = int(args[0])
        b = int(args[1])
    except ValueError:
        print("A, B must be ints")
        return

    m = μ(num(a), num(b))
    print("motif:", m)
    print("pair: ", motif_to_pair(m))


def cmd_swap(ev: PureEvaluator, args):
    if len(args) != 2:
        print("usage: swap A B")
        return
    try:
        a = int(args[0])
        b = int(args[1])
    except ValueError:
        print("A, B must be ints")
        return

    pair = μ(num(a), num(b))
    swap_cl = swap_xy_closure()

    # Use the same activation shape as example_rcx / test_programs
    expr = activate(swap_cl, pair)

    print("pair motif:    ", pair, " => ", motif_to_pair(pair))
    print("activation raw:", expr)

    # PureEvaluator.reduce does not take max_steps as a keyword
    res = ev.reduce(expr)

    decoded = motif_to_pair(res)
    if decoded is not None:
        print("reduced:       ", res, " => ", decoded)
    else:
        print("reduced:       ", res)


def cmd_rot(ev: PureEvaluator, args):
    if len(args) != 3:
        print("usage: rot A B C")
        return
    try:
        a = int(args[0])
        b = int(args[1])
        c = int(args[2])
    except ValueError:
        print("A, B, C must be ints")
        return

    triple = μ(num(a), num(b), num(c))
    rot_cl = rotate_xyz_closure()

    # Same activation helper as tests
    expr = activate(rot_cl, triple)

    print("triple motif:  ", triple, " => ", motif_to_triple(triple))
    print("activation raw:", expr)

    res = ev.reduce(expr)

    decoded = motif_to_triple(res)
    if decoded is not None:
        print("reduced:       ", res, " => ", decoded)
    else:
        print("reduced:       ", res)


def cmd_classify(ev: PureEvaluator, args):
    if not args:
        print("usage: classify num N | classify pair A B")
        return

    kind = args[0]

    if kind == "num":
        if len(args) != 2:
            print("usage: classify num N")
            return
        try:
            n = int(args[1])
        except ValueError:
            print("N must be an int")
            return

        v = num(n)
        tagged = classify_motif(v)
        print("motif:   ", v)
        print("tagged:  ", tagged)
        print("pretty:  ", pretty_motif(tagged))
        print("is_meta_tagged(tagged):", is_meta_tagged(tagged))
        print("is_self_host_safe(tagged):", is_self_host_safe(tagged))

    elif kind == "pair":
        if len(args) != 3:
            print("usage: classify pair A B")
            return
        try:
            a = int(args[1])
            b = int(args[2])
        except ValueError:
            print("A, B must be ints")
            return

        pair = μ(num(a), num(b))
        tagged = classify_motif(pair)
        print("motif:   ", pair)
        print("tagged:  ", tagged)
        print("pretty:  ", pretty_motif(tagged))
        print("is_meta_tagged(tagged):", is_meta_tagged(tagged))
        print("is_self_host_safe(tagged):", is_self_host_safe(tagged))

    else:
        print("unknown classify kind:", kind)
        print("usage: classify num N | classify pair A B")


def cmd_pretty(ev: PureEvaluator, args):
    if not args:
        print("usage: pretty num N | pretty pair A B")
        return

    kind = args[0]

    if kind == "num":
        if len(args) != 2:
            print("usage: pretty num N")
            return
        try:
            n = int(args[1])
        except ValueError:
            print("N must be an int")
            return

        v = num(n)
        print("motif: ", v)
        print("pretty:", pretty_motif(v))

    elif kind == "pair":
        if len(args) != 3:
            print("usage: pretty pair A B")
            return
        try:
            a = int(args[1])
            b = int(args[2])
        except ValueError:
            print("A, B must be ints")
            return

        pair = μ(num(a), num(b))
        tagged = classify_motif(pair)
        print("motif:  ", pair)
        print("tagged: ", tagged)
        print("pretty:", pretty_motif(tagged))

    else:
        print("unknown pretty kind:", kind)
        print("usage: pretty num N | pretty pair A B")


def cmd_safe(ev: PureEvaluator, args):
    """
    Self-host safety probe:

      safe num N
      safe pair A B
    """
    if not args:
        print("usage: safe num N | safe pair A B")
        return

    kind = args[0]

    if kind == "num":
        if len(args) != 2:
            print("usage: safe num N")
            return
        try:
            n = int(args[1])
        except ValueError:
            print("N must be an int")
            return

        v = num(n)
        print("v:", v)
        print("is_pure_peano(v):         ", is_pure_peano(v))
        print("is_structurally_pure(v):  ", is_structurally_pure(v))
        print("is_self_host_value(v):    ", is_self_host_value(v))
        print("is_self_host_safe(v):     ", is_self_host_safe(v))

    elif kind == "pair":
        if len(args) != 3:
            print("usage: safe pair A B")
            return
        try:
            a = int(args[1])
            b = int(args[2])
        except ValueError:
            print("A, B must be ints")
            return

        pair = μ(num(a), num(b))
        print("pair:", pair)
        print("is_pure_peano(pair):        ", is_pure_peano(pair))
        print("is_structurally_pure(pair): ", is_structurally_pure(pair))
        print("is_self_host_value(pair):   ", is_self_host_value(pair))
        print("is_self_host_safe(pair):    ", is_self_host_safe(pair))

    else:
        print("unknown safe kind:", kind)
        print("usage: safe num N | safe pair A B")


def cmd_help():
    print(__doc__)


# --- main loop ----------------------------------------------------------


def main():
    ev = PureEvaluator()
    print("=== RCX-π REPL ===")
    print("Type 'help' for commands, 'quit' to exit.")

    while True:
        try:
            line = input("rcx> ").strip()
        except EOFError:
            print()
            break

        if not line:
            continue
        if line in ("quit", "exit"):
            break
        if line == "help":
            cmd_help()
            continue

        parts = line.split()
        cmd, args = parts[0], parts[1:]

        if cmd == "num":
            cmd_num(ev, args)
        elif cmd == "pair":
            cmd_pair(ev, args)
        elif cmd == "swap":
            cmd_swap(ev, args)
        elif cmd == "rot":
            cmd_rot(ev, args)
        elif cmd == "classify":
            cmd_classify(ev, args)
        elif cmd == "pretty":
            cmd_pretty(ev, args)
        elif cmd == "safe":
            cmd_safe(ev, args)
        else:
            print("unknown command:", cmd)
            print("Type 'help' for usage.")


if __name__ == "__main__":
    main()
