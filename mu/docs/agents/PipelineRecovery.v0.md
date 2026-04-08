<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-03-31
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

---
DOC_STATUS: DRAFT
---

# Pipeline Recovery System — Design v0

**Date:** 2026-03-31
**Status:** DRAFT — design only, not implemented
**Author:** Claude Opus 4.6 / Jeff Abrams

---

## Architecture Overview

The recovery system sits between `executor_dispatch.py` and the individual executors. It intercepts failure results and classifies them into four tiers.

```
                     executor_dispatch.py
                             |
                      dispatch() result
                             |
                +--- recovery_gate.py ---+
                |                        |
         classify_failure()        recovery_log.json
                |
   +------+------+------+------+
   |      |      |      |      |
 Tier 1  Tier 2  Tier 3  Tier 4
 (fix)   (retry) (diag)  (esc)
   |      |      |      |
 cleanup retry  claude   STOP
 + retry        haiku    + report
                + retry
```

**Key constraint:** `recovery_gate.py` is a single-file module importing only stdlib + `executor_common.py`. It never imports `bridge_supervisor`, `bridge_adapters`, or any agent module. Tier 3 diagnosis calls `claude --print` directly via subprocess — no bridge loop, no SDK agents.

---

## Failure Classification Taxonomy

```python
class FailureClass(Enum):
    # Tier 1 — deterministic auto-fix (zero tokens)
    STALE_BRIDGE_LOCK = "stale_bridge_lock"
    STALE_GIT_INDEX_LOCK = "stale_git_index_lock"
    STALE_EXECUTOR_STATE = "stale_executor_state"
    STALE_CONTINUATION = "stale_continuation"
    MIXED_STAGING = "mixed_staging"

    # Tier 2 — auto-retry with adjustment (zero tokens)
    PROCESS_TIMEOUT = "process_timeout"
    TRANSIENT_KILL = "transient_kill"
    AGGREGATION_HANG = "aggregation_hang"
    IMPLEMENTER_STALE = "implementer_stale"

    # Tier 3 — LLM diagnosis (small focused prompt)
    GIT_STAGING_CONFLICT = "git_staging_conflict"
    TEST_FAILURE = "test_failure"
    AGENT_REVIEW_CRASH = "agent_review_crash"
    UNKNOWN_ERROR = "unknown_error"

    # Tier 4 — escalate (never recover)
    TERMINAL_POLICY = "terminal_policy"
    UNCLASSIFIED = "unclassified"
```

Classification is pure dict inspection — reads `result["status"]`, `result["step"]`, `result.get("stderr")`, exit codes. No external calls.

---

## Tier Definitions

### Tier 1: Deterministic Auto-Fix (zero tokens)

| Failure Signal | Detection | Recovery |
|---|---|---|
| `.agent_bus/bridge.lock` held by dead PID | `kill -0 pid` fails | Truncate lock file |
| `.git/index.lock` exists | `Path.exists()` | `os.unlink()` |
| Stale `phase_b_state.json` from prior run | wave_id mismatch with current routing | `Path.unlink()` |
| Stale commit_executor continuation records | File age > 1h, no executor alive | `Path.unlink()` |
| Mixed staged/unstaged state | `git status --porcelain` shows both index and worktree changes | `git reset HEAD -- <files>` |

After fix: retry the failed step via `dispatch()` with same routing.

### Tier 2: Auto-Retry with Adjustment (zero tokens)

| Failure Signal | Detection | Recovery |
|---|---|---|
| Process timeout | `status == "timeout"` | Increase timeout 50% (capped 2x), retry once |
| Transient process kill | exit_code in (-9, -15, 137) | Retry with same parameters |
| Bridge aggregation hang | stderr contains "aggregation" | Clear bridge state, retry |
| Implementer stale timeout | `implementer_status == "stale"` | Increase stale timeout, retry |

Timeout adjustments passed via `RCX_RECOVERY_TIMEOUT_OVERRIDE` env var.

