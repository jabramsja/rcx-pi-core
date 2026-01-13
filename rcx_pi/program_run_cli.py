from __future__ import annotations

import argparse
import json
import sys
from typing import List

from rcx_pi.program_run import SCHEMA, SCHEMA_DOC, run_program_json
from rcx_pi.program_registry import list_program_names


def _read_input(args: argparse.Namespace) -> List[int]:
    if args.stdin:
        raw = sys.stdin.read()
    elif args.input_file:
        raw = open(args.input_file, "r", encoding="utf-8").read()
    else:
        raw = args.input_json

    try:
        data = json.loads(raw)
    except Exception as e:
        raise SystemExit(f"Input is not valid JSON: {e}")

    if not isinstance(data, list) or not all(isinstance(x, int) for x in data):
        raise SystemExit("Input must be a JSON list of integers, e.g. [1,2,3].")

    return data


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Run a named RCX-π list program and emit JSON (contracted)."
    )
    ap.add_argument("--schema", action="store_true", help="Print schema tag + doc path and exit.")
    ap.add_argument("--list", action="store_true", help="List available named programs and exit.")

    ap.add_argument("program", nargs="?", help="Program name (e.g. succ-list)")
    ap.add_argument("input_json", nargs="?", default="", help="JSON list of ints (e.g. [1,2,3])")

    ap.add_argument("--stdin", action="store_true", help="Read input JSON list from stdin.")
    ap.add_argument("--input-file", help="Read input JSON list from file path.")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")

    args = ap.parse_args(argv)

    if args.schema:
        print(f"{SCHEMA} {SCHEMA_DOC}")
        return 0

    if args.list:
        for name in list_program_names():
            print(name)
        return 0

    if not args.program:
        ap.error("program is required unless --schema or --list is used")

    if not (args.stdin or args.input_file) and not args.input_json:
        ap.error("input_json is required unless --stdin or --input-file is used")

    input_list = _read_input(args)
    payload = run_program_json(args.program, input_list)

    if args.pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
