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

if [ "$JSON_OUTPUT" = true ]; then
    # JSON output for programmatic use
    # Use anchored patterns (^[[:space:]]*@) to match actual decorators
    # Also count "# @host_*" comments for nested function debt that can't be decorated
    HOST_RECURSION=$(count_markers "^[[:space:]]*@host_recursion" "rcx_pi/")
    HOST_BUILTIN=$(count_markers "^[[:space:]]*@host_builtin" "rcx_pi/")
    HOST_ITERATION_DECORATED=$(count_markers "^[[:space:]]*@host_iteration" "rcx_pi/")
    HOST_ITERATION_COMMENT=$(count_markers "# @host_iteration" "rcx_pi/")
    HOST_ITERATION=$((HOST_ITERATION_DECORATED + HOST_ITERATION_COMMENT))
    HOST_MUTATION=$(count_markers "^[[:space:]]*@host_mutation" "rcx_pi/")
    BOOTSTRAP=$(count_markers "^[[:space:]]*@bootstrap_only" "rcx_pi/")
    AST_OK_BOOTSTRAP=$(count_markers "# AST_OK:[[:space:]]*bootstrap" "rcx_pi/")
    PROTO_BUILTIN=$(count_markers "host_builtin" "prototypes/")
    PROTO_ITERATION=$(count_markers "host_iteration" "prototypes/")
    TOTAL_TRACKED=$((HOST_RECURSION + HOST_BUILTIN + HOST_ITERATION + HOST_MUTATION + BOOTSTRAP))
    TOTAL_SEMANTIC=$((TOTAL_TRACKED + AST_OK_BOOTSTRAP))

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
    "prototype_builtin": $PROTO_BUILTIN,
    "prototype_iteration": $PROTO_ITERATION,
    "total_tracked": $TOTAL_TRACKED,
    "total_semantic": $TOTAL_SEMANTIC
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

    # Use anchored patterns (^[[:space:]]*@) to match actual decorators
    # Also count "# @host_*" comments for nested function debt that can't be decorated
    HOST_RECURSION=$(count_markers "^[[:space:]]*@host_recursion" "rcx_pi/")
    HOST_BUILTIN=$(count_markers "^[[:space:]]*@host_builtin" "rcx_pi/")
    HOST_ITERATION_DECORATED=$(count_markers "^[[:space:]]*@host_iteration" "rcx_pi/")
    HOST_ITERATION_COMMENT=$(count_markers "# @host_iteration" "rcx_pi/")
    HOST_ITERATION=$((HOST_ITERATION_DECORATED + HOST_ITERATION_COMMENT))
    HOST_MUTATION=$(count_markers "^[[:space:]]*@host_mutation" "rcx_pi/")
    BOOTSTRAP=$(count_markers "^[[:space:]]*@bootstrap_only" "rcx_pi/")

    printf "  @host_recursion:  %3d\n" "$HOST_RECURSION"
    printf "  @host_builtin:    %3d\n" "$HOST_BUILTIN"
    printf "  @host_iteration:  %3d\n" "$HOST_ITERATION"
    printf "  @host_mutation:   %3d\n" "$HOST_MUTATION"
    printf "  @bootstrap_only:  %3d\n" "$BOOTSTRAP"

    TOTAL_TRACKED=$((HOST_RECURSION + HOST_BUILTIN + HOST_ITERATION + HOST_MUTATION + BOOTSTRAP))
    echo "----------------------------------------------"
    printf "  Total Tracked:    %3d (ceiling: 15)\n" "$TOTAL_TRACKED"
    echo ""

    echo "AST_OK Bypasses (rcx_pi/) - Statement-level semantic debt"
    echo "----------------------------------------------"

    AST_OK_BOOTSTRAP=$(count_markers "# AST_OK:[[:space:]]*bootstrap" "rcx_pi/")
    AST_OK_INFRA=$(count_markers "# AST_OK:[[:space:]]*infra" "rcx_pi/")

    printf "  # AST_OK: bootstrap: %3d (semantic debt)\n" "$AST_OK_BOOTSTRAP"
    printf "  # AST_OK: infra:     %3d (scaffolding)\n" "$AST_OK_INFRA"
    echo "----------------------------------------------"
    TOTAL_SEMANTIC=$((TOTAL_TRACKED + AST_OK_BOOTSTRAP))
    printf "  Total Semantic:   %3d (tracked + bootstrap)\n" "$TOTAL_SEMANTIC"
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
