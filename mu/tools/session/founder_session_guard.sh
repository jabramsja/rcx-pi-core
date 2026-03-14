#!/usr/bin/env bash
set -uo pipefail

usage() {
    cat <<'EOF'
Usage:
  ./tools/session/founder_session_guard.sh <mode> [--run]

Modes:
  redteam   Founder bootstrap + deep runtime/parity/doc audit startup
  parity    Python/JS parity and authority-focused startup
  docs      Doc-truth and canonical-index startup
  closeout  Validation and report-placement startup

Notes:
  - This script operationalizes founder/bootstrap protocol locally.
  - It does NOT auto-invoke Codex skills. It prints the required skill names so
    the operator/session can apply them deliberately.
  - Default behavior is dry-run: print required docs, skills, and commands.
  - Pass --run to execute the command set and return non-zero if any command fails.
  - For proof-class / active-doc attestation after startup, run
    ./tools/session/founder_session_attest.sh <mode>
  - For periodic reminders during a long session, run
    ./tools/session/founder_session_heartbeat.sh <mode> --interval 300
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] || [ $# -eq 0 ]; then
    usage
    exit 0
fi

MODE="$1"
shift
RUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --run)
            RUN=1
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "ERROR: must run inside the WorkingRCX git repo" >&2
    exit 2
}
cd "$REPO_ROOT"

COMMON_DOCS=(
    "FOUNDER_SESSION_BOOTSTRAP.md"
    "STATUS.md"
    "TASKS.md"
    "CHANGELOG.md"
    "reports/README.md"
    "CLAUDE.md"
    "roadmap/MANIFEST.md"
    "mu/docs/agents/AgentRunbook.v0.md"
    "mu/docs/core/Why_RCX_PI_VM_EXISTS.md"
    "mu/docs/core/SelfHosting.v0.md"
    "mu/docs/core/MetaCircularKernel.v0.md"
    "mu/docs/core/StructuralPurity.v0.md"
)

COMMON_COMMANDS=(
    "git status --short"
    "python3 tools/checks/enforce_l4_execution_contract.py --staged"
    "python3 mu/tools/checks/check_host_semantics_ratchet.py --json"
    "python3 tools/checks/check_host_authority_inventory_ratchet.py"
    "./tools/checks/check_docs_consistency.sh"
)

SKILLS=()
EXTRA_DOCS=()
EXTRA_COMMANDS=()

