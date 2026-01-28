#!/usr/bin/env bash
set -euo pipefail

# ----
# macOS bash session-save quirks: prevent "unbound variable" crashes
# ----
export HISTTIMEFORMAT="${HISTTIMEFORMAT:-}"
export size="${size:-}"

echo "== 0) Repo clean =="
test -z "$(git status --porcelain)" || { echo "Repo not clean"; git status --porcelain; exit 1; }

echo "== 1) Full suite (hash-seeded) =="
PYTHONHASHSEED=0 pytest -q
test -z "$(git status --porcelain)" || { echo "Dirty after pytest"; git status --porcelain; exit 1; }

echo "== 2) IndependentEncounter tests only =="
PYTHONHASHSEED=0 pytest -q -k 'independent_encounter'

echo "== 3) Enginenews tests only =="
PYTHONHASHSEED=0 pytest -q -k 'enginenews'

echo "== 3.1) Bytecode VM v0 tests =="
PYTHONHASHSEED=0 pytest -q tests/test_bytecode_vm_v0.py

echo "== 3.2) Bytecode VM v0 audit =="
./tools/audit_bytecode.sh

echo "== 3.3) Semantic purity audit (self-hosting readiness) =="
./tools/audit_semantic_purity.sh

echo "== 3.4) Contraband check (grep-based) =="
./tools/contraband.sh rcx_pi

echo "== 3.5) AST police (catches what grep misses) =="
python3 tools/ast_police.py

echo "== 4) Anti-cheat scans =="
echo "-- no private attr access in tests/ or prototypes/"
! grep -RInE '\._[a-zA-Z0-9]+' tests/ prototypes/ || { echo "Found private attr access"; exit 1; }

echo "-- no underscored imports from rcx_pi in tests/ or prototypes/"
! grep -RInE 'from rcx_pi\..* import _' tests/ prototypes/ || { echo "Found underscored import from rcx_pi"; exit 1; }

echo "-- no underscore-prefixed keys in prototype JSON (non-standard Mu)"
# Note: _marker is allowed in seeds/ - it's a security feature for done-wrapper spoofing prevention
# Note: _type is allowed in seeds/ - Phase 6c type tags for list/dict disambiguation
# Note: kernel.v1.json is excluded - kernel state MUST use underscore-prefixed fields (_mode, _phase, etc.)
#       to distinguish kernel state from domain data (see MetaCircularKernel.v0.md)
# Note: match.v2.json and subst.v2.json are excluded - they use _match_ctx/_subst_ctx for kernel integration
! grep -RInE '"_[a-zA-Z]+":' prototypes/ seeds/ 2>/dev/null | grep -v '"_marker":' | grep -v '"_type":' | grep -v 'kernel.v1.json' | grep -v 'match.v2.json' | grep -v 'subst.v2.json' || { echo "Found non-standard underscore keys in JSON"; exit 1; }

echo "== 5) Fixture size check (all v2 jsonl) =="
find tests/fixtures/traces_v2 -name '*.v2.jsonl' -maxdepth 3 -print | sort | while read -r f; do
  n="$(wc -l < "$f" | tr -d ' ')"
  printf "%-80s %s lines\n" "$f" "$n"
done

echo "== 6) CLI exec-summary spot-check (enginenews fixtures) =="
fixtures=(
  tests/fixtures/traces_v2/enginenews_spec_v0/progressive_refinement.v2.jsonl
  tests/fixtures/traces_v2/enginenews_spec_v0/stall_pressure.v2.jsonl
  tests/fixtures/traces_v2/enginenews_spec_v0/multi_cycle.v2.jsonl
  tests/fixtures/traces_v2/enginenews_spec_v0/idempotent_cycle.v2.jsonl
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
candidate = next((ln for ln in reversed(lines) if ln.startswith("{") and ln.endswith("}")), None)
assert candidate, "No JSON line found:\n" + s
j = json.loads(candidate)
assert j["v"] == 2
assert set(j["counts"].keys()) == {"stall","fix","fixed"}
assert j["final_status"] in ("ACTIVE","STALLED")
print("OK:", j["final_status"], j["counts"])
'
done

echo "✅ audit_all pass"
