#!/bin/bash
# PostCompact hook: re-injects critical behavioral overrides after context compaction.
# When context compacts, CLAUDE.md emphasis gets summarized away.
# This hook restores the highest-priority rules at system-reminder level.

cat << 'HOOKEOF'
{"additionalContext":"POST-COMPACTION OVERRIDE REINJECT: (1) Read code BEFORE implementing. (2) Lead with reasoning, not conclusions. (3) Verify every assumption — grep locates, Read verifies. (4) Never claim 'all tests pass' when output shows failures. (5) CLAUDE.md and MEMORY.md are MANDATORY. Re-read MEMORY.md now if you haven't recently."}
HOOKEOF
exit 0
