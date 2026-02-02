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
    local count
    count=$(grep -rE "$pattern" "$dir" --include="*.py" 2>/dev/null | grep -v __pycache__ | wc -l | tr -d '[:space:]') || count=0
    echo "${count:-0}"
}

# Read infra ceiling from STATUS.md (single source of truth)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
INFRA_CEILING=$(grep "^INFRA_CEILING:" "$PROJECT_ROOT/STATUS.md" 2>/dev/null | head -1 | cut -d: -f2 | awk '{print $1}')
INFRA_CEILING=${INFRA_CEILING:-35}  # Default to 35 if not found

if [ "$JSON_OUTPUT" = true ]; then
    # JSON output for programmatic use
    # Use anchored patterns (^[[:space:]]*@) to match actual decorators only
    # Comment mentions (# @host_*) are documentation, not counted as debt
    HOST_RECURSION=$(count_markers "^[[:space:]]*@host_recursion" "rcx_pi/")
    HOST_BUILTIN=$(count_markers "^[[:space:]]*@host_builtin" "rcx_pi/")
    HOST_ITERATION=$(count_markers "^[[:space:]]*@host_iteration" "rcx_pi/")
    HOST_MUTATION=$(count_markers "^[[:space:]]*@host_mutation" "rcx_pi/")
    BOOTSTRAP=$(count_markers "^[[:space:]]*@bootstrap_only" "rcx_pi/")
    AST_OK_BOOTSTRAP=$(count_markers "# AST_OK:[[:space:]]*bootstrap" "rcx_pi/")
    AST_OK_INFRA=$(count_markers "# AST_OK:[[:space:]]*infra" "rcx_pi/")
    PROTO_BUILTIN=$(count_markers "host_builtin" "prototypes/")
    PROTO_ITERATION=$(count_markers "host_iteration" "prototypes/")
    TOTAL_TRACKED=$((HOST_RECURSION + HOST_BUILTIN + HOST_ITERATION + HOST_MUTATION + BOOTSTRAP))
    TOTAL_SEMANTIC=$((TOTAL_TRACKED + AST_OK_BOOTSTRAP))

    # JavaScript debt
    JS_FILE="substrates/js/eval_step.js"
    JS_ITERATION=$(grep -c "@host_iteration" "$JS_FILE" 2>/dev/null || echo 0)
    JS_RECURSION=$(grep -c "@host_recursion" "$JS_FILE" 2>/dev/null || echo 0)
    JS_BUILTIN=$(grep -c "@host_builtin" "$JS_FILE" 2>/dev/null || echo 0)
    JS_BOOTSTRAP=$(grep -c "BOOTSTRAP_PRIMITIVE" "$JS_FILE" 2>/dev/null || echo 0)
    JS_TOTAL=$((JS_ITERATION + JS_RECURSION + JS_BUILTIN))

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
    "prototype_builtin": $PROTO_BUILTIN,
    "prototype_iteration": $PROTO_ITERATION,
    "total_tracked": $TOTAL_TRACKED,
    "total_semantic": $TOTAL_SEMANTIC,
    "js_iteration": $JS_ITERATION,
    "js_recursion": $JS_RECURSION,
    "js_builtin": $JS_BUILTIN,
    "js_bootstrap_primitives": $JS_BOOTSTRAP,
    "js_total": $JS_TOTAL
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

    # Use anchored patterns (^[[:space:]]*@) to match actual decorators only
    # Comment mentions (# @host_*) are documentation, not counted as debt
    HOST_RECURSION=$(count_markers "^[[:space:]]*@host_recursion" "rcx_pi/")
    HOST_BUILTIN=$(count_markers "^[[:space:]]*@host_builtin" "rcx_pi/")
    HOST_ITERATION=$(count_markers "^[[:space:]]*@host_iteration" "rcx_pi/")
    HOST_MUTATION=$(count_markers "^[[:space:]]*@host_mutation" "rcx_pi/")
    BOOTSTRAP=$(count_markers "^[[:space:]]*@bootstrap_only" "rcx_pi/")

    printf "  @host_recursion:  %3d\n" "$HOST_RECURSION"
    printf "  @host_builtin:    %3d\n" "$HOST_BUILTIN"
    printf "  @host_iteration:  %3d\n" "$HOST_ITERATION"
    printf "  @host_mutation:   %3d\n" "$HOST_MUTATION"
    printf "  @bootstrap_only:  %3d\n" "$BOOTSTRAP"

    TOTAL_TRACKED=$((HOST_RECURSION + HOST_BUILTIN + HOST_ITERATION + HOST_MUTATION + BOOTSTRAP))
    echo "----------------------------------------------"
    printf "  Total Tracked:    %3d (ceiling: 12)\n" "$TOTAL_TRACKED"
    echo ""

    echo "AST_OK Bypasses (rcx_pi/) - Statement-level semantic debt"
    echo "----------------------------------------------"

    AST_OK_BOOTSTRAP=$(count_markers "# AST_OK:[[:space:]]*bootstrap" "rcx_pi/")
    AST_OK_INFRA=$(count_markers "# AST_OK:[[:space:]]*infra" "rcx_pi/")

    printf "  # AST_OK: bootstrap: %3d (semantic debt)\n" "$AST_OK_BOOTSTRAP"
    printf "  # AST_OK: infra:     %3d (scaffolding, ceiling: %d)\n" "$AST_OK_INFRA" "$INFRA_CEILING"
    echo "----------------------------------------------"
    TOTAL_SEMANTIC=$((TOTAL_TRACKED + AST_OK_BOOTSTRAP))
    printf "  Total Semantic:   %3d (tracked + bootstrap)\n" "$TOTAL_SEMANTIC"

    # Warn if infra ceiling exceeded (prevents unbounded accumulation)
    if [ "$AST_OK_INFRA" -gt "$INFRA_CEILING" ]; then
        echo ""
        echo "WARNING: AST_OK:infra ($AST_OK_INFRA) exceeds ceiling ($INFRA_CEILING)"
        echo "         Review and reduce scaffolding markers before adding more."
    fi
    echo ""

    echo "Prototype Debt (prototypes/) - Acceptable during development"
    echo "----------------------------------------------"

    PROTO_BUILTIN=$(count_markers "host_builtin" "prototypes/")
    PROTO_ITERATION=$(count_markers "host_iteration" "prototypes/")
    PROTO_RECURSION=$(count_markers "host_recursion" "prototypes/")

    printf "  host_builtin:     %3d\n" "$PROTO_BUILTIN"
    printf "  host_iteration:   %3d\n" "$PROTO_ITERATION"
    printf "  host_recursion:   %3d\n" "$PROTO_RECURSION"

    PROTO_TOTAL=$((PROTO_BUILTIN + PROTO_ITERATION + PROTO_RECURSION))
    echo "----------------------------------------------"
    printf "  Total Prototype:  %3d (not blocking)\n" "$PROTO_TOTAL"
    echo ""

    echo "JavaScript Guardrails (L3 Parity Enforcement)"
    echo "----------------------------------------------"
    # Check that all JS guardrail scripts exist and are executable
    JS_GUARDS=("check_js_debt.sh" "contraband_js.sh" "ast_police_js.sh" "check_test_theater_js.sh" "seed_police.sh")
    for guard in "${JS_GUARDS[@]}"; do
        if [ -x "tools/$guard" ]; then
            printf "  ✓ %s\\n" "$guard"
        else
            printf "  ✗ %s MISSING or not executable\\n" "$guard"
        fi
    done
    echo ""

    echo "JavaScript Debt (substrates/js/eval_step.js) - L3 Parity"
    echo "----------------------------------------------"
    JS_FILE="substrates/js/eval_step.js"
    if [ -f "$JS_FILE" ]; then
        JS_ITERATION=$(grep -c "@host_iteration" "$JS_FILE" 2>/dev/null || echo 0)
        JS_RECURSION=$(grep -c "@host_recursion" "$JS_FILE" 2>/dev/null || echo 0)
        JS_BUILTIN=$(grep -c "@host_builtin" "$JS_FILE" 2>/dev/null || echo 0)
        JS_BOOTSTRAP=$(grep -c "BOOTSTRAP_PRIMITIVE" "$JS_FILE" 2>/dev/null || echo 0)

        printf "  @host_iteration:     %3d (header + inline markers)\n" "$JS_ITERATION"
        printf "  @host_recursion:     %3d (header + inline markers)\n" "$JS_RECURSION"
        printf "  @host_builtin:       %3d (header + inline markers)\n" "$JS_BUILTIN"
        printf "  BOOTSTRAP_PRIMITIVE: %3d (5 expected)\n" "$JS_BOOTSTRAP"
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
        if node "$JS_FILE" 2>&1 | grep -q "All tests passed: true"; then
            echo "  OK: JS tests pass"
        else
            echo "  WARNING: JS tests may be failing"
        fi
    else
        echo "  WARNING: $JS_FILE not found"
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