case "$MODE" in
    redteam)
        SKILLS=(
            "rcx-redteam-runtime"
            "rcx-parity-authority-audit"
            "rcx-doc-truth-sync"
            "rcx-wave-closeout"
        )
        EXTRA_DOCS=(
            "mu/docs/core/L4ExitChecklist.v0.md"
            "mu/docs/core/L4MicroAbi.v0.md"
            "mu/docs/core/L4DecisionCard.v0.md"
            "mu/docs/core/G8CpsFeasibility.v0.md"
        )
        EXTRA_COMMANDS=(
            "PYTHONHASHSEED=0 python3 -m pytest mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py -q"
            "PYTHONHASHSEED=0 python3 -m pytest mu/tests/l4_gates/test_wave_j_arch_gaps_gate.py -q"
            "PYTHONHASHSEED=0 python3 -m pytest mu/tests/l4_gates/test_lower_stage0.py -q"
            "PYTHONHASHSEED=0 python3 -m pytest mu/tests/l4_gates/test_stage0_vm_cutover.py -q"
            "python3 tools/checks/check_simulated_production_logic.py"
            "python3 tools/checks/check_gate_behavioral_pairs.py --root mu/tests/l4_gates"
            "./mu/tools/checks/check_test_theater.sh"
            "./mu/tools/checks/check_test_theater_js.sh"
            "./mu/tools/checks/linters/seed_police.sh"
            "./tools/checks/check_js_debt.sh"
            "node mu/host/js/eval_step.js"
        )
        ;;
    parity)
        SKILLS=(
            "rcx-parity-authority-audit"
            "rcx-redteam-runtime"
        )
        EXTRA_COMMANDS=(
            "PYTHONHASHSEED=0 python3 -m pytest mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py -q"
            "PYTHONHASHSEED=0 python3 -m pytest mu/tests/l4_gates/test_stage0_vm_cutover.py -q"
            "PYTHONHASHSEED=0 python3 -m pytest tests/tools/test_check_host_authority_inventory_ratchet.py -q"
            "node mu/host/js/eval_step.js"
            "./tools/checks/check_js_debt.sh"
        )
        ;;
    docs)
        SKILLS=(
            "rcx-doc-truth-sync"
            "rcx-wave-closeout"
        )
        EXTRA_COMMANDS=(
            "PYTHONHASHSEED=0 python3 -m pytest tests/docs/test_doc_freshness.py tests/docs/test_manifest_discoverability.py tests/docs/test_debt_truth_gate.py mu/tests/structural/test_status_md_grounding.py -q"
            "python3 tools/docs/docs_sync_report.py --check"
            "rg -n \"GROUNDING_TESTS: none|L4ExitChecklist|L4MicroAbi|G8CpsFeasibility|L4DecisionCard\" roadmap/MANIFEST.md mu/docs/core STATUS.md TASKS.md"
        )
        ;;
    closeout)
        SKILLS=(
            "rcx-wave-closeout"
        )
        EXTRA_COMMANDS=(
            "git status --short"
            "python3 mu/tools/checks/check_host_semantics_ratchet.py --json"
            "python3 tools/checks/check_host_authority_inventory_ratchet.py"
            "./tools/checks/check_docs_consistency.sh"
            "PYTHONHASHSEED=0 python3 -m pytest mu/tests/structural/test_status_md_grounding.py tests/docs/test_debt_truth_gate.py -q"
        )
        ;;
    *)
        echo "ERROR: unknown mode '$MODE'" >&2
        usage >&2
        exit 2
        ;;
esac

print_list() {
    local title="$1"
    shift
    echo "$title"
    for item in "$@"; do
        echo "  - $item"
    done
    echo ""
}

echo "RCX Founder Session Guard"
echo "mode: $MODE"
echo "repo: $REPO_ROOT"
echo ""
echo "This wrapper operationalizes founder/bootstrap protocol and skill selection."
echo "It does not auto-run skills; it names the required skill workflows."
echo ""
echo "Recommended follow-up attestation: ./tools/session/founder_session_attest.sh $MODE"
echo ""

ALL_DOCS=("${COMMON_DOCS[@]}")
if [ "${#EXTRA_DOCS[@]}" -gt 0 ]; then
    ALL_DOCS+=("${EXTRA_DOCS[@]}")
fi

for path in "${ALL_DOCS[@]}"; do
    if [ ! -e "$path" ]; then
        echo "ERROR: required path missing: $path" >&2
        exit 1
    fi
done

print_list "Required skills:" "${SKILLS[@]}"
print_list "Required docs to read:" "${ALL_DOCS[@]}"
print_list "Bootstrap commands:" "${COMMON_COMMANDS[@]}"
print_list "Mode-specific commands:" "${EXTRA_COMMANDS[@]}"

if [ "$RUN" -ne 1 ]; then
    echo "Dry-run only. Re-run with --run to execute the command set."
    exit 0
fi

FAILURES=0

run_command() {
    local cmd="$1"
    echo ">>> $cmd"
    if bash -lc "$cmd"; then
        echo "OK"
    else
        local status=$?
        echo "FAIL (exit $status)"
        FAILURES=$((FAILURES + 1))
    fi
    echo ""
}

for cmd in "${COMMON_COMMANDS[@]}"; do
    run_command "$cmd"
done

for cmd in "${EXTRA_COMMANDS[@]}"; do
    run_command "$cmd"
done

if [ "$FAILURES" -ne 0 ]; then
    echo "Founder session guard completed with $FAILURES failing command(s)." >&2
    exit 1
fi

echo "Founder session guard completed successfully."
