#!/usr/bin/env bash
# Semantic Purity Audit - Self-hosting readiness guardrails
#
# Ensures RCX semantics are host-independent and portable.
# These checks are valid now and remain valid as we move toward self-hosting.
#
# Checks:
# 1. Semantic purity: No Python-specific types in traces
# 2. Host closure detection: No Python lambda/def in rule motifs
# 3. Bytecode portability: No Python builtins in opcodes
# 4. Trace portability: No host-specific serialization artifacts

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=== Semantic Purity Audit (Self-Hosting Readiness) ==="
echo ""

FAILED=0
WARNINGS=0

# -----------------------------------------------------------------------------
# 1. Semantic Purity: No Python-specific types in trace fixtures
# -----------------------------------------------------------------------------
echo "== 1. Semantic Purity: Trace Fixtures =="

# Patterns that indicate Python types leaked into traces
PYTHON_TYPE_PATTERNS=(
    "<class '"           # Python class repr
    "<function "         # Python function repr
    "<lambda>"           # Lambda repr
    "<built-in"          # Built-in function
    "<module '"          # Module repr
    "object at 0x"       # Memory address (object repr)
    "__main__"           # Python main module
    "'__dict__'"         # Python dunder
    "'__class__'"        # Python dunder
)

echo "Scanning trace fixtures for Python-specific types..."
for pattern in "${PYTHON_TYPE_PATTERNS[@]}"; do
    if grep -r "$pattern" tests/fixtures/traces/ tests/fixtures/traces_v2/ 2>/dev/null; then
        echo "ERROR: Found Python-specific pattern: $pattern"
        FAILED=1
    fi
done

if [ $FAILED -eq 0 ]; then
    echo "  ✓ No Python-specific types in trace fixtures"
fi
echo ""

# -----------------------------------------------------------------------------
# 2. Host Closure Detection: No Python closures in rule motifs
# -----------------------------------------------------------------------------
echo "== 2. Host Closure Detection: Rule Motifs =="

# Check rule_motifs_v0.py for closures stored as data
echo "Scanning rule motif definitions for host closures..."

# These patterns would indicate a rule stores a Python function
CLOSURE_PATTERNS=(
    '"body": lambda'     # Lambda as body
    '"pattern": lambda'  # Lambda as pattern
    '"apply": lambda'    # Lambda as apply function
    'def.*:.*#.*motif'   # Inline function definition
)

for pattern in "${CLOSURE_PATTERNS[@]}"; do
    if grep -E "$pattern" rcx_pi/rule_motifs_v0.py 2>/dev/null; then
        echo "ERROR: Rule motif contains host closure: $pattern"
        FAILED=1
    fi
done

# Check that rule motifs are pure data (JSON-serializable structure)
# This verifies the rules are represented as motifs, not as Python functions
if [ -f "rcx_pi/rule_motifs_v0.py" ]; then
    # Look for functions that return callable instead of data
    if grep -E "return lambda|return def" rcx_pi/rule_motifs_v0.py 2>/dev/null; then
        echo "ERROR: Rule motif function returns closure instead of data"
        FAILED=1
    fi
fi

if [ $FAILED -eq 0 ]; then
    echo "  ✓ No host closures in rule motif definitions"
fi
echo ""

# -----------------------------------------------------------------------------
# 3. Bytecode Portability: No Python builtins in opcode definitions
# -----------------------------------------------------------------------------
echo "== 3. Bytecode Portability: Opcode Definitions =="

echo "Scanning bytecode VM for Python-specific builtins in opcodes..."

# Opcodes should not directly reference Python builtins that wouldn't exist
# in other languages
PYTHON_BUILTIN_PATTERNS=(
    'eval('              # Dynamic eval
    'exec('              # Dynamic exec
    'compile('           # Python compile
    '__import__'         # Dynamic import
    'globals()'          # Python globals
    'locals()'           # Python locals
    'vars()'             # Python vars
    'type('              # Python type() for dynamic typing
    'isinstance.*str'    # Type check against Python str (OK for validation)
)

# Only flag eval/exec/compile/__import__ as errors (truly non-portable)
HARD_ERRORS=(
    'eval('
    'exec('
    'compile('
    '__import__'
)

for pattern in "${HARD_ERRORS[@]}"; do
    if grep -n "$pattern" rcx_pi/bytecode_vm.py 2>/dev/null | grep -v "#"; then
        echo "ERROR: Bytecode VM uses non-portable Python builtin: $pattern"
        FAILED=1
    fi
done

if [ $FAILED -eq 0 ]; then
    echo "  ✓ No non-portable Python builtins in bytecode VM"
