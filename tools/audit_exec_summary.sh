#!/usr/bin/env bash
set -euo pipefail

fixtures=(
  tests/fixtures/traces_v2/stall_then_fix_then_end.v2.jsonl
  tests/fixtures/traces_v2/stall_at_end.v2.jsonl
)

for f in "${fixtures[@]}"; do
  echo "== $f =="

  out="$(
    PYTHONHASHSEED=0 python3 -m rcx_pi.rcx_cli replay \
      --trace "$f" --check-canon --print-exec-summary 2>&1
  )"

  echo "$out"

  printf '%s' "$out" | python3 -c '
import json, sys

s = sys.stdin.read().strip()
lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
candidate = next(
    (ln for ln in reversed(lines) if ln.startswith("{") and ln.endswith("}")),
    None
)

assert candidate is not None, "No JSON line found:\n" + s
j = json.loads(candidate)

assert j["v"] == 2
assert set(j["counts"].keys()) == {"stall", "fix", "fixed"}
assert j["final_status"] in ("ACTIVE", "STALLED")

print("OK:", j["final_status"], j["counts"])
'
done