### Tier 3: LLM Diagnosis (one focused API call)

| Failure Signal | Detection | Recovery |
|---|---|---|
| Git staging conflict | `git add` failure in commit_executor | Claude reads git status + error, emits shell commands |
| Test failure in pre-commit | supervisor_rejected with test output | Claude reads test output (last 100 lines), emits diagnosis |
| Agent review crash | partial status JSON, no report | Claude reads partial status + agent log, decides retry/skip/escalate |
| Unknown executor error | `status == "error"` with no Tier 1/2 match | Claude reads error JSON + log tail, emits recovery plan |

**Tier 3 uses a Recovery Loop (not one-shot):**

```
Recovery Loop:  Diagnose → Implement Fix → Verify → ─(pass)─→ Re-enter Pipeline
                  ↑                          |
                  └───────(fail, max 3)──────┘
                              |
                         (exhausted)
                              ↓
                    Escalate + Learning Store
```

- **Diagnose**: Claude reads error + logs (~2K token focused prompt)
- **Implement Fix**: Claude emits shell commands OR small code edits (NOT a full Phase B pass)
- **Verify**: Run the specific check that failed (one gate, not full audit_fast)
- **Max 3 iterations**, then escalate to Tier 4
- Invocation: `subprocess.run(["claude", "--print", "-p", prompt_text], timeout=60)` — NOT through bridge adapter stack (bootstrap paradox)
- Token budget: ~2000 input, ~200 output per iteration

**Key constraint:** Recovery does NOT invoke Phase B, bridge review, or SDK agents. The recovery loop is lighter than the main pipeline — it diagnoses, applies a bounded fix, and verifies the specific gate that failed. If the fix works, re-enter the main pipeline at the failed step.

### Tier 4: Escalate

| Failure Signal | Detection | Recovery |
|---|---|---|
| Same failure after 3 recovery loop iterations | Recovery loop exhausted | Stop + detailed report |
| Same failure after 2 recovery gate attempts | Recovery log shows 2 prior attempts for (wave_id, step, class) | Stop + report |
| Terminal executor outcome | `question_for_founder`, `max_rounds_reached`, `supervisor_rejected` | Never recover — these are policy decisions |
| Unknown failure class | Classifier returns None | Stop + report |
| Recovery script itself failed | Tier 3 commands returned nonzero | Stop + report both errors |

---

## Learning Store

The learning store turns recovery_log.json into an adaptive system. It sits on top of the existing logging infrastructure and adds three capabilities: pattern promotion, cross-session persistence, and subagent learning injection.

### Architecture: Two-Tier Storage

```
Tier A: Ephemeral Log (per-worktree)
  .agent_bus/recovery/recovery_log.json    ← already exists (RecoveryAttempt records)
  - Written by attempt_recovery(), run_recovery_loop(), attempt_tier2_recovery()
  - Capped at 500 entries, dies with worktree
  - Raw event stream: every attempt, success or failure

Tier B: Persistent Learning Store (main repo)
  .agent_bus/recovery/learned_patterns.json  ← NEW
  - Promoted patterns extracted from Tier A
  - Survives worktree cleanup (synced to main repo before worktree teardown)
  - Read at pipeline start, written after recovery events
```

**Sync protocol:** When a worktree is created, copy `learned_patterns.json` from the main repo. When a worktree is torn down (or after any successful promotion), sync `learned_patterns.json` back. Dispatch already has pre/post worktree hooks — add sync there.

### Data Model: LearnedPattern

