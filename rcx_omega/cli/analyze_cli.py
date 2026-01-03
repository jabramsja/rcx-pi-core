"""
RCX-Ω analyze CLI (staging)

This is a tiny post-processor for trace output. It intentionally does NOT
depend on π internals beyond string forms. The goal is stable observability.

Usage:
  python3 -m rcx_omega.cli.analyze_cli --help

Common:
  python3 -m rcx_omega.cli.trace_cli --json void | python3 -m rcx_omega.cli.analyze_cli
  python3 -m rcx_omega.cli.trace_cli --json --max-steps 32 "mu(mu())" | python3 -m rcx_omega.cli.analyze_cli

Output:
  - steps, first, last
  - whether it converged (last == result)
  - a tiny "signature" of the last motif (node count from π if parseable, else len(str))
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class AnalyzeReport:
    steps: int
    input: str
    result: str
    first: str
    last: str
    converged: bool
    last_size_hint: int


def _size_hint(s: str) -> int:
    # Prefer a structural metric if we can cheaply get one, otherwise string length.
    # We keep this Ω-only: best-effort, never required.
    try:
        # Minimal parser for π motif string forms would be heavier; for now:
        # count occurrences of "μ" as a rough proxy for structure size.
        return s.count("μ") + 1
    except Exception:
        return len(s)


def analyze_trace_payload(payload: Dict[str, Any]) -> AnalyzeReport:
    steps: List[Dict[str, Any]] = payload.get("steps") or []

    if not steps:
        # Allow analyzing omega_cli JSON, which is summary-shaped and may not include steps[].
        classification = payload.get("classification")
        stats = payload.get("stats")
        if classification or stats:
            # Emit something stable-ish for piping / smoke tests.
            print("analyze: summary")
            if classification:
                ctype = classification.get("type", "unknown")
                period = classification.get("period")
                max_steps = classification.get("max_steps")
                extra = []
                if period is not None:
                    extra.append(f"period={period}")
                if max_steps is not None:
                    extra.append(f"max_steps={max_steps}")
                tail = (" " + " ".join(extra)) if extra else ""
                print(f"classification: {ctype}{tail}")
            if stats:
                # stats shape varies; print compactly without assuming keys.
                print("stats: " + str(stats))
            raise SystemExit(0)
        sys.stderr.write("analyze_cli: payload had no steps[]\n")
        return 1

    input_s = str(payload.get("input", ""))
    result_s = str(payload.get("result", ""))
    first_s = str(steps[0].get("value", ""))
    last_s = str(steps[-1].get("value", ""))

    return AnalyzeReport(
        steps=len(steps),
        input=input_s,
        result=result_s,
        first=first_s,
        last=last_s,
        converged=(last_s == result_s),
        last_size_hint=_size_hint(last_s),
    )


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the parsed JSON (debug)",
    )
    args = ap.parse_args(argv[1:])

    raw = sys.stdin.read()
    if not raw.strip():
        raise SystemExit("analyze_cli: expected JSON on stdin")

    payload = json.loads(raw)

    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))

    rep = analyze_trace_payload(payload)

    print("== Ω analyze ==")
    print(f"steps:      {rep.steps}")
    print(f"input:      {rep.input}")
    print(f"first:      {rep.first}")
    print(f"last:       {rep.last}")
    print(f"result:     {rep.result}")
    print(f"converged:  {rep.converged}")
    print(f"size_hint:  {rep.last_size_hint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
