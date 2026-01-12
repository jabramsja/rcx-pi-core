#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/world_score.sh <trace.json|-> [--json] [--max-steps N] [--loop]

Purpose:
  Compute simple, deterministic "world scoring" metrics from trace-shaped JSON emitted by RCX tooling.
  This is an inspector only; it does not change runtime semantics.

Accepted trace shapes (best-effort):
  - A JSON list of step objects/values
  - A JSON dict with one embedded list under: trace|steps|states|events

Input:
  <trace.json>   Path to JSON file
  -              Read JSON from stdin

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

# If TRACE is "-", slurp stdin into a temp file.
TMP=""
if [ "$TRACE" = "-" ]; then
  TMP="$(mktemp -t rcx_trace.XXXXXX.json)"
  cat > "$TMP"
  TRACE="$TMP"
fi

cleanup() {
  if [ -n "${TMP:-}" ] && [ -f "${TMP:-}" ]; then
    rm -f "$TMP" || true
  fi
}
trap cleanup EXIT

test -f "$TRACE" || { echo "ERROR: trace not found: $TRACE" >&2; exit 2; }

python3 - "$TRACE" "$AS_JSON" "$MAX_STEPS" "$DO_LOOP" <<'PY'
from __future__ import annotations
import json, sys, hashlib, re, math
from pathlib import Path
from typing import Any

p = Path(sys.argv[1])
as_json = bool(int(sys.argv[2]))
max_steps = int(sys.argv[3])
do_loop = bool(int(sys.argv[4]))

raw = p.read_text(encoding="utf-8", errors="replace")
m = re.search(r"[\[{]", raw)
if not m:
    raise SystemExit("ERROR: no JSON object/array found in trace input")
raw = raw[m.start():].strip()
obj = json.loads(raw)

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
        for k in STATE_KEYS:
            if k in s:
                rep = s[k]
                break
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

novelty_rate = unique_states / max(1, n)
step_penalty = 1.0 / (1.0 + n)
loop_penalty = 0.5 if loop_info else 1.0
score = novelty_rate * step_penalty * loop_penalty

# --- RCX structural scoring guardrails ---
# Penalize trivial traces (no evolution)
if n <= 1:
    score = 0.0

# Penalize immediate sink / degenerate cycles
if unique_states <= 1:
    score = 0.0

# --- RCX cycle quality bonus ---
# Reward structured oscillation (limit cycles)
if loop_info and loop_info.get("period", 0) >= 2:
    cycle_bonus = min(1.0, 0.1 * loop_info["period"])
    score = max(score, cycle_bonus)


meta = {}
if isinstance(obj, dict):
    for k in ("input", "result", "stats", "steps", "max_steps", "halt_reason", "halt", "stop_reason", "world", "seed"):
        if k in obj:
            meta[k] = obj[k]

violation = None
rc = 0
if max_steps > 0 and n > max_steps:
    violation = {"kind": "max_steps", "reason": f"inferred steps {n} exceeds max {max_steps}"}
    rc = 1


# --- Structural metrics ---
total_actions = sum(action_hist.values()) or 1
rule_entropy = -sum(
    (c/total_actions) * math.log2(c/total_actions)
    for c in action_hist.values()
    if c > 0
)

orbit_kind = None
orbit_period = None
if isinstance(obj, dict) and "orbit" in obj:
    orbit = obj.get("orbit") or {}
    orbit_kind = orbit.get("kind")
    orbit_period = orbit.get("period")


# --- Rule signature (hash of the actual staged world rules, if resolvable) ---
# We prefer hashing the world file content (normalized) so mutations change rule_signature.
# Fallback: hash action histogram (kept as rule_influence_signature).
def _normalize_world_text(s: str) -> str:
    out = []
    for ln in s.splitlines():
        ln2 = ln.strip()
        if not ln2 or ln2.startswith("#"):
            continue
        # normalize whitespace around arrow
        ln2 = re.sub(r"\s*->\s*", " -> ", ln2)
        out.append(ln2)
    return "\n".join(out).rstrip() + "\n"

rule_signature = None
world_file_path = None
world_file_sha256 = None
world_file_normalized_sha256 = None
rule_signature_basis = None

world_name = obj.get("world") if isinstance(obj, dict) else None
if isinstance(world_name, str) and world_name:
    candidates = [
        Path("rcx_pi_rust") / "mu_programs" / f"{world_name}.mu",
        Path("mu_programs") / f"{world_name}.mu",
    ]
    for wp in candidates:
        if wp.is_file():
            wbytes = wp.read_bytes()
            wraw = wbytes.decode("utf-8", errors="replace")
            wnorm = _normalize_world_text(wraw)

            world_file_path = str(wp)
            world_file_sha256 = hashlib.sha256(wbytes).hexdigest()
            world_file_normalized_sha256 = hashlib.sha256(wnorm.encode("utf-8")).hexdigest()

            rule_signature = world_file_normalized_sha256
            rule_signature_basis = "world_file_normalized"
            break

# --- Rule influence signature (stable hash of action histogram) ---
rule_influence_signature = hashlib.sha256(
    json.dumps(action_hist, sort_keys=True, ensure_ascii=False).encode('utf-8')
).hexdigest()

if rule_signature is None:
    rule_signature = rule_influence_signature
    rule_signature_basis = 'action_histogram_fallback'
# --- Trace signature (stable hash of ordered step state representations) ---
trace_signature = hashlib.sha256(
    json.dumps([
        (s.get('state') if isinstance(s, dict) and 'state' in s else (s.get('expr') if isinstance(s, dict) and 'expr' in s else s))
        for s in steps
    ], sort_keys=True, ensure_ascii=False).encode('utf-8')
).hexdigest()

out = {
    "trace_file": str(p),
    "steps_inferred": n,
    "unique_states": unique_states,
    "novelty_rate": novelty_rate,
    "loop_detected": bool(loop_info),
    "loop": loop_info,
    "action_histogram": {k: action_hist[k] for k in sorted(action_hist.keys())},
    "rule_signature": rule_signature,
    "rule_signature_basis": rule_signature_basis,
    "world_file_path": world_file_path,
    "world_file_sha256": world_file_sha256,
    "world_file_normalized_sha256": world_file_normalized_sha256,
    "rule_influence_signature": rule_influence_signature,
    "trace_signature": trace_signature,
    "score": score,
    "rule_entropy": rule_entropy,
    "orbit_kind": orbit_kind,
    "orbit_period": orbit_period,
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
