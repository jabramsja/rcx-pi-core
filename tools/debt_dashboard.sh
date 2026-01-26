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

# Count markers
count_markers() {
    local pattern="$1"
    local dir="$2"
    local count
    count=$(grep -r "$pattern" "$dir" 2>/dev/null | wc -l | tr -d '[:space:]') || count=0
    echo "${count:-0}"
}

if [ "$JSON_OUTPUT" = true ]; then
    # JSON output for programmatic use
    HOST_RECURSION=$(count_markers "@host_recursion" "rcx_pi/")
    HOST_BUILTIN=$(count_markers "@host_builtin" "rcx_pi/")
    HOST_ITERATION=$(count_markers "@host_iteration" "rcx_pi/")
    BOOTSTRAP=$(count_markers "@bootstrap_only" "rcx_pi/")
    PROTO_BUILTIN=$(count_markers "host_builtin" "prototypes/")
    PROTO_ITERATION=$(count_markers "host_iteration" "prototypes/")
    TOTAL=$((HOST_RECURSION + HOST_BUILTIN + HOST_ITERATION + BOOTSTRAP))

    cat <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "debt": {
    "host_recursion": $HOST_RECURSION,
    "host_builtin": $HOST_BUILTIN,
    "host_iteration": $HOST_ITERATION,
    "bootstrap_only": $BOOTSTRAP,
    "prototype_builtin": $PROTO_BUILTIN,
    "prototype_iteration": $PROTO_ITERATION,
    "total_core": $TOTAL
  }
}
EOF
else
    # Human-readable output
    echo "=============================================="
    echo "       RCX Host Debt Dashboard"
    echo "=============================================="
    echo ""
    echo "Core Debt (rcx_pi/) - Must be zero for self-hosting"
    echo "----------------------------------------------"

    HOST_RECURSION=$(count_markers "@host_recursion" "rcx_pi/")
    HOST_BUILTIN=$(count_markers "@host_builtin" "rcx_pi/")
    HOST_ITERATION=$(count_markers "@host_iteration" "rcx_pi/")
    BOOTSTRAP=$(count_markers "@bootstrap_only" "rcx_pi/")

    printf "  @host_recursion:  %3d\n" "$HOST_RECURSION"
    printf "  @host_builtin:    %3d\n" "$HOST_BUILTIN"
    printf "  @host_iteration:  %3d\n" "$HOST_ITERATION"
    printf "  @bootstrap_only:  %3d\n" "$BOOTSTRAP"

    TOTAL=$((HOST_RECURSION + HOST_BUILTIN + HOST_ITERATION + BOOTSTRAP))
    echo "----------------------------------------------"
    printf "  Total Core Debt:  %3d\n" "$TOTAL"
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

    # Show locations if there's core debt
    if [ "$TOTAL" -gt 0 ]; then
        echo "Core Debt Locations:"
        echo "----------------------------------------------"
        grep -rn "@host_recursion\|@host_builtin\|@host_iteration\|@bootstrap_only" rcx_pi/ 2>/dev/null | head -20 || true
        echo ""
    fi

    # Summary
    echo "=============================================="
    if [ "$TOTAL" -eq 0 ]; then
        echo "SELF-HOSTING READY: No core host debt!"
    elif [ "$TOTAL" -le 5 ]; then
        echo "ALMOST THERE: $TOTAL core dependencies remain"
    else
        echo "WORK NEEDED: $TOTAL core dependencies to eliminate"
    fi
    echo "=============================================="
fi
