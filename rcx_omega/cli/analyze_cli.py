"""
RCX-Ω analyze CLI (staging)

Consumes JSON from stdin (pipe-friendly) and prints a tiny analysis summary.
Accepts:
- trace-shaped payloads (has steps[])
- omega summary payloads (kind="omega", has classification/orbit)

Examples:
  python3 -m rcx_omega.cli.trace_cli --json void | python3 -m rcx_omega.cli.analyze_cli
  python3 -m rcx_omega.cli.omega_cli --json "μ(μ())" | python3 -m rcx_omega.cli.analyze_cli
  python3 -m rcx_omega.cli.omega_cli --json --trace "μ(μ())" | python3 -m rcx_omega.cli.analyze_cli
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def _read_text_from_file(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _read_text_from_stdin() -> str:
    return sys.stdin.read()


def _load_json(text: str) -> Dict[str, Any]:
    try:
        obj = json.loads(text)
    except Exception as e:
        raise SystemExit(f"analyze_cli: invalid JSON: {e}") from e
    if not isinstance(obj, dict):
        raise SystemExit("analyze_cli: JSON payload must be an object")
    return obj


def _detect_kind(payload: Dict[str, Any]) -> str:
    k = payload.get("kind")
    if isinstance(k, str) and k:
        return k
    if isinstance(payload.get("steps"), list):
        return "trace"
    if isinstance(payload.get("classification"), dict) or isinstance(payload.get("orbit"), list):
        return "omega"
    return "unknown"


def _safe_get_stats(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    s = payload.get("stats")
    return s if isinstance(s, dict) else None


def _trace_converged(payload: Dict[str, Any]) -> bool:
    inp = payload.get("input")
    res = payload.get("result")
    if inp is not None and res is not None and inp == res:
        return True

    steps = payload.get("steps")
    if isinstance(steps, list) and steps:
        last = steps[-1]
        if isinstance(last, dict):
            dn = last.get("delta_nodes")
            dd = last.get("delta_depth")
            if isinstance(dn, int) and isinstance(dd, int):
                return (dn == 0) and (dd == 0)

    return False


def _omega_classification_summary(payload: Dict[str, Any]) -> str:
    """
    Always returns a stable, test-friendly line starting with:
      classification: ...
    """
    c = payload.get("classification")
    if not isinstance(c, dict):
        return "classification: unknown"

    ctype = c.get("type")
    mu = c.get("mu")
    period = c.get("period")
    max_steps = c.get("max_steps")

    def fmt(v: Any) -> str:
        return "?" if v is None else str(v)

    if not isinstance(ctype, str) or not ctype:
        return "classification: unknown"

    if ctype == "fixed_point":
        return f"classification: fixed_point period={fmt(period)} max_steps={fmt(max_steps)}"
    if ctype == "limit_cycle":
        return f"classification: limit_cycle mu={fmt(mu)} period={fmt(period)} max_steps={fmt(max_steps)}"
    if ctype == "cutoff":
        return f"classification: cutoff max_steps={fmt(max_steps)}"

    return f"classification: {ctype} mu={fmt(mu)} period={fmt(period)} max_steps={fmt(max_steps)}"


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--stdin", action="store_true", help="Read JSON from stdin (default)")
    ap.add_argument("--file", type=str, default=None, help="Read JSON from file path")
    args = ap.parse_args(argv[1:])

    if args.stdin and args.file:
        print("analyze_cli: --stdin and --file are mutually exclusive", file=sys.stderr)
        return 2

    raw = _read_text_from_file(Path(args.file)) if args.file is not None else _read_text_from_stdin()
    payload = _load_json(raw)
    kind = _detect_kind(payload)

    if kind == "trace":
        steps = payload.get("steps")
        n_steps = len(steps) if isinstance(steps, list) else 0
        print("analyze: trace")
        print(f"steps: {n_steps}")
        stats = _safe_get_stats(payload)
        if stats is not None:
            print(f"stats: {stats}")
        print(f"converged: {'true' if _trace_converged(payload) else 'false'}")
        print("== Ω analyze ==")
        return 0

    if kind == "omega":
        print("analyze: summary")
        print(_omega_classification_summary(payload))
        stats = _safe_get_stats(payload)
        if stats is not None:
            print(f"stats: {stats}")
        print("== Ω analyze ==")
        return 0

    print("analyze: unknown")
    stats = _safe_get_stats(payload)
    if stats is not None:
        print(f"stats: {stats}")
    print("== Ω analyze ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
