#!/bin/bash
# Stop hook: checks if the response contains premature conclusions
# without verification language. Returns exit code 2 ("block") to force
# the model to continue when it detects the jump-to-conclusion pattern.
#
# The hook receives JSON on stdin with last_assistant_message.
# Only blocks if ALL of these are true:
#   1. Response is short (under 500 chars)
#   2. Response contains strong claim language ("is active", "confirmed", "works", etc.)
#   3. Response does NOT contain verification language ("verified", "checked", "reading", etc.)
#
# This catches the common failure mode (grep count → claim) without
# blocking valid short responses like status updates or acknowledgments.

INPUT=$(cat)

# Extract last_assistant_message
MSG=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    msg = data.get('last_assistant_message', '')
    print(msg)
except:
    print('')
" 2>/dev/null)

# Skip if no message or message is long (long = likely has reasoning)
MSG_LEN=${#MSG}
if [ "$MSG_LEN" -eq 0 ] || [ "$MSG_LEN" -gt 500 ]; then
    exit 0
fi

# Check for strong claim patterns (case-insensitive)
HAS_CLAIM=$(echo "$MSG" | grep -iEc "(is active|is not active|is patched|not patched|confirmed|it works|this works|all (tests|checks) pass|is present|is absent|does not exist|doesn.t exist|is correct|is wrong|is broken|is fixed)")

# Check for verification language
HAS_VERIFY=$(echo "$MSG" | grep -iEc "(verified|I checked|I read|reading|let me (check|verify|read|look)|after reading|the code shows|at line|looking at)")

if [ "$HAS_CLAIM" -gt 0 ] && [ "$HAS_VERIFY" -eq 0 ]; then
    echo '{"decision":"block","reason":"Response contains a claim without verification. Show the evidence (read the code, cite the line) before stating the conclusion."}'
    exit 0
fi

# Allow stop
exit 0
