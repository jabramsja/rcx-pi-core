#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/world_score.sh <trace.json> [--json] [--max-steps N] [--loop]

Purpose:
  Compute simple, deterministic "world scoring" metrics from trace-shaped JSON emitted by RCX tooling.
  This is an inspector only; it does not change runtime semantics.

Accepted trace shapes (best-effort):
  - A JSON list of step objects/values
  - A JSON dict with one embedded list under: trace|steps|states|events

Options:
  --json         Emit stable JSON summary
  --max-steps N  Fail (exit 1) if inferred steps > N (tooling gate)
  --loop         Attempt loop detection by hashing step state representations (best-effort)

Exit codes:
  0 OK
  1 Violation detected (e.g., max-steps exceeded)
  2 Usage / file / parse errors
USAGE
}

if [ $# -lt 1 ]; then usage; exit 2; fi
TRACE="$1"; shift || true

AS_JSON=0
MAX_STEPS=0
DO_LOOP=0

while [ $# -gt 0 ]; do
  case "$1" in
    --json) AS_JSON=1; shift;;
    --max-steps) MAX_STEPS="${2-0}"; shift 2;;
    --loop) DO_LOOP=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "ERROR: unknown arg: $1" >&2; usage; exit 2;;
  esac
done

test -f "$TRACE" || { echo "ERROR: trace not found: $TRACE" >&2; exit 2; }

python3 - "$TRACE" "$AS_JSON" "$MAX_STEPS" "$DO_LOOP" <<'PY'
from __future__ import annotations
import json, sys, hashlib, math
from pathlib import Path
from typing import Any

p = Path(sys.argv[1])
as_json = bool(int(sys.argv[2]))
max_steps = int(sys.argv[3])
do_loop = bool(int(sys.argv[4]))

obj = json.loads(p.read_text(encoding="utf-8", errors="replace"))

def find_steps(x: Any) -> list[Any]:
    if isinstance(x, list):
        return x
    if isinstance(x, dict):
        for k in ("trace", "steps", "states", "events"):
            v = x.get(k)
            if isinstance(v, list):
                return v
    return []

steps = find_steps(obj)
n = len(steps)

# Prefer a stable "state representation" per step if present
STATE_KEYS = ("state", "expr", "term", "value", "snapshot", "result")
ACTION_KEYS = ("action", "rule", "op", "kind")

def stable_hash(v: Any) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

unique_states = 0
action_hist: dict[str, int] = {}
loop_info = None

seen: dict[str, int] = {}
for i, s in enumerate(steps):
    rep = s
    act = "other"

    if isinstance(s, dict):
        # state rep
        for k in STATE_KEYS:
            if k in s:
                rep = s[k]
                break
        # action label (best-effort)
        for k in ACTION_KEYS:
            if k in s and isinstance(s[k], (str, int, float, bool)):
                act = str(s[k]).lower()
                break

    h = stable_hash(rep)
    if h not in seen:
        unique_states += 1
        seen[h] = i
    elif do_loop and loop_info is None:
        loop_info = {"first_repeat_step": seen[h], "repeat_step": i, "period": i - seen[h]}

    action_hist[act] = action_hist.get(act, 0) + 1

# Simple, deterministic score components (kept intentionally boring):
# - novelty_rate: unique_states / max(1, n)
# - step_penalty: 1 / (1 + n)
# - loop_penalty: 0.5 if loop detected else 1.0
novelty_rate = unique_states / max(1, n)
step_penalty = 1.0 / (1.0 + n)
loop_penalty = 0.5 if loop_info else 1.0

score = novelty_rate * step_penalty * loop_penalty

# Optional: read producer meta if present
meta = {}
if isinstance(obj, dict):
    for k in ("input", "result", "stats", "steps", "max_steps", "halt_reason", "halt", "stop_reason"):
        if k in obj:
            meta[k] = obj[k]

violation = None
rc = 0
if max_steps > 0 and n > max_steps:
    violation = {"kind": "max_steps", "reason": f"inferred steps {n} exceeds max {max_steps}"}
    rc = 1

out = {
    "trace_file": str(p),
    "steps_inferred": n,
    "unique_states": unique_states,
    "novelty_rate": novelty_rate,
    "loop_detected": bool(loop_info),
    "loop": loop_info,
    "action_histogram": {k: action_hist[k] for k in sorted(action_hist.keys())},
    "score": score,
    "precedence_basis": "trace order (as emitted)",
    "meta_present_keys": sorted(meta.keys()),
    "violation": violation,
}

if as_json:
    print(json.dumps(out, ensure_ascii=False, indent=2))
else:
    print(f"trace_file: {out['trace_file']}")
    print(f"steps_inferred: {out['steps_inferred']}")
    print(f"unique_states: {out['unique_states']}")
    print(f"novelty_rate: {out['novelty_rate']:.6f}")
    print(f"loop_detected: {out['loop_detected']}")
    if out["loop"]:
        print(f"loop: {out['loop']}")
    print("action_histogram:")
    for k in sorted(out["action_histogram"].keys()):
        print(f"  - {k}: {out['action_histogram'][k]}")
    print(f"score: {out['score']:.8f}")
    if out["meta_present_keys"]:
        print(f"meta_present_keys: {out['meta_present_keys']}")
    if out["violation"]:
        print(f"VIOLATION: {out['violation']['reason']}")

sys.exit(rc)
PY
