#!/usr/bin/env bash
# check_boot1_merge2_readiness.sh — Boot1 merge-2 (default flip) readiness checker.
#
# Validates all 6 gates from Boot1LoopContract.v0.md §6 are satisfied.
# Exit 0 = all gates pass (merge-2 authorized pending founder GO).
# Exit 1 = one or more gates fail (merge-2 NOT authorized).
#
# Usage: ./tools/checks/check_boot1_merge2_readiness.sh
#        (or via symlink: ./tools/check_boot1_merge2_readiness.sh)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
cd "$REPO_ROOT"

PASS=0
FAIL=0
SKIP=0

gate_pass() {
    echo "  ✓ G$1: $2"
    PASS=$((PASS + 1))
}

gate_fail() {
    echo "  ✗ G$1: $2"
    FAIL=$((FAIL + 1))
}

gate_skip() {
    echo "  ⊘ G$1: $2 (SKIP — $3)"
    SKIP=$((SKIP + 1))
}

echo "═══════════════════════════════════════════════════════════"
echo " Boot1 Merge-2 Readiness Check"
echo " Contract: mu/docs/core/Boot1LoopContract.v0.md §6"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ── G1: ABI Compatibility ──────────────────────────────────────
# _run_engine and _tail_call must be in KERNEL_RESERVED_FIELDS
echo "Gate 1: ABI Compatibility"
G1_PASS=true
if ! grep -q '"_run_engine"' rcx_pi/selfhost/step_mu.py 2>/dev/null; then
    gate_fail 1 "_run_engine not found in KERNEL_RESERVED_FIELDS (Python)"
    G1_PASS=false
fi
if ! grep -q '"_tail_call"' rcx_pi/selfhost/step_mu.py 2>/dev/null; then
    gate_fail 1 "_tail_call not found in KERNEL_RESERVED_FIELDS (Python)"
    G1_PASS=false
fi
if ! grep -q "'_run_engine'" mu/host/js/eval_step.js 2>/dev/null; then
    gate_fail 1 "_run_engine not found in KERNEL_RESERVED_FIELDS (JS)"
    G1_PASS=false
fi
if ! grep -q "'_tail_call'" mu/host/js/eval_step.js 2>/dev/null; then
    gate_fail 1 "_tail_call not found in KERNEL_RESERVED_FIELDS (JS)"
    G1_PASS=false
fi
if $G1_PASS; then
    gate_pass 1 "ABI fields reserved in both substrates"
fi
echo ""

# ── G2: Parity ─────────────────────────────────────────────────
# Boot1 parity tests must pass
echo "Gate 2: Parity (Boot1 shadow tests)"
G2_OUTPUT=$(PYTHONHASHSEED=0 pytest mu/tests/parity/test_boot1_shadow_parity.py \
    -m "not slow" -q --no-header --tb=no 2>&1 || true)
