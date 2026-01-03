"""
RCX-Ω trace CLI (staging)

Usage:
  python3 -m rcx_omega.trace_cli void
  python3 -m rcx_omega.trace_cli unit
  python3 -m rcx_omega.trace_cli mu
  python3 -m rcx_omega.trace_cli "mu(mu())"

JSON mode:
  python3 -m rcx_omega.trace_cli --json void
  python3 -m rcx_omega.trace_cli --json --max-steps 16 "mu(mu())"

This is intentionally tiny and dumb: it's a debug lens.
"""

from __future__ import annotations

import argparse
import json
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
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("motif", help="Motif literal: void|unit|mu|mu(mu())")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    parser.add_argument("--max-steps", type=int, default=64, help="Trace cap")
    args = parser.parse_args(argv[1:])

    x = parse_token(args.motif)
    ev = new_evaluator()
    tr = trace_reduce(ev, x, max_steps=args.max_steps)

    if args.json:
        payload = {
            "input": str(x),
            "result": str(tr.result),
            "steps": [{"i": s.i, "value": str(s.value)} for s in tr.steps],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    for s in tr.steps:
        print(f"{s.i:03d}: {s.value}")

    print(f"result: {tr.result}")
    print(f"steps:  {len(tr.steps)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
