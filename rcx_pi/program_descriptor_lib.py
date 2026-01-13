from __future__ import annotations

import datetime
import hashlib
import json
from typing import Any, Dict, List

from rcx_pi.program_descriptor import describe_program

SCHEMA = "rcx-program-descriptor.v1"
SCHEMA_DOC = "docs/program_descriptor_schema.md"


def _utc_now_z() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _hash_inputs(program: str) -> str:
    blob = json.dumps({"program": program}, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def describe_program_json(program: str) -> Dict[str, Any]:
    """
    Canonical JSON output contract for program descriptor.
    """
    now = _utc_now_z()
    inputs_hash = _hash_inputs(program)

    warnings: List[str] = []
    ok = True
    descriptor: Any = None

    try:
        descriptor = describe_program(program)
    except Exception as e:
        ok = False
        warnings.append(f"{type(e).__name__}: {e}")
        descriptor = {}

    payload: Dict[str, Any] = {
        "schema": SCHEMA,
        "schema_doc": SCHEMA_DOC,
        "program": program,
        "descriptor": descriptor,
        "ok": ok,
        "warnings": warnings,
        "meta": {
            "tool": "program_descriptor",
            "generated_at": now,
            "determinism": {
                "inputs_hash": inputs_hash,
            },
        },
    }
    return payload
