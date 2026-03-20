#!/usr/bin/env bash
# PostToolUse hook: verify STATUS.md authority counts match baseline after edit.
# Catches stale authority/total inventory numbers that caused 4+ commit failures
# in the W3E-W4C session.
set -euo pipefail

FILE=$(jq -r '.tool_input.file_path // .tool_response.filePath // ""' < /dev/stdin 2>/dev/null || echo "")
[[ "$FILE" != *STATUS.md ]] && exit 0

# Fail closed: reject empty/unset CLAUDE_PROJECT_DIR before cd attempt
# cd "" succeeds (stays in cwd), so explicit check is required for fail-closed behavior
if [[ -z "${CLAUDE_PROJECT_DIR:-}" ]]; then
  echo '{"decision": "block", "reason": "CLAUDE_PROJECT_DIR not set - blocking for safety"}'
  exit 0
fi
cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || {
  echo '{"decision": "block", "reason": "Cannot cd to project directory - blocking for safety"}'
  exit 0
}

# Run the debt truth gate authority consistency test (no --timeout flag — avoids pytest-timeout dependency)
# Temporarily disable errexit to capture exit code (ensures fail-closed path is reachable on unexpected failures)
set +e
RESULT=$(PYTHONHASHSEED=0 python3 -m pytest tests/docs/test_debt_truth_gate.py::TestAuthorityCountConsistency::test_all_authority_mentions_match_baseline -x -q --no-header 2>&1)
EXIT_CODE=$?
set -e

if [ $EXIT_CODE -ne 0 ]; then
  if echo "$RESULT" | grep -q "FAILED\|AssertionError"; then
    # Test ran but authority counts don't match
    DETAILS=$(echo "$RESULT" | grep -A2 "authority count mismatch" | head -3)
    cat <<EOF
{"decision": "block", "reason": "STATUS.md has stale authority counts after edit. Fix before continuing.\n$DETAILS\nRun: PYTHONHASHSEED=0 pytest tests/docs/test_debt_truth_gate.py -q"}
EOF
  else
    # Unexpected failure (missing module, import error, etc) — fail closed
    SNIPPET=$(echo "$RESULT" | tail -3 | tr '\n' ' ')
    cat <<EOF
{"decision": "block", "reason": "Authority sync check failed unexpectedly (exit $EXIT_CODE). Investigate before continuing.\n$SNIPPET"}
EOF
  fi
fi
