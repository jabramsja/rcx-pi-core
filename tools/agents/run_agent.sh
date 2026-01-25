#!/bin/bash
# Run an RCX verification or adversary agent
#
# Usage:
#   ./tools/agents/run_agent.sh verifier [files...]
#   ./tools/agents/run_agent.sh adversary [files...]
#
# This prepares the context and instructions for running with Claude.
# You can pipe the output to claude or copy/paste into a new session.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

AGENT_TYPE="${1:-}"
shift || true
FILES="${*:-rcx_pi/eval_seed.py}"

if [[ -z "$AGENT_TYPE" ]]; then
    echo "Usage: $0 <verifier|adversary> [files...]"
    echo ""
    echo "Examples:"
    echo "  $0 verifier rcx_pi/eval_seed.py"
    echo "  $0 adversary rcx_pi/kernel.py rcx_pi/eval_seed.py"
    echo "  $0 verifier  # defaults to eval_seed.py"
    echo ""
    echo "To run with Claude:"
    echo "  $0 verifier | pbcopy  # copy to clipboard, paste in new Claude session"
    echo "  # OR in Claude Code:"
    echo "  # 'Spawn a verifier agent to check rcx_pi/eval_seed.py'"
    exit 1
fi

case "$AGENT_TYPE" in
    verifier)
        PROMPT_FILE="$SCRIPT_DIR/verifier_prompt.md"
        echo "# VERIFIER AGENT SESSION"
        echo ""
        echo "Read the following prompt file for your role:"
        echo "  $PROMPT_FILE"
        echo ""
        echo "Then verify these files:"
        for f in $FILES; do
            echo "  - $f"
        done
        echo ""
        echo "Produce a structured Verification Report."
        ;;
    adversary)
        PROMPT_FILE="$SCRIPT_DIR/adversary_prompt.md"
        echo "# ADVERSARY AGENT SESSION"
        echo ""
        echo "Read the following prompt file for your role:"
        echo "  $PROMPT_FILE"
        echo ""
        echo "Then attack these files:"
        for f in $FILES; do
            echo "  - $f"
        done
        echo ""
        echo "Try to break invariants. Produce a structured Adversary Report."
        ;;
    *)
        echo "Unknown agent type: $AGENT_TYPE"
        echo "Use: verifier or adversary"
        exit 1
        ;;
esac
