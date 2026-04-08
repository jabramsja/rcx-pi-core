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

# --- Check 4: Conjecture/attribution without diagnostic evidence ---
# Catches definitive causal claims ("caused by", "due to", "the cause is")
# without grep/read evidence. Prevents blaming symptoms on unverified causes
# (e.g., attributing a crash to "Bun AVX" without tracing the actual error).
#
# Escape hatches (honest uncertainty is fine):
#   - Hedging words: likely, possibly, maybe, probably, might, could, appears
#   - Hypothesis markers: "I believe...but haven't verified", "hypothesis:"
#   - Tool result references: r[0-9]+ (citing prior tool output)
HAS_ATTRIBUTION=$(echo "$MSG" | grep -iEc "(caused by|due to|this is (a|an|the) .*(crash|issue|bug|error|failure)|the (root )?cause (is|was)|attributed to|because of the)" || true)
HAS_HEDGE=$(echo "$MSG" | grep -iEc "(likely|possibly|maybe|probably|may be|may not|might be|could be|appears to|seems to|hypothesis|I believe.*but|not verified|haven.t verified|unverified)" || true)
HAS_DIAGNOSTIC=$(echo "$MSG" | grep -iEc "(\.py:[0-9]+|\.js:[0-9]+|line [0-9]+|output shows|stderr shows|exit code [0-9]|traceback|the (error|exception) (at|in|from)|result.*r[0-9]+\b|traced to|verified by (running|reading|checking))" || true)
if [ "$HAS_ATTRIBUTION" -gt 0 ] && [ "$HAS_HEDGE" -eq 0 ] && [ "$HAS_DIAGNOSTIC" -eq 0 ]; then
    echo '{"decision":"block","reason":"Response attributes a cause as fact without diagnostic evidence or uncertainty hedging. Either (1) cite file:line or command output that proves the cause, or (2) use hedging language (likely, possibly, hypothesis) to signal this is unverified."}'
    exit 0
fi

# --- Check 5: Option-shopping before diagnosis ---
# Catches "Option A / Option B" or "Three options" near error/failure discussion
# without file:line evidence. Proposing fixes before finding the root cause.
HAS_OPTIONS=$(echo "$MSG" | grep -iEc "(option [A-C]|three options|two options|options:|approaches:|the fix (would|should|could) be)" || true)
HAS_ERROR_CONTEXT=$(echo "$MSG" | grep -iEc "(fail|error|crash|broke|issue|bug|timeout|dead|killed)" || true)
HAS_ROOT_EVIDENCE=$(echo "$MSG" | grep -iEc "(\.py:[0-9]+|\.js:[0-9]+|\.sh:[0-9]+|line [0-9]+|at line|result.*r[0-9]+\b)" || true)
if [ "$HAS_OPTIONS" -gt 0 ] && [ "$HAS_ERROR_CONTEXT" -gt 0 ] && [ "$HAS_ROOT_EVIDENCE" -eq 0 ]; then
    echo '{"decision":"block","reason":"Response proposes fix options before completing root-cause diagnosis. Find the source code file:line that causes the issue FIRST, then propose the fix. Options without diagnosis is premature closure."}'
    exit 0
fi

# --- Check 6: Labeling instead of diagnosing ---
# Catches "known pattern", "recurring issue", "same pattern as before" near errors.
# These label symptoms instead of tracing to source code.
HAS_LABEL=$(echo "$MSG" | grep -iEc "(known (pattern|issue)|recurring (issue|pattern|problem)|persistent (issue|pattern|problem)|same (pattern|issue) as|this is a .*(pattern|issue) we)" || true)
if [ "$HAS_LABEL" -gt 0 ] && [ "$HAS_ERROR_CONTEXT" -gt 0 ] && [ "$HAS_ROOT_EVIDENCE" -eq 0 ]; then
    echo '{"decision":"block","reason":"Response labels an issue as a known/recurring pattern without citing the root cause file:line. Labeling is not diagnosing. Trace to source code before categorizing."}'
    exit 0
fi

# --- Check 7: Dismissing without investigating ---
# Catches "should continue past", "handled by our fix", "not blocking" near errors
# without having shown diagnostic evidence for the current instance.
HAS_DISMISS=$(echo "$MSG" | grep -iEc "(should (continue|proceed|move) past|handled by (our|the|my) fix|not (actually )?blocking|we can (ignore|skip|move past)|cosmetic (only|issue|warning)|pre-existing|pre.existing)" || true)
if [ "$HAS_DISMISS" -gt 0 ] && [ "$HAS_ERROR_CONTEXT" -gt 0 ] && [ "$HAS_ROOT_EVIDENCE" -eq 0 ]; then
    echo '{"decision":"block","reason":"Response dismisses an error/issue without diagnostic evidence for THIS instance. Even if a prior fix exists, verify it applies here — cite file:line or tool output before dismissing."}'
    exit 0
fi

# --- Check 8: Restart without diagnosis ---
# Catches "restart", "re-dispatch", "retry the pipeline", "clear stale state"
# without a diagnosed root cause file:line. Restarting without understanding
# why it failed is the #1 premature-closure pattern in this codebase.
HAS_RESTART=$(echo "$MSG" | grep -iEc "(restart|re-dispatch|re-launch|retry the pipeline|clear stale state|restart from)" || true)
HAS_DIAGNOSIS=$(echo "$MSG" | grep -iEc "(\.py:[0-9]+|\.js:[0-9]+|root cause.*at|traced to|the (bug|issue|problem) is (at|in)|line [0-9]+ (of|in))" || true)
if [ "$HAS_RESTART" -gt 0 ] && [ "$HAS_DIAGNOSIS" -eq 0 ]; then
    echo '{"decision":"block","reason":"BLOCKED: Attempting to restart/retry pipeline without stating the diagnosed root cause file:line. Restarting without diagnosis is a PROTOCOL VIOLATION. Read the dispatch log, trace to source code, cite the file:line, THEN restart."}'
    exit 0
fi

# --- Check 9: Passive waiting with dead pipeline ---
# Catches "awaiting direction", "waiting for founder", "idle monitoring"
# when discussing a dead/failed pipeline. Standing auth says diagnose proactively.
HAS_PASSIVE=$(echo "$MSG" | grep -iEc "(awaiting (direction|founder|input|your)|waiting for (your|founder|direction)|idle monitor|ready (for|when you))" || true)
HAS_DEAD_PIPELINE=$(echo "$MSG" | grep -iEc "(pipeline (is )?(dead|down|failed|died)|failed at|recovery.*exhausted)" || true)
if [ "$HAS_PASSIVE" -gt 0 ] && [ "$HAS_DEAD_PIPELINE" -gt 0 ]; then
    echo '{"decision":"block","reason":"BLOCKED: Pipeline is dead and you are waiting passively. Standing auth (feedback_autonomous_executor_fix.md) says: detect failures proactively, not wait to be told twice. Diagnose NOW — read dispatch log, trace to source file:line, fix root cause."}'
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
