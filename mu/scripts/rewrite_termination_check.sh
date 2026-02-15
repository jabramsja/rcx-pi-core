#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/rewrite_termination_check.sh <trace.json> [--json] [--loop] [--max-steps N]

What it does:
  - Inspects trace-shaped JSON and emits a termination summary.
  - Best-effort: supports either a list-of-steps JSON, or a dict containing an embedded list.

Options:
  --json        Emit stable JSON summary.
  --loop        Attempt loop detection by hashing step "state" fields (best-effort).
  --max-steps N Fail (exit 1) if inferred steps > N.

Exit codes:
  0 OK / within limits
  1 Detected violation (e.g. max-steps exceeded)
  2 Usage / parse errors
USAGE
}

if [ $# -lt 1 ]; then usage; exit 2; fi
TRACE="$1"; shift || true
AS_JSON=0
DO_LOOP=0
MAX_STEPS=0

while [ $# -gt 0 ]; do
  case "$1" in
    --json) AS_JSON=1; shift;;
    --loop) DO_LOOP=1; shift;;
    --max-steps) MAX_STEPS="${2-0}"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "ERROR: unknown arg: $1" >&2; usage; exit 2;;
  esac
done

python3 - "$TRACE" "$AS_JSON" "$DO_LOOP" "$MAX_STEPS" <<'PY'
from __future__ import annotations
import json, sys, hashlib
from pathlib import Path
from typing import Any

p = Path(sys.argv[1])
as_json = bool(int(sys.argv[2]))
do_loop = bool(int(sys.argv[3]))
max_steps = int(sys.argv[4])

if not p.is_file():
    raise SystemExit(f"ERROR: file not found: {p}")

obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))

def find_steps(x: Any) -> list[Any]:
    # Prefer a list directly, else look for common embedded list keys.
    if isinstance(x, list):
        return x
    if isinstance(x, dict):
        for k in ("trace", "steps", "states", "events"):
            v = x.get(k)
            if isinstance(v, list):
                return v
    return []

steps = find_steps(obj)
inferred_steps = len(steps)

# Best-effort: read optional metadata if present at top-level
meta_halt = None
meta_steps = None
meta_max = None
if isinstance(obj, dict):
    meta_halt = obj.get("halt_reason") or obj.get("halt") or obj.get("stop_reason")
    meta_steps = obj.get("steps")
    meta_max = obj.get("max_steps")

loop_info = None
if do_loop and steps:
    seen: dict[str, int] = {}
    # Try to extract a stable "state" representation from each step object.
    # Preference order: state, expr, term, value, snapshot, result
    keys = ("state", "expr", "term", "value", "snapshot", "result")
    for i, s in enumerate(steps):
        if isinstance(s, dict):
            rep = None
            for k in keys:
                if k in s:
                    rep = s[k]
                    break
            if rep is None:
                rep = s
        else:
            rep = s
        h = hashlib.sha256(json.dumps(rep, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        if h in seen:
            loop_info = {"first_repeat_step": seen[h], "repeat_step": i, "period": i - seen[h]}
            break
        seen[h] = i

out = {
    "trace_file": str(p),
    "steps_inferred": inferred_steps,
    "steps_meta": meta_steps,
    "max_steps_meta": meta_max,
    "halt_reason_meta": meta_halt,
    "loop_detected": bool(loop_info),
    "loop": loop_info,
}

# Enforce a max if asked (inferred only; tooling check)
viol = False
viol_reason = None
if max_steps > 0 and inferred_steps > max_steps:
    viol = True
    viol_reason = f"inferred steps {inferred_steps} exceeds max {max_steps}"

if as_json:
    if viol:
        out["violation"] = {"kind": "max_steps", "reason": viol_reason}
    print(json.dumps(out, ensure_ascii=False, indent=2))
else:
    print(f"trace_file: {out['trace_file']}")
    print(f"steps_inferred: {out['steps_inferred']}")
    if out["steps_meta"] is not None: print(f"steps_meta: {out['steps_meta']}")
    if out["max_steps_meta"] is not None: print(f"max_steps_meta: {out['max_steps_meta']}")
    if out["halt_reason_meta"] is not None: print(f"halt_reason_meta: {out['halt_reason_meta']}")
    print(f"loop_detected: {out['loop_detected']}")
    if out["loop"]: print(f"loop: {out['loop']}")
    if viol: print(f"VIOLATION: {viol_reason}")

sys.exit(1 if viol else 0)
PY
