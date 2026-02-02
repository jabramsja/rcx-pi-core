#!/usr/bin/env bash
set -euo pipefail

# Ensure deterministic dict ordering for ALL subprocesses (including pytest-xdist workers)
export PYTHONHASHSEED=0

# ============================================================================
# FULL AUDIT - CI standard (~4-6 minutes with parallel, ~10+ without)
# ============================================================================
#
# This is the comprehensive audit for CI and pre-push validation. It runs:
# - All 2,100+ tests including fuzzer (hash-seeded for determinism)
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

echo "== 1a) Core + Fuzzer tests (hash-seeded) =="
# Run all tests EXCEPT stress tests (those have very long timeouts)
# Stress tests are for edge case validation, not CI blocking
pytest $PARALLEL_FLAG -q --ignore=tests/stress/
test -z "$(git status --porcelain)" || { echo "Dirty after core pytest"; git status --porcelain; exit 1; }

echo "== 1b) Stress tests (deep/wide edge cases, optional) =="
# Stress tests probe pathological inputs - run sequentially with longer timeouts
# These are for comprehensive validation, not CI blocking
if [ "${RCX_SKIP_STRESS:-}" = "1" ]; then
    echo "Skipping stress tests (RCX_SKIP_STRESS=1)"
else
    pytest -q tests/stress/ --timeout=300 2>/dev/null || echo "Note: Stress tests skipped or failed (non-blocking)"
fi

echo "== 2) Semantic purity audit (self-hosting readiness) =="
./tools/audit_semantic_purity.sh

echo "== 3) Contraband check (grep-based) =="
./tools/contraband.sh rcx_pi

echo "== 3b) Test theater check (assert True) =="
./tools/check_test_theater.sh tests

echo "== 3c) JS contraband check (L3 parity) =="
./tools/contraband_js.sh

echo "== 3d) JS AST police (catches what grep misses in JS) =="
./tools/ast_police_js.sh

echo "== 3e) JS test theater check =="
./tools/check_test_theater_js.sh

echo "== 3f) Seed police (structure, theater, host leakage) =="
./tools/seed_police.sh

echo "== 4) AST police (catches what grep misses in Python) =="
python3 tools/ast_police.py

echo "== 5) Anti-cheat scans =="
echo "-- no private attr access in tests/ or prototypes/"
# Exclude:
#   - self._method (private methods in test classes - Python convention)
#   - Lines testing that contraband catches _getframe patterns (grounding tests)
#   - Lines marked with # ANTICHEAT_OK
! grep -RInE '\._[a-zA-Z0-9]+' tests/ prototypes/ | \
    grep -v 'self\._' | \
    grep -v '_getframe.*CONTRABAND_OK' | \
    grep -v '# ANTICHEAT_OK' | \
    grep -v 'sys\._getframe\|sys\._current_frames' | \
    grep -v 'test_contraband_detection.py.*"""' || { echo "Found private attr access"; exit 1; }

echo "-- no underscored imports from rcx_pi in tests/ or prototypes/"
# Exclude:
#   - test_type_tag_security.py (grounding tests for _is_kernel_internal_state security fix)
#   - Lines marked with # ANTICHEAT_OK
! grep -RInE 'from rcx_pi\..* import _' tests/ prototypes/ | \
    grep -v 'test_type_tag_security.py' | \
    grep -v '# ANTICHEAT_OK' || { echo "Found underscored import from rcx_pi"; exit 1; }

echo "-- no underscore-prefixed keys in prototype JSON (non-standard Mu)"
# Note: _marker is allowed - it's a security feature for done-wrapper spoofing prevention
# Note: _type is allowed - Phase 6c type tags for list/dict disambiguation
# Note: kernel/match/subst seeds use underscore-prefixed fields for state (_mode, _phase, etc.)
# Note: mu/closures/ seeds (recurrence, exhaustion) use underscore-prefixed fields for engine state
# Note: mu/programs/ seeds (rcx_engine) use underscore-prefixed fields for engine state
# Note: mu/host/python is a symlink to rcx_pi/selfhost - exclude it to avoid scanning Python files
! grep -RInE --include='*.json' '"_[a-zA-Z]+":' prototypes/ seeds/ mu/ 2>/dev/null | grep -v '"_marker":' | grep -v '"_type":' | grep -v 'kernel.v1.json' | grep -v 'match.v2.json' | grep -v 'subst.v2.json' | grep -v 'recurrence.v1.json' | grep -v 'exhaustion.v1.json' | grep -v 'rcx_engine.v1.json' | grep -v 'enginenews.v1.json' | grep -v 'exhaust.v1.json' || { echo "Found non-standard underscore keys in JSON"; exit 1; }

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

echo "== 7) CLI exec-summary spot-check (recurrence/closure fixtures) =="
fixtures=(
  tests/fixtures/traces_v2/recurrence_spec_v0/progressive_refinement.v2.jsonl
  tests/fixtures/traces_v2/recurrence_spec_v0/stall_pressure.v2.jsonl
  tests/fixtures/traces_v2/recurrence_spec_v0/multi_cycle.v2.jsonl
  tests/fixtures/traces_v2/recurrence_spec_v0/idempotent_cycle.v2.jsonl
)

for f in "${fixtures[@]}"; do
  echo "== $f =="

  out="$(
    python3 -m rcx_pi.rcx_cli replay \
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

echo "== 8) JavaScript L3 parity check =="
echo "-- JS debt markers (must match Python) --"
./tools/check_js_debt.sh

echo "-- JS tests (must all pass) --"
node mu/host/js/eval_step.js 2>&1 | tail -5 | head -1
if node mu/host/js/eval_step.js 2>&1 | grep -q "All tests passed: true"; then
    echo "OK: JS tests pass"
else
    echo "FAIL: JS tests failed"
    exit 1
fi

echo "✅ audit_all pass"
