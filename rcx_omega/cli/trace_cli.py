"""
RCX-Ω trace CLI (staging)
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List

from rcx_pi import new_evaluator, μ, VOID, UNIT
from rcx_omega.engine.lens import trace_reduce_with_stats


def parse_token(tok: str):
    t = tok.strip().lower()

    if t in ("void", "0"):
        return VOID
    if t in ("unit", "1"):
        return UNIT
    if t in ("mu", "μ", "mu()"):
        return μ()
    if t == "mu(mu())":
        return μ(μ())

    raise SystemExit(
        f"Unsupported motif literal: {tok!r}\n"
        "Supported: void, unit, mu, mu(mu())"
    )


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("motif")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-steps", type=int, default=64)
    args = parser.parse_args(argv[1:])

    ev = new_evaluator()
    x = parse_token(args.motif)
    lr = trace_reduce_with_stats(ev, x, max_steps=args.max_steps)

    if args.json:
        payload = {
            "input": str(x),
            "result": str(lr.trace.result),
            "steps": [
                {
                    "i": d.i,
                    "nodes": d.nodes,
                    "depth": d.depth,
                    "delta_nodes": d.delta_nodes,
                    "delta_depth": d.delta_depth,
                }
                for d in lr.stats.deltas
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    for d in lr.stats.deltas:
        print(
            f"{d.i:03d}: nodes={d.nodes:+d} depth={d.depth:+d} "
            f"(Δn={d.delta_nodes:+d}, Δd={d.delta_depth:+d})"
        )

    print(f"result: {lr.trace.result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
