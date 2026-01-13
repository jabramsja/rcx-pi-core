from __future__ import annotations

import argparse
import json
from typing import List

from rcx_pi.program_descriptor import SCHEMA_DOC, SCHEMA_TAG, resolve_mu_program


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Emit a ProgramDescriptor (pure metadata, no execution)."
    )
    ap.add_argument(
        "--schema",
        action="store_true",
        help="Print ProgramDescriptor schema tag + schema doc path and exit.",
    )
    ap.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON",
    )
    ap.add_argument(
        "program",
        nargs="?",
        help="Mu program name (e.g. rcx_core) or a path to a .mu file",
    )

    args = ap.parse_args(argv)

    if args.schema:
        print(f"{SCHEMA_TAG} {SCHEMA_DOC}")
        return 0

    if not args.program:
        ap.error("program is required unless --schema is used")

    desc = resolve_mu_program(args.program)
    payload = desc.to_dict()

    if args.pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
