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
# 2026-04-11 founder directive: REMOVED "likely", "probably", "most likely"
# from HAS_HEDGE escape clause. Hedge words are no longer acceptable as
# substitutes for diagnostic evidence — they enable lazy conjecture cloaked
# in fake humility. Acceptable hedges remain: explicit hypothesis markers
# and "haven't verified" admissions.
#
# Escape hatches (honest uncertainty is fine):
#   - Acceptable: "I believe X but haven't verified", "hypothesis: X",
#                 "appears to" (visual/literal observation only),
#                 "I have not yet verified Y"
#   - REMOVED (denied): likely, probably, most likely, possibly, maybe,
#                       might, could, seems to (these became hedge cover
#                       for attribution without diagnosis — see learning.md
#                       2026-04-11 DEBUG entry on "most likely" anti-pattern)
HAS_ATTRIBUTION=$(echo "$MSG" | grep -iEc "(caused by|due to|this is (a|an|the) .*(crash|issue|bug|error|failure)|the (root )?cause (is|was)|attributed to|because of the)" || true)
HAS_HEDGE=$(echo "$MSG" | grep -iEc "(hypothesis|I believe.*but|not (yet )?verified|haven.t verified|unverified|I have not (yet )?verified)" || true)
HAS_DIAGNOSTIC=$(echo "$MSG" | grep -iEc "(\.py:[0-9]+|\.js:[0-9]+|line [0-9]+|output shows|stderr shows|exit code [0-9]|traceback|the (error|exception) (at|in|from)|result.*r[0-9]+\b|traced to|verified by (running|reading|checking))" || true)
if [ "$HAS_ATTRIBUTION" -gt 0 ] && [ "$HAS_HEDGE" -eq 0 ] && [ "$HAS_DIAGNOSTIC" -eq 0 ]; then
    echo '{"decision":"block","reason":"Response attributes a cause as fact without diagnostic evidence. Cite file:line or command output that proves the cause. Hedge words (likely/probably/most likely/maybe/possibly) are NOT acceptable substitutes — they have been removed from the escape hatch list per founder directive 2026-04-11. Acceptable alternatives: explicit hypothesis (\"hypothesis: X\"), unverified admission (\"I have not yet verified Y\"), or direct evidence (file:line)."}'
    exit 0
fi

# --- Check 4b: Hedge denylist (founder directive 2026-04-11) ---
# Standalone block on hedge words used as cover for unverified claims.
# Triggers regardless of attribution context. The pattern catches
# "most likely", "likely", "probably" used to dilute claim certainty
# without backing diagnostic evidence.
HAS_DENIED_HEDGE=$(echo "$MSG" | grep -iEc "(\bmost likely\b|\blikely\b|\bprobably\b|\bmost likely\b)" || true)
HAS_DIAG_OR_HYPOTH=$(echo "$MSG" | grep -iEc "(\.py:[0-9]+|\.js:[0-9]+|\.sh:[0-9]+|line [0-9]+|hypothesis:|I have not (yet )?verified|haven.t verified|verified by)" || true)
if [ "$HAS_DENIED_HEDGE" -gt 0 ] && [ "$HAS_DIAG_OR_HYPOTH" -eq 0 ]; then
    echo '{"decision":"block","reason":"BLOCKED: Response uses denied hedge word (likely/probably/most likely) without diagnostic evidence or explicit hypothesis marker. These words are on the deny list per founder directive 2026-04-11. Either (1) cite file:line that proves the claim, or (2) state \"hypothesis: X\" / \"I have not yet verified Y\" explicitly. Lazy hedging cloaked in fake humility is not acceptable."}'
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

# --- Check 7a: Dismissing with file:line cover ---
# Catches "should continue past", "handled by our fix", "not blocking" near errors
# without having shown diagnostic evidence for the current instance.
# (Note: this check has an escape via HAS_ROOT_EVIDENCE because some dismissals
# are legitimate when paired with the source-of-truth file:line.)
HAS_DISMISS=$(echo "$MSG" | grep -iEc "(should (continue|proceed|move) past|handled by (our|the|my) fix|not (actually )?blocking|we can (ignore|skip|move past)|cosmetic (only|issue|warning))" || true)
if [ "$HAS_DISMISS" -gt 0 ] && [ "$HAS_ERROR_CONTEXT" -gt 0 ] && [ "$HAS_ROOT_EVIDENCE" -eq 0 ]; then
    echo '{"decision":"block","reason":"Response dismisses an error/issue without diagnostic evidence for THIS instance. Even if a prior fix exists, verify it applies here — cite file:line or tool output before dismissing."}'
    exit 0
fi

# --- Check 7b: "Pre-existing" / "known flake" denylist (founder directive 2026-04-11) ---
# Founder directives 2026-04-11:
#   1. "the point is that it doesn't matter if it's pre-existing — we don't just ignore it"
#   2. "if it's non-blocking we can add to non-blocking in /deferred, while
#       blocking needs to be taken care of"
#
# Operational rule: pre-existing failures get one of TWO actions:
#   (a) BLOCKING failure → fix the root cause
#   (b) NON-BLOCKING failure → file to reports/deferred/ and continue
#
# The hook fires when "pre-existing" / "known flake" / "already broken" appears
# in an error context UNLESS the response shows one of the two action paths:
#   - HAS_FIX_INTENT: "fixing now", "root cause is", "applying fix", "patch:"
#   - HAS_DEFER_ACTION: "reports/deferred", "deferring to", "adding to deferred",
#                       "filed to deferred", "/deferred"
#
# Allowed historical references (won't trigger because no error_context):
#   - "Learning entry: 2026-04-08 fixed pre-existing flake X" (in a doc)
#   - "git blame shows this pattern was pre-existing" (without error context)
HAS_PRE_EXISTING_DISMISS=$(echo "$MSG" | grep -iEc "(pre-existing|pre.existing|pre existing|already (broken|failing|flaky)|known flake|known flaky|flaky test|test is flaky|\bflake\b|\bflaky\b)" || true)
HAS_FIX_INTENT=$(echo "$MSG" | grep -iEc "(fixing now|fixing it|root cause is at|applying (the |a )?fix|patching|patch applied|reproducing first|reproduce.*first|writing the fix|landing the fix)" || true)
HAS_DEFER_ACTION=$(echo "$MSG" | grep -iEc "(reports/deferred|/deferred|deferring to|adding to deferred|filed (to|under) deferred|defer.*as non.blocking|non.blocking.*defer)" || true)
if [ "$HAS_PRE_EXISTING_DISMISS" -gt 0 ] && [ "$HAS_ERROR_CONTEXT" -gt 0 ] && [ "$HAS_FIX_INTENT" -eq 0 ] && [ "$HAS_DEFER_ACTION" -eq 0 ]; then
    echo '{"decision":"block","reason":"BLOCKED: Response treats a failing test/error as pre-existing or a flake without taking either of the two acceptable actions. Founder directive 2026-04-11: \"It does not matter if it is pre-existing — we do not just ignore it. If non-blocking we can add to /deferred; if blocking it needs to be taken care of.\" Required next move: (1) BLOCKING — fix the root cause and cite file:line of the fix, or (2) NON-BLOCKING — file the finding under reports/deferred/ with an explanation. Choose one. Categorizing as pre-existing without action is not acceptable."}'
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
