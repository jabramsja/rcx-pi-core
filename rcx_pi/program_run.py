from __future__ import annotations

import datetime
import hashlib
import json
from typing import Any, Dict, List, Tuple

from rcx_pi.api import run_named_list_program


SCHEMA = "rcx-program-run.v1"
SCHEMA_DOC = "docs/program_run_schema.md"


def _utc_now_z() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _hash_inputs(program: str, input_list: List[int]) -> str:
    # Determinism hash should be simple and stable across platforms.
    blob = json.dumps({"program": program, "input": input_list}, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def run_program(
    program: str,
    input_list: List[int],
) -> Tuple[List[int] | None, List[str]]:
    """
    Canonical execution seam: run a named list program on Python ints.

    Returns:
        (output_list_or_none, warnings)
    """
    warnings: List[str] = []
    try:
        out = run_named_list_program(program, input_list)
        return out, warnings
    except KeyError as e:
        warnings.append(str(e))
        return None, warnings
    except Exception as e:
        warnings.append(f"{type(e).__name__}: {e}")
        return None, warnings


def run_program_json(
    program: str,
    input_list: List[int],
) -> Dict[str, Any]:
    """
    Canonical JSON output contract for program runs.
    """
    now = _utc_now_z()
    inputs_hash = _hash_inputs(program, input_list)

    out, warnings = run_program(program, input_list)

    payload: Dict[str, Any] = {
        "schema": SCHEMA,
        "schema_doc": SCHEMA_DOC,
        "program": program,
        "input": input_list,
        "output": out if out is not None else [],
        "ok": out is not None,
        "warnings": warnings,
        "meta": {
            "tool": "program_run",
            "generated_at": now,
            "determinism": {
                "inputs_hash": inputs_hash,
            },
        },
    }
    return payload
