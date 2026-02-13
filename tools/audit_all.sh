#!/usr/bin/env bash
set -euo pipefail

# Ensure deterministic dict ordering for ALL subprocesses (including pytest-xdist workers)
export PYTHONHASHSEED=0

# Use fast Hypothesis profile for local runs (50 examples vs 500 default)
# CI sets its own profile via environment variable (ci_fast or ci_full)
export HYPOTHESIS_PROFILE="${HYPOTHESIS_PROFILE:-ci_fast}"

# ============================================================================
# FULL AUDIT - CI standard (~4-6 minutes with parallel, ~10+ without)
# ============================================================================
#
# This is the comprehensive audit for CI and pre-push validation. It runs:
# - All 3,155+ tests including fuzzer and slow (hash-seeded for determinism)
# - Semantic purity checks, contraband detection, AST police
# - Anti-cheat scans, fixture validation
#
# For local iteration, use ./tools/audit_fast.sh (~2 minutes)
#
# Usage:
#   ./tools/audit_all.sh
#
# Output:
#   Prints founder-readable synthesis summary at end
# ============================================================================

# === Timing and result tracking for synthesis summary ===
AUDIT_START_TIME=$SECONDS
TESTS_PASSED=0

# Phase timing (bash 3 compatible - no associative arrays)
TIME_STRUCTURAL=0
TIME_TESTS=0
TIME_SECURITY=0
TIME_ANTICHEAT=0
TIME_FIXTURES=0
TIME_CLI=0
TIME_L3_PARITY=0
PHASE_START=0

# Check if pytest-xdist is available for parallel execution
# Using --dist worksteal for better load balancing (idle workers steal from busy)
PARALLEL_FLAG=""
if python3 -c "import xdist" 2>/dev/null; then
    PARALLEL_FLAG="-n auto --dist worksteal"
    echo "Using parallel execution with worksteal (pytest-xdist detected)"
fi

PHASE_START=$SECONDS
echo "== 0a) Repo clean =="
test -z "$(git status --porcelain)" || { echo "Repo not clean"; git status --porcelain; exit 1; }

echo "== 0b) Doc consistency check =="
./tools/check_docs_consistency.sh
TIME_STRUCTURAL=$((SECONDS - PHASE_START))

PHASE_START=$SECONDS
echo "== 1a) Core + Fuzzer tests (hash-seeded, excludes slow) =="
# Run all tests EXCEPT stress and slow tests
# Slow tests (meta-circular recurrence, paxos e2e) run in 1c below
# Stress tests are for edge case validation, not CI blocking
# Also exclude test_js_parity_automated.py - JS parity verified via node run below
TEST_OUTPUT=$(pytest $PARALLEL_FLAG -q -m "not slow" --ignore=tests/stress/ --ignore=tests/test_js_parity_automated.py 2>&1) || { echo "$TEST_OUTPUT"; exit 1; }
echo "$TEST_OUTPUT"
# Parse test counts (format: "X passed, Y skipped in Zs" or "X passed in Zs")
if echo "$TEST_OUTPUT" | grep -qE '[0-9]+ passed'; then
    TESTS_PASSED=$(echo "$TEST_OUTPUT" | grep -oE '[0-9]+ passed' | tail -1 | grep -oE '[0-9]+')
fi
test -z "$(git status --porcelain)" || { echo "Dirty after core pytest"; git status --porcelain; exit 1; }

echo "== 1b) Slow tests (meta-circular recurrence, paxos e2e) =="
# These go through the full meta-circular kernel path and take 2-10 minutes
SLOW_OUTPUT=$(pytest -q -m slow --timeout=300 2>&1) || { echo "$SLOW_OUTPUT"; exit 1; }
echo "$SLOW_OUTPUT"
if echo "$SLOW_OUTPUT" | grep -qE '[0-9]+ passed'; then
    SLOW_PASSED=$(echo "$SLOW_OUTPUT" | grep -oE '[0-9]+ passed' | tail -1 | grep -oE '[0-9]+')
    TESTS_PASSED=$((TESTS_PASSED + SLOW_PASSED))
fi

echo "== 1c) Stress tests (deep/wide edge cases, optional) =="
# Stress tests probe pathological inputs - run sequentially with longer timeouts
# These are for comprehensive validation, not CI blocking
if [ "${RCX_SKIP_STRESS:-}" = "1" ]; then
    echo "Skipping stress tests (RCX_SKIP_STRESS=1)"
else
    pytest -q tests/stress/ --timeout=300 2>/dev/null || echo "Note: Stress tests skipped or failed (non-blocking)"
fi
TIME_TESTS=$((SECONDS - PHASE_START))

PHASE_START=$SECONDS
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

echo "== 4a) Structural lint (projection validity) =="
python3 tools/structural_lint.py mu/

echo "== 4b) AST police (catches what grep misses in Python) =="
python3 tools/ast_police.py
TIME_SECURITY=$((SECONDS - PHASE_START))

PHASE_START=$SECONDS
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
    grep -v 'test_contraband_detection.py.*"""' | \
    grep -v '__pycache__' || { echo "Found private attr access"; exit 1; }

echo "-- no underscored imports from rcx_pi in tests/ or prototypes/ (AST-based)"
python3 tools/check_underscore_imports.py || exit 1