```python
@dataclass
class LearnedPattern:
    """A recovery pattern that has been observed enough times to be trusted."""
    pattern_id: str                 # Stable hash of (failure_class, action, fingerprint)
    failure_class: str              # FailureClass enum value
    action: str                     # The fix action that worked
    fingerprint: str                # Stderr/error text snippet for matching
    promoted_tier: int              # Current tier (1=auto-fix, 2=auto-retry, 3=LLM)
    original_tier: int              # Tier when first observed
    success_count: int              # Total successful applications
    failure_count: int              # Total failed applications after promotion
    last_success: str               # ISO timestamp
    last_failure: str | None        # ISO timestamp or None
    created_at: str                 # First observation
    updated_at: str                 # Last modification
    environment_tags: list[str]     # Machine-specific context (e.g., ["no-avx", "darwin"])
    detail: str                     # Human-readable description of what this pattern fixes
    expired: bool                   # Soft-expired (not seen in 30 days)
```

**pattern_id derivation:** `sha256(f"{failure_class}:{action}:{fingerprint[:80]}")[:12]`. The fingerprint is the first 80 chars of the stderr pattern that triggered classification. This ensures the same failure on the same machine maps to the same pattern across worktrees and sessions.

### Promotion Lifecycle

```
            observe()     observe()     observe()
  Unknown  ─────────►  Seen (1x)  ─────────►  Seen (2x)  ─────────►  PROMOTED
                           │                      │                    (Tier 1)
                           │                      │                       │
                       (different                (env                  apply()
                        machine)                 change)                  │
                           │                      │              ┌───────┤
                           ▼                      ▼              │  success
                     Reset counter          Reset counter        │    │
                                                                 │    ▼
                                                              observe()
                                                              (count++)
                                                                 │
                                                              failure
                                                                 │
                                                                 ▼
                                                              DEMOTED
                                                             (Tier 2→3)
```

**Promotion rules:**
1. Same `(failure_class, action)` succeeds **3 times** across **at least 2 distinct wave_ids** → promote to Tier 1
2. The "distinct wave_ids" requirement prevents a single flaky wave from promoting a coincidental fix
3. Promotion is idempotent — re-promoting an already-promoted pattern just updates `last_success`
4. Promoted patterns are checked BEFORE the static classifier in `classify_failure()` — they override default tier assignment

