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
# 18. Host Smuggling Detection (Comprehensive)
# -----------------------------------------------------------------------------
echo "== 18. Host Smuggling: Comprehensive Detection =="

# 18a. Host Arithmetic in eval_seed.py
echo ""
echo "  18a. Host Arithmetic (+, -, *, /, % on values):"
if [ -f "rcx_pi/eval_seed.py" ]; then
    # Look for arithmetic on variables (not in comments, not in strings, not in docstrings)
    # Pattern: variable + variable or variable + number (actual arithmetic)
    ARITH_HITS=$(grep -nE "=[[:space:]]*[a-z_]+[[:space:]]*[\+\-\*/%][[:space:]]*[a-z_0-9]+" rcx_pi/eval_seed.py 2>/dev/null | \
        grep -v "^[[:space:]]*#" | \
        grep -v '"""' | \
        grep -v "WARNINGS" | \
        grep -v "@host" || true)
    if [ -n "$ARITH_HITS" ]; then
        echo "    WARNING: Possible host arithmetic found:"
        echo "$ARITH_HITS" | head -5 | while read line; do echo "      $line"; done
        WARNINGS=$((WARNINGS + 1))
    else
        echo "    ✓ No obvious host arithmetic in eval_seed.py"
    fi
fi

# 18b. Host Builtins in eval_seed.py
echo ""
echo "  18b. Host Builtins (len, sorted, sum, max, min, abs, round):"
if [ -f "rcx_pi/eval_seed.py" ]; then
    BUILTIN_HITS=$(grep -nE "\b(len|sorted|sum|max|min|abs|round|enumerate|zip|map|filter|reduce)\s*\(" rcx_pi/eval_seed.py 2>/dev/null | \
        grep -v "^[[:space:]]*#" || true)
    if [ -n "$BUILTIN_HITS" ]; then
        echo "    WARNING: Host builtins found (should be structural):"
        echo "$BUILTIN_HITS" | while read line; do echo "      $line"; done
        WARNINGS=$((WARNINGS + 1))
    else
        echo "    ✓ No suspicious host builtins in eval_seed.py"
    fi
fi

# 18c. Host String Operations
echo ""
echo "  18c. Host String Ops (.split, .join, .format, .replace, .strip):"
if [ -f "rcx_pi/eval_seed.py" ]; then
    STRING_HITS=$(grep -nE "\.(split|join|format|replace|strip|upper|lower|startswith|endswith)\s*\(" rcx_pi/eval_seed.py 2>/dev/null | \
        grep -v "^[[:space:]]*#" || true)
    if [ -n "$STRING_HITS" ]; then
        echo "    WARNING: Host string operations found:"
        echo "$STRING_HITS" | while read line; do echo "      $line"; done
        WARNINGS=$((WARNINGS + 1))
    else
        echo "    ✓ No host string operations in eval_seed.py"
    fi
fi

# 18d. Host Mutation
echo ""
echo "  18d. Host Mutation (.append, .pop, .extend, .clear, del, []=):"
if [ -f "rcx_pi/eval_seed.py" ]; then
    MUTATION_HITS=$(grep -nE "\.(append|pop|extend|clear|insert|remove)\s*\(|del\s+[a-z]|\[[a-z_]+\]\s*=" rcx_pi/eval_seed.py 2>/dev/null | \
        grep -v "^[[:space:]]*#" | \
        grep -v "__slots__" || true)
    if [ -n "$MUTATION_HITS" ]; then
        echo "    WARNING: Host mutation found (RCX should be immutable):"
        echo "$MUTATION_HITS" | while read line; do echo "      $line"; done
        WARNINGS=$((WARNINGS + 1))
    else
        echo "    ✓ No host mutation in eval_seed.py"
    fi
fi

# 18e. Host Comparison for Logic
echo ""
echo "  18e. Host Comparison (<, >, <=, >= for logic, not validation):"
if [ -f "rcx_pi/eval_seed.py" ]; then
    # This is tricky - < > are OK for validation, not for logic
    COMPARE_HITS=$(grep -nE "[a-z_]+\s*[<>]=?\s*[a-z_0-9]+" rcx_pi/eval_seed.py 2>/dev/null | \
        grep -v "^[[:space:]]*#" | \
        grep -v "# validation" | \
        grep -v "# guardrail" | \
        grep -v "@host" || true)
    if [ -n "$COMPARE_HITS" ]; then
        echo "    INFO: Possible host comparison (review if logic vs validation):"
        echo "$COMPARE_HITS" | head -3 | while read line; do echo "      $line"; done
        # Don't increment warnings - needs manual review
    else
        echo "    ✓ No obvious host comparison in eval_seed.py"
    fi
fi

