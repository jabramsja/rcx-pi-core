from __future__ import annotations

# Allow running this file directly without requiring PYTHONPATH.
# When invoked as a module (python -m rcx_pi.program_run_cli), this block is harmless.
if __package__ is None or __package__ == "":
    import sys
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))

import argparse
import datetime
import hashlib
import json
import sys
from typing import Any, List

from rcx_pi.api import run_named_list_program
from rcx_pi.program_registry import list_program_names


SCHEMA_TAG = "rcx-program-run.v1"
SCHEMA_DOC = "docs/program_run_schema.md"


def _now_utc() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_int_list(text: str) -> List[int]:
    """
    Accept:
      - JSON array:    "[1,2,3]"
      - CSV-ish:       "1,2,3"
      - Space-ish:     "1 2 3"
      - Single int:    "7"
    """
    s = text.strip()
    if not s:
        return []

    if s.startswith("["):
        val = json.loads(s)
        if not isinstance(val, list):
            raise ValueError("input must be a JSON array of ints")
        return [int(x) for x in val]

    # split on commas or whitespace
    parts = [p for p in s.replace(",", " ").split() if p]
    return [int(p) for p in parts]


def _payload(program: str, xs: List[int], out: List[int], warnings: List[str] | None = None) -> dict[str, Any]:
    warnings = list(warnings or [])
    inputs_hash = hashlib.sha256(
        (json.dumps({"program": program, "input": xs}, sort_keys=True)).encode("utf-8")
    ).hexdigest()

    return {
        "schema": SCHEMA_TAG,
        "schema_doc": SCHEMA_DOC,
        "program": program,
        "input": xs,
        "output": out,
        "ok": True,
        "warnings": warnings,
        "meta": {
            "tool": "program_run_cli",
            "generated_at": _now_utc(),
            "determinism": {
                "inputs_hash": inputs_hash,
            },
        },
    }


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Run a named RCX-π program on a list of ints and emit contract-shaped JSON."
    )
    ap.add_argument("--schema", action="store_true", help="Print schema tag + doc path and exit.")
    ap.add_argument("--list", action="store_true", help="List registered program names and exit.")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    ap.add_argument("program", nargs="?", help="Program name (e.g. succ-list)")
    ap.add_argument("input", nargs="?", help='Input list: JSON "[1,2]" or "1,2" or "1 2"')
    args = ap.parse_args(argv)

    if args.schema:
        print(f"{SCHEMA_TAG} {SCHEMA_DOC}")
        return 0

    if args.list:
        for n in list_program_names():
            print(n)
        return 0

    if not args.program or args.input is None:
        ap.error("program and input are required unless --schema/--list is used")

    try:
        xs = _parse_int_list(args.input)
    except Exception as e:
        print(f"Invalid input list: {e}", file=sys.stderr)
        return 2

    try:
        out = run_named_list_program(args.program, xs)
    except KeyError:
        avail = ", ".join(list_program_names())
        print(f"Unknown program: {args.program!r}. Available: {avail}", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"Program execution failed: {e}", file=sys.stderr)
        return 4

    payload = _payload(args.program, xs, out)
    if args.pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