fi
echo ""

# -----------------------------------------------------------------------------
# 4. Trace Portability: No host-specific serialization
# -----------------------------------------------------------------------------
echo "== 4. Trace Portability: Serialization =="

echo "Checking trace serialization for portability..."

# Traces should use standard JSON types only
# Check that mu payloads don't contain Python-specific types
NON_JSON_PATTERNS=(
    'datetime.datetime'  # Python datetime
    'Decimal('           # Python Decimal
    'bytes('             # Python bytes
    "b'"                 # Bytes literal in traces
    'set(['              # Python set
    'frozenset('         # Python frozenset
    'complex('           # Python complex number
)

for pattern in "${NON_JSON_PATTERNS[@]}"; do
    if grep -r "$pattern" tests/fixtures/traces/ tests/fixtures/traces_v2/ 2>/dev/null; then
        echo "WARNING: Non-JSON type found in traces: $pattern"
        WARNINGS=$((WARNINGS + 1))
    fi
done

if [ $WARNINGS -eq 0 ]; then
    echo "  ✓ Trace serialization uses portable JSON types only"
else
    echo "  ⚠ $WARNINGS warnings (non-JSON types detected)"
fi
echo ""

# -----------------------------------------------------------------------------
# 5. Opcode Enum Portability
# -----------------------------------------------------------------------------
echo "== 5. Opcode Enum: Language-Agnostic Definitions =="

echo "Verifying opcodes are defined as language-agnostic constants..."

if [ -f "rcx_pi/bytecode_vm.py" ]; then
    # Check that opcodes are simple enum values, not complex Python objects
    OPCODE_COUNT=$(grep -c "= auto()" rcx_pi/bytecode_vm.py 2>/dev/null || echo "0")
    echo "  Found $OPCODE_COUNT opcode definitions"

    # Opcodes should be simple identifiers (UPPER_CASE)
    if grep -E "class Opcode" rcx_pi/bytecode_vm.py >/dev/null 2>&1; then
        echo "  ✓ Opcodes defined as enum (portable)"
    else
        echo "  WARNING: Opcode definition structure unclear"
        WARNINGS=$((WARNINGS + 1))
    fi
fi
echo ""

# -----------------------------------------------------------------------------
# 6. Value Hash Portability
# -----------------------------------------------------------------------------
echo "== 6. Value Hash: Deterministic & Portable =="

echo "Checking value_hash implementation for portability..."

if [ -f "rcx_pi/trace_canon.py" ]; then
    # value_hash should use standard SHA-256, not Python-specific hashing
    if grep -n "def value_hash" rcx_pi/trace_canon.py >/dev/null 2>&1; then
        # Check it uses hashlib (standard) not hash() (Python-specific)
        # Use larger window (15 lines) to capture full function
        if grep -A15 "def value_hash" rcx_pi/trace_canon.py | grep -q "hashlib"; then
            echo "  ✓ value_hash uses hashlib.sha256 (portable)"
        elif grep -A15 "def value_hash" rcx_pi/trace_canon.py | grep -q "hash("; then
            echo "  ERROR: value_hash uses Python hash() (non-portable, non-deterministic)"
            FAILED=1
        else
            echo "  WARNING: Could not determine hash implementation"
            WARNINGS=$((WARNINGS + 1))
        fi
    fi
fi
echo ""

# -----------------------------------------------------------------------------
# 7. Reserved Opcode Discipline
# -----------------------------------------------------------------------------
echo "== 7. Reserved Opcode Discipline =="

echo "Verifying reserved opcodes remain unimplemented..."

# Note: STALL implemented in v1a, FIX/FIXED in v1b, ROUTE/CLOSE remain blocked
RESERVED_OPS="ROUTE CLOSE"
for op in $RESERVED_OPS; do
    op_lower=$(echo "$op" | tr '[:upper:]' '[:lower:]')
    if grep -n "def op_${op_lower}" rcx_pi/bytecode_vm.py 2>/dev/null | grep -v "Reserved"; then
        echo "  ERROR: Reserved opcode $op has implementation (should be blocked until promoted)"
        FAILED=1
    fi
done

# Verify STALL is implemented (v1a)
if grep -q "def op_stall" rcx_pi/bytecode_vm.py 2>/dev/null; then
    echo "  ✓ STALL opcode implemented (v1a)"
else
    echo "  ERROR: STALL opcode should be implemented (v1a)"
    FAILED=1
fi