# 18f. Host Control Flow for Logic
echo ""
echo "  18f. Host Control Flow (if/elif with value-based decisions):"
if [ -f "rcx_pi/eval_seed.py" ]; then
    CONTROL_HITS=$(grep -nE "if\s+[a-z_]+\s*==\s*[0-9'\"]" rcx_pi/eval_seed.py 2>/dev/null | \
        grep -v "^[[:space:]]*#" | \
        grep -v "NO_MATCH" || true)
    if [ -n "$CONTROL_HITS" ]; then
        echo "    INFO: Possible host control flow (value-based if):"
        echo "$CONTROL_HITS" | head -3 | while read line; do echo "      $line"; done
    else
        echo "    ✓ No obvious value-based control flow in eval_seed.py"
    fi
fi

# 18g. Host set() operations
echo ""
echo "  18g. Host set() Operations (should be structural comparison):"
if [ -f "rcx_pi/eval_seed.py" ]; then
    SET_HITS=$(grep -nE "\bset\s*\(" rcx_pi/eval_seed.py 2>/dev/null | \
        grep -v "^[[:space:]]*#" | grep -v "@host" || true)
    if [ -n "$SET_HITS" ]; then
        echo "    WARNING: Host set() found:"
        echo "$SET_HITS" | while read line; do echo "      $line"; done
        WARNINGS=$((WARNINGS + 1))
    else
        echo "    ✓ No set() operations in eval_seed.py"
    fi
fi

# 18h. Host any()/all() aggregation
echo ""
echo "  18h. Host any()/all() Aggregation:"
if [ -f "rcx_pi/eval_seed.py" ]; then
    AGG_HITS=$(grep -nE "\b(any|all)\s*\(" rcx_pi/eval_seed.py 2>/dev/null | \
        grep -v "^[[:space:]]*#" | grep -v "@host" || true)
    if [ -n "$AGG_HITS" ]; then
        echo "    WARNING: Host aggregation found:"
        echo "$AGG_HITS" | while read line; do echo "      $line"; done
        WARNINGS=$((WARNINGS + 1))
    else
        echo "    ✓ No any()/all() in eval_seed.py"
    fi
fi

# 18i. List/Dict comprehensions (host iteration)
echo ""
echo "  18i. Host Comprehensions (list/dict iteration):"
if [ -f "rcx_pi/eval_seed.py" ]; then
    COMP_HITS=$(grep -nE "\[.*for.*in.*\]|\{.*:.*for.*in.*\}" rcx_pi/eval_seed.py 2>/dev/null | \
        grep -v "^[[:space:]]*#" | grep -v "@host" || true)
    if [ -n "$COMP_HITS" ]; then
        echo "    WARNING: Host comprehensions found:"
        echo "$COMP_HITS" | while read line; do echo "      $line"; done
        WARNINGS=$((WARNINGS + 1))
    else
        echo "    ✓ No comprehensions in eval_seed.py"
    fi
fi

# 18j. Host-specific libraries (itertools, functools, os, sys, etc.)
echo ""
echo "  18j. Host Libraries (itertools, functools, os, sys, random, datetime):"
SEED_FILES="rcx_pi/eval_seed.py rcx_pi/kernel.py"
LIB_HITS=""
for f in $SEED_FILES; do
    if [ -f "$f" ]; then
        hits=$(grep -nE "^import (itertools|functools|os|sys|random|datetime|collections)|^from (itertools|functools|os|sys|random|datetime|collections)" "$f" 2>/dev/null || true)
        if [ -n "$hits" ]; then
            LIB_HITS="$LIB_HITS$f: $hits\n"
        fi
    fi
done
if [ -n "$LIB_HITS" ]; then
    echo "    WARNING: Host-specific libraries imported:"
    echo -e "$LIB_HITS" | while read line; do [ -n "$line" ] && echo "      $line"; done
    WARNINGS=$((WARNINGS + 1))
else
    echo "    ✓ No host-specific library imports in kernel/seed code"
fi

# 18k. Non-deterministic behavior (random, time, uuid, etc.)
echo ""
echo "  18k. Non-Deterministic Operations (random, time.time, uuid, datetime.now):"
for f in $SEED_FILES; do
    if [ -f "$f" ]; then
        NONDET_HITS=$(grep -nE "random\.|time\.time|uuid\.|datetime\.now|os\.urandom" "$f" 2>/dev/null | \
            grep -v "^[[:space:]]*#" || true)
        if [ -n "$NONDET_HITS" ]; then
            echo "    ERROR: Non-deterministic operation in $f:"
            echo "$NONDET_HITS" | while read line; do echo "      $line"; done
            FAILED=1
        fi
    fi
done
if [ $FAILED -eq 0 ]; then
    echo "    ✓ No non-deterministic operations in kernel/seed code"
fi

