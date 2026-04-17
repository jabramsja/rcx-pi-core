<!--
DOC_STATUS
TYPE: IMPLEMENTATION
LAST_VERIFIED: 2026-04-16
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
DOC_STATUS: IMPLEMENTATION
---

# Pipeline Recovery System — Design v0

**Date:** 2026-04-16
**Status:** IMPLEMENTED behind `hybrid_recovery_enabled: false` rollout gate
**Author:** Claude Opus 4.6 / Jeff Abrams

---

## Architecture Overview

`recovery_gate.py` still sits between `executor_dispatch.py` and the individual
executors, but Tier 3 is now split into two branches:

1. deterministic `shell` / literal `edit` actions for the existing bounded path
2. a gated `delegate_implementer` branch that reuses `phase_b_implementer`
   only for a narrow control-surface repair and only after recovery captures its
   own scope / inventory / git-control baseline

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
 cleanup retry  shell/edit or  STOP
 + retry        delegate_implementer
                + retry
```

**Current implementation truth**

- Tier 1 and Tier 2 remain deterministic.
- Tier 4 remains a hard escalation boundary.
- Tier 3 diagnosis still runs through the configured recovery-agent path and
  returns JSON only; diagnosis does not get tool-use rights.
- The hybrid branch is disabled by default behind
  `hybrid_recovery_enabled: false`.
- `recovery_gate.py` remains stdlib + `executor_common` at module import time.
  The hybrid branch lazy-loads `phase_b_implementer` only after payload
  validation and baseline capture, with bytecode writes suppressed so the
  loader itself does not create repo-local `__pycache__` drift outside the
  admitted scope contract.
- The learning store remains routing + warming only. It may warm the
  implementer prompt, but it does not expand write or validator authority.

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

### Tier 3: LLM Diagnosis + Hybrid Delegate

| Failure Signal | Detection | Recovery |
|---|---|---|
| Git staging conflict | `git add` failure in commit_executor | diagnosis may still emit bounded `shell` |
| Test failure in pre-commit | supervisor_rejected with test output | diagnosis may emit bounded `shell`, `edit`, or `delegate_implementer` |
| Agent review crash | partial status JSON, no report | diagnosis may retry/skip/escalate; bootstrap/adapter faults are not hybrid-eligible |
| Unknown executor error | `status == "error"` with no Tier 1/2 match | diagnosis may choose `delegate_implementer` only when the bounded contract below is satisfiable |

**Recovery loop**

```
Recover: Diagnose → Apply bounded action → Audit → Validate → Audit → Retry
                         ↑                                      |
                         └────────────── (fail / max 3) ────────┘
```

**Structured `delegate_implementer` contract**

- `action` must be `delegate_implementer`.
- `commands` must be a singleton array containing exactly one object.
- `files_in_scope` may resolve only to:
  - `mu/tools/executors/recovery_gate.py`
  - `mu/tools/executors/executor_common.py`
- landing-surface-only files remain outside runtime delegation:
  - `mu/tools/executors/executor_config.json`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/docs/agents/PipelineRecovery.v0.md`
- bootstrap / adapter / implementer surfaces remain ineligible:
  - `mu/tools/executors/phase_b_implementer.py`
  - `.agent_bus/bridge_config.json`
  - bridge adapter loading / selection / invocation bootstrap faults
- `validation_spec` is a closed schema:
  - only `pytest_targeted`
  - only targets from `mu/tests/tools/test_recovery_gate.py` and
    `mu/tests/tools/test_phase_b_executor.py`
  - no raw `validation_commands`
  - no `args`
  - no unsupported validator ids or fields

**Observed-drift and validator contract**

- recovery captures a pre-run manifest for every pre-existing non-directory path
  outside `.git/`, plus a repo-root inventory that still descends into
  `.scratch/`
- the exact `.scratch` exception set is:
  - repo-root `.scratch/` directory node
  - `.scratch/phase_b_implementer_prompt.md`
  - `.scratch/phase_b_implementer_output_<job>.txt`
- any other `.scratch/*` descendant, symlink, `readlink` target change, or
  file/link/directory type transition fails closed
- hybrid success requires two audits against the same pre-launch baseline:
  - immediately after implementer return and before validator execution
  - again after validator execution and before any retry/success outcome
- these audits prove only surviving-drift evidence at the checkpoints. They do
  **not** prove the absence of transient out-of-scope create-delete or
  modify-restore touches that leave no trace by the time the snapshot is taken
- hybrid success also requires exact equality of the repo-local git-control
  tuple across both checkpoints:
  - `.git/index`
  - `HEAD`
  - every ref returned by `git for-each-ref`, including tags and remote refs
  - remote config

**Executor-owned verification**

- recovery builds validator argv/env itself; diagnosis does not hand recovery
  shell text
- `pytest_targeted` runs with:
  - `[sys.executable, "-m", "pytest", "-x", "--tb=short", "-p", "no:cacheprovider", *targets]`
  - `PYTHONHASHSEED=0`
  - `PYTHONDONTWRITEBYTECODE=1`
  - isolated `TMPDIR` / `XDG_CACHE_HOME` outside repo root

**Governance proof limit**

- this packet proves repo-local git-control immutability and bounded
  surviving-drift at the checkpoints above
- it does **not** claim a broader preventive sandbox over adapter-side remote,
  PR, or network activity beyond the local tuple it can actually measure

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

The learning store turns recovery_log.json into an adaptive system. It sits on
top of the existing logging infrastructure and adds pattern promotion,
cross-session persistence, and prompt warming. It does **not** expand write,
validator, or governance authority.

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

1. **Bootstrap paradox** — Tier 3 diagnosis still stays outside the full bridge/meta-review loop. The hybrid branch may lazy-load `phase_b_implementer` only after payload validation and recovery-owned baseline capture, and it may not target bridge / adapter / implementer bootstrap surfaces.
2. **Infinite loops** — 2-attempt bound per (wave, step, class). Never retry terminal policy outcomes.
3. **Masking real bugs** — Recovery may modify source code only through bounded `edit` or the gated `delegate_implementer` branch. It may not skip validation or treat prompt text as proof of scope control.
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
