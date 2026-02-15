"""
RCX-Ω trace CLI (staging)

Key rule: CLI derives per-step stats from motifs, not from TraceStep fields.
That keeps Ω stable even if the engine's internal TraceStep shape changes.

Examples:
  python3 -m rcx_omega.cli.trace_cli void
  python3 -m rcx_omega.cli.trace_cli --json void
  echo "μ(μ(), μ(μ()))" | python3 -m rcx_omega.cli.trace_cli --json --stdin
  python3 -m rcx_omega.cli.trace_cli --json --file motif.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

from rcx_pi import new_evaluator, μ, VOID, UNIT
from rcx_pi.core.motif import Motif

from rcx_omega.engine.trace import trace_reduce
from rcx_omega.core.motif_codec import motif_to_json_obj
from rcx_omega.json_versioning import maybe_add_schema_fields


def _motif_children(x: Motif) -> Tuple[Motif, ...]:
    # π Motif exposes .structure (tuple of children)
    try:
        s = getattr(x, "structure")
        if isinstance(s, tuple):
            return tuple(s)
    except Exception:
        pass
    return ()


def _motif_depth(x: Motif) -> int:
    kids = _motif_children(x)
    if not kids:
        return 1
    return 1 + max(_motif_depth(k) for k in kids)


def _read_text_file(p: str) -> str:
    return Path(p).read_text(encoding="utf-8").strip()


def _read_stdin() -> str:
    return sys.stdin.read().strip()


def _parse_simple_atom(tok: str) -> Motif:
    t = tok.strip()
    tl = t.lower()

    if tl in ("void", "0"):
        return VOID
    if tl in ("unit", "1"):
        return UNIT
    if tl in ("mu", "μ", "mu()", "μ()"):
        return μ()

    raise ValueError(f"Unsupported atom literal: {tok!r}")


def _split_top_level_commas(s: str) -> List[str]:
    parts: List[str] = []
    depth = 0
    start = 0
    for i, ch in enumerate(s):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(s[start:i].strip())
            start = i + 1
    tail = s[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def parse_motif_expr(expr: str) -> Motif:
    """
    Minimal parser for:
      - atoms: void, unit, mu, μ(), 0, 1
      - μ(...) / mu(...)
    """
    s = expr.strip()
    if not s:
        raise ValueError("Empty motif expression")

    if s.startswith("mu"):
        s = "μ" + s[2:]

    if s == "μ()":
        return μ()

    if s.startswith("μ(") and s.endswith(")"):
        inner = s[2:-1].strip()
        if inner == "":
            return μ()
        args = _split_top_level_commas(inner)
        kids = [parse_motif_expr(a) for a in args]
        return μ(*kids)

    return _parse_simple_atom(s)


def _step_motif(step: Any) -> Optional[Motif]:
    """
    Trace engine may change TraceStep shape over time.
    We try a few common attribute names and only accept Motif instances.
    """
    for name in (
        "motif",
        "state",
        "value",
        "node",
        "expr",
        "x",
        "current",
        "result",
        "out",
    ):
        try:
            v = getattr(step, name)
        except Exception:
            continue
        if isinstance(v, Motif):
            return v
    return None


def _iter_steps(tr: Any) -> List[Any]:
    steps = getattr(tr, "steps", None)
    if isinstance(steps, list):
        return steps
    if isinstance(steps, tuple):
        return list(steps)
    if steps is None:
        return []
    if isinstance(steps, Iterable):
        return list(steps)
    return []


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("motif", nargs="?", help="Motif literal/expression")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    parser.add_argument("--max-steps", type=int, default=64, help="Trace cap")
    parser.add_argument("--stdin", action="store_true", help="Read motif from stdin")
    parser.add_argument("--file", type=str, default=None, help="Read motif from file")
    args = parser.parse_args(argv[1:])

    if args.stdin and args.file:
        print("error: --stdin and --file are mutually exclusive", file=sys.stderr)
        return 2

    if args.stdin:
        raw = _read_stdin()
    elif args.file is not None:
        raw = _read_text_file(args.file)
    else:
        if args.motif is None:
            parser.error("the following arguments are required: motif")
        raw = args.motif

    x = parse_motif_expr(raw)
    ev = new_evaluator()
    tr = trace_reduce(ev, x, max_steps=args.max_steps)

    steps = _iter_steps(tr)

    # Derive per-step metrics from motifs (do NOT assume TraceStep has nodes/depth)
    derived_steps = []
    prev_nodes = None
    prev_depth = None

    for idx, s in enumerate(steps):
        m = _step_motif(s) or x  # fallback: at least something motif-shaped
        nodes = m.count_nodes()
        depth = _motif_depth(m)
        delta_nodes = 0 if prev_nodes is None else nodes - prev_nodes
        delta_depth = 0 if prev_depth is None else depth - prev_depth
        i = getattr(s, "i", idx)

        derived_steps.append(
            {
                "i": int(i),
                "nodes": int(nodes),
                "depth": int(depth),
                "delta_nodes": int(delta_nodes),
                "delta_depth": int(delta_depth),
            }
        )
        prev_nodes, prev_depth = nodes, depth

    # Stats for input/result
    in_nodes = x.count_nodes()
    in_depth = _motif_depth(x)
    result_motif = getattr(tr, "result", x)
    if not isinstance(result_motif, Motif):
        result_motif = x
    out_nodes = result_motif.count_nodes()
    out_depth = _motif_depth(result_motif)

    if args.json:
        payload = {
            "input": motif_to_json_obj(x, include_meta=False),
            "result": motif_to_json_obj(result_motif, include_meta=False),
            "stats": {
                "input": {"nodes": in_nodes, "depth": in_depth},
                "result": {"nodes": out_nodes, "depth": out_depth},
            },
            "steps": derived_steps
            if derived_steps
            else [
                {
                    "i": 0,
                    "nodes": in_nodes,
                    "depth": in_depth,
                    "delta_nodes": 0,
                    "delta_depth": 0,
                }
            ],
        }
        print(
            json.dumps(
                maybe_add_schema_fields(payload, kind="trace"), indent=2, sort_keys=True
            )
        )
        return 0

    # Human output (tests expect "result:" and "steps:")
    for s in (
        derived_steps
        if derived_steps
        else [
            {
                "i": 0,
                "nodes": in_nodes,
                "depth": in_depth,
                "delta_nodes": 0,
                "delta_depth": 0,
            }
        ]
    ):
        print(
            f"{s['i']:03d}: nodes={s['nodes']:+d} depth={s['depth']:+d} "
            f"(Δn={s['delta_nodes']:+d}, Δd={s['delta_depth']:+d})"
        )
    print(f"result: {result_motif}")
    print(f"steps:  {len(derived_steps) if derived_steps else 1}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
