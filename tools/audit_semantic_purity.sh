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

RESERVED_OPS="STALL FIX ROUTE CLOSE"
for op in $RESERVED_OPS; do
    op_lower=$(echo "$op" | tr '[:upper:]' '[:lower:]')
    if grep -n "def op_${op_lower}" rcx_pi/bytecode_vm.py 2>/dev/null | grep -v "Reserved"; then
        echo "  ERROR: Reserved opcode $op has implementation (should be blocked until v1)"
        FAILED=1
    fi
done

if [ $FAILED -eq 0 ]; then
    echo "  ✓ Reserved opcodes (STALL/FIX/ROUTE/CLOSE) remain unimplemented"
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
echo "  7. Reserved opcodes: Unimplemented"
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
