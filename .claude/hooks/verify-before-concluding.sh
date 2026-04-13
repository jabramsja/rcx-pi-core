#!/bin/bash
# Pipeline bypass: set by bridge_adapters.py for all pipeline subprocesses.
[ "${RCX_PIPELINE_SESSION:-}" = "1" ] && exit 0
# PostToolUse hook for Grep, Read, Bash results.
# Injects a lightweight verification reminder as additionalContext.
# This directly addresses the failure mode of jumping to conclusions
# from search results before reading the actual code.

# The hook receives tool result JSON on stdin. We don't need to parse it —
# the reminder is unconditional for matched tools (Grep|Read|Bash).
# The additionalContext field is injected as a system-reminder the model sees.

echo '{"additionalContext":"Verify before concluding: grep counts locate, Read verifies. Never state exists/absent based on grep alone."}'
exit 0
