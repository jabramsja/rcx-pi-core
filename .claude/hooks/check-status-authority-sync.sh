#!/usr/bin/env bash
# PostToolUse hook: verify STATUS.md authority counts match baseline after edit.
# Catches stale authority/total inventory numbers that caused 4+ commit failures
# in the W3E-W4C session.
set -euo pipefail

FILE=$(jq -r '.tool_input.file_path // .tool_response.filePath // ""' < /dev/stdin 2>/dev/null || echo "")
[[ "$FILE" != *STATUS.md ]] && exit 0

cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || exit 0

# Run the debt truth gate authority consistency test
RESULT=$(PYTHONHASHSEED=0 python3 -m pytest tests/docs/test_debt_truth_gate.py::TestAuthorityCountConsistency::test_all_authority_mentions_match_baseline -x -q --timeout=10 --no-header 2>&1 || true)

if echo "$RESULT" | grep -q "FAILED\|AssertionError"; then
  # Extract the mismatch details
  DETAILS=$(echo "$RESULT" | grep -A2 "authority count mismatch" | head -3)
  cat <<EOF
{"continue": false, "stopReason": "STATUS.md has stale authority counts after edit. Fix before continuing.\n$DETAILS\nRun: PYTHONHASHSEED=0 pytest tests/docs/test_debt_truth_gate.py -q"}
EOF
fi
