from __future__ import annotations

import argparse
import json
from typing import Sequence

from rcx_pi.program_descriptor import SCHEMA_DOC, SCHEMA_TAG, describe_program


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rcx-program-descriptor")
    ap.add_argument(
        "--schema",
        action="store_true",
        help="Print schema tag + schema doc path and exit.",
    )
    # Keep --json for backwards/ergonomic symmetry, but default is JSON anyway.
    ap.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON (default).",
    )
    ap.add_argument("program", nargs="?", help="Program name or path to a .mu file")

    args = ap.parse_args(argv)

    if args.schema:
        print(f"{SCHEMA_TAG} {SCHEMA_DOC}")
        return 0

    if not args.program:
        ap.error("program is required unless --schema is used")

    warnings: list[str] = []
    try:
        desc = describe_program(args.program)
        # describe_program returns a flat dict; contract wants it nested under 'descriptor'
        payload = {
            "schema": SCHEMA_TAG,
            "schema_doc": SCHEMA_DOC,
            "program": args.program,
            "descriptor": {
                "name": desc.get("name"),
                "resolved_path": desc.get("resolved_path"),
                "format": desc.get("format"),
                "bytes": desc.get("bytes"),
            },
            "ok": True,
            "warnings": warnings,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    except Exception as e:
        warnings.append(str(e))
        payload = {
            "schema": SCHEMA_TAG,
            "schema_doc": SCHEMA_DOC,
            "program": args.program,
            "descriptor": None,
            "ok": False,
            "warnings": warnings,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
