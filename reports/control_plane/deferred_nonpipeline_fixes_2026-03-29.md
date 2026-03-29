# Deferred Non-Pipeline Fixes

**Phase-A-Lock: LOCKED**
**Task:** [NEXT-CODEX-POST-REDTEAM]
**Wave class:** L4_ENABLER
**Target gate:** G8

---

## Scope (3 fixes + 1 pipeline fix)

### Fix 1: Agent-compliance hook fails open on missing/empty transcript
**File:** `.claude/hooks/validate-agent-compliance.sh`

The hook claims "FAILS CLOSED" (line 8) but contradicts this at:
- Line 48-49: exits 0 (allow) when transcript path is empty or file missing
- Line 66-67: exits 0 (allow) when extracted output is empty

**Change:** Replace both `exit 0` with block JSON output:
```bash
# Line 48-49: Change from:
if [ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ]; then
  exit 0
fi
# To:
if [ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ]; then
  jq -n '{"decision": "block", "reason": "Agent transcript missing or path empty — cannot verify compliance (fail closed)"}'
  exit 0
fi

# Line 66-67: Change from:
if [ -z "$AGENT_OUTPUT" ]; then
  exit 0
fi
# To:
if [ -z "$AGENT_OUTPUT" ]; then
  jq -n '{"decision": "block", "reason": "Agent produced no extractable output — cannot verify compliance (fail closed)"}'
  exit 0
fi
```

### Fix 2: Terminal escape injection via bot comment bodies
**File:** `mu/tools/observability/_pane_prci.sh`

Line 47 echoes unsanitized bot comment bodies that could contain terminal escape sequences from PR comments.

**Change:** Pipe the jq output through `sed` to strip ANSI/terminal escape sequences:
```bash
# Line 47: Add escape sanitization
BOT_COMMENTS=$(gh pr view "$PR" --json comments --jq '...' 2>/dev/null | sed 's/\x1b\[[0-9;]*[a-zA-Z]//g') || BOT_COMMENTS=""
```

### Fix 3: Bridge zero-output stale timeout too low for Codex xhigh
**File:** `mu/tools/agents/bridge_supervisor.py`

Line 89: `BRIDGE_ZERO_OUTPUT_TIMEOUT_S = 240.0` — Codex with xhigh reasoning regularly exceeds 240s of thinking before emitting stdout. Increase to 600s.

## Validation (Phase B-local)
```bash
# Hook test
echo '{"agent_type":"verifier","agent_transcript_path":""}' | bash .claude/hooks/validate-agent-compliance.sh
# Should output block JSON, not exit silently

# Pane script syntax check
bash -n mu/tools/observability/_pane_prci.sh

```

Note: W5A gate test (re-entry coverage) deferred to a separate wave — not in scope for this wave.
