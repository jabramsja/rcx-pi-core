from __future__ import annotations

"""
RCX Program Run CLI

This is a small "runner seam" for RCX-π named programs (program_registry),
mirroring the style of worlds/world_trace_cli.py but for closure-motif programs.

Contract: emits JSON with schema tag + schema_doc.
"""

import argparse
import datetime
import hashlib
import json
import sys
from typing import Any, List, Optional

from rcx_pi.api import run_named_list_program
from rcx_pi.program_registry import list_program_names


SCHEMA_TAG = "rcx-program-run.v1"
SCHEMA_DOC = "docs/program_run_schema.md"


def _utc_now_z() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _inputs_hash(program: str, xs: List[int]) -> str:
    payload = json.dumps({"program": program, "input": xs}, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _parse_int_list_from_json_text(text: str) -> List[int]:
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Input must be JSON. Parse error: {e}") from e

    if not isinstance(obj, list):
        raise ValueError("Input JSON must be a list of integers (e.g. [1,2,3]).")

    out: List[int] = []
    for i, v in enumerate(obj):
        if isinstance(v, bool):
            # bool is an int subclass, but we don't want True/False silently.
            raise ValueError(f"Input[{i}] is boolean; expected integer.")
        try:
            out.append(int(v))
        except Exception as e:
            raise ValueError(f"Input[{i}] is not an integer: {v!r}") from e
    return out


def _read_input_json(args: argparse.Namespace) -> List[int]:
    """
    Priority:
      1) positional input_json (if provided)
      2) --input-file
      3) --stdin
    """
    if args.input_json is not None:
        return _parse_int_list_from_json_text(args.input_json)

    if args.input_file is not None:
        try:
            text = args.input_file.read()
        finally:
            try:
                args.input_file.close()
            except Exception:
                pass
        return _parse_int_list_from_json_text(text)

    if args.stdin:
        text = sys.stdin.read()
        return _parse_int_list_from_json_text(text)

    raise ValueError("No input provided. Use positional JSON, --input-file, or --stdin.")


def _emit(payload: dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Run a named RCX-π program on a JSON list of ints and emit JSON.")
    ap.add_argument("--schema", action="store_true", help="Print schema tag + schema doc path and exit.")
    ap.add_argument("--list", action="store_true", help="List known program names and exit.")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    ap.add_argument("--stdin", action="store_true", help="Read input JSON from stdin.")
    ap.add_argument(
        "--input-file",
        type=argparse.FileType("r", encoding="utf-8"),
        default=None,
        help="Read input JSON from a file (expects a JSON list of ints).",
    )

    ap.add_argument("program", nargs="?", help="Registered program name (e.g. succ-list)")
    ap.add_argument(
        "input_json",
        nargs="?",
        default=None,
        help='Input JSON list of ints, e.g. "[1,2,3]". Optional if using --stdin/--input-file.',
    )

    args = ap.parse_args(argv)

    if args.schema:
        print(f"{SCHEMA_TAG} {SCHEMA_DOC}")
        return 0

    if args.list:
        for name in list_program_names():
            print(name)
        # a tiny hint line for humans (kept non-contractual; it's --list output only)
        print('python3 -m rcx_pi.program_run_cli succ-list "[1,2,3]" --pretty | head -n 80')
        return 0

    if not args.program:
        ap.error("program is required unless --schema or --list is used")

    warnings: List[str] = []
    try:
        xs = _read_input_json(args)
    except Exception as e:
        print(f"Invalid input: {e}", file=sys.stderr)
        return 2

    try:
        out_xs = run_named_list_program(args.program, xs)
        ok = True
    except Exception as e:
        ok = False
        out_xs = []
        warnings.append(str(e))

    payload: dict[str, Any] = {
        "schema": SCHEMA_TAG,
        "schema_doc": SCHEMA_DOC,
        "program": args.program,
        "input": xs,
        "output": out_xs,
        "ok": bool(ok),
        "warnings": warnings,
        "meta": {
            "tool": "program_run_cli",
            "generated_at": _utc_now_z(),
            "determinism": {
                "inputs_hash": _inputs_hash(args.program, xs),
            },
        },
    }

    _emit(payload, pretty=bool(args.pretty))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