# 18l. Debug statements (print, pdb, breakpoint)
echo ""
echo "  18l. Debug Statements (print, pdb, breakpoint, logging):"
for f in $SEED_FILES; do
    if [ -f "$f" ]; then
        DEBUG_HITS=$(grep -nE "^\s*print\s*\(|^\s*pdb\.|^\s*breakpoint\s*\(|^\s*logging\." "$f" 2>/dev/null || true)
        if [ -n "$DEBUG_HITS" ]; then
            echo "    WARNING: Debug statements in $f:"
            echo "$DEBUG_HITS" | while read line; do echo "      $line"; done
            WARNINGS=$((WARNINGS + 1))
        fi
    fi
done
if [ $WARNINGS -eq 0 ]; then
    echo "    ✓ No debug statements in kernel/seed code"
fi

echo ""

# -----------------------------------------------------------------------------
# 19. Host Debt Threshold (Anti-Boiling-Frog Guardrail)
# -----------------------------------------------------------------------------
echo "== 19. Host Debt: Threshold Check =="

# Count ALL debt markers (host operations + deferred reviews)
# DEBT POLICY (RATCHET):
# - Threshold is a CEILING that can only go DOWN, never up
# - When debt is reduced, threshold MUST be lowered to match
# - To add new debt, you must first reduce existing debt below threshold
# - Deferred reviews ("PHASE 3 REVIEW") count as debt to prevent silent accumulation
#
# UPDATE THIS when debt is paid down:
# - Phase 2 start: 5 host + 1 review = 6
# - After Phase 3: 0 (self-hosting complete)
DEBT_THRESHOLD=6  # <-- RATCHET: Lower this as debt is paid, never raise it

echo "Counting all debt markers..."

# Host operation debt (@host_* decorators)
RECURSION_COUNT=$(grep -rE "^[[:space:]]*@host_recursion" rcx_pi/ --include="*.py" 2>/dev/null | wc -l | tr -d ' ')
ARITHMETIC_COUNT=$(grep -rE "^[[:space:]]*@host_arithmetic" rcx_pi/ --include="*.py" 2>/dev/null | wc -l | tr -d ' ')
BUILTIN_COUNT=$(grep -rE "^[[:space:]]*@host_builtin" rcx_pi/ --include="*.py" 2>/dev/null | wc -l | tr -d ' ')
MUTATION_COUNT=$(grep -rE "^[[:space:]]*@host_mutation" rcx_pi/ --include="*.py" 2>/dev/null | wc -l | tr -d ' ')
COMPARISON_COUNT=$(grep -rE "^[[:space:]]*@host_comparison" rcx_pi/ --include="*.py" 2>/dev/null | wc -l | tr -d ' ')
STRING_COUNT=$(grep -rE "^[[:space:]]*@host_string_op" rcx_pi/ --include="*.py" 2>/dev/null | wc -l | tr -d ' ')

HOST_DEBT=$((RECURSION_COUNT + ARITHMETIC_COUNT + BUILTIN_COUNT + MUTATION_COUNT + COMPARISON_COUNT + STRING_COUNT))

# Deferred review debt (PHASE 3 REVIEW markers)
# These are items we've consciously deferred but MUST address - they're debt too
REVIEW_COUNT=$(grep -rE "PHASE [0-9]+ REVIEW:" rcx_pi/ --include="*.py" 2>/dev/null | wc -l | tr -d ' ')

TOTAL_DEBT=$((HOST_DEBT + REVIEW_COUNT))

echo "  Host operation debt (@host_* decorators):"
echo "    @host_recursion:  $RECURSION_COUNT"
echo "    @host_arithmetic: $ARITHMETIC_COUNT"
echo "    @host_builtin:    $BUILTIN_COUNT"
echo "    @host_mutation:   $MUTATION_COUNT"
echo "    @host_comparison: $COMPARISON_COUNT"
echo "    @host_string_op:  $STRING_COUNT"
echo "    ─────────────────────"
echo "    Host subtotal:    $HOST_DEBT"
echo ""
echo "  Deferred review debt (PHASE N REVIEW markers):"
echo "    Review markers:   $REVIEW_COUNT"
echo "    ─────────────────────"
echo "    TOTAL DEBT:       $TOTAL_DEBT (threshold: $DEBT_THRESHOLD)"
echo ""

if [ "$TOTAL_DEBT" -gt "$DEBT_THRESHOLD" ]; then
    echo "  ERROR: Debt exceeds threshold ($TOTAL_DEBT > $DEBT_THRESHOLD)"
    echo "  POLICY: To add new debt, you must first reduce existing debt."
    echo "  The threshold is a RATCHET - it can only go down, never up."
    FAILED=1
