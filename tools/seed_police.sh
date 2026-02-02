#!/usr/bin/env bash
# RCX Seed Police
# Validates seed JSON files for structural integrity and theater detection
#
# Usage: ./tools/seed_police.sh [seed_dir]
#        Default: checks both seeds/ (legacy) and mu/ (new structure)
#
# Checks:
#   1. Structure: Required fields (id, pattern, body)
#   2. Theater: Empty patterns, trivial bodies, duplicate IDs
#   3. Host leakage: Python/JS-specific patterns in seeds
#   4. Security: Reserved field misuse, injection patterns

set -euo pipefail

# If specific directory given, use that; otherwise check both seeds/ and mu/
if [ -n "${1:-}" ]; then
    SEED_DIRS=("$1")
else
    SEED_DIRS=()
    [ -d "seeds" ] && SEED_DIRS+=("seeds")
    [ -d "mu" ] && SEED_DIRS+=("mu/substrate" "mu/closures" "mu/programs" "mu/utilities")
fi

if [ ${#SEED_DIRS[@]} -eq 0 ]; then
    echo "ERROR: No seed directories found"
    exit 1
fi

echo "Seed Police inspecting: ${SEED_DIRS[*]}"
echo "   Checking: structure, theater, host leakage, security"
echo ""

ERRORS=0
WARNINGS=0

# Check each JSON seed file in all directories
for SEED_DIR in "${SEED_DIRS[@]}"; do
  [ -d "$SEED_DIR" ] || continue
  for seed_file in "$SEED_DIR"/*.json; do
    [ -f "$seed_file" ] || continue

    filename=$(basename "$seed_file")
    echo "-- $filename"

    # 1. Basic JSON validity
    # SECURITY: Use sys.argv to pass filename, NOT string interpolation (code injection risk)
    if ! python3 -c "import json, sys; json.load(open(sys.argv[1]))" "$seed_file" 2>/dev/null; then
        echo "  ✗ INVALID JSON: Parse error"
        ERRORS=$((ERRORS + 1))
        continue
    fi

    # 2. Required structure: must have "projections" array
    # SECURITY: Use sys.argv to pass filename, NOT string interpolation
    if ! python3 -c "
import json, sys
data = json.load(open(sys.argv[1]))
assert 'projections' in data, 'Missing projections key'
assert isinstance(data['projections'], list), 'projections must be list'
" "$seed_file" 2>/dev/null; then
        echo "  ✗ STRUCTURE: Missing or invalid 'projections' array"
        ERRORS=$((ERRORS + 1))
        continue
    fi

    # 3. Check each projection for required fields and theater
    # SECURITY: Pass filename as argument, not in heredoc (prevents code injection)
    python3 - "$seed_file" << 'EOF'
import json
import sys

data = json.load(open(sys.argv[1]))
projections = data.get('projections', [])
errors = 0
warnings = 0
seen_ids = set()

for i, proj in enumerate(projections):
    loc = f"projection[{i}]"

    # Required fields
    if 'id' not in proj:
        print(f"  ✗ STRUCTURE: {loc} missing 'id'")
        errors += 1
    else:
        pid = proj['id']
        if pid in seen_ids:
            print(f"  ✗ THEATER: Duplicate projection id '{pid}'")
            errors += 1
        seen_ids.add(pid)

    if 'pattern' not in proj:
        print(f"  ✗ STRUCTURE: {loc} missing 'pattern'")
        errors += 1

    if 'body' not in proj:
        print(f"  ✗ STRUCTURE: {loc} missing 'body'")
        errors += 1

    # Theater detection: empty or trivial patterns/bodies
    pattern = proj.get('pattern')
    body = proj.get('body')

    # Empty pattern (matches nothing meaningful)
    if pattern == {} or pattern == []:
        print(f"  ✗ THEATER: {loc} has empty pattern (matches nothing)")
        errors += 1

    # Pattern equals body exactly (identity projection - suspicious)
    if pattern == body and pattern is not None:
        # Exception: wrap projections legitimately return their input
        pid = proj.get('id', '')
        if 'wrap' not in pid and 'init' not in pid:
            print(f"  ? WARNING: {loc} pattern === body (identity projection)")
            warnings += 1

    # Body is just null (no transformation)
    if body is None and proj.get('id', '').endswith('.done') is False:
        # Exception: some terminal projections legitimately return null
        pid = proj.get('id', '')
        if not any(x in pid for x in ['end', 'done', 'fail', 'null', 'empty']):
            print(f"  ? WARNING: {loc} body is null (no transformation)")
            warnings += 1

# Host leakage detection in string values
def check_host_leakage(obj, path=""):
    global errors
    if isinstance(obj, str):
        # Python-specific
        if 'lambda' in obj.lower():
            print(f"  ✗ HOST LEAK: '{path}' contains 'lambda'")
            errors += 1
        if 'def ' in obj:
            print(f"  ✗ HOST LEAK: '{path}' contains 'def '")
            errors += 1
        # Block dunders (__class__, __init__, etc.) - _mode is fine (no double underscore)
        # Exception: _marker field VALUES can be dunders for security tokens
        # SECURITY FIX (9-agent adversary finding 2026-01-30):
        # Only allow dunders if the IMMEDIATE parent key is "_marker" (not deep in path)
        # e.g., "_marker" value can be "__done__" but "_marker.__class__" is blocked
        parent_is_marker = path.endswith('._marker') or path == '_marker'
        if '__' in obj and not parent_is_marker:
            print(f"  ✗ HOST LEAK: '{path}' contains dunder")
            errors += 1
        # JS-specific
        if 'function(' in obj or 'function (' in obj:
            print(f"  ✗ HOST LEAK: '{path}' contains 'function'")
            errors += 1
        if '=>' in obj:
            print(f"  ✗ HOST LEAK: '{path}' contains arrow function")
            errors += 1
        if 'eval(' in obj:
            print(f"  ✗ HOST LEAK: '{path}' contains 'eval'")
            errors += 1
    elif isinstance(obj, dict):
        for k, v in obj.items():
            check_host_leakage(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            check_host_leakage(v, f"{path}[{i}]")

for i, proj in enumerate(projections):
    check_host_leakage(proj, f"projections[{i}]")

# Security: Check for reserved field misuse in patterns
# Patterns shouldn't contain kernel reserved fields as literals (forge attempts)
RESERVED = ['_mode', '_phase', '_input', '_remaining', '_match_ctx', '_subst_ctx',
            '_kernel_ctx', '_status', '_result', '_stall', '_step', '_projs']

import os
seed_filename = os.path.basename(sys.argv[1])  # e.g., "kernel.v1.json"

# SECURITY FIX (9-agent adversary finding 2026-01-30):
# Only allow reserved fields if BOTH:
#   1. The SEED FILE is in the allowed list (kernel.*, match.*, etc.)
#   2. The projection ID matches the seed file's namespace
# This prevents "kernel.trojan" in "evil.v1.json" from using reserved fields
#
# Allowed seed files and their valid projection ID prefixes:
ALLOWED_SEEDS = {
    'kernel': ['kernel.'],           # kernel.v1.json -> kernel.*
    'match': ['match.'],             # match.v1.json, match.v2.json -> match.*
    'subst': ['subst.'],             # subst.v1.json, subst.v2.json -> subst.*
    'enginenews': ['enginenews.'],   # enginenews.v1.json -> enginenews.* (legacy)
    'exhaust': ['exhaust.'],         # exhaust.v1.json -> exhaust.* (legacy)
    'recurrence': ['recurrence.'],   # recurrence.v1.json -> recurrence.* (mu/closures/)
    'exhaustion': ['exhaustion.'],   # exhaustion.v1.json -> exhaustion.* (mu/closures/)
    'rcx_engine': ['engine.'],       # rcx_engine.v1.json -> engine.* (mu/programs/)
}

# Get seed base name (kernel.v1.json -> kernel)
seed_base = seed_filename.split('.')[0]
allowed_prefixes = ALLOWED_SEEDS.get(seed_base, [])

for i, proj in enumerate(projections):
    pattern = proj.get('pattern', {})
    pid = proj.get('id', '')

    # Skip projections that legitimately use reserved fields
    # BOTH conditions must be true:
    # 1. Seed file is in allowed list (kernel.v1.json, match.v2.json, etc.)
    # 2. Projection ID prefix matches allowed prefixes for this seed
    if any(pid.startswith(prefix) for prefix in allowed_prefixes):
        continue

    def check_reserved_in_pattern(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in RESERVED:
                    print(f"  ✗ SECURITY: projections[{i}] pattern contains reserved field '{k}'")
                    return True
                if check_reserved_in_pattern(v, f"{path}.{k}"):
                    return True
        elif isinstance(obj, list):
            for j, item in enumerate(obj):
                if check_reserved_in_pattern(item, f"{path}[{j}]"):
                    return True
        return False

    if check_reserved_in_pattern(pattern):
        errors += 1

if errors > 0:
    sys.exit(1)
print(f"  ✓ OK ({len(projections)} projections, {warnings} warnings)")
EOF

    if [ $? -ne 0 ]; then
        ERRORS=$((ERRORS + 1))
    fi
  done
done

echo ""

# 4. Cross-seed validation: check for ID collisions across seeds
echo "-- Cross-seed ID collision check"
# SECURITY: Pass seed_dirs as arguments, not in heredoc
python3 - "${SEED_DIRS[@]}" << 'EOF'
import json
import os
import sys

seed_dirs = sys.argv[1:]
all_ids = {}
errors = 0

for seed_dir in seed_dirs:
    if not os.path.isdir(seed_dir):
        continue
    for filename in os.listdir(seed_dir):
        if not filename.endswith('.json'):
            continue
        filepath = os.path.join(seed_dir, filename)
        try:
            data = json.load(open(filepath))
            for proj in data.get('projections', []):
                pid = proj.get('id')
                if pid:
                    if pid in all_ids:
                        other_file = all_ids[pid]
                        # Allow same ID across v1/v2 versions of same seed family
                        # e.g., match.v1.json and match.v2.json can both have match.done
                        base1 = filename.replace('.v1.json', '').replace('.v2.json', '')
                        base2 = other_file.replace('.v1.json', '').replace('.v2.json', '')
                        if base1 == base2:
                            continue  # Same family, versioned - OK
                        # Allow renamed seeds (enginenews -> recurrence, exhaust -> exhaustion)
                        # These have different prefixes so no collision
                        print(f"  ✗ ID COLLISION: '{pid}' in both {other_file} and {filename}")
                        errors += 1
                    all_ids[pid] = filename
        except Exception as e:
            pass

if errors == 0:
    print(f"  ✓ OK (no ID collisions across {len(all_ids)} total projections)")
else:
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    ERRORS=$((ERRORS + 1))
fi

echo ""

if [ $ERRORS -gt 0 ]; then
    echo "------------------------------------------------------------"
    echo "❌ Seed Police found $ERRORS error(s)"
    exit 1
fi

echo "------------------------------------------------------------"
echo "✅ Seed Police: All seeds valid"
