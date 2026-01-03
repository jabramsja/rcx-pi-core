"""
RCX-Ω trace CLI (staging)

Usage:
  python3 -m rcx_omega.trace_cli void
  python3 -m rcx_omega.trace_cli unit
  python3 -m rcx_omega.trace_cli mu
  python3 -m rcx_omega.trace_cli "mu(mu())"

This is intentionally tiny and dumb: it's a debug lens.
"""

from __future__ import annotations

import sys
from typing import List

from rcx_pi import new_evaluator, μ, VOID, UNIT
from rcx_omega.trace import trace_reduce


def parse_token(tok: str):
    t = tok.strip().lower()

    if t in ("void", "0"):
        return VOID
    if t in ("unit", "1"):
        return UNIT
    if t in ("mu", "μ", "mu()"):
        return μ()

    # ultra-minimal parser for a few patterns:
    # "mu(mu())" -> μ(μ())
    if t == "mu(mu())":
        return μ(μ())

    raise SystemExit(
        f"Unsupported motif literal: {tok!r}\n"
        "Supported: void, unit, mu, mu(mu())"
    )


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip())
        return 2

    x = parse_token(argv[1])
    ev = new_evaluator()
    tr = trace_reduce(ev, x, max_steps=64)

    for s in tr.steps:
        print(f"{s.i:03d}: {s.value}")

    print(f"result: {tr.result}")
    print(f"steps:  {len(tr.steps)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
