#!/bin/bash
# artifact-edit-gate.sh — PreToolUse:Edit, PreToolUse:Write
#
# BLOCKS edits to pipeline artifacts until root-cause investigation has occurred.
#
# Pipeline bypass: set by bridge_adapters.py for all pipeline subprocesses.
[ "${RCX_PIPELINE_SESSION:-}" = "1" ] && exit 0
#
# Pipeline artifacts are NOT source code — they're outputs produced by executors.
# Editing them directly is almost always a band-aid. The source code that produced
# the artifact incorrectly is the real fix target.
#
# Behavior:
#   First attempt to edit an artifact path: BLOCKED with diagnostic message.
#   Second attempt (after 30s): ALLOWED with warning injection.
#   Non-artifact paths: always allowed (pass-through).
#
# Artifact patterns:
#   reports/control_plane/*     — plan packets, tracked packets, session handoffs
#   .agent_bus/*                — bridge configs, executor state, recovery logs
#   .scratch/*                  — temporary pipeline outputs
#   post_merge_package.json     — dispatch routing artifact
#
# Allowlist (never blocked):
#   .claude/rules/learning.md   — mechanical learning writes
#   .claude/settings*.json      — configuration changes
#   .claude/skills/*            — skill definitions
#   *MEMORY.md / CLAUDE.md      — memory/instruction writes
#   STATUS.md / TASKS.md        — governance docs (not pipeline artifacts)

set -euo pipefail

TRACKER_DIR="/tmp/.rcx_artifact_edit_gate"
MIN_SECONDS=30
EXPIRY_SECONDS=300

# Read tool parameters from stdin
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# No file path — pass through
[ -z "$FILE_PATH" ] && exit 0

# --- Allowlist (never block) ---
case "$FILE_PATH" in
  */learning.md)       exit 0 ;;
  */.claude/settings*) exit 0 ;;
  */.claude/skills/*)  exit 0 ;;
  */MEMORY.md)         exit 0 ;;
  */CLAUDE.md)         exit 0 ;;
  */STATUS.md)         exit 0 ;;
  */TASKS.md)          exit 0 ;;
  */bridge_config.json) exit 0 ;;
  */executor_config.json) exit 0 ;;
esac

# --- Artifact detection ---
# Match both absolute (*/reports/...) and root-relative (reports/...) paths.
IS_ARTIFACT=false
case "$FILE_PATH" in
  */reports/control_plane/*|reports/control_plane/*) IS_ARTIFACT=true ;;
  */.agent_bus/*|.agent_bus/*)                       IS_ARTIFACT=true ;;
  */.scratch/*|.scratch/*)                           IS_ARTIFACT=true ;;
  */post_merge_package.json|post_merge_package.json) IS_ARTIFACT=true ;;
esac

# --- L3 parity reminder (non-blocking) for substrate files ---
if [ "$IS_ARTIFACT" = "false" ]; then
  case "$FILE_PATH" in
    */mu/host/python/rcx_pi/selfhost/*|*/rcx_pi/selfhost/*)
      cat <<EOFPARITY
L3 PARITY: You are editing a Python substrate file.
- Python changes MUST be mirrored in JS (North Star #13)
- Verify after: node mu/host/js/eval_step.js
- Run agents before done: run_review.py --pr --depth quick
EOFPARITY
      exit 0 ;;
    */mu/host/js/*)
      cat <<EOFPARITY
L3 PARITY: You are editing a JS substrate file.
- JS changes MUST match Python semantics (North Star #13)
- Verify after: node mu/host/js/eval_step.js
- Run agents before done: run_review.py --pr --depth quick
EOFPARITY
      exit 0 ;;
  esac
  exit 0
fi

# --- Tracker logic (two-attempt gate with minimum investigation time) ---
mkdir -p "$TRACKER_DIR"

# Clean up expired tracker files (older than EXPIRY_SECONDS)
find "$TRACKER_DIR" -type f -mmin +$((EXPIRY_SECONDS / 60)) -delete 2>/dev/null || true

# Generate tracker file name from path hash
HASH=$(echo "$FILE_PATH" | md5 -q 2>/dev/null || echo "$FILE_PATH" | md5sum 2>/dev/null | cut -d' ' -f1 || echo "fallback")
TRACKER_FILE="$TRACKER_DIR/$HASH"

if [ -f "$TRACKER_FILE" ]; then
  # Second+ attempt — check if enough time has passed
  CREATED=$(stat -f %m "$TRACKER_FILE" 2>/dev/null || stat -c %Y "$TRACKER_FILE" 2>/dev/null || echo 0)
  NOW=$(date +%s)
  AGE=$((NOW - CREATED))

  if [ "$AGE" -lt "$MIN_SECONDS" ]; then
    # Too quick — still blocked (JSON protocol: decision=block, exit 0)
    REMAINING=$((MIN_SECONDS - AGE))
    jq -n --arg reason "BLOCKED: Artifact edit too quick (${AGE}s < ${MIN_SECONDS}s). Target: $FILE_PATH. ${REMAINING}s remaining. Investigate ROOT CAUSE first: (1) grep/read which executor produces this artifact, (2) read the source code, (3) fix the .py file, (4) then re-attempt." \
      '{"decision": "block", "reason": $reason}'
    exit 0
  fi

  # Enough time passed — allow with warning
  rm -f "$TRACKER_FILE"
  cat <<EOFALLOW
ARTIFACT EDIT ALLOWED (${AGE}s elapsed since first block).

Target: $FILE_PATH
Before this edit proceeds, confirm in your reasoning:
- Root cause source code file:line identified
- Source code fix applied (or queued for next commit)
- This edit is for the CURRENT RUN only (not a permanent workaround)
EOFALLOW
  exit 0
else
  # First attempt — BLOCK and create tracker (JSON protocol: decision=block, exit 0)
  touch "$TRACKER_FILE"
  jq -n --arg reason "BLOCKED: Pipeline artifact edit requires root-cause evidence. Target: $FILE_PATH. This is a pipeline artifact, not source code. REQUIRED (${MIN_SECONDS}s minimum investigation): (1) grep/read which executor produces this artifact, (2) read the source code to find the bug, (3) fix the .py file, (4) re-attempt. Common roots: reports/control_plane/ -> phase_a/b_executor.py, .agent_bus/ -> phase_b/commit_executor.py, .scratch/ -> executor subprocess, post_merge_package.json -> executor_dispatch.py" \
    '{"decision": "block", "reason": $reason}'
  exit 0
fi