echo "-- no underscore-prefixed keys in prototype JSON (non-standard Mu)"
# Note: _marker is allowed - it's a security feature for done-wrapper spoofing prevention
# Note: _type is allowed - Phase 6c type tags for list/dict disambiguation
# Note: kernel/match/subst seeds use underscore-prefixed fields for state (_mode, _phase, etc.)
# Note: mu/closures/ seeds (recurrence, exhaustion) use underscore-prefixed fields for engine state
# Note: mu/programs/ seeds (rcx_engine) use underscore-prefixed fields for engine state
# Note: mu/bridge/ seeds (bootstrap_structural) use underscore-prefixed fields for match state
# Note: mu/host/python is a symlink to rcx_pi/selfhost - exclude it to avoid scanning Python files
! grep -RInE --include='*.json' '"_[a-zA-Z]+":' prototypes/ mu/ 2>/dev/null | grep -v '"_marker":' | grep -v '"_type":' | grep -v 'kernel.v1.json' | grep -v 'match.v2.json' | grep -v 'subst.v2.json' | grep -v 'recurrence.v1.json' | grep -v 'exhaustion.v1.json' | grep -v 'rcx_engine.v1.json' | grep -v 'enginenews.v1.json' | grep -v 'exhaust.v1.json' | grep -v 'bootstrap_structural.v1.json' || { echo "Found non-standard underscore keys in JSON"; exit 1; }
TIME_ANTICHEAT=$((SECONDS - PHASE_START))

PHASE_START=$SECONDS
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
TIME_FIXTURES=$((SECONDS - PHASE_START))

PHASE_START=$SECONDS
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

TIME_CLI=$((SECONDS - PHASE_START))

PHASE_START=$SECONDS
echo "== 8) JavaScript L3 parity check =="
./tools/check_js_debt.sh
if node mu/host/js/eval_step.js 2>&1 | grep -q "All tests passed: true"; then
    echo "OK: JS tests pass"
else
    echo "FAIL: JS tests failed"
    node mu/host/js/eval_step.js 2>&1 | tail -10
    exit 1
fi
TIME_L3_PARITY=$((SECONDS - PHASE_START))

# ============================================================================
# SYNTHESIS SUMMARY - Founder-readable overview of audit results
# ============================================================================
TOTAL_TIME=$((SECONDS - AUDIT_START_TIME))
TOTAL_MINS=$((TOTAL_TIME / 60))
TOTAL_SECS=$((TOTAL_TIME % 60))

# Get debt info
DEBT_CURRENT=$(grep -E '^CURRENT:' STATUS.md 2>/dev/null | grep -oE '[0-9]+' | head -1 || echo "?")
DEBT_THRESHOLD=$(grep -E '^THRESHOLD:' STATUS.md 2>/dev/null | grep -oE '[0-9]+' | head -1 || echo "?")

# Get seed counts
SEED_COUNT=$(find mu -name '*.json' -type f 2>/dev/null | wc -l | tr -d ' ')
SELFHOST_COUNT=$(find rcx_pi/selfhost -name '*.py' -type f 2>/dev/null | wc -l | tr -d ' ')

# Get current phase from STATUS.md
CURRENT_PHASE=$(grep -E '^PHASE:' STATUS.md 2>/dev/null | sed 's/PHASE: *//' || echo "?")

echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║                     RCX FULL AUDIT SYNTHESIS                               ║"
echo "║                     $(date '+%Y-%m-%d %H:%M:%S')                                    ║"
echo "╠════════════════════════════════════════════════════════════════════════════╣"
echo "║                                                                            ║"
printf "║  %-10s  %-8s  %s\n" "PHASE" "TIME" "STATUS                                    ║"
echo "║  ──────────  ────────  ──────────────────────────────────────────────────  ║"
printf "║  %-10s  %3ds      ✅ Repo clean, docs match code                       ║\n" "Structural" "$TIME_STRUCTURAL"
printf "║  %-10s  %3ds      ✅ %s tests passed                                  ║\n" "Tests" "$TIME_TESTS" "${TESTS_PASSED:-2000+}"
printf "║  %-10s  %3ds      ✅ Contraband, AST, theater, seeds clean             ║\n" "Security" "$TIME_SECURITY"
printf "║  %-10s  %3ds      ✅ No private attrs, no underscore imports           ║\n" "Anti-cheat" "$TIME_ANTICHEAT"
printf "║  %-10s  %3ds      ✅ %d fixtures validated                             ║\n" "Fixtures" "$TIME_FIXTURES" "$FIXTURE_COUNT"
printf "║  %-10s  %3ds      ✅ CLI exec-summary spot-checks pass                 ║\n" "CLI" "$TIME_CLI"
printf "║  %-10s  %3ds      ✅ Python/JS identical (debt markers match)          ║\n" "L3 Parity" "$TIME_L3_PARITY"
echo "║                                                                            ║"
echo "╠════════════════════════════════════════════════════════════════════════════╣"
echo "║  CODEBASE STATS                                                            ║"
echo "║  ──────────────────────────────────────────────────────────────────────    ║"
printf "║  Phase: %-6s  │  Debt: %s/%s  │  Seeds: %s  │  Selfhost: %s files      ║\n" "$CURRENT_PHASE" "$DEBT_CURRENT" "$DEBT_THRESHOLD" "$SEED_COUNT" "$SELFHOST_COUNT"
echo "║                                                                            ║"
echo "╠════════════════════════════════════════════════════════════════════════════╣"
printf "║  TOTAL TIME: %dm %ds                                                      ║\n" "$TOTAL_MINS" "$TOTAL_SECS"
echo "║                                                                            ║"
echo "║                         ✅ OVERALL: SHIP IT                                ║"
echo "║                                                                            ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ audit_all pass"
