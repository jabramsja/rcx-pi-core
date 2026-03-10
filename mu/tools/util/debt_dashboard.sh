#!/usr/bin/env bash
# RCX Host Debt Dashboard
# Shows all host dependencies that need to be eliminated for self-hosting
#
# Usage: ./tools/debt_dashboard.sh [--json]

set -euo pipefail

JSON_OUTPUT=false
if [ "${1:-}" = "--json" ]; then
    JSON_OUTPUT=true
fi

# Count markers (uses extended regex for flexibility)
count_markers() {
    local pattern="$1"
    local dir="$2"
    local include_glob="${3:-*.py}"
    local count
    count=$(grep -rE "$pattern" "$dir" --include="$include_glob" 2>/dev/null | grep -v __pycache__ | wc -l | tr -d '[:space:]') || count=0
    echo "${count:-0}"
}

count_loc_lines() {
    local dir="$1"
    local include_glob="$2"
    local exclude_path="${3:-}"
    local count=0
    local file
    local lines

    if [ ! -d "$dir" ]; then
        echo "0"
        return
    fi

    if [ -n "$exclude_path" ]; then
        while IFS= read -r -d '' file; do
            lines=$(wc -l < "$file" | tr -d '[:space:]')
            count=$((count + lines))
        done < <(find "$dir" -type f -name "$include_glob" ! -path "$exclude_path" -print0)
    else
        while IFS= read -r -d '' file; do
            lines=$(wc -l < "$file" | tr -d '[:space:]')
            count=$((count + lines))
        done < <(find "$dir" -type f -name "$include_glob" -print0)
    fi

    echo "$count"
}

# Read infra ceiling from STATUS.md (single source of truth)
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
cd "$PROJECT_ROOT"
INFRA_CEILING=$(grep "^INFRA_CEILING:" "$PROJECT_ROOT/STATUS.md" 2>/dev/null | head -1 | cut -d: -f2 | awk '{print $1}')
INFRA_CEILING=${INFRA_CEILING:-35}  # Default to 35 if not found

# Core Python debt markers (stable existing semantics)
# Use anchored patterns (^[[:space:]]*@) to match actual decorators only
# Comment mentions (# @host_*) are documentation, not counted as debt
HOST_RECURSION=$(count_markers "^[[:space:]]*@host_recursion" "rcx_pi/")
HOST_BUILTIN=$(count_markers "^[[:space:]]*@host_builtin" "rcx_pi/")
HOST_ITERATION=$(count_markers "^[[:space:]]*@host_iteration" "rcx_pi/")
HOST_MUTATION=$(count_markers "^[[:space:]]*@host_mutation" "rcx_pi/")
BOOTSTRAP=$(count_markers "^[[:space:]]*@bootstrap_only" "rcx_pi/")
AST_OK_BOOTSTRAP=$(count_markers "# AST_OK:[[:space:]]*bootstrap" "rcx_pi/")
AST_OK_INFRA=$(count_markers "# AST_OK:[[:space:]]*infra" "rcx_pi/")
TOTAL_TRACKED=$((HOST_RECURSION + HOST_BUILTIN + HOST_ITERATION + HOST_MUTATION + BOOTSTRAP))
TOTAL_SEMANTIC=$((TOTAL_TRACKED + AST_OK_BOOTSTRAP))

# JavaScript debt markers
JS_DIR="mu/host/js"
JS_ITERATION=$(count_markers "@host_iteration" "$JS_DIR" "*.js")
JS_RECURSION=$(count_markers "@host_recursion" "$JS_DIR" "*.js")
JS_BUILTIN=$(count_markers "@host_builtin" "$JS_DIR" "*.js")
JS_BOOTSTRAP=$(count_markers "BOOTSTRAP_PRIMITIVE" "$JS_DIR" "*.js")
JS_TOTAL=$((JS_ITERATION + JS_RECURSION + JS_BUILTIN))

