"""
RCX-Ω trace CLI (staging)

Provides a simple debug lens around π:
- text mode: per-step deltas + result + steps count
- JSON mode: motif-shaped JSON + stats + per-step deltas

This is intentionally tiny and dumb: it's a debug lens.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List

from rcx_pi import new_evaluator, μ, VOID, UNIT
from rcx_omega.core.motif_codec import motif_to_json_obj
from rcx_omega.core import parse_motif
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

    # If it looks like a μ(...) expression, try the μ-only parser.
    if "(" in tok and (("μ" in tok) or ("mu" in tok.lower())):
        try:
            return parse_motif(tok)
        except ValueError as e:
            raise SystemExit(f"Invalid μ literal: {tok!r}\n{e}") from None

    raise SystemExit(
        f"Unsupported motif literal: {tok!r}\n"
        "Supported: void, unit, mu, mu(mu()), or any μ(...) tree like μ(μ())"
    )


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("motif")
    parser.add_argument("--json", action="store_true", help="Emit JSON payload")
    parser.add_argument("--max-steps", type=int, default=64, help="Trace cap")
    parser.add_argument("--stdin", action="store_true", help="Read motif literal from stdin")
    parser.add_argument("--file", type=str, default=None, help="Read motif literal from a file")
    args = parser.parse_args(argv[1:])

    ev = new_evaluator()
    # Input selection (positional | --stdin | --file)
    if args.stdin and args.file:
        raise SystemExit("Use only one of --stdin or --file")

    if args.file is not None:
        raw = Path(args.file).read_text(encoding="utf-8")
    elif args.stdin:
        raw = sys.stdin.read()
    else:
        if args.motif is None:
            raise SystemExit("Missing motif literal. Provide MOTIF, or use --stdin/--file.")
        raw = args.motif

    raw = raw.strip()
    if not raw:
        raise SystemExit("Empty motif literal")

    x = parse_token(raw)
    lr = trace_reduce_with_stats(ev, x, max_steps=args.max_steps)

    if args.json:
        payload = {
            "input": motif_to_json_obj(x),
            "result": motif_to_json_obj(lr.trace.result),
            "stats": {
                "input": {
                    "nodes": lr.stats.input_stats.nodes,
                    "depth": lr.stats.input_stats.depth,
                },
                "result": {
                    "nodes": lr.stats.result_stats.nodes,
                    "depth": lr.stats.result_stats.depth,
                },
            },
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
    print(f"steps:  {len(lr.stats.deltas)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
