#!/usr/bin/env bash
# Bytecode VM v0/v1b anti-cheat audit script
#
# Checks for:
# 1. Private attribute access in tests (._foo)
# 2. Reserved opcode execution logic (ROUTE/CLOSE blocked; STALL/FIX/FIXED implemented)
# 3. Hardcoded hashes or mocked VM internals
# 4. Opcode coverage (10 v0 opcodes + v1a STALL + v1b FIX/FIXED)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=== Bytecode VM v0/v1b Audit ==="
echo ""

FAILED=0

# 1. Check for private attribute access in bytecode tests
echo "Checking for private attribute access in bytecode tests..."
if grep -n '\._[a-z]' tests/test_bytecode_vm_v0.py 2>/dev/null | grep -v '# noqa' | grep -v 'def _'; then
    echo "WARNING: Private attribute access found in bytecode tests"
    echo "  Tests should use public API only"
    # Note: Some internal state access may be necessary for unit testing opcodes
    # This is a warning, not a failure
fi
echo "  Done (warnings above are advisory)"
echo ""

# 2. Reserved opcode guard - ROUTE/CLOSE must not have execution logic
# Note: STALL promoted in v1a, FIX/FIXED promoted in v1b
echo "Checking reserved opcode guard..."
for op in route close; do
    if grep -n "def op_${op}" rcx_pi/bytecode_vm.py 2>/dev/null | grep -v "Reserved" | grep -v "#"; then
        echo "ERROR: Reserved opcode ${op} has execution method (not yet promoted)"
        echo "  Reserved opcodes must not be implemented until promoted from VECTOR"
        FAILED=1
    fi
done
# Verify STALL is implemented (v1a)
if grep -q "def op_stall" rcx_pi/bytecode_vm.py 2>/dev/null; then
    echo "  ✓ STALL opcode implemented (v1a)"
else
    echo "ERROR: STALL opcode should be implemented (v1a)"
    FAILED=1
fi
# Verify FIX is implemented (v1b)
if grep -q "def op_fix" rcx_pi/bytecode_vm.py 2>/dev/null; then
    echo "  ✓ FIX opcode implemented (v1b)"
else
    echo "ERROR: FIX opcode should be implemented (v1b)"
    FAILED=1
fi
# Verify FIXED is implemented (v1b)
if grep -q "def op_fixed" rcx_pi/bytecode_vm.py 2>/dev/null; then
    echo "  ✓ FIXED opcode implemented (v1b)"
else
    echo "ERROR: FIXED opcode should be implemented (v1b)"
    FAILED=1
fi
if [ $FAILED -eq 0 ]; then
    echo "  No reserved opcode execution logic found (ROUTE/CLOSE blocked)"
fi
echo ""

# 3. Check for hardcoded hashes in tests
echo "Checking for hardcoded hashes in bytecode tests..."
HASH_PATTERN='[0-9a-f]{16,}'
if grep -En "$HASH_PATTERN" tests/test_bytecode_vm_v0.py 2>/dev/null | grep -v "fixture" | grep -v "golden" | grep -v "#"; then
    echo "WARNING: Possible hardcoded hashes in bytecode tests"
    echo "  Tests should compute expected values, not hardcode them"
fi
echo "  Done"
echo ""

# 4. Check for mocked VM internals
echo "Checking for mocked VM internals..."
if grep -n "mock.*BytecodeVM" tests/test_bytecode_vm_v0.py 2>/dev/null; then
    echo "ERROR: VM internals are being mocked"
    echo "  Tests must use real VM execution, not mocks"
    FAILED=1
fi
if grep -n "@patch.*bytecode_vm" tests/test_bytecode_vm_v0.py 2>/dev/null; then
    echo "ERROR: Bytecode VM is being patched"
    FAILED=1
fi
if [ $FAILED -eq 0 ]; then
    echo "  No mocked VM internals found"
fi
echo ""

# 5. Opcode coverage check (v0 + v1a STALL + v1b FIX/FIXED)
echo "Checking opcode coverage..."
V0_OPCODES="INIT LOAD_EVENT CANON_EVENT STORE_MU EMIT_CANON ADVANCE SET_PHASE ASSERT_CONTIGUOUS HALT_OK HALT_ERR"
V1A_OPCODES="STALL"
V1B_OPCODES="FIX FIXED"
ALL_OPCODES="$V0_OPCODES $V1A_OPCODES $V1B_OPCODES"
MISSING_COVERAGE=""
for op in $ALL_OPCODES; do
    # Check for either Opcode.NAME or op_name pattern
    op_lower=$(echo "$op" | tr '[:upper:]' '[:lower:]')
    if ! grep -qE "(Opcode\.${op}|op_${op_lower})" tests/test_bytecode_vm_v0.py 2>/dev/null; then
        MISSING_COVERAGE="$MISSING_COVERAGE $op"
    fi
done
if [ -n "$MISSING_COVERAGE" ]; then
    echo "ERROR: Missing test coverage for opcodes:$MISSING_COVERAGE"
    FAILED=1
else
    echo "  All v0 opcodes (10) + v1a STALL + v1b FIX/FIXED have test coverage"
fi
echo ""

# 6. Check that BytecodeVM file exists and has expected structure
echo "Checking BytecodeVM structure..."
if [ ! -f "rcx_pi/bytecode_vm.py" ]; then
    echo "ERROR: rcx_pi/bytecode_vm.py not found"
    FAILED=1
else
    # Check for required classes
    for cls in BytecodeVM Opcode Phase ExecutionStatus; do
        if ! grep -q "class $cls" rcx_pi/bytecode_vm.py; then
            echo "ERROR: Missing class $cls in bytecode_vm.py"
            FAILED=1
        fi
    done
    echo "  BytecodeVM structure verified"
fi
echo ""

# 7. Check test file structure
echo "Checking test file structure..."
if [ ! -f "tests/test_bytecode_vm_v0.py" ]; then
    echo "ERROR: tests/test_bytecode_vm_v0.py not found"
    FAILED=1
else
    # Check for test classes (v0 + v1a + v1b)
    TEST_CLASSES="TestOpcodeInit TestEventMappingTraceStart TestGoldenRoundTrip TestRejection TestReservedOpcodeGuard TestOpcodeStall TestV1aRegisters TestOpcodeFix TestOpcodeFixed TestV1bRegisters"
    for cls in $TEST_CLASSES; do
        if ! grep -q "class $cls" tests/test_bytecode_vm_v0.py; then
            echo "WARNING: Missing test class $cls"
        fi
    done
    echo "  Test file structure verified"
fi
echo ""

# Final result
echo "=== Audit Result ==="
if [ $FAILED -eq 0 ]; then
    echo "PASS: Bytecode VM v0/v1b audit passed"
    exit 0
else
    echo "FAIL: Bytecode VM v0/v1b audit failed"
    exit 1
fi
