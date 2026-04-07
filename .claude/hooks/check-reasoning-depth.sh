#!/bin/bash
# Stop hook: checks if the response contains premature conclusions
# without verification language. Returns exit code 2 ("block") to force
# the model to continue when it detects the jump-to-conclusion pattern.
#
# The hook receives JSON on stdin with last_assistant_message.
#
# Check 1 (claim-without-evidence): blocks short responses (<800 chars)
#   that contain claim language but no verification language.
#
# Check 2 (cron-without-evidence): blocks cron responses that lack
#   tool call evidence markers (MCP results, Read results, line numbers).
#   Cron responses are identified by "[cron:" prefix pattern.

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

MSG_LEN=${#MSG}
if [ "$MSG_LEN" -eq 0 ]; then
    exit 0
fi

# --- Check 2: Cron response evidence gate ---
# Cron responses MUST contain evidence of tool usage (MCP query result,
# Read tool result reference, or explicit line citation).
# Only applies to SHORT messages (<1500 chars) — long messages that mention
# [cron:] are discussions ABOUT the cron, not cron responses themselves.
IS_CRON=$(echo "$MSG" | grep -c '\[cron:' || true)
if [ "$IS_CRON" -gt 0 ] && [ "$MSG_LEN" -lt 600 ]; then
    HAS_EVIDENCE=$(echo "$MSG" | grep -iEc "(mcp__sqlite|read_query|r[0-9]+\]|MEMORY\.md.*(line|read|unchanged)|bridge\.db|job_id|AWAITING|COMPLETE|FAILED|phase-b|Read tool|MCP query)" || true)
    if [ "$HAS_EVIDENCE" -eq 0 ]; then
        echo '{"decision":"block","reason":"Cron response lacks tool-call evidence. You MUST include at least one: MCP sqlite query result, Read tool output reference, or specific data from a tool call. Self-reported claims are not evidence."}'
        exit 0
    fi
fi

# --- Check 3: Test result claims at ANY length ---
# Catches "all N tests pass" or "N/N passed" without recent test execution evidence.
# This check applies regardless of message length because test result fabrication
# is a high-severity violation (override #9: unit tests are NOT proof without running them).
HAS_TEST_CLAIM=$(echo "$MSG" | grep -iEc "(all.*tests pass|all.*checks pass|[0-9]+/[0-9]+ pass|tests passing|test suite.*(clean|green|pass))" || true)
HAS_TEST_EVIDENCE=$(echo "$MSG" | grep -iEc "(pytest|test_|\.sh.*2>&1|passed in [0-9]|failed in [0-9]|exit code|PASSED \[|FAILED \[)" || true)
if [ "$HAS_TEST_CLAIM" -gt 0 ] && [ "$HAS_TEST_EVIDENCE" -eq 0 ]; then
    echo '{"decision":"block","reason":"Response claims test results without evidence of running tests. Show the actual test output (pytest result, exit code, pass/fail counts from a tool call) before claiming tests pass."}'
    exit 0
fi

# --- Check 1: Claim without verification (general) ---
# Skip long messages (likely have reasoning chain)
if [ "$MSG_LEN" -gt 800 ]; then
    exit 0
fi

# Check for strong claim patterns (case-insensitive)
HAS_CLAIM=$(echo "$MSG" | grep -iEc "(is active|is not active|is patched|not patched|confirmed|it works|this works|all (tests|checks) pass|is present|is absent|does not exist|doesn.t exist|is correct|is wrong|is broken|is fixed|no (violations|contradictions|issues)|status: clean)" || true)

# Check for verification language
HAS_VERIFY=$(echo "$MSG" | grep -iEc "(verified|I checked|I read|reading|let me (check|verify|read|look)|after reading|the code shows|at line|looking at|evidence:|tool call|result.*r[0-9])" || true)

if [ "$HAS_CLAIM" -gt 0 ] && [ "$HAS_VERIFY" -eq 0 ]; then
    echo '{"decision":"block","reason":"Response contains a claim without verification. Show the evidence (read the code, cite the line) before stating the conclusion."}'
    exit 0
fi

# Allow stop
exit 0
