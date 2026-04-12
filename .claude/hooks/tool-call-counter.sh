#!/bin/bash
# PostToolUse hook: BLOCKS every 40th tool call for a forced verification step.
# Injects friction reminder every 10th call (non-blocking).
#
# The blocking checkpoint forces a full stop and verification statement.
# The non-blocking reminder creates lighter friction between checkpoints.
#
# Scope: applies ONLY to the main interactive Claude Code session.  Pipeline
# subprocess sessions (phase_a/b executor, commit_executor, meta_bridge
# supervisor, bridge_adapters) already enforce verification discipline via
# the bridge review loop and run with a bounded turn budget per round, so
# adding per-call checkpoints on top of the bridge loop wastes turns and
# produces cross-session counter contamination through the shared /tmp
# counter file.  Early-exit silently in those contexts (verified 2026-04-10
# via impl-fde7f3d8 hitting #5360 mid-round and producing zero Edits).
#
# Uses a counter file in /tmp — session-scoped, resets on restart.

COUNTER_FILE="/tmp/.rcx_tool_call_counter"

# Early-exit: if any ancestor of this hook is a pipeline executor, do not
# count.  Walks up the process ancestry from ${PPID} (the bash that spawned
# this hook — its parent is the Claude Code session) until PID 1 or until
# an ancestor matches one of the known pipeline executor command-line
# fragments.  POSIX-portable (ps + case glob), no bash-only constructs.
_pid=${PPID}
while [ -n "${_pid}" ] && [ "${_pid}" != "1" ] && [ "${_pid}" != "0" ]; do
    _cmd=$(ps -p "${_pid}" -o command= 2>/dev/null || printf '')
    case "${_cmd}" in
        *phase_a_executor.py*|*phase_b_executor.py*|*commit_executor.py*|*meta_bridge_supervisor*|*bridge_adapters*|*executor_dispatch*)
            exit 0
            ;;
    esac
    _pid=$(ps -p "${_pid}" -o ppid= 2>/dev/null | tr -d ' ')
    [ -z "${_pid}" ] && break
done

# Increment counter
if [ -f "$COUNTER_FILE" ]; then
  COUNT=$(cat "$COUNTER_FILE")
  COUNT=$((COUNT + 1))
else
  COUNT=1
fi
echo "$COUNT" > "$COUNTER_FILE"

# Every 40th call: BLOCK — force verification step
if [ $((COUNT % 40)) -eq 0 ]; then
  echo '{"decision":"block","reason":"VERIFICATION CHECKPOINT (#'"$COUNT"'): You have made 40 tool calls since the last checkpoint. Before continuing, you MUST state: (1) What you are trying to accomplish. (2) What you have verified so far. (3) What assumption you are about to act on. Resume after stating these."}'
  exit 0
fi

# Every 10th call (not 40th — the block path above already exited): non-blocking reminder
if [ $((COUNT % 10)) -eq 0 ]; then
  echo '{"additionalContext":"TOOL-CALL CHECKPOINT (#'"$COUNT"'): Are you following override #7 (diagnosis first)? Are you verifying assumptions (#4) or shortcutting? If you are about to claim something works without running it, STOP."}'
fi

exit 0