elif [ "$TOTAL_DEBT" -lt "$DEBT_THRESHOLD" ]; then
    echo "  DEBT REDUCED! Current ($TOTAL_DEBT) < threshold ($DEBT_THRESHOLD)"
    echo "  ACTION REQUIRED: Lower DEBT_THRESHOLD in audit_semantic_purity.sh to $TOTAL_DEBT"
    echo "  (The ratchet must be tightened when debt is paid)"
    FAILED=1  # Force update of threshold
elif [ "$TOTAL_DEBT" -eq "$DEBT_THRESHOLD" ] && [ "$TOTAL_DEBT" -gt 0 ]; then
    echo "  AT CEILING: $TOTAL_DEBT markers = threshold (no room for new debt)"
    echo "  To add new debt, first eliminate existing debt."
    echo "  When debt is paid, threshold MUST be lowered (ratchet)."
    WARNINGS=$((WARNINGS + 1))
else
    echo "  ✓ ZERO debt markers - self-hosting ready!"
fi

echo ""

# -----------------------------------------------------------------------------
# 20. Guardrail Coverage (New File Detection)
# -----------------------------------------------------------------------------
echo "== 20. Guardrail Coverage: New File Detection =="

echo "Checking for Python files in rcx_pi/ not covered by audits..."

# List of files we explicitly audit
AUDITED_FILES="eval_seed.py kernel.py mu_type.py"

# Find all .py files in rcx_pi/ (excluding __pycache__)
ALL_PY_FILES=$(find rcx_pi -maxdepth 1 -name "*.py" -type f 2>/dev/null | xargs -I{} basename {} | sort)

UNAUDITED=""
for f in $ALL_PY_FILES; do
    # Skip __init__.py
    if [ "$f" = "__init__.py" ]; then
        continue
    fi

    # Check if it's in our audited list or is legacy/infrastructure
    case "$f" in
        # Explicitly audited (self-hosting critical)
        eval_seed.py|kernel.py|mu_type.py)
            ;;
        # Legacy/infrastructure - not self-hosting critical
        bytecode_vm.py|programs.py|rcx_cli.py)
            ;;
        trace_*.py|rule_motifs*.py|replay*.py|execution*.py)
            ;;
        # Utilities and CLI tools
        api.py|bench.py|cli_schema*.py|higher.py|listutils.py|meta.py|pretty.py)
            ;;
        program_*.py|projection.py|self_host.py|test_worlds_probe.py|worlds_json.py|worlds_bridge.py|worlds_probe.py)
            ;;
        *)
            # New file - needs review
            UNAUDITED="$UNAUDITED $f"
            ;;
    esac
done

if [ -n "$UNAUDITED" ]; then
    echo "  WARNING: New files found that may need audit coverage:"
    for f in $UNAUDITED; do
        echo "    - rcx_pi/$f"
    done
    echo "  Action: Add to AUDITED_FILES list or mark as legacy/infrastructure"
    WARNINGS=$((WARNINGS + 1))
else
    echo "  ✓ All logic files in rcx_pi/ are covered by audits"
fi

echo ""

# -----------------------------------------------------------------------------
# 21. Self-Hosting Readiness Checklist
# -----------------------------------------------------------------------------
echo "== 21. Self-Hosting Readiness Checklist =="

echo ""
echo "  Pre-merge checklist for kernel/seed changes:"
echo "  ┌─────────────────────────────────────────────────────────────────┐"
echo "  │ □ No new @host_* markers without reducing existing debt        │"
echo "  │ □ No Python-specific optimizations (use simple abstractions)   │"
echo "  │ □ No new imports from itertools/functools/os/sys/random        │"
echo "  │ □ No print/pdb/breakpoint left in code                         │"
echo "  │ □ All new functions reviewed for host operations               │"
echo "  │ □ Non-deterministic behavior explicitly wrapped                │"
echo "  │ □ Tests don't mask host dependencies                           │"
echo "  └─────────────────────────────────────────────────────────────────┘"
echo ""
echo "  Reviewer questions for PRs touching rcx_pi/kernel.py or eval_seed.py:"
echo "  ┌─────────────────────────────────────────────────────────────────┐"
echo "  │ 1. Could this logic be expressed as projections?               │"
echo "  │ 2. Does this use Python iteration where kernel loop would do?  │"
echo "  │ 3. Does this add host computation without a debt marker?       │"
echo "  │ 4. Does this increase the debt count?                          │"
echo "  └─────────────────────────────────────────────────────────────────┘"
echo ""

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
echo "  18. Host smuggling: Comprehensive (arithmetic, builtins, mutation, set, any/all, comprehensions, libraries, non-det, debug)"
echo "  19. Host debt: Threshold check (current debt vs maximum allowed)"
echo "  20. Guardrail coverage: New file detection (ensures no unaudited code)"
echo "  21. Self-hosting checklist: Pre-merge and reviewer guidelines"
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