# Verify FIX/FIXED are implemented (v1b)
if grep -q "def op_fix" rcx_pi/bytecode_vm.py 2>/dev/null; then
    echo "  ✓ FIX opcode implemented (v1b)"
else
    echo "  ERROR: FIX opcode should be implemented (v1b)"
    FAILED=1
fi

if grep -q "def op_fixed" rcx_pi/bytecode_vm.py 2>/dev/null; then
    echo "  ✓ FIXED opcode implemented (v1b)"
else
    echo "  ERROR: FIXED opcode should be implemented (v1b)"
    FAILED=1
fi

if [ $FAILED -eq 0 ]; then
    echo "  ✓ Reserved opcodes (ROUTE/CLOSE) remain unimplemented"
fi
echo ""

# -----------------------------------------------------------------------------
# 8. Mu Type Guardrails
# -----------------------------------------------------------------------------
echo "== 8. Mu Type: Self-Hosting Readiness =="

echo "Checking Mu type validation module exists..."

if [ -f "rcx_pi/mu_type.py" ]; then
    echo "  ✓ mu_type.py exists"

    # Check that is_mu function exists
    if grep -q "def is_mu" rcx_pi/mu_type.py 2>/dev/null; then
        echo "  ✓ is_mu() validation function defined"
    else
        echo "  ERROR: is_mu() validation function missing"
        FAILED=1
    fi

    # Check that assert_mu function exists
    if grep -q "def assert_mu" rcx_pi/mu_type.py 2>/dev/null; then
        echo "  ✓ assert_mu() guardrail function defined"
    else
        echo "  ERROR: assert_mu() guardrail function missing"
        FAILED=1
    fi

    # Check for NaN/Infinity rejection in is_mu
    if grep -E "float\('inf'\)|float\('-inf'\)|!= value" rcx_pi/mu_type.py >/dev/null 2>&1; then
        echo "  ✓ is_mu() rejects NaN/Infinity"
    else
        echo "  WARNING: is_mu() may not reject NaN/Infinity"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo "  ERROR: rcx_pi/mu_type.py not found (Mu type validation required)"
    FAILED=1
fi

echo ""

# -----------------------------------------------------------------------------
# 9. Structural Purity Guardrails
# -----------------------------------------------------------------------------
echo "== 9. Structural Purity: Programming IN RCX =="

echo "Checking structural purity guardrail functions exist..."

if [ -f "rcx_pi/mu_type.py" ]; then
    # Check that has_callable exists
    if grep -q "def has_callable" rcx_pi/mu_type.py 2>/dev/null; then
        echo "  ✓ has_callable() detector defined"
    else
        echo "  ERROR: has_callable() detector missing"
        FAILED=1
    fi

    # Check that assert_no_callables exists
    if grep -q "def assert_no_callables" rcx_pi/mu_type.py 2>/dev/null; then
        echo "  ✓ assert_no_callables() guardrail defined"
    else
        echo "  ERROR: assert_no_callables() guardrail missing"
        FAILED=1
    fi

    # Check that assert_seed_pure exists
    if grep -q "def assert_seed_pure" rcx_pi/mu_type.py 2>/dev/null; then
        echo "  ✓ assert_seed_pure() seed validator defined"
    else
        echo "  ERROR: assert_seed_pure() seed validator missing"
        FAILED=1
    fi

    # Check that assert_handler_pure exists
    if grep -q "def assert_handler_pure" rcx_pi/mu_type.py 2>/dev/null; then
        echo "  ✓ assert_handler_pure() handler wrapper defined"
    else
        echo "  ERROR: assert_handler_pure() handler wrapper missing"
        FAILED=1
    fi

    # Check that validate_kernel_boundary exists
    if grep -q "def validate_kernel_boundary" rcx_pi/mu_type.py 2>/dev/null; then
        echo "  ✓ validate_kernel_boundary() primitive validator defined"
    else
        echo "  ERROR: validate_kernel_boundary() primitive validator missing"
        FAILED=1
    fi
fi

echo ""

# -----------------------------------------------------------------------------
# 10. Kernel Purity (when kernel.py exists)
# -----------------------------------------------------------------------------
echo "== 10. Kernel Purity: No Host Logic in Kernel =="