# Additive host-surface visibility metrics (no change to legacy debt math)
HOST_RUNTIME_LOC_PY=$(count_loc_lines "rcx_pi/selfhost" "*.py")
HOST_RUNTIME_LOC_JS=$(count_loc_lines "$JS_DIR" "*.js" "$JS_DIR/tests/*")
HOST_TEST_LOC_JS=$(count_loc_lines "$JS_DIR/tests" "*.js")
HOST_RUNTIME_LOC_TOTAL=$((HOST_RUNTIME_LOC_PY + HOST_RUNTIME_LOC_JS))
AST_OK_TOTAL_PY=$(count_markers "# AST_OK:" "rcx_pi/" "*.py")
AST_OK_TOTAL_JS=$(count_markers "AST_OK_JS:" "$JS_DIR" "*.js")
AST_OK_TOTAL_HOST=$((AST_OK_TOTAL_PY + AST_OK_TOTAL_JS))

if [ "$JSON_OUTPUT" = true ]; then
    # JSON output for programmatic use
    cat <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "debt": {
    "host_recursion": $HOST_RECURSION,
    "host_builtin": $HOST_BUILTIN,
    "host_iteration": $HOST_ITERATION,
    "host_mutation": $HOST_MUTATION,
    "bootstrap_only": $BOOTSTRAP,
    "ast_ok_bootstrap": $AST_OK_BOOTSTRAP,
    "ast_ok_infra": $AST_OK_INFRA,
    "ast_ok_infra_ceiling": $INFRA_CEILING,
    "total_tracked": $TOTAL_TRACKED,
    "total_semantic": $TOTAL_SEMANTIC,
    "js_iteration": $JS_ITERATION,
    "js_recursion": $JS_RECURSION,
    "js_builtin": $JS_BUILTIN,
    "js_bootstrap_primitives": $JS_BOOTSTRAP,
    "js_total": $JS_TOTAL,
    "host_runtime_loc_py": $HOST_RUNTIME_LOC_PY,
    "host_runtime_loc_js": $HOST_RUNTIME_LOC_JS,
    "host_test_loc_js": $HOST_TEST_LOC_JS,
    "host_runtime_loc_total": $HOST_RUNTIME_LOC_TOTAL,
    "ast_ok_total_py": $AST_OK_TOTAL_PY,
    "ast_ok_total_js": $AST_OK_TOTAL_JS,
    "ast_ok_total_host": $AST_OK_TOTAL_HOST
  }
}
EOF
else
    # Human-readable output
    echo "=============================================="
    echo "       RCX Host Debt Dashboard"
    echo "=============================================="
    echo ""
    echo "Tracked Markers (rcx_pi/) - @host_* decorators"
    echo "----------------------------------------------"

    printf "  @host_recursion:  %3d\n" "$HOST_RECURSION"
    printf "  @host_builtin:    %3d\n" "$HOST_BUILTIN"
    printf "  @host_iteration:  %3d\n" "$HOST_ITERATION"
    printf "  @host_mutation:   %3d\n" "$HOST_MUTATION"
    printf "  @bootstrap_only:  %3d\n" "$BOOTSTRAP"

    echo "----------------------------------------------"
    printf "  Total Tracked:    %3d (ceiling: 13)\n" "$TOTAL_TRACKED"
    echo ""

    echo "AST_OK Bypasses (rcx_pi/) - Statement-level semantic debt"
    echo "----------------------------------------------"

    printf "  # AST_OK: bootstrap: %3d (semantic debt)\n" "$AST_OK_BOOTSTRAP"
    printf "  # AST_OK: infra:     %3d (scaffolding, ceiling: %d)\n" "$AST_OK_INFRA" "$INFRA_CEILING"
    echo "----------------------------------------------"
    printf "  Total Semantic:   %3d (tracked + bootstrap)\n" "$TOTAL_SEMANTIC"

    # Warn if infra ceiling exceeded (prevents unbounded accumulation)
    if [ "$AST_OK_INFRA" -gt "$INFRA_CEILING" ]; then
        echo ""
        echo "WARNING: AST_OK:infra ($AST_OK_INFRA) exceeds ceiling ($INFRA_CEILING)"
        echo "         Review and reduce scaffolding markers before adding more."
    fi
    echo ""

    echo "JavaScript Guardrails (L3 Parity Enforcement)"
    echo "----------------------------------------------"
    # Check that all JS guardrail scripts exist and are executable
    JS_GUARDS=("checks/check_js_debt.sh" "checks/linters/contraband_js.sh" "checks/linters/ast_police_js.sh" "checks/check_test_theater_js.sh" "checks/linters/seed_police.sh")
    for guard in "${JS_GUARDS[@]}"; do
        if [ -x "tools/$guard" ]; then
            printf "  ✓ %s\\n" "$guard"
        else
            printf "  ✗ %s MISSING or not executable\\n" "$guard"
        fi
    done
    echo ""

    echo "JavaScript Debt (mu/host/js/) - L3 Parity"
    echo "----------------------------------------------"
    if [ -d "$JS_DIR" ]; then
        printf "  @host_iteration:     %3d (header + inline markers)\n" "$JS_ITERATION"
        printf "  @host_recursion:     %3d (header + inline markers)\n" "$JS_RECURSION"
        printf "  @host_builtin:       %3d (header + inline markers)\n" "$JS_BUILTIN"
        printf "  BOOTSTRAP_PRIMITIVE: %3d (4 active + 1 eliminated)\n" "$JS_BOOTSTRAP"
        echo "----------------------------------------------"

        # Check JS debt markers exist
        if [ "$JS_BOOTSTRAP" -lt 5 ]; then
            echo "  WARNING: Missing BOOTSTRAP_PRIMITIVE markers ($JS_BOOTSTRAP < 5)"
        elif [ "$JS_ITERATION" -lt 6 ] || [ "$JS_RECURSION" -lt 4 ] || [ "$JS_BUILTIN" -lt 2 ]; then
            echo "  WARNING: Missing @host_* markers"
        else
            echo "  OK: JS debt markers present (same bootstrap as Python)"
        fi

        # Quick JS test check
        if node "$JS_DIR/eval_step.js" 2>&1 | grep -q "All tests passed: true"; then
            echo "  OK: JS tests pass"
        else
            echo "  WARNING: JS tests may be failing"
        fi
    else
        echo "  WARNING: $JS_DIR not found"
    fi
    echo ""

    echo "Host Surface Visibility (Additive Metrics)"
    echo "----------------------------------------------"
    printf "  host_runtime_loc_py:     %4d\n" "$HOST_RUNTIME_LOC_PY"
    printf "  host_runtime_loc_js:     %4d\n" "$HOST_RUNTIME_LOC_JS"
    printf "  host_test_loc_js:        %4d\n" "$HOST_TEST_LOC_JS"
    printf "  host_runtime_loc_total:  %4d\n" "$HOST_RUNTIME_LOC_TOTAL"
    printf "  ast_ok_total_py:         %4d\n" "$AST_OK_TOTAL_PY"
    printf "  ast_ok_total_js:         %4d\n" "$AST_OK_TOTAL_JS"
    printf "  ast_ok_total_host:       %4d\n" "$AST_OK_TOTAL_HOST"
    if [ "$AST_OK_TOTAL_JS" -eq 0 ]; then
        echo "  (ast_ok_total_js=0 is expected baseline; JS has no AST_OK_JS markers yet)"
    fi
    echo ""

    # Show locations if there's semantic debt
    if [ "$TOTAL_SEMANTIC" -gt 0 ]; then
        echo "Semantic Debt Locations:"
        echo "----------------------------------------------"
        grep -rn "@host_recursion\|@host_builtin\|@host_iteration\|@host_mutation\|@bootstrap_only\|# AST_OK: bootstrap" rcx_pi/ 2>/dev/null | head -25 || true
        echo ""
    fi

    # Summary
    echo "=============================================="
    if [ "$TOTAL_SEMANTIC" -eq 0 ]; then
        echo "SELF-HOSTING READY: No semantic debt!"
    else
        echo "SEMANTIC DEBT: $TOTAL_SEMANTIC (tracked: $TOTAL_TRACKED, AST_OK bootstrap: $AST_OK_BOOTSTRAP)"
        echo "Note: ~289 lines unmarked debt not counted (see DebtCategories.v0.md)"
    fi
    echo "=============================================="
fi
