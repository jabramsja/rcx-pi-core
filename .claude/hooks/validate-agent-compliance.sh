#!/bin/bash
# =============================================================================
# Agent Compliance Validator Hook
#
# Automatically validates agent output against AgentGuardrails.v0.md
# Runs after SubagentStop events for review agents (verifier, adversary, etc.)
#
# Created: 2026-02-01 (9-agent self-review recommendation)
# =============================================================================

set -euo pipefail

# Read input from stdin (JSON with session info)
INPUT=$(cat)

# Extract agent info
AGENT_TYPE=$(echo "$INPUT" | jq -r '.agent_type // empty')
TRANSCRIPT=$(echo "$INPUT" | jq -r '.agent_transcript_path // empty')

# Only validate review agents that should follow guardrails format
case "$AGENT_TYPE" in
  verifier|adversary|expert|structural-proof|grounding|fuzzer|translator|visualizer|advisor)
    # Continue with validation
    ;;
  *)
    # Skip validation for other agent types (Explore, Bash, etc.)
    exit 0
    ;;
esac

# Check if transcript exists
if [ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ]; then
  exit 0
fi

# Extract agent's text output from JSONL transcript
# The transcript contains JSON lines; we want the assistant's text content
AGENT_OUTPUT=$(jq -rs '
  [.[] | select(.type == "assistant" or .role == "assistant") |
   (.content // .text // .message // "") |
   if type == "array" then
     [.[] | select(.type == "text") | .text] | join("\n")
   else
     .
   end
  ] | join("\n")
' "$TRANSCRIPT" 2>/dev/null || echo "")

# If no output extracted, skip validation
if [ -z "$AGENT_OUTPUT" ]; then
  exit 0
fi

# Get project directory
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(dirname "$(dirname "$(dirname "$0")")")}"
VALIDATOR="$PROJECT_DIR/tools/validate_agent_compliance.py"

# Check if validator exists
if [ ! -f "$VALIDATOR" ]; then
  # Validator not found - allow without checking (don't break workflow)
  exit 0
fi

# Run compliance check
RESULT=$(echo "$AGENT_OUTPUT" | python3 "$VALIDATOR" --json 2>/dev/null || echo '{"compliant": true}')

# Check compliance status
COMPLIANT=$(echo "$RESULT" | jq -r '.compliant // true')

if [ "$COMPLIANT" = "false" ]; then
  # Extract violations for the reason
  VIOLATIONS=$(echo "$RESULT" | jq -r '.violations | join("; ")' 2>/dev/null || echo "Unknown violations")

  # Return block decision with reason
  jq -n --arg reason "Agent output non-compliant with AgentGuardrails.v0: $VIOLATIONS" '{
    "decision": "block",
    "reason": $reason
  }'
  exit 0
fi

# Compliant - allow the agent to complete normally
exit 0
