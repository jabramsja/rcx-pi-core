from __future__ import annotations

# Allow running this file directly (subprocess tests, ad-hoc use) without requiring PYTHONPATH.
# When invoked as a module (python -m rcx_pi.worlds.world_trace_cli), this block is harmless.
if __package__ is None or __package__ == "":
    import sys
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))

import argparse
import json
import hashlib
import datetime
import sys
from typing import Any, Dict, List

from rcx_pi.worlds.worlds_bridge import orbit_with_world_parsed

# Step-011: self-describing contract without running a trace
if "--schema" in sys.argv:
    print("rcx-world-trace.v1 docs/world_trace_json_schema.md")
    raise SystemExit(0)



def _as_trace_json(world: str, seed: str, max_steps: int, parsed: Dict[str, Any]) -> Dict[str, Any]:
    states: List[str] = list(parsed.get("states") or [])
    kind = parsed.get("kind")
    period = parsed.get("period")

    trace = []
    prev = None
    for i, s in enumerate(states):
        entry = {"step": i, "state": s}
        if prev is not None:
            entry["delta"] = {
                "changed": s != prev
            }
        trace.append(entry)
        prev = s

    out: Dict[str, Any] = {
    now = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    inputs_hash = hashlib.sha256(
        f"{world}|{seed}|{max_steps}".encode("utf-8")
    ).hexdigest()

        "schema": "rcx-world-trace.v1",
        "schema_doc": "docs/world_trace_json_schema.md",
        "world": world,
        "seed": seed,
        "max_steps": max_steps,
        "trace": trace,
        "orbit": {
            "kind": kind,
            "period": period,
            "states": states,
            "invariants": {
                "unique_states": len(set(states)),
                "is_fixed_point": bool(states) and all(s == states[0] for s in states),
                "is_cycle": period is not None and period > 0,
            },
        },
    }
    # Step A: optional semantic summary (purely derived, no inference)
    if kind is not None:
        out["classification_summary"] = {
            "kind": kind,
            "period": period,
        }

    # Step D: run-level provenance (pure metadata)
    out["meta"] = {
        "tool": "world_trace_cli",
        "schema": out.get("schema"),
        "generated_at": now,
        "determinism": {
            "inputs_hash": inputs_hash,
        },
    }

    return out


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Emit trace-shaped JSON for a Mu world by running the Rust orbit_cli example."
    )
    ap.add_argument("world", help="World name (e.g. rcx_core, pingpong, paradox_1over0)")
    ap.add_argument("seed", help="Seed term for orbit (e.g. ping, [omega,[a,b]])")
    ap.add_argument("--max-steps", type=int, default=12, help="Max orbit steps (default 12)")
    ap.add_argument("--json", action="store_true", help="Emit JSON to stdout (default)")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    ap.add_argument("--raw", action="store_true", help="Also include raw orbit_cli output in JSON")

    args = ap.parse_args(argv)

    code, raw, parsed = orbit_with_world_parsed(args.world, args.seed, max_steps=args.max_steps)
    if code != 0:
        print(raw, file=sys.stderr)
        return code

    payload = _as_trace_json(args.world, args.seed, args.max_steps, parsed)
    if args.raw:
        payload["raw_output"] = raw

    if args.json or True:
        if args.pretty:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(payload, ensure_ascii=False))
        return 0

    # (unreachable; kept for future non-json modes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
