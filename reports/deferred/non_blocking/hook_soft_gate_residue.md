# Hook Soft-Gate Residue (Deferred)

**Date:** 2026-03-20
**Wave:** P0 Hook Remediation
**Status:** DEFERRED (acceptable risk for soft gates)
**Founder Decision:** 2026-03-20

---

## Context

During P0 hook remediation, Codex found additional edge cases that are intentional-circumvention class or annoyance-level false positives. Per founder decision, these are deferred as acceptable soft-gate residue rather than expanding scope into command parsing.

## Deferred Findings

### 1. Quote-Split Git Bypass (POLICY_BOUND)

**File:** `.claude/hooks/block-protected-branch.sh:11`
**Attack:** `gi""t commit -m x` bypasses regex
**Classification:** Intentional circumvention, out of scope
**Rationale:** The hook catches 99% of accidental protected-branch violations. Quote-splitting requires intentional bad faith. Real enforcement is git pre-commit hook.

### 2. Quote-Split Bridge Bypass (POLICY_BOUND)

**File:** `.claude/hooks/check-agents-before-bridge.sh:7-13`
**Attack:** `br""idge_supervisor.py review` or similar quote-splitting bypasses regex
**Classification:** Intentional circumvention, out of scope
**Rationale:** Same as above. Protocol enforcement is wave discipline, not perfect regex.

### 3. Protected-Branch False Positive on Inert Text (DOC_ACCURACY)

**File:** `.claude/hooks/block-protected-branch.sh:11`
**Example:** `echo git commit` triggers block
**Classification:** Annoyance, not security break
**Rationale:** Rare in practice. User can dismiss or rephrase.

### 4. Bridge Hook False Positive Eliminated

**File:** `.claude/hooks/check-agents-before-bridge.sh:7-13`
**Status:** RESOLVED in P0 wave
**Fix:** Matcher now requires subcommand after `.py` or exact module path `-m tools.agents.bridge_supervisor`
**Example:** `sed -n '1,5p' tools/agents/bridge_supervisor.py` no longer triggers (no subcommand after `.py`)

### 5. Protected-Branch False Positive on Chained Commands (DOC_ACCURACY)

**File:** `.claude/hooks/block-protected-branch.sh:14`
**Example:** `git status && ./tools/pre-push-fast` triggers block (matches "push" in path)
**Classification:** Annoyance, not security break
**Rationale:** The regex `\bgit\b.*\b(push|...)\b` matches any occurrence of `push` as a word, not just as a git subcommand. Real enforcement is git pre-commit hook.

### 5b. Bridge Hook False Positive on Echo Commands (DOC_ACCURACY)

**File:** `.claude/hooks/check-agents-before-bridge.sh:24`
**Example:** `echo bridge_supervisor.py --repo-root /tmp review` triggers block
**Classification:** Annoyance, not security break
**Rationale:** Same regex-based matching limitation as protected-branch hook. The command regex catches the pattern in inert text. Real enforcement is wave discipline.

### 5c. Manual Review File Satisfies Evidence Gates (POLICY_BOUND)

**Files:** `.claude/hooks/check-agents-before-bridge.sh:67-70`, `tools/checks/check_agent_review_needed.sh:43-49`
**Example:** `printf 'manual note' > reports/manual_review.md` satisfies both the bridge evidence check and the session-start review checker
**Classification:** Intentional circumvention, out of scope
**Rationale:** The gate's purpose is catching "forgot to run agents" not "intentionally bypassed". Creating a manual review file requires deliberate action. Content inspection would add complexity for minimal value. Same class as quote-split bypasses.

---

## Founder Decision (2026-03-20)

### 6. Native Subagent Evidence Not Bridge-Eligible (RESOLVED - OPTION A)

**File:** `.claude/hooks/check-agents-before-bridge.sh:39-72`
**Context:** Cross-repo leakage fix removed `/private/tmp/claude-*/` scanning. Native subagents write there (Claude Code controlled), so they no longer satisfy the bridge gate.

**Decision:** Option A — Native subagents are NOT bridge-eligible. Only SDK agents (`run_review.py`) or explicit `.agent_bus/` writes satisfy the gate.

**Rationale (per founder):**
- CLAUDE.md:158,161 already states native subagents are ad-hoc and do not replace run_review.py
- Wave protocol requires run_review.py before bridge (CLAUDE.md:38,45)
- AgentRunbook.v0.md:46,352,412 makes the same boundary explicit
- Option B (SubagentStop hook persistence) would be a separate feature wave, not a fix-wave detail

**Current behavior:** Native subagents trigger bridge block asking to run SDK agents first.
**Impact:** Low — SDK agents are the primary review path. Native subagents remain useful for ad-hoc checks.

---

## Next Wave: Hook Hardening (#3, #4 from P0 Codex review)

### 7. Agent-Compliance Hook Fails Open on Missing/Empty Transcript (DEFECT)

**File:** `.claude/hooks/validate-agent-compliance.sh:42-62`
**Issue:** Hook exits 0 (no block) when transcript path doesn't exist or extracted output is empty
**Evidence:** `printf '{"agent_type":"verifier","agent_transcript_path":"/nonexistent"}' | ./.claude/hooks/validate-agent-compliance.sh` → exits 0
**Fix Required:** Emit block JSON when transcript is missing or has no assistant output
**Severity:** Medium

### 8. Validator Accepts Garbage as Compliant (DEFECT)

**File:** `tools/runners/validate_agent_compliance.py:476,579`
**Issue:** `--strict` mode allows `compliant: true` for input with zero findings/structure
**Evidence:** `printf 'nonsense\n' | python3 tools/runners/validate_agent_compliance.py --json --strict` → `compliant: true`
**Fix Required:** Require at least one structured finding block or explicit verdict for compliance
**Severity:** Medium

---

## Resolution Path

If these become problematic in practice:
1. Replace raw command-string matching with proper command parsing
2. Use argv[0] detection instead of substring search
3. Add regression tests for quote-splitting and inert-text cases

For now: ship current P0 fixes, monitor in practice.