if [ -f "rcx_pi/kernel.py" ]; then
    echo "Checking kernel.py for structural purity..."

    # No lambdas in kernel (except in comments)
    if grep -n "lambda" rcx_pi/kernel.py 2>/dev/null | grep -v "#" | grep -v '"""' | grep -v "'''" ; then
        echo "  WARNING: Lambda found in kernel.py"
        WARNINGS=$((WARNINGS + 1))
    else
        echo "  ✓ No lambdas in kernel.py"
    fi

    # All handlers should be wrapped with assert_handler_pure
    # (Check for handler ASSIGNMENT without wrapping - reads are OK)
    if grep -n "_handlers\[.*\] =" rcx_pi/kernel.py 2>/dev/null | grep -v "assert_handler_pure" | grep -v "# wrapped"; then
        echo "  WARNING: Possibly unwrapped handler registration in kernel.py"
        WARNINGS=$((WARNINGS + 1))
    else
        echo "  ✓ Handler registration uses assert_handler_pure"
    fi
else
    echo "  (kernel.py not yet created - will check when it exists)"
fi

echo ""

# -----------------------------------------------------------------------------
# 11. Seed Purity (when seeds/ directory exists)
# -----------------------------------------------------------------------------
echo "== 11. Seed Purity: Seeds as Pure Mu =="

