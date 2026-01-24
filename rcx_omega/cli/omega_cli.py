"""
RCX-Ω omega CLI (staging)

Examples:
  python3 -m rcx_omega.cli.omega_cli --json "μ(μ(), μ(μ()))"
  echo "μ(μ())" | python3 -m rcx_omega.cli.omega_cli --json --stdin
  python3 -m rcx_omega.cli.omega_cli --json --file motif.txt

Trace-shaped JSON (adds steps[] with deltas; still includes omega classification/orbit):
  python3 -m rcx_omega.cli.omega_cli --json --trace "μ(μ(), μ(μ()))" | \
    python3 -m rcx_omega.cli.analyze_cli

Notes:
- JSON output is pipe-friendly (intended for analyze_cli).
- Non-JSON mode prints a tiny orbit summary.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from rcx_omega.core.motif_parser import parse_motif
from rcx_omega.core.omega_runner import omega_run_to_json, run_omega
from rcx_omega.json_versioning import maybe_add_schema_fields


def _read_text_from_file(p: Path) -> str:
    return p.read_text(encoding="utf-8").strip()


def _read_text_from_stdin() -> str:
    return sys.stdin.read().strip()


def _resolve_input(
    motif_arg: Optional[str], *, use_stdin: bool, file_path: Optional[str]
) -> str:
    sources = sum([1 if use_stdin else 0, 1 if file_path else 0, 1 if motif_arg else 0])
    if sources != 1:
        raise SystemExit("Provide exactly one input source: motif OR --stdin OR --file")

    if motif_arg:
        return motif_arg.strip()
    if use_stdin:
        return _read_text_from_stdin()
    assert file_path is not None
    return _read_text_from_file(Path(file_path))


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("motif", nargs="?", help="Motif text, e.g. μ(μ())")
    parser.add_argument(
        "--json", action="store_true", help="Emit JSON only (pipe-friendly)"
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="When used with --json, include trace-shaped steps[] (with deltas) for piping into analyze_cli",
    )
    parser.add_argument("--max-steps", type=int, default=64, help="ω cap")
    parser.add_argument("--stdin", action="store_true", help="Read motif from stdin")
    parser.add_argument(
        "--file", type=str, default=None, help="Read motif from file path"
    )
    args = parser.parse_args(argv[1:])

    src = _resolve_input(args.motif, use_stdin=args.stdin, file_path=args.file)
    seed = parse_motif(src)
    run = run_omega(seed, max_steps=args.max_steps)

    if args.json:
        payload = omega_run_to_json(
            run, include_meta=False, include_steps=bool(args.trace)
        )
        print(
            json.dumps(
                maybe_add_schema_fields(payload, kind="omega"), indent=2, sort_keys=True
            )
        )
        return 0

    # tiny human mode
    print(f"classification: {run.classification}")
    if run.mu is not None and run.period is not None:
        print(f"cycle: μ={run.mu} period={run.period}")
    print(f"steps: {len(run.orbit)} (max_steps={args.max_steps})")
    for s in run.orbit[: min(len(run.orbit), 16)]:
        print(f"{s.i:03d}: {s.value}")
    if len(run.orbit) > 16:
        print("... (truncated)")
    print(f"result: {run.result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
