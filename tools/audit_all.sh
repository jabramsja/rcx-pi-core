#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# FULL AUDIT - CI standard (~4-6 minutes with parallel, ~10+ without)
# ============================================================================
#
# This is the comprehensive audit for CI and pre-push validation. It runs:
# - All 1300+ tests including fuzzer (hash-seeded for determinism)
# - Semantic purity checks, contraband detection, AST police
# - Anti-cheat scans, fixture validation
#
# For local iteration, use ./tools/audit_fast.sh (~2 minutes)
#
# Usage:
#   ./tools/audit_all.sh
# ============================================================================

# Check if pytest-xdist is available for parallel execution
# Using --dist worksteal for better load balancing (idle workers steal from busy)
PARALLEL_FLAG=""
if python3 -c "import xdist" 2>/dev/null; then
    PARALLEL_FLAG="-n auto --dist worksteal"
    echo "Using parallel execution with worksteal (pytest-xdist detected)"
fi

echo "== 0) Repo clean =="
test -z "$(git status --porcelain)" || { echo "Repo not clean"; git status --porcelain; exit 1; }

echo "== 1) Full suite (hash-seeded) =="
# NOTE: This runs ALL tests including IndependentEncounter, Enginenews, etc.
# No need for separate -k filter runs - they're subsets of the full suite.
PYTHONHASHSEED=0 pytest $PARALLEL_FLAG -q
test -z "$(git status --porcelain)" || { echo "Dirty after pytest"; git status --porcelain; exit 1; }

echo "== 2) Semantic purity audit (self-hosting readiness) =="
./tools/audit_semantic_purity.sh

echo "== 3) Contraband check (grep-based) =="
./tools/contraband.sh rcx_pi

echo "== 4) AST police (catches what grep misses) =="
python3 tools/ast_police.py

echo "== 5) Anti-cheat scans =="
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

echo "== 6) Fixture validation (v2 jsonl) =="
# Count fixtures and verify none are empty
FIXTURE_COUNT=0
EMPTY_COUNT=0
for f in $(find tests/fixtures/traces_v2 -name '*.v2.jsonl' -maxdepth 3 2>/dev/null | sort); do
  FIXTURE_COUNT=$((FIXTURE_COUNT + 1))
  n="$(wc -l < "$f" | tr -d ' ')"
  if [ "$n" -eq 0 ]; then
    echo "ERROR: Empty fixture: $f"
    EMPTY_COUNT=$((EMPTY_COUNT + 1))
  fi
done
echo "Validated $FIXTURE_COUNT fixtures"
[ "$EMPTY_COUNT" -eq 0 ] || { echo "Found $EMPTY_COUNT empty fixtures"; exit 1; }
[ "$FIXTURE_COUNT" -ge 10 ] || { echo "Expected 10+ fixtures, found $FIXTURE_COUNT"; exit 1; }

echo "== 7) CLI exec-summary spot-check (enginenews fixtures) =="
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