if [ -d "seeds" ]; then
    echo "Checking seeds/ directory..."

    # Seeds should be JSON files
    SEED_COUNT=$(ls -1 seeds/*.json 2>/dev/null | wc -l | tr -d ' ')
    if [ "$SEED_COUNT" -gt 0 ]; then
        echo "  Found $SEED_COUNT seed JSON files"

        # Validate each seed is valid JSON
        for seed in seeds/*.json; do
            if ! python3 -c "import json; json.load(open('$seed'))" 2>/dev/null; then
                echo "  ERROR: Seed $seed is not valid JSON"
                FAILED=1
            fi
        done

        if [ $FAILED -eq 0 ]; then
            echo "  ✓ All seeds are valid JSON"
        fi
    else
        echo "  (No seed JSON files yet)"
    fi

    # No .py files in seeds/ (seeds should be data, not code)
    PY_COUNT=$(ls -1 seeds/*.py 2>/dev/null | wc -l | tr -d ' ')
    if [ "$PY_COUNT" -gt 0 ]; then
        echo "  WARNING: Found Python files in seeds/ - seeds should be pure Mu (JSON)"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo "  (seeds/ directory not yet created - will check when it exists)"
fi

echo ""

# -----------------------------------------------------------------------------
# 12. Python Equality in Kernel (Anti-Coercion)
# -----------------------------------------------------------------------------
echo "== 12. Python Equality: No == on Mu Values =="

echo "Checking for Python == used on Mu values in kernel code..."

if [ -f "rcx_pi/kernel.py" ]; then
    # Look for == that might be comparing Mu values (not hashes)
    # Allowed: hash1 == hash2 (strings)
    # Forbidden: mu1 == mu2 (should use mu_equal)
    if grep -n " == " rcx_pi/kernel.py 2>/dev/null | grep -v "hash" | grep -v "#" | grep -v "str" ; then
        echo "  WARNING: Possible Python == on non-hash values in kernel.py"
        echo "  Use mu_equal() for Mu comparison, not Python =="
        WARNINGS=$((WARNINGS + 1))
    else
        echo "  ✓ No suspicious == usage in kernel.py"
    fi
else
    echo "  (kernel.py not yet created - will check when it exists)"
fi

echo ""

# -----------------------------------------------------------------------------
# 13. isinstance Dispatch in Kernel
# -----------------------------------------------------------------------------
echo "== 13. isinstance Dispatch: No Host Type Dispatch =="

echo "Checking for isinstance used for dispatch in kernel code..."

if [ -f "rcx_pi/kernel.py" ]; then
    # isinstance is OK in guardrails (marked with # guardrail)
    # isinstance is NOT OK for dispatch logic
    if grep -n "isinstance" rcx_pi/kernel.py 2>/dev/null | grep -v "# guardrail" | grep -v "#.*isinstance"; then
        echo "  WARNING: isinstance found in kernel.py without # guardrail marker"
        echo "  isinstance should only be used in guardrails, not for dispatch"
        WARNINGS=$((WARNINGS + 1))
    else
        echo "  ✓ No isinstance dispatch in kernel.py"
    fi
else
    echo "  (kernel.py not yet created - will check when it exists)"
fi

echo ""

# -----------------------------------------------------------------------------
# 14. Bare Except Clauses
# -----------------------------------------------------------------------------
echo "== 14. Bare Except: No Swallowed Validation Errors =="

echo "Checking for bare except clauses that might swallow validation errors..."

# Check kernel and mu_type for bare excepts
for file in rcx_pi/kernel.py rcx_pi/mu_type.py; do
    if [ -f "$file" ]; then
        if grep -n "except:" "$file" 2>/dev/null | grep -v "# intentional"; then
            echo "  WARNING: Bare 'except:' in $file (may swallow validation errors)"
            WARNINGS=$((WARNINGS + 1))
        fi
        if grep -n "except Exception:" "$file" 2>/dev/null | grep -v "# intentional"; then
            echo "  WARNING: Broad 'except Exception:' in $file"
            WARNINGS=$((WARNINGS + 1))
        fi
    fi
done

if [ $WARNINGS -eq 0 ]; then
    echo "  ✓ No bare except clauses found"
fi

echo ""

# -----------------------------------------------------------------------------
# 15. Guardrail Mocking in Tests
# -----------------------------------------------------------------------------
echo "== 15. Test Integrity: No Guardrail Mocking =="

echo "Checking for tests that mock guardrail functions..."

MOCK_PATTERNS=(
    "@patch.*mu_type.assert_mu"
    "@patch.*mu_type.is_mu"
    "@patch.*mu_type.validate_mu"
    "@patch.*mu_type.assert_seed_pure"
    "@patch.*mu_type.mu_equal"
)

for pattern in "${MOCK_PATTERNS[@]}"; do
    if grep -r "$pattern" tests/ 2>/dev/null; then
        echo "  ERROR: Found mock of guardrail function: $pattern"
        echo "  Tests must not mock guardrails - this creates false positives"
        FAILED=1
    fi
done

if [ $FAILED -eq 0 ]; then
    echo "  ✓ No guardrail mocking in tests"
fi

echo ""

# -----------------------------------------------------------------------------
# 16. Bootstrap Markers
# -----------------------------------------------------------------------------
echo "== 16. Bootstrap Markers: Temporary Python Code =="

echo "Checking for BOOTSTRAP markers in Python code..."

BOOTSTRAP_COUNT=$(grep -r "# BOOTSTRAP:" rcx_pi/ 2>/dev/null | wc -l | tr -d ' ')
if [ "$BOOTSTRAP_COUNT" -gt 0 ]; then
    echo "  Found $BOOTSTRAP_COUNT BOOTSTRAP markers (temporary Python code)"
    echo "  These must be removed for true self-hosting (Phase 3)"
    grep -r "# BOOTSTRAP:" rcx_pi/ 2>/dev/null | head -5
else
    echo "  ✓ No BOOTSTRAP markers found (or Phase 3 complete)"
fi

echo ""

# -----------------------------------------------------------------------------
# 17. mu_equal Usage (Anti-Coercion)
# -----------------------------------------------------------------------------
echo "== 17. mu_equal: Structural Equality Function =="

echo "Checking mu_equal() exists and is used for Mu comparison..."

if [ -f "rcx_pi/mu_type.py" ]; then
    if grep -q "def mu_equal" rcx_pi/mu_type.py 2>/dev/null; then
        echo "  ✓ mu_equal() function defined"
    else
        echo "  ERROR: mu_equal() function missing from mu_type.py"
        FAILED=1
    fi
fi

echo ""

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
echo "=== Semantic Purity Audit Summary ==="
echo ""
echo "Checks completed:"
echo "  1. Trace fixtures: No Python-specific types"
echo "  2. Rule motifs: No host closures"
echo "  3. Bytecode VM: No non-portable builtins"
echo "  4. Trace serialization: JSON-portable types"
echo "  5. Opcodes: Language-agnostic enum"
echo "  6. Value hash: Deterministic SHA-256"
echo "  7. Reserved opcodes: ROUTE/CLOSE blocked, STALL/FIX/FIXED implemented (v1b)"
echo "  8. Mu type: Basic validation guardrails"
echo "  9. Structural purity: Programming IN RCX guardrails"
echo "  10. Kernel purity: No host logic (when kernel.py exists)"
echo "  11. Seed purity: Seeds as pure Mu (when seeds/ exists)"
echo "  12. Python equality: No == on Mu values (use mu_equal)"
echo "  13. isinstance dispatch: No host type dispatch in kernel"
echo "  14. Bare except: No swallowed validation errors"
echo "  15. Test integrity: No guardrail mocking"
echo "  16. Bootstrap markers: Temporary Python code tracked"
echo "  17. mu_equal: Structural equality function exists"
echo ""

if [ $FAILED -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "✅ PASS: Semantic purity audit passed (self-hosting ready)"
    exit 0
elif [ $FAILED -eq 0 ]; then
    echo "⚠️  PASS WITH WARNINGS: $WARNINGS warnings (review recommended)"
    exit 0
else
    echo "❌ FAIL: Semantic purity audit failed"
    exit 1
fi
