#!/bin/bash
# =============================================================================
# Agent Compliance Validator Hook
#
# Automatically validates agent output against AgentGuardrails.v0.md
# Runs after SubagentStop events for review agents (verifier, adversary, etc.)
#
# SECURITY: This hook FAILS CLOSED - if validator is missing or crashes,
# agent output is BLOCKED (not allowed). This prevents bypassing validation
# by deleting the validator or causing it to crash.
#
# Created: 2026-02-01 (9-agent self-review recommendation)
# Updated: 2026-02-02 (Critical fix: fail closed, not open)
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

# =============================================================================
# CRITICAL: Fail closed - if validator missing or crashes, BLOCK output
# =============================================================================

# Check if validator exists
if [ ! -f "$VALIDATOR" ]; then
  # SECURITY: Validator not found - BLOCK (fail closed)
  jq -n '{
    "decision": "block",
    "reason": "Validator script not found at tools/validate_agent_compliance.py - cannot verify compliance"
  }'
  exit 0
fi

# Run compliance check - capture exit code
RESULT=$(echo "$AGENT_OUTPUT" | python3 "$VALIDATOR" --json 2>&1) || VALIDATOR_EXIT=$?
VALIDATOR_EXIT=${VALIDATOR_EXIT:-0}

# If validator crashed, BLOCK (fail closed)
if [ "$VALIDATOR_EXIT" -ne 0 ]; then
  jq -n --arg error "$RESULT" '{
    "decision": "block",
    "reason": ("Validator script crashed: " + $error)
  }'
  exit 0
fi

# Check if result is valid JSON
if ! echo "$RESULT" | jq -e . >/dev/null 2>&1; then
  jq -n --arg output "$RESULT" '{
    "decision": "block",
    "reason": ("Validator produced invalid JSON: " + $output)
  }'
  exit 0
fi

# Check compliance status (default to false if missing - fail closed)
COMPLIANT=$(echo "$RESULT" | jq -r '.compliant // false')

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
