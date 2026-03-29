#!/bin/bash
# =============================================================================
# Agent Compliance Validator Hook
#
# Automatically validates agent output against AgentGuardrails.v0.md
# Runs after SubagentStop events for review agents (verifier, adversary, etc.)
#
# CRITICAL: This hook validates TRUTH, not just FORMAT:
# - --verify-files: Checks FILE paths actually exist
# - --verify-code: Checks CODE actually appears at FILE:LINE
# - Fabricated citations are DETECTED and BLOCKED
#
# SECURITY: This hook FAILS CLOSED - if validator is missing or crashes,
# agent output is BLOCKED (not allowed). This prevents bypassing validation
# by deleting the validator or causing it to crash.
#
# Created: 2026-02-01 (9-agent self-review recommendation)
# Updated: 2026-02-02 (Critical fix: fail closed, not open)
# Updated: 2026-02-03 (Critical: now verifies CODE matches actual files)
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
  explore|bash|general-purpose|plan)
    # Skip validation for non-review agent types
    exit 0
    ;;
  *)
    # Unknown agent_type — fail closed
    echo '{"decision": "block", "reason": "Unknown agent_type: validation cannot be skipped for unrecognized types"}'
    exit 0
    ;;
esac

# Check if transcript exists
if [ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ]; then
  jq -n '{"decision": "block", "reason": "Agent transcript missing or path empty — cannot verify compliance (fail closed)"}'
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

# If no output extracted, block (fail closed)
if [ -z "$AGENT_OUTPUT" ]; then
  jq -n '{"decision": "block", "reason": "Agent produced no extractable output — cannot verify compliance (fail closed)"}'
  exit 0
fi

# Get project directory
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(dirname "$(dirname "$(dirname "$0")")")}"
VALIDATOR="$PROJECT_DIR/tools/runners/validate_agent_compliance.py"

# =============================================================================
# CRITICAL: Fail closed - if validator missing or crashes, BLOCK output
# =============================================================================

# Check if validator exists
if [ ! -f "$VALIDATOR" ]; then
  # SECURITY: Validator not found - BLOCK (fail closed)
  jq -n '{
    "decision": "block",
    "reason": "Validator script not found at tools/runners/validate_agent_compliance.py - cannot verify compliance"
  }'
  exit 0
fi

# Run compliance check with STRICT mode (verifies FILE exists AND CODE matches)
# --strict enables --verify-files and --verify-code automatically
RESULT=$(echo "$AGENT_OUTPUT" | python3 "$VALIDATOR" --json --strict 2>&1) || VALIDATOR_EXIT=$?
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
  # Check if fabrications were detected (this is the serious case)
  FABRICATIONS=$(echo "$RESULT" | jq -r '.fabrications // 0')

  if [ "$FABRICATIONS" != "0" ]; then
    # CRITICAL: Fabricated citations detected
    FABRICATION_DETAILS=$(echo "$RESULT" | jq -r '.fabrication_details | join("; ")' 2>/dev/null || echo "")
    jq -n --arg reason "FABRICATION DETECTED: Agent cited code that doesn't match actual files. $FABRICATION_DETAILS" '{
      "decision": "block",
      "reason": $reason
    }'
    exit 0
  fi

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
