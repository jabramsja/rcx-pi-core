from __future__ import annotations

import argparse
import json
import sys
from typing import List

from rcx_pi.program_descriptor_lib import SCHEMA, SCHEMA_DOC, describe_program_json


from rcx_pi.cli_schema import print_schema_triplet

SCHEMA_JSON = "docs/schemas/program_descriptor_schema.json"


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Describe a program (Mu) and emit JSON (contracted)."
    )
    ap.add_argument(
        "--schema", action="store_true", help="Print schema tag + doc path and exit."
    )
    ap.add_argument(
        "--json", action="store_true", help="Emit JSON to stdout (default)."
    )
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    ap.add_argument(
        "program",
        nargs="?",
        help="Program name or path (e.g. rcx_core or path/to/world.mu)",
    )

    args = ap.parse_args(argv)

    if args.schema:
        print_schema_triplet(
            "rcx-program-descriptor.v1",
            "docs/program_descriptor_schema.md",
            SCHEMA_JSON,
        )
        return 0

    if not args.program:
        ap.error("program is required unless --schema is used")

    payload = describe_program_json(args.program)

    if args.pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