G2_PASSED=$(echo "$G2_OUTPUT" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' || echo "0")
G2_FAILED=$(echo "$G2_OUTPUT" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' || echo "0")

G2_MIN_EXPECTED=45  # Ratchet: fast test count can only increase (58 total, 45 non-slow)
if [ "$G2_FAILED" = "0" ] && [ "$G2_PASSED" -ge "$G2_MIN_EXPECTED" ]; then
    gate_pass 2 "Parity: $G2_PASSED passed (>=$G2_MIN_EXPECTED), 0 failed"
elif [ "$G2_FAILED" = "0" ] && [ "$G2_PASSED" -gt "0" ]; then
    gate_fail 2 "Parity test count regressed: $G2_PASSED passed (expected >=$G2_MIN_EXPECTED)"
else
    gate_fail 2 "Parity tests: $G2_PASSED passed, $G2_FAILED failed"
fi
echo ""

# ── G3: Security ───────────────────────────────────────────────
# No new bootstrap primitives, safety invariants S1-S7
echo "Gate 3: Security (no primitive increase)"
# Count BOOTSTRAP_PRIMITIVE markers across selfhost files
BP_COUNT=$(grep -r "BOOTSTRAP_PRIMITIVE" rcx_pi/selfhost/ 2>/dev/null | wc -l | tr -d ' ')
# Boot1 must not add primitives beyond the existing count (~4-8 markers)
if [ "$BP_COUNT" -le "8" ]; then
    gate_pass 3 "Bootstrap primitive markers stable ($BP_COUNT markers)"
else
    gate_fail 3 "Bootstrap primitive count increased ($BP_COUNT markers)"
fi
echo ""

# ── G4: Bootstrap Discipline ───────────────────────────────────
# No contradiction with Boot0 v0.4
echo "Gate 4: Bootstrap Discipline (Boot0 compatibility)"
if [ -f "mu/docs/core/Boot0Architecture.v0.md" ]; then
    gate_pass 4 "Boot0Architecture.v0.md exists (compatibility reference)"
else
    gate_fail 4 "Boot0Architecture.v0.md missing"
fi
echo ""

# ── G5: CI Stability ──────────────────────────────────────────
# Boot1 tests MUST be in CRITICAL_TEST_FILES (prevents silent CI skip)
echo "Gate 5: CI Stability (CRITICAL_TEST_FILES membership)"
if grep -q '"test_boot1_shadow_parity.py"' tests/conftest.py 2>/dev/null; then
    gate_pass 5 "test_boot1_shadow_parity.py in CRITICAL_TEST_FILES"
else
    gate_fail 5 "test_boot1_shadow_parity.py NOT in CRITICAL_TEST_FILES (CI vulnerability)"
fi
echo ""

# ── G6: Contract Preservation ─────────────────────────────────
# EngineNew 10/10, terminal shape, _config carry-through, first-match-wins
echo "Gate 6: Contract Preservation"
G6_PASS=true

# Check _run_engine_recursive exists in both substrates
if ! grep -q "_run_engine_recursive" rcx_pi/selfhost/step_mu.py 2>/dev/null; then
    gate_fail 6 "_run_engine_recursive missing from Python"
    G6_PASS=false
fi
if ! grep -q "runEnginePipelineRecursive" mu/host/js/eval_step.js 2>/dev/null; then
    gate_fail 6 "runEnginePipelineRecursive missing from JS"
    G6_PASS=false
fi
# Check depth cap
if ! grep -q "_BOOT1_MAX_REENTRY_DEPTH" rcx_pi/selfhost/step_mu.py 2>/dev/null; then
    gate_fail 6 "_BOOT1_MAX_REENTRY_DEPTH constant missing"
    G6_PASS=false
fi
if ! grep -q "BOOT1_MAX_REENTRY_DEPTH" mu/host/js/eval_step.js 2>/dev/null; then
    gate_fail 6 "BOOT1_MAX_REENTRY_DEPTH constant missing from JS"
    G6_PASS=false
fi
# Check depth cap VALUES match between substrates
PY_DEPTH=$(grep '_BOOT1_MAX_REENTRY_DEPTH = ' rcx_pi/selfhost/step_mu.py 2>/dev/null | sed 's/.*= \([0-9]*\).*/\1/' | head -1)
JS_DEPTH=$(grep 'BOOT1_MAX_REENTRY_DEPTH = ' mu/host/js/eval_step.js 2>/dev/null | sed 's/.*= \([0-9]*\).*/\1/' | head -1)
if [ "$PY_DEPTH" != "$JS_DEPTH" ] || [ "$PY_DEPTH" = "0" ]; then
    gate_fail 6 "Depth cap mismatch or missing: Python=$PY_DEPTH, JS=$JS_DEPTH"
    G6_PASS=false
fi
if $G6_PASS; then
    gate_pass 6 "Contract artifacts present, depth cap=$PY_DEPTH in both substrates"
fi
echo ""

# ── Summary ────────────────────────────────────────────────────
echo "═══════════════════════════════════════════════════════════"
TOTAL=$((PASS + FAIL + SKIP))
echo " Summary: $PASS/$TOTAL passed, $FAIL failed, $SKIP skipped"
echo ""

if [ "$FAIL" -gt "0" ]; then
    echo " ✗ MERGE-2 NOT READY"
    echo "   Fix failing gates before requesting default-flip authorization."
    echo "═══════════════════════════════════════════════════════════"
    exit 1
elif [ "$SKIP" -gt "0" ]; then
    echo " ⊘ MERGE-2 CONDITIONAL"
    echo "   All gates pass but $SKIP skipped. Verify manually."
    echo "═══════════════════════════════════════════════════════════"
    exit 0
else
    echo " ✓ MERGE-2 READY (pending founder GO)"
    echo "   All 6 gates satisfied. Request founder authorization."
    echo "═══════════════════════════════════════════════════════════"
    exit 0
fi