**Demotion rules:**
1. A promoted Tier 1 pattern that fails → demote to Tier 2 (auto-retry, one more chance)
2. A demoted Tier 2 pattern that fails again → demote to Tier 3 (back to LLM diagnosis)
3. Demotion resets `failure_count` to 0 and increments a `demotion_count` field
4. A pattern demoted 3 times is permanently locked at Tier 3 (unstable fix — don't trust)

**Expiry:**
- Patterns not seen for 30 days: set `expired: true` — still in the store but not auto-applied
- Expired patterns can be re-promoted if observed again (resets the timer)
- Patterns not seen for 90 days: eligible for cleanup (removed from store during compaction)

### Cross-Session Persistence Bridge

The recovery log (`recovery_log.json`) is ephemeral — it dies with the worktree. The learning store (`learned_patterns.json`) persists. The bridge between them:

1. **On worktree creation:** Copy `learned_patterns.json` from main repo → worktree `.agent_bus/recovery/`
2. **After each recovery attempt:** Check promotion eligibility against combined log (worktree log + store history)
3. **On promotion/demotion:** Write updated `learned_patterns.json` in worktree
4. **On worktree teardown:** Sync `learned_patterns.json` back to main repo (merge, not overwrite — concurrent worktrees may have different patterns)
5. **Merge strategy:** Union of patterns. If same `pattern_id` exists in both, keep the one with higher `success_count` + more recent `updated_at`

### Integration with .claude/rules/learning.md

The Claude session learning log (`.claude/rules/learning.md`) and the recovery gate learning store serve different purposes but can cross-pollinate:

| Aspect | `.claude/rules/learning.md` | `learned_patterns.json` |
|--------|---------------------------|------------------------|
| Scope | Main Claude session errors | Pipeline recovery attempts |
| Written by | capture-learning.sh hook + manual | recovery_gate.py |
| Read by | Main Claude (auto-loaded rule) | recovery_gate.py classify_failure() |
| Format | Markdown fingerprint entries | Structured JSON |
| Persistence | Git-tracked file (permanent) | .agent_bus file (synced) |

**Cross-pollination protocol:**
- When a new `LearnedPattern` is promoted, also append a corresponding entry to `.claude/rules/learning.md` so the main Claude session knows about it. Use the existing format: `- [DATE] PIPELINE | fingerprint: \`text\` | refs: N`
- When `.claude/rules/learning.md` has a `FIXED` entry with a concrete fix action, the recovery gate can look for a matching `fingerprint` in the static classifier's patterns and consider it for Tier 1 candidacy
- This is one-way advisory, not hard coupling — either system works independently

### Subagent Learning Injection

The 9 SDK review agents (adversary, verifier, etc.) currently start cold every run. The learning store can warm them:

1. **At agent prompt construction** (`run_single_agent()` in `run_review.py`): Read `learned_patterns.json` and `.claude/rules/learning.md` for entries tagged with the current agent's failure patterns
2. **Inject as `learning_context`** alongside existing `memory_context` and `cs_context`:
   ```python
   learning_entries = load_relevant_learnings(agent_name, self.files)
   learning_context = format_learning_context(learning_entries, max_len=1000)
   ```
3. **Filter by relevance:** Only inject entries where `failure_class` matches patterns the agent would encounter (e.g., adversary gets security-related learnings, expert gets complexity learnings)
4. **Budget:** Cap at 1000 tokens — learning context should not dominate the agent's prompt. Most recent entries first.

### Environment Fingerprinting

Different machines produce different failure patterns. The learning store captures environment context:

```python
def _environment_tags() -> list[str]:
    tags = [sys.platform]                           # "darwin", "linux"
    if not _has_avx_support():
        tags.append("no-avx")                       # Bun AVX warnings
    if shutil.which("claude") is None:
        tags.append("no-claude-cli")                 # Tier 3 unavailable
    return tags
```

Patterns are tagged at creation. Promotion considers environment: a pattern that works on `darwin+no-avx` but hasn't been seen on `linux` is only auto-applied on matching environments.

### Security Constraints

1. **No code execution from learned patterns.** Promoted Tier 1 fixes must map to existing `fix_fn` functions in recovery_gate.py — they cannot introduce new shell commands. The learning store adjusts ROUTING (which existing fix to apply), not BEHAVIOR.
2. **Fingerprint poisoning.** An adversarial stderr message could match a learned pattern and trigger the wrong fix. Mitigation: fingerprints are matched against the FIRST 80 chars of the classifier's extracted signal, not raw stderr. The classifier extracts signal before matching.
3. **Promotion flooding.** A rapid-fire test loop could generate 3+ successes for a bad pattern. Mitigation: "distinct wave_ids" requirement — 3 successes must span at least 2 different waves.
4. **Demotion evasion.** A pattern that works 99% of the time but fails catastrophically 1%. Mitigation: single failure demotes immediately. The cost of one unnecessary LLM call (Tier 3) is far less than the cost of a silently wrong auto-fix.

### Implementation Sketch

```python
# In recovery_gate.py — new functions

def check_learned_patterns(
    repo_root: Path, failure_class: str, stderr_signal: str
) -> LearnedPattern | None:
    """Check if a learned pattern matches this failure. Returns pattern or None."""
    store = _load_learning_store(repo_root)
    for pattern in store:
        if (pattern["failure_class"] == failure_class
                and not pattern["expired"]
                and _fingerprint_matches(pattern["fingerprint"], stderr_signal)
                and _environment_matches(pattern["environment_tags"])):
            return LearnedPattern(**pattern)
    return None

def observe_outcome(
    repo_root: Path, failure_class: str, action: str,
    fingerprint: str, outcome: str, wave_id: str
) -> None:
    """Record an outcome and check for promotion/demotion."""
    store = _load_learning_store(repo_root)
    pattern = _find_or_create(store, failure_class, action, fingerprint)
    if outcome == "success":
        pattern.success_count += 1
        pattern.last_success = _now_iso()
        _check_promotion(pattern, store, wave_id)
    else:
        pattern.failure_count += 1
        pattern.last_failure = _now_iso()
        _check_demotion(pattern)
    _save_learning_store(repo_root, store)
```

**Call sites:** Insert `check_learned_patterns()` at the top of `classify_failure()` (before static classification). Insert `observe_outcome()` at each `_save_recovery_log()` call site (6 total). The integration is mechanical — no architectural changes needed.

---

## Bounded Retry Policy

- **Recovery loop**: max 3 diagnose/fix/verify iterations per Tier 3 invocation
- **Recovery gate**: max 2 attempts per (wave_id, step, failure_class) tuple
- Different failure classes counted independently
- Recovery log at `.agent_bus/recovery/recovery_log.json` (capped at 500 entries)
- Dispatch `max_attempts` is independent outer bound
- Terminal policy outcomes are never recovered

```json
{
  "attempts": [
    {
      "timestamp": "2026-03-31T14:22:00Z",
      "wave_id": "wave1a-validation",
      "step": "stage_files",
      "failure_class": "stale_git_index_lock",
      "tier": 1,
      "action": "unlink .git/index.lock",
      "outcome": "success",
      "duration_s": 0.3,
      "tokens_used": 0
    }
  ]
}
```

---

## Re-entry Protocol

After recovery, the pipeline resumes at the failed step using existing mechanisms:

1. **Phase B resume** — `phase_b_executor.py` persists state at `.agent_bus/executors/phase_b_state.json`. Recovery preserves valid state (environmental failure) or clears stale state.
2. **Commit continuation** — `commit_executor.py:_load_post_commit_continuation()` resumes post-commit steps from continuation records.
3. **Dispatch retry** — `executor_dispatch.py` retry loop (line ~1098-1144) with `_clear_phase_b_state_for_retry()` and `_auto_refresh_routing()`.

The recovery gate hooks into the dispatch retry loop between `_is_terminal_executor_outcome()` and the retry sleep. Returns modified result with `status: "recovered"` (loop retries) or original result (loop handles normally).

---

## Observability

**Recovery log** — `.agent_bus/recovery/recovery_log.json` is source of truth.

**Web dashboard** — Add `recovery_status()` to `get_state()`:
- "Idle" / "Recovering (Tier N): failure_class" / "Escalated: reason"
- Recent attempts table

**tmux pane** — Add "RECOVERY" section after "BRIDGE" block:
- Last attempt: tier, action, outcome, age
- Active recovery indicator

---

## Anti-Patterns

1. **Bootstrap paradox** — Never import bridge_supervisor/bridge_adapters in recovery. Use `claude --print` directly for Tier 3.
2. **Infinite loops** — 2-attempt bound per (wave, step, class). Never retry terminal policy outcomes.
3. **Masking real bugs** — Recovery doesn't modify source code or skip tests. Tier 3 can diagnose but only emit cleanup commands.
4. **Accidental kills** — Never use `pkill -f`. Use `terminate_process_tree()` with specific PIDs.
5. **Expensive Tier 3** — Cap at 2000 input tokens, 200 output. Not a code review task.
6. **Recovering policy decisions** — `question_for_founder`, `supervisor_rejected`, etc. are the pipeline working correctly.

---

## Implementation Phases

| Phase | Scope | Effort |
|---|---|---|
| **1** | Classifier + Tier 1 auto-fix + recovery log | 1 wave |
| **2** | Tier 2 auto-retry + timeout adjustment | 0.5 wave |
| **3** | Observability (dashboard + tmux) | 0.5 wave |
| **4** | Tier 3 LLM diagnosis + remediation | 1 wave |
| **5** | Bounded retry integration + end-to-end test | 0.5 wave |

**New file:** `mu/tools/executors/recovery_gate.py`
**Modified files:** `executor_dispatch.py` (hook), `pipeline_dashboard_web.py` (UI), `_pane_processes.sh` (tmux)
